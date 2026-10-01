"""Valida a imagem pública já implantada sem usar base privada."""
import json
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest
from jacare_analytics.runtime_config import load_runtime_config, validate_public_manifest

root = Path("/app")
assert os.environ.get("JACARE_PUBLIC_MODE") == "true"
assert not (root/"data").exists()
assert not (root/".streamlit/secrets.toml").exists()
config = load_runtime_config(root)
manifest = json.loads(config.current_manifest_path.read_text())
validate_public_manifest(manifest, config)
app = AppTest.from_file(str(root/"app/streamlit_app.py"), default_timeout=60).run()
pages = app.sidebar.radio[0].options
assert len(pages) == 8 and "Atualizar dados" not in pages
for page in pages:
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception, [error.message for error in app.exception]
    assert not app.get("file_uploader")
    assert any("DEMONSTRAÇÃO" in info.value for info in app.info)
    print("OK:", page)
print("Imagem pública validada: sem dados privados, sem credenciais, oito telas sintéticas.")
