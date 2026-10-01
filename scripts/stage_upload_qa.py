"""Prepara apenas fontes reais oficiais para um teste privado e isolado."""
from pathlib import Path
import json
from jacare_analytics.source_files import collect_local

root=Path(__file__).resolve().parents[1]
target=root/"data/private/upload_qa_inputs"
target.mkdir(parents=True,exist_ok=False)
files={}
for index,(key,source) in enumerate(sorted(collect_local(root).items())):
    name=f"source_{index:02d}.bin"
    (target/name).write_bytes(source.payload)
    files[key]={"name":source.name,"stored":name}
(target/"sources.json").write_text(json.dumps(files,ensure_ascii=False),encoding="utf-8")
print("Pacote privado de QA preparado a partir das fontes oficiais reais. Não publicar no Git.")
