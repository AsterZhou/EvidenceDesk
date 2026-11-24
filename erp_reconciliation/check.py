"""Run read-only reconciliation rules on synthetic in-memory SQLite data."""
import argparse
import csv
from pathlib import Path
import sqlite3
import sys

HERE = Path(__file__).resolve().parent

def open_snapshot():
    database = sqlite3.connect(":memory:")
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys=ON")
    database.executescript((HERE / "fixture.sql").read_text())
    return database

def investigate(database):
    sql = (HERE / "reconcile.sql").read_text()
    for row in database.execute(sql):
        evidence = dict(row)
        flags = evidence["findings"].rstrip("|")
        evidence["findings"] = flags or "OK"
        evidence["decision"] = "REVIEW" if flags else "MATCH"
        yield evidence

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only-review", action="store_true")
    args = parser.parse_args()
    database = open_snapshot()
    try:
        rows = list(investigate(database))
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            if not args.only_review or row["decision"] == "REVIEW":
                writer.writerow(row)
    finally:
        database.close()

if __name__ == "__main__":
    main()
