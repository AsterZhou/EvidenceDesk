# EvidenceDesk

EvidenceDesk checks whether a quotation workflow can explain its decisions. It replays a JSONL trace of tool calls, tests whether prices survive human approval and export intact, and reports the first step where each rule breaks.

[浏览示例判定 / Browse sample verdicts](#sample-verdicts) · [Machine-readable results](examples/summary.json) · [Downloadable HTML report](examples/report.html)

This AI-assisted portfolio prototype uses invented procurement records. It runs locally with Python 3.9+ and the standard library. It requires no credentials, model endpoint or customer data.

## Run the demo

```bash
python3 evidencedesk.py examples/demo.jsonl --json results.json --html report.html
python3 -m unittest discover -s tests -v
```

Open `report.html` in a browser, select an outcome, and expand a case. Each event shows its call ID, the state before and after the call, and the submitted evidence. The JSON report includes the same event history and a structured reason for each failed check.

For a CI gate, add `--fail-on-error`. Exit codes are 0 for a completed evaluation, 1 for rule failures with the gate enabled, and 2 for malformed inputs or file errors. A valid review handoff does not block this gate. The checked-in demo intentionally includes policy failures.

## Sample verdicts

| Synthetic scenario | Result | What a reviewer can check |
| --- | --- | --- |
| Source-backed export | Pass | Source, currency and decimal amount match the approved quote. |
| Conflicting pack sizes | Review | The workflow stops and records why a person needs to decide. |
| Review followed by a new quote | Pass | A source-backed price, human approval and export follow the handoff. |
| Suggested price without a source | Fail | The quote never advances into the quoted state. |
| Tool call replayed | Fail | A duplicate call ID appears in the trace. |
| Approval during review | Fail | A human sign-off alone cannot resolve conflicting evidence. |
| Price multiplied by ten at export | Fail | The exported amount differs from the approved value. |
| Export before approval | Fail | The attempted transition is rejected. |
| Reviewer cites a different row | Fail | The approval references a different source. |
| Currency changes at export | Fail | A CNY quote reaches export as USD. |

The demo contains ten traces with the outcomes **2 pass, 1 review, 7 fail**. These counts describe the supplied fixtures, not accuracy on unseen workflows.

## Trace contract

Each nonblank line is one JSON object with a unique string `case_id` and an ordered, nonempty `events` array. Each event has a `tool` and a `call_id`, unique within that case. The caller supplies complete traces in execution order. A rejected event leaves state unchanged and its finding stays on the final record.

| Tool | Accepted from | Required fields | New state |
| --- | --- | --- | --- |
| `intake` | new | Common event fields | open |
| `quote_lookup` | open, review | `source_id`, positive decimal string `amount` at up to two decimal places, three-letter uppercase `currency` | quoted |
| `request_review` | open, quoted | Nonempty `reason` | review |
| `approve` | quoted | `actor_type: "human"`, nonempty `actor_id`, matching `source_id` | approved |
| `export` | approved | Source ID, currency and numeric amount from the approved quote | exported |

A quote that needs investigation can end in review. A clean export requires an approved quote. Any other unfinished trace or any rule violation results in a failure. Duplicate case IDs and malformed records are input errors so the CLI cannot publish an apparently complete evaluation of a partially read file.

## Scope

EvidenceDesk verifies consistency among recorded events. Source IDs and actor identities are supplied by the producer. A production integration would need to resolve immutable source documents and bind sign-off to authenticated users. The demo models one currency and quoted amount per case, omitting tax, quantities and conversions. It does not execute agent tools or send data anywhere.
