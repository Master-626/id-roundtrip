"""Pytest coverage for value-free difference labels and report aliasing."""
import csv
import json
from pathlib import Path

from id_roundtrip import DIFFERENCE_KINDS, audit

ROOT = Path(__file__).resolve().parents[1]


def write_pair(tmp_path, left, right, *, key="k"):
    reference = tmp_path / "reference.csv"
    observed = tmp_path / "observed.csv"
    for path, value in ((reference, left), (observed, right)):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["key", "id"])
            writer.writerow([key, value])
    return reference, observed


def kind_of(tmp_path, left, right):
    reference, observed = write_pair(tmp_path, left, right)
    report = audit(reference, observed, keys=["key"], fields=["id"])
    assert report["blank_identifier_cells"] == [] or left.strip() == "" or right.strip() == ""
    assert len(report["changed_cells"]) == 1
    cell = report["changed_cells"][0]
    assert set(cell) == {"field", "reference_record", "observed_record", "kind"}
    assert cell["kind"] in DIFFERENCE_KINDS
    return cell["kind"]


def test_difference_kinds_are_textual_and_closed(tmp_path):
    cases = {
        ("00123", "123"): "leading_zeros",
        ("00", "0"): "leading_zeros",
        ("010", "10"): "leading_zeros",
        ("001", "002"): "replaced",
        ("1E10", "10000000000"): "replaced",
        ("00A", "A"): "replaced",
        ("+001", "1"): "replaced",
        (" 001 ", "1"): "replaced",
        ("ABC", "ABC "): "whitespace",
        ("A B", "A  B"): "replaced",
        ("a", "A"): "case",
        ("é", "É"): "case",
        ("straße", "STRASSE"): "replaced",
        ("NA", ""): "blanked",
        ("001", "   "): "blanked",
        ("é", "e\u0301"): "normalization",
        ("É", "e\u0301"): "replaced",
        ("SEPT2", "2-Sep"): "replaced",
    }
    for (left, right), expected in cases.items():
        assert kind_of(tmp_path, left, right) == expected


def test_blank_and_changed_entries_are_distinct_objects(tmp_path):
    reference, observed = write_pair(tmp_path, "NA", "")
    report = audit(reference, observed, keys=["key"], fields=["id"])
    assert len(report["changed_cells"]) == 1
    assert len(report["blank_identifier_cells"]) == 1
    changed = report["changed_cells"][0]
    blank = report["blank_identifier_cells"][0]
    assert changed is not blank
    changed["kind"] = "mutated"
    assert "kind" not in blank
    assert blank == {"field": "id", "reference_record": 1, "observed_record": 1}


def test_unchanged_blank_is_not_a_change(tmp_path):
    reference, observed = write_pair(tmp_path, " ", " ")
    report = audit(reference, observed, keys=["key"], fields=["id"])
    assert report["ok"] is False
    assert report["changed_cells"] == []
    assert len(report["blank_identifier_cells"]) == 1
    assert "kind" not in report["blank_identifier_cells"][0]


def test_kind_labels_do_not_reveal_identifier_text(tmp_path):
    sentinel = "ZZSECRET99"
    reference, observed = write_pair(tmp_path, sentinel, sentinel.lower(), key="QQKEY88")
    report = audit(reference, observed, keys=["key"], fields=["id"])
    blob = json.dumps(report)
    assert sentinel not in blob
    assert sentinel.lower() not in blob
    assert "QQKEY88" not in blob
    assert report["changed_cells"][0]["kind"] == "case"


def test_bundled_example_labels_four_cells_without_values():
    report = audit(
        ROOT / "examples" / "reference.csv",
        ROOT / "examples" / "changed.csv",
        keys=["row_key"],
        fields=["sample_id", "barcode"],
    )
    assert report["schema_version"] == 2
    assert report["ok"] is False
    assert report["reference_rows"] == 2
    assert report["matched_rows"] == 2
    kinds = sorted(cell["kind"] for cell in report["changed_cells"])
    assert kinds == ["leading_zeros", "leading_zeros", "replaced", "replaced"]
    visible = json.dumps({
        "changed_cells": report["changed_cells"],
        "blank_identifier_cells": report["blank_identifier_cells"],
        "keys": report["keys"],
        "fields": report["fields"],
    })
    for secret in ("00123", "SEPT2", "00987", "2-Sep", "12345678901234567", "12345678901234500"):
        assert secret not in visible


def test_multiline_records_are_numbered_once(tmp_path):
    reference = tmp_path / "reference.csv"
    observed = tmp_path / "observed.csv"
    reference.write_text('key,id\nx,"A\nB"\ny,C\n', encoding="utf-8")
    observed.write_text('key,id\ny,CHANGED\nx,"A\nB"\n', encoding="utf-8")
    report = audit(reference, observed, keys=["key"], fields=["id"])
    assert report["changed_cells"] == [{
        "field": "id",
        "reference_record": 2,
        "observed_record": 1,
        "kind": "replaced",
    }]
    assert "CHANGED" not in json.dumps(report["changed_cells"])
