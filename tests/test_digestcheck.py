"""Unit tests for digestcheck.verify_attribution - the mechanical check
that mechanisms a digest attributes to a repo actually appear in that
repo's OWN gathered content (the v2.1 confabulation fix: Vivaha's
Cloudflare-Worker pattern was once described as if it were Friday's)."""

from __future__ import annotations

import unittest

from friday.contracts import Idempotency, REGISTRY
from friday.errors import PreconditionError
from friday.l1.digestcheck import verify_attribution
from tests.helpers import EnvTestCase


class TestVerifyAttribution(EnvTestCase):
    def _ctx(self, **kw) -> dict:
        return kw

    def test_correct_attribution_passes(self):
        ctx = {"aether": "sync.sh syncs the WSL workspace into ~/aether for fast builds"}
        digest = "Suggestion: Adopt Aether's sync.sh workspace helper for config syncing."
        out = verify_attribution(digest, ctx)
        self.assertIn("## Attribution check", out)
        self.assertIn("All 1 attributed mechanism(s) confirmed", out)
        self.assertNotIn("UNVERIFIED", out)

    def test_cross_repo_misattribution_flagged(self):
        """The exact v2.1 failure shape: Vivaha's Cloudflare-Worker pattern
        attributed to Friday. Must be flagged, not silently delivered."""
        ctx = {
            "friday": "gmail watcher capability-gap executor tests",
            "vivaha": "image moderation via a Cloudflare Worker with a background queue",
        }
        digest = "Suggestion: Use Friday's cloudflare worker pattern for image moderation."
        out = verify_attribution(digest, ctx)
        self.assertIn("UNVERIFIED attribution", out)
        self.assertIn("cloudflare worker pattern", out)
        self.assertIn("Friday", out)
        self.assertIn("Vivaha's content instead", out)  # points at the real owner

    def test_unconnected_suggestion_flagged(self):
        """v2's S1 shape: 'daily email summaries' attributed to Vivaha when
        nothing in Vivaha's gathered content mentions email summaries."""
        ctx = {"vivaha": "wedding palette retheme, mega menu navbar, supabase migration"}
        digest = "Suggestion: Add daily email summaries to Vivaha's dashboard."
        out = verify_attribution(digest, ctx)
        self.assertIn("UNVERIFIED attribution", out)
        self.assertIn("daily email summaries", out)

    def test_legit_roadmap_claim_passes(self):
        ctx = {"vivaha": "Q4: Move the Admin moderation tools out of the main Next.js app"}
        digest = "Suggestion: implement Vivaha's admin moderation tools as a separate app."
        out = verify_attribution(digest, ctx)
        self.assertIn("All 1 attributed mechanism(s) confirmed", out)

    def test_no_claims_is_honest_not_silent(self):
        digest = "Friday had commits about gmail and the watcher. Vivaha rethemed its UI."
        out = verify_attribution(digest, {"friday": "gmail watcher", "vivaha": "retheme"})
        self.assertIn("No concrete mechanism attributions detected", out)
        self.assertNotIn("UNVERIFIED", out)

    def test_dotted_mechanism_in_no_repo_flagged(self):
        digest = "Suggestion: adopt mysterio.sh everywhere."
        out = verify_attribution(digest, {"friday": "gmail watcher", "vivaha": "retheme"})
        self.assertIn("UNVERIFIED mechanism: 'mysterio.sh'", out)

    def test_empty_digest_raises(self):
        with self.assertRaises(PreconditionError):
            verify_attribution("", {"friday": "x"})

    def test_empty_context_raises(self):
        with self.assertRaises(PreconditionError):
            verify_attribution("Suggestion: adopt Aether's sync.sh.", {})

    def test_context_values_may_be_lists(self):
        ctx = {
            "friday": ["gmail watcher commit", "log rotation + redaction"],
            "vivaha": ["roadmap: admin dashboard extraction"],
        }
        digest = "Suggestion: reuse Friday's log rotation in Vivaha's admin dashboard."
        out = verify_attribution(digest, ctx)
        self.assertIn("All 1 attributed mechanism(s) confirmed", out)

    def test_typographic_apostrophes_are_matched(self):
        """Regression (2026-08-11): a real LLM digest used U+2019
        right-single-quotes (\u2019) and non-breaking hyphens - the
        ASCII-only possessive regex matched NOTHING, silently skipping
        the whole check. Normalized matching must catch the claim."""
        ctx = {"friday": "capability-gap loop: refusal record triage gate"}
        digest = "Suggestion: Apply Friday\u2019s capability\u2011gap loop to Vivaha."
        out = verify_attribution(digest, ctx)
        self.assertIn("All 1 attributed mechanism(s) confirmed", out)
        self.assertNotIn("UNVERIFIED", out)

    def test_typographic_quote_misattribution_still_flagged(self):
        ctx = {"friday": "gmail watcher tests", "vivaha": "cloudflare worker queue"}
        digest = "Use Friday\u2019s cloudflare worker pattern for moderation."
        out = verify_attribution(digest, ctx)
        self.assertIn("UNVERIFIED attribution", out)
        self.assertIn("Vivaha's content instead", out)

    def test_idempotent(self):
        ctx = {"aether": "sync.sh for WSL builds"}
        digest = "Suggestion: Adopt Aether's sync.sh helper."
        self.assertEqual(verify_attribution(digest, ctx), verify_attribution(digest, ctx))

    def test_registered(self):
        c = REGISTRY.get("digestcheck.verify_attribution")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)
        self.assertTrue(hasattr(verify_attribution, "__contract__"))


if __name__ == "__main__":
    unittest.main()
