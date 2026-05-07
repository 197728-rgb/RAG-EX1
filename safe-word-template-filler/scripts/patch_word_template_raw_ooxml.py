#!/usr/bin/env python3
"""
Raw OOXML Word template patcher.

Safety model:
- Opens .docx as a ZIP package.
- Reads word/document.xml as raw UTF-8 bytes.
- Verifies exact form markers before writing.
- Uses an explicit approval_map.json for all writable fields.
- Patches only approved values.
- Refuses to infer write locations.

This implementation is intentionally conservative. It supports safe placeholder
replacement and full report generation. Merged-cell visual-grid label patching is
reserved for project-specific hardening and is not inferred automatically.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

TEXT_NODE_RE = re.compile(rb"<w:t(?P<attrs>[^>]*)>(?P<text>.*?)</w:t>", re.DOTALL)
XML_ESCAPE = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&apos;",
}


@dataclass
class FillEvent:
    field: str
    status: str
    message: str
    old_value: str | None = None
    new_value: str | None = None
    marker: str | None = None


@dataclass
class StructureGuard:
    pass_: bool
    document_xml_size_before: int
    document_xml_size_after: int
    text_nodes_before: int
    text_nodes_after: int
    intentional_text_node_creations: int
    text_nodes_delta_expected: int
    text_nodes_delta_actual: int
    text_nodes_delta_matches_expected: bool
    package_parts_preserved: bool
    errors: List[str]

    def to_json(self) -> Dict[str, Any]:
        data = asdict(self)
        data["pass"] = data.pop("pass_")
        return data


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def escape_xml_text(value: str) -> bytes:
    text = "" if value is None else str(value)
    for src, repl in XML_ESCAPE.items():
        text = text.replace(src, repl)
    return text.encode("utf-8")


def unescape_xml_text(value: bytes) -> str:
    text = value.decode("utf-8", errors="replace")
    return (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
        .replace("&amp;", "&")
    )


def read_document_xml(docx_path: Path) -> Tuple[bytes, List[str]]:
    with zipfile.ZipFile(docx_path, "r") as zin:
        names = zin.namelist()
        if "word/document.xml" not in names:
            raise RuntimeError("DOCX missing word/document.xml")
        return zin.read("word/document.xml"), names


def verify_form_markers(document_xml: bytes, approval_map: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    markers = approval_map.get("form_markers") or []
    xml_text = unescape_xml_text(document_xml)
    for marker in markers:
        if marker not in xml_text:
            errors.append(f"Missing required form marker: {marker}")
    return errors


def target_cell_guard(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    if text.endswith(":"):
        return True
    lowered = text.casefold()
    label_words = ["name", "date", "status", "revision", "form", "signature", "approved", "inspector"]
    return len(text) < 80 and any(word in lowered for word in label_words)


def build_placeholder_patterns(field: str, mapping: Dict[str, Any]) -> List[bytes]:
    explicit = mapping.get("placeholder") or mapping.get("marker")
    patterns: List[str] = []
    if explicit:
        patterns.append(str(explicit))
    patterns.extend([
        "{{ " + field + " }}",
        "{{" + field + "}}",
        "[[" + field + "]]",
        "${" + field + "}",
    ])
    return [p.encode("utf-8") for p in dict.fromkeys(patterns)]


def patch_placeholders(document_xml: bytes, evidence: Dict[str, Any], approval_map: Dict[str, Any]) -> Tuple[bytes, List[FillEvent]]:
    patched = bytearray(document_xml)
    events: List[FillEvent] = []
    fields = approval_map.get("fields") or []

    for mapping in fields:
        field = mapping.get("field")
        if not field:
            events.append(FillEvent(field="", status="error", message="Approval-map field entry missing 'field'"))
            continue

        if field not in evidence:
            events.append(FillEvent(field=field, status="preserved", message="Evidence key missing; original DOCX value preserved"))
            continue

        value = evidence.get(field)
        if value is None:
            events.append(FillEvent(field=field, status="missing", message="Evidence value is null; original DOCX value preserved"))
            continue

        value_text = str(value)
        if not value_text.strip() and not mapping.get("explicit_empty_clears"):
            events.append(FillEvent(field=field, status="skipped", message="Empty value ignored because explicit_empty_clears is not enabled"))
            continue

        replacement = escape_xml_text(value_text)
        patterns = build_placeholder_patterns(field, mapping)
        replaced = False

        for pattern in patterns:
            idx = bytes(patched).find(pattern)
            if idx >= 0:
                old_value = unescape_xml_text(pattern)
                if target_cell_guard(old_value) and not mapping.get("allow_label_like_target"):
                    events.append(FillEvent(field=field, status="blocked", message="Target looked label-like/header-like", old_value=old_value, new_value=value_text, marker=old_value))
                    replaced = True
                    break
                patched[idx : idx + len(pattern)] = replacement
                events.append(FillEvent(field=field, status="filled", message="Approved placeholder patched", old_value=old_value, new_value=value_text, marker=old_value))
                replaced = True
                break

        if not replaced:
            label = mapping.get("label")
            events.append(FillEvent(field=field, status="not_found", message=f"No approved placeholder found; label-grid patching not inferred. label={label!r}"))

    return bytes(patched), events


def copy_docx_with_new_document_xml(input_docx: Path, output_docx: Path, new_document_xml: bytes) -> None:
    output_docx.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_docx.with_suffix(output_docx.suffix + ".tmp")
    with zipfile.ZipFile(input_docx, "r") as zin, zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = new_document_xml
            zout.writestr(item, data)
    shutil.move(str(tmp_path), str(output_docx))


def write_fill_csv(path: Path, events: List[FillEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["field", "status", "message", "old_value", "new_value", "marker"])
        writer.writeheader()
        for event in events:
            writer.writerow(asdict(event))


def write_label_debug(path: Path, document_xml: bytes, approval_map: Dict[str, Any]) -> None:
    text_nodes = []
    for index, match in enumerate(TEXT_NODE_RE.finditer(document_xml), start=1):
        text_nodes.append({
            "index": index,
            "text": unescape_xml_text(match.group("text")),
            "start": match.start(),
            "end": match.end(),
        })
    write_json(path, {
        "form_id": approval_map.get("form_id"),
        "form_version": approval_map.get("form_version"),
        "text_nodes_count": len(text_nodes),
        "text_nodes": text_nodes,
    })


def run(args: argparse.Namespace) -> int:
    input_docx = Path(args.input_docx)
    evidence_path = Path(args.evidence_json)
    approval_map_path = Path(args.approval_map)
    output_docx = Path(args.output_docx)
    report_dir = Path(args.report_dir)

    evidence = load_json(evidence_path)
    approval_map = load_json(approval_map_path)

    if not isinstance(evidence, dict):
        raise RuntimeError("evidence.json must be a flat JSON object")
    if any(isinstance(v, (dict, list)) for v in evidence.values()):
        raise RuntimeError("evidence.json must be flat; nested review metadata is not allowed")

    document_xml, _package_parts = read_document_xml(input_docx)
    errors = verify_form_markers(document_xml, approval_map)

    text_nodes_before = len(TEXT_NODE_RE.findall(document_xml))
    if errors:
        events = [FillEvent(field="__form__", status="error", message=err) for err in errors]
        write_json(report_dir / "fill_report.json", [asdict(e) for e in events])
        write_fill_csv(report_dir / "fill_report.csv", events)
        write_label_debug(report_dir / "label_debug_dump.json", document_xml, approval_map)
        guard = StructureGuard(False, len(document_xml), len(document_xml), text_nodes_before, text_nodes_before, 0, 0, 0, True, True, errors)
        write_json(report_dir / "structure_guard_report.json", guard.to_json())
        return 2

    patched_xml, events = patch_placeholders(document_xml, evidence, approval_map)
    text_nodes_after = len(TEXT_NODE_RE.findall(patched_xml))
    expected_delta = 0
    actual_delta = text_nodes_after - text_nodes_before
    guard_errors = [e.message for e in events if e.status in {"error", "blocked"}]
    guard_pass = not guard_errors and actual_delta == expected_delta

    copy_docx_with_new_document_xml(input_docx, output_docx, patched_xml)
    write_json(report_dir / "fill_report.json", [asdict(e) for e in events])
    write_fill_csv(report_dir / "fill_report.csv", events)
    write_label_debug(report_dir / "label_debug_dump.json", patched_xml, approval_map)

    guard = StructureGuard(
        pass_=guard_pass,
        document_xml_size_before=len(document_xml),
        document_xml_size_after=len(patched_xml),
        text_nodes_before=text_nodes_before,
        text_nodes_after=text_nodes_after,
        intentional_text_node_creations=0,
        text_nodes_delta_expected=expected_delta,
        text_nodes_delta_actual=actual_delta,
        text_nodes_delta_matches_expected=(actual_delta == expected_delta),
        package_parts_preserved=True,
        errors=guard_errors,
    )
    write_json(report_dir / "structure_guard_report.json", guard.to_json())
    return 0 if guard_pass else 3


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely patch approved DOCX placeholders using flat evidence JSON and an exact approval map.")
    parser.add_argument("--input-docx", required=True)
    parser.add_argument("--evidence-json", required=True)
    parser.add_argument("--approval-map", required=True)
    parser.add_argument("--output-docx", required=True)
    parser.add_argument("--report-dir", required=True)
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    try:
        return run(parse_args(argv or sys.argv[1:]))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
