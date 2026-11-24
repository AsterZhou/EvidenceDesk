import unittest
from check import investigate, open_snapshot

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.database = open_snapshot()
        self.addCleanup(self.database.close)

    def rows(self):
        return {row["row_id"]: row for row in investigate(self.database)}

    def test_partial_receipts_do_not_multiply_invoices(self):
        rows = self.rows()
        self.assertEqual(len(rows), 10)
        for key in ["L01", "L02"]:
            self.assertEqual((rows[key]["submitted_qty"], rows[key]["received_qty"]), (8, 8))
            self.assertEqual(rows[key]["decision"], "MATCH")

    def test_all_findings_are_preserved(self):
        rows = self.rows()
        self.assertEqual(set(rows["L03"]["findings"].split("|")), {"PRICE_MISMATCH", "ABOVE_ORDER", "ABOVE_RECEIPTS"})
        self.assertEqual(rows["L10"]["findings"], "ABOVE_ORDER|ABOVE_RECEIPTS")

    def test_duplicate_headers_and_invalid_references(self):
        rows = self.rows()
        expected = dict(L04="DUPLICATE_INVOICE", L05="DUPLICATE_INVOICE", L06="CURRENCY_MISMATCH",
                        L07="UNKNOWN_PO", L08="SUPPLIER_MISMATCH", L09="ABOVE_RECEIPTS")
        for key, flag in expected.items():
            with self.subTest(key=key):
                self.assertEqual(rows[key]["findings"], flag)
                self.assertEqual(rows[key]["decision"], "REVIEW")

    def test_duplicate_number_is_scoped_to_supplier(self):
        self.database.execute("INSERT INTO invoices VALUES ('I11','OTHER','A101','CNY')")
        self.assertEqual(self.rows()["L01"]["decision"], "MATCH")

    def test_multi_line_invoice_does_not_count_as_duplicate_header(self):
        self.database.execute("INSERT INTO invoice_lines VALUES ('L11','I1','P11-1',1,800)")
        self.assertEqual(self.rows()["L01"]["imports"], 1)

    def test_requery_does_not_modify_records(self):
        before = self.database.total_changes
        self.assertEqual(self.rows(), self.rows())
        self.assertEqual(before, self.database.total_changes)
