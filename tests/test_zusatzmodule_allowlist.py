"""
Tests for the (currently disabled) Zusatzmodule Modul-Nr/Kurs-Nr allowlist
pre-filter in data_loader.py - see the "ZUSATZMODULE-VORFILTER" section
there and settings/zusatzmodule_allowlist.json.

This feature has no real allowlist to filter against yet (ZHAW has not
published one) - it exists so that a future session only needs to drop in
the real list and flip ZUSATZMODULE_ALLOWLIST_ENABLED, instead of designing
the filter from scratch. Most tests here therefore exercise the loader/
filter functions directly with a temporary settings file and an explicit
monkeypatch of the enabled flag, rather than relying on any real data.
"""

import json

import pandas as pd
import pytest

import data_loader
from data_loader import (
    _filter_zusatzmodule_by_allowlist,
    load_schedule_from_dataframe,
    load_zusatzmodule_allowlist,
)


def _minimal_zusatzmodule_df(rows: list) -> pd.DataFrame:
    """
    Build a minimal, already-header-shaped raw dataframe (mirroring a real
    ZHAW export's own header spellings, like the rest of this test suite -
    see test_data_loader.py) with one row per dict in `rows`. Every row
    needs the structurally required columns (wochentag/startzeit/endzeit/
    modulname) plus modul_nr/kurs_nr, since those are what the allowlist
    filter checks.
    """
    return pd.DataFrame(
        [
            {
                "Wochentag": row.get("wochentag", "Montag"),
                "Startzeit": row.get("startzeit", "08:00"),
                "Endzeit": row.get("endzeit", "10:00"),
                "Modulname": row.get("modulname", "Testmodul"),
                "Modul-Nr": row.get("modul_nr", ""),
                "Kurs-Nr": row.get("kurs_nr", ""),
                "ECTS": row.get("ects", 1),
            }
            for row in rows
        ]
    )


# --- ZUSATZMODULE_ALLOWLIST_ENABLED default -----------------------------------

def test_allowlist_is_disabled_by_default():
    # The whole point of this feature at this stage: it must ship inert.
    # If this ever flips to True by accident, every test below that relies
    # on monkeypatching it back to True to test the "future" behaviour
    # would stop proving anything - so pin the shipped default explicitly.
    assert data_loader.ZUSATZMODULE_ALLOWLIST_ENABLED is False


# --- load_zusatzmodule_allowlist() --------------------------------------------

def test_load_zusatzmodule_allowlist_reads_shipped_settings_file():
    # The file committed at settings/zusatzmodule_allowlist.json is a
    # fictional placeholder (see its own "_hinweis" field), but it must
    # still be valid, loadable JSON in the shape this function expects -
    # this is what a future session will build on.
    allowlist = load_zusatzmodule_allowlist()
    assert allowlist is not None
    assert "ZZ1" in allowlist["modul_nr"]
    assert "ZZ1-1" in allowlist["kurs_nr"]


def test_load_zusatzmodule_allowlist_missing_file_returns_none(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"
    assert load_zusatzmodule_allowlist(missing_path) is None


def test_load_zusatzmodule_allowlist_malformed_json_returns_none(tmp_path):
    bad_file = tmp_path / "broken.json"
    bad_file.write_text("{ this is not valid json", encoding="utf-8")
    assert load_zusatzmodule_allowlist(bad_file) is None


def test_load_zusatzmodule_allowlist_rejects_non_object_json(tmp_path):
    not_an_object = tmp_path / "list.json"
    not_an_object.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_zusatzmodule_allowlist(not_an_object) is None


def test_load_zusatzmodule_allowlist_normalizes_and_deduplicates(tmp_path):
    custom = tmp_path / "custom.json"
    custom.write_text(
        json.dumps(
            {
                "erlaubte_modul_nr": [" ZZ1 ", "ZZ1", "ZZ2", 123],
                "erlaubte_kurs_nr": ["ZZ1-1"],
            }
        ),
        encoding="utf-8",
    )
    allowlist = load_zusatzmodule_allowlist(custom)
    assert allowlist["modul_nr"] == {"ZZ1", "ZZ2", "123"}
    assert allowlist["kurs_nr"] == {"ZZ1-1"}


def test_load_zusatzmodule_allowlist_missing_keys_yield_empty_sets(tmp_path):
    custom = tmp_path / "partial.json"
    custom.write_text(json.dumps({"erlaubte_modul_nr": ["ZZ1"]}), encoding="utf-8")
    allowlist = load_zusatzmodule_allowlist(custom)
    assert allowlist["modul_nr"] == {"ZZ1"}
    assert allowlist["kurs_nr"] == set()


# --- _filter_zusatzmodule_by_allowlist() --------------------------------------
# Unlike the end-to-end tests further below, these call the filter directly
# with ALREADY-normalized column names (modul_nr/kurs_nr, lowercase) - that's
# the shape it actually receives its input in from load_schedule_from_
# dataframe(), which only calls it after _normalize_columns() has already
# run (see the pipeline overview in this module's docstring).

def test_filter_keeps_only_rows_matching_modul_nr():
    df = pd.DataFrame({"modul_nr": ["ZZ1", "ZZ2"]})
    filtered, excluded = _filter_zusatzmodule_by_allowlist(df, {"modul_nr": {"ZZ1"}, "kurs_nr": set()})
    assert len(filtered) == 1
    assert filtered.iloc[0]["modul_nr"] == "ZZ1"
    assert excluded == 1


def test_filter_keeps_rows_matching_kurs_nr_even_without_modul_nr_match():
    df = pd.DataFrame(
        {
            "modul_nr": ["ZZ-OTHER", "ZZ-OTHER"],
            "kurs_nr": ["ZZ1-1", "ZZ9-9"],
        }
    )
    filtered, excluded = _filter_zusatzmodule_by_allowlist(
        df, {"modul_nr": {"ZZ1"}, "kurs_nr": {"ZZ1-1"}}
    )
    assert len(filtered) == 1
    assert filtered.iloc[0]["kurs_nr"] == "ZZ1-1"
    assert excluded == 1


def test_filter_is_noop_when_allowlist_is_empty():
    df = pd.DataFrame({"modul_nr": ["ZZ1", "ZZ2"]})
    filtered, excluded = _filter_zusatzmodule_by_allowlist(df, {"modul_nr": set(), "kurs_nr": set()})
    assert len(filtered) == 2
    assert excluded == 0


def test_filter_is_noop_when_neither_column_present():
    df = pd.DataFrame({"wochentag": ["Montag"], "startzeit": ["08:00"]})
    filtered, excluded = _filter_zusatzmodule_by_allowlist(df, {"modul_nr": {"ZZ1"}, "kurs_nr": set()})
    assert len(filtered) == 1
    assert excluded == 0


# --- End-to-end via load_schedule_from_dataframe() ----------------------------

def test_disabled_by_default_is_a_pure_noop(monkeypatch):
    """
    The single most important test in this file: with the shipped default
    (ZUSATZMODULE_ALLOWLIST_ENABLED = False), a restrictive allowlist that
    would otherwise exclude every row must have NO effect at all - proving
    today's behaviour is unchanged by this feature's mere presence in the
    code.
    """
    monkeypatch.setattr(data_loader, "ZUSATZMODULE_ALLOWLIST_ENABLED", False)
    monkeypatch.setattr(
        data_loader,
        "load_zusatzmodule_allowlist",
        lambda *a, **kw: {"modul_nr": set(), "kurs_nr": set()},
    )
    df = _minimal_zusatzmodule_df([{"modul_nr": "ZZ1"}, {"modul_nr": "ZZ2"}])
    modules = load_schedule_from_dataframe(df, ist_zusatzmodul=True)
    assert len(modules) == 2


def test_enabled_filters_out_disallowed_modules(monkeypatch):
    """
    Documents/exercises the future "flip it on" behaviour: once enabled,
    only allowlisted Modul-Nr values survive the Zusatzmodule import.
    """
    monkeypatch.setattr(data_loader, "ZUSATZMODULE_ALLOWLIST_ENABLED", True)
    monkeypatch.setattr(
        data_loader,
        "load_zusatzmodule_allowlist",
        lambda *a, **kw: {"modul_nr": {"ZZ1"}, "kurs_nr": set()},
    )
    df = _minimal_zusatzmodule_df([{"modul_nr": "ZZ1"}, {"modul_nr": "ZZ2"}])
    modules = load_schedule_from_dataframe(df, ist_zusatzmodul=True)
    assert len(modules) == 1
    assert modules[0].modul_nr == "ZZ1"


def test_enabled_never_filters_the_main_upload(monkeypatch):
    """
    The allowlist is scoped to Zusatzmodule uploads only (see the concept:
    it's the Bachelor-level supplementary catalog that has far too many
    choosable-but-not-allowed courses, not the main Master schedule). Even
    with the feature enabled and a restrictive list, ist_zusatzmodul=False
    must never be filtered.
    """
    monkeypatch.setattr(data_loader, "ZUSATZMODULE_ALLOWLIST_ENABLED", True)
    monkeypatch.setattr(
        data_loader,
        "load_zusatzmodule_allowlist",
        lambda *a, **kw: {"modul_nr": {"ZZ1"}, "kurs_nr": set()},
    )
    df = _minimal_zusatzmodule_df([{"modul_nr": "ZZ1"}, {"modul_nr": "ZZ2"}])
    modules = load_schedule_from_dataframe(df, ist_zusatzmodul=False)
    assert len(modules) == 2


def test_enabled_with_no_allowlist_file_falls_back_to_unfiltered(monkeypatch, tmp_path):
    # If the feature is switched on but the settings file is missing/broken
    # (e.g. mid-deployment), the import must still succeed unfiltered rather
    # than raising or silently dropping every row.
    monkeypatch.setattr(data_loader, "ZUSATZMODULE_ALLOWLIST_ENABLED", True)
    monkeypatch.setattr(data_loader, "ZUSATZMODULE_ALLOWLIST_PATH", tmp_path / "missing.json")
    df = _minimal_zusatzmodule_df([{"modul_nr": "ZZ1"}, {"modul_nr": "ZZ2"}])
    modules = load_schedule_from_dataframe(df, ist_zusatzmodul=True)
    assert len(modules) == 2
