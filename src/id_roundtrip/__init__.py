"""Exact, read-only verification of identifier columns after a CSV round trip."""
import csv
import hashlib
import io
import os
import stat
import unicodedata

__version__ = "0.1.2"

# Closed vocabulary for changed_cells[].kind. Labels describe the text only.
DIFFERENCE_KINDS = frozenset({
    "whitespace",
    "case",
    "blanked",
    "leading_zeros",
    "normalization",
    "replaced",
})


class AuditError(ValueError):
    """Input cannot be audited unambiguously."""


def _columns(values, name):
    if isinstance(values, str):
        raise AuditError(f"{name} must be a sequence, not a string")
    try:
        values = tuple(values)
    except TypeError as exc:
        raise AuditError(f"{name} must be a sequence of column names") from exc
    if not values or any(not isinstance(v, str) or not v.strip() for v in values):
        raise AuditError(f"{name} must contain nonblank column names")
    if len(set(values)) != len(values):
        raise AuditError(f"duplicate {name}")
    return values


def _read(path, keys, fields, delimiter):
    if delimiter not in (",", "\t", ";"):
        raise AuditError("delimiter must be comma, tab, or semicolon")
    # Reject special files before opening; verify the opened descriptor as well.
    # O_NONBLOCK prevents a regular-file-to-FIFO replacement from hanging on POSIX.
    if not stat.S_ISREG(os.stat(path).st_mode):
        raise AuditError("input must be a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise AuditError("input must be a regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read()
    finally:
        os.close(fd)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise AuditError("input must be UTF-8") from exc
    if "\x00" in text:
        raise AuditError("NUL bytes are not allowed")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    try:
        header = next(reader, None)
        if not header or any(not h.strip() for h in header) or len(set(header)) != len(header):
            raise AuditError("header must contain unique nonblank names")
        if not set(keys + fields).issubset(header):
            raise AuditError("required column missing")
        key_indexes = [header.index(k) for k in keys]
        field_indexes = [header.index(f) for f in fields]
        rows = {}
        for ordinal, row in enumerate(reader, 1):
            if len(row) != len(header):
                raise AuditError(f"record {ordinal}: inconsistent column count")
            key = tuple(row[i] for i in key_indexes)
            if any(not k.strip() for k in key):
                raise AuditError(f"record {ordinal}: blank key")
            if key in rows:
                raise AuditError(f"record {ordinal}: duplicate key")
            rows[key] = (ordinal, tuple(row[i] for i in field_indexes))
    except csv.Error as exc:
        raise AuditError("malformed CSV") from exc
    if not rows:
        raise AuditError("header-only input is not an auditable dataset")
    return rows, hashlib.sha256(raw).hexdigest()


def _ascii_digits(value):
    return bool(value) and value.isascii() and value.isdigit()


def _difference_kind(left, right):
    """Label an unequal pair without echoing either string or parsing numbers.

    ``case`` uses ``str.lower``, not ``str.casefold``, so expansions such as
    ``ß`` versus ``ss`` stay ``replaced``. ``leading_zeros`` applies only when
    both sides are ASCII digits (including ``0`` versus ``00``).
    """
    if left == right:
        raise ValueError("difference kind requires unequal values")
    if left.strip() == right.strip():
        return "whitespace"
    if left.lower() == right.lower():
        return "case"
    if not left.strip() or not right.strip():
        return "blanked"
    if _ascii_digits(left) and _ascii_digits(right) and left.lstrip("0") == right.lstrip("0"):
        return "leading_zeros"
    if unicodedata.normalize("NFC", left) == unicodedata.normalize("NFC", right):
        return "normalization"
    return "replaced"


def audit(reference, observed, *, keys, fields, delimiter=",", observed_delimiter=None):
    """Compare UTF-8 CSVs as exact strings, keyed independently of row order.

    Output excludes cell values and key values; record numbers are one-based
    data records (not physical lines). Each changed cell includes a ``kind``
    from ``DIFFERENCE_KINDS``. Does not modify either input.
    """
    keys, fields = _columns(keys, "keys"), _columns(fields, "fields")
    if set(keys) & set(fields):
        raise AuditError("keys and checked fields must be disjoint")
    before, before_hash = _read(reference, keys, fields, delimiter)
    after, after_hash = _read(observed, keys, fields, delimiter if observed_delimiter is None else observed_delimiter)
    missing = sorted(before[k][0] for k in before.keys() - after.keys())
    added = sorted(after[k][0] for k in after.keys() - before.keys())
    changes = []
    blank = []
    for key, (record, values) in before.items():
        if key not in after:
            continue
        other_record, other_values = after[key]
        for field, left, right in zip(fields, values, other_values):
            # Separate dicts: one cell can be both blank and changed.
            location = {"field": field, "reference_record": record, "observed_record": other_record}
            if not left.strip() or not right.strip():
                blank.append(dict(location))
            if left != right:
                changed = dict(location)
                changed["kind"] = _difference_kind(left, right)
                changes.append(changed)
    return {
        "schema_version": 2,
        "ok": not (missing or added or changes or blank),
        "reference_sha256": before_hash,
        "observed_sha256": after_hash,
        "keys": list(keys), "fields": list(fields),
        "reference_rows": len(before), "observed_rows": len(after),
        "matched_rows": len(before.keys() & after.keys()),
        "missing_reference_records": missing, "added_observed_records": added,
        "changed_cells": changes, "blank_identifier_cells": blank,
    }
