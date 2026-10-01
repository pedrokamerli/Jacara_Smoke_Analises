"""Inventaria cabeçalhos e abas em ZIPs sem exibir linhas de dados.

O comando percorre ZIPs aninhados e lê apenas metadados de CSV/XLSX.
Ele não extrai os arquivos de origem nem escreve dados de clientes no relatório.
"""

from __future__ import annotations

import argparse
import csv
import io
import itertools
import posixpath
import zipfile
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

MAX_NESTING = 5
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _safe_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ").strip()


def _archive_name(value: str) -> str:
    """Repair ZIPs whose UTF-8 filenames were stored without the UTF-8 flag."""
    try:
        repaired = value.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return repaired if "\ufffd" not in repaired else value


def _read_csv_header(payload: bytes) -> tuple[str, list[str]]:
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = payload.decode("utf-16")
        encoding = "UTF-16"
    else:
        try:
            text = payload.decode("utf-8-sig")
            encoding = "UTF-8"
        except UnicodeDecodeError:
            text = payload.decode("cp1252")
            encoding = "Windows-1252"

    rows = []
    for row in itertools.islice(csv.reader(io.StringIO(text), delimiter=","), 3):
        if row and not row[0].strip().lower().startswith("sep="):
            rows.append(row)
    if not rows:
        return encoding, []

    # Exports may put a report title before the header. Inspect at most three
    # logical records and keep the widest; ties keep the earliest row.
    header = max(rows, key=len)
    return encoding, [_safe_text(column) for column in header]


def _xlsx_sheets_and_headers(payload: bytes) -> list[tuple[str, list[str]]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as workbook:
        names = set(workbook.namelist())
        workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
        rel_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
        relationships = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in rel_root.findall(f"{{{PKG_REL_NS}}}Relationship")
        }

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for item in root.findall(f"{{{MAIN_NS}}}si"):
                shared_strings.append(
                    "".join(
                        part.text or ""
                        for part in item.iter(f"{{{MAIN_NS}}}t")
                    )
                )

        sheets: list[tuple[str, list[str]]] = []
        for sheet in workbook_root.findall(f".//{{{MAIN_NS}}}sheet"):
            title = _safe_text(sheet.attrib.get("name", "(sem nome)"))
            relation_id = sheet.attrib.get(f"{{{REL_NS}}}id", "")
            target = relationships.get(relation_id, "")
            if not target:
                sheets.append((title, []))
                continue
            sheet_path = (
                target.lstrip("/")
                if target.startswith("/")
                else posixpath.normpath(posixpath.join("xl", target))
            )
            if sheet_path not in names:
                sheets.append((title, []))
                continue

            root = ET.fromstring(workbook.read(sheet_path))
            headers: list[str] = []
            sheet_data = root.find(f".//{{{MAIN_NS}}}sheetData")
            candidate_rows = [] if sheet_data is None else sheet_data.findall(f"{{{MAIN_NS}}}row")[:3]

            def cell_text(cell: ET.Element) -> str:
                value = cell.find(f"{{{MAIN_NS}}}v")
                inline = cell.find(f"{{{MAIN_NS}}}is")
                raw = ""
                if inline is not None:
                    raw = "".join(
                        part.text or ""
                        for part in inline.iter(f"{{{MAIN_NS}}}t")
                    )
                elif value is not None and value.text is not None:
                    raw = value.text
                    if cell.attrib.get("t") == "s":
                        try:
                            raw = shared_strings[int(raw)]
                        except (ValueError, IndexError):
                            raw = ""
                return _safe_text(raw)

            parsed_rows = [
                [cell_text(cell) for cell in row.findall(f"{{{MAIN_NS}}}c")]
                for row in candidate_rows
            ]
            if parsed_rows:
                headers = max(parsed_rows, key=lambda row: sum(bool(value) for value in row))
            sheets.append((title, headers))
        return sheets


def _walk_zip(
    payload: bytes,
    label: str,
    depth: int = 0,
) -> Iterator[tuple[str, str, str, list[tuple[str, list[str]]]]]:
    if depth > MAX_NESTING:
        yield (label, "ZIP", "limite de profundidade", [])
        return

    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile:
        yield (label, "ZIP", "arquivo ZIP inválido", [])
        return

    with archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_name = _archive_name(member.filename)
            member_label = f"{label}!/{member_name}"
            suffix = Path(member_name).suffix.lower()
            if suffix not in {".zip", ".xlsx", ".csv"}:
                continue
            if member.file_size > MAX_MEMBER_BYTES:
                yield (member_label, suffix[1:].upper(), "ignorado: acima de 100 MiB", [])
                continue

            content = archive.read(member)
            if suffix == ".zip":
                yield from _walk_zip(content, member_label, depth + 1)
            elif suffix == ".csv":
                try:
                    encoding, columns = _read_csv_header(content)
                    yield (member_label, "CSV", f"codificação {encoding}", [("CSV", columns)])
                except (UnicodeDecodeError, csv.Error) as exc:
                    yield (member_label, "CSV", f"não foi possível ler cabeçalho: {type(exc).__name__}", [])
            else:
                try:
                    sheets = _xlsx_sheets_and_headers(content)
                    yield (member_label, "XLSX", "cabeçalhos apenas", sheets)
                except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
                    yield (member_label, "XLSX", f"não foi possível ler metadados: {type(exc).__name__}", [])


def build_report(archives: list[Path]) -> str:
    lines = [
        "# Inventário automático das fontes",
        "",
        "> Gerado sem extrair arquivos. O relatório contém somente nomes de arquivos, abas e cabeçalhos; não inclui valores de registros.",
        "",
    ]
    for archive_path in archives:
        lines.extend([f"## `{archive_path.name}`", ""])
        try:
            payload = archive_path.read_bytes()
        except OSError as exc:
            lines.extend([f"Não foi possível abrir o pacote: `{type(exc).__name__}`.", ""])
            continue
        for label, file_type, note, sheets in _walk_zip(payload, archive_path.name):
            lines.append(f"### `{label}` ({file_type})")
            lines.append("")
            lines.append(f"- Leitura: {note}.")
            for sheet_name, columns in sheets:
                lines.append(f"- Aba `{sheet_name}`; {len(columns)} colunas.")
                if columns:
                    lines.append("  - Cabeçalho: " + " | ".join(f"`{column}`" for column in columns))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lista arquivos, abas e cabeçalhos em ZIPs, sem exibir registros."
    )
    parser.add_argument(
        "archives",
        nargs="*",
        type=Path,
        help="Pacotes ZIP; por padrão, procura ZIPs na pasta atual.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/inventario_automatico.md"),
        help="Arquivo Markdown de saída (padrão: docs/inventario_automatico.md).",
    )
    args = parser.parse_args()
    archives = args.archives or sorted(Path.cwd().glob("*.zip"))
    report = build_report(archives)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Inventário salvo em {args.output} ({len(archives)} pacotes).")


if __name__ == "__main__":
    main()
