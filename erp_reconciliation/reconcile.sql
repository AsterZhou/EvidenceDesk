-- Each invoice row appears once, even if deliveries are split across receipts.
WITH receipt_totals AS (
    SELECT po_line, SUM(quantity) AS received_qty FROM receipts GROUP BY po_line
), billed AS (
    -- Quantities are aggregated on the supplier as well as the PO line.
    -- Duplicate imports are *not* silently discarded; they trigger a review.
    SELECT l.po_line, i.supplier, i.currency, SUM(l.quantity) AS submitted_qty
    FROM invoice_lines l JOIN invoices i USING(import_id)
    GROUP BY l.po_line, i.supplier, i.currency
), header_copies AS (
    SELECT supplier, invoice_number, COUNT(*) AS imports
    FROM invoices GROUP BY supplier, invoice_number
), evidence AS (
    SELECT l.row_id, l.import_id, i.supplier, i.invoice_number, i.currency,
           l.po_line, l.quantity, l.unit_price_cents, p.supplier AS po_supplier,
           p.currency AS po_currency, p.ordered_qty, p.unit_price_cents AS po_price_cents,
           COALESCE(r.received_qty, 0) AS received_qty, b.submitted_qty, h.imports
    FROM invoice_lines l JOIN invoices i USING(import_id)
    LEFT JOIN po_lines p USING(po_line) LEFT JOIN receipt_totals r USING(po_line)
    JOIN billed b ON b.po_line=l.po_line AND b.supplier=i.supplier AND b.currency=i.currency
    JOIN header_copies h ON h.supplier=i.supplier AND h.invoice_number=i.invoice_number
)
SELECT e.*,
    CASE WHEN po_supplier IS NULL THEN 'UNKNOWN_PO|' ELSE '' END ||
    CASE WHEN imports>1 THEN 'DUPLICATE_INVOICE|' ELSE '' END ||
    CASE WHEN supplier<>po_supplier THEN 'SUPPLIER_MISMATCH|' ELSE '' END ||
    CASE WHEN currency<>po_currency THEN 'CURRENCY_MISMATCH|' ELSE '' END ||
    CASE WHEN currency=po_currency AND unit_price_cents<>po_price_cents THEN 'PRICE_MISMATCH|' ELSE '' END ||
    CASE WHEN supplier=po_supplier AND currency=po_currency AND submitted_qty>ordered_qty
         THEN 'ABOVE_ORDER|' ELSE '' END ||
    CASE WHEN supplier=po_supplier AND currency=po_currency AND submitted_qty>received_qty
         THEN 'ABOVE_RECEIPTS|' ELSE '' END AS findings
FROM evidence e ORDER BY row_id;
