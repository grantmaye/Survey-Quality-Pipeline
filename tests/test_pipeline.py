import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from surveylens.pipeline import FIELDS, connect, ingest, report, rejections
from surveylens.render import render_html, write_report

SAMPLE = Path(__file__).resolve().parents[1] / "surveylens/data/evaluations.csv"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.db = connect(Path(self.folder.name) / "test.sqlite")
        self.addCleanup(self.db.close)

    def csv(self, rows, name="input.csv"):
        filename = Path(self.folder.name) / name
        with filename.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(FIELDS)
            writer.writerows(rows)
        return filename

    def test_fixture_quality_counts_replay_and_reports(self):
        first = ingest(self.db, SAMPLE)
        self.assertEqual((first["accepted"], first["duplicates"], first["rejected"]), (13, 1, 3))
        again = ingest(self.db, SAMPLE)
        self.assertTrue(again["replayed"])
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM responses").fetchone()[0], 13)
        groups = {group["course"]: group for group in report(self.db)["groups"]}
        self.assertEqual(groups["CS101"]["mean_rating"], 3.83)
        self.assertEqual(groups["CS101"]["favorable_pct"], 66.7)
        self.assertEqual(groups["ENG201"]["mean_rating"], 4.0)
        self.assertTrue(groups["ART105"]["suppressed"])
        self.assertIsNone(groups["ART105"]["responses"])
        self.assertIsNone(groups["ART105"]["mean_rating"])
        self.assertIsNone(groups["ART105"]["favorable_pct"])

    def test_cross_file_duplicates_and_conflicts_do_not_replace_answers(self):
        row = ["r1", "CS101", "2026-fall", "5", "2026-09-20T12:00:00Z"]
        ingest(self.db, self.csv([row]))
        duplicate = row.copy(); duplicate[4] = "2026-09-20T08:00:00-04:00"
        conflict = row.copy(); conflict[3] = "1"
        result = ingest(self.db, self.csv([duplicate, conflict], "second.csv"))
        self.assertEqual((result["accepted"], result["duplicates"], result["rejected"]), (0, 1, 1))
        self.assertEqual(self.db.execute("SELECT rating FROM responses").fetchone()[0], 5)
        self.assertEqual(rejections(self.db, result["id"])[0]["reason"], "conflicting_response_id")

    def test_headers_fail_before_mutation(self):
        bad = Path(self.folder.name) / "bad.csv"
        bad.write_text("response_id,rating\nr1,5\n")
        with self.assertRaises(ValueError):
            ingest(self.db, bad)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 0)

    def test_bad_rows_are_quarantined_without_raw_data(self):
        result = ingest(self.db, self.csv([
            ["private-person@example.test", "CS101", "2026-fall", "5", "2026-09-20T12:00:00Z"],
            ["r1", "CS101", "2026-fall", "5", "2026-09-20T12:00:00"],
            ["r2", "CS101", "2026-fall", "NaN", "2026-09-20T12:00:00Z"],
            ["r3", "CS101", "2026-fall", "5", "2026-09-20T12:00:00Z", "extra"],
        ]))
        self.assertEqual(result["rejected"], 4)
        self.assertNotIn("private-person", json.dumps(rejections(self.db, result["id"])))

    def test_database_failure_rolls_back_run_and_earlier_rows(self):
        self.db.execute("""CREATE TRIGGER fail_row BEFORE INSERT ON responses WHEN NEW.response_id='r002'
                         BEGIN SELECT RAISE(ABORT, 'simulated failure'); END""")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            ingest(self.db, SAMPLE)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM responses").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 0)
        self.db.execute("DROP TRIGGER fail_row"); self.db.commit()
        self.assertEqual(ingest(self.db, SAMPLE)["accepted"], 13)

    def test_suppression_boundary_and_minimum_validation(self):
        ingest(self.db, SAMPLE)
        self.assertFalse(next(g for g in report(self.db, 5)["groups"] if g["course"] == "ENG201")["suppressed"])
        self.assertTrue(next(g for g in report(self.db, 6)["groups"] if g["course"] == "ENG201")["suppressed"])
        for minimum in [0, 2, 3.5, True]:
            with self.assertRaises(ValueError):
                report(self.db, minimum)

    def test_outputs_agree_and_html_escapes_labels(self):
        ingest(self.db, SAMPLE)
        payload = report(self.db)
        files = write_report(payload, Path(self.folder.name) / "reports")
        self.assertEqual(json.loads(Path(files["json"]).read_text()), payload)
        self.assertIn("3.83", Path(files["html"]).read_text())
        payload["groups"][0]["course"] = "<script>alert(1)</script>"
        rendered = render_html(payload)
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)

    def test_malformed_csv_rolls_back_preceding_valid_record(self):
        source = self.csv([["ok", "CS101", "2026-fall", "5", "2026-09-20T12:00:00Z"]])
        with source.open("a") as handle:
            handle.write('"unterminated field')
        with self.assertRaises(csv.Error):
            ingest(self.db, source)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM responses").fetchone()[0], 0)

    def test_invalid_encoding_leaves_database_unchanged(self):
        source = Path(self.folder.name) / "invalid.csv"
        source.write_bytes(b"\xff\xfe")
        with self.assertRaises(UnicodeError):
            ingest(self.db, source)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 0)

    def test_cli_demo_writes_real_reports(self):
        dest = Path(self.folder.name) / "demo"
        result = subprocess.run([sys.executable, "-m", "surveylens", "demo", "--output", str(dest)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["accepted"], 13)
        self.assertTrue((dest / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
