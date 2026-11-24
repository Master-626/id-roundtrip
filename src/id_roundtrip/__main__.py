import argparse
import errno
import json
import os
import sys
from . import AuditError, audit


def _output_pipe_closed(exc):
    """True when writing the report failed because the consumer closed stdout.

    Windows often reports that as WinError 109/232 or EINVAL instead of EPIPE.
    EINVAL is only treated as a closed pipe on Windows.
    """
    if isinstance(exc, BrokenPipeError) or exc.errno == errno.EPIPE:
        return True
    if getattr(exc, "winerror", None) in (109, 232):
        return True
    return os.name == "nt" and exc.errno == errno.EINVAL


def _silence_broken_pipe():
    """Point stdout at devnull so shutdown does not overwrite the audit status.

    Python flushes stdout again while exiting. After EPIPE that second flush
    becomes an ignored BrokenPipeError and the process exits 120, hiding
    whether the audit passed.
    """
    try:
        sys.stdout.close()
    except OSError as exc:
        if not _output_pipe_closed(exc):
            raise
    try:
        null_fd = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        return
    try:
        os.dup2(null_fd, 1)
    finally:
        os.close(null_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit exact identifier preservation in CSV exports.")
    parser.add_argument("reference")
    parser.add_argument("observed")
    parser.add_argument("--key", action="append", required=True)
    parser.add_argument("--field", action="append", required=True)
    parser.add_argument("--delimiter", choices=["comma", "tab", "semicolon"], default="comma")
    parser.add_argument("--observed-delimiter", choices=["comma", "tab", "semicolon"])
    args = parser.parse_args(argv)
    separators = {"comma": ",", "tab": "\t", "semicolon": ";"}
    try:
        result = audit(args.reference, args.observed, keys=args.key, fields=args.field,
                       delimiter=separators[args.delimiter],
                       observed_delimiter=separators.get(args.observed_delimiter))
    except AuditError as exc:
        # Never print cell contents, filenames, or raw parser errors.
        print(f"id-roundtrip: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print("id-roundtrip: could not read input file", file=sys.stderr)
        return 2
    status = 0 if result["ok"] else 1
    try:
        print(json.dumps(result, ensure_ascii=True, indent=2))
        sys.stdout.flush()
    except OSError as exc:
        if not _output_pipe_closed(exc):
            raise
        _silence_broken_pipe()
    return status


if __name__ == "__main__":
    sys.exit(main())
