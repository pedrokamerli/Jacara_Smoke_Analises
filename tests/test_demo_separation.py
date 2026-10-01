"""Garantias de separação da demo e da geração real."""
import copy
import hashlib
import json
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from jacare_analytics.demo import prepare_demo
from jacare_analytics.pipeline import PROJECT_ROOT, run_pipeline
from jacare_analytics.runtime_config import load_runtime_config, validate_public_manifest


class DemoSeparationTests(unittest.TestCase):
    def test_public_pages_work_without_private_data_access(self):
        from streamlit.testing.v1 import AppTest
        if not (PROJECT_ROOT/"demo/public/current_run.json").exists():
            self.skipTest("Gere a demo")
        with patch.dict(os.environ, {"JACARE_PUBLIC_MODE":"true", "JACARE_PUBLIC_DATA_DIR":str(PROJECT_ROOT/"demo/public")}):
            with patch("duckdb.connect", side_effect=AssertionError("Demo não pode abrir o banco real")):
                app = AppTest.from_file(str(PROJECT_ROOT/"app/streamlit_app.py"), default_timeout=30).run()
                for page in app.sidebar.radio[0].options:
                    app.sidebar.radio[0].set_value(page).run()
                    self.assertFalse(app.exception, [error.message for error in app.exception])
                    self.assertTrue(any("DEMONSTRAÇÃO" in item.value for item in app.info))
                    self.assertFalse(app.get("file_uploader"))
                    self.assertFalse(app.sidebar.date_input)

    def test_generator_does_not_read_files_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory)/"a", Path(directory)/"b"
            with patch.object(Path, "read_bytes", side_effect=AssertionError("Não ler fontes")), patch.object(Path, "read_text", side_effect=AssertionError("Não ler fontes")):
                prepare_demo(a)
                prepare_demo(b)
            for relative in ["daily_sales_ml.csv", "orders.parquet", "items.parquet"]:
                self.assertEqual(a.joinpath(relative).read_bytes(), b.joinpath(relative).read_bytes())

    def test_demo_cannot_replace_real_workspace(self):
        with self.assertRaises(ValueError):
            run_pipeline({}, project_root=PROJECT_ROOT, demo=True)

    def test_real_or_unclassified_package_is_rejected_even_when_approved(self):
        config = load_runtime_config(PROJECT_ROOT, {"JACARE_PUBLIC_MODE":"true"})
        if not config.current_manifest_path.exists():
            self.skipTest("Demo não gerada")
        manifest = json.loads(config.current_manifest_path.read_text(encoding="utf-8"))
        validate_public_manifest(manifest, config)
        for kind in ("real_confidential", None):
            modified = copy.deepcopy(manifest)
            modified["dataset_kind"] = kind
            with self.assertRaises(ValueError):
                validate_public_manifest(modified, config)

    def test_demo_series_and_predictions_are_separate_from_real(self):
        real_path = PROJECT_ROOT/"data/current_run.json"
        demo_path = PROJECT_ROOT/"demo/public/current_run.json"
        if not real_path.exists() or not demo_path.exists():
            self.skipTest("Requer ambas as gerações locais")
        real = json.loads(real_path.read_text(encoding="utf-8"))
        demo = json.loads(demo_path.read_text(encoding="utf-8"))
        self.assertNotEqual(real["series_sha256"], demo["series_sha256"])
        self.assertNotEqual(real["source_end"], demo["source_end"])
        self.assertNotEqual(hashlib.sha256((PROJECT_ROOT/real["forecast_metrics"]).read_bytes()).hexdigest(), demo["artifact_sha256"]["ml/forecast_metrics.json"])


if __name__ == "__main__":
    unittest.main()
