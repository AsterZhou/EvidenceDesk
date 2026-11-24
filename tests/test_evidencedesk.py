import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import evidencedesk as ed

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "demo.jsonl"
CLEAN = json.loads(FIXTURE.read_text().splitlines()[0])


def mutated(index, **updates):
    trace = json.loads(json.dumps(CLEAN))
    trace["events"][index].update(updates)
    return ed.replay(trace)


class AcceptanceTests(unittest.TestCase):
    def test_all_fixture_labels(self):
        with FIXTURE.open() as stream:
            report = ed.evaluate(stream)
        expected = ["pass", "review", "pass"] + ["fail"] * 7
        self.assertEqual([case["outcome"] for case in report["cases"]], expected)
        self.assertEqual(report["counts"], {"pass": 2, "review": 1, "fail": 7})

    def test_export_decimal_equivalence(self):
        self.assertEqual(mutated(3, amount="18.4")["outcome"], "pass")

    def test_amount_must_be_positive_finite_decimal(self):
        for invalid in [0.01, "-1", "NaN", "Infinity", "2.001", "0", None]:
            with self.subTest(invalid=invalid):
                result = mutated(1, amount=invalid)
                self.assertIn("INVALID_AMOUNT", [i["code"] for i in result["findings"]])

    def test_no_machine_approval(self):
        self.assertEqual(mutated(2, actor_type="agent")["findings"][0]["code"], "MISSING_APPROVER")

    def test_mismatch_keeps_previous_state(self):
        result = mutated(2, source_id="SYN-different")
        self.assertEqual(result["history"][2]["after"], "quoted")
        self.assertEqual(result["final_state"], "quoted")

    def test_untrusted_markup_escaped(self):
        trace = dict(CLEAN, case_id="<svg/onload=alert(1)>")
        report = ed.evaluate([json.dumps(trace)])
        self.assertNotIn(trace["case_id"], ed.html_report(report))
        self.assertIn("&lt;svg", ed.html_report(report))

    def test_duplicate_case_rejected(self):
        line = json.dumps(CLEAN)
        with self.assertRaisesRegex(ValueError, "line 2: duplicate case_id"):
            ed.evaluate([line, line])

    def test_invalid_and_empty_inputs(self):
        for content in ["", "{", "[]", '{"case_id":"x","events":[]}', '{"case_id":"x","events":[[]]}']:
            with self.subTest(content=content), self.assertRaises(ValueError):
                ed.evaluate(io.StringIO(content))

    def test_open_trace_is_incomplete(self):
        trace = dict(CLEAN, events=CLEAN["events"][:-1])
        self.assertEqual(ed.replay(trace)["findings"][0]["code"], "INCOMPLETE_TRACE")

    def test_cli_exit_codes_and_consistent_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            html_path = Path(temp) / "report.html"
            json_path = Path(temp) / "report.json"
            command = [sys.executable, str(ROOT / "evidencedesk.py"), str(FIXTURE),
                       "--html", str(html_path), "--json", str(json_path)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(subprocess.run(command + ["--fail-on-error"], capture_output=True).returncode, 1)
            report = json.loads(json_path.read_text())
            self.assertEqual(html_path.read_text(), ed.html_report(report))
            self.assertEqual(subprocess.run(command + ["--json", str(FIXTURE)], capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
