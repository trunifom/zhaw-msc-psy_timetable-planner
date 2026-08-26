# Testing Guide

This project has an automated pytest suite (`tests/`) covering the data
pipeline, domain model, conflict logic, export logic, and translations -
everything that sits behind the Streamlit UI in `src/app.py`.

## Running the tests

```bash
# from the repo root, with the project environment active
pytest -q
```

Prerequisites: `pytest` must be installed (it is listed in
`requirements.txt` / `environment.yaml`; if your environment was created
before it was added, run `pip install pytest`).

`tests/conftest.py` adds `src/` to `sys.path` automatically, so tests can
do `from data_loader import load_schedule_from_dataframe` etc. directly,
matching how `src/app.py` itself imports its sibling modules (flat
imports, no package structure - see the "Architektur" section of the main
README).

## Test files and what they cover

| File | Covers | Style |
|---|---|---|
| `tests/test_models.py` | `src/models.py` - the `ZHAWModule` Pydantic model: weekday/time/date parsing and their many accepted formats, ECTS bounds, exam-flag inference, attendance-percentage parsing, `duration_minutes`, `to_ui_dict()`. | Narrow unit tests, one `ZHAWModule` built per test via a `make_module(**overrides)` helper. |
| `tests/test_scheduler.py` | `src/scheduler.py`'s `find_time_conflicts` - the active conflict-detection algorithm (the rest of that file is unused legacy code, see its module docstring). Overlap math, same-date vs. same-weekday matching, duplicate-row suppression, pair de-duplication. | Narrow unit tests with 2-3 hand-built modules per test. |
| `tests/test_export.py` | `src/export.py`'s building blocks in isolation: RFC5545 text escaping and line folding, the dependency-free Europe/Zurich -> UTC DST conversion (including the March/October transition boundaries), UID slugification, event-title marker logic (exam / missing-date), the Excel export round-trip, and a few ICS structural edge cases (empty selection, `TRANSP` for real vs. placeholder events). | Narrow unit tests against small hand-built `ZHAWModule` lists. |
| `tests/test_i18n.py` | `src/i18n.py` - most importantly, that the `de`/`en`/`fr` translation blocks define **exactly the same set of keys** (catches translation drift), plus `get_text()`'s fallback chain and placeholder formatting. | Consistency checks + narrow unit tests. |
| `tests/test_data_loader.py` | The **full import pipeline** end-to-end: `data_loader.load_schedule_from_dataframe` against both fictional fixture files (header-banner detection, column aliasing incl. alternate/English headers, mixed date formats, weekday/multi-lecturer/placeholder parsing), the `MissingColumnError`/`DataLoaderError` structural-failure paths, plus regression tests for two real bugs found and fixed in this codebase (see below) and an integration check that the ICS export never silently drops a selected module. | Integration-style, built on two module-scoped fixtures loading `vorlesungsverzeichnis_fiktiv.xlsx` and `edge_cases_fiktiv.csv` once per test session. |

Rule of thumb used when writing these: if a test needs to construct a
`ZHAWModule` directly to isolate one behaviour, it belongs in the
`test_models.py` / `test_scheduler.py` / `test_export.py` style (narrow,
fast, no file I/O). If a test is really about "does a realistic uploaded
file survive the whole pipeline", it belongs in `test_data_loader.py`
against the shared fixture.

## Test data

Two separate locations, with two very different purposes and git policies
(see the main README's own "Testdaten" section for the short version):

- **`tests/fixtures/vorlesungsverzeichnis_fiktiv.xlsx`** - a fully
  **fictional** dataset (invented module names, course codes, and
  lecturer names) that mirrors the *structure* of a real ZHAW
  "Vorlesungsverzeichnis" export: a title banner row and a note row above
  the real header, the same column names (`SG`, `Lehrperson`, `Tag`,
  `Datum`, `von`, `bis`, `Modul-I`, `Kurs-Nr.`, `Anlassbezeichnung`,
  `Pruefung`, `Modulart`), `N.N.` placeholder lecturers, multi-lecturer
  `"A & B"` strings, sessions that genuinely change weekday/time from
  week to week within the same course (the real-world pattern that makes
  this app's guided planning necessary in the first place - a course is
  *not* simply "every Monday 8-10"), and a few exam rows whose module
  name already ends in `"/ PRUEFUNG"` (a real ZHAW export convention).
- **`tests/fixtures/edge_cases_fiktiv.csv`** - a small, purpose-built
  fictional fixture (3 rows) that deliberately uses a *different* set of
  column headers (`Weekday`/`Start`/`End`/`Course`/`Credits`/`Date`/
  `Room`/`Lecturer`/`Art`) than the primary fixture, to exercise the
  `COLUMN_ALIASES` mapping breadth that the primary (already-German)
  fixture never touches. Also covers mixed date formats in one file
  (`dd.mm.yyyy` and ISO side by side) and a genuinely blank date cell in a
  real multi-row CSV.

Both fixture files **are committed to git** - they contain no real
personal data, so there's nothing to protect.
- **`data/real/`** - not a fixture at all: a place to drop *your own real*
  exported Excel file for manual local testing. This folder has its own
  `.gitignore` (`*` / `!.gitignore` / `!.gitkeep`) and the root
  `.gitignore` explicitly re-includes the folder itself so that nested
  `.gitignore` can take effect - net result: nothing you put in
  `data/real/` other than those two dotfiles can ever be committed. Use
  this to sanity-check the app against your actual timetable without any
  risk of that data ending up in the repository (see README.md
  "Datenschutz").

If you need a *new* fixture (e.g. to reproduce a bug against a specific
column layout), regenerate or add another fictional `.xlsx`/`.csv` under
`tests/fixtures/` the same way - fabricate the data, never anonymize a
real export by hand (too easy to miss something).

## Regression tests worth knowing about

Two real, previously-shipped bugs are specifically guarded against so
they can't silently come back:

1. **`tests/test_data_loader.py::test_row_without_any_date_is_kept_not_dropped`**
   and **`tests/test_models.py::test_pandas_nat_date_becomes_none`** -
   `pandas.NaT` (pandas' "missing datetime" value) satisfies
   `isinstance(v, datetime)` in Python, so an earlier version of
   `ZHAWModule`'s date validator called `NaT.date()`, which returns `NaT`
   again rather than raising - this made Pydantic's core validator throw
   an opaque `TypeError` instead of cleanly producing `datum=None`, which
   in turn made the data loader silently discard the **entire row** (not
   just the date) since a `TypeError` isn't a `ValidationError` and wasn't
   caught by the row-level retry logic.
2. **`tests/test_data_loader.py::test_ics_export_includes_every_module`** -
   the ICS calendar export used to skip any module without a `datum`
   entirely. Since every selected module is expected to represent one
   concrete session (see `src/models.py`'s module docstring), this made
   students' calendars silently miss courses. The export now always
   produces one event per selected module - dated sessions as normal
   timed events, anything still missing a date as a clearly-marked,
   non-blocking all-day placeholder instead of disappearing.

## What isn't covered

`src/app.py` itself (the Streamlit UI - session-state wiring, widget
layout, Plotly chart construction, the guided-planning flow) has no
automated tests here. Streamlit apps don't lend themselves to typical unit
testing without a browser/AppTest harness, and this suite deliberately
focuses on the parts that are pure, deterministic business logic
(everything app.py delegates to `data_loader`/`models`/`scheduler`/`export`).
Manually exercising the running app (`streamlit run src/app.py`) against
the fixture file - or your own file in `data/real/` - remains the way to
check the UI itself.

This gap is real, not theoretical: a design-system pass on `src/app.py`
(card-based layout, `st.column_config` table formatting, status-color
Stylers) shipped three bugs that `pytest -q` was structurally unable to
catch, all only found by actually loading the fixture file in a browser:

- **`ImportError: background_gradient requires matplotlib.`** - pandas'
  `Styler.background_gradient(cmap=...)` silently requires matplotlib,
  which is not a dependency of this project, and only raises the first
  time a table using it actually renders with data (not at import time or
  in any syntax/compile check). Fixed by `_style_sequential_red()` in
  `src/app.py`, a small dependency-free replacement - reuse that function
  for any future "color a numeric column by severity" table instead of
  reaching for `background_gradient()` again.
- A card title rendered literal `**asterisks**` on screen - some i18n
  strings still carry markdown bold markers left over from an older
  `st.markdown()`-based section header, and the `card()` helper inserts
  its `title` argument as plain text (not markdown-parsed). See `card()`'s
  own docstring for the `.strip("*")` convention this requires.
- Low text contrast at the high-severity end of a red heatmap-style column
  (dark text on near-black-red). Fixed by flipping to white text past the
  ratio midpoint in `_style_sequential_red()`.

None of these can get an automated regression test under the current
"app.py is UI-only, untested" policy - they're recorded here instead so
the same mistakes aren't repeated. If `src/app.py` ever grows a browser-
based test harness (e.g. Streamlit's `AppTest`), these three are the first
candidates to convert into real regression tests.

## Adding new tests

- Match the file that already covers the module you're changing (see the
  table above) rather than creating a new file per feature.
- Prefer the narrow `make_module(**overrides)` style for anything that
  doesn't need a whole realistic file.
- If you're fixing a bug, add a regression test for it in the same
  commit/PR and reference the bug in the test name or a short comment
  (see "Regression tests worth knowing about" above for the expected
  style) - this list should stay accurate as the project evolves.
