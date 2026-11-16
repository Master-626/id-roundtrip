# Validation record: 2026-11-14

- Linux, CPython 3.12.14: 14 unittest methods pass, with additional subcases for
  malformed inputs, exact-text mutations and invalid delimiter/key arguments.
- Wheel builds with installed setuptools using --no-build-isolation.
- Built wheel installed without dependencies in a clean venv; same suite passes.
- Independent review reproduced an invalid observed-delimiter fallback and
  non-sequence key error inconsistency; both fixed, regression cases added.
- Review clarified Python CSV strict mode is not complete RFC validation and
  value-minimized reports are not anonymous.
- CI matrix prepared for Linux/Windows/macOS and Python 3.10/3.12/3.13, NOT RUN.
- No real Excel/LibreOffice round-trip test, benchmark or external adoption test.
- No publication, public repo, package registry upload or promotion performed.

## 2026-11-15: private 0.1.1 candidate

The original 0.1.0 files and published repositories were not modified. A separate
candidate adds regular-file validation, nonblocking POSIX open and descriptor
validation. This prevents a named pipe with no writer from hanging the audit and
rejects devices such as /dev/zero before a potentially unbounded read.
The original FIFO hang was reproduced with a 1-second subprocess timeout.
19 tests pass on Linux/Python 3.12, including 5 new special-file/error tests.
The wheel was built without network dependencies and installed in a clean venv;
all 19 tests pass there too. Windows/macOS and real Excel remain untested.
README now acknowledges daff as well as csv-diff; no unique-diff claim is made.
