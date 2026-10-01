import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import duckdb
from scripts.package_private_data import portable_warehouse


class PrivateSnapshotTests(unittest.TestCase):
    def test_view_becomes_portable_table(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv = root / "input.csv"
            csv.write_text("quantity\n2\n3\n", encoding="utf-8")
            source, target = root / "source.duckdb", root / "snapshot.duckdb"
            with duckdb.connect(str(source)) as db:
                db.execute("create schema analytics")
                name = csv.as_posix().replace("'", "''")
                db.execute(f"create view analytics.example as select * from read_csv_auto('{name}')")
            with patch("scripts.package_private_data.TABLES", frozenset({"example"})):
                portable_warehouse(source, target)
            csv.unlink()
            with duckdb.connect(str(target), read_only=True) as db:
                self.assertEqual(db.execute("select sum(quantity) from analytics.example").fetchone()[0], 5)
                self.assertEqual(db.execute("select table_type from information_schema.tables where table_schema='analytics'").fetchone()[0], "BASE TABLE")
            with self.assertRaises(ValueError):
                portable_warehouse(source, target)

    def test_unexpected_models_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "source.duckdb", Path(directory) / "snapshot.duckdb"
            with duckdb.connect(str(source)) as db:
                db.execute("create schema analytics")
                db.execute("create table analytics.unexpected as select 1 as value")
            with self.assertRaises(ValueError):
                portable_warehouse(source, target)
