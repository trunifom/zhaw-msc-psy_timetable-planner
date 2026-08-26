"""
Tests for src/models.py - the Pydantic domain model (ZHAWModule) that
every row of an uploaded timetable is converted into.

These are deliberately narrow, fast unit tests that construct a ZHAWModule
directly (no file upload, no data_loader involved) so each test isolates
exactly one validator/behaviour. Integration-style "does a whole real
export parse correctly" coverage lives in tests/test_data_loader.py.
"""

import pytest
from datetime import date, time
from pydantic import ValidationError

from models import ZHAWModule, Weekday


def make_module(**overrides):
    """Build a minimal valid ZHAWModule, overriding only the fields under test."""
    defaults = dict(
        modulname="Testmodul",
        wochentag="montag",
        startzeit="08:15",
        endzeit="10:00",
        ects=3,
    )
    defaults.update(overrides)
    return ZHAWModule(**defaults)


# --- Weekday parsing -------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("montag", Weekday.MONDAY),
        ("Montag", Weekday.MONDAY),
        ("  MONTAG  ", Weekday.MONDAY),
        ("mo", Weekday.MONDAY),
        ("monday", Weekday.MONDAY),
        ("di", Weekday.TUESDAY),
        ("tue", Weekday.TUESDAY),
        ("mi", Weekday.WEDNESDAY),
        ("wed", Weekday.WEDNESDAY),
        ("do", Weekday.THURSDAY),
        ("thu", Weekday.THURSDAY),
        ("fr", Weekday.FRIDAY),
        ("fri", Weekday.FRIDAY),
        ("sa", Weekday.SATURDAY),
        ("so", Weekday.SUNDAY),
        ("sun", Weekday.SUNDAY),
    ],
)
def test_weekday_aliases_normalize_correctly(raw, expected):
    assert make_module(wochentag=raw).wochentag == expected


def test_unknown_weekday_raises():
    with pytest.raises(ValidationError):
        make_module(wochentag="irgendwas")


# --- Time parsing ------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("08:15", time(8, 15)),
        ("8:15", time(8, 15)),
        ("08:15:00", time(8, 15)),
        ("08.15", time(8, 15)),  # common typo/alt-format: dot instead of colon
    ],
)
def test_time_string_formats_are_parsed(raw, expected):
    assert make_module(startzeit=raw).startzeit == expected


def test_invalid_time_string_raises():
    with pytest.raises(ValidationError):
        make_module(startzeit="not-a-time")


def test_end_time_before_start_time_raises():
    with pytest.raises(ValidationError):
        make_module(startzeit="10:00", endzeit="08:00")


def test_end_time_equal_to_start_time_raises():
    # A zero-length session isn't schedulable; the model requires end > start.
    with pytest.raises(ValidationError):
        make_module(startzeit="10:00", endzeit="10:00")


# --- Date parsing --------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("16.09.2026", date(2026, 9, 16)),
        ("2026-09-16", date(2026, 9, 16)),
        ("16/09/2026", date(2026, 9, 16)),
        ("16.09.26", date(2026, 9, 16)),
        ("2026-09-16 00:00:00", date(2026, 9, 16)),
        (date(2026, 9, 16), date(2026, 9, 16)),
    ],
)
def test_date_formats_are_parsed(raw, expected):
    assert make_module(datum=raw).datum == expected


@pytest.mark.parametrize("raw", [None, "", "n/a", "N/A", "none", "NaN", "nat"])
def test_missing_date_placeholders_become_none(raw):
    assert make_module(datum=raw).datum is None


def test_nan_float_date_becomes_none():
    # Regression: pandas leaves a float NaN (not a clean None) in a column
    # after a failed date parse in some paths - the validator must treat
    # that the same as a missing date, not attempt to interpret it as a
    # date and blow up.
    assert make_module(datum=float("nan")).datum is None


def test_pandas_nat_date_becomes_none():
    # Regression: pandas.NaT satisfies isinstance(v, datetime) but calling
    # .date() on it returns NaT again (not a real date), which used to
    # raise a confusing TypeError deep inside Pydantic instead of cleanly
    # producing datum=None. See models.py's parse_date_value docstring.
    pd = pytest.importorskip("pandas")
    assert make_module(datum=pd.NaT).datum is None


def test_unparseable_date_string_raises():
    with pytest.raises(ValidationError):
        make_module(datum="not-a-date-at-all")


# --- ECTS bounds -----------------------------------------------------------

@pytest.mark.parametrize("value", [0, 3, 30, 60])
def test_valid_ects_values_are_accepted(value):
    assert make_module(ects=value).ects == value


@pytest.mark.parametrize("value", [-1, 61])
def test_out_of_range_ects_raises(value):
    with pytest.raises(ValidationError):
        make_module(ects=value)


# --- Optional identifiers ----------------------------------------------------

@pytest.mark.parametrize("raw", ["N/A", "n/a", "", "none", "NaN"])
def test_placeholder_identifiers_become_none(raw):
    m = make_module(modul_nr=raw, kurs_nr=raw)
    assert m.modul_nr is None
    assert m.kurs_nr is None


def test_real_identifiers_are_kept():
    m = make_module(modul_nr="ZF6", kurs_nr="ZF6-1")
    assert m.modul_nr == "ZF6"
    assert m.kurs_nr == "ZF6-1"


# --- Exam boolean parsing --------------------------------------------------

@pytest.mark.parametrize("raw", ["ja", "Ja", "yes", "true", "1", "pruefung", "prüfung", "exam", True])
def test_truthy_exam_flags_parse_as_true(raw):
    assert make_module(ist_pruefung=raw).ist_pruefung is True


@pytest.mark.parametrize("raw", ["nein", "no", "false", "0", "", None, False])
def test_falsy_exam_flags_parse_as_false(raw):
    assert make_module(ist_pruefung=raw).ist_pruefung is False


def test_exam_is_auto_inferred_from_module_title():
    # Even without an explicit ist_pruefung flag, a title containing
    # "Pruefung"/"Prüfung" (a common ZHAW export convention, e.g.
    # "Kursname / PRUEFUNG") should still be recognized as an exam.
    m = make_module(modulname="Entscheidungsverhalten / PRUEFUNG")
    assert m.ist_pruefung is True


def test_exam_is_auto_inferred_from_pruefung_flag_column():
    m = make_module(pruefung_flag="Prüfung")
    assert m.ist_pruefung is True


# --- Attendance percentage parsing -----------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("80", 80.0),
        ("80%", 80.0),
        ("0.8", 80.0),  # fraction <= 1 is scaled up to a percentage
        ("80,5", 80.5),  # German-style comma decimal separator
        (80, 80.0),
    ],
)
def test_attendance_percentage_formats_are_parsed(raw, expected):
    assert make_module(anwesenheitspflicht_prozent=raw).anwesenheitspflicht_prozent == expected


@pytest.mark.parametrize("raw", [None, "", "n/a"])
def test_missing_attendance_percentage_becomes_none(raw):
    assert make_module(anwesenheitspflicht_prozent=raw).anwesenheitspflicht_prozent is None


# --- Helper methods / misc --------------------------------------------------

def test_duration_minutes_computes_correctly():
    m = make_module(startzeit="08:15", endzeit="10:00")
    assert m.duration_minutes == 105


def test_to_ui_dict_contains_expected_labeled_keys():
    m = make_module(datum="16.09.2026", ects=3)
    ui = m.to_ui_dict()
    assert ui["Modul"] == "Testmodul"
    assert ui["Tag"] == "Montag"
    assert ui["Datum"] == "2026-09-16"
    assert ui["Zeit"] == "08:15 - 10:00"
    assert ui["ECTS"] == 3
    assert ui["Pruefung"] == "Nein"


def test_extra_unknown_columns_are_silently_ignored():
    # extra="ignore" in model_config: a real export often carries columns
    # we don't model (e.g. "SG"/Studiengang) - they must not break parsing.
    m = make_module(sg="MSc", some_other_column="whatever")
    assert m.modulname == "Testmodul"
    assert not hasattr(m, "sg")
