# ERP support exercise for three-way matching

A supplier asks why two lines on an invoice went to review even though goods were received. This AI-assisted work sample reconciles purchase orders, receipts and invoices, then produces a CSV that a support engineer and an accounts-payable analyst can inspect together. All suppliers, amounts and transactions are invented.

## Reproduce the support ticket

From the root of EvidenceDesk, with Python 3.9 or later:

```sh
python3 erp_reconciliation/check.py > results.csv
python3 erp_reconciliation/check.py --only-review
python3 -m unittest discover -s erp_reconciliation -v
```

[Open the expected CSV](sample.csv) in a spreadsheet. The fixture contains six purchase-order lines, six receipts, ten imported invoice headers and ten invoice rows. Two invoice rows match and eight need review. Six tests cover split receipts, multiple simultaneous exceptions, duplicate imports, supplier scope, multi-line invoices and read-only repeatability.

## Investigate a discrepancy

Start with invoice A103, row L03. It bills five units at 820 cents on PO line P11-1. The order sets a unit price of 800 cents, and receipt R3 covers five units. A second invoice A110 bills two more units against that line. The snapshot therefore shows seven units billed against five received. Both invoices carry the quantity exception. Only A103 carries the price exception. Ask the buyer to verify a possible price amendment and the warehouse to check outstanding receipts before releasing either row.

Then compare invoices A101 and A102. Their PO allows ten units, the warehouse logged deliveries of three and five, and the supplier billed three and five. Both pass. A direct join between the two invoice lines and the two receipts would create four rows. The SQL aggregates receipts and invoiced quantities before joining so each invoice row appears once.

| Column | How to use it |
| --- | --- |
| row_id / import_id | Identify the invoice line and source import |
| submitted_qty / received_qty / ordered_qty | Compare total claims with inventory evidence |
| imports | See how many invoice headers share the supplier and invoice number |
| currency / po_currency | Verify units before comparing monetary values |
| findings | Read every applicable exception; resolve them against source documents |

## Scope

This is a read-only snapshot, with positive integer quantities and prices in integer cents. Duplicate headers are deliberately retained for human review, including their quantities. The quantity finding applies to a whole order line at snapshot time. Deciding which earlier invoice was payable requires dated posting history. Taxes, unit conversions, returns, partial-payment allocation, price tolerances and currency conversion are outside this example. A match does not trigger a payment.
