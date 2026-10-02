"""Retain a complete HF research artifact offline without secrets or network access."""

import argparse
import json
from pathlib import Path

from auto_invest.market_data.hf_research import retain_complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = retain_complete(args.source, args.output)
        print(json.dumps({"result": "RETAINED", "live_eligible": False, "orders_submitted": 0,
                          "manifest_sha256": receipt["retained_manifest_sha256"]}))
        return 0
    except Exception:
        print('{"result":"RETENTION_REFUSED","live_eligible":false,"orders_submitted":0}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
