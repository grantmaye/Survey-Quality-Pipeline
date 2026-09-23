import argparse
import csv
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from .pipeline import connect, ingest, report, rejections
from .render import write_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validate survey CSV files and generate aggregate reports.")
    sub = parser.add_subparsers(dest="command", required=True)
    incoming = sub.add_parser("ingest", help="Import a CSV; invalid records are quarantined")
    incoming.add_argument("csv", type=Path)
    incoming.add_argument("--db", default="data/surveys.sqlite")
    outgoing = sub.add_parser("report", help="Export JSON and HTML summaries")
    outgoing.add_argument("--db", default="data/surveys.sqlite")
    outgoing.add_argument("--output", default="reports")
    outgoing.add_argument("--minimum", type=int, default=5)
    demo = sub.add_parser("demo", help="Run synthetic data in a temporary database")
    demo.add_argument("--output", default="demo-output")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            with tempfile.TemporaryDirectory() as folder:
                db = connect(Path(folder) / "demo.sqlite")
                try:
                    result = ingest(db, Path(__file__).resolve().parent / "data" / "evaluations.csv")
                    result["rejections"] = rejections(db, result["id"])
                    result["reports"] = write_report(report(db), args.output)
                    print(json.dumps(result, indent=2))
                finally:
                    db.close()
        else:
            if args.command == "report" and not Path(args.db).is_file():
                raise ValueError("Database does not exist; run ingest first")
            db = connect(args.db)
            try:
                if args.command == "ingest":
                    result = ingest(db, args.csv)
                    result["rejections"] = rejections(db, result["id"])
                else:
                    result = write_report(report(db, args.minimum), args.output)
                print(json.dumps(result, indent=2))
            finally:
                db.close()
        return 0
    except (ValueError, OSError, sqlite3.Error, csv.Error) as exc:
        print(f"surveylens: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
