#!/usr/bin/env python3
"""Fixed diagnostic read only; preserves the existing paper runtime identity."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from auto_invest.analytics.intraday_collection_record import read_recorded_status
from auto_invest.analytics.intraday_service import read_service_status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["service-status"])
    parser.parse_args()
    result = read_recorded_status(Path("/var/lib/auto-invest-intraday"), datetime.now(UTC),
                                 read_service_status)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
