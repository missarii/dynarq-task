"""Comprehensive tests for the rules engine.

Run from inside python/:  python -m unittest
"""

import unittest
from plan import build_plan, parse_date


class ParseDateTest(unittest.TestCase):
    def test_valid_date(self):
        d = parse_date("2026-09-30")
        self.assertEqual(d.year, 2026)
        self.assertEqual(d.month, 9)
        self.assertEqual(d.day, 30)

    def test_none_returns_none(self):
        self.assertIsNone(parse_date(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_date(""))

    def test_wrong_format_slash(self):
        self.assertIsNone(parse_date("30/09/2026"))

    def test_feb_30_invalid(self):
        self.assertIsNone(parse_date("2026-02-30"))

    def test_non_string_returns_none(self):
        self.assertIsNone(parse_date(12345))

    def test_leap_year_valid(self):
        self.assertIsNotNone(parse_date("2024-02-29"))

    def test_non_leap_year_feb29_invalid(self):
        self.assertIsNone(parse_date("2025-02-29"))


class ShapeTest(unittest.TestCase):
    def test_empty_input_gives_empty_plan(self):
        plan = build_plan([], [], "2026-10-12")
        self.assertEqual(plan, {"today": "2026-10-12", "actions": [], "skipped": []})


class DuplicateIdTest(unittest.TestCase):
    def test_duplicate_id_skipped_once(self):
        invoices = [
            {"id": "INV-X", "customer": "A", "email": "a@a.test",
             "amount": 100.0, "currency": "EUR", "due_date": "2026-09-01", "paid_date": None},
            {"id": "INV-X", "customer": "B", "email": "b@b.test",
             "amount": 200.0, "currency": "EUR", "due_date": "2026-09-01", "paid_date": None},
        ]
        plan = build_plan(invoices, [], "2026-10-12")
        self.assertEqual(plan["actions"], [])
        # Must appear only once
        skipped_ids = [s["invoice_id"] for s in plan["skipped"]]
        self.assertEqual(skipped_ids.count("INV-X"), 1)
        self.assertEqual(plan["skipped"][0]["reason"], "duplicate_id")


class InvalidAmountTest(unittest.TestCase):
    def test_missing_amount(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "currency": "EUR", "due_date": "2026-09-01", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "invalid_amount")

    def test_zero_amount(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 0, "currency": "EUR", "due_date": "2026-09-01", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "invalid_amount")

    def test_negative_amount(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": -50.0, "currency": "EUR", "due_date": "2026-09-01", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "invalid_amount")

    def test_string_amount(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": "100", "currency": "EUR", "due_date": "2026-09-01", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "invalid_amount")

    def test_bool_amount(self):
        # True is a bool and bool is a subclass of int in Python; must be rejected
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": True, "currency": "EUR", "due_date": "2026-09-01", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "invalid_amount")

    def test_valid_amount(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-09-01", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"], [])


class MissingDueDateTest(unittest.TestCase):
    def test_null_due_date(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": None, "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "missing_due_date")

    def test_empty_string_due_date(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "missing_due_date")

    def test_missing_due_date_key(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "missing_due_date")


class InvalidDueDateTest(unittest.TestCase):
    def test_feb30(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-02-30", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "invalid_due_date")

    def test_slash_format(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "30/09/2026", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "invalid_due_date")


class InvalidPaidDateTest(unittest.TestCase):
    def test_empty_string_paid_date_is_not_invalid(self):
        # empty string means unpaid, not invalid_paid_date
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-09-01", "paid_date": ""}
        plan = build_plan([inv], [], "2026-10-12")
        # "" means unpaid (not a date), check it is treated as unpaid and produces an action if overdue
        # due date 2026-09-01, today 2026-10-12 → 41 days overdue → final
        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["skipped"], [])

    def test_invalid_paid_date_format(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-09-01", "paid_date": "bad-date"}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "invalid_paid_date")

    def test_paid_date_in_future(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-09-01", "paid_date": "2026-12-01"}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["skipped"][0]["reason"], "invalid_paid_date")


class PaidInvoiceTest(unittest.TestCase):
    def test_paid_invoice_plans_nothing(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-09-01",
               "paid_date": "2026-10-05"}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["actions"], [])
        self.assertEqual(plan["skipped"], [])

    def test_paid_today_plans_nothing(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-09-01",
               "paid_date": "2026-10-12"}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["actions"], [])


class NotYetOverdueTest(unittest.TestCase):
    def test_due_today_plans_nothing(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-10-12", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["actions"], [])

    def test_1_day_overdue_plans_nothing(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-10-11", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["actions"], [])

    def test_2_days_overdue_plans_nothing(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-10-10", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(plan["actions"], [])


class StepSelectionTest(unittest.TestCase):
    def _invoice(self, due_date):
        return {"id": "INV-1", "customer": "Acme Corp", "email": "a@a.test",
                "amount": 500.0, "currency": "EUR", "due_date": due_date, "paid_date": None}

    def test_3_days_overdue_plans_friendly(self):
        # due 2026-10-09, today 2026-10-12 → 3 days
        plan = build_plan([self._invoice("2026-10-09")], [], "2026-10-12")
        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["step"], "friendly")
        self.assertFalse(plan["actions"][0]["needs_approval"])
        self.assertEqual(plan["actions"][0]["days_overdue"], 3)

    def test_10_days_overdue_plans_firm_not_friendly(self):
        # due 2026-10-02, today 2026-10-12 → 10 days
        plan = build_plan([self._invoice("2026-10-02")], [], "2026-10-12")
        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["step"], "firm")
        self.assertTrue(plan["actions"][0]["needs_approval"])

    def test_24_days_overdue_plans_final(self):
        # due 2026-09-18, today 2026-10-12 → 24 days
        plan = build_plan([self._invoice("2026-09-18")], [], "2026-10-12")
        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["step"], "final")
        self.assertTrue(plan["actions"][0]["needs_approval"])

    def test_12_days_overdue_plans_firm_only(self):
        # README example: 12 days overdue with nothing sent → firm only
        plan = build_plan([self._invoice("2026-09-30")], [], "2026-10-12")
        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["step"], "firm")


class AlreadySentTest(unittest.TestCase):
    def _invoice(self):
        return {"id": "INV-1", "customer": "A", "email": "a@a.test",
                "amount": 100.0, "currency": "EUR", "due_date": "2026-10-09", "paid_date": None}

    def test_friendly_already_sent_plans_nothing(self):
        # 3 days overdue, friendly already sent → nothing
        sent = [{"invoice_id": "INV-1", "step": "friendly", "sent_on": "2026-10-10"}]
        plan = build_plan([self._invoice()], sent, "2026-10-12")
        self.assertEqual(plan["actions"], [])

    def test_firm_already_sent_but_invoice_at_friendly_level(self):
        # 3 days overdue, only reached friendly; but firm is in sent.json
        # highest step reached = friendly; firm sent counts as >= friendly → nothing
        sent = [{"invoice_id": "INV-1", "step": "firm", "sent_on": "2026-10-10"}]
        plan = build_plan([self._invoice()], sent, "2026-10-12")
        self.assertEqual(plan["actions"], [])

    def test_friendly_sent_but_now_at_firm_level(self):
        # 10 days overdue, friendly sent but firm not sent → plan firm
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-10-02", "paid_date": None}
        sent = [{"invoice_id": "INV-1", "step": "friendly", "sent_on": "2026-10-05"}]
        plan = build_plan([inv], sent, "2026-10-12")
        self.assertEqual(len(plan["actions"]), 1)
        self.assertEqual(plan["actions"][0]["step"], "firm")

    def test_final_already_sent_plans_nothing(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-09-01", "paid_date": None}
        sent = [{"invoice_id": "INV-1", "step": "final", "sent_on": "2026-09-26"}]
        plan = build_plan([inv], sent, "2026-10-12")
        self.assertEqual(plan["actions"], [])


class SortingTest(unittest.TestCase):
    def test_actions_sorted_lexicographically(self):
        invoices = [
            {"id": "INV-99", "customer": "B", "email": "b@b.test",
             "amount": 100.0, "currency": "EUR", "due_date": "2026-10-09", "paid_date": None},
            {"id": "INV-100", "customer": "A", "email": "a@a.test",
             "amount": 100.0, "currency": "EUR", "due_date": "2026-10-09", "paid_date": None},
        ]
        plan = build_plan(invoices, [], "2026-10-12")
        ids = [a["invoice_id"] for a in plan["actions"]]
        self.assertEqual(ids, ["INV-100", "INV-99"])  # INV-100 < INV-99 lexicographically

    def test_skipped_sorted_lexicographically(self):
        invoices = [
            {"id": "INV-99", "customer": "B", "email": "b@b.test",
             "amount": None, "currency": "EUR", "due_date": "2026-10-09", "paid_date": None},
            {"id": "INV-100", "customer": "A", "email": "a@a.test",
             "amount": None, "currency": "EUR", "due_date": "2026-10-09", "paid_date": None},
        ]
        plan = build_plan(invoices, [], "2026-10-12")
        ids = [s["invoice_id"] for s in plan["skipped"]]
        self.assertEqual(ids, ["INV-100", "INV-99"])


class SentIgnoredForUnknownIdsTest(unittest.TestCase):
    def test_sent_entry_for_unknown_id_ignored(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-10-09", "paid_date": None}
        sent = [{"invoice_id": "INV-BOGUS", "step": "friendly", "sent_on": "2026-10-10"}]
        plan = build_plan([inv], sent, "2026-10-12")
        self.assertEqual(len(plan["actions"]), 1)

    def test_sent_entry_with_invalid_step_ignored(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-10-09", "paid_date": None}
        sent = [{"invoice_id": "INV-1", "step": "other", "sent_on": "2026-10-10"}]
        plan = build_plan([inv], sent, "2026-10-12")
        # "other" is not a valid step → ignored → action should still be planned
        self.assertEqual(len(plan["actions"]), 1)


class MessageContentTest(unittest.TestCase):
    def test_message_contains_required_fields(self):
        inv = {"id": "INV-1001", "customer": "Acme Corp", "email": "a@a.test",
               "amount": 1250.0, "currency": "EUR", "due_date": "2026-09-30", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        self.assertEqual(len(plan["actions"]), 1)
        msg = plan["actions"][0]["message"]
        self.assertIn("Acme Corp", msg)
        self.assertIn("INV-1001", msg)
        self.assertIn("2026-09-30", msg)
        self.assertIn("EUR", msg)
        self.assertIn("1,250.00", msg)
        # days overdue = 12
        self.assertIn("12", msg)

    def test_message_no_fees_or_interest(self):
        inv = {"id": "INV-1", "customer": "A", "email": "a@a.test",
               "amount": 100.0, "currency": "EUR", "due_date": "2026-09-18", "paid_date": None}
        plan = build_plan([inv], [], "2026-10-12")
        msg = plan["actions"][0]["message"].lower()
        # No made-up fees/interest
        self.assertNotIn("fee", msg)
        self.assertNotIn("interest", msg)
        self.assertNotIn("penalty", msg)


class SampleDataTest(unittest.TestCase):
    """Integration test using the actual sample data files."""

    INVOICES = [
        {"id": "INV-1001", "customer": "Alder Fabrication Ltd", "email": "accounts@alder-fabrication.test",
         "amount": 1250.0, "currency": "EUR", "due_date": "2026-09-30", "paid_date": None},
        {"id": "INV-1002", "customer": "Birchway Studio", "email": "billing@birchway.test",
         "amount": 480.0, "currency": "EUR", "due_date": "2026-10-09", "paid_date": None},
        {"id": "INV-1003", "customer": "Copperleaf Catering", "email": "finance@copperleaf.test",
         "amount": 3200.0, "currency": "EUR", "due_date": "2026-10-11", "paid_date": None},
        {"id": "INV-1004", "customer": "Driftwood Logistics GmbH", "email": "ap@driftwood-logistics.test",
         "amount": 7600.0, "currency": "EUR", "due_date": "2026-09-10", "paid_date": None},
        {"id": "INV-1005", "customer": "Elmstead Print", "email": "office@elmstead.test",
         "amount": 215.5, "currency": "EUR", "due_date": "2026-09-01", "paid_date": None},
        {"id": "INV-1006", "customer": "Fernhill Dental", "email": "admin@fernhill.test",
         "amount": 990.0, "currency": "EUR", "due_date": "2026-09-20", "paid_date": "2026-10-05"},
        {"id": "INV-1007", "customer": "Granite Row Architects", "email": "studio@graniterow.test",
         "amount": 1500.0, "currency": "EUR", "due_date": "2026-02-30", "paid_date": None},
        {"id": "INV-1008", "customer": "Harbour Lane Bakery", "email": "orders@harbourlane.test",
         "amount": 640.0, "currency": "EUR", "due_date": None, "paid_date": None},
        {"id": "INV-1009", "customer": "Ironbridge Tools", "email": "accounts@ironbridge.test",
         "amount": 2100.0, "currency": "EUR", "due_date": "2026-09-30", "paid_date": None},
        {"id": "INV-1010", "customer": "Juniper Events", "email": "hello@juniper-events.test",
         "amount": 560.0, "currency": "EUR", "due_date": "2026-09-25", "paid_date": None},
        {"id": "INV-1010", "customer": "Juniper Events", "email": "hello@juniper-events.test",
         "amount": 720.0, "currency": "EUR", "due_date": "2026-09-28", "paid_date": None},
        {"id": "INV-1011", "customer": "Kestrel Outdoor", "email": "payables@kestrel-outdoor.test",
         "amount": 845.25, "currency": "USD", "due_date": "2026-10-02", "paid_date": None},
        {"id": "INV-1012", "customer": "Larkspur Florists", "email": "shop@larkspur.test",
         "amount": 310.0, "currency": "EUR", "due_date": "2026-10-20", "paid_date": None},
    ]

    SENT = [
        {"invoice_id": "INV-1001", "step": "friendly", "sent_on": "2026-10-03"},
        {"invoice_id": "INV-1004", "step": "friendly", "sent_on": "2026-09-13"},
        {"invoice_id": "INV-1004", "step": "firm", "sent_on": "2026-09-20"},
        {"invoice_id": "INV-1005", "step": "friendly", "sent_on": "2026-09-04"},
        {"invoice_id": "INV-1005", "step": "firm", "sent_on": "2026-09-11"},
        {"invoice_id": "INV-1005", "step": "final", "sent_on": "2026-09-25"},
        {"invoice_id": "INV-1006", "step": "friendly", "sent_on": "2026-09-23"},
    ]

    def test_sample_data_today_2026_10_12(self):
        plan = build_plan(self.INVOICES, self.SENT, "2026-10-12")

        # INV-1001: 12 days overdue, friendly sent, firm not sent → firm
        inv1001 = next((a for a in plan["actions"] if a["invoice_id"] == "INV-1001"), None)
        self.assertIsNotNone(inv1001)
        self.assertEqual(inv1001["step"], "firm")
        self.assertEqual(inv1001["days_overdue"], 12)

        # INV-1002: 3 days overdue, nothing sent → friendly
        inv1002 = next((a for a in plan["actions"] if a["invoice_id"] == "INV-1002"), None)
        self.assertIsNotNone(inv1002)
        self.assertEqual(inv1002["step"], "friendly")

        # INV-1003: 1 day overdue → nothing
        inv1003 = next((a for a in plan["actions"] if a["invoice_id"] == "INV-1003"), None)
        self.assertIsNone(inv1003)

        # INV-1004: 32 days overdue, friendly+firm sent, firm is not >= final → plan final
        inv1004 = next((a for a in plan["actions"] if a["invoice_id"] == "INV-1004"), None)
        self.assertIsNotNone(inv1004)
        self.assertEqual(inv1004["step"], "final")

        # INV-1005: 41 days overdue, final already sent → nothing
        inv1005 = next((a for a in plan["actions"] if a["invoice_id"] == "INV-1005"), None)
        self.assertIsNone(inv1005)

        # INV-1006: paid → nothing in actions
        inv1006 = next((a for a in plan["actions"] if a["invoice_id"] == "INV-1006"), None)
        self.assertIsNone(inv1006)

        # INV-1007: invalid_due_date (2026-02-30) → skipped
        skip1007 = next((s for s in plan["skipped"] if s["invoice_id"] == "INV-1007"), None)
        self.assertIsNotNone(skip1007)
        self.assertEqual(skip1007["reason"], "invalid_due_date")

        # INV-1008: missing due_date → skipped
        skip1008 = next((s for s in plan["skipped"] if s["invoice_id"] == "INV-1008"), None)
        self.assertIsNotNone(skip1008)
        self.assertEqual(skip1008["reason"], "missing_due_date")

        # INV-1009: 12 days overdue, nothing sent → firm
        inv1009 = next((a for a in plan["actions"] if a["invoice_id"] == "INV-1009"), None)
        self.assertIsNotNone(inv1009)
        self.assertEqual(inv1009["step"], "firm")

        # INV-1010: duplicate → skipped (once)
        skip1010 = [s for s in plan["skipped"] if s["invoice_id"] == "INV-1010"]
        self.assertEqual(len(skip1010), 1)
        self.assertEqual(skip1010[0]["reason"], "duplicate_id")

        # INV-1011: 10 days overdue, nothing sent → firm
        inv1011 = next((a for a in plan["actions"] if a["invoice_id"] == "INV-1011"), None)
        self.assertIsNotNone(inv1011)
        self.assertEqual(inv1011["step"], "firm")

        # INV-1012: not yet overdue (due 2026-10-20) → nothing
        inv1012 = next((a for a in plan["actions"] if a["invoice_id"] == "INV-1012"), None)
        self.assertIsNone(inv1012)

    def test_actions_sorted_by_id(self):
        plan = build_plan(self.INVOICES, self.SENT, "2026-10-12")
        ids = [a["invoice_id"] for a in plan["actions"]]
        self.assertEqual(ids, sorted(ids))

    def test_skipped_sorted_by_id(self):
        plan = build_plan(self.INVOICES, self.SENT, "2026-10-12")
        ids = [s["invoice_id"] for s in plan["skipped"]]
        self.assertEqual(ids, sorted(ids))


if __name__ == "__main__":
    unittest.main()
