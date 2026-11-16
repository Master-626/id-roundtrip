# id-roundtrip

A small, dependency-free Python library and CLI that checks whether selected
identifier fields survived a CSV round trip **exactly**. Local only; no network,
telemetry, repairs, guessed padding, or numeric conversions.

## 中文简介

把未经表格软件改写的原始 CSV 与回传 CSV 对照，按独立、稳定的行键检查指定
编号列是否原样保留。可发现前导零丢失、长编号改写、日期状编号变化，以及行
增删。允许排序和列顺序变化。不自动补零或猜测修复，不声称能证明变化是 Excel
造成的。先保留原始文件，使用不会被改写的文本行键（如 `row-a`）。

## Why this exists

Microsoft documents automatic conversion of leading-zero identifiers, long
numbers, E-shaped codes and date-shaped text. US education data submission
support documents the resulting identifier/import failures. See [research notes](RESEARCH.md).
This project verifies the *actual exported text* against a trusted reference,
not spreadsheet formatting. Synthetic fixtures demonstrate the checks; no
real-world adoption or Excel integration testing is claimed.

## Install and run

Python 3.10+. From this source directory:

```sh
python -m pip install .
id-roundtrip examples/reference.csv examples/changed.csv --key row_key --field sample_id --field barcode
```

The example exits **1** and reports four changed cells, including their reference
and observed record numbers. It intentionally fails. For a passing example:

```sh
id-roundtrip examples/reference.csv examples/reference.csv --key row_key --field sample_id --field barcode
```

Repeat `--key` for a composite key. Repeat `--field` for the identifier columns.
Use `--delimiter tab` or `--delimiter semicolon` for explicitly chosen dialects;
`--observed-delimiter` overrides only the returned file's delimiter. No guessing.

JSON goes to stdout. Exit status: **0** exact preservation with no blank checked
identifiers; **1** changes, blank checked identifiers or added/missing rows;
**2** invalid input, ambiguous keys or unreadable file. The CLI creates no files.
If redirecting output in a shell, choose a fresh report path, never either input:
shell redirection can truncate a file *before this program starts*.

```python
from id_roundtrip import audit
report = audit('original.csv', 'returned.csv', keys=['row_key'],
               fields=['sample_id', 'barcode'])
assert report['ok']
```

## Contract and safety

- UTF-8 with optional BOM; Python `csv.reader(strict=True)` quoting rules (not full RFC validation). All rows must match header width.
- Unique, nonblank headers and unique, nonblank keys required. Empty datasets
  are rejected rather than reported as a successful check.
- Keys and checked fields must be disjoint. Do not use the identifier being
  checked as its own key. Altered keys produce missing/added rows, never guesses.
- Exact Unicode string equality. Whitespace, case, leading zeros, line endings
  inside cells and Unicode normalization differences count as changes. No float
  parsing. Text such as `NA`, `NULL` and `NaN` remains ordinary text.
- Row/column order may change. Extra unchecked columns are ignored, by design.
- Reports contain SHA-256 hashes of input bytes and one-based **data record**
  numbers, not physical line numbers. Multiline quoted records count once.
- Reports omit identifier/key *values* and file paths, but include column names,
  row counts, hashes and positions. This is data minimization, **not anonymization**.
  Treat reports as potentially sensitive; review before sharing.
- Duplicate keys, missing selected columns, ragged rows, blank records, malformed
  quoting, invalid UTF-8 and NUL bytes stop the audit. Both sides must be valid.

## Limits

Requires an independently preserved trusted reference and stable record keys.
If both copies were corrupted in the same way, this tool cannot detect that.
It does not read XLSX, run Excel/LibreOffice, verify formulas, detect display-only
formatting, identify root cause, compare unchecked fields, or recover lost digits.
Two identically blank identifiers fail the check: they are not valid preserved
identifiers under this contract. Changed identifiers may be intentional; a failure
requires human review, not automatic rejection of the business operation.

Inputs must be regular files; directories, devices and named pipes are rejected.
Symlinks to regular files are allowed. This is not a sandbox for adversarial paths.
Files and row maps are held in memory, so use for modest exports, not unbounded
or adversarial data. The Python CSV parser's field-size limit applies. Reads are
not a filesystem transaction; work on stable snapshot copies. No security or
compliance certification is implied.

## Alternatives

Use Excel's text import / automatic-conversion controls to prevent changes.
Use [csv-diff](https://github.com/simonw/csv-diff) for general-purpose human-readable
CSV/JSON differences, or [daff](https://github.com/paulfitz/daff) for table diffs.
Both can detect ordinary identifier changes; composite keys are not unique to this tool.
This package's narrow contract is explicit selected-field
preservation, fail-closed ambiguous input, composite keys, and value-minimized
machine reports. It is not a new diff algorithm or a replacement for a full data
quality platform. Master-626's existing CSV Toolkit performs merge/split/filter/
sort/convert operations rather than this audit; no existing repository was changed.

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pip wheel --no-deps . -w dist
```

On Windows, install the package first, then run `python -m unittest discover -s tests -v`.
Tests cover reordered rows/headers, exact text regressions, composite keys, blank
and malformed inputs, BOM/multiline data, delimiter differences, CLI status codes,
input immutability, value minimization and deterministic randomized permutations.
See VALIDATION.md for the environments actually run. MIT license.
