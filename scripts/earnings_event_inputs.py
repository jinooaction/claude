"""Offline local observation receipts and as-of queries for reviewed earnings claims."""

import argparse
import json
import sys
from pathlib import Path

from auto_invest.analytics.earnings_event_inputs import import_bundle, query_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    collect = commands.add_parser('import')
    collect.add_argument('--input', type=Path, required=True)
    collect.add_argument('--output', type=Path, required=True)
    collect.add_argument('--previous', type=Path)
    query = commands.add_parser('query')
    query.add_argument('--bundle', type=Path, required=True)
    query.add_argument('--as-of', required=True)
    query.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'import':
            result = import_bundle(args.input, args.output, args.previous)
        else:
            result = query_bundle(args.bundle, args.as_of)
            with args.output.open('x') as handle:
                json.dump(result, handle, indent=2, sort_keys=True)
                handle.write('\n')
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError) as exc:
        # Source documents may contain arbitrary content; do not echo their contents.
        print(f'Input operation refused: {type(exc).__name__}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
