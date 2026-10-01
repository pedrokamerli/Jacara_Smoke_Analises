import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from jacare_analytics.authentication import authorized_google_user


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.claims = dict(iss="https://accounts.google.com", sub="test-subject", email="owner@example.com", email_verified=True, iat=1000, exp=4600)
        self.access = dict(allowed_emails=["owner@example.com"], max_session_seconds=3600)

    def test_verified_allowed_account(self):
        self.assertTrue(authorized_google_user(self.claims, self.access, 2000))

    def test_wrong_or_missing_claims_are_rejected(self):
        for key, value in [("iss", "https://attacker.invalid"), ("sub", ""), ("email", "other@example.com"), ("email_verified", False), ("email_verified", "true"), ("exp", None), ("iat", float("nan"))]:
            with self.subTest(key=key):
                self.assertFalse(authorized_google_user({**self.claims, key:value}, self.access, 2000))

    def test_expired_future_and_excessively_long_session(self):
        for instant in (999, 4600, 5000):
            self.assertFalse(authorized_google_user(self.claims, self.access, instant))
        self.assertFalse(authorized_google_user(self.claims, {**self.access, "max_session_seconds":300}, 1400))

    def test_invalid_configuration(self):
        for config in ({}, {"allowed_emails":"owner@example.com"}, {**self.access,"max_session_seconds":True}, {**self.access,"max_session_seconds":86400}):
            self.assertFalse(authorized_google_user(self.claims, config, 2000))

    def test_private_without_credentials_stops_before_data_read(self):
        from streamlit.testing.v1 import AppTest
        root = Path(__file__).resolve().parents[1]
        with patch.dict(os.environ, {"JACARE_PUBLIC_MODE":"false", "JACARE_AUTH_MODE":"oidc"}), patch("streamlit.secrets", {}), patch("duckdb.connect", side_effect=AssertionError("Não ler dados sem login")):
            app = AppTest.from_file(str(root/"app/streamlit_app.py"), default_timeout=30).run()
            self.assertFalse(app.exception, [x.message for x in app.exception])
            self.assertTrue(app.error)
            self.assertFalse(app.metric)
            self.assertFalse(app.get("download_button"))
            self.assertFalse(app.sidebar.radio)


if __name__ == "__main__":
    unittest.main()
