"""Quality filtering for extracted entities (shared by Postgres + BigQuery).

GCP NL faithfully extracts every name it sees in an article — including the
self-referential furniture of news pages: the publisher's own name, wire-service
attributions ("according to Reuters"), and image-credit boilerplate ("Image:
Getty Images"). Those dominate a naive most-mentioned ranking but are not what
the news is *about*, so the entity charts exclude them.

Two layers, applied together:

1. ``wikipedia_url IS NOT NULL`` — keep only Knowledge-Graph-resolved entities,
   dropping generic common nouns the model tags ("investors", "markets", "CEO",
   "one", "two"). (Applied at the query site.)
2. ``PUBLISHER_ENTITY_DENYLIST`` — drop news organisations, wire services, and
   credit-line names. These ARE real orgs (they have a wikipedia_url), so layer
   1 does not catch them; this explicit denylist does.

Names are compared case-insensitively (``LOWER(entity_name)``), so every entry
here is lowercase.
"""

from __future__ import annotations

# News organisations / wire services / image-credit names that appear as
# self-referential pollution rather than news subjects. Includes our own
# ingestion sources and the common publishers/agencies they syndicate from,
# with the spelling variants GCP NL emits (e.g. "Getty Images" and "Getty").
PUBLISHER_ENTITY_DENYLIST: frozenset[str] = frozenset(
    {
        # Wire services / agencies
        "reuters",
        "associated press",
        "ap",
        "afp",
        "agence france-presse",
        "bloomberg",
        "pa media",
        "press association",
        # Broadcasters / papers (our sources + common syndication partners)
        "bbc",
        "cnn",
        "cnbc",
        "the guardian",
        "guardian",
        "the new york times",
        "new york times",
        "nytimes",
        "the independent",
        "independent",
        "sky news",
        "politico",
        "time",
        "yahoo",
        "yahoo news",
        "dw",
        "deutsche welle",
        "financial post",
        "foreign policy",
        "businesstoday",
        "business today",
        "phys.org",
        "popular science",
        "scidev.net",
        "scitechdaily",
        "google news",
        "google-news",
        # Image-credit boilerplate
        "getty",
        "getty images",
        "reuters/",
        "shutterstock",
        "associated press/",
    }
)


def publisher_denylist_lower() -> list[str]:
    """The denylist as a sorted list of lowercase strings, for SQL parameters.

    Sorted so the bound parameter array is deterministic across calls (stable
    query text / test fixtures).
    """
    return sorted(PUBLISHER_ENTITY_DENYLIST)
