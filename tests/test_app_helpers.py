"""
Tests for the pure, Streamlit-independent helper functions added to/changed
in src/app.py during the 2026-10-12 UX-feedback round (short chart labels,
Kurs-Nr-aware tile codes, Pruefungseinsicht/exam/conflict chart markers,
and the "Quelle" column's BSc/MSc text), plus `_hidden_selected_count()`
from the same day's follow-up "filter quick wins" round - it does read
`st.session_state`, but only via `.get(...)`, which works fine outside a
real Streamlit session (confirmed empirically: it just returns the
provided default, with a harmless warning, not an exception) - so it's
tested here too by setting the relevant keys directly before calling it.

`src/app.py` itself is policy-documented as not having automated UI tests
(see docs/TESTING-README.md "What isn't covered" - manual/Playwright
browser testing covers the interactive Streamlit flow instead, notably the
guided-planning selection-persistence-across-filters fix and the
individual-item removal list, both verified live and documented in their
commit messages, NOT here). These functions are the exception: they are
plain Python (no `st.*` calls), take/return ordinary values or a Plotly
figure, and are cheap and meaningful to test in isolation - the same
reasoning tests/test_scheduler.py and tests/test_models.py already apply
to the rest of the backend.

Importing `app` directly (unlike every other test file, which imports
narrower backend modules) is intentional and new for this file - see the
module-level comment below for why it's safe.
"""

from datetime import date, time

import pandas as pd
import plotly.graph_objects as go
import pytest

from models import ZHAWModule, Weekday

# Importing the full app.py module (not just a function) is unusual for
# this test suite, but required to reach these module-private helpers.
# app.py calls `st.set_page_config(...)` and sets up logging at import
# time - both are harmless outside a real `streamlit run` session (the
# former only emits a "missing ScriptRunContext" warning in bare mode,
# confirmed empirically; it does not raise). Importing it exactly once
# here (Python caches the module) does not execute `main()` - that only
# runs behind the `if __name__ == "__main__":` guard at the bottom of the
# file - so no UI is actually rendered and no upload/session state is
# touched by this import.
import app


def make_module(**overrides):
    """Build a minimal valid ZHAWModule, overriding only the fields under
    test - same helper pattern as tests/test_models.py and
    tests/test_scheduler.py, for consistency across the suite."""
    defaults = dict(
        modulname="Testmodul",
        wochentag="montag",
        startzeit="08:15",
        endzeit="10:00",
        ects=3,
    )
    defaults.update(overrides)
    return ZHAWModule(**defaults)


# --- _truncate_text ---------------------------------------------------

def test_truncate_text_leaves_short_text_unchanged():
    assert app._truncate_text("Statistik II") == "Statistik II"


def test_truncate_text_cuts_long_text_and_appends_ellipsis():
    long_title = "Wissenschaftstheoretische und methodologische Grundlagen"
    result = app._truncate_text(long_title, max_len=20)
    assert len(result) == 20
    assert result.endswith("…")
    assert long_title.startswith(result[:-1].rstrip())


def test_truncate_text_handles_none_and_empty_input():
    assert app._truncate_text(None) == ""
    assert app._truncate_text("") == ""


def test_truncate_text_exact_length_boundary_not_truncated():
    # Exactly max_len characters must NOT get an ellipsis - only text
    # that's actually longer than the limit should be cut.
    exact = "A" * 28
    assert app._truncate_text(exact, max_len=28) == exact


# --- _module_legend_label ----------------------------------------------

def test_module_legend_label_combines_modul_nr_and_truncated_title():
    long_title = "Wissenschaftstheoretische und methodologische Grundlagen der Psychologie"
    m = make_module(modulname=long_title, modul_nr="AS1")
    label = app._module_legend_label(m, max_len=20)
    assert label.startswith("AS1 - ")
    assert label.endswith("…")
    assert len(label) <= len("AS1 - ") + 20


def test_module_legend_label_prefers_kurs_nr_over_modul_nr_when_different():
    m = make_module(modulname="Kurs", modul_nr="AKP10", kurs_nr="AKP10-1")
    assert app._module_legend_label(m).startswith("AKP10-1 - ")


def test_module_legend_label_falls_back_to_title_only_without_identifiers():
    m = make_module(modulname="Kurs ohne Nummer")
    assert app._module_legend_label(m) == "Kurs ohne Nummer"


# --- _module_short_code --------------------------------------------------

def test_module_short_code_distinguishes_course_components_via_kurs_nr():
    # The real-world case this was fixed for: a module made of two
    # mandatory course components (AKP10-1 / AKP10-2) must not render as
    # the same tile text "AKP10" for both - see guided.step3_preview_caption.
    m1 = make_module(modulname="Kurs 1", modul_nr="AKP10", kurs_nr="AKP10-1")
    m2 = make_module(modulname="Kurs 2", modul_nr="AKP10", kurs_nr="AKP10-2")
    assert app._module_short_code(m1) == "AKP10-1"
    assert app._module_short_code(m2) == "AKP10-2"
    assert app._module_short_code(m1) != app._module_short_code(m2)


def test_module_short_code_uses_modul_nr_when_kurs_nr_matches_or_missing():
    m = make_module(modulname="Kurs", modul_nr="AS1")
    assert app._module_short_code(m) == "AS1"


def test_module_short_code_falls_back_to_title_prefix():
    m = make_module(modulname="Ganz ohne jede Nummer")
    assert app._module_short_code(m) == "Ganz ohne "[:10] or app._module_short_code(m) == "Ganz ohne "


# --- _is_pruefungseinsicht -----------------------------------------------

@pytest.mark.parametrize(
    "title,expected",
    [
        ("Statistik - Pruefungseinsicht", True),
        ("Statistik - Prüfungseinsicht", True),
        ("Statistik/PRUEFUNGSEINSICHT", True),
        ("Statistik - Pruefung", False),
        ("Normale Vorlesung", False),
    ],
)
def test_is_pruefungseinsicht_detects_real_spelling_variants(title, expected):
    m = make_module(modulname=title)
    assert app._is_pruefungseinsicht(m) is expected


# --- _zusatzmodul_marker / _style_source_rows ----------------------------

def test_zusatzmodul_marker_returns_bsc_for_zusatzmodul_row():
    m = make_module(ist_zusatzmodul=True)
    assert app._zusatzmodul_marker(m) == app.t("col.source.bsc") == "BSc"


def test_zusatzmodul_marker_returns_msc_for_main_list_row_not_blank():
    # Regression guard: this used to return "" for the common case - see
    # the commit that changed it, the user explicitly asked for an always-
    # filled column instead of a blank cell for Master rows.
    m = make_module(ist_zusatzmodul=False)
    assert app._zusatzmodul_marker(m) == app.t("col.source.msc") == "MSc"
    assert app._zusatzmodul_marker(m) != ""


def test_style_source_rows_only_tints_bsc_rows_not_every_non_empty_cell():
    # Regression guard for the bug _style_source_rows's own docstring
    # describes: once "Quelle" is always filled, a "cell is non-empty"
    # check would incorrectly tint every row, not just BSc ones.
    df = pd.DataFrame(
        {
            "Modul": ["A", "B"],
            "Quelle": [app.t("col.source.bsc"), app.t("col.source.msc")],
        }
    )
    html = app._style_source_rows(df, "Quelle").to_html()
    info_color = app._ROW_TONE_COLORS["info"]
    # Exactly one styled <tr> should carry the info background color.
    assert html.count(f"background-color: {info_color}") == 1


# --- _semester_grid_figure: sort order, Pruefungseinsicht exclusion ------

def _grid_week_order(fig) -> list[str]:
    """Extract the y-axis category order _semester_grid_figure() actually
    used, from its `category_orders` - the chart-building code under test
    documents this must run earliest-week-first/top-to-bottom."""
    return list(fig.layout.yaxis.categoryarray)


def test_semester_grid_figure_orders_weeks_ascending_by_real_date():
    # HS (autumn semester) year-boundary case: KW38 (September, this year)
    # must sort before KW3 (January, NEXT year) despite the raw ISO week
    # number being smaller - this is the exact bug reported ("KW3 shows
    # above KW51").
    early = make_module(modulname="Fruehes Modul", datum=date(2026, 9, 14))  # KW38
    late = make_module(modulname="Spaetes Modul", datum=date(2027, 1, 18))  # KW3, next year
    fig, excluded_undated, excluded_pe = app._semester_grid_figure([early, late], [early, late])
    assert excluded_undated == 0
    assert excluded_pe == 0
    weeks = _grid_week_order(fig)
    assert len(weeks) == 2
    # Plotly stores a y-axis's resolved `categoryarray` in BOTTOM-to-TOP
    # order internally - i.e. reversed relative to the `category_orders`
    # list the chart-building code passes in - specifically so that the
    # FIRST element of the list given to `category_orders` ends up
    # visually at the TOP. Empirically confirmed twice: once with a
    # standalone kaleido-rendered PNG comparison during development, once
    # live via Playwright against the running app (screenshot showed
    # "KW 38 (14.09.)" - the semester's actual first week - at the top of
    # the real chart). So the LAST entry of `categoryarray`, not the
    # first, is the one that renders at the top - assert against that.
    assert "38" in weeks[-1]
    assert weeks[0].startswith("KW 3 ")
    # No explicit axis reversal - reversing it would put the chart's LAST
    # category_orders entry at the top instead, which is the exact bug
    # this was fixed for (see _semester_grid_figure()'s own docstring).
    assert fig.layout.yaxis.autorange != "reversed"


def test_semester_grid_figure_excludes_pruefungseinsicht_sessions():
    normal = make_module(modulname="Normale Vorlesung", datum=date(2026, 9, 14))
    pe = make_module(modulname="Statistik - Pruefungseinsicht", datum=date(2026, 8, 1))
    fig, excluded_undated, excluded_pe = app._semester_grid_figure([normal, pe], [normal, pe])
    assert excluded_pe == 1
    assert excluded_undated == 0
    # Only the normal session should actually be plotted.
    assert fig.data[0].hovertext == ("Normale Vorlesung",) or "Normale Vorlesung" in str(fig.data[0].hovertext)


def test_semester_grid_figure_returns_none_when_everything_is_undated():
    undated = make_module(modulname="Ohne Datum")
    fig, excluded_undated, excluded_pe = app._semester_grid_figure([undated], [undated])
    assert fig is None
    assert excluded_undated == 1
    assert excluded_pe == 0


# --- exam/conflict marker overlays on a Plotly figure --------------------

def test_mark_exam_sessions_gives_only_exam_points_the_red_outline():
    fig = go.Figure(
        go.Scatter(
            x=[1, 2],
            y=[1, 2],
            mode="markers",
            marker=dict(line=dict(color="white", width=1)),
            customdata=[[False], [True]],
        )
    )
    app._mark_exam_sessions(fig)
    trace = fig.data[0]
    assert trace.marker.line.color == ("white", app._EXAM_MARKER_COLOR)
    assert trace.marker.line.width == (1, 3)


def test_mark_exam_sessions_is_a_noop_when_no_session_is_an_exam():
    fig = go.Figure(
        go.Scatter(x=[1], y=[1], mode="markers", marker=dict(line=dict(color="white", width=1)), customdata=[[False]])
    )
    app._mark_exam_sessions(fig)
    # Untouched: stays a plain scalar, not rewritten into a 1-element tuple.
    assert fig.data[0].marker.line.color == "white"


def test_mark_conflicted_sessions_overrides_exam_color_with_conflict_black():
    # A session that is BOTH an exam AND part of a time conflict must show
    # the conflict marking (run second, intentionally wins) - see
    # _mark_conflicted_sessions()'s own docstring for why this ordering is
    # load-bearing, not incidental.
    fig = go.Figure(
        go.Scatter(
            x=[1],
            y=[1],
            mode="markers",
            marker=dict(line=dict(color="white", width=1)),
            customdata=[[True, True]],  # is_exam=True, is_conflict=True
        )
    )
    app._mark_exam_sessions(fig)
    app._mark_conflicted_sessions(fig)
    trace = fig.data[0]
    assert trace.marker.line.color == (app._CONFLICT_MARKER_COLOR,)
    assert trace.marker.line.width == (4,)


def test_semester_grid_figure_marks_real_time_conflict_with_black_outline():
    a = make_module(modulname="Kurs A", modul_nr="A1", datum=date(2026, 9, 14), startzeit=time(9, 0), endzeit=time(11, 0))
    b = make_module(modulname="Kurs B", modul_nr="B1", datum=date(2026, 9, 14), startzeit=time(10, 0), endzeit=time(12, 0))
    fig, _, _ = app._semester_grid_figure([a, b], [a, b])
    for trace in fig.data:
        assert trace.marker.line.color == (app._CONFLICT_MARKER_COLOR,)


# --- _hidden_selected_count (Schritt-2 filter quick wins) -----------------

@pytest.fixture(autouse=True)
def _clear_selection_state():
    """Every _hidden_selected_count test below sets selected_course_bases/
    selected_row_ids directly - reset both before AND after each test so
    one test's fixture state can never leak into the next (st.session_state
    is just a process-wide dict in bare/test mode, not request-scoped)."""
    for key in ("selected_course_bases", "selected_row_ids"):
        app.st.session_state.pop(key, None)
    yield
    for key in ("selected_course_bases", "selected_row_ids"):
        app.st.session_state.pop(key, None)


def test_hidden_selected_count_module_mode_counts_keys_outside_filtered():
    visible = make_module(modulname="Sichtbar", modul_nr="VIS1")
    hidden = make_module(modulname="Versteckt", modul_nr="HID1")
    app.st.session_state["selected_course_bases"] = ["VIS1", "HID1"]
    # `filtered` only contains the visible module - HID1's key is selected
    # but not part of the currently filtered/visible set.
    count = app._hidden_selected_count([visible, hidden], [visible], app.t("guided.mode.module"))
    assert count == 1


def test_hidden_selected_count_is_zero_when_everything_selected_is_visible():
    visible = make_module(modulname="Sichtbar", modul_nr="VIS1")
    app.st.session_state["selected_course_bases"] = ["VIS1"]
    count = app._hidden_selected_count([visible], [visible], app.t("guided.mode.module"))
    assert count == 0


def test_hidden_selected_count_row_mode_uses_positions_not_identity():
    a = make_module(modulname="Kurs A")
    b = make_module(modulname="Kurs B")
    all_modules = [a, b]
    # Position 1 (Kurs B) is selected but filtered out (`filtered` only has
    # Kurs A) - row mode stores POSITIONS in selected_row_ids, not id()s.
    app.st.session_state["selected_row_ids"] = [1]
    count = app._hidden_selected_count(all_modules, [a], app.t("guided.mode.row"))
    assert count == 1


def test_hidden_selected_count_no_selection_at_all_is_zero():
    m = make_module(modulname="Kurs")
    count = app._hidden_selected_count([m], [], app.t("guided.mode.module"))
    assert count == 0


# --- _weekly_timeline_slots: on-bar text must be short, not the raw title --

def test_weekly_timeline_slots_short_label_is_module_short_code_not_full_title():
    # Regression guard: an earlier version set "short_label" to the raw,
    # untruncated `modulname` despite the name - reported by a user as
    # making the Wochenplan Gantt chart's on-bar text unreadable with real
    # (60+ character) ZHAW course titles. It must be the same short code
    # _module_short_code() already uses for the Schritt-3 preview tiles.
    long_title = "Wissenschaftstheoretische und methodologische Grundlagen der Psychologie"
    m = make_module(modulname=long_title, modul_nr="AS1", kurs_nr="AS1-1")
    slots = app._weekly_timeline_slots([m])
    assert len(slots) == 1
    assert slots[0]["short_label"] == app._module_short_code(m) == "AS1-1"
    assert slots[0]["short_label"] != long_title
    # The full name must still be available somewhere on the slot (used for
    # hover_name by the chart that consumes this) - not lost, just not the
    # permanently-visible on-bar text anymore.
    assert long_title in slots[0]["label"]


def test_weekly_timeline_slots_distinguishes_same_module_different_kurs_nr():
    # Two course components of the same module (see _module_short_code()'s
    # own test for the identical AKP10-1/-2 scenario) must still render
    # distinguishable short codes on the Gantt chart, not both "AKP10".
    m1 = make_module(modulname="Kurs 1", modul_nr="AKP10", kurs_nr="AKP10-1")
    m2 = make_module(modulname="Kurs 2", modul_nr="AKP10", kurs_nr="AKP10-2", startzeit=time(14, 0), endzeit=time(16, 0))
    slots = {slot["short_label"] for slot in app._weekly_timeline_slots([m1, m2])}
    assert slots == {"AKP10-1", "AKP10-2"}


# --- _calculate_module_overlap_summary: chart column must stay short -----

def test_overlap_summary_chart_label_is_truncated_even_without_modul_nr():
    # _module_group_title() (the function this summary groups by) falls
    # back to the full, untruncated base course title when a module has no
    # Modul-Nr at all - a real edge case this summary's own "_chart_label"
    # column exists specifically to guard against, so a title-only module
    # still can't feed a long name straight into the overlap bar chart's
    # axis (_overlap_bar_figure).
    long_title = "Wissenschaftstheoretische und methodologische Grundlagen der Psychologie"
    m = make_module(modulname=long_title)  # no modul_nr at all
    summary = app._calculate_module_overlap_summary([m])
    assert len(summary) == 1
    row = summary.iloc[0]
    assert row["_chart_label"] != long_title
    assert len(row["_chart_label"]) <= 24
    # The untruncated value remains available under its own, table-facing
    # column (c("base_course")) - only the chart-only column is shortened.
    assert row[app.c("base_course")] == long_title


def test_overlap_summary_chart_label_matches_short_modul_nr_unchanged():
    m = make_module(modulname="Kurs", modul_nr="AS1")
    summary = app._calculate_module_overlap_summary([m])
    assert summary.iloc[0]["_chart_label"] == "AS1"


# --- _chart_section_title / *_headline: settings.CHART_TITLE_STYLE -------
#
# Implements docs/UX-OPTIMIERUNGEN-README.md's Zusatzempfehlung C. Only the
# pure headline-computation helpers and the style switch itself are tested
# here; the st.markdown() render call sites in render_dashboard() are UI,
# not covered per this module's own docstring/policy.

def test_chart_section_title_label_mode_ignores_headline(monkeypatch):
    monkeypatch.setattr(app.settings, "CHART_TITLE_STYLE", "label")
    assert app._chart_section_title("dashboard.chart.weekday_title", "Some headline") == app.t(
        "dashboard.chart.weekday_title"
    )


def test_chart_section_title_headline_mode_uses_headline_when_present(monkeypatch):
    monkeypatch.setattr(app.settings, "CHART_TITLE_STYLE", "headline")
    assert app._chart_section_title("dashboard.chart.weekday_title", "**Some headline**") == "**Some headline**"


def test_chart_section_title_headline_mode_falls_back_without_headline(monkeypatch):
    # No data to summarize yet (headline is None) - must never go blank.
    monkeypatch.setattr(app.settings, "CHART_TITLE_STYLE", "headline")
    assert app._chart_section_title("dashboard.chart.weekday_title", None) == app.t("dashboard.chart.weekday_title")


def test_weekday_distribution_headline_matches_busiest_weekday():
    m1 = make_module(modulname="Kurs A", wochentag="dienstag")
    m2 = make_module(modulname="Kurs B", wochentag="dienstag", startzeit=time(14, 0), endzeit=time(16, 0))
    m3 = make_module(modulname="Kurs C", wochentag="montag")
    headline = app._weekday_distribution_headline([m1, m2, m3])
    assert headline == app.t("dashboard.chart.weekday_headline", day=app.t("weekday.dienstag"), count=2)


def test_weekday_distribution_headline_none_for_empty_list():
    assert app._weekday_distribution_headline([]) is None


def test_overlap_headline_none_for_empty_summary():
    assert app._overlap_headline(app._calculate_module_overlap_summary([])) is None


def test_overlap_headline_names_top_overlapping_course():
    a = make_module(modulname="Kurs A", modul_nr="AS1", wochentag="montag", startzeit=time(8, 15), endzeit=time(10, 0))
    b = make_module(modulname="Kurs B", modul_nr="BS1", wochentag="montag", startzeit=time(9, 0), endzeit=time(10, 30))
    summary = app._calculate_module_overlap_summary([a, b])
    headline = app._overlap_headline(summary)
    top_label = summary.iloc[0]["_chart_label"]
    top_minutes = int(summary.iloc[0][app.c("overlap_total_min")])
    assert headline == app.t("dashboard.chart.overlap_headline", course=top_label, minutes=top_minutes)


def test_semester_timeline_headline_names_busiest_week():
    tue = make_module(modulname="Dienstag-Kurs", datum=date(2026, 9, 15), wochentag="dienstag")
    wed = make_module(modulname="Mittwoch-Kurs", datum=date(2026, 9, 16), wochentag="mittwoch")
    other_wed = make_module(
        modulname="Noch ein Mittwoch-Kurs", datum=date(2026, 9, 16), wochentag="mittwoch", startzeit=time(14, 0), endzeit=time(16, 0)
    )
    headline = app._semester_timeline_headline([tue, wed, other_wed])
    weeks = app._semester_week_groups([tue, wed, other_wed])
    busiest = max(weeks, key=lambda week: week["session_count"])
    assert headline == app.t("dashboard.chart.semester_headline", label=busiest["label"], count=busiest["session_count"])


def test_semester_timeline_headline_none_without_dated_rows():
    undated = make_module(modulname="Ohne Datum", datum=None)
    assert app._semester_timeline_headline([undated]) is None


def test_daily_load_headline_names_busiest_date():
    short = make_module(modulname="Kurz", datum=date(2026, 9, 15), startzeit=time(8, 0), endzeit=time(9, 0))
    long_a = make_module(modulname="Lang A", datum=date(2026, 9, 16), startzeit=time(8, 0), endzeit=time(11, 0))
    long_b = make_module(modulname="Lang B", datum=date(2026, 9, 16), startzeit=time(13, 0), endzeit=time(14, 0))
    headline = app._daily_load_headline([short, long_a, long_b])
    assert headline == app.t("dashboard.chart.daily_load_headline", date="16.09.2026", minutes=240)


def test_daily_load_headline_none_without_dated_rows():
    undated = make_module(modulname="Ohne Datum", datum=None)
    assert app._daily_load_headline([undated]) is None


# --- _semester_week_groups: the "list (by week)" drill-down's data -------
#
# The rendering half (_render_semester_week_list) is st.*-based UI and,
# per this project's policy (see module docstring), is verified manually/
# via Playwright instead - these tests cover only the pure data-shaping
# function behind it (docs/UX-OPTIMIERUNGEN-README.md Punkt 3's second,
# originally-still-open sub-point).

def test_semester_week_groups_orders_weeks_by_actual_monday_date_not_raw_iso_week():
    # Same year-boundary-wraparound bug class _semester_grid_figure() was
    # already fixed for (see that function's own test) - a semester
    # spanning a calendar-year boundary has an early session in ISO week
    # 38 of 2026 and a later one in ISO week 1 of 2027; naive sorting by
    # raw week number alone would put "week 1" before "week 38".
    early = make_module(modulname="Fruehes Modul", datum=date(2026, 9, 14), wochentag="montag")
    late = make_module(modulname="Spaetes Modul", datum=date(2027, 1, 4), wochentag="montag")
    weeks = app._semester_week_groups([late, early])
    assert [w["week_monday"] for w in weeks] == [date(2026, 9, 14), date(2027, 1, 4)]


def test_semester_week_groups_skips_undated_rows():
    dated = make_module(modulname="Mit Datum", datum=date(2026, 9, 14))
    undated = make_module(modulname="Ohne Datum", datum=None)
    weeks = app._semester_week_groups([dated, undated])
    assert len(weeks) == 1
    assert weeks[0]["session_count"] == 1


def test_semester_week_groups_returns_empty_list_when_everything_is_undated():
    undated = make_module(modulname="Ohne Datum", datum=None)
    assert app._semester_week_groups([undated]) == []


def test_semester_week_groups_counts_sessions_and_distinct_conflict_dates():
    # Two sessions in the same week, only one of their two distinct dates
    # is in `conflict_dates` - conflict_count must reflect DISTINCT
    # conflicting dates in the week (matching how the heatmap view counts/
    # marks conflict days), not the number of sessions.
    tue = make_module(modulname="Dienstag-Kurs", datum=date(2026, 9, 15), wochentag="dienstag")
    wed = make_module(modulname="Mittwoch-Kurs", datum=date(2026, 9, 16), wochentag="mittwoch")
    weeks = app._semester_week_groups([tue, wed], conflict_dates={date(2026, 9, 15)})
    assert len(weeks) == 1
    week = weeks[0]
    assert week["session_count"] == 2
    assert week["conflict_count"] == 1

    sessions_by_module = {row[app.c("module")]: row for row in week["sessions"]}
    tue_row = next(row for name, row in sessions_by_module.items() if "Dienstag" in name)
    wed_row = next(row for name, row in sessions_by_module.items() if "Mittwoch" in name)
    assert tue_row[app.c("conflict")] != ""
    assert wed_row[app.c("conflict")] == ""


def test_semester_week_groups_sessions_sorted_by_date_then_start_time():
    later_day = make_module(
        modulname="Spaeter im Verlauf", datum=date(2026, 9, 16), wochentag="mittwoch", startzeit=time(8, 0), endzeit=time(10, 0)
    )
    earlier_day_later_time = make_module(
        modulname="Fruehere im Verlauf, spaeter am Tag",
        datum=date(2026, 9, 15),
        wochentag="dienstag",
        startzeit=time(14, 0),
        endzeit=time(16, 0),
    )
    earlier_day_earlier_time = make_module(
        modulname="Fruehester Termin der Woche",
        datum=date(2026, 9, 15),
        wochentag="dienstag",
        startzeit=time(8, 15),
        endzeit=time(10, 0),
    )
    weeks = app._semester_week_groups([later_day, earlier_day_later_time, earlier_day_earlier_time])
    assert len(weeks) == 1
    ordered_names = [row[app.c("module")] for row in weeks[0]["sessions"]]
    assert ordered_names == [
        "Fruehester Termin der Woche",
        "Fruehere im Verlauf, spaeter am Tag",
        "Spaeter im Verlauf",
    ]


def test_semester_week_groups_label_contains_iso_week_and_date_range():
    m = make_module(modulname="Kurs", datum=date(2026, 9, 15), wochentag="dienstag")
    week = app._semester_week_groups([m])[0]
    assert "KW 38" in week["label"]
    assert "14.09." in week["label"]  # the week's Monday
    assert "20.09." in week["label"]  # the week's Sunday


# --- _main_tab_specs: settings.SHOW_RAW_DATA_TAB toggle ------------------
#
# The rest of main() (actually rendering st.tabs()) is UI and, per this
# module's own docstring, not covered here - only the pure "which tabs are
# visible, in which order" decision this helper makes is tested.

def test_main_tab_specs_includes_raw_tab_by_default(monkeypatch):
    monkeypatch.setattr(app.settings, "SHOW_RAW_DATA_TAB", True)
    keys = [key for key, _label in app._main_tab_specs()]
    assert keys == ["guided", "dashboard", "timetable", "conflicts", "raw"]


def test_main_tab_specs_drops_raw_tab_when_disabled(monkeypatch):
    monkeypatch.setattr(app.settings, "SHOW_RAW_DATA_TAB", False)
    keys = [key for key, _label in app._main_tab_specs()]
    assert keys == ["guided", "dashboard", "timetable", "conflicts"]
    assert "raw" not in keys


# --- _resolve_default_theme: settings.DEFAULT_THEME ("auto"/"light"/"dark") --

def test_resolve_default_theme_fixed_light_ignores_context(monkeypatch):
    monkeypatch.setattr(app.settings, "DEFAULT_THEME", "light")
    assert app._resolve_default_theme("dark") == "light"
    assert app._resolve_default_theme(None) == "light"


def test_resolve_default_theme_fixed_dark_ignores_context(monkeypatch):
    monkeypatch.setattr(app.settings, "DEFAULT_THEME", "dark")
    assert app._resolve_default_theme("light") == "dark"
    assert app._resolve_default_theme(None) == "dark"


def test_resolve_default_theme_auto_follows_context_signal(monkeypatch):
    monkeypatch.setattr(app.settings, "DEFAULT_THEME", "auto")
    assert app._resolve_default_theme("dark") == "dark"
    assert app._resolve_default_theme("light") == "light"


def test_resolve_default_theme_auto_falls_back_to_light_without_signal(monkeypatch):
    # Streamlit's st.context.theme.type is None before a real browser
    # background-color signal is known (typically the very first script run
    # of a brand-new session) - must not crash and must fall back to the
    # app's original fixed default.
    monkeypatch.setattr(app.settings, "DEFAULT_THEME", "auto")
    assert app._resolve_default_theme(None) == "light"
    assert app._resolve_default_theme("something_unexpected") == "light"
