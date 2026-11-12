"""The /merchants page: its numbers equal the run files, the quote slot stays hidden while empty, the form stores nothing."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SITE = ROOT / "site"


def page_server():
    from scripts import record_scene as rs
    return rs.StaticSite(rs.SITE)


class MerchantsData(unittest.TestCase):
    def setUp(self):
        self.m = json.loads((SITE / "data" / "merchants.json").read_text(encoding="utf-8"))

    def test_counts_equal_counts_json_and_the_batch_run_file(self):
        counts = json.loads((SITE / "data" / "counts.json").read_text(encoding="utf-8"))
        self.assertEqual(self.m["counts"], counts)
        batch = json.loads((ROOT / self.m["batch_source"]).read_text(encoding="utf-8"))
        self.assertEqual(counts["cases"], len(batch["cases"]))
        self.assertEqual(counts["settled"], sum(1 for c in batch["cases"] if c["outcome"] == "settled_inquiry_no_fee"))

    def test_voice_block_equals_the_voice_run_file(self):
        voice = json.loads((ROOT / self.m["voice_source"]).read_text(encoding="utf-8"))
        by = {c["case"]: c for c in voice["cases"]}
        c4 = self.m["voice"]["case4"]
        self.assertEqual(c4["refund_id"], by[4]["paypal"]["refund_id"])
        self.assertEqual(c4["status"], by[4]["paypal"]["status"])
        self.assertEqual(c4["writes"], 1)
        c9 = self.m["voice"]["case9"]
        self.assertIs(c9["money_moved"], False)
        self.assertEqual(c9["writes"], 1)

    def test_fees_come_from_the_cited_fee_source_and_the_sandbox_record(self):
        from clearwake import fees
        k = self.m["cost"]
        self.assertEqual(k["standard_fee"], f"{fees.STANDARD_FEE_MINOR / 100:.2f}")
        self.assertEqual(k["high_volume_fee"], f"{fees.HIGH_VOLUME_FEE_MINOR / 100:.2f}")
        recs = sorted((ROOT / "data" / "runs").glob("case-records-*.json"))
        body = json.loads(recs[-1].read_text(encoding="utf-8"))
        fee = next(m["amount"]["value"] for c in body["cases"] if c.get("n") == 3 for m in c["paypal_record"]["money_movements"] if m.get("reason") == "DISPUTE_SETTLEMENT_FEE")
        self.assertEqual(k["settlement_fee"], fee)

    def test_the_page_types_no_figure_and_stores_nothing(self):
        html = (SITE / "merchants.html").read_text(encoding="utf-8")
        js = (SITE / "merchants.js").read_text(encoding="utf-8")
        for number in ("0.77", "15.00", "30.00", "9J379948UG997645D"):
            self.assertNotIn(number, html)
            self.assertNotIn(number, js)
        for banned in ("localStorage", "sessionStorage", "indexedDB", "XMLHttpRequest", "sendBeacon", "POST"):
            self.assertNotIn(banned, js)

    def test_every_page_links_to_merchants_and_the_audit_lists_it(self):
        for name in ("index", "control-room", "break", "proof", "developers", "merchants"):
            self.assertIn('href="/merchants"', (SITE / f"{name}.html").read_text(encoding="utf-8"), name)
        self.assertIn('"/merchants"', (ROOT / "scripts" / "check_pages.py").read_text(encoding="utf-8"))

    def test_no_banned_words_or_dashes_in_the_new_page(self):
        text = (SITE / "merchants.html").read_text(encoding="utf-8")
        text = re.sub(r"<[^>]+>", " ", text)
        for word in ("demo", "rehearsal", "invented", "synthetic", "fake", "mock", "simulated", "learning", "beta"):
            self.assertIsNone(re.search(r"\b" + word + r"\b", text, re.I), word)
        self.assertNotIn("!", text)
        self.assertNotIn("—", text)
        self.assertNotIn("–", text)


class MerchantsBrowser(unittest.TestCase):
    def run_page(self, path, quotes, check):
        from playwright.sync_api import sync_playwright
        with page_server() as base:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": 1200, "height": 900})
                if quotes is not None:
                    page.route("**/data/quotes.json", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(quotes)))
                page.goto(base.rstrip("/") + path, wait_until="networkidle")
                page.wait_for_timeout(500)
                try:
                    return check(page)
                finally:
                    browser.close()

    def test_page_numbers_equal_the_run_files(self):
        m = json.loads((SITE / "data" / "merchants.json").read_text(encoding="utf-8"))
        shown = self.run_page("/merchants", None, lambda p: p.evaluate("[...document.querySelectorAll('#m-nums dd')].map(d => d.textContent)"))
        c = m["counts"]
        self.assertEqual(shown, [f"{c['resolved']} of {c['cases']}", str(c["settled"]), str(c["answered_with_proof"]), str(c["waiting_for_owner"])])
        text = self.run_page("/merchants", None, lambda p: p.inner_text("#m-cost"))
        self.assertIn("USD " + m["cost"]["standard_fee"], text)
        self.assertIn("USD " + m["cost"]["settlement_fee"], text)

    def test_quote_slot_is_hidden_while_empty(self):
        for path in ("/merchants", "/proof"):
            hidden = self.run_page(path, [], lambda p: p.evaluate("document.querySelector('#quotes').hidden"))
            self.assertTrue(hidden, path)
        self.assertRegex((ROOT / "video" / "endcard.html").read_text(encoding="utf-8"), r"data-quotes hidden")

    def test_quote_slot_shows_only_a_quote_with_permission(self):
        good = {"text": "It saved me a fee.", "name": "A Seller", "role": "sells notebooks", "permission": True}
        no_permission = {"text": "Hidden words", "name": "Someone", "permission": False}
        out = self.run_page("/merchants", [good, no_permission], lambda p: (p.evaluate("document.querySelector('#quotes').hidden"), p.inner_text("#quotes")))
        self.assertFalse(out[0])
        self.assertIn("It saved me a fee.", out[1])
        self.assertNotIn("Hidden words", out[1])
        self.assertTrue(self.run_page("/merchants", [no_permission], lambda p: p.evaluate("document.querySelector('#quotes').hidden")))

    def test_the_form_builds_a_mail_link_with_the_four_answers(self):
        def check(page):
            page.fill("#f-name", "Test Seller")
            page.fill("#f-sell", "notebooks")
            page.fill("#f-count", "3")
            page.check("input[name=quote][value=yes]")
            page.click("#m-form button[type=submit]")
            page.wait_for_timeout(600)
            return page.inner_text("#m-status")
        self.assertIn("mail app", self.run_page("/merchants", None, check))

    def test_empty_form_asks_for_all_four_answers(self):
        def check(page):
            page.click("#m-form button[type=submit]")
            return page.inner_text("#m-status")
        self.assertIn("all four", self.run_page("/merchants", None, check))


if __name__ == "__main__":
    unittest.main()
