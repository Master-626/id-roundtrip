import argparse
import json
import sys
from . import AuditError, audit


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
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result["ok"] else 1
    except (AuditError, OSError) as exc:
        # Never print cell contents, filenames, or raw parser errors.
        message = str(exc) if isinstance(exc, AuditError) else "could not read input file"
        print(f"id-roundtrip: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
