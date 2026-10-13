"""
Central, single-file feature-flag/settings module for the ZHAW timetable
planner (src/app.py imports this as `import settings`, flat-import style -
same convention as models.py/data_loader.py/scheduler.py/export.py/i18n.py).

Why this file exists: the app is being pilot-tested with several groups of
students, and some UI/UX decisions here are still genuinely open questions
(see docs/UX-OPTIMIERUNGEN-README.md) rather than settled product decisions -
e.g. "should the Rohdaten tab be visible at all", "should charts lead with a
stated takeaway or a plain label". Rather than hunting through the ~6000
lines of app.py for the right `if` to flip before each test round, every
such still-open toggle lives here, in one place, with its default and the
reasoning behind it documented right next to it.

How to use this for a test round: edit the value on the right of a flag
below, save, and restart `streamlit run src/app.py` (a flag is read once per
script rerun - Streamlit already reruns the whole script on every
interaction, so no other restart or cache-clearing is needed). To compare
two versions with two groups of testers, keep two checked-out copies of this
one file (e.g. via git stash/branch) rather than duplicating app.py.

When a question here gets settled (the team picks a winner after testing),
remove the flag and hard-code the chosen behavior directly in app.py instead
of leaving a permanent, never-changed "configuration option" - this file is
for ACTIVE decisions, not a general-purpose config system. See
docs/SETTINGS-README.md for the full list with screenshots/context and the
"what to do once a flag is settled" checklist.
"""

from typing import Literal

# ==========================================
# Feedback
# ==========================================

FEEDBACK_EMAIL: str = "trug@zhaw.ch"
"""
Recipient for the floating feedback widget (mailto: link + QR code, see
app.py's _render_feedback_widget()) - the only address feedback/bug reports
get sent to, no mail server involved. Not tied to the pilot-testing
A/B-toggle purpose of the rest of this file (there is only ever one correct
value), but kept here anyway so every piece of "which single constant do I
change for the next test round / next semester" config lives in one file.
"""

# ==========================================
# Navigation / tabs
# ==========================================

SHOW_RAW_DATA_TAB: bool = False
"""
Whether the "🗄️ Rohdaten" tab (original upload + cleaned/selected data as
plain tables - mainly a transparency/debugging aid, not a planning tool) is
shown at all. Hidden by default (2026-10-13 product decision) - it is
overflow/debugging content that every actual MSc Psychology student can do
without; kept behind this flag rather than deleted since it's still useful
to flip back on when troubleshooting a specific student's upload or during
a future pilot round. Read by app.py's `_main_tab_specs()`.
"""

# ==========================================
# Onboarding / first screen
# ==========================================

SHOW_EXTENDED_QUICKSTART: bool = True
"""
Whether the "🚀 Schnellstart"-Karte at the very top of the app (the first
thing a visitor sees, before any upload) includes three extra lines beyond
its original short purpose/3-step text: an estimated time-to-complete, what
file is needed and where to get it, and an explicit "this is not a course
registration" disclaimer.

`True` (new, extended) follows the GOV.UK Design System's "start page"
pattern (docs/UX-OPTIMIERUNGEN-README.md, Zusatzempfehlung A) - state
roughly how long the task takes and what the visitor needs before they
start, and make unmistakably clear what the tool does NOT do. `False`
reverts to the original, shorter card text only - kept as a flag (rather
than just adding the lines unconditionally) so pilot feedback can compare
"does the extra text actually get read/help, or is it just more to scroll
past" between test groups.
"""

SHOW_STEP_PROGRESS_INDICATOR: bool = True
"""
Whether a compact, named step-progress indicator ("1 Datei hochladen ->
2 Module wählen -> 3 Plan prüfen -> 4 Exportieren") is shown near the top of
the app, right under the Quickstart card. Each stage is marked done/current/
upcoming based on existing session state (file uploaded, modules selected,
planning finalized) - purely an always-visible orientation aid; nothing
about navigation itself is gated by it, a student can still freely jump
between tabs exactly as before.

Follows NN/g "Progress Indicators" guidance (name the steps, don't just
show a percentage) and is the first, additive part of docs/UX-
OPTIMIERUNGEN-README.md's Hauptpunkt 4 - the bigger, riskier part of that
recommendation (collapsing completed steps into an editable one-liner with
a "Change" link, GOV.UK "Check answers"-style) is intentionally NOT part of
this flag; see that doc entry's own status note for what's still open.
"""

# ==========================================
# Appearance
# ==========================================

ThemeDefault = Literal["light", "dark", "auto"]

DEFAULT_THEME: ThemeDefault = "auto"
"""
The theme ("light"/"dark") a first-time visitor sees before ever touching
the sidebar light/dark toggle. The manual toggle itself always remains
available regardless of this setting - this only picks the STARTING point
for a brand-new session.
- "light" / "dark": always start every visitor in that theme (the app's
  original, fixed behavior was "light").
- "auto": try to match the browser/OS's own light/dark preference via
  Streamlit's `st.context.theme.type`, falling back to "light" if that
  signal isn't available yet - a known Streamlit limitation on the very
  first script run of a session (see app._resolve_default_theme()'s
  docstring for the exact fallback rule).

Recommended/default per the UX research behind docs/UX-OPTIMIERUNGEN-
README.md's "Zusatzempfehlung B" (NN/g: users treat dark mode as a
system-wide setting they expect apps to respect, not something to
re-toggle per app).
"""

ChartTitleStyle = Literal["label", "headline"]

CHART_TITLE_STYLE: ChartTitleStyle = "headline"
"""
How the Dashboard's four chart/section headings (Wochentagsverteilung,
Top-Überlappungen, Semesterübersicht, Gesamte Vorlesungsdauer) are worded:
- "label": the original, static, descriptive heading (e.g. "Top-
  Überlappungen pro Modul") - what the section IS.
- "headline" (default): a data-driven one-line takeaway computed for the
  student's CURRENT selection (e.g. "Grösste Überlappung: AS1 (45 Min.)")
  - what the section's data actually SAYS, following "Storytelling with
  Data"/Evergreen's "active title" practice and the GOV.UK Analysis
  Function's "headline + subtitle" chart guidance (docs/UX-OPTIMIERUNGEN-
  README.md, Zusatzempfehlung C). Falls back to the static "label" wording
  automatically whenever no takeaway can be computed yet (e.g. nothing
  dated in the current selection), so a heading never goes blank.

The exact wording for each chart's headline lives in `src/i18n.py` under
the `dashboard.chart.*_headline` keys (one per language) - edit the
TEMPLATE TEXT there; this flag only switches which wording style is used,
it does not need touching to tweak phrasing.
"""

# ==========================================
# Export
# ==========================================

ExportPlacement = Literal["main", "sidebar"]

EXPORT_SECTION_PLACEMENT: ExportPlacement = "main"
"""
Where the Export section (Excel/ICS download buttons, gated behind the
"Planung abgeschlossen" checkbox - that gating logic is unchanged either
way) is shown:
- "main" (default): as its own, clearly visible "4 Exportieren" card in
  the main area, right after the result tabs - the actual payoff moment of
  the whole upload-to-export flow, the same way Calendly treats "add to
  calendar" as the payoff of its scheduling flow (docs/UX-OPTIMIERUNGEN-
  README.md, Hauptpunkt 6).
- "sidebar": the app's original placement, tucked below the upload cards
  in the sidebar - functionally identical, but easy to overlook given it's
  the actual goal of the whole tool.
"""
