# Scope decision, 2026-11-14

## Documented need, not claimed users

- Microsoft: https://support.microsoft.com/en-us/excel/keeping-leading-zeros-and-large-numbers
  Documents automatic leading-zero removal, 15-digit numeric precision, E/date
  conversions and preventive text import. These establish a failure class, not
  demand specifically for this package.
- US Department of Education CRDC resource:
  https://crdc.communities.ed.gov/sites/default/files/2024-12/Troubleshooting%20School%20or%20LEA%20IDs%20Converted%20by%20Excel.pdf
  Describes changed school/LEA identifiers preventing CSV submission. No education
  records or personal identifiers were downloaded or bundled.
- Existing alternative: https://github.com/simonw/csv-diff
  Keyed CSV comparison is established work. Prefer that tool when full value diffs
  are wanted. Do not claim this package is the first identifier checker.

Master-626 repository inventory was checked via authenticated read-only connector:
39 repositories, including private plate-join-audit. csv-toolkit README was read;
it covers transforming CSV data, not reference-based identifier preservation.
roi-replicates and plate-join-audit solve different tasks. Neither was edited.

A generic ML split-leakage checker was considered and rejected after finding many
similar public projects. This implementation instead takes a small export-quality
problem with documented support burden. Product-market fit is not established.

All example records are synthetic. Tests simulate output mutations; they do not
establish that a specific Excel version produces those mutations. Missing or
changed fields are detected without guessing whether a spreadsheet caused them.
