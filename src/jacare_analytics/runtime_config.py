"""Limites de execução: exposição pública falha fechada e nunca lê a geração privada."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping

PUBLIC_ARTIFACTS = frozenset({
    "analysis/analysis_results.json", "analysis/analysis_report.md", "ml/forecast_metrics.json",
})
PUBLIC_MANIFEST_KEYS = frozenset({
    "schema_version", "public_schema_version", "publication_approved", "aggregation_only",
    "minimum_group_size", "run_id", "updated_at_utc", "cutoff", "source_start", "source_end",
    "quality", "series_sha256", "forecast_metrics", "analysis_report", "analysis_results",
    "artifact_sha256", "publication_policy", "dbt_models_built", "dbt_tests_passed",
    "dataset_kind",
})
PRIVATE_DIRECTORIES = frozenset({"private", "raw", "runs", "processed", "interim"})


@dataclass(frozen=True)
class RuntimeConfig:
    project_root: Path
    public_mode: bool
    data_root: Path
    read_only: bool = False
    import_queue: Path | None = None

    @property
    def queued_imports_enabled(self) -> bool:
        return not self.public_mode and self.import_queue is not None

    @property
    def imports_enabled(self) -> bool:
        return not self.public_mode and not self.read_only

    @property
    def current_manifest_path(self) -> Path:
        return self.data_root / "current_run.json"

    def resolve_artifact(self, relative_path: str) -> Path:
        """Resolve somente um arquivo autorizado; bloqueia traversal, drives e links externos."""
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError("Caminho de artefato inválido.")
        posix = PurePosixPath(relative_path)
        windows = PureWindowsPath(relative_path)
        if posix.is_absolute() or windows.drive or windows.is_absolute() or "\\" in relative_path or ".." in posix.parts:
            raise ValueError("O artefato precisa ter um caminho relativo seguro.")
        if self.public_mode:
            if relative_path not in PUBLIC_ARTIFACTS:
                raise ValueError("Artefato não permitido no modo público.")
            base, permitted = self.data_root, self.data_root
        else:
            base, permitted = self.project_root, self.project_root / "data/runs"
        path = (base / relative_path).resolve()
        if not path.is_relative_to(permitted.resolve()) or not path.is_file():
            raise ValueError("Artefato ausente ou fora do diretório permitido.")
        return path


def load_runtime_config(project_root: Path, environ: Mapping[str, str] | None = None) -> RuntimeConfig:
    env = os.environ if environ is None else environ
    setting = env.get("JACARE_PUBLIC_MODE", "true").strip().lower()
    if setting not in {"true", "false"}:
        raise ValueError("JACARE_PUBLIC_MODE deve ser true ou false; valores ambíguos são bloqueados.")
    root = project_root.resolve()
    public = setting == "true"
    if not public:
        read_only = env.get("JACARE_READ_ONLY", "false").strip().lower()
        if read_only not in {"true", "false"}:
            raise ValueError("Modo de leitura inválido")
        queue = env.get("JACARE_IMPORT_QUEUE", "").strip()
        queue_path = Path(queue) if queue else None
        if queue_path is not None and (not queue_path.is_absolute() or queue_path == root):
            raise ValueError("Fila de importação inválida")
        return RuntimeConfig(root, False, root / "data", read_only == "true", queue_path)
    configured = Path(env.get("JACARE_PUBLIC_DATA_DIR", str(root / "demo/public")))
    directory = (configured if configured.is_absolute() else root / configured).resolve()
    # A VPS não deve apontar para um pacote de origem, uma geração completa ou o segredo HMAC.
    forbidden = [root / "data" / name for name in PRIVATE_DIRECTORIES]
    forbidden += [root / "jacare anaise perfil", root / "JACARE_SMOKE_HOUSE_PEDIDOS_E_RELATORIOS_ORGANIZADOS_2026"]
    if directory == root or directory == root / "data" or any(directory.is_relative_to(path.resolve()) for path in forbidden):
        raise ValueError("O modo público exige um diretório separado de exportação agregada.")
    return RuntimeConfig(root, True, directory)


def require_local_import(config: RuntimeConfig) -> None:
    if not config.imports_enabled:
        raise PermissionError("Importação e acesso a pastas locais estão desabilitados no modo público.")


def validate_public_manifest(manifest: dict, config: RuntimeConfig) -> None:
    """Atesta o contrato e a integridade do pacote; não substitui revisão humana de privacidade."""
    if not config.public_mode:
        raise ValueError("A validação pública exige o modo público.")
    if not isinstance(manifest, dict) or set(manifest) - PUBLIC_MANIFEST_KEYS:
        raise ValueError("O manifesto público contém campos não autorizados.")
    if manifest.get("public_schema_version") != 1 or manifest.get("schema_version") != 1:
        raise ValueError("Formato de publicação não reconhecido.")
    if manifest.get("dataset_kind") != "synthetic":
        raise ValueError("Somente a demonstração sintética pode ser publicada. Dados reais são confidenciais.")
    if manifest.get("publication_approved") is not True:
        raise ValueError("A exportação ainda não recebeu aprovação de publicação do responsável pelo negócio.")
    minimum = manifest.get("minimum_group_size")
    if manifest.get("aggregation_only") is not True or isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 5:
        raise ValueError("A publicação precisa conter somente agregados e exigir grupos de pelo menos cinco.")
    if (manifest.get("analysis_report"), manifest.get("analysis_results"), manifest.get("forecast_metrics")) != (
        "analysis/analysis_report.md", "analysis/analysis_results.json", "ml/forecast_metrics.json",
    ):
        raise ValueError("O pacote público deve conter somente os três artefatos definidos.")
    quality = manifest.get("quality", {})
    if quality.get("all_passed") is not True or not quality.get("checks") or not all(value is True for value in quality["checks"].values()):
        raise ValueError("O pacote não possui verificações de qualidade aprovadas.")
    hashes = manifest.get("artifact_sha256", {})
    if set(hashes) != PUBLIC_ARTIFACTS:
        raise ValueError("Faltam hashes dos artefatos públicos.")
    permitted_members = PUBLIC_ARTIFACTS | {"current_run.json", "analysis", "ml"}
    for member in config.data_root.rglob("*"):
        if member.is_symlink() or member.relative_to(config.data_root).as_posix() not in permitted_members:
            raise ValueError("O diretório público contém dados extras ou links; monte somente o pacote exportado.")
    for relative_path in PUBLIC_ARTIFACTS:
        expected = hashes[relative_path]
        if not isinstance(expected, str) or len(expected) != 64 or hashlib.sha256(config.resolve_artifact(relative_path).read_bytes()).hexdigest() != expected:
            raise ValueError("Falha de integridade no pacote público; revise a exportação antes de expor o painel.")
