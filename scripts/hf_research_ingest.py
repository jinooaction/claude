"""Fixed HF research access CLI; never print source errors or private values."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from auto_invest.market_data.hf_research import Collector


def read_small(path: Path):
    if path.is_symlink() or path.resolve() != path.absolute() or path.stat().st_size > 4096:
        raise ValueError("INVALID_INPUT_FILE")
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--previous-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        history = read_small(args.history)
        previous = None
        if args.previous_state.exists():
            try:
                previous = read_small(args.previous_state)
            except Exception:
                previous = {"invalid": True}
        repository = Path(__file__).resolve().parents[1]
        subprocess.run(["git", "-C", str(repository), "diff", "--quiet", "HEAD"],
                       check=True, capture_output=True, timeout=10)
        commit = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"],
                                         text=True, timeout=10).strip()
        collector = Collector(args.output, history, previous, source_commit=commit)
        result = collector.run(os.environ.get("HF_DATA_API_KEY", ""))
        print(json.dumps({"result": result["result"], "live_eligible": False,
                          "orders_submitted": 0}))
        return 0 if result["result"] == "COMPLETE" else 3
    except Exception:
        print('{"result":"CONTRACT_OR_STORAGE_REFUSED","live_eligible":false,"orders_submitted":0}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
