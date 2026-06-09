# Mediastack source slugs. Fetched for every configured language
# (MEDIASTACK_LANGUAGES, e.g. "en,de"), so an outlet only returns articles in
# the languages it actually publishes — English outlets serve EN, the German
# national outlets below serve DE.
SOURCES = [
    # English-language outlets
    "dw",
    "bbc",
    "cnn",
    "bloomberg",
    "politico",
    "independent",
    "time",
    "nytimes",
    "guardian",
    "skynews",
    "foreignpolicy",
    "businesstoday",
    "financialpost",
    "iotbusinessnews",
    "yahoo",
    "cnbc",
    "google-news",
    "scidev",
    "scitechdaily",
    "phys",
    "scienceandtechnologyresearchnews",
    "popsci",
    # German national outlets (slugs verified live against the Mediastack
    # /v1/sources + /v1/news endpoints — each returns lang=de articles). `dw`
    # above also has a German feed and is reused. `die-welt` is the correct
    # slug (not `welt`); `ard-tagesschau` duplicates `tagesschau`.
    "spiegel",
    "zeit",
    "faz",
    "sueddeutsche",
    "die-welt",
    "handelsblatt",
    "tagesschau",
    "stern",
    "focus",
]

# German-language outlets only (incl. dw's German feed). Used by the German
# backfill job to pull historical `languages=de` articles from just these
# sources, rather than querying every English outlet for German content it
# won't have.
GERMAN_SOURCES = [
    "dw",
    "spiegel",
    "zeit",
    "faz",
    "sueddeutsche",
    "die-welt",
    "handelsblatt",
    "tagesschau",
    "stern",
    "focus",
]
