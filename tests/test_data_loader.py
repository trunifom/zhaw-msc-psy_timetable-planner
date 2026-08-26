from pathlib import Path

import pandas as pd
import pytest

from data_loader import DataLoaderError, MissingColumnError, load_schedule_from_dataframe
from export import generate_ics_download

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "vorlesungsverzeichnis_fiktiv.xlsx"
EDGE_CASE_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "edge_cases_fiktiv.csv"


@pytest.fixture(scope="module")
def fixture_modules():
    raw_df = pd.read_excel(FIXTURE_PATH, header=None, sheet_name="Vorlesungsverzeichnis")
    return load_schedule_from_dataframe(raw_df)


def test_fixture_file_exists():
    assert FIXTURE_PATH.exists()


def test_banner_rows_are_skipped_and_all_rows_parsed(fixture_modules):
    # The fixture has two metadata rows above the real header, mirroring the
    # real ZHAW export. If header detection failed, either far fewer rows
    # would parse, or none at all.
    assert len(fixture_modules) == 62


def test_every_row_keeps_its_date(fixture_modules):
    # Each row in the source data represents one dated session; a row
    # silently losing its date used to make the whole row disappear
    # (a pandas.NaT edge case in the Pydantic validator).
    missing = [m.modulname for m in fixture_modules if m.datum is None]
    assert missing == []


def test_exam_rows_are_flagged(fixture_modules):
    exams = [m for m in fixture_modules if m.ist_pruefung]
    assert len(exams) == 3
    assert all("PRUEFUNG" in m.modulname.upper() for m in exams)


def test_irregular_weekly_schedule_is_preserved(fixture_modules):
    # ZKP10-2 meets at a different weekday/time almost every week - this is
    # the core real-world pattern the export must not collapse into a
    # single recurring weekly slot.
    zkp10_2 = [m for m in fixture_modules if m.kurs_nr == "ZKP10-2"]
    assert len(zkp10_2) == 8
    distinct_slots = {(m.wochentag, m.startzeit, m.endzeit) for m in zkp10_2}
    assert len(distinct_slots) > 1


def test_multi_lecturer_and_placeholder_names_are_kept(fixture_modules):
    names = {m.dozierende for m in fixture_modules}
    assert any("&" in name for name in names)
    assert "N.N." in names


def test_ics_export_includes_every_module(fixture_modules):
    # Regression test: the ICS export used to silently drop any module
    # without a datum. Every currently selected module must produce
    # exactly one VEVENT.
    ics_text = generate_ics_download(fixture_modules, calendar_name="Test").decode("utf-8")
    assert ics_text.count("BEGIN:VEVENT") == len(fixture_modules)


def test_ics_export_marks_exams_with_reminder(fixture_modules):
    ics_text = generate_ics_download(fixture_modules, calendar_name="Test").decode("utf-8")
    exam_count = sum(1 for m in fixture_modules if m.ist_pruefung)
    assert ics_text.count("CATEGORIES:PRUEFUNG") == exam_count
    # Exams get two reminders (1 day + 2 hours before); regular sessions get none.
    assert ics_text.count("BEGIN:VALARM") == exam_count * 2


def test_ics_export_never_exceeds_line_length(fixture_modules):
    ics_text = generate_ics_download(fixture_modules, calendar_name="Test")
    for line in ics_text.split(b"\r\n"):
        assert len(line) <= 75


def test_ics_categories_tag_course_code_for_color_coding(fixture_modules):
    ics_text = generate_ics_download(fixture_modules, calendar_name="Test").decode("utf-8")
    assert "CATEGORIES:LEHRVERANSTALTUNG,ZF6-1" in ics_text


def test_ics_uid_is_stable_across_repeated_exports(fixture_modules):
    # Re-exporting the same selection should update existing calendar
    # entries on re-import (same UID), not create duplicates.
    first = generate_ics_download(fixture_modules, calendar_name="Test").decode("utf-8")
    second = generate_ics_download(fixture_modules, calendar_name="Test").decode("utf-8")
    uids_first = [line for line in first.split("\r\n") if line.startswith("UID:")]
    uids_second = [line for line in second.split("\r\n") if line.startswith("UID:")]
    assert uids_first == uids_second
    assert len(uids_first) == len(set(uids_first))  # all unique


def test_ics_exam_title_has_no_duplicate_pruefung_suffix(fixture_modules):
    # Source names often already end in "/ PRUEFUNG" (ZHAW export
    # convention); the title marker shouldn't repeat that.
    ics_text = generate_ics_download(fixture_modules, calendar_name="Test").decode("utf-8")
    summary_lines = [l for l in ics_text.split("\r\n") if l.startswith("SUMMARY:") and "Pruefung" in l]
    assert summary_lines
    assert all(not l.rstrip().upper().endswith("PRUEFUNG") for l in summary_lines)


def test_ics_events_are_sorted_chronologically(fixture_modules):
    ics_text = generate_ics_download(fixture_modules, calendar_name="Test").decode("utf-8")
    starts = [line[len("DTSTART:"):] for line in ics_text.split("\r\n") if line.startswith("DTSTART:")]
    assert starts == sorted(starts)


def test_row_without_any_date_is_kept_not_dropped():
    # Regression test: a datum value that fails to parse (pandas.NaT) used
    # to raise an uncaught TypeError deep in Pydantic, silently discarding
    # the entire row instead of just the date.
    df = pd.DataFrame(
        {
            "Wochentag": ["Montag"],
            "Startzeit": ["08:15"],
            "Endzeit": ["10:00"],
            "Modulname": ["Kurs ohne Datum"],
            "ECTS": [1],
            "Datum": ["n/a"],
        }
    )
    modules = load_schedule_from_dataframe(df)
    assert len(modules) == 1
    assert modules[0].datum is None


# --- Edge-case fixture: alternate (English-style) column headers -----------
# tests/fixtures/edge_cases_fiktiv.csv uses a different set of header
# spellings than the primary fixture (which already uses the real ZHAW
# German headers) specifically to exercise the COLUMN_ALIASES mapping
# breadth, plus mixed date formats and a row with a genuinely blank date
# in a realistic multi-row CSV (not just a synthetic in-memory frame).

@pytest.fixture(scope="module")
def edge_case_modules():
    df = pd.read_csv(EDGE_CASE_FIXTURE_PATH)
    return load_schedule_from_dataframe(df)


def test_edge_case_fixture_file_exists():
    assert EDGE_CASE_FIXTURE_PATH.exists()


def test_alternate_column_headers_are_aliased_correctly(edge_case_modules):
    # "Weekday"/"Start"/"End"/"Course"/"Credits"/"Date"/"Room"/"Lecturer"/"Art"
    # must all map onto the canonical schema despite not being the German
    # column names used elsewhere in this project.
    assert len(edge_case_modules) == 3
    names = {m.modulname for m in edge_case_modules}
    assert "Testkurs Alpha" in names


def test_mixed_date_formats_in_the_same_file_both_parse(edge_case_modules):
    by_name = {m.modulname: m for m in edge_case_modules}
    assert by_name["Testkurs Alpha"].datum.isoformat() == "2026-09-16"  # dd.mm.yyyy
    assert by_name["Testkurs Beta"].datum.isoformat() == "2026-09-17"  # ISO


def test_english_weekday_alias_is_recognized(edge_case_modules):
    beta = next(m for m in edge_case_modules if m.modulname == "Testkurs Beta")
    assert beta.wochentag.value == "dienstag"  # "tue" -> Tuesday -> dienstag


def test_blank_date_cell_in_a_real_csv_row_is_kept_without_a_date(edge_case_modules):
    gamma = next(m for m in edge_case_modules if "Gamma" in m.modulname)
    assert gamma.datum is None
    assert gamma.ist_pruefung is True  # inferred from "/ Pruefung" in the title


# --- Structural error paths --------------------------------------------------

def test_missing_required_columns_raises_missing_column_error():
    df = pd.DataFrame({"Irgendwas": ["x"], "NochEtwas": ["y"]})
    with pytest.raises(MissingColumnError):
        load_schedule_from_dataframe(df)


def test_all_rows_invalid_raises_data_loader_error():
    # Every row fails validation (garbage time strings) -> the loader must
    # not silently return an empty list, since that looks identical to "an
    # empty file was uploaded" from the caller's point of view.
    df = pd.DataFrame(
        {
            "Wochentag": ["Montag"],
            "Startzeit": ["nicht-eine-zeit"],
            "Endzeit": ["auch-nicht"],
            "Modulname": ["Kaputte Zeile"],
            "ECTS": [1],
        }
    )
    with pytest.raises(DataLoaderError):
        load_schedule_from_dataframe(df)


def test_empty_dataframe_returns_empty_list_without_raising():
    assert load_schedule_from_dataframe(pd.DataFrame()) == []
