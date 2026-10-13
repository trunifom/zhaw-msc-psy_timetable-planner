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

SHOW_RAW_DATA_TAB: bool = True
"""
Whether the "🗄️ Rohdaten" tab (original upload + cleaned/selected data as
plain tables - mainly a transparency/debugging aid, not a planning tool) is
shown at all. Pilot feedback suggested most students never need it day to
day; kept behind this flag rather than deleted since it's still useful when
troubleshooting a specific student's upload. Read by app.py's
`_main_tab_specs()`.
"""
