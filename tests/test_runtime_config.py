"""Testes dos limites de publicação: somente a demo sintética é pública."""

import copy
import hashlib
import json
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from jacare_analytics.export_public import export_public_snapshot, sanitize_answers, sanitize_metrics
from jacare_analytics.runtime_config import PUBLIC_ARTIFACTS, load_runtime_config, require_local_import, validate_public_manifest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="jacare-runtime-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_is_public_without_local_import(self):
        config = load_runtime_config(self.root, {})
        self.assertTrue(config.public_mode)
        self.assertFalse(config.imports_enabled)
        self.assertEqual(config.current_manifest_path, self.root / "demo/public/current_run.json")
        with self.assertRaises(PermissionError):
            require_local_import(config)

    def test_only_explicit_false_enables_local_import(self):
        config = load_runtime_config(self.root, {"JACARE_PUBLIC_MODE": "false"})
        self.assertFalse(config.public_mode)
        self.assertTrue(config.imports_enabled)
        self.assertEqual(config.current_manifest_path, self.root / "data/current_run.json")
        require_local_import(config)
        for value in ("", "0", "no", "local", "tru", "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_runtime_config(self.root, {"JACARE_PUBLIC_MODE": value})

    def test_public_cannot_point_to_private_or_original_directories(self):
        for relative in (".", "data", "data/private", "data/runs/run", "data/raw", "data/processed", "data/interim", "jacare anaise perfil", "JACARE_SMOKE_HOUSE_PEDIDOS_E_RELATORIOS_ORGANIZADOS_2026"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                load_runtime_config(self.root, {"JACARE_PUBLIC_DATA_DIR": str(self.root / relative)})

    def test_public_paths_are_exact_allowlist_and_existing_files(self):
        config = load_runtime_config(self.root, {})
        for path in ("../../secrets.toml", "C:/private/file.json", "/etc/passwd", "analysis\\analysis_results.json", "data/runs/x/warehouse.duckdb", "ml/forecast_models.joblib", "processed/source_manifest.json"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                config.resolve_artifact(path)
        with self.assertRaises(ValueError):
            config.resolve_artifact("analysis/analysis_report.md")

    def test_local_paths_still_cannot_escape_the_run_directory(self):
        config = load_runtime_config(self.root, {"JACARE_PUBLIC_MODE": "false"})
        with self.assertRaises(ValueError):
            config.resolve_artifact("data/private/hmac.key")
        with self.assertRaises(ValueError):
            config.resolve_artifact("data/runs/../private/hmac.key")

    def contract_package(self):
        # Somente bytes de contrato vazio: nenhum pedido ou cliente de teste é fabricado.
        config = load_runtime_config(self.root, {})
        hashes = {}
        for relative in PUBLIC_ARTIFACTS:
            path = config.data_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"{}")
            hashes[relative] = hashlib.sha256(b"{}").hexdigest()
        manifest = {
            "dataset_kind": "synthetic",
            "schema_version": 1, "public_schema_version": 1, "publication_approved": True,
            "aggregation_only": True, "minimum_group_size": 5,
            "quality": {"all_passed": True, "checks": {"contract": True}},
            "analysis_report": "analysis/analysis_report.md", "analysis_results": "analysis/analysis_results.json",
            "forecast_metrics": "ml/forecast_metrics.json", "artifact_sha256": hashes,
        }
        return config, manifest

    def test_unsigned_publication_and_unapproved_quality_fail_closed(self):
        config, manifest = self.contract_package()
        unsigned = copy.deepcopy(manifest)
        unsigned["publication_approved"] = False
        with self.assertRaises(ValueError):
            validate_public_manifest(unsigned, config)
        failed = copy.deepcopy(manifest)
        failed["quality"]["checks"]["contract"] = False
        with self.assertRaises(ValueError):
            validate_public_manifest(failed, config)

    def test_manifest_private_keys_and_modified_artifact_are_rejected(self):
        config, manifest = self.contract_package()
        validate_public_manifest(manifest, config)
        forbidden = copy.deepcopy(manifest)
        forbidden["warehouse"] = "jacare_analytics.duckdb"
        with self.assertRaises(ValueError):
            validate_public_manifest(forbidden, config)
        (config.data_root / "ml/forecast_metrics.json").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            validate_public_manifest(manifest, config)

    def test_groups_below_five_and_noninteger_threshold_are_rejected(self):
        config, manifest = self.contract_package()
        for value in (4, 4.9, True, "5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_public_manifest({**manifest, "minimum_group_size": value}, config)

    def test_extra_raw_or_serialized_artifact_blocks_the_entire_package(self):
        config, manifest = self.contract_package()
        (config.data_root / "model.joblib").write_bytes(b"no-model-was-serialized")
        with self.assertRaises(ValueError):
            validate_public_manifest(manifest, config)


@unittest.skipUnless((ROOT / "data/current_run.json").exists(), "Requer geração real local.")
class RealPublicationTests(unittest.TestCase):
    def test_monthly_projection_public_contract_keeps_only_estimates_and_rejects_actual_or_private_fields(self):
        manifest = json.loads((ROOT / "data/current_run.json").read_text(encoding="utf-8"))
        metrics = json.loads((ROOT / manifest["forecast_metrics"]).read_text(encoding="utf-8"))
        if not all("monthly_projection" in result for result in metrics.get("targets", {}).values()):
            self.skipTest("Reprocesse a projeção mensal solicitada com os modelos reais.")
        clean, _ = sanitize_metrics(metrics, {})
        for target, result in metrics["targets"].items():
            projection = result["monthly_projection"]
            self.assertEqual(clean["targets"][target]["monthly_projection"], projection)
            self.assertEqual(projection["month"], "2026-09")
            self.assertEqual(projection["forecast_origin"], "2026-08-19")
            self.assertEqual(projection["horizon_from_origin_days"], 42)
            self.assertEqual(projection["bridge_days"], 12)
            self.assertEqual(len(projection["predictions"]), 30)
            self.assertEqual(projection["summary"]["predicted_open_days"], 26)
        contaminated = copy.deepcopy(metrics)
        contaminated["targets"]["paid_orders"]["monthly_projection"]["predictions"][0]["actual"] = None
        with self.assertRaises(ValueError):
            sanitize_metrics(contaminated, {})
        contaminated = copy.deepcopy(metrics)
        contaminated["targets"]["paid_orders"]["monthly_projection"]["summary"]["customer_key"] = "field-name-rejection-only"
        with self.assertRaises(ValueError):
            sanitize_metrics(contaminated, {})

    def test_real_answers_keep_only_permitted_columns_and_safe_groups(self):
        manifest = json.loads((ROOT / "data/current_run.json").read_text(encoding="utf-8"))
        answers = json.loads((ROOT / manifest["analysis_report"]).with_name("analysis_results.json").read_text(encoding="utf-8"))
        clean, omitted = sanitize_answers(answers)
        self.assertEqual([row["id"] for row in clean], list(range(1, 16)))
        self.assertGreaterEqual(omitted, 0)
        self.assertEqual(sum(len(rows) for answer in answers for rows in answer["results"]), sum(len(rows) for answer in clean for rows in answer["results"]) + omitted)
        contaminated = copy.deepcopy(answers)
        contaminated[0]["results"][0][0]["customer_key"] = "field-name-rejection-only"
        with self.assertRaises(ValueError):
            sanitize_answers(contaminated)

    def test_export_candidate_contains_no_private_artifacts_and_is_not_approved(self):
        manifest = json.loads((ROOT / "data/current_run.json").read_text(encoding="utf-8"))
        metrics = json.loads((ROOT / manifest["forecast_metrics"]).read_text(encoding="utf-8"))
        if metrics.get("schema_version") != 4:
            self.skipTest("Reprocesse o experimento ML atualizado antes de exportar.")
        with tempfile.TemporaryDirectory(prefix="jacare-public-candidate-") as directory:
            output = Path(directory) / "snapshot"
            for approved in (False, True):
                with self.assertRaises(ValueError):
                    export_public_snapshot(output, business_approval=approved)
            self.assertFalse(output.exists())

    def test_demo_dashboard_has_eight_readonly_pages_without_import_controls(self):
        if not (ROOT / "demo/public/current_run.json").exists():
            self.skipTest("Gere a demo independente.")
        from streamlit.testing.v1 import AppTest
        output = ROOT / "demo/public"
        with patch.dict(os.environ, {"JACARE_PUBLIC_MODE": "true", "JACARE_PUBLIC_DATA_DIR": str(output)}):
                app = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=30).run()
                self.assertFalse(app.exception, [error.message for error in app.exception])
                pages = app.sidebar.radio[0].options
                self.assertEqual(len(pages), 8)
                self.assertNotIn("Atualizar dados", pages)
                for page in pages:
                    with self.subTest(page=page):
                        app.sidebar.radio[0].set_value(page).run()
                        self.assertFalse(app.exception, [error.message for error in app.exception])
                        self.assertFalse(app.get("file_uploader"))
                        self.assertFalse(app.text_input)
                        self.assertFalse(app.sidebar.date_input)


if __name__ == "__main__":
    unittest.main()
