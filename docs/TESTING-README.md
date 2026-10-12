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
| `tests/test_scheduler.py` | `src/scheduler.py`'s `find_time_conflicts` - the active conflict-detection algorithm (the rest of that file is unused legacy code, see its module docstring). Overlap math, same-date vs. same-weekday matching, duplicate-row suppression, pair de-duplication, and that a conflict between a main-list and a Zusatzmodul (Passerelle supplementary module) is caught exactly like any other conflict. Also covers `find_critical_first_session_conflicts` - the Passerelle "don't miss a course's 1st/2nd session" narrowing used by the Konfliktanalyse/Dashboard "kritische Ersttermine" cards: session-position counting per course family (via an injected `family_key` callable, keeping this module decoupled from app.py's title-parsing rules), exam/undated-row exclusion from that counting, and the Zusatzmodul-involvement gate (pure Master↔Master conflicts are never flagged here). | Narrow unit tests with 2-3 hand-built modules per test. |
| `tests/test_export.py` | `src/export.py`'s building blocks in isolation: RFC5545 text escaping and line folding, the dependency-free Europe/Zurich -> UTC DST conversion (including the March/October transition boundaries), UID slugification, event-title marker logic (exam / missing-date), the Excel export round-trip, a few ICS structural edge cases (empty selection, `TRANSP` for real vs. placeholder events), and the Zusatzmodule export tagging (Excel "Quelle" column, ICS "Zusatzmodul (Passerelle)" description line). | Narrow unit tests against small hand-built `ZHAWModule` lists. |
| `tests/test_i18n.py` | `src/i18n.py` - most importantly, that the `de`/`en`/`fr` translation blocks define **exactly the same set of keys** (catches translation drift), plus `get_text()`'s fallback chain and placeholder formatting. | Consistency checks + narrow unit tests. |
| `tests/test_data_loader.py` | The **full import pipeline** end-to-end: `data_loader.load_schedule_from_dataframe` against all three original fictional fixture files (header-banner detection, column aliasing incl. alternate/English headers, mixed date formats, weekday/multi-lecturer/placeholder parsing), the `MissingColumnError`/`DataLoaderError` structural-failure paths, deriving `wochentag` from `datum` when no weekday column exists at all, the `ist_zusatzmodul` flag being set correctly per upload path, plus regression tests for two real bugs found and fixed in this codebase (see below) and an integration check that the ICS export never silently drops a selected module. | Integration-style, built on module-scoped fixtures loading `vorlesungsverzeichnis_fiktiv.xlsx`, `edge_cases_fiktiv.csv`, and `vorlesungsverzeichnis_passerelle_fiktiv.xlsx` once per test session. |
| `tests/test_zusatzmodule_fixtures.py` | The same full import pipeline **at realistic real-world scale**, against the large-scale/scenario fixtures described in "Test data" below (full-size fictionalized Bachelor/Master catalogs, an engineered cross-catalog conflict pair, an engineered Modul-Nr collision pair): row counts surviving import, weekday derivation across the *entire* real date range, every real `Modulart` value, both real "parallel offerings" patterns (labeled `- Gruppe a..h` and unlabeled/ambiguous - see `app._has_undistinguished_parallel_offerings`), `ist_zusatzmodul` tagging, cross-catalog conflict detection end-to-end (not hand-built `ZHAWModule`s, plus that the same engineered conflict pair is also caught by `find_critical_first_session_conflicts` as a critical first-session conflict), the Modul-Nr-collision data-layer contract, Excel/ICS export at ~1500 combined rows, and (skipped unless `data/real/` is present locally) a direct diff against the real files proving no real name/module code/title leaked into the committed fixtures. | Integration-style, built on module-scoped fixtures loading the six fixtures generated by `tests/fixtures/generate_fictional_fixtures.py`. |
| `tests/test_zusatzmodule_allowlist.py` | The (currently disabled) Modul-Nr/Kurs-Nr allowlist pre-filter for the Zusatzmodule upload - see `src/data_loader.py`'s "ZUSATZMODULE-VORFILTER" section and `settings/zusatzmodule_allowlist.json`. Covers: loading/normalizing the JSON settings file (missing file, malformed JSON, non-object JSON, deduplication all degrade to an empty/`None` result rather than raising), the row-filtering logic in isolation, that the feature is a complete no-op with the shipped default (`ZUSATZMODULE_ALLOWLIST_ENABLED = False`), and - via `monkeypatch` - the future "flipped on" behaviour (filters the Zusatzmodule upload, never the main upload, falls back to unfiltered if the settings file is missing). | Narrow unit tests plus a few `monkeypatch`-based end-to-end calls through `load_schedule_from_dataframe`. |
| `tests/test_app_helpers.py` | A deliberate, narrow exception to the "`src/app.py` has no automated tests" policy described in "What isn't covered" below: the handful of helper functions added/changed in the 2026-10-12 UX-feedback round(s) that are plain Python needing no real Streamlit session - `_truncate_text`/`_module_legend_label` (chart legend/axis label shortening), `_module_short_code` (Kurs-Nr-aware Schritt-3 tile codes), `_is_pruefungseinsicht` (title-based exam-review detection), `_zusatzmodul_marker`/`_style_source_rows` (the "Quelle" column's BSc/MSc text and its row-tinting), `_semester_grid_figure`/`_mark_exam_sessions`/`_mark_conflicted_sessions` (the Schritt-3 preview grid's week-ordering, Pruefungseinsicht exclusion, and red/black marker-outline logic), and `_hidden_selected_count` (the Schritt-2 "N of your selections are hidden by the active filters" hint's counting logic - the one function here that DOES read `st.session_state`, via `.get(...)` only, which works fine outside a real session). Imports `src/app.py` directly (every other file here imports a narrower backend module) - see that test file's module docstring for why that's safe. | Narrow unit tests, same `make_module(**overrides)` helper pattern as `test_models.py`/`test_scheduler.py`; a couple of tests build a minimal `plotly.graph_objects.Figure` directly instead of a `ZHAWModule` list, to test the marker-overlay functions without going through the full chart-building function; the `_hidden_selected_count` tests use an autouse fixture to set/clear the relevant `st.session_state` keys around each test so they can't leak into each other. |
| `tests/test_deployment_config.py` | Not application code at all - `requirements.txt`/`environment.yaml` themselves. Added after a real incident where `requirements.txt` was missing the `numpy<2.0` pin that `environment.yaml` carries (lost in an earlier cleanup commit, invisible locally since the hand-curated conda env never re-resolves dependencies) - Streamlit Community Cloud builds from a fresh `pip install -r requirements.txt`, not from `environment.yaml`, so a drift here can break or silently misbehave on Cloud while every local/CI run (inside the already-correct conda env) stays green. Parses both files and checks their version pins/constraints stay consistent with each other. | Config-parsing assertions, no app code imported. |

Rule of thumb used when writing these: if a test needs to construct a
`ZHAWModule` directly to isolate one behaviour, it belongs in the
`test_models.py` / `test_scheduler.py` / `test_export.py` style (narrow,
fast, no file I/O). If a test is really about "does a realistic uploaded
file survive the whole pipeline", it belongs in `test_data_loader.py`
against the shared fixture - unless it's specifically about the
Zusatzmodule/Passerelle feature at realistic scale or a cross-catalog
scenario, in which case it belongs in `test_zusatzmodule_fixtures.py`
instead, to keep that feature's now-large fixture set from crowding out
`test_data_loader.py`'s general-purpose pipeline coverage.

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
- **`tests/fixtures/vorlesungsverzeichnis_passerelle_fiktiv.xlsx`** - a
  fully **fictional** Bachelor-level course catalog (26 rows), fictionalized
  from the structure of a real ZHAW export handed to Passerelle students as
  a second, optional upload. Deliberately has **no weekday column at all** (only
  `Datum`) - by design, to exercise the "derive wochentag from datum" rule
  in `data_loader.load_schedule_from_dataframe`. Also models two different
  "parallel offerings at the same slot" patterns found in the real catalog:
  module `PF3` (six lecturers, no distinguishing suffix in the title at
  all) and module `ANW7` (three lecturers, likewise undistinguished) -
  neither is something `data_loader.py` resolves or deduplicates; the UI
  layer (`app._has_undistinguished_parallel_offerings`, not covered by
  this suite - see "What isn't covered" below) only surfaces a hint about
  the ambiguity instead of silently going on as if it weren't there.

All three fixture files **are committed to git** - they contain no real
personal data, so there's nothing to protect.

- **`tests/fixtures/generate_fictional_fixtures.py`** + the six files it
  writes - a large-scale/scenario expansion of the Zusatzmodule fixtures
  above, added when the feature's test coverage was deliberately broadened
  beyond hand-picked excerpts. Two categories:
  - **Full-scale, real-data-derived**: `vorlesungsverzeichnis_bsc_
    vollstaendig_fiktiv.xlsx` (1182 rows) and `vorlesungsverzeichnis_msc_
    vollstaendig_fiktiv.xlsx` (343 rows) are the *entire* real HS26
    Bachelor/Master catalogs, fictionalized end to end - every Lehrperson,
    Modul-Nr/Kurs-Nr, and Anlassbezeichnung is replaced via a deterministic
    mapping (same real value -> same fictional value every time the script
    is rerun), while scheduling metadata that isn't personally identifying
    (SG, Semester, Datum, von, bis, Modulart, the Pruefung flag/Tag column)
    is kept exactly as in the real export - preserving the real diversity
    (every real `Modulart` value, the real date range, both real
    "parallel offerings" patterns) is the whole point. The generator
    script itself is committed too (it contains no real data, only logic
    and a closed pool of fictional names/titles) so the fixtures' exact
    provenance stays transparent and reproducible; it reads from
    `data/real/` (only present locally, never in git/CI - see below) and
    is a no-op for this pair of fixtures if those files aren't there.
  - **Hand-engineered, NOT derived from real data**: `vorlesungsverzeichnis_
    konflikt_hauptliste_fiktiv.xlsx` + `..._zusatzliste_fiktiv.xlsx` (one
    guaranteed cross-catalog time conflict, one guaranteed non-conflict) and
    `vorlesungsverzeichnis_modulnr_kollision_hauptliste_fiktiv.xlsx` +
    `..._zusatzliste_fiktiv.xlsx` (the two catalogs coincidentally reusing
    the same Modul-Nr). A real catalog, even fictionalized,
    can't reliably guarantee a specific condition like "these two rows must
    overlap" - these four files always regenerate, independent of whether
    `data/real/` exists.

  Run `python tests/fixtures/generate_fictional_fixtures.py` to regenerate
  all six (e.g. after a newer real export replaces the files in
  `data/real/`) - see the script's own module docstring for the full
  fictionalization rules.

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

`src/app.py`'s actual Streamlit UI - session-state wiring, widget layout,
the guided-planning selection flow, and anything that reads/writes
`st.session_state` or calls `st.*` widgets - has no automated tests here.
Streamlit apps don't lend themselves to typical unit testing without a
browser/AppTest harness, and this suite deliberately focuses on the parts
that are pure, deterministic business logic (everything app.py delegates
to `data_loader`/`models`/`scheduler`/`export`, plus - as of
`tests/test_app_helpers.py`, see the table above - a handful of app.py's
own helper functions that happen to be pure Python themselves). In
particular, none of the following are covered by `pytest -q` and were
instead verified live with Playwright against the running app (see the
2026-10-12 entry further down for the specific repro steps used):
Schritt 2's filter-widgets-vs-selection-persistence interaction, the
individual-item selection-removal list, and the structured search fields'
autocomplete behavior.
Manually exercising the running app (`streamlit run src/app.py`) against
the fixture file - or your own file in `data/real/` - remains the way to
check the UI itself. This includes the Zusatzmodule upload/merge feature
(second sidebar upload, source badges in the four result tables, and the
"undistinguished parallel offerings" hint) - verified manually via
Playwright against the real Bachelor/Master catalogs and the fixture
files, not by an automated test. Also included: the floating feedback tab
(`_render_feedback_widget()` in `src/app.py`, see the README's "Feedback
geben" section) - pure HTML/CSS with no Streamlit widget behind it, so
there's nothing for `pytest`/Streamlit's own test tooling to exercise;
its hover/click/open behavior and light/dark rendering were checked with
Playwright screenshots instead. What automated coverage it *does* have:
the `test_i18n.py` exhaustive-coverage test (see the table above) fails
if a `feedback.*` key is ever added to only one of the three language
blocks.

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

A later manual pass (switching UI language back and forth, then a ZHAW
corporate-design/contrast pass) found three more of the same kind:

- Switching the sidebar language selector left the labels positioned
  *before* the selectbox in the script (sidebar header, card titles, the
  theme-toggle label) stuck in the old language for one extra rerun, while
  everything rendered after that point already showed the new language -
  same root cause and same fix pattern as the dark/light toggle bug above
  (read the widget's own frontend-updated session_state key at the very
  top of the script, before any `t()` call depends on the derived value).
  See the `sidebar_language_selector` block near the top of `src/app.py`.
- Download buttons (Excel/ICS export) rendered with a dark background and
  dark, barely-readable text in light mode - they were relying on
  Streamlit's own native button styling, which (like the input widgets
  above) is decoupled from this app's light/dark toggle unless explicitly
  covered by `_inject_design_system_css()`. Fixed by giving `.stButton`/
  `.stDownloadButton` the same `--zp-*` tokens as inputs and cards.
- Combining Plotly's `color=` and `pattern_shape=` on the weekly timeline
  chart (used to give exam sessions a texture, not just a color) made
  Plotly Express auto-name each legend entry `"{type}, {examBool}"`,
  leaking a literal "False" into labels like "Wahlpflichtmodul, False".
  Fixed in `_weekly_timeline_figure()` by trimming trace names back down
  to just the color value via `fig.for_each_trace(...)` and hiding the
  resulting duplicate legend entries. Worth remembering if `pattern_shape`
  is ever combined with `color` on another chart in this file.

None of these can get an automated regression test under the current
"app.py is UI-only, untested" policy - they're recorded here instead so
the same mistakes aren't repeated. If `src/app.py` ever grows a browser-
based test harness (e.g. Streamlit's `AppTest`), these are the first
candidates to convert into real regression tests.

A 2026-09-10/11 round adding the "Anwesenheits-Ampel" (attendance
traffic light, `_attendance_status_dataframe()`/`_style_attendance_rows()`
in `src/app.py`) and fixing four bugs a real user hit with real ZHAW data
found the same pattern again - all caught only by actually driving the
running app (Playwright, purpose-built fixtures, real browser
interaction), not by `pytest -q`:

- The Konflikte-Tab's per-course attendance table was accidentally nested
  inside the absence-rule-only `if absence_all_df.empty:` branch, so it
  never rendered at all for a student with zero absence rules configured -
  a completely normal case. Fixed by giving it its own, independent
  emptiness check.
- An unknown `anwesenheitspflicht_prozent` value rendered as the literal
  string "None" in a table cell (a `float`/`None`-mixed pandas column
  reads as "None" text in `st.dataframe`, not blank) - the common case,
  since most real ZHAW exports don't carry that column yet. Fixed by
  formatting the column as a display string (`""` for unknown) instead of
  passing the raw value through.
- **The most impactful one:** every Dashboard and Wochenplan chart came up
  completely blank (title/caption/settings panel rendered, but no plot and
  no error message) for a user with real data. Root cause:
  `_render_chart_toolbar()`'s weekday-filter `st.multiselect` only honors
  `default=` the very first time its `key` is created; every later rerun
  restores `st.session_state[key]` intersected with the current `options`
  with **no error even if that intersection is empty** - and it silently
  was, because the widget's session-state entry from an earlier
  file/session shared zero weekdays with the newly uploaded data. Every
  chart built from the resulting empty `filtered_modules` then hit its own
  `if not modules: return None` guard, and (for the weekday/overlap charts
  specifically) there was no `st.info(...)` fallback for that case either,
  so the result was a silent gap. Reproduced with
  `streamlit.testing.v1.AppTest` first (proving the exact multiselect
  behavior), then end-to-end with two purpose-built fixtures with
  non-overlapping weekday sets uploaded one after another. Fixed by
  tracking an "options signature" companion session-state key in
  `_render_chart_toolbar()` and resetting the stored selection back to
  "everything selected" whenever the available weekdays actually change,
  plus adding the missing `st.info(t("dashboard.chart.no_data"))`
  fallbacks so a genuinely empty result explains itself instead of looking
  broken.
- The weekly timeline chart's legend (`_weekly_timeline_figure()`) sized
  itself to the single longest course name in Plotly's default
  right-of-plot vertical legend - with real (60+ character) ZHAW course
  titles, this squeezed the actual weekday timeline down to a narrow
  sliver next to a wall of legend text. Fixed by truncating long legend
  labels and switching to a horizontal, wrapping legend below the plot
  instead of beside it.

A fifth report from the same round - a course checkbox in the
guided-planning selection tables (`st.data_editor` + `CheckboxColumn`,
"module"/"course"/"row" mode) sometimes needing more than one click, and
occasionally losing an already-made selection - turned out **not** to be
fixable in `src/app.py` at all: two rounds of code review found no stray
`st.rerun()` or session-state bug, and the user confirmed (after testing
across multiple browsers) that it only happens when clicking a different
checkbox again before the previous click's full script rerun has finished
reloading the table - a timing/race condition inherent to committing a
`data_editor` edit via a rerun, not something this app's code controls.
Addressed with an in-UI hint (`guided.checkbox_click_hint`, shown directly
above all three selection tables) telling students to wait for the table
to finish reloading between clicks, rather than a structural rewrite - see
the "module_group_selector_editor" comments in `src/app.py` if a more
robust fix (real per-row `st.checkbox()` widgets instead of a
`CheckboxColumn` grid) is ever revisited.

A later addition in the same vein, but a rare case where the interesting
logic could actually live in `src/scheduler.py` instead of `src/app.py`:
the Passerelle "kritische Ersttermine" feature (`find_critical_first_
session_conflicts` - detects a conflict landing on a course's 1st/2nd
dated session, specifically for Passerelle students whose Bachelor
Zusatzmodule and Master modules collide far more than two Master modules
normally would). Because the detection algorithm is a pure function over a
`ZHAWModule` list with no `st.session_state` dependency, it got full
automated `pytest` coverage (see the `test_scheduler.py`/
`test_zusatzmodule_fixtures.py` rows above) - only the two new `src/app.py`
UI cards that call it (`dash-passerelle-critical`, `conflicts-passerelle-
critical`, both gated behind a Zusatzmodule upload existing at all) needed
manual Playwright verification: confirmed absent with only a main-list
upload, confirmed appearing with the engineered `vorlesungsverzeichnis_
konflikt_hauptliste_fiktiv.xlsx`/`..._zusatzliste_fiktiv.xlsx` fixture pair
(where the single engineered conflict is, by construction, each module's
1st session), and checked in dark mode.

Following a request to make this feature's explanation more thorough, both
cards also gained a collapsed `st.expander` ("ℹ️ Warum ist das wichtig - und
was tun?") with a fuller rationale (what a 1st/2nd session typically covers:
assessment requirements, exam format, group assignment, course structure,
reading list) and concrete action items for a flagged conflict (contact
both instructors early, ask classmates for materials, check for a
recording/alternative session, factor it into course choice in guided
planning Step 2) - shared verbatim between the Dashboard and Konfliktanalyse
cards via `passerelle_critical.*` i18n keys (see docs/i18n-README.md's note
on that namespace) rather than duplicated per tab, so the two can't drift
apart. Manually verified rendering (bullet lists, bold text) in German,
English, and French via Playwright.

A 2026-10-12 round responding to a batch of 14 real user-reported UX issues
in Schritt 2/3 of guided planning (long course names cluttering charts,
indistinguishable AKP10-1/-2 tiles, a filter wiping the whole selection, no
way to remove a single selected item, typo-prone search fields, the
Schritt-3 preview sorted backwards, no exam/conflict marking, an always-
blank "Quelle" column for Master rows) again found the most impactful bug
only by actually driving the app, not by code review or `pytest -q`:

- **The most impactful one, reported verbatim as "Stelle ich den Filter
  um... so löscht es mir meine gesamte Vorauswahl":** narrowing any Schritt
  2 filter (search text, a weekday/type/lecturer multiselect) silently
  dropped every previously selected module/course/row that the new filter
  no longer showed, in all three selection modes ("Modulbasiert"/
  "Kursbasiert"/"Alle Termine darstellen"). Root cause: `selected_course_
  bases`/the final `selected_modules` list were rebuilt from scratch every
  rerun using only the *currently filtered/visible* table rows - a
  selection outside that filtered view had nowhere to persist. Reproduced
  live with Playwright (select all 6 modules via "Alle auswählen", filter
  to "Montag" only, watch the selection count stay wrongly correct **in
  code review** but need the live run to catch what actually happened to
  `selected_modules` across the rerun) and fixed by tracking selection
  state against TWO groupings per mode: the filtered one (for the visible
  table) and one built from the full, unfiltered `all_modules` (for
  resolving which actual rows belong to an already-selected-but-currently-
  hidden key). Verified live afterwards: the same repro now keeps all 62
  originally selected sessions selected after the weekday filter, and the
  "Bestandteile je gewähltem Modul" expanders for the 3 now-filtered-out
  modules still render correctly.
- **A regression introduced by this round's own fix for the bug above,
  caught only by re-testing live, not by `pytest -q` (242 tests, including
  the new `test_app_helpers.py`, stayed green throughout):** the new
  "remove one selected item individually" list
  (`_render_selected_items_removal()`) initially called `st.rerun()` from
  its "✕" button handler while still positioned *inside* the manually
  entered-but-not-yet-exited `guided_step2_card` (a `card()` - see that
  function's own docstring for why its `.__enter__()`/`.__exit__()` are
  called manually here rather than via a `with` block). `st.rerun()` works
  by raising an exception to abort the script early; doing so before the
  manually-managed card's `.__exit__()` had run meant the `st.container()`
  it wraps was abandoned mid-`with`. This reproduced, almost exactly, a
  previously-documented-and-fixed bug class (see the two `_select_all_
  controls()` bugs further up this file): the main tab strip's own
  active/underline state kept updating correctly on every click, but the
  visible panel content silently stayed frozen on "Geführte Planung" no
  matter which tab was clicked afterwards. Confirmed live with Playwright
  (click "✕", then click the "Dashboard" tab, screenshot the result - the
  tab indicator moved but the Guided Planning content was still showing
  underneath it). Explicit `key=` on the tabs/file uploader - the fix
  applied the FIRST time this bug class appeared - did **not** prevent it
  this time, since the actual cause this time was the abandoned card
  container, not a keyless widget. Fixed by moving the call to
  `_render_selected_items_removal()` to right after `guided_step2_card.
  __exit__(None, None, None)` instead of before it, so `st.rerun()` now
  only ever fires from inside its own real `with st.expander(...)` block
  (whose `__exit__` Python guarantees runs even when an exception/rerun
  propagates through it). Re-verified live afterwards with the exact same
  repro: Dashboard tab now renders Dashboard content correctly after a
  removal. See `_render_selected_items_removal()`'s own docstring in
  `src/app.py` for the full account - worth reading in full before adding
  any FUTURE `st.rerun()` call anywhere in this file, given this is now
  the *second* time an extra rerun mid-interaction has caused this exact
  symptom.
- The Schritt-3 preview grid (`_semester_grid_figure()`) sorted weeks
  latest-first top-to-bottom instead of earliest-first (reported as "KW3
  shows above KW51" for an HS/autumn-semester upload) - traced to an
  `fig.update_yaxes(autorange="reversed")` call. Verified the fix
  empirically two different ways before shipping it: a standalone
  `kaleido`-rendered PNG comparison of a 3-category chart with/without
  `autorange="reversed"` (confirmed Plotly puts the FIRST `category_orders`
  entry at the top by default, and reversing flips that - the opposite of
  what was assumed when the original code was written), then live via
  Playwright against the real app with real semester dates. Also exercised
  non-interactively in `test_app_helpers.py` - see that test's own comment
  for a second surprise hit while writing it: `fig.layout.yaxis.
  categoryarray` itself is stored in the OPPOSITE order from the visual
  top-to-bottom reading order (Plotly's internal bottom-up numeric-axis
  convention), so a test asserting on that attribute has to check its LAST
  element for "renders at the top", not its first - a non-obvious enough
  quirk that it's called out explicitly in both places.
- Two courses overlapping in time landed on the exact same Schritt-3 grid
  cell and silently overplotted each other with no visual sign there were
  two different courses there at all ("Was passiert bei Konflikt?" in the
  original report). Fixed with a black marker outline for any session
  involved in a real `find_time_conflicts()` conflict (on top of, not
  instead of, the red exam outline added in the same round) - verified
  live with two intentionally overlapping test courses.

A 2026-10-12 follow-up round, implementing the first of several UX-research-
backed "quick wins" for Schritt 2's filters (a collapsible filter section
with an active-filter count in its own label, a "🧹 Alle Filter
zurücksetzen" button, and a transparency hint when some of the student's
already-made selection is hidden by the active filters), again found a real
bug only by driving the app live, not by code review:

- **The expander's own label/open-state got stuck one rerun behind after
  clicking "reset".** The first version put the "🧹 Alle Filter
  zurücksetzen" button INSIDE the filter expander, at the top, before the
  individual filter widgets. Clicking it correctly cleared every filter
  widget's session_state (confirmed: the widgets themselves came back
  empty immediately, no `st.rerun()` needed there - see
  `_reset_all_filters()`'s docstring for why that part doesn't need one).
  But the expander's own label text and `expanded=` default are computed
  from `_active_filter_count()` *before* `st.expander(...)` is even
  called - i.e. before the button inside it has had a chance to run. Live
  with Playwright: clicking reset correctly emptied every filter and
  showed "62 Treffer" again, but the expander's title stayed on
  "🔍 Filter (1 aktiv)" instead of reverting to the plain "🔍 Filter" -
  cosmetically wrong, and confusing since it implies a filter is still
  active when none is. Fixed by moving the reset button to run BEFORE
  `active_filter_count`/`expander_label` are computed (and resetting that
  local variable to `0` right in the button's own `if` block) - the same
  "finish touching what a later value depends on before that value is
  computed, same run" principle as the earlier filter-persistence and
  rerun/card-exit fixes in this file, just one step upstream this time.
  Re-verified live afterwards: label correctly reads plain "🔍 Filter"
  immediately after clicking reset, in the same script run.

## Adding new tests

- Match the file that already covers the module you're changing (see the
  table above) rather than creating a new file per feature.
- Prefer the narrow `make_module(**overrides)` style for anything that
  doesn't need a whole realistic file.
- If you're fixing a bug, add a regression test for it in the same
  commit/PR and reference the bug in the test name or a short comment
  (see "Regression tests worth knowing about" above for the expected
  style) - this list should stay accurate as the project evolves.
