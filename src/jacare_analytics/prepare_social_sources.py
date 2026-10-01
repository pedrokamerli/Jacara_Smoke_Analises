"""Prepara séries agregadas do Instagram sem importar dados de perfil/público."""

from __future__ import annotations

import argparse
import csv
import io
import json
import unicodedata
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_ARCHIVE = Path("jacare anaise perfil.zip")
METRIC_PREFIXES = {
    "reach": "alcance",
    "link_clicks": "cliques no link",
    "content_interactions": "intera",
    "followers": "seguidores",
    "profile_visits": "visitas",
    "views": "visualiza",
}


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return normalized.encode("ascii", "ignore").decode("ascii")


def _number(value: str) -> float | None:
    raw = value.strip().replace("\u00a0", "")
    if not raw:
        return None
    raw = raw.replace("%", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _select_member(names: list[str], prefix: str) -> str:
    matches = [
        name for name in names
        if name.casefold().endswith(".csv")
        and prefix in _plain(Path(name).name)
        and "insta" in _plain(Path(name).name)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Esperava um CSV de métrica Instagram (`{prefix}`); encontrei {len(matches)}.")
    return matches[0]


def _read_metric(payload: bytes, member: str, metric_key: str) -> list[dict[str, Any]]:
    text = payload.decode("utf-16")
    rows = csv.reader(io.StringIO(text))
    next(rows, None)  # sep=,
    title_row = next(rows, [])
    source_label = title_row[0].strip().strip('"') if title_row else metric_key
    header = next(rows, [])
    if len(header) < 2 or header[0].strip().casefold() != "data" or header[1].strip().casefold() != "primary":
        raise RuntimeError(f"Cabeçalho de série inesperado em {Path(member).name}.")
    records = []
    for line_number, row in enumerate(rows, start=4):
        if not row or not row[0].strip():
            continue
        try:
            event_date = date.fromisoformat(row[0].strip()[:10])
        except ValueError as exc:
            raise RuntimeError(f"Data inválida na linha {line_number} de {Path(member).name}.") from exc
        metric_value = _number(row[1]) if len(row) > 1 else None
        records.append({
            "metric_date": event_date,
            "metric_key": metric_key,
            "source_label": source_label,
            "metric_value": metric_value,
        })
    dates = [record["metric_date"] for record in records]
    if len(dates) != len(set(dates)):
        raise RuntimeError(f"Há mais de um valor por data em {Path(member).name}; revisar antes de agregar.")
    return records


def prepare_social_archive(archive_path: Path, output_dir: Path) -> dict[str, int]:
    records: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        selected = {
            metric: _select_member(names, prefix)
            for metric, prefix in METRIC_PREFIXES.items()
        }
        for metric, member in selected.items():
            records.extend(_read_metric(archive.read(member), member, metric))

    frame = pd.DataFrame.from_records(records)
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = output_dir / "instagram_daily.parquet"
    frame.to_parquet(parquet_path, index=False, engine="pyarrow")
    summary = {
        "source_archive": archive_path.name,
        "parquet": str(parquet_path),
        "series": {
            key: {
                "observations": int((frame["metric_key"] == key).sum()),
                "first_date": frame.loc[frame["metric_key"] == key, "metric_date"].min().isoformat(),
                "last_date": frame.loc[frame["metric_key"] == key, "metric_date"].max().isoformat(),
            }
            for key in METRIC_PREFIXES
        },
    }
    summary_path = Path("data/interim/instagram_prepare_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {key: data["observations"] for key, data in summary["series"].items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara apenas séries diárias agregadas do Instagram.")
    parser.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    counts = prepare_social_archive(args.archive, args.output_dir)
    print("Séries agregadas Instagram preparadas: " + ", ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
