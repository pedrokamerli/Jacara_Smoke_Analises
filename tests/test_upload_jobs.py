import io
import json
import os
import tempfile
import time
import unittest
import zipfile
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from jacare_analytics.authentication import authorized_import_admin
from jacare_analytics.runtime_config import load_runtime_config
from jacare_analytics.source_files import SourceFile, collect_local, collect_uploads, logical_name, validate_payload
from jacare_analytics.upload_jobs import atomic_json, cleanup_inputs, job_path, list_jobs, load_bundle, set_status, submit_job, timestamp
from jacare_analytics.upload_worker import freeze_forecast, process_job, publish_snapshot

ROOT=Path(__file__).resolve().parents[1]

class UploadAuthorizationTests(unittest.TestCase):
    def setUp(self):
        now=time.time()
        self.claims={"iss":"https://accounts.google.com","sub":"qa-subject","email":"admin@example.com","email_verified":True,"iat":now-1,"exp":now+1800}
        self.access={"allowed_emails":["admin@example.com","viewer@example.com"],"admin_emails":["admin@example.com"]}

    def test_admin_is_explicit_and_also_requires_reader_authorization(self):
        self.assertTrue(authorized_import_admin(self.claims,self.access))
        self.assertFalse(authorized_import_admin(self.claims,{**self.access,"admin_emails":[]}))
        self.assertFalse(authorized_import_admin(self.claims,{**self.access,"allowed_emails":["viewer@example.com"]}))
        self.assertFalse(authorized_import_admin({**self.claims,"email":"viewer@example.com"},self.access))
        self.assertFalse(authorized_import_admin({**self.claims,"exp":time.time()-1},self.access))

    def test_public_ignores_queue_and_private_database_remains_read_only(self):
        public=load_runtime_config(ROOT,{"JACARE_PUBLIC_MODE":"true","JACARE_IMPORT_QUEUE":"/imports"})
        self.assertFalse(public.queued_imports_enabled)
        private=load_runtime_config(ROOT,{"JACARE_PUBLIC_MODE":"false","JACARE_READ_ONLY":"true","JACARE_IMPORT_QUEUE":str(ROOT/"data/private/test_queue")})
        self.assertTrue(private.queued_imports_enabled)
        self.assertFalse(private.imports_enabled)

    def test_explicit_all_readers_policy_still_rejects_outsiders_and_expired_sessions(self):
        access={**self.access,"uploads_for_all_allowed":True}
        self.assertTrue(authorized_import_admin({**self.claims,"email":"viewer@example.com"},access))
        self.assertFalse(authorized_import_admin({**self.claims,"email":"outsider@example.com"},access))
        self.assertFalse(authorized_import_admin({**self.claims,"exp":time.time()-1},access))
        self.assertFalse(authorized_import_admin({**self.claims,"email":"viewer@example.com"},{**access,"uploads_for_all_allowed":"true"}))

    def test_viewer_has_no_upload_menu_and_admin_has_no_server_folder_browser(self):
        env={"JACARE_PUBLIC_MODE":"false","JACARE_AUTH_MODE":"oidc","JACARE_READ_ONLY":"true","JACARE_IMPORT_QUEUE":str(ROOT/"data/private/test_queue")}
        for email,admin in [("viewer@example.com",False),("admin@example.com",True)]:
            user=SimpleNamespace(is_logged_in=True,to_dict=lambda:{**self.claims,"email":email})
            with patch.dict(os.environ,env),patch("streamlit.user",user),patch("streamlit.secrets",{"access":self.access}),patch("jacare_analytics.authentication.enforce_private_access"):
                app=AppTest.from_file(str(ROOT/"app/streamlit_app.py"),default_timeout=60).run()
                self.assertFalse(app.exception)
                self.assertEqual("Atualizar dados" in app.sidebar.radio[0].options,admin)
                if admin:
                    app.sidebar.radio[0].set_value("Atualizar dados").run()
                    self.assertFalse(app.exception)
                    self.assertTrue(app.get("file_uploader"))
                    self.assertFalse(app.text_input)
                    self.assertFalse(app.metric)


class ArchiveValidationTests(unittest.TestCase):
    def test_updated_export_dates_are_recognized(self):
        cases={"01_Todos_os_pedidos_01-01_a_30-09-2026.xlsx":"orders","02_Historico_Itens_Vendidos_01-01_a_30-09-2026.xlsx":"items","Pedidos_AppDelivery_01-01_a_30-09-2026.xlsx":"appdelivery","_Dados do pedido(01-07-2026_30-09-2026).xlsx":"food99"}
        for name,key in cases.items(): self.assertEqual(logical_name(name),key)

    def test_spoofed_xlsx_is_rejected(self):
        with self.assertRaises(ValueError): validate_payload("01_Todos_os_pedidos_09.xlsx",b"not a spreadsheet")

    def test_zip_traversal_and_links_are_rejected(self):
        for name,attr in [("../stolen.csv",0),("link",0o120777<<16),("C:/file.csv",0)]:
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,"w") as archive:
                info=zipfile.ZipInfo(name)
                info.external_attr=attr
                archive.writestr(info,b"payload")
            with self.assertRaises(ValueError): collect_uploads([("report.zip",buffer.getvalue())])

    def test_no_user_path_can_select_a_job_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            for value in ("../data","/imports","", "a"*31):
                with self.assertRaises(ValueError): job_path(Path(folder),value)


@unittest.skipUnless((ROOT/"data/current_run.json").exists(),"Fontes reais ausentes")
class RealUploadQueueTests(UploadAuthorizationTests):
    @classmethod
    def setUpClass(cls): cls.bundle=collect_local(ROOT)

    def test_enqueue_integrity_single_job_and_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            queue=Path(folder)
            atomic_json(queue/"heartbeat.json",{"at":timestamp()})
            job=submit_job(queue,self.bundle,date(2026,8,19),self.claims,self.access)
            loaded,cutoff=load_bundle(queue/job)
            self.assertEqual({k:v.sha256 for k,v in loaded.items()},{k:v.sha256 for k,v in self.bundle.items()})
            self.assertEqual(cutoff,date(2026,8,19))
            with self.assertRaises(ValueError): submit_job(queue,self.bundle,cutoff,self.claims,self.access)
            cleanup_inputs(queue/job)
            self.assertFalse(list((queue/job).glob("*.bin")))
            self.assertFalse((queue/job/"request.json").exists())
            self.assertEqual(list_jobs(queue)[0]["state"],"queued")

    def test_viewer_cannot_enqueue_even_with_a_complete_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(PermissionError): submit_job(Path(folder),self.bundle,date(2026,8,19),{**self.claims,"email":"viewer@example.com"},self.access)
            self.assertFalse(list(Path(folder).iterdir()))

    def test_worker_failure_preserves_current_manifest_and_original_forecast(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            data=root/"data"
            manifest=json.loads((ROOT/"data/current_run.json").read_text())
            forecast=root/manifest["forecast_metrics"]
            forecast.parent.mkdir(parents=True)
            forecast.write_bytes((ROOT/manifest["forecast_metrics"]).read_bytes())
            atomic_json(data/"current_run.json",manifest)
            before=(data/"current_run.json").read_bytes()
            queue=root/"queue"
            atomic_json(queue/"heartbeat.json",{"at":timestamp()})
            job=submit_job(queue,self.bundle,date(2026,8,19),self.claims,self.access)
            key=root/"key"
            key.write_text("q"*64)
            with patch("jacare_analytics.upload_worker.run_pipeline",side_effect=RuntimeError("test processing failure")):
                process_job(ROOT,queue,data,job,key)
            self.assertEqual((data/"current_run.json").read_bytes(),before)
            archived=list((data/"forecast_archive").glob("*.json"))
            self.assertEqual(len(archived),1)
            original=json.loads(archived[0].read_text())
            freeze_forecast(data,manifest)
            self.assertEqual(json.loads(archived[0].read_text()),original)
            self.assertEqual(list_jobs(queue)[0]["state"],"failed")
            self.assertFalse(list((queue/job).glob("*.bin")))
            self.assertFalse((queue/job/"work").exists())

    def test_month_only_is_not_published_over_cumulative_history(self):
        manifest=json.loads((ROOT/"data/current_run.json").read_text())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for change in ({"source_start":"2026-09-01"},{"source_end":"2026-07-31"},{"quality":{**manifest["quality"],"paid_orders":0}}):
                with self.assertRaises(ValueError): publish_snapshot(ROOT,root/"data",{**manifest,**change},manifest,"a"*32)
            self.assertFalse((root/"data/current_run.json").exists())
