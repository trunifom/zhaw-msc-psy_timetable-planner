"""
Tests for src/i18n.py - the translation lookup helper and, importantly,
consistency across the three language packs (de/en/fr). See
docs/i18n-README.md for the authoring conventions these tests enforce.
"""

import pytest

from i18n import TEXTS, get_text

LANGUAGES = ["de", "en", "fr"]


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
