"""
Tests for src/scheduler.py's `find_time_conflicts` - the active
conflict-detection logic used by the "Konfliktanalyse" tab and the guided
planning module-status check. (The rest of scheduler.py is unused legacy
prototype code - see the module docstring in src/scheduler.py - and is not
covered here.)
"""

from datetime import date

from models import ZHAWModule
from scheduler import find_time_conflicts


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


def test_empty_input_returns_no_conflicts():
    assert find_time_conflicts([]) == []


def test_single_module_has_no_conflicts():
    assert find_time_conflicts([make_module()]) == []


def test_overlapping_times_same_weekday_conflict_when_undated():
    a = make_module(modulname="Modul A", startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="Modul B", startzeit="09:00", endzeit="11:00")
    conflicts = find_time_conflicts([a, b])
    assert len(conflicts) == 1
    assert {conflicts[0][0].modulname, conflicts[0][1].modulname} == {"Modul A", "Modul B"}


def test_non_overlapping_times_same_weekday_no_conflict():
    a = make_module(modulname="Modul A", startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="Modul B", startzeit="10:30", endzeit="12:00")
    assert find_time_conflicts([a, b]) == []


def test_touching_intervals_are_not_a_conflict():
    # [08:00,10:00) and [10:00,12:00) share only the boundary instant -
    # a half-open interval overlap test must not flag this as a clash.
    a = make_module(modulname="Modul A", startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="Modul B", startzeit="10:00", endzeit="12:00")
    assert find_time_conflicts([a, b]) == []


def test_different_weekdays_never_conflict_even_if_times_overlap():
    a = make_module(modulname="Modul A", wochentag="montag", startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="Modul B", wochentag="dienstag", startzeit="08:00", endzeit="10:00")
    assert find_time_conflicts([a, b]) == []


def test_same_weekday_different_dates_do_not_conflict():
    # Both are Mondays, but on different calendar weeks - once a real date
    # is known, "same weekday" is no longer a good enough proxy for
    # "actually the same time slot".
    a = make_module(modulname="Modul A", datum=date(2026, 9, 14), startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="Modul B", datum=date(2026, 9, 21), startzeit="08:00", endzeit="10:00")
    assert find_time_conflicts([a, b]) == []


def test_conflict_detected_between_main_and_zusatzmodul():
    # See docs/planung/KONZEPT-passerelle-zusatzmodule.md section 4.1: once
    # a Zusatzmodul (Passerelle student's supplementary module, tagged via
    # ist_zusatzmodul=True) is merged into the same flat module list as the
    # main schedule, find_time_conflicts() must catch a genuine overlap
    # between the two exactly like it would between two main-list modules -
    # no separate code path exists (or should exist) for this.
    main_module = make_module(
        modulname="MSc Pflichtmodul", ist_zusatzmodul=False, startzeit="08:00", endzeit="10:00"
    )
    zusatzmodul = make_module(
        modulname="BSc Zusatzmodul", ist_zusatzmodul=True, startzeit="09:00", endzeit="11:00"
    )
    conflicts = find_time_conflicts([main_module, zusatzmodul])
    assert len(conflicts) == 1
    assert {conflicts[0][0].ist_zusatzmodul, conflicts[0][1].ist_zusatzmodul} == {True, False}


def test_same_exact_date_overlap_conflicts():
    a = make_module(modulname="Modul A", datum=date(2026, 9, 14), startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="Modul B", datum=date(2026, 9, 14), startzeit="09:00", endzeit="11:00")
    assert len(find_time_conflicts([a, b])) == 1


def test_dated_vs_undated_falls_back_to_weekday_comparison():
    # One row has a date, the other doesn't - _same_occurrence() can only
    # compare on the info both sides actually have, so it falls back to
    # weekday matching rather than refusing to compare at all.
    a = make_module(modulname="Modul A", wochentag="montag", datum=None, startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="Modul B", wochentag="montag", startzeit="09:00", endzeit="11:00")
    assert len(find_time_conflicts([a, b])) == 1


def test_exact_duplicate_rows_are_not_reported_as_a_conflict():
    # Same module, same everything (identical semantic signature) - this
    # is duplicate data (e.g. the same session listed under two study
    # programs), not two different things clashing with each other.
    a = make_module(modulname="Modul A", modul_nr="X1", kurs_nr="X1-1", raum="R1")
    b = make_module(modulname="Modul A", modul_nr="X1", kurs_nr="X1-1", raum="R1")
    assert find_time_conflicts([a, b]) == []


def test_each_conflicting_pair_reported_only_once():
    a = make_module(modulname="Modul A", startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="Modul B", startzeit="09:00", endzeit="11:00")
    c = make_module(modulname="Modul C", startzeit="09:30", endzeit="10:30")
    conflicts = find_time_conflicts([a, b, c])
    # A-B, A-C, B-C all overlap -> exactly 3 pairs, none duplicated.
    assert len(conflicts) == 3
    pair_names = {frozenset((x.modulname, y.modulname)) for x, y in conflicts}
    assert pair_names == {frozenset(("Modul A", "Modul B")), frozenset(("Modul A", "Modul C")), frozenset(("Modul B", "Modul C"))}
