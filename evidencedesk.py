"""Replay ordered enterprise-agent decision traces. Uses only Python's standard library."""

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from html import escape
from pathlib import Path


# A review can reopen a quote when a new source is supplied.
TRANSITIONS = {
    "new": {"intake": "open"},
    "open": {"quote_lookup": "quoted", "request_review": "review"},
    "quoted": {"approve": "approved", "request_review": "review"},
    "review": {"quote_lookup": "quoted"},
    "approved": {"export": "exported"},
    "exported": {},
}


def field_text(value):
    return isinstance(value, str) and bool(value.strip())


def money(value):
    """Require a finite positive decimal string with at most two fractional places."""
    if not field_text(value):
        return None
    try:
        number = Decimal(value)
        if number.is_finite() and number > 0 and number.as_tuple().exponent >= -2:
            return number
    except InvalidOperation:
        pass
    return None


def replay(trace):
    case_id = trace.get("case_id") if isinstance(trace, dict) else None
    if not field_text(case_id):
        raise ValueError("each record needs a non-empty string case_id")
    events = trace.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError(f"{case_id}: events must be a non-empty array")

    state = "new"
    calls = set()
    evidence = None
    findings = []
    history = []
    for step, event in enumerate(events, start=1):
        before = state
        if not isinstance(event, dict):
            raise ValueError(f"{case_id}, step {step}: expected an event object")
        tool = event.get("tool")
        call_id = event.get("call_id")
        if not field_text(tool) or not field_text(call_id):
            raise ValueError(f"{case_id}, step {step}: tool and call_id must be non-empty strings")

        errors = []

        def fail(code, reason):
            errors.append({"step": step, "code": code, "reason": reason})

        if call_id in calls:
            fail("DUPLICATE_CALL", f"Call {call_id} was already observed.")
        calls.add(call_id)

        next_state = TRANSITIONS[state].get(tool)
        if not next_state:
            fail("ILLEGAL_TRANSITION", f"{tool} cannot execute from {state}.")
        if state == "review" and tool in {"approve", "export"}:
            fail("REVIEW_PENDING", "A new quote with evidence is required to leave review.")

        if tool == "quote_lookup":
            source = event.get("source_id")
            currency = event.get("currency")
            if not field_text(source):
                fail("MISSING_SOURCE", "The proposed price has no source identifier.")
            if money(event.get("amount")) is None:
                fail("INVALID_AMOUNT", "Price needs a positive decimal string with at most two decimals.")
            if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
                fail("INVALID_CURRENCY", "Currency must be a three-letter uppercase code.")
        elif tool == "request_review" and not field_text(event.get("reason")):
            fail("MISSING_REASON", "A reviewer needs a reason for this handoff.")
        elif tool == "approve":
            if event.get("actor_type") != "human" or not field_text(event.get("actor_id")):
                fail("MISSING_APPROVER", "Approval needs an identified human reviewer.")
            if evidence and event.get("source_id") != evidence["source_id"]:
                fail("SOURCE_MISMATCH", "The approval references a different price source.")
        elif tool == "export" and evidence:
            if (event.get("source_id") != evidence["source_id"]
                    or money(event.get("amount")) != money(evidence["amount"])
                    or event.get("currency") != evidence["currency"]):
                fail("EXPORT_DRIFT", "Exported source, price or currency differs from the approved quote.")

        if not errors:
            state = next_state
            if tool == "quote_lookup":
                evidence = {key: event[key] for key in ("source_id", "amount", "currency")}
            elif tool == "request_review":
                evidence = None
        findings.extend(errors)
        history.append({"step": step, "call_id": call_id, "tool": tool, "before": before, "after": state,
                        "evidence": {key: event[key] for key in ("source_id", "amount", "currency", "actor_id", "reason") if key in event}})
    if not findings and state not in {"exported", "review"}:
        findings.append({"step": len(events), "code": "INCOMPLETE_TRACE", "reason": f"Trace ended in {state}."})
    outcome = "fail" if findings else ("review" if state == "review" else "pass")
    return {"case_id": case_id, "outcome": outcome, "final_state": state, "findings": findings, "history": history}


def evaluate(lines):
    cases = []
    seen = set()
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            case = replay(json.loads(line))
            if case["case_id"] in seen:
                raise ValueError(f"duplicate case_id {case['case_id']}")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"line {line_no}: {exc}") from exc
        seen.add(case["case_id"])
        cases.append(case)
    if not cases:
        raise ValueError("input has no traces")
    counts = Counter(case["outcome"] for case in cases)
    return {"version": 1, "total": len(cases), "counts": {key: counts[key] for key in ("pass", "review", "fail")},
            "cases": cases}


def html_report(report):
    def h(value):
        return escape(str(value))

    cards = []
    for case in report["cases"]:
        rows = "".join(
            f'<tr><td>{item["step"]}</td><td>{h(item["tool"])}<small>{h(item["call_id"])}</small></td>'
            f'<td>{h(item["before"])} → {h(item["after"])}</td>'
            f'<td>{h(" · ".join(str(v) for v in item["evidence"].values()) or "—")}</td></tr>'
            for item in case["history"]
        )
        issues = "".join(f'<li>Step {i["step"]} · <b>{h(i["code"])}</b> · {h(i["reason"])}</li>' for i in case["findings"])
        if issues:
            notes = f"<ul>{issues}</ul>"
        elif case["outcome"] == "review":
            notes = "<p>Handoff recorded. A reviewer must resolve the quote before export.</p>"
        else:
            notes = "<p>The approved source and price match the exported quote.</p>"
        status = case["outcome"]
        cards.append(f'<details data-status="{status}"><summary><strong>{h(case["case_id"])}</strong>'
                     f'<span class="{status}">{status.upper()}</span></summary>{notes}<div class="scroll"><table>'
                     f'<tr><th>Step</th><th>Tool / call ID</th><th>State</th><th>Event evidence</th></tr>{rows}</table></div></details>')
    numbers = "".join(f'<div><b>{v}</b>{k.title()}</div>' for k, v in report["counts"].items())
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>EvidenceDesk | Workflow acceptance</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f3;color:#172b28;font:16px/1.55 system-ui,sans-serif}main{max-width:930px;margin:auto;padding:36px 18px}
header{border-bottom:2px solid #244c44}h1{font-size:clamp(34px,7vw,64px);letter-spacing:-.05em;margin:0}h2{font-size:22px}
.metrics{display:flex;margin:20px 0;gap:10px}.metrics div{flex:1;padding:12px;background:#e1ebe4;border-left:4px solid #42695b}.metrics b{display:block;font-size:28px}
details{background:white;border:1px solid #cdd9d1;border-radius:8px;padding:14px;margin:10px 0}summary{cursor:pointer;list-style-position:inside}
summary span{float:right;font-size:12px;font-weight:bold;letter-spacing:.04em;border-radius:4px;padding:2px 8px}.pass{background:#daeee1}.fail{background:#fbe2dc}.review{background:#fff0c1}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;border-top:1px solid #dae0da;padding:6px 8px;vertical-align:top}small{display:block;color:#435f56}
.scroll{overflow-x:auto}li,p{overflow-wrap:anywhere}select{font:inherit;padding:3px 8px}footer{margin-top:20px;color:#435f56}
</style><main><header><h1>EvidenceDesk</h1><p>Workflow acceptance · quote evidence, human review and export integrity</p></header>
<section class="metrics">''' + numbers + '''</section><h2>Trace review</h2>
<label>Show <select id="filter"><option value="all">All outcomes</option><option value="fail">Failed</option><option value="review">Human review</option><option value="pass">Passed</option></select></label>''' + "".join(cards) + '''
<footer>An evidence ID identifies the recorded source. Verify source authenticity separately.</footer></main><script>
document.querySelector('#filter').addEventListener('change', e => {document.querySelectorAll('details').forEach(d => {d.hidden=e.target.value!=='all'&&d.dataset.status!==e.target.value})})
</script></html>'''


def write_result(path, content):
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as handle:
        tmp = Path(handle.name)
        try:
            handle.write(content)
            handle.close()
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSONL file containing one complete case per line")
    parser.add_argument("--json", type=Path, help="write JSON to this path instead of stdout")
    parser.add_argument("--html", type=Path, help="write a standalone interactive HTML report")
    parser.add_argument("--fail-on-error", action="store_true", help="exit 1 if any case fails policy")
    args = parser.parse_args(argv)
    paths = [p.resolve() for p in (args.input, args.json, args.html) if p is not None]
    if len(set(paths)) != len(paths):
        parser.error("input and output paths must be distinct")
    try:
        with args.input.open(encoding="utf-8") as file:
            report = evaluate(file)
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.json:
            write_result(args.json, rendered)
        else:
            sys.stdout.write(rendered)
        if args.html:
            write_result(args.html, html_report(report))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"evidencedesk: {exc}\n")
    return int(args.fail_on_error and bool(report["counts"]["fail"]))


if __name__ == "__main__":
    sys.exit(main())
