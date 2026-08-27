"""
Tests for src/i18n.py - the translation lookup helper and, importantly,
consistency across the three language packs (de/en/fr). See
docs/i18n-README.md for the authoring conventions these tests enforce.
"""

import ast
from pathlib import Path

import pytest

from i18n import TEXTS, get_text

LANGUAGES = ["de", "en", "fr"]
APP_PY_PATH = Path(__file__).resolve().parent.parent / "src" / "app.py"


def test_all_languages_define_the_exact_same_keys():
    # The most valuable test in this file: if a key is added/renamed in
    # only one language block, get_text() would silently fall back to
    # German (or the raw key) for the others instead of failing loudly -
    # this test is what actually catches that drift, at review/CI time
    # rather than a student noticing an English label stuck in German.
    key_sets = {lang: set(TEXTS[lang]) for lang in LANGUAGES}
    de_keys = key_sets["de"]
    for lang in LANGUAGES:
        missing = de_keys - key_sets[lang]
        extra = key_sets[lang] - de_keys
        assert not missing, f"{lang} is missing keys present in de: {sorted(missing)}"
        assert not extra, f"{lang} has keys not present in de: {sorted(extra)}"


def test_all_translation_values_are_non_empty_strings():
    for lang in LANGUAGES:
        for key, value in TEXTS[lang].items():
            assert isinstance(value, str)
            assert value.strip() != "", f"{lang}.{key} is empty"


def test_get_text_returns_the_requested_language():
    assert get_text("en", "export.subheader") == TEXTS["en"]["export.subheader"]


def test_get_text_falls_back_to_german_for_unknown_language():
    # "xx" is not a configured language pack at all.
    assert get_text("xx", "export.subheader") == TEXTS["de"]["export.subheader"]


def test_get_text_falls_back_to_key_when_missing_everywhere():
    assert get_text("de", "this.key.does.not.exist") == "this.key.does.not.exist"


def test_get_text_formats_placeholders():
    text = get_text("de", "export.ics_summary", count=5)
    assert "5" in text


def test_get_text_returns_unformatted_text_on_placeholder_mismatch():
    # If the caller forgets a placeholder the translated string expects,
    # get_text must degrade gracefully (return the raw text) instead of
    # raising a KeyError and crashing the page.
    text = get_text("de", "export.ics_summary")  # missing the {count} kwarg
    assert text == TEXTS["de"]["export.ics_summary"]


@pytest.mark.parametrize("lang", LANGUAGES)
def test_column_label_namespace_is_populated(lang):
    # "col.*" keys back app.py's c() helper (dataframe column headers) -
    # spot-check one to make sure that namespace is genuinely translated,
    # not just present as an empty placeholder.
    assert TEXTS[lang]["col.module"].strip() != ""


# --- app.py <-> i18n.py cross-check -------------------------------------
# The tests above only check TEXTS for *internal* consistency (do de/en/fr
# agree with each other). None of them can catch app.py calling
# t("some.key") for a key that was never added to TEXTS at all - that
# failure mode is exactly what was reported live against this app: a
# sidebar card showing the literal text "sidebar.section.zusatzmodule"
# instead of a translated label, because get_text()'s fallback chain (see
# its own docstring) is deliberately lenient at runtime - it shows the
# raw key instead of crashing the page, which is good for end users but
# means a missing key is otherwise silent. These two tests read app.py's
# actual source and make that loud again, at test time.

def _static_i18n_keys_referenced_in_app_py() -> set[str]:
    """
    Every literal-string key passed to t("...")/c("...") in app.py - the
    real, ground-truth set of i18n keys the running app can ask for.

    Parses app.py's actual syntax tree (via `ast`) rather than
    regex-scanning the source text - an earlier version of this function
    used a regex, which does NOT understand Python syntax and happily
    "matched" illustrative example text like `t("upload.\n    dates_
    missing", count=3))` inside t()'s own docstring (a few lines above
    this file, prose showing how to call t() - never executed as code) as
    if it were a real call, producing false-positive "missing key"
    reports. Walking the AST's actual Call nodes can't make that mistake:
    a docstring is just a string *value* in the tree, never parsed as
    nested Python syntax, so text that merely *looks* like a call inside
    a comment or docstring is never visited as one.

    Not covered: the ~8 call sites in app.py that build a key
    dynamically at runtime (e.g. `t(f"weekday.{day_key}")`,
    `t(f"chart.settings_{option_key}")`) - an f-string's key can't be
    known without executing it. This is a known, accepted gap in this
    scan, not a silently missed case: every one of those dynamic
    prefixes ("weekday.", "chart.palette.", "chart.settings_", "col.")
    already has at least one *static* call site elsewhere in app.py that
    this function does catch, so a wholesale missing namespace would
    still be caught - only a single missing variant within an
    otherwise-present namespace could slip through.
    """
    tree = ast.parse(APP_PY_PATH.read_text(encoding="utf-8"), filename=str(APP_PY_PATH))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args):
            continue
        first_arg = node.args[0]
        if not (isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str)):
            continue  # dynamic key (f-string, variable, ...) - not statically checkable
        if node.func.id == "t":
            keys.add(first_arg.value)
        elif node.func.id == "c":
            keys.add(f"col.{first_arg.value}")
    return keys


def test_every_static_i18n_key_used_in_app_py_is_defined():
    referenced_keys = _static_i18n_keys_referenced_in_app_py()
    # Sanity check on the extraction itself: app.py has hundreds of t()/
    # c() calls, so finding suspiciously few would mean the regex broke
    # (e.g. after a refactor that changes how t()/c() are invoked) rather
    # than that app.py genuinely stopped using translations.
    assert len(referenced_keys) > 100

    missing = sorted(
        (lang, key)
        for key in referenced_keys
        for lang in LANGUAGES
        if key not in TEXTS[lang]
    )
    assert not missing, (
        f"app.py calls t()/c() with {len(missing)} (language, key) combination(s) that "
        "don't exist in i18n.TEXTS - these render as the raw key string in the UI "
        f"instead of translated text: {missing}"
    )


def test_get_text_never_echoes_a_key_that_app_py_actually_uses():
    """
    Stronger, behavioural companion to the test above: not just "the key
    exists in TEXTS", but "calling get_text() for it doesn't fall through
    to the raw-key fallback" - also guards against a key existing with a
    falsy-ish value (empty string) that get_text()'s
    `lang_pack.get(key) or ...` chain would treat as absent.
    """
    for key in sorted(_static_i18n_keys_referenced_in_app_py()):
        for lang in LANGUAGES:
            resolved = get_text(lang, key)
            assert resolved != key, (
                f"get_text({lang!r}, {key!r}) returned the raw key instead of a translation "
                "- app.py uses this key, but it resolves to nothing in any language."
            )
