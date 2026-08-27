"""
Tests for src/export.py - the Excel (XLSX) and calendar (ICS) export
layer. These use small, hand-built ZHAWModule instances to isolate
individual behaviours; the full pipeline (real file -> loader -> export)
is covered by the fixture-based tests in tests/test_data_loader.py.
"""

import io
from datetime import date, datetime

import pandas as pd
import pytest

from models import ZHAWModule
from export import (
    _escape_ics_text,
    _fold_ics_line,
    _zurich_to_utc,
    _uid_base,
    _event_summary,
    _event_description,
    generate_excel_download,
    generate_ics_download,
    prepare_timetable_for_export,
)


def make_module(**overrides):
    defaults = dict(
        modulname="Testmodul",
        wochentag="montag",
        startzeit="08:15",
        endzeit="10:00",
        ects=3,
    )
    defaults.update(overrides)
    return ZHAWModule(**defaults)


# --- ICS text escaping / line folding (RFC5545) -----------------------------

def test_escape_ics_text_escapes_special_characters():
    raw = "A, B; C\\D\nE"
    escaped = _escape_ics_text(raw)
    assert escaped == "A\\, B\\; C\\\\D\\nE"


def test_fold_ics_line_leaves_short_lines_untouched():
    line = "SUMMARY:Kurz"
    assert _fold_ics_line(line) == line


def test_fold_ics_line_wraps_long_lines_under_75_octets():
    line = "DESCRIPTION:" + ("x" * 200)
    folded = _fold_ics_line(line)
    physical_lines = folded.split("\r\n")
    assert len(physical_lines) > 1
    for i, physical in enumerate(physical_lines):
        assert len(physical.encode("utf-8")) <= 75
        if i > 0:
            assert physical.startswith(" ")  # continuation-line marker per RFC5545


def test_fold_ics_line_does_not_split_multibyte_utf8_sequences():
    # A run of umlauts/emoji means naive byte-offset slicing could land
    # inside a multi-byte UTF-8 sequence and corrupt it - decoding each
    # folded segment must not raise, and re-joining must reproduce the text.
    line = "DESCRIPTION:" + ("ä⚠️❓" * 40)
    folded = _fold_ics_line(line)
    physical_lines = folded.split("\r\n")
    rejoined = "".join(p[1:] if i > 0 else p for i, p in enumerate(physical_lines))
    assert rejoined == line
    for physical in physical_lines:
        physical.encode("utf-8")  # would raise if a char got split


# --- Europe/Zurich -> UTC conversion (DST-aware, no external tz dependency) --

def test_zurich_to_utc_in_summer_is_utc_plus_2():
    # 15 September is well within CEST (last Sunday of March - last Sunday
    # of October).
    local = datetime(2026, 9, 15, 8, 15)
    assert _zurich_to_utc(local) == datetime(2026, 9, 15, 6, 15)


def test_zurich_to_utc_in_winter_is_utc_plus_1():
    local = datetime(2026, 1, 15, 8, 15)
    assert _zurich_to_utc(local) == datetime(2026, 1, 15, 7, 15)


def test_zurich_to_utc_dst_start_boundary_2026():
    # DST 2026 starts last Sunday of March = 2026-03-29, 02:00 local.
    # Just before: still CET (+1). At/after: CEST (+2).
    before = datetime(2026, 3, 29, 1, 59)
    after = datetime(2026, 3, 29, 2, 0)
    assert _zurich_to_utc(before) == datetime(2026, 3, 29, 0, 59)
    assert _zurich_to_utc(after) == datetime(2026, 3, 29, 0, 0)


def test_zurich_to_utc_dst_end_boundary_2026():
    # DST 2026 ends last Sunday of October = 2026-10-25, 03:00 local.
    # (The 02:00-03:00 hour is inherently ambiguous in real Europe/Zurich
    # time - it occurs twice - so this checks clearly-before/clearly-after
    # values rather than the ambiguous instant itself.)
    before = datetime(2026, 10, 25, 1, 0)  # still CEST (+2)
    after = datetime(2026, 10, 25, 4, 0)  # already CET (+1)
    assert _zurich_to_utc(before) == datetime(2026, 10, 24, 23, 0)
    assert _zurich_to_utc(after) == datetime(2026, 10, 25, 3, 0)


# --- UID generation ----------------------------------------------------------

def test_uid_base_prefers_kurs_nr_over_modul_nr_and_name():
    m = make_module(modul_nr="ZF6", kurs_nr="ZF6-1", modulname="Something")
    assert _uid_base(m) == "zf6-1"


def test_uid_base_slugifies_special_characters():
    m = make_module(modul_nr=None, kurs_nr=None, modulname="Modul: äöü / Test!")
    slug = _uid_base(m)
    assert slug.isascii()
    assert " " not in slug and ":" not in slug and "/" not in slug


# --- Event title (SUMMARY) building ------------------------------------------

def test_summary_plain_module_has_no_marker():
    m = make_module(modulname="Forschungstheorien")
    assert _event_summary(m, has_date=True) == "Forschungstheorien"


def test_summary_exam_gets_warning_marker():
    m = make_module(modulname="Theorie", ist_pruefung=True)
    summary = _event_summary(m, has_date=True)
    assert summary.startswith("⚠️")
    assert "Theorie" in summary


def test_summary_exam_suffix_in_source_name_is_not_duplicated():
    # Source titles often already end in "/ PRUEFUNG" (ZHAW convention);
    # the generated marker must not repeat that suffix a second time.
    m = make_module(modulname="Theorie / PRUEFUNG", ist_pruefung=True)
    summary = _event_summary(m, has_date=True)
    assert not summary.upper().rstrip().endswith("PRUEFUNG")


def test_summary_missing_date_gets_question_mark_marker():
    m = make_module(modulname="Kurs")
    summary = _event_summary(m, has_date=False)
    assert summary.startswith("❓")


def test_summary_exam_without_date_shows_both_conditions():
    m = make_module(modulname="Kurs", ist_pruefung=True)
    summary = _event_summary(m, has_date=False)
    assert "⚠️" in summary
    assert "unbekannt" in summary.lower()


# --- Excel export -------------------------------------------------------------

def test_prepare_timetable_for_export_from_modules():
    m = make_module(modulname="Kurs A", datum=date(2026, 9, 16), modul_nr="X1")
    df = prepare_timetable_for_export([m])
    assert list(df["Modul"]) == ["Kurs A"]
    assert list(df["Datum"]) == ["2026-09-16"]
    assert list(df["Modul-Nr"]) == ["X1"]


# --- Zusatzmodule / Passerelle export tagging --------------------------------
# See docs/planung/KONZEPT-passerelle-zusatzmodule.md section 4.5.

def test_prepare_timetable_for_export_quelle_column_marks_zusatzmodul():
    main = make_module(modulname="MSc-Modul", ist_zusatzmodul=False)
    zusatz = make_module(modulname="BSc-Zusatzmodul", ist_zusatzmodul=True)
    df = prepare_timetable_for_export([main, zusatz])
    assert list(df["Quelle"]) == ["Hauptliste", "Zusatzmodul"]


def test_event_description_flags_zusatzmodul():
    m = make_module(modulname="Kurs", datum=date(2026, 9, 16), ist_zusatzmodul=True)
    description = _event_description(m, has_date=True)
    assert "Zusatzmodul (Passerelle)" in description


def test_event_description_omits_zusatzmodul_marker_for_main_list_rows():
    m = make_module(modulname="Kurs", datum=date(2026, 9, 16), ist_zusatzmodul=False)
    description = _event_description(m, has_date=True)
    assert "Zusatzmodul" not in description


def test_prepare_timetable_for_export_from_plain_dicts():
    df = prepare_timetable_for_export([{"Modul": "Kurs A", "ECTS": 3}])
    assert list(df["Modul"]) == ["Kurs A"]


def test_prepare_timetable_for_export_empty_input_returns_empty_dataframe():
    df = prepare_timetable_for_export([])
    assert df.empty


def test_generate_excel_download_produces_readable_xlsx():
    df = prepare_timetable_for_export([make_module(modulname="Kurs A")])
    xlsx_bytes = generate_excel_download(df)
    assert xlsx_bytes[:2] == b"PK"  # xlsx files are zip archives
    roundtrip = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name="Stundenplan")
    assert list(roundtrip["Modul"]) == ["Kurs A"]


# --- ICS export: structural edge cases ---------------------------------------

def test_generate_ics_download_with_no_modules_is_still_a_valid_empty_calendar():
    ics = generate_ics_download([], calendar_name="Leer")
    text = ics.decode("utf-8")
    assert text.startswith("BEGIN:VCALENDAR")
    assert text.rstrip().endswith("END:VCALENDAR")
    assert "BEGIN:VEVENT" not in text


def test_generate_ics_download_skips_rows_with_no_time_at_all():
    # startzeit/endzeit are required fields on ZHAWModule, so this can't
    # happen via the normal loader path - this only guards the function's
    # own defensive `continue` for a malformed/duck-typed input object.
    class FakeModuleWithoutTimes:
        modulname = "Ghost"
        startzeit = None
        endzeit = None
        datum = None
        ist_pruefung = False

    ics = generate_ics_download([FakeModuleWithoutTimes()], calendar_name="Test")
    assert b"BEGIN:VEVENT" not in ics


def test_dated_event_is_marked_opaque_and_placeholder_is_transparent():
    dated = make_module(modulname="Real", datum=date(2026, 9, 16))
    undated = make_module(modulname="Unbekannt")
    ics = generate_ics_download(
        [dated, undated], calendar_name="Test", fallback_date=date(2026, 9, 1)
    ).decode("utf-8")
    events = ics.split("BEGIN:VEVENT")[1:]
    real_event = next(e for e in events if "Real" in e)
    placeholder_event = next(e for e in events if "Unbekannt" in e)
    assert "TRANSP:OPAQUE" in real_event
    assert "TRANSP:TRANSPARENT" in placeholder_event
    assert "VALUE=DATE" not in real_event
    assert "VALUE=DATE" in placeholder_event
