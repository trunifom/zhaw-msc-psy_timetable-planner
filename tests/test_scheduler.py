"""
Tests for src/scheduler.py's `find_time_conflicts` and
`find_critical_first_session_conflicts` - the active conflict-detection
logic used by the "Konfliktanalyse" tab and the guided planning
module-status check. (The rest of scheduler.py is unused legacy prototype
code - see the module docstring in src/scheduler.py - and is not covered
here.)
"""

from datetime import date

from models import ZHAWModule
from scheduler import find_time_conflicts, find_critical_first_session_conflicts


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


# ==========================================
# find_critical_first_session_conflicts
# ==========================================
# Passerelle-specific narrowing of find_time_conflicts(): only conflicts
# where >=1 side is a Zusatzmodul (ist_zusatzmodul=True) AND >=1 side falls
# within its own course's first 2 dated, non-exam sessions (see that
# function's docstring in src/scheduler.py for the full rationale - missed
# assessment/exam/group-assignment info in an early session is hard to
# recover later). `family_key` groups rows into "one course" - tests use a
# simple kurs_nr-based key, mirroring app.py's real
# `_module_course_family_key` closely enough for this logic (which only
# needs *a* stable per-course grouping, not app.py's title-parsing rules).


def _family_key(module: ZHAWModule) -> str:
    return module.kurs_nr or module.modulname


def test_first_session_conflict_between_zusatzmodul_and_main_is_flagged():
    zusatz_first = make_module(
        modulname="BSc Kurs", kurs_nr="B1", ist_zusatzmodul=True,
        datum=date(2026, 9, 14), startzeit="08:00", endzeit="10:00",
    )
    zusatz_second = make_module(
        modulname="BSc Kurs", kurs_nr="B1", ist_zusatzmodul=True,
        datum=date(2026, 9, 21), startzeit="08:00", endzeit="10:00",
    )
    main_module = make_module(
        modulname="MSc Kurs", kurs_nr="M1", ist_zusatzmodul=False,
        datum=date(2026, 9, 14), startzeit="09:00", endzeit="11:00",
    )
    results = find_critical_first_session_conflicts([zusatz_first, zusatz_second, main_module], _family_key)
    assert len(results) == 1
    entry = results[0]
    involved = {entry["left"].modulname, entry["right"].modulname}
    assert involved == {"BSc Kurs", "MSc Kurs"}
    zusatz_side = entry["left"] if entry["left"].ist_zusatzmodul else entry["right"]
    zusatz_position = entry["left_session_position"] if entry["left"].ist_zusatzmodul else entry["right_session_position"]
    assert zusatz_side.datum == date(2026, 9, 14)
    assert zusatz_position == 1


def test_third_session_conflict_is_not_flagged():
    # Both courses' 3rd dated session collide - neither side is within its
    # own family's protected first-2 window (each family also has two
    # earlier, non-conflicting sessions), so nothing should be flagged even
    # though a Zusatzmodul is involved.
    zusatz_rows = [
        make_module(modulname="BSc Kurs", kurs_nr="B1", ist_zusatzmodul=True, datum=date(2026, 9, 14), startzeit="08:00", endzeit="10:00"),
        make_module(modulname="BSc Kurs", kurs_nr="B1", ist_zusatzmodul=True, datum=date(2026, 9, 21), startzeit="08:00", endzeit="10:00"),
        make_module(modulname="BSc Kurs", kurs_nr="B1", ist_zusatzmodul=True, datum=date(2026, 9, 28), startzeit="08:00", endzeit="10:00"),
    ]
    main_rows = [
        make_module(modulname="MSc Kurs", kurs_nr="M1", ist_zusatzmodul=False, datum=date(2026, 9, 7), startzeit="09:00", endzeit="11:00"),
        make_module(modulname="MSc Kurs", kurs_nr="M1", ist_zusatzmodul=False, datum=date(2026, 9, 14), startzeit="14:00", endzeit="16:00"),
        make_module(modulname="MSc Kurs", kurs_nr="M1", ist_zusatzmodul=False, datum=date(2026, 9, 28), startzeit="09:00", endzeit="11:00"),
    ]
    results = find_critical_first_session_conflicts(zusatz_rows + main_rows, _family_key)
    assert results == []


def test_pure_master_master_conflict_never_flagged_even_on_first_session():
    a = make_module(modulname="MSc Kurs A", kurs_nr="M1", ist_zusatzmodul=False, datum=date(2026, 9, 14), startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="MSc Kurs B", kurs_nr="M2", ist_zusatzmodul=False, datum=date(2026, 9, 14), startzeit="09:00", endzeit="11:00")
    assert find_critical_first_session_conflicts([a, b], _family_key) == []


def test_exam_rows_are_skipped_when_counting_session_position():
    # An exam row dated BEFORE the two real teaching sessions must not push
    # the real 1st/2nd session out of the protected window.
    exam = make_module(modulname="BSc Kurs", kurs_nr="B1", ist_zusatzmodul=True, ist_pruefung=True, datum=date(2026, 9, 7), startzeit="08:00", endzeit="10:00")
    real_first = make_module(modulname="BSc Kurs", kurs_nr="B1", ist_zusatzmodul=True, datum=date(2026, 9, 14), startzeit="08:00", endzeit="10:00")
    real_second = make_module(modulname="BSc Kurs", kurs_nr="B1", ist_zusatzmodul=True, datum=date(2026, 9, 21), startzeit="08:00", endzeit="10:00")
    main_module = make_module(modulname="MSc Kurs", kurs_nr="M1", ist_zusatzmodul=False, datum=date(2026, 9, 21), startzeit="09:00", endzeit="11:00")
    results = find_critical_first_session_conflicts([exam, real_first, real_second, main_module], _family_key)
    assert len(results) == 1
    zusatz_position = results[0]["left_session_position"] if results[0]["left"].ist_zusatzmodul else results[0]["right_session_position"]
    assert zusatz_position == 2  # real_second is the course's 2nd non-exam session, not 3rd


def test_undated_row_is_never_treated_as_protected():
    undated = make_module(modulname="BSc Kurs", kurs_nr="B1", ist_zusatzmodul=True, datum=None, wochentag="montag", startzeit="08:00", endzeit="10:00")
    main_module = make_module(modulname="MSc Kurs", kurs_nr="M1", ist_zusatzmodul=False, datum=None, wochentag="montag", startzeit="09:00", endzeit="11:00")
    assert find_critical_first_session_conflicts([undated, main_module], _family_key) == []


def test_bachelor_bachelor_conflict_on_first_session_is_flagged():
    # Two Zusatzmodule colliding with each other (no Master module involved
    # at all) still counts - the risk (missed intro info) is the same.
    a = make_module(modulname="BSc Kurs A", kurs_nr="B1", ist_zusatzmodul=True, datum=date(2026, 9, 14), startzeit="08:00", endzeit="10:00")
    b = make_module(modulname="BSc Kurs B", kurs_nr="B2", ist_zusatzmodul=True, datum=date(2026, 9, 14), startzeit="09:00", endzeit="11:00")
    results = find_critical_first_session_conflicts([a, b], _family_key)
    assert len(results) == 1
    assert results[0]["left_session_position"] == 1
    assert results[0]["right_session_position"] == 1
