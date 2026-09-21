"""Read-only audit of a fixed sparse one-minute dataset (spec 193)."""
import argparse
import json
import sys
from pathlib import Path

from auto_invest.analytics.observed_intraday_inputs import audit_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError('output exists')
        report = audit_manifest(args.manifest)
        encoded = json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+'\n'
        with args.output.open('x') as handle:
            handle.write(encoded)
    except (ValueError, TypeError, KeyError, OverflowError, OSError) as error:
        # Malformed source cells may contain private text; do not echo their contents.
        print(f'observation audit rejected ({type(error).__name__})', file=sys.stderr)
        return 2
    print(json.dumps({'status': 'AUDITED', 'live_eligible': False,
                      'symbols': report['scope']['symbols']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
