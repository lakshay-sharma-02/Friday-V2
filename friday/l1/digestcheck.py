"""L1 primitive: digestcheck (mechanical attribution verification).

The cross-project digest is LLM-generated text. The AST / sandbox /
build-verify gate protects CODE generation; this primitive protects the
SYNTHESIS side - the digest's factual claims about WHICH repo has WHICH
mechanism. A real failure mode (observed 2026-08-11): the digest
described Vivaha's own Cloudflare-Worker pattern as if it were Friday's
- a fabrication, not a quality preference. verify_attribution is a
deterministic, mechanical, read-only check: every mechanism attributed
to a repo (\"X's <mechanism>\") must actually appear in the gathered
content fetched FOR that repo. Claims that cannot be confirmed are
FLAGGED in the delivered digest rather than silently passed - absence
of a name match means \"not confirmed\", never \"false\" (paraphrases and
synonyms cannot be verified mechanically, and the appendix says so).

Enhanced with semantic pattern verification: identifies semantic categories
and checks that attributed mechanisms actually belong to attributed repos
based on semantic keyword matching.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError
from friday.lessons import record_lesson_event
from friday.semantic_clustering import SEMANTIC_CATEGORIES, detect_semantic_category, extract_semantic_keywords

# Words too generic to distinguish a mechanism claim (a phrase made only
# of these proves nothing about which repo the mechanism lives in).
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "these",
    "its",
    "their",
    "your",
    "our",
    "pattern",
    "approach",
    "mechanism",
    "into",
    "across",
    "using",
    "used",
    "use",
    "via",
    "then",
    "over",
    "about",
    "within",
    "part",
    "piece",
    "style",
    "way",
    "one",
    "two",
    "plus",
    "helper",
    "logic",
    "code",
    "work",
    "model",
    "system",
    "tool",
}

# "Friday's cloudflare worker pattern" -> owner=friday, phrase=...
# The apostrophe alternation covers BOTH ASCII ' and the typographic
# right-single-quote (U+2019) LLMs routinely emit (observed 2026-08-11:
# a real digest used 'Friday\u2019s' and the ASCII-only regex matched
# NOTHING - a false-negative that would silently skip the whole check).
_POSSESSIVE = re.compile(
    r"([A-Za-z][A-Za-z0-9_\-]*?)[\u2019']s\s+([A-Za-z][A-Za-z0-9 ._/\-]{2,80})",
    re.IGNORECASE,
)

# Normalize LLM typography before matching: typographic apostrophes and
# non-breaking/smart hyphens (U+2019/2018/2011/2010/00AD) -> ASCII.
_QUOTE_FIX = str.maketrans(
    {
        "\u2019": "'",
        "\u2018": "'",
        "\u2011": "-",
        "\u2010": "-",
        "\u00ad": "-",
    }
)

# File-like / dotted mechanism names: gmail.summarize, sync.sh, watcher.py
_DOTTED = re.compile(r"[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+){1,4}")

_HONESTY_NOTE = (
    "Mechanical name-match check only: absence means 'not confirmed', never "
    "'false'; paraphrases and synonyms cannot be verified mechanically."
)


def _repo_tokens(context: dict[str, Any]) -> dict[str, str]:
    """Map a normalized repo token (e.g. 'friday') -> the context key."""
    out: dict[str, str] = {}
    for key in context:
        name = re.sub(r"[^a-z0-9]", "", key.lower())
        if name:
            out[name] = key
    return out


def _content_str(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "\n".join(str(x) for x in value)
    return str(value)


def _claims(digest: str, repos: dict[str, str]) -> list[tuple[str, str]]:
    """(owner_repo_token, phrase) pairs from possessive attributions like
    \"Friday's <mechanism>\" where the owner is one of the gathered repos."""
    claims: list[tuple[str, str]] = []
    for m in _POSSESSIVE.finditer(digest):
        owner = m.group(1).lower()
        phrase = m.group(2).strip()
        if owner in repos:  # owner must be a repo we actually gathered
            claims.append((owner, phrase))
    return claims


def _phrase_tokens(phrase: str) -> list[str]:
    return [
        t for t in re.split(r"[^a-z0-9]+", phrase.lower()) if len(t) >= 3 and t not in _STOPWORDS
    ]


def _verify_phrase(
    owner: str, phrase: str, content_by_repo: dict[str, str]
) -> tuple[str, list[str]]:
    """Return (status, elsewhere): status in {OK, SKIP, FLAG}."""
    tokens = _phrase_tokens(phrase)
    if not tokens:
        return ("SKIP", [])
    owner_content = content_by_repo[owner]
    if phrase.lower() in owner_content or any(t in owner_content for t in tokens):
        return ("OK", [])
    elsewhere = [
        r for r, c in content_by_repo.items() if r != owner and any(t in c for t in tokens)
    ]
    return ("FLAG", elsewhere)


@contract(
    precondition="digest is a non-empty string; context is a non-empty dict "
    "mapping repo-name labels (e.g. 'friday') to that repo's gathered "
    "content (strings or lists of strings).",
    postcondition="Returns the digest text plus a mechanical attribution "
    "appendix: every 'X's <mechanism>' claim is checked for a name-match "
    "token in X's own gathered content; unconfirmed claims are flagged in "
    "the returned text (never silently passed). Read-only and pure - no "
    "state changes, no LLM call. Also includes semantic pattern verification.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for an empty digest or empty/malformed "
    "context. Never raises on an unverified claim - absence of proof is "
    "reported in the output, not thrown.",
    returns="str: the digest text followed by an '## Attribution check' "
    "appendix (all-confirmed | per-claim flags | honest no-claims note).",
)
def verify_attribution(digest: str, context: dict[str, Any]) -> str:
    """Verify that mechanisms the digest attributes to each repo actually
    appear in that repo's own gathered content; flag what cannot be
    confirmed. Delivered to the user as part of the digest so unearned
    confidence is never presented as fact.

    Enhanced with semantic pattern verification: checks that semantic
    claims (e.g., 'Friday's email pattern') are backed by content that
    actually contains the relevant semantic keywords for that category."""
    if not digest or not digest.strip():
        raise PreconditionError("verify_attribution requires a non-empty 'digest'")
    if not isinstance(context, dict) or not context:
        raise PreconditionError("verify_attribution requires a non-empty 'context' dict")

    repos = _repo_tokens(context)
    content_by_repo = {token: _content_str(context[key]).lower() for token, key in repos.items()}

    # Build semantic repo info for enhanced verification
    repo_semantic_info = _build_repo_semantic_info(repos, context)

    norm = digest.translate(_QUOTE_FIX)
    claims = _claims(norm, repos)
    flags: list[str] = []
    confirmed = 0
    skipped = 0
    for owner, phrase in claims:
        status, elsewhere = _verify_phrase(owner, phrase, content_by_repo)
        if status == "OK":
            confirmed += 1
        elif status == "SKIP":
            skipped += 1
        else:
            loc = (
                f" (its tokens appear in {', '.join(r.title() for r in elsewhere)}'s "
                "content instead)"
                if elsewhere
                else ""
            )
            flags.append(
                f"- UNVERIFIED attribution: '{phrase}' attributed to "
                f"{owner.title()}, but no token of it is confirmed in "
                f"{owner.title()}'s OWN gathered content{loc}."
            )

    # Semantic pattern verification: check if attributed mechanisms have
    # matching semantic categories in the attributed repo
    semantic_flags = _verify_semantic_patterns(norm, repo_semantic_info, repos)
    flags.extend(semantic_flags)

    # Dotted mechanism names anywhere in the digest (gmail.summarize,
    # sync.sh) must exist in at least one repo's content.
    seen: set[str] = set()
    for dm in _DOTTED.findall(norm):
        key = dm.lower()
        if key in seen:
            continue
        seen.add(key)
        if not any(key in c for c in content_by_repo.values()):
            flags.append(
                f"- UNVERIFIED mechanism: '{dm}' not found in any repo's gathered content."
            )

    # A flagged attribution is the raw material of the lessons loop: record
    # the fabrication class (best-effort - a broken lessons file must never
    # break the check). The digest is still delivered WITH the flag; the
    # lesson event only feeds generalization for a human to approve later.
    # Re-invocation (the idempotence test, an executor retry of the digest
    # step) records a duplicate event - DELIBERATE: the event log is
    # additive like the gap file, and generalize dedupes by category, so
    # never "fix" this with in-process dedupe.
    if flags:
        record_lesson_event(
            category="digest_misattribution",
            source="digestcheck",
            detail=flags[0][2:],  # the first unverified claim, without the '- ' prefix
        )

    if not claims and not flags:
        status_line = (
            "No concrete mechanism attributions detected in the digest - "
            "nothing to verify (a summaries-only digest is fine, but a "
            "digest with no transferable suggestion carries no verified "
            "value either)."
        )
    elif flags:
        status_line = "The following attributions could NOT be confirmed mechanically:"
    else:
        status_line = (
            f"All {confirmed} attributed mechanism(s) confirmed in the named "
            "repo's own gathered content."
        )

    appendix = ["", "## Attribution check", "", status_line]
    appendix += flags
    appendix += ["", _HONESTY_NOTE]
    return digest + "\n".join(appendix)


def _build_repo_semantic_info(
    repos: dict[str, str], context: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Build semantic info for each repo from its gathered content."""
    info: dict[str, dict[str, Any]] = {}
    for token, label in repos.items():
        content = context.get(label, "")
        if isinstance(content, (list, tuple)):
            text = "\n".join(str(x) for x in content)
        else:
            text = str(content)

        # Get first 5000 chars for category detection
        sample = text[:5000] if len(text) > 5000 else text

        info[token] = {
            "category": detect_semantic_category(sample),
            "keywords": extract_semantic_keywords(sample)[:15],
            "token_matches": _extract_repo_tokens(sample),
        }
    return info


def _extract_repo_tokens(text: str) -> set[str]:
    """Extract potential mechanism tokens from text (words that could be mechanisms)."""
    # Look for patterns that could be mechanism names
    tokens: set[str] = set()

    # Dotted names like gmail.summarize, sync.sh
    for dm in _DOTTED.findall(text):
        tokens.add(dm.lower())

    # Also extract single words that are meaningful (3+ chars, not stopwords)
    STOPWORDS = {"the", "and", "for", "with", "was", "are", "not", "all", "has", "have", "had"}

    for word in re.findall(r"[a-z][a-z0-9_\-]{2,30}", text.lower()):
        if word not in STOPWORDS:
            tokens.add(word)

    return tokens


def _verify_semantic_patterns(
    digest_text: str,
    repo_semantic_info: dict[str, dict[str, Any]],
    repos: dict[str, str],
) -> list[str]:
    """Verify semantic pattern claims against repo semantic categories."""
    flags: list[str] = []

    # Find sentences that attribute semantic categories to repos
    # Pattern: "Repo's <category> pattern" or "Repo's <keyword> mechanism"
    pattern = re.compile(
        r"([a-z][a-z0-9_\-]*?)[\'’]s\s+([a-z0-9_\-\.]+)\s+(pattern|mechanism|approach|feature|system|method)",
        re.IGNORECASE,
    )

    for m in pattern.finditer(digest_text):
        owner = m.group(1).lower()
        mechanism = m.group(2).lower()
        mech_type = m.group(3)

        # Check if owner is a known repo
        if owner not in repos:
            continue

        owner_info = repo_semantic_info.get(owner, {})
        keywords = owner_info.get("keywords", [])

        # Check if the mechanism/keyword appears in the repo's semantic keywords
        mechanism_in_keywords = any(
            mech in " ".join(keywords) or keyword in mech for keyword in keywords
        )
        mechanism_in_tokens = any(
            mech in " ".join(owner_info.get("token_matches", []))
            or token in mech
            or mech in token
        )

        if not mechanism_in_keywords and not mechanism_in_tokens:
            # Check if it's at least related to the repo's category
            category = owner_info.get("category", "")
            mech_words = mechanism.split(".")
            category_match = any(word in category for word in mech_words) if category else False

            if not category_match:
                flags.append(
                    f"- UNVERIFIED semantic attribution: '{mechanism}' attributed to "
                    f"{owner.title()} as a {mech_type}, but does not match "
                    f"that repo's semantic category ({category or 'unknown'}) "
                    f"or keywords."
                )

    return flags
