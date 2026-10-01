"""Interface administrativa; processamento nunca acontece no processo Streamlit."""
from datetime import date
import streamlit as st

from .authentication import is_import_admin
from .source_files import collect_uploads
from .upload_jobs import REQUIRED, ROLES, list_jobs, submit_job


@st.fragment(run_every="5s")
def progress_panel(queue):
    if not is_import_admin(False):
        st.warning("Sessão autorizada indisponível ou expirada. Entre novamente para acompanhar.")
        return
    jobs=list_jobs(queue)
    if not jobs:
        st.info("Nenhuma importação enviada neste serviço.")
        return
    labels={"queued":"Aguardando processamento","running":"Processando","complete":"Concluída","failed":"Não aprovada"}
    for job in jobs[:5]:
        with st.container(border=True):
            st.write(labels.get(job["state"],"Indisponível"))
            st.caption(job["step"])
            if job["state"]=="complete":
                st.success("Nova geração aprovada. As páginas de análise já podem usar os dados atualizados.")
                if job.get("source_end"): st.caption("Última data de vendas realmente encontrada: "+job["source_end"])
                if st.button("Recarregar painel",key="reload_"+job["job_id"]): st.rerun()
            elif job["state"]=="failed":
                st.warning("Envie novamente após conferir o pacote. A geração anterior foi preservada.")


def render_upload(runtime,manifest):
    if not runtime.queued_imports_enabled or not is_import_admin(runtime.public_mode):
        st.error("Atualização disponível somente às contas Google autorizadas.")
        return
    st.title("Atualizar dados")
    st.write("Envie o pacote consolidado de relatórios reais. O serviço interno prepara os dados, executa SQL/dbt, auditoria e Machine Learning. A troca da base só acontece se todas as etapas passarem.")
    st.warning("Envie o histórico completo atualizado: janeiro a setembro, não apenas setembro. A importação é uma substituição validada do pacote completo, não uma soma automática de planilhas mensais.")
    st.caption("Você e o proprietário podem enviar com as contas Google já autorizadas. O público não recebe arquivos nem dados reais. As previsões anteriores ficam arquivadas sem alteração para comparação posterior.")
    jobs=list_jobs(runtime.import_queue)
    active=any(job["state"] in {"queued","running"} for job in jobs)
    nonce=st.session_state.get("upload_nonce",0)
    uploads=st.file_uploader("Relatórios oficiais ou ZIPs",type=["zip","xlsx","csv"],accept_multiple_files=True,key=f"admin_upload_{nonce}",disabled=active,help="Até 200 MiB no total; fontes até 100 MiB e limite de descompressão. Nenhum arquivo é executado.")
    cutoff=st.date_input("Última data completa do pacote",value=date.fromisoformat(manifest["cutoff"]) if manifest else date.today(),max_value=date.today(),format="DD/MM/YYYY",disabled=active)
    st.caption("Ao importar setembro completo, selecione 30/09/2026. A data deve refletir a cobertura real, não a data de hoje.")
    with st.expander("Quais arquivos preciso enviar?",expanded=True):
        for role in sorted(REQUIRED): st.write("• "+ROLES[role])
        st.caption("Meta Ads e relatório adicional iFood são opcionais. Se não forem enviados, a nova geração informa ausência dessas fontes; não reutiliza silenciosamente dados antigos. Nomes com datas atualizadas são aceitos, mantendo o formato oficial das planilhas.")
    checked=st.checkbox("Confirmo que o pacote é consolidado e que a data final representa um dia completo",disabled=active)
    if st.button("Enviar e processar atualização",type="primary",disabled=active or not checked or not uploads):
        # Reautorizar nesta ação, inclusive se a sessão expirou depois de abrir a tela.
        if not is_import_admin(False):
            st.error("Sessão autorizada expirada. Faça login novamente.")
            return
        try:
            bundle=collect_uploads(((upload.name,upload.getvalue()) for upload in uploads),updated_dates=True)
            missing=REQUIRED-bundle.keys()
            if missing:
                st.error("Faltam fontes obrigatórias: "+", ".join(ROLES[role] for role in sorted(missing)))
                return
            submit_job(runtime.import_queue,bundle,cutoff,st.user.to_dict(),dict(st.secrets["access"]))
            st.session_state["upload_nonce"]=nonce+1
            st.rerun()
        except (ValueError,PermissionError) as error:
            st.error(str(error))
        except Exception:
            st.error("Não foi possível registrar a importação. A base atual não foi alterada.")
    st.subheader("Andamento das últimas importações")
    st.caption("Atualização automática a cada cinco segundos enquanto esta página estiver aberta. O processamento continua se você fechar o navegador.")
    progress_panel(runtime.import_queue)
