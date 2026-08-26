"""
ZHAW MSc Psychology - Timetable Planner (Presentation Layer)
Author: HealthData CodeArchitect
Description: Advanced Streamlit GUI focusing on state-of-the-art UI/UX,
robust error handling, and separation of concerns.

Architecture / role of this file:
    This module is the presentation layer only. It owns all Streamlit widgets,
    page layout, session-state handling and chart/table rendering, but it does
    NOT own business rules such as CSV/Excel parsing, data validation, or
    time-conflict detection - those live in the sibling modules it imports:
      - models.py       domain model (ZHAWModule) and its validation rules
      - data_loader.py  turns an uploaded dataframe into validated ZHAWModule objects
      - scheduler.py    provides find_time_conflicts() (pairwise overlap detection)
      - export.py       builds the Excel/ICS export payloads
      - i18n.py         translation lookup used via the t()/c() helpers below
    Some analysis helpers below (e.g. the "_calculate_*"/"_absence_*" family)
    re-implement small pieces of overlap logic locally for UI-specific summaries
    (tables/charts); see the comments near those functions for how they relate
    to scheduler.find_time_conflicts().

How to run:
    This file uses flat, non-package imports (`from data_loader import ...`,
    not `from src.data_loader import ...`), so it must be launched with the
    `src/` directory as the working/import root:
        streamlit run src/app.py
    Running it as part of a package (e.g. `python -m src.app`) will break the
    imports above.
"""

import streamlit as st
import pandas as pd
import logging
from typing import List, Tuple, Any
from datetime import date, timedelta
from contextlib import contextmanager
import re
import plotly.express as px
from i18n import get_text

# ==========================================
# 0. LOGGING
# ==========================================
# Same self-contained per-module pattern as data_loader.py (a module-owned
# logger + handler, guarded so re-importing/rerunning this script - which
# Streamlit does on every single user interaction - never registers a
# second handler and duplicates every log line).
#
# IMPORTANT for anyone debugging this app: `st.error(...)`/`st.warning(...)`
# calls throughout this file are the *user-facing* half of error reporting
# only. Streamlit does not surface Python's `logging` output in the browser
# UI at all - every `logger.*(...)` call below only ever shows up in the
# terminal/console that `streamlit run src/app.py` is running in. If a user
# reports "I got an error message", the short message they saw is in the
# UI; the full exception/traceback for actually diagnosing it is in that
# terminal's log output (or wherever it's redirected in a deployment), not
# anywhere in the app itself. See README.md "Logging" for details.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_handler)

# Backend modules are imported defensively: if any of them fail to import
# (e.g. a missing dependency, or the app being started from the wrong working
# directory so the flat imports above don't resolve), we don't want a raw
# Python traceback - we want a friendly Streamlit error and a controlled
# st.stop() later in main(). MODULES_AVAILABLE is checked there.
try:
    from data_loader import load_schedule_from_dataframe, DataLoaderError
    from scheduler import find_time_conflicts
    from models import ZHAWModule
    # NEU: Export-Funktionen hier in den Try-Block aufnehmen
    from export import prepare_timetable_for_export, generate_excel_download, generate_ics_download
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    # This is a setup/deployment problem (wrong working directory, missing
    # dependency, ...) rather than something a user caused - always worth a
    # server-side record even though the on-page message already explains
    # it, since whoever redeploys this app is the one who'll need the detail.
    logger.exception("Failed to import backend modules (data_loader/scheduler/models/export).")
    st.error(get_text("de", "system.backend_missing", error=e))


# ==========================================
# 1. PAGE CONFIGURATION & DESIGN SYSTEM
# ==========================================
st.set_page_config(
    page_title=get_text("de", "app.page_title"),
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# `ui_theme` must exist in session_state BEFORE the CSS below is generated
# (the CSS picks colors based on it), but the full init_session_state()
# function is defined further down and only called later in the script.
# This minimal, idempotent bootstrap breaks that chicken-and-egg problem
# without reordering the whole file; init_session_state() re-applies the
# same guarded assignment below for documentation completeness (harmless -
# `if key not in session_state` makes both calls safe together).
if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "dark"

# Keep ui_theme in sync with the sidebar toggle's own widget state BEFORE
# the CSS is generated below. Without this, toggling the theme would look
# like it does nothing for one extra rerun: the toggle's on-click handler
# (in render_sidebar(), which runs much later in the script) is what
# normally writes st.session_state.ui_theme, but this CSS block always
# runs first on every script execution - so on the very rerun the toggle
# is clicked, the CSS would still paint the *previous* theme, and only
# catch up on the *next* unrelated rerun. Streamlit already updates a
# widget's own session_state key (here "sidebar_theme_toggle") from the
# frontend before the script starts running, so reading it directly here -
# instead of waiting for render_sidebar() to translate it into ui_theme -
# makes the switch apply immediately, in the same rerun the user toggled it.
if "sidebar_theme_toggle" in st.session_state:
    st.session_state.ui_theme = "dark" if st.session_state.sidebar_theme_toggle else "light"

# --- Design tokens -----------------------------------------------------
# Single source of truth for every color used in the custom CSS below.
# Two palettes (dark/light) sharing the same token *names* is what makes
# the light/dark toggle possible without touching component-level CSS
# rules - only this dict changes per theme, the rules that reference
# `var(--zp-*)` stay identical. "zp" = ZHAW Planner, used as a namespace
# prefix so these custom properties/classes never collide with Streamlit's
# own CSS variables or a future third-party component's.
THEME_TOKENS: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#0b0d12",
        "surface": "#1a1f2e",
        "surface-hover": "#212739",
        "border": "rgba(255,255,255,0.14)",
        "border-strong": "rgba(255,255,255,0.24)",
        "text": "#eaeef7",
        "text-muted": "#9aa3b8",
        "accent": "#4f8cff",
        "accent-text": "#ffffff",
        "success": "#22c55e",
        "success-bg": "rgba(34,197,94,0.14)",
        "warning": "#eab308",
        "warning-bg": "rgba(234,179,8,0.14)",
        "danger": "#f87171",
        "danger-bg": "rgba(239,68,68,0.16)",
        "info": "#38bdf8",
        "info-bg": "rgba(56,189,248,0.14)",
        "shadow": "0 8px 24px rgba(0,0,0,0.20)",
    },
    "light": {
        "bg": "#f4f5f9",
        "surface": "#ffffff",
        "surface-hover": "#eef0f6",
        "border": "rgba(15,17,23,0.12)",
        "border-strong": "rgba(15,17,23,0.22)",
        "text": "#1b1f2a",
        "text-muted": "#5b6472",
        "accent": "#2f6fed",
        "accent-text": "#ffffff",
        "success": "#15803d",
        "success-bg": "rgba(21,128,61,0.10)",
        "warning": "#a15c07",
        "warning-bg": "rgba(161,92,7,0.10)",
        "danger": "#c0272d",
        "danger-bg": "rgba(192,39,45,0.10)",
        "info": "#0c6faa",
        "info-bg": "rgba(12,111,170,0.10)",
        "shadow": "0 8px 24px rgba(15,17,23,0.10)",
    },
}

# Curated Plotly Express qualitative color sequences offered to the user in
# each chart's "Diagramm-Einstellungen" panel (see render_dashboard). Kept
# as a name -> sequence mapping (rather than exposing raw hex lists in the
# UI) so the selectbox can show a short, translatable label while the
# actual colors stay Plotly's own well-tested, perceptually-distinct sets.
# "colorblind_safe" specifically maps to Plotly's "Safe" set, designed to
# stay distinguishable under the most common forms of color vision
# deficiency - offered explicitly rather than only as an implicit default,
# per this app's accessibility-in-color-coding principle (see also
# _style_absence_rows/_style_risk_rows, which pair color with text/labels
# rather than relying on color alone for the same reason).
CHART_PALETTES: dict[str, list[str]] = {
    "default": px.colors.qualitative.Plotly,
    "pastel": px.colors.qualitative.Pastel,
    "vivid": px.colors.qualitative.Vivid,
    "colorblind_safe": px.colors.qualitative.Safe,
    "dark24": px.colors.qualitative.Dark24,
}

# Continuous scales offered for charts that color by a numeric value
# (currently only the overlap-severity bar chart) rather than by category.
CONTINUOUS_COLOR_SCALES: list[str] = ["Reds", "Oranges", "Blues", "Viridis", "Sunsetdark"]


def _inject_design_system_css() -> None:
    """
    Injects the app-wide design system as CSS custom properties (driven by
    THEME_TOKENS[st.session_state.ui_theme]) plus the component-level rules
    that consume them. Called once per script run, after ui_theme is known.

    Two things this enables beyond the old static dark-only CSS block it
    replaces:
      1. Light/Dark toggle: swapping which token dict is picked is the only
         theme-dependent line here: every rule below reads `var(--zp-*)`,
         so re-running this function after the user flips the sidebar
         theme toggle is enough to restyle the whole app.
      2. A reusable "card" pattern for grouping related content (Gestalt's
         "common region" principle: a shared border/background reads as
         "these things belong together" far more strongly than whitespace
         alone). Any `st.container(border=True, key="zp-card-<name>")` -
         see the `card()` helper below - automatically gets card styling
         via the `[class*="st-key-zp-card-"]` selector, which matches
         Streamlit's documented behavior of adding a `st-key-<key>` CSS
         class to a container created with `key=...`.
    """
    theme = THEME_TOKENS.get(st.session_state.get("ui_theme", "dark"), THEME_TOKENS["dark"])
    css_vars = "\n".join(f"    --zp-{name}: {value};" for name, value in theme.items())

    st.markdown(
        f"""
        <style>
        :root {{
{css_vars}
        }}

        /* --- Base app surface -------------------------------------- */
        .stApp {{
            background: var(--zp-bg);
            color: var(--zp-text);
        }}
        /* Streamlit's own top toolbar (Deploy/menu/"Stop" while running)
           lives in a separate fixed header above .stApp's own background,
           so without this it stays hard-coded white regardless of theme -
           a jarring bright strip at the very top of an otherwise dark page. */
        header[data-testid="stHeader"] {{
            background: var(--zp-bg);
        }}
        section[data-testid="stSidebar"] {{
            background: var(--zp-surface);
            border-right: 1px solid var(--zp-border);
        }}

        /* --- Typography scale ---------------------------------------
           Streamlit's own h1-h3 (from st.title/st.header/st.subheader)
           get a consistent weight/size/color scale here so visual weight
           always matches semantic importance (pre-attentive hierarchy),
           instead of every heading defaulting to the same look. */
        .stApp h1 {{ color: var(--zp-text); font-weight: 800; letter-spacing: -0.01em; }}
        .stApp h2 {{ color: var(--zp-text); font-weight: 700; }}
        .stApp h3 {{ color: var(--zp-text); font-weight: 600; }}
        .stApp p, .stApp label {{ color: var(--zp-text); }}
        .stCaption, [data-testid="stCaptionContainer"] {{ color: var(--zp-text-muted) !important; }}

        /* --- Metrics --------------------------------------------------- */
        .stMetric {{
            background: var(--zp-surface);
            color: var(--zp-text);
            padding: 15px;
            border-radius: 12px;
            border: 1px solid var(--zp-border);
            box-shadow: var(--zp-shadow);
        }}
        .stMetric label, .stMetric [data-testid="stMetricLabel"], .stMetric [data-testid="stMetricDelta"], .stMetric [data-testid="stMetricValue"] {{
            color: var(--zp-text) !important;
        }}

        /* --- Tabs: active tab gets the accent color as an underline,
           making "where am I" unambiguous at a glance. --------------- */
        div[data-testid="stTabs"] button {{
            color: var(--zp-text-muted) !important;
        }}
        div[data-testid="stTabs"] button[aria-selected="true"] {{
            color: var(--zp-text) !important;
            border-bottom: 2px solid var(--zp-accent) !important;
        }}

        .stDataFrame, .stDataEditor {{
            border-radius: 12px;
        }}

        /* --- Card pattern -----------------------------------------------
           See card() helper below: st.container(border=True, key="zp-card-X").
           Streamlit adds a "st-key-zp-card-X" class to the container; the
           substring selector below matches that class regardless of the
           specific card name suffix, so one rule styles every card. */
        div[class*="st-key-zp-card-"] {{
            background: var(--zp-surface) !important;
            border: 1px solid var(--zp-border) !important;
            border-radius: 14px !important;
            box-shadow: var(--zp-shadow);
            padding: 0.25rem 0.25rem 0.5rem 0.25rem;
            margin-bottom: 1rem;
        }}

        /* --- Card header (icon + title + optional subtitle), rendered
           by the card() helper as one consistent block per card. ------ */
        .zp-card-header {{
            display: flex;
            align-items: baseline;
            gap: 0.5rem;
            flex-wrap: wrap;
            padding: 0.5rem 0.75rem 0.75rem 0.75rem;
            margin-bottom: 0.5rem;
            border-bottom: 1px solid var(--zp-border);
        }}
        .zp-card-icon {{ font-size: 1.3rem; line-height: 1; }}
        .zp-card-title {{ font-size: 1.05rem; font-weight: 700; color: var(--zp-text); }}
        .zp-card-subtitle {{ font-size: 0.85rem; color: var(--zp-text-muted); }}

        /* --- Semantic status badges --------------------------------
           Consistent small color-coded pills for OK/warning/danger/info
           states, reused anywhere the app currently shows raw colored
           text (e.g. absence risk, conflict severity, exam status) so
           the same meaning always looks the same everywhere in the app. */
        .zp-badge {{
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            white-space: nowrap;
        }}
        .zp-badge-success {{ background: var(--zp-success-bg); color: var(--zp-success); }}
        .zp-badge-warning {{ background: var(--zp-warning-bg); color: var(--zp-warning); }}
        .zp-badge-danger  {{ background: var(--zp-danger-bg);  color: var(--zp-danger); }}
        .zp-badge-info    {{ background: var(--zp-info-bg);    color: var(--zp-info); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_design_system_css()

# ==========================================
# 2. SESSION STATE INITIALIZATION
# ==========================================
def init_session_state() -> None:
    """
    Initializes default variables in Streamlit's session state.

    Streamlit re-runs this whole script on every widget interaction, so any
    value that needs to persist across reruns (uploaded data, user selections,
    UI language, ...) must live in st.session_state rather than a plain local
    variable. Each key below is only set once (guarded by `not in`), so
    existing values survive reruns; this function is safe to call on every
    script execution.

    Keys initialized here:
      - raw_data: the last uploaded file's data as a raw (untransformed)
        pandas DataFrame, kept around so render_raw_data() can show the
        student what was actually in their upload.
      - processed_modules: List[ZHAWModule] - the full set of validated
        schedule rows produced by data_loader.load_schedule_from_dataframe(),
        i.e. everything from the upload, before any user filtering/selection.
      - conflicts: cached output of scheduler.find_time_conflicts() over
        processed_modules (recomputed on each new upload).
      - planning_finalized: bool gate for render_export_section() - the
        student must explicitly tick a checkbox before downloads unlock
        (see render_export_section for the rationale).
      - selected_modules: List[ZHAWModule] - the subset of processed_modules
        the student has chosen via the guided-planning tab; this is what
        drives the dashboard/timetable/conflicts/export views.
      - filters_initialized: reserved flag for one-time filter-widget setup
        (kept for forward compatibility with guided-planning filter state).
      - selected_course_bases: list of module/course group keys the student
        checked in the guided-planning selection tables, persisted so the
        checkboxes stay selected across reruns (see render_guided_planning).
      - ui_language: current UI language code ("de"/"en"/"fr"), read by
        t()/c() below to resolve translations.
      - ui_theme: current UI color theme ("dark"/"light"), read by
        _inject_design_system_css() (see "1. PAGE CONFIGURATION & DESIGN
        SYSTEM" above) to pick the active THEME_TOKENS palette. Bootstrapped
        even earlier than this function runs (see the note above
        THEME_TOKENS) since the CSS needs it before init_session_state()
        is first called; re-declared here too so this function stays the
        single documented list of every session-state key the app uses.
    """
    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'processed_modules' not in st.session_state:
        st.session_state.processed_modules = []
    if 'conflicts' not in st.session_state:
        st.session_state.conflicts = []
    if 'planning_finalized' not in st.session_state:
        st.session_state.planning_finalized = False
    if 'selected_modules' not in st.session_state:
        st.session_state.selected_modules = []
    if 'filters_initialized' not in st.session_state:
        st.session_state.filters_initialized = False
    if 'selected_course_bases' not in st.session_state:
        st.session_state.selected_course_bases = []
    if 'ui_language' not in st.session_state:
        st.session_state.ui_language = "de"
    if 'ui_theme' not in st.session_state:
        st.session_state.ui_theme = "dark"


def t(key: str, **kwargs: object) -> str:
    """
    Translate a UI label using the current session language, with a German
    (de) fallback baked into i18n.get_text().

    This is the general-purpose i18n entry point for all visible text: page
    titles, button labels, help texts, warnings, etc. `key` is a dotted i18n
    key (e.g. "guided.step1", "export.download_excel"); `**kwargs` are
    forwarded as named placeholders for string formatting (e.g. t("upload.
    dates_missing", count=3)). See docs/i18n-README.md for the full key
    naming/placeholder conventions and how to add a new language.
    """
    return get_text(st.session_state.get("ui_language", "de"), key, **kwargs)


def c(key: str) -> str:
    """
    Shortcut for dataframe/table column labels: translates "col.<key>" via
    t(). Used everywhere a pandas DataFrame column name is built (e.g.
    c("weekday") -> t("col.weekday")), so that column headers shown in
    st.dataframe()/st.data_editor() respect the selected UI language just
    like any other label. See docs/i18n-README.md ("col.*" namespace).
    """
    return t(f"col.{key}")

init_session_state()


@contextmanager
def card(key: str, icon: str = "", title: str = "", subtitle: str = ""):
    """
    Design-system building block: a bordered "card" section with an
    optional icon+title+subtitle header, styled by the CSS rules in
    _inject_design_system_css() above (Gestalt "common region" grouping -
    see that function's docstring). Use as:

        with card("dashboard-metrics", "📊", t("dashboard.section.metrics")):
            st.metric(...)
            ...

    `key` must be unique per card *on the page it's used on* and should not
    include the "zp-card-" prefix (added here) - it becomes part of a CSS
    class name, so keep it to ASCII letters/digits/hyphens. Passing an
    empty `title` renders the card with no header row at all (just the
    bordered container), for cases where the surrounding code already
    provides its own heading.

    Gotcha when migrating an old `st.markdown(t("..."))` section header into
    a card title: several i18n strings (originally written for direct
    `st.markdown()` calls, which parse markdown) still have a literal
    "**...**" baked into the translated text for bolding. `title` here is
    inserted as plain text inside an HTML <span> (see below), NOT run
    through markdown, so passing one of those strings unmodified renders
    the literal asterisks on screen - call `.strip("*")` on the translation
    first (see the guided-planning/conflicts/raw-data card() calls in this
    file for the pattern). This bit the "Wichtige Kennzahlen" dashboard
    card during development; grep this file for `.strip("*")` before adding
    a new card title to see whether the key you're using needs it too.
    """
    with st.container(border=True, key=f"zp-card-{key}"):
        if title:
            subtitle_html = f'<span class="zp-card-subtitle">{subtitle}</span>' if subtitle else ""
            st.markdown(
                f'<div class="zp-card-header">'
                f'<span class="zp-card-icon">{icon}</span>'
                f'<span class="zp-card-title">{title}</span>'
                f'{subtitle_html}'
                f'</div>',
                unsafe_allow_html=True,
            )
        yield


def badge(text: str, kind: str = "info") -> str:
    """
    Return an HTML snippet for a small color-coded status pill (see the
    .zp-badge* CSS rules in _inject_design_system_css()). `kind` is one of
    "success"/"warning"/"danger"/"info" and maps to the matching semantic
    color token - callers must still pass a `text` that also conveys the
    status in words (e.g. "OK"/"Risiko"), since color alone must never be
    the only signal (see this app's color-accessibility principle, also
    applied in _style_absence_rows/_style_risk_rows). Must be rendered with
    st.markdown(..., unsafe_allow_html=True) by the caller.
    """
    safe_kind = kind if kind in {"success", "warning", "danger", "info"} else "info"
    return f'<span class="zp-badge zp-badge-{safe_kind}">{text}</span>'


def _apply_chart_theme(fig):
    """
    Apply the app's current color theme to a Plotly figure and return it
    (for easy `return _apply_chart_theme(fig)` one-liners).

    Plotly Express figures default to an opaque *white* paper/plot
    background regardless of the surrounding page - every chart in this
    app used to render as a stark white rectangle punched into the
    dark-themed layout (or, after the light theme was added, into a
    mismatched off-white in light mode). Every `_..._figure()` builder and
    every inline px.* chart call in this file routes its figure through
    this function before handing it to st.plotly_chart(), so:
      - paper/plot background become fully transparent, letting the
        surrounding card's own background (see the card() helper) show
        through seamlessly instead of fighting it, and
      - axis/legend/hover text and gridlines switch to the active theme's
        colors, so they stay legible in both dark and light mode.
    This is intentionally applied globally (every chart, not just the
    Dashboard tab's) because a mismatched chart background is a base
    theming concern, not tab-specific content - leaving it unfixed on
    other tabs would undermine the one-consistent-look-across-the-app goal
    even though those tabs' charts aren't otherwise part of this pass.
    """
    theme = THEME_TOKENS.get(st.session_state.get("ui_theme", "dark"), THEME_TOKENS["dark"])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=theme["text"],
        legend=dict(font_color=theme["text"]),
        xaxis=dict(gridcolor=theme["border"], zerolinecolor=theme["border"], linecolor=theme["border"]),
        yaxis=dict(gridcolor=theme["border"], zerolinecolor=theme["border"], linecolor=theme["border"]),
    )
    return fig


# ==========================================
# 3. HELPER FUNCTIONS (UI LOGIC)
# ==========================================
def _format_user_facing_error(exc: Exception) -> str:
    """
    Turn a caught exception into a short, non-technical string suitable for
    st.error(..., error=...) interpolation.

    Most exceptions this app catches already carry a clean, hand-written
    message (DataLoaderError/MissingColumnError from data_loader.py, or a
    plain pandas parser error) - `str(exc)` is fine for those as-is. The one
    exception (pun intended) is `pydantic.ValidationError`: its default
    `str()` is a multi-line technical dump per failed field, complete with a
    "For further information visit https://errors.pydantic.dev/..." link -
    informative for a developer, intimidating for a student who just wants
    to know their Excel file has a typo. When one of those reaches here
    (they generally shouldn't - data_loader.load_schedule_from_dataframe()
    catches per-row ValidationErrors internally - but pandas' own CSV/Excel
    parsers can also raise ValueError subclasses that land in the same
    `except ValueError` branch as a real ValidationError would), this
    condenses it to one "field: message" line per problem instead.
    """
    errors_method = getattr(exc, "errors", None)
    if callable(errors_method):
        try:
            details = errors_method()
        except Exception:
            details = None
        if details:
            lines = [f"{'.'.join(str(p) for p in d.get('loc', ())) or '?'}: {d.get('msg', '')}" for d in details]
            return "; ".join(lines)
    return str(exc)


def handle_file_upload(uploaded_file: Any) -> None:
    """
    Handles the parsing of the uploaded file with comprehensive error handling.
    Supports CSV and Excel files.

    Side effects (all on success): populates st.session_state.raw_data,
    processed_modules and conflicts, resets selected_modules/
    selected_course_bases (a new upload invalidates any prior selection made
    against the old dataset), and shows a success toast. On failure it
    renders an st.error()/st.info() and leaves session state untouched.

    CSV vs. Excel handling differs deliberately:
      - CSV: there is exactly one "sheet" and pandas' default header=0
        parsing is used directly - real ZHAW CSV exports are expected to
        have a clean header row as the first line.
      - Excel: real ZHAW Excel exports are inconsistent - the actual
        timetable can live on any sheet (not necessarily the first), and
        that sheet can have several metadata/banner rows above the real
        header row (e.g. a title, an export timestamp). To cope with this
        without hard-coding assumptions, every sheet is read with
        header=None (so nothing is assumed to be a header yet) and handed to
        load_schedule_from_dataframe(), which internally scans the first
        rows to locate and promote the real header
        (see data_loader._try_reheader_from_rows). We keep trying sheets
        until one of them parses successfully into the required schema, and
        use the first one that works. If none of them parse, we surface the
        last error we saw (or a generic "no matching sheet" error).
    """
    try:
        # Determine file type and parse accordingly
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            st.session_state.raw_data = df
            st.session_state.processed_modules = load_schedule_from_dataframe(df)
            st.session_state.conflicts = find_time_conflicts(st.session_state.processed_modules)
            st.session_state.selected_modules = []
            st.session_state.selected_course_bases = []
            st.toast(t("upload.success"), icon="✅")
            _warn_if_dates_missing(st.session_state.processed_modules)
            return
        elif uploaded_file.name.endswith(('.xls', '.xlsx')):
            xls = pd.ExcelFile(uploaded_file)
            last_error: Exception | None = None

            # Try every sheet in order, header=None so data_loader can locate
            # the real header row itself (see docstring above). We stop at
            # the first sheet that yields a valid schedule.
            for sheet_name in xls.sheet_names:
                candidate_df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                if candidate_df.empty:
                    continue

                try:
                    processed_modules = load_schedule_from_dataframe(candidate_df)
                except Exception as err:
                    # This sheet didn't contain a valid schedule (e.g. it's a
                    # notes/legend sheet) - remember the error in case ALL
                    # sheets fail, but keep trying the remaining sheets. INFO
                    # (not WARNING/ERROR): a non-matching sheet in a
                    # multi-sheet workbook is expected, normal behavior, not
                    # a problem in itself - only worth escalating if *every*
                    # sheet fails (see the "raise last_error" below).
                    logger.info(f"Sheet '{sheet_name}' did not contain a valid schedule: {err}")
                    last_error = err
                    continue

                st.session_state.raw_data = candidate_df
                st.session_state.processed_modules = processed_modules
                st.session_state.conflicts = find_time_conflicts(st.session_state.processed_modules)
                st.session_state.selected_modules = []
                st.session_state.selected_course_bases = []
                st.toast(t("upload.success_sheet", sheet_name=sheet_name), icon="✅")
                _warn_if_dates_missing(st.session_state.processed_modules)
                return

            # No sheet could be parsed into the required schema.
            if last_error is not None:
                raise last_error
            raise DataLoaderError(t("upload.no_sheet"))
        else:
            st.error(t("upload.unsupported"))
            return

    except ValueError as ve:
        # Catches both a raw pandas parser error (e.g. a malformed CSV -
        # pandas.errors.ParserError subclasses ValueError) and, in principle,
        # a pydantic.ValidationError that escaped data_loader (it also
        # subclasses ValueError) - though the latter shouldn't normally
        # happen since load_schedule_from_dataframe() already catches
        # per-row ValidationErrors itself. WARNING, not ERROR: this is a
        # data-quality problem in the *user's* file, not an app bug - but
        # still worth a server-side record in case the same file keeps
        # coming back as a support question.
        logger.warning(f"Upload rejected due to a data validation error: {ve}")
        st.error(t("upload.validation_error", error=_format_user_facing_error(ve)))
        st.info(t("upload.validation_hint"))
    except Exception as e:
        # Catch unforeseen errors (e.g., corrupted file). Unlike the
        # ValueError branch above, this is by definition a case we didn't
        # anticipate, so logger.exception() (full traceback, not just the
        # message) is what actually gives a developer a chance to diagnose
        # it - the short message shown in the UI alone rarely does.
        logger.exception("Unexpected error while processing an uploaded file.")
        st.error(t("upload.unexpected_error", error=_format_user_facing_error(e)))


def _warn_if_dates_missing(modules: List) -> None:
    """Surface a visible warning if rows lost their date during import (each row is expected to carry one)."""
    missing = sum(1 for m in modules if getattr(m, "datum", None) is None)
    if missing:
        st.warning(t("upload.dates_missing", count=missing))


def render_export_section(modules: List) -> None:
    """
    Renders the download button and handles the export logic pipeline.
    Transforms module objects to dataframe, then serializes to Excel.

    UX note - the "planning finalized" gate:
    Export (Excel + ICS download buttons) is deliberately locked behind the
    `planning_finalized` checkbox below rather than being available as soon
    as any module is selected. This is intentional: a student may still be
    experimenting with the guided-planning filters/selection, and exporting
    a half-finished, still-changing selection invites confusion (stale
    files, wrong ECTS totals, etc.). Requiring an explicit checkbox forces a
    conscious "yes, this is my final selection" confirmation before any file
    is generated/downloaded, rather than silently offering a download of
    whatever happens to be selected at the moment.
    """
    if not modules:
        return  # Nichts anzeigen, wenn noch keine Daten da sind

    st.subheader(t("export.subheader"))

    st.session_state.planning_finalized = st.checkbox(
        t("export.finalize_checkbox"),
        value=st.session_state.planning_finalized,
        help=t("export.finalize_help"),
    )

    if not st.session_state.planning_finalized:
        st.info(t("export.locked_info"))
        return

    try:
        with st.spinner(t("export.spinner")):
            # 1. Daten über die Business-Logik (export.py) transformieren
            export_data = prepare_timetable_for_export(modules)
            
            # 2. Binären Excel-Stream generieren
            excel_bytes = generate_excel_download(export_data)
            semester_start, _semester_end = _semester_date_bounds(
                st.session_state.get("processed_modules") or modules
            )
            ics_bytes = generate_ics_download(
                modules,
                calendar_name=t("export.calendar_name"),
                fallback_date=semester_start,
            )

            # 3. Streamlit Download-Widget rendern
            st.download_button(
                label=t("export.download_excel"),
                data=excel_bytes,
                file_name="ZHAW_Planner_Export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help=t("export.download_excel_help")
            )

            st.download_button(
                label=t("export.download_ics"),
                data=ics_bytes,
                file_name="ZHAW_Planner_Export.ics",
                mime="text/calendar",
                help=t("export.download_ics_help"),
            )

            modules_without_date = sum(1 for m in modules if getattr(m, "datum", None) is None)
            st.caption(t("export.ics_summary", count=len(modules)))
            if modules_without_date:
                st.warning(t("export.ics_missing_dates", count=modules_without_date))
    except Exception as e:
        # A failure here means a student's finalized selection can't be
        # downloaded at all - always unexpected (the export functions are
        # meant to handle any valid module list) and worth a full traceback,
        # not just the message, to actually track down.
        logger.exception(f"Export failed for {len(modules)} selected module(s).")
        st.error(t("export.error", error=_format_user_facing_error(e)))


def _weekday_label(module: Any) -> str:
    """Return the localized, display-ready weekday name for a module row
    (e.g. "Montag"/"Monday"/"Lundi" depending on ui_language). Falls back to
    a capitalized raw value if no translation exists for that key."""
    value = getattr(module.wochentag, "value", module.wochentag)
    normalized = str(value).strip().lower()
    translated = t(f"weekday.{normalized}")
    if translated.startswith("weekday."):
        return str(value).capitalize()
    return translated


def _weekday_key(module: Any) -> str:
    """Return canonical weekday key (language independent)."""
    value = getattr(module.wochentag, "value", module.wochentag)
    return str(value).strip().lower()


def _weekday_labels_in_order() -> list[str]:
    """Localized weekday labels in Monday-first chronological order; used as
    the category_orders/axis order for charts and filter widgets so weekdays
    never appear alphabetically sorted."""
    return [
        t("weekday.montag"),
        t("weekday.dienstag"),
        t("weekday.mittwoch"),
        t("weekday.donnerstag"),
        t("weekday.freitag"),
        t("weekday.samstag"),
        t("weekday.sonntag"),
    ]


def _weekday_keys_in_order() -> list[str]:
    """Canonical (language-independent) weekday keys, Monday-first - the
    counterpart to _weekday_labels_in_order() used wherever code needs a
    stable key rather than a translated label (e.g. session-state storage,
    index lookups)."""
    return ["montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag"]


def _blocking_weekday_labels() -> list[str]:
    """Weekdays shown in the blocked-days selector; weekends remain supported internally."""
    return _weekday_labels_in_order()[:5]


def _blocking_weekday_keys() -> list[str]:
    """Weekday keys shown in blocked-days selector; weekends remain supported internally."""
    return _weekday_keys_in_order()[:5]


def _semester_date_bounds(modules: List[Any]) -> tuple[date | None, date | None]:
    """Return (earliest, latest) date among all dated schedule rows.
    Used to bound date_input widgets (so students can't pick an absence date
    outside the actual semester) and as a fallback date for export. Rows
    without a concrete date (getattr(m, "datum", None) is None - e.g.
    recurring weekly slots with no fixed calendar date) are ignored; returns
    (None, None) if no row has a date at all."""
    dates = sorted({m.datum for m in modules if getattr(m, "datum", None) is not None})
    if not dates:
        return (None, None)
    return (dates[0], dates[-1])


def _default_absence_end(start_value: date, max_value: date | None) -> date:
    """Prefer the following day as default end date, capped by semester max date."""
    candidate = start_value + timedelta(days=1)
    if max_value is not None and candidate > max_value:
        return max_value
    return candidate


def _absence_settings() -> dict[str, Any]:
    """
    Read and normalize the guided-planning absence widgets' raw session-state
    values into one structured dict consumed by all the "_absence_*" helpers
    below (_absence_rules_summary, _absence_reasons_for_module, etc.).

    This app supports three independent, optionally-combined ways a student
    can declare "I am not available" (all set via widgets in
    render_guided_planning's step 1, see the "q_absence_period" /
    "q_absent_dates" / "q_blocked_days" radios):
      - period: a single contiguous absence date range (e.g. vacation),
        keys "period_enabled"/"period_start"/"period_end".
      - dates: an explicit set of individual absence dates (e.g. medical
        appointments), keys "dates_enabled"/"dates".
      - blocked_days: recurring weekly unavailability, e.g. "never on
        Wednesdays" or "never on Wednesday afternoons", keys
        "blocked_enabled"/"blocked_days"/"blocked_halfday".
    Any subset of these can be active at once; each rule is evaluated
    independently in _absence_reasons_for_module() and their hits are unioned.

    The blocked-days normalization loop below is needed because the
    multiselect widget's stored values may be either canonical weekday keys
    ("montag") or already-translated labels (depending on widget history/
    language switches); we accept both and always normalize to canonical
    lowercase keys so downstream comparisons (_weekday_key()) are reliable
    regardless of the current UI language.
    """
    raw_blocked_days = st.session_state.get("absence_blocked_days_values", []) or []
    normalized_blocked_days: set[str] = set()
    for day in raw_blocked_days:
        token = str(day).strip().lower()
        if token in _weekday_keys_in_order():
            normalized_blocked_days.add(token)
            continue
        for key in _weekday_keys_in_order():
            if token == t(f"weekday.{key}").strip().lower():
                normalized_blocked_days.add(key)
                break

    return {
        "period_enabled": bool(st.session_state.get("absence_period_enabled", False)),
        "period_start": st.session_state.get("absence_period_start"),
        "period_end": st.session_state.get("absence_period_end"),
        "dates_enabled": bool(st.session_state.get("absence_dates_enabled", False)),
        "dates": set(st.session_state.get("absence_dates_values", []) or []),
        "blocked_enabled": bool(st.session_state.get("absence_blocked_enabled", False)),
        "blocked_days": normalized_blocked_days,
        "blocked_halfday": st.session_state.get("absence_blocked_halfday_value", t("guided.full_day")),
    }


def _absence_rules_summary(settings: dict[str, Any]) -> list[str]:
    """Human-readable summary of active absence constraints."""
    rules: list[str] = []

    if settings["period_enabled"] and settings["period_start"] and settings["period_end"]:
        rules.append(
            t(
                "dashboard.absence.period",
                start=settings["period_start"].strftime("%d.%m.%Y"),
                end=settings["period_end"].strftime("%d.%m.%Y"),
            )
        )

    if settings["dates_enabled"] and settings["dates"]:
        sorted_dates = sorted(settings["dates"])
        shown = ", ".join(d.strftime("%d.%m.%Y") for d in sorted_dates[:5])
        suffix = " ..." if len(sorted_dates) > 5 else ""
        rules.append(t("dashboard.absence.dates", dates=f"{shown}{suffix}"))

    if settings["blocked_enabled"] and settings["blocked_days"]:
        days = ", ".join(t(f"weekday.{d}") for d in sorted(settings["blocked_days"]))
        rules.append(
            t(
                "dashboard.absence.blocked_days",
                days=days,
                halfday=settings["blocked_halfday"],
            )
        )

    return rules


def _absence_reasons_for_module(module: Any, settings: dict[str, Any]) -> list[str]:
    """
    Return all matching absence reasons for a single module row, i.e. every
    active absence rule (from _absence_settings()) that this row violates.
    A row can match zero, one, or several reasons at once (e.g. it falls
    inside a blocked absence period AND on a recurring blocked weekday); an
    empty list means the row is unaffected by any absence rule. This is the
    single source of truth other helpers build on: _absence_conflict_dataframe
    calls it per-row to decide which rows to list, and
    _absence_course_impact_dataframe uses "has any reason" as its per-row
    impact flag.
    """
    reasons: list[str] = []
    datum_value = getattr(module, "datum", None)
    day_key = _weekday_key(module)

    if settings["period_enabled"] and settings["period_start"] and settings["period_end"] and datum_value is not None:
        if settings["period_start"] <= datum_value <= settings["period_end"]:
            reasons.append(t("absence.reason.period"))

    if settings["dates_enabled"] and datum_value in settings["dates"]:
        reasons.append(t("absence.reason.date"))

    if settings["blocked_enabled"] and day_key in settings["blocked_days"] and _matches_halfday(module, settings["blocked_halfday"]):
        reasons.append(t("absence.reason.weekday_halfday", halfday=settings["blocked_halfday"]))

    return reasons


def _absence_conflict_dataframe(modules: List[Any], settings: dict[str, Any]) -> pd.DataFrame:
    """Build a flat table (one row per affected module occurrence) listing
    every module that violates at least one active absence constraint, with
    a human-readable, comma-joined list of the matching reason(s). Rows with
    no matching reason are omitted entirely - this dataframe is meant to be
    read as "here's what you need to look at", not a full listing."""
    if not modules:
        return pd.DataFrame()

    rows = []
    for module in modules:
        reasons = _absence_reasons_for_module(module, settings)
        if not reasons:
            continue
        rows.append(
            {
                c("date"): _conflict_date_label(module),
                c("weekday"): _weekday_label(module),
                c("module"): _module_label(module),
                c("time"): f"{module.startzeit.strftime('%H:%M')} - {module.endzeit.strftime('%H:%M')}",
                c("reason"): ", ".join(reasons),
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values([c("date"), c("weekday"), c("time")], ascending=[True, True, True])


def _absence_course_impact_dataframe(modules: List[Any], settings: dict[str, Any]) -> pd.DataFrame:
    """
    Summarize absence impact per base course (grouped by _module_group_title,
    i.e. Modul-Nr where available) and flag a risk status against each
    course's mandatory-attendance requirement.

    Risk computation:
      - `attendance_req_pct` (col c("attendance_req_pct")) comes from the
        source data's `anwesenheitspflicht_prozent` field (e.g. "80" means
        the student must attend at least 80% of that course's sessions).
        Not every course specifies this - if it's missing, risk stays
        "unknown" because we simply have no threshold to compare against.
      - `allowed_absence_pct` = 100 - attendance_req_pct, i.e. the maximum
        share of sessions the student is permitted to miss while still
        satisfying the requirement.
      - `absence_pct` = (rows hit by an active absence rule) / (total rows
        for that course) * 100, i.e. what fraction of this course's
        sessions the student's current absence settings would actually make
        them miss.
      - risk_status is "high" when absence_pct exceeds allowed_absence_pct
        (the student is on track to violate the attendance requirement),
        "ok" when it's within the allowed budget, and "unknown" when no
        requirement percentage was available to compare against at all.
    """
    if not modules:
        return pd.DataFrame()

    totals: dict[str, dict[str, Any]] = {}
    for module in modules:
        key = _module_group_title(module)
        if key not in totals:
            totals[key] = {
                c("base_course"): key,
                c("rows"): 0,
                c("absence_rows"): 0,
                c("absence_pct"): 0.0,
                c("attendance_req_pct"): None,
                c("allowed_absence_pct"): None,
                c("risk_status"): t("absence.risk.unknown"),
            }

        totals[key][c("rows")] += 1
        if _absence_reasons_for_module(module, settings):
            totals[key][c("absence_rows")] += 1

        raw_req = getattr(module, "anwesenheitspflicht_prozent", None)
        if raw_req is not None and totals[key][c("attendance_req_pct")] is None:
            try:
                totals[key][c("attendance_req_pct")] = float(raw_req)
            except Exception:
                pass

    rows = []
    for row in totals.values():
        total = max(1, int(row[c("rows")]))
        impacted = int(row[c("absence_rows")])
        absence_pct = round((impacted / total) * 100.0, 1)
        row[c("absence_pct")] = absence_pct

        req = row[c("attendance_req_pct")]
        if req is None:
            row[c("allowed_absence_pct")] = None
            row[c("risk_status")] = t("absence.risk.unknown")
        else:
            allowed = max(0.0, min(100.0, 100.0 - float(req)))
            row[c("allowed_absence_pct")] = round(allowed, 1)
            row[c("risk_status")] = t("absence.risk.high") if absence_pct > allowed else t("absence.risk.ok")

        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values([c("absence_pct"), c("absence_rows"), c("base_course")], ascending=[False, False, True])


# Semantic row-tint colors for pandas Styler output, expressed as the same
# CSS custom properties _inject_design_system_css() defines on :root (see
# THEME_TOKENS). Browsers resolve var(...) inside an inline style="..."
# attribute too (which is what df.style.apply(...) below produces), so
# these tints automatically follow the active light/dark theme instead of
# being pinned to whichever theme they were originally tuned against - the
# same "success"/"warning"/"danger"/"info" vocabulary as badge() below,
# just for whole table rows instead of a single inline pill.
_ROW_TONE_COLORS = {
    "success": "var(--zp-success-bg)",
    "warning": "var(--zp-warning-bg)",
    "danger": "var(--zp-danger-bg)",
    "info": "var(--zp-info-bg)",
}


def _style_status_column(df: pd.DataFrame, status_col: str, tone_map: dict[str, str]) -> Any:
    """
    Tint every row's background according to one column's (already-
    localized) status text, using the app's semantic status tones.

    `tone_map` maps the exact, localized cell values that can appear in
    `status_col` to one of "success"/"warning"/"danger"/"info" (see
    _ROW_TONE_COLORS); any value not present in `tone_map` (including "")
    gets no styling rather than raising. This is the reusable, whole-row
    counterpart to badge() - built once here so every status-bearing table
    in the app (guided-planning module status, exam feasibility, ...) gets
    the same color treatment instead of each call site reinventing it.
    """
    def _row_style(row: pd.Series) -> list[str]:
        tone = tone_map.get(str(row.get(status_col, "")))
        color = _ROW_TONE_COLORS.get(tone)
        return [f"background-color: {color}" if color else ""] * len(row)

    return df.style.apply(_row_style, axis=1)


# Matches matplotlib's "Reds" colormap endpoints (very light pink -> deep
# red) closely enough for a severity ramp, without actually depending on
# matplotlib - see _style_sequential_red() below for why that matters.
_RED_RAMP_LOW = (255, 245, 240)
_RED_RAMP_HIGH = (103, 0, 13)


def _style_sequential_red(df: pd.DataFrame, value_col: str) -> Any:
    """
    Tint one column's cell backgrounds with a red intensity proportional to
    that cell's value (linearly normalized across the column's own min..max,
    same idea as a heatmap) - a sequential "how severe is this" encoding,
    matching the color language _apply_chart_theme() already uses for the
    equivalent charts (continuous "Reds" scale = higher number = worse).

    This exists as a dependency-free replacement for pandas' built-in
    `Styler.background_gradient(cmap="Reds")`: that method requires
    matplotlib to resolve the named colormap, which is NOT a dependency of
    this project (not in requirements.txt/environment.yaml) - calling it
    raises `ImportError: background_gradient requires matplotlib.` the
    first time a student's data actually reaches a table using it, not at
    import time, so this was a real, previously-shipped, latent crash
    (see docs/TESTING-README.md's regression-test notes) rather than a
    theoretical concern. Every other Styler helper in this file
    (_style_absence_rows, _style_risk_rows, _style_status_column) already
    only emits plain CSS strings for exactly this reason.
    """
    values = df[value_col].astype(float)
    vmin, vmax = values.min(), values.max()
    span = (vmax - vmin) or 1.0  # avoid a division by zero when every value is identical

    def _cell_color(value: Any) -> str:
        ratio = max(0.0, min(1.0, (float(value) - vmin) / span))
        r = round(_RED_RAMP_LOW[0] + ratio * (_RED_RAMP_HIGH[0] - _RED_RAMP_LOW[0]))
        g = round(_RED_RAMP_LOW[1] + ratio * (_RED_RAMP_HIGH[1] - _RED_RAMP_LOW[1]))
        b = round(_RED_RAMP_LOW[2] + ratio * (_RED_RAMP_HIGH[2] - _RED_RAMP_LOW[2]))
        # The ramp's dark-red end is too dark for default (dark) cell text
        # to stay readable against - switch to white past the midpoint,
        # same "flip label color over a dark fill" rule any heatmap needs.
        text_color = "white" if ratio > 0.5 else "black"
        return f"background-color: rgb({r}, {g}, {b}); color: {text_color}"

    return df.style.map(_cell_color, subset=[value_col])


def _style_absence_rows(df: pd.DataFrame, reason_col: str) -> Any:
    """Style rows to highlight absence-related violations."""
    def _row_style(row: pd.Series) -> list[str]:
        has_reason = bool(str(row.get(reason_col, "")).strip())
        if has_reason:
            return [f"background-color: {_ROW_TONE_COLORS['danger']}"] * len(row)
        return [""] * len(row)

    return df.style.apply(_row_style, axis=1)


def _style_risk_rows(df: pd.DataFrame) -> Any:
    """Style course impact table by risk status."""
    status_col = c("risk_status")

    def _row_style(row: pd.Series) -> list[str]:
        status = str(row.get(status_col, ""))
        if status == t("absence.risk.high"):
            return [f"background-color: {_ROW_TONE_COLORS['danger']}"] * len(row)
        if status == t("absence.risk.ok"):
            return [f"background-color: {_ROW_TONE_COLORS['success']}"] * len(row)
        return [f"background-color: {_ROW_TONE_COLORS['warning']}"] * len(row)

    return df.style.apply(_row_style, axis=1)


def _absence_overlay_for_week(settings: dict[str, Any]) -> pd.DataFrame:
    """Build synthetic "blocked" bar rows (not real modules) to overlay onto
    the weekly Gantt chart (_weekly_timeline_figure), so recurring blocked
    weekdays/half-days are visible directly on the timetable rather than
    only in a separate text summary. Returns an empty dataframe when the
    blocked-days rule is inactive or empty - nothing to overlay."""
    if not settings.get("blocked_enabled") or not settings.get("blocked_days"):
        return pd.DataFrame()

    # Map the selected half-day option to a wall-clock time range for the
    # overlay bar; "full day" spans midnight-to-midnight (23:59 as a
    # practical end-of-day stand-in).
    halfday = settings.get("blocked_halfday", t("guided.full_day"))
    if halfday == t("guided.morning"):
        start = "00:00:00"
        end = "12:00:00"
    elif halfday == t("guided.afternoon"):
        start = "12:00:00"
        end = "23:59:00"
    else:
        start = "00:00:00"
        end = "23:59:00"

    rows = []
    for day_key in sorted(settings.get("blocked_days", []), key=lambda d: _weekday_keys_in_order().index(d) if d in _weekday_keys_in_order() else 99):
        rows.append(
            {
                c("weekday"): t(f"weekday.{day_key}"),
                c("module"): t("timetable.absence_overlay_label"),
                # 1970-01-01 dummy date: Plotly's px.timeline() (a Gantt chart)
                # requires real datetimes for x_start/x_end, but this chart
                # only cares about time-of-day, not a calendar date. Anchoring
                # every bar to the same arbitrary date makes all rows land on
                # a shared, comparable time-of-day x-axis. Must match the
                # dummy date used for real module rows in
                # _weekly_timeline_figure() so the overlay aligns correctly
                # when concatenated with them.
                c("start"): pd.to_datetime(f"1970-01-01 {start}"),
                c("end"): pd.to_datetime(f"1970-01-01 {end}"),
                c("type"): t("timetable.absence_overlay_type"),
            }
        )
    return pd.DataFrame(rows)


def _lessons_per_week(modules: List[Any]) -> tuple[float, float, int]:
    """
    Estimate a representative weekly teaching load, expressed both as
    "lessons" (45-minute academic units, the standard Swiss/ZHAW lesson
    length) and as hours. Returns (lessons_per_week, hours_per_week,
    observed_weeks).

    The schedule mixes two kinds of rows: recurring rows with no fixed
    `datum` (they repeat every week, e.g. a weekly seminar slot) and dated
    rows tied to a specific calendar date (e.g. a one-off workshop day).
    These can't just be summed and divided by the number of calendar weeks,
    because recurring rows contribute their full duration to *every* week
    while dated rows only contribute to the specific week they fall in. So:
      - undated_minutes: summed once, since a recurring row's load repeats
        identically every week.
      - dated rows: grouped by ISO (year, week) and averaged, giving the
        *typical* additional per-week load contributed by one-off dated
        events across the whole observed period.
    total_week_minutes is then the recurring load plus that average dated
    load, giving a representative single "typical week" figure rather than
    a simple grand total. observed_weeks is returned for transparency, so
    the UI can caption "based on N weeks with dated sessions".
    """
    if not modules:
        return (0.0, 0.0, 0)

    undated_minutes = sum(m.duration_minutes for m in modules if getattr(m, "datum", None) is None)

    dated_rows = []
    for module in modules:
        datum_value = getattr(module, "datum", None)
        if datum_value is None:
            continue
        iso = datum_value.isocalendar()
        dated_rows.append({"year": iso.year, "week": iso.week, "minutes": module.duration_minutes})

    avg_dated_week_minutes = 0.0
    observed_weeks = 0
    if dated_rows:
        dated_df = pd.DataFrame(dated_rows)
        weekly = dated_df.groupby(["year", "week"], as_index=False)["minutes"].sum()
        avg_dated_week_minutes = float(weekly["minutes"].mean())
        observed_weeks = int(len(weekly))

    total_week_minutes = undated_minutes + avg_dated_week_minutes
    lessons = round(total_week_minutes / 45.0, 1)
    hours = round(total_week_minutes / 60.0, 1)
    return (lessons, hours, observed_weeks)


def _matches_halfday(module: Any, halfday: str) -> bool:
    """Check whether a module's start time falls within the given half-day
    window ("full day" always matches; "morning" is before 12:00, "afternoon"
    is 12:00 or later). Used by the blocked-weekday absence rule to decide
    whether a specific occurrence is actually blocked."""
    start_hour = module.startzeit.hour
    if halfday == t("guided.full_day"):
        return True
    if halfday == t("guided.morning"):
        return start_hour < 12
    if halfday == t("guided.afternoon"):
        return start_hour >= 12
    return False


def _module_to_row(module: Any, module_id: int, selected: bool) -> dict:
    """Build one localized dict/row for the row-level selection table in
    render_guided_planning's "row" selection mode (st.data_editor with a
    checkbox column). `module_id` is the row's position in the full
    all_modules list, used later to map checked rows back to module objects."""
    datum_value = getattr(module, "datum", None)
    return {
        c("select"): selected,
        c("id"): module_id,
        c("module_no"): getattr(module, "modul_nr", None) or "",
        c("course_no"): getattr(module, "kurs_nr", None) or "",
        c("module"): module.modulname,
        c("weekday"): _weekday_label(module),
        # None (not "") when there's no date, so st.column_config.DateColumn
        # at the call site can render it as a clean blank cell instead of
        # trying to parse an empty string as a date.
        c("date"): datum_value.strftime("%Y-%m-%d") if datum_value else None,
        c("start"): module.startzeit.strftime("%H:%M"),
        c("end"): module.endzeit.strftime("%H:%M"),
        c("exam"): t("guided.yes") if getattr(module, "ist_pruefung", False) else t("guided.no"),
        c("type"): module.modultyp,
        c("lecturers"): module.dozierende,
        c("ects"): module.ects,
    }


def _split_course_variant(course_name: str) -> tuple[str, str, bool]:
    """
    Split a raw course title into (base_title, variant_label, is_exam).

    Background: ZHAW exports encode multiple pieces of information into a
    single free-text course name using "/" or "-" separated suffixes, e.g.:
        "Statistik II/Gruppe A"
        "Statistik II/Gruppe A/Prüfung"
        "Praktikum/TK1 Gruppe A & Gruppe B"
        "Seminar/Durchführung 2"
    There is no separate structured column for "which group/run/exam this
    is" - it all lives inside `modulname`. This function reverse-engineers
    that structure with regexes so the rest of the app can group rows that
    belong to the same underlying course ("Statistik II") while still
    telling its group/run/exam variants apart. The result feeds the
    module/course grouping helpers below (_module_group_key,
    _module_course_family_key, _module_variant_label) which decide what
    counts as "the same thing" vs. "a choice between alternatives" during
    guided planning.

    Algorithm (suffixes are stripped from the end, right to left):
      1. Exam suffix: a trailing "/Prüfung" (or "-Prüfung", with common
         umlaut/typo spelling variants uf/ue/ü) is detected and removed
         first, setting is_exam=True and recording a synthetic "PRUEFUNG"
         variant marker. This must run before the generic variant loop
         below, otherwise ".../Gruppe A/Prüfung" would leave "Prüfung"
         attached to the "Gruppe A" match (variant_pattern's trailing
         "$" anchor only strips one suffix per iteration, but exam
         suffixes don't share the group/run vocabulary so they need their
         own dedicated pass).
      2. Variant suffix loop: repeatedly strips one recognized suffix at a
         time from the end of the (already exam-stripped) name - covering
         "Ganzklasse" (whole-class), "Gruppe <label>" (a lettered/numbered
         group, e.g. "Gruppe A" or "Gruppe A+B"), "TK<n> Gruppe <letter>[ &
         Gruppe <letter>]" (teaching-group combinations), and
         "Durchführung <n>" (a numbered repeated run of the same course).
         It loops (not just a single re.sub) because some titles stack more
         than one suffix, e.g. "Kurs/TK1 Gruppe A/Durchführung 2" - each
         iteration peels off the outermost (rightmost) suffix and
         re-anchors on what's left. Recognized parts are inserted at the
         front of variant_parts (index 0) so the final joined variant label
         reads in the same left-to-right order as they appeared in the
         original title, despite being discovered right-to-left.
      3. Whatever remains after stripping known suffixes is the base title
         (e.g. "Statistik II"), used to group all variants of one course
         together; if stripping ever leaves an empty string (a pathological
         input), we fall back to the original raw title rather than losing
         it.

    variant is the recognized suffixes joined with " | " (e.g.
    "GRUPPE A | DURCHFUEHRUNG 2"), or "" if none matched - a plain title
    with no variant suffix. is_exam additionally influences ist_pruefung
    detection alongside the explicit flag/model-level inference in
    models.py (ZHAWModule.validate_time_logic).
    """
    raw = str(course_name or "").strip()
    if not raw:
        return ("Unbekannter Kurs", "", False)

    name = raw
    variant_parts: list[str] = []
    is_exam = False

    exam_pattern = r"\s*[/\-]\s*pr(?:u|ue|uef|uf|uef|ü)fung\s*$"
    if re.search(exam_pattern, name, flags=re.IGNORECASE):
        is_exam = True
        variant_parts.append("PRUEFUNG")
        name = re.sub(exam_pattern, "", name, flags=re.IGNORECASE).strip()

    variant_pattern = (
        r"\s*[/\-]\s*("
        r"ganzklasse|"
        r"gruppe\s+[a-z0-9][a-z0-9\s&+\-]*|"
        r"tk\d+\s+gruppe\s+[a-z](?:\s*&\s*gruppe\s*[a-z])?|"
        r"durchf(?:u|ue|ü)hrung\s*\d+"
        r")\s*$"
    )
    while True:
        match = re.search(variant_pattern, name, flags=re.IGNORECASE)
        if not match:
            break
        variant_text = match.group(1).strip()
        # Insert at the front: suffixes are discovered right-to-left (each
        # loop iteration strips the current rightmost suffix), but should be
        # displayed in their original left-to-right order.
        variant_parts.insert(0, variant_text.upper())
        name = re.sub(variant_pattern, "", name, count=1, flags=re.IGNORECASE).strip()

    base = name.strip("-/ ") or raw
    variant = " | ".join(variant_parts)
    return (base, variant, is_exam)


def _module_group_key(module: Any) -> str:
    """
    Return a stable key identifying which "module" (the top-level grouping
    unit in guided-planning's "module" selection mode) a row belongs to.
    Prefers the structured Modul-Nr identifier from the source data when
    present (e.g. "KP10-1") since it's the most reliable grouping signal;
    falls back to a "BASIS::<lowercased base title>" key derived from
    _split_course_variant() when Modul-Nr is missing, so rows can still be
    grouped by course name alone. The "BASIS::" prefix keeps the fallback
    namespace visually/programmatically distinct from real Modul-Nr values
    (see _module_group_display, which checks for this prefix).
    """
    modul_nr = str(getattr(module, "modul_nr", "") or "").strip()
    if modul_nr:
        return modul_nr
    base, _, _ = _split_course_variant(module.modulname)
    return f"BASIS::{base.lower()}"


def _module_group_display(module_key: str, modules: List[Any]) -> str:
    """Human-readable group label for module-level selection: just the base
    course title for name-derived (BASIS::) keys, or "<Modul-Nr> - <base
    title>" when a real module number is available, so the number stays
    visible for students cross-referencing the official course catalog."""
    if module_key.startswith("BASIS::"):
        base, _, _ = _split_course_variant(modules[0].modulname)
        return base
    base, _, _ = _split_course_variant(modules[0].modulname)
    return f"{module_key} - {base}"


def _module_variant_label(module: Any) -> str:
    """Return the normalized variant label used to decide, within one course
    family (see _module_course_family_key), whether rows are interchangeable
    alternatives. "STANDARD" is used as the label when a row has no
    recognizable variant suffix at all (see render_guided_planning: a family
    with only one distinct variant label - including the "STANDARD" case -
    is treated as mandatory/auto-included, whereas 2+ distinct labels mean
    the student must actively choose one, e.g. Gruppe A vs. Gruppe B)."""
    _, variant, _ = _split_course_variant(module.modulname)
    return variant or "STANDARD"


def _module_course_family_key(module: Any) -> str:
    """
    Return the grouping key for one "course component/family" inside a
    module - the level at which mandatory-vs-choice variant detection
    happens (see render_guided_planning's "module" selection mode).
    Example: a module might contain both a lecture component and a seminar
    component, each of which might itself have "Gruppe A"/"Gruppe B"
    variants; each component is its own family so the seminar's group choice
    doesn't get mixed up with the lecture's.
    Prefers Kurs-Nr (course identifier) when present, since it's the most
    reliable signal for "these rows are the same course component"; falls
    back to a "BASIS::<base title>" key (base title from
    _split_course_variant, NOT lowercased here - unlike _module_group_key -
    since this key is only used for internal grouping/lookup, never
    case-insensitively compared against user text).
    """
    kurs_nr = str(getattr(module, "kurs_nr", "") or "").strip()
    if kurs_nr:
        return kurs_nr
    base, _, _ = _split_course_variant(module.modulname)
    return f"BASIS::{base}"


def _module_label(module: Any) -> str:
    """Human-readable label used in charts and tables (e.g. as the Plotly
    color/hover legend entry, or a table's module-name column): combines
    Modul-Nr and/or Kurs-Nr with the raw module title when available,
    falling back to just the title when neither identifier is present, so
    students can always cross-reference a chart entry back to the source
    catalog numbers."""
    modul_nr = str(getattr(module, "modul_nr", "") or "").strip()
    kurs_nr = str(getattr(module, "kurs_nr", "") or "").strip()
    base = str(getattr(module, "modulname", "") or "").strip()
    if modul_nr and kurs_nr:
        return f"{modul_nr} / {kurs_nr} - {base}"
    if modul_nr:
        return f"{modul_nr} - {base}"
    if kurs_nr:
        return f"{kurs_nr} - {base}"
    return base


def _module_to_ui_row(module: Any) -> dict:
    """Localized row representation for selected module tables."""
    datum_value = getattr(module, "datum", None)
    return {
        c("module_no"): getattr(module, "modul_nr", None) or "",
        c("course_no"): getattr(module, "kurs_nr", None) or "",
        c("module"): module.modulname,
        c("weekday"): _weekday_label(module),
        c("date"): datum_value.strftime("%Y-%m-%d") if datum_value else "",
        c("time"): f"{module.startzeit.strftime('%H:%M')} - {module.endzeit.strftime('%H:%M')}",
        c("duration_min"): module.duration_minutes,
        c("ects"): module.ects,
        c("exam"): t("guided.yes") if getattr(module, "ist_pruefung", False) else t("guided.no"),
        c("lecturers"): module.dozierende,
        c("room"): module.raum,
        c("type"): module.modultyp,
    }


def _module_group_title(module: Any) -> str:
    """Short group title for one module: its Modul-Nr if available, else its
    base course title (no variant suffix). Used as the grouping key for
    dashboard/absence summaries (e.g. _absence_course_impact_dataframe),
    distinct from _module_group_display which additionally needs a `modules`
    list to render the "<Modul-Nr> - <title>" combined display form."""
    modul_nr = str(getattr(module, "modul_nr", "") or "").strip()
    if modul_nr:
        return modul_nr
    base, _, _ = _split_course_variant(module.modulname)
    return base


def _module_signature(module: Any) -> tuple:
    """Semantic signature (date/weekday/time/identifiers/room) used to
    detect two module objects that represent the exact same schedule entry,
    even if they are different Python objects (e.g. the same row appearing
    in both `all_modules` and a filtered/selected subset). Used to
    deduplicate pairs in the overlap/conflict calculations below so a row
    is never reported as "conflicting with itself"."""
    return (
        getattr(module, "datum", None),
        _weekday_label(module),
        module.startzeit.strftime("%H:%M"),
        module.endzeit.strftime("%H:%M"),
        str(getattr(module, "modul_nr", "") or "").strip(),
        str(getattr(module, "kurs_nr", "") or "").strip(),
        str(getattr(module, "modulname", "") or "").strip(),
        str(getattr(module, "raum", "") or "").strip(),
    )


def _same_occurrence_context(left: Any, right: Any) -> bool:
    """
    True when two rows plausibly occur "at the same time" and are therefore
    worth comparing for overlap at all. If both rows carry a concrete date,
    they must fall on the exact same calendar date. If either (or both) lack
    a date - i.e. at least one is a recurring weekly slot - we fall back to
    comparing weekday labels, since a recurring Monday slot could coincide
    with any dated Monday occurrence. This mirrors scheduler._same_occurrence
    in scheduler.py (the same rule, reimplemented locally for the UI's
    overlap-summary helpers - see _calculate_overlap_rows and
    _calculate_module_overlap_summary below).
    """
    left_date = getattr(left, "datum", None)
    right_date = getattr(right, "datum", None)
    if left_date is not None and right_date is not None:
        return left_date == right_date
    return _weekday_label(left) == _weekday_label(right)


def _conflict_date_label(module: Any) -> str:
    """Display-ready date for conflict/overlap tables: the row's actual date
    if known, otherwise a localized "unknown date" placeholder (used for
    undated, recurring rows where only the weekday is meaningful)."""
    datum_value = getattr(module, "datum", None)
    if datum_value is None:
        return t("common.unknown_date")
    return datum_value.strftime("%Y-%m-%d")


def _minutes_overlap(left: Any, right: Any) -> int:
    """
    Return the overlap, in minutes, between two modules' time-of-day
    intervals [start, end) - regardless of date/weekday (callers are
    responsible for first checking the two rows actually occur on the same
    day, e.g. via _same_occurrence_context()).

    Standard interval-overlap formula: given [left_start, left_end) and
    [right_start, right_end), the overlapping region is
    [max(left_start, right_start), min(left_end, right_end)); its length is
    min(left_end, right_end) - max(left_start, right_start). If the
    intervals don't actually overlap this comes out negative, hence the
    max(0, overlap) clamp - a negative "overlap" would be meaningless here
    and always means "no overlap", not "overlap of X minutes in the past".
    """
    left_start = left.startzeit.hour * 60 + left.startzeit.minute
    left_end = left.endzeit.hour * 60 + left.endzeit.minute
    right_start = right.startzeit.hour * 60 + right.startzeit.minute
    right_end = right.endzeit.hour * 60 + right.endzeit.minute
    overlap = min(left_end, right_end) - max(left_start, right_start)
    return max(0, overlap)


def _calculate_overlap_rows(modules: List[Any]) -> List[dict]:
    """
    Build one detailed table row per overlapping pair of modules, with the
    overlap duration expressed both in minutes and as a percentage of each
    module's own duration (so a 15-minute overlap reads very differently for
    a 30-minute vs. a 4-hour session). Feeds tables/charts elsewhere in the
    dashboard.

    This performs its own O(n^2) pairwise comparison rather than reusing
    scheduler.find_time_conflicts(): that function only answers "do these
    conflict at all" (yes/no via interval overlap), while this one needs the
    actual overlap-in-minutes value plus percentage figures for display, and
    additionally applies _same_occurrence_context()'s "same date, or same
    weekday if either is undated" rule up front (same logic as
    scheduler._same_occurrence). Exact-duplicate rows (identical
    _module_signature) are skipped so a row is never compared against an
    identical copy of itself, and seen_pairs deduplicates by a sorted tuple
    of both signatures so each unordered pair is only emitted once even
    though the loop below is a triangular (i, i+1..) scan.
    """
    rows: List[dict] = []
    seen_pairs: set[tuple[tuple, tuple]] = set()
    for i, left in enumerate(modules):
        for right in modules[i + 1 :]:
            if not _same_occurrence_context(left, right):
                continue
            left_signature = _module_signature(left)
            right_signature = _module_signature(right)
            if left_signature == right_signature:
                continue
            overlap = _minutes_overlap(left, right)
            if overlap <= 0:
                continue

            pair_key = tuple(sorted((left_signature, right_signature)))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            left_duration = max(1, left.duration_minutes)
            right_duration = max(1, right.duration_minutes)
            rows.append(
                {
                    c("date"): _conflict_date_label(left),
                    c("module_1"): _module_label(left),
                    c("module_2"): _module_label(right),
                    c("weekday"): _weekday_label(left),
                    c("overlap_min"): overlap,
                    c("overlap_pct_module_1"): round((overlap / left_duration) * 100, 1),
                    c("overlap_pct_module_2"): round((overlap / right_duration) * 100, 1),
                    c("start_1"): left.startzeit.strftime("%H:%M"),
                    c("end_1"): left.endzeit.strftime("%H:%M"),
                    c("start_2"): right.startzeit.strftime("%H:%M"),
                    c("end_2"): right.endzeit.strftime("%H:%M"),
                }
            )
    return rows


def _calculate_module_overlap_summary(modules: List[Any]) -> pd.DataFrame:
    """
    Per-module rollup (one row per module, not per pair) of total overlap
    minutes with any other module, used to drive the "which modules are most
    affected by conflicts" bar chart (_overlap_bar_figure). Uses the same
    pairwise scan, same-occurrence check, and dedup strategy as
    _calculate_overlap_rows() above, but instead of emitting a row per
    conflicting pair, it accumulates each pair's overlap onto *both*
    module's running totals (totals[id(left)] and totals[id(right)] each
    get += overlap), keyed by Python object identity (id()) since two
    different rows can otherwise be indistinguishable by value.
    """
    if not modules:
        return pd.DataFrame()

    totals = {id(module): 0 for module in modules}
    seen_pairs: set[tuple[tuple, tuple]] = set()
    for i, left in enumerate(modules):
        for right in modules[i + 1 :]:
            if not _same_occurrence_context(left, right):
                continue
            left_signature = _module_signature(left)
            right_signature = _module_signature(right)
            if left_signature == right_signature:
                continue
            overlap = _minutes_overlap(left, right)
            if overlap <= 0:
                continue
            pair_key = tuple(sorted((left_signature, right_signature)))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            totals[id(left)] += overlap
            totals[id(right)] += overlap

    summary_rows = []
    for module in modules:
        overlap_total = totals[id(module)]
        duration = max(1, module.duration_minutes)
        summary_rows.append(
            {
                c("module"): _module_label(module),
                c("base_course"): _module_group_title(module),
                c("weekday"): _weekday_label(module),
                c("duration_min"): module.duration_minutes,
                c("overlap_total_min"): overlap_total,
                c("overlap_pct"): round((overlap_total / duration) * 100, 1),
            }
        )

    df = pd.DataFrame(summary_rows)
    if not df.empty:
        df = df.sort_values([c("overlap_total_min"), c("module")], ascending=[False, True])
    return df


def _summarize_conflicts(conflicts: List[Tuple[Any, Any]]) -> pd.DataFrame:
    """
    Aggregate the raw (module_a, module_b) conflict pairs returned by
    scheduler.find_time_conflicts() into one summary row per unique
    course-label pair, counting how many separate occurrences (dates/
    weekdays) they conflict on and their total combined overlap minutes.
    Unlike _calculate_overlap_rows()/_calculate_module_overlap_summary()
    (which independently recompute overlap over an arbitrary module list),
    this function consumes conflicts already detected by
    scheduler.find_time_conflicts() and only re-derives the overlap minutes
    (_minutes_overlap) per pair for display - it does not redo the
    conflict-detection decision itself.

    Pair keys are built from sorted display labels (`sorted([label_a,
    label_b])`) rather than sorted module signatures, so that all conflicts
    between the same two *courses* accumulate into one summary row even
    though each occurrence is a different pair of module objects (e.g. every
    week two overlapping recurring slots collide, and this rolls all of
    those weekly collisions into one line).
    """
    if not conflicts:
        return pd.DataFrame()

    summary: dict[tuple[str, str], dict[str, Any]] = {}
    for left, right in conflicts:
        labels = sorted([_module_label(left), _module_label(right)])
        key = (labels[0], labels[1])
        overlap = _minutes_overlap(left, right)
        day_label = _weekday_label(left)
        date_label = _conflict_date_label(left)

        if key not in summary:
            summary[key] = {
                c("module_1"): labels[0],
                c("module_2"): labels[1],
                c("conflict_days_count"): 0,
                c("overlap_total_min"): 0,
                c("conflict_dates"): [],
                c("conflict_weekdays"): [],
            }

        summary[key][c("conflict_days_count")] += 1
        summary[key][c("overlap_total_min")] += overlap
        summary[key][c("conflict_dates")].append(date_label)
        summary[key][c("conflict_weekdays")].append(day_label)

    rows = []
    for data in summary.values():
        rows.append(
            {
                c("module_1"): data[c("module_1")],
                c("module_2"): data[c("module_2")],
                c("conflict_days_count"): data[c("conflict_days_count")],
                c("overlap_total_min"): data[c("overlap_total_min")],
                c("conflict_dates"): ", ".join(sorted(set(data[c("conflict_dates")]))[:6]),
                c("conflict_weekdays"): ", ".join(sorted(set(data[c("conflict_weekdays")]))),
            }
        )

    return pd.DataFrame(rows).sort_values([c("overlap_total_min"), c("conflict_days_count")], ascending=[False, False])


def _semester_timeline_figure(modules: List[Any], color_sequence: list[str] | None = None, color_by: str = "module"):
    """
    Build a Gantt-style Plotly timeline (px.timeline) spanning the whole
    semester: one horizontal bar per dated lesson, positioned on its actual
    calendar date+time, grouped by weekday row and colored by module. Unlike
    _weekly_timeline_figure() (which shows a single representative week),
    this chart uses REAL dates on the x-axis (not the 1970-01-01 dummy-date
    trick), so students can see the actual semester-long cadence of a
    course (e.g. "every second Monday" becomes visually obvious).
    Undated/recurring rows (no `datum`) are skipped since they have no
    single calendar position to place on this axis; returns None (nothing to
    render) if no row has a date at all.

    `color_sequence`: an optional list of hex colors (see CHART_PALETTES)
    overriding Plotly's default qualitative palette - exposed to the user
    via the chart's "Diagramm-Einstellungen" panel in render_dashboard().
    `color_by`: "module" (default, one color per course) or "type" (one
    color per Modulart/Vorlesung-Seminar-etc.) - lets the user re-purpose
    the same chart to answer a different question ("which course is this?"
    vs. "what kind of session is this?") without needing a second chart.
    """
    color_dimension = c("type") if color_by == "type" else c("module")

    rows = []
    for module in modules:
        datum_value = getattr(module, "datum", None)
        if datum_value is None:
            continue
        rows.append(
            {
                c("module"): _module_label(module),
                c("start_datetime"): pd.to_datetime(f"{datum_value.isoformat()} {module.startzeit.strftime('%H:%M:%S')}"),
                c("end_datetime"): pd.to_datetime(f"{datum_value.isoformat()} {module.endzeit.strftime('%H:%M:%S')}"),
                c("weekday"): _weekday_label(module),
                c("type"): module.modultyp,
            }
        )

    if not rows:
        return None

    df = pd.DataFrame(rows)
    fig = px.timeline(
        df,
        x_start=c("start_datetime"),
        x_end=c("end_datetime"),
        y=c("weekday"),
        color=color_dimension,
        color_discrete_sequence=color_sequence,
        hover_name=c("module"),
        hover_data={c("type"): True},
        category_orders={c("weekday"): _weekday_labels_in_order()},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=560,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_title=t("chart.xaxis_semester"),
        yaxis_title="",
        legend_title_text=t("chart.legend_modules") if color_by == "module" else t("col.type"),
    )
    return _apply_chart_theme(fig)


def _daily_load_figure(modules: List[Any], color_sequence: list[str] | None = None, split_by_module: bool = False):
    """Bar chart of total scheduled minutes per calendar date across the
    semester (dated rows only, grouped/summed by date) - helps spot
    unusually heavy single days (e.g. an all-day workshop) at a glance.
    Returns None when no dated rows exist.

    `color_sequence`: optional palette override (see CHART_PALETTES).
    `split_by_module`: when True, each day's bar is stacked by module
    instead of shown as one solid total - trades a simpler silhouette for
    the ability to see *which* course is driving a heavy day, another
    user-toggleable view exposed via the chart's settings panel.
    """
    rows = []
    for module in modules:
        datum_value = getattr(module, "datum", None)
        if datum_value is None:
            continue
        rows.append({c("date"): datum_value, c("duration_min"): module.duration_minutes, c("module"): _module_label(module)})

    if not rows:
        return None

    df = pd.DataFrame(rows)
    if split_by_module:
        daily = df.groupby([c("date"), c("module")], as_index=False)[c("duration_min")].sum()
        fig = px.bar(
            daily,
            x=c("date"),
            y=c("duration_min"),
            color=c("module"),
            color_discrete_sequence=color_sequence,
            title=t("chart.daily_load_title"),
        )
    else:
        daily = df.groupby(c("date"), as_index=False)[c("duration_min")].sum()
        single_color = [color_sequence[0]] if color_sequence else None
        fig = px.bar(
            daily,
            x=c("date"),
            y=c("duration_min"),
            color_discrete_sequence=single_color,
            title=t("chart.daily_load_title"),
        )
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=40, b=10), yaxis_title=t("chart.yaxis_minutes"), xaxis_title=t("chart.xaxis_semester"))
    return _apply_chart_theme(fig)


def _calculate_exam_feasibility(modules: List[Any]) -> pd.DataFrame:
    """
    For every exam row (ist_pruefung=True) in the selection, check whether
    it is realistically attendable: does it overlap, on the same calendar
    date, with any non-exam module also in the selection (e.g. a regular
    lecture scheduled at the same time as the exam)? This only makes sense
    for dated exams - an exam with no fixed `datum` yet is reported as
    status "unknown" rather than "ok", since we simply cannot check it.
    Deliberately restricted to same-date comparisons (not the more general
    _same_occurrence_context() weekday fallback used elsewhere) because an
    exam is a one-off dated event by nature; comparing it to an undated
    weekly slot "on the same weekday" would produce false positives for
    every week that slot recurs, most of which aren't actually the exam
    date.
    """
    exam_rows = []
    exam_modules = [m for m in modules if getattr(m, "ist_pruefung", False)]
    normal_modules = [m for m in modules if not getattr(m, "ist_pruefung", False)]

    for exam in exam_modules:
        conflict_count = 0
        if getattr(exam, "datum", None) is not None:
            for other in normal_modules:
                if getattr(other, "datum", None) != exam.datum:
                    continue
                if _minutes_overlap(exam, other) > 0:
                    conflict_count += 1

        if getattr(exam, "datum", None) is None:
            status = t("exam.status_unknown")
        elif conflict_count == 0:
            status = t("exam.status_ok")
        else:
            status = t("exam.status_conflict")

        exam_rows.append(
            {
                c("exam_name"): _module_label(exam),
                c("module"): _module_group_title(exam),
                # None (not "") for a missing date - see _module_to_row for
                # why: lets st.column_config.DateColumn render a blank cell
                # instead of failing to parse an empty string.
                c("date"): exam.datum.strftime("%Y-%m-%d") if getattr(exam, "datum", None) else None,
                c("time"): f"{exam.startzeit.strftime('%H:%M')} - {exam.endzeit.strftime('%H:%M')}",
                c("conflicts"): conflict_count,
                c("status"): status,
            }
        )

    return pd.DataFrame(exam_rows)


def _weekly_timeline_figure(modules: List[Any]):
    """
    Build the "typical week" Gantt-style timeline used in the Timetable tab:
    one row per weekday, one bar per module colored by module type,
    overlaid with synthetic bars for any active blocked-weekday absence rule
    (see _absence_overlay_for_week). Unlike _semester_timeline_figure() this
    intentionally collapses the whole semester into a single representative
    week - every module (dated or recurring) is plotted purely by its
    time-of-day, ignoring which actual calendar date it falls on, which is
    exactly what the 1970-01-01 dummy-date trick below achieves (see inline
    comment at the `c("start")`/`c("end")` construction).
    """
    if not modules:
        return None

    day_labels = _weekday_labels_in_order()
    day_order = {label: idx for idx, label in enumerate(day_labels)}
    rows = []
    settings = _absence_settings()
    for module in modules:
        rows.append(
            {
                c("weekday"): _weekday_label(module),
                c("module"): _module_label(module),
                # 1970-01-01 dummy-date trick: px.timeline() (Plotly's Gantt
                # chart) requires real datetime values for x_start/x_end, but
                # this chart only wants to compare times-of-day across
                # different weekday rows, not real calendar dates. Anchoring
                # every bar to the same arbitrary date turns the x-axis into
                # a pure "time of day" axis (tick-formatted as %H:%M further
                # below) while still satisfying Plotly's datetime
                # requirement. Must match the dummy date used in
                # _absence_overlay_for_week() so overlay bars line up
                # correctly once concatenated below.
                c("start"): pd.to_datetime(f"1970-01-01 {module.startzeit.strftime('%H:%M:%S')}"),
                c("end"): pd.to_datetime(f"1970-01-01 {module.endzeit.strftime('%H:%M:%S')}"),
                c("type"): module.modultyp,
            }
        )

    df = pd.DataFrame(rows)
    overlay_df = _absence_overlay_for_week(settings)
    if not overlay_df.empty:
        df = pd.concat([df, overlay_df], ignore_index=True)
    if df.empty:
        return None

    fig = px.timeline(
        df,
        x_start=c("start"),
        x_end=c("end"),
        y=c("weekday"),
        color=c("type"),
        hover_name=c("module"),
        hover_data={c("start"): False, c("end"): False},
        category_orders={c("weekday"): list(day_order.keys())},
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis_title=t("chart.xaxis_time"),
        yaxis_title="",
        legend_title_text=t("chart.legend_module_type"),
    )
    fig.update_xaxes(tickformat="%H:%M")
    return _apply_chart_theme(fig)


def _weekday_bar_figure(modules: List[Any], color_sequence: list[str] | None = None):
    """Simple histogram of row counts per weekday (relying on px.bar's
    implicit count-of-occurrences when no y is given), in Monday-first
    order - a quick "which days are busiest" overview for the dashboard.

    Colored per-weekday (rather than one flat color) using `color_sequence`
    (see CHART_PALETTES) so the user-chosen palette is visible even on a
    single-series chart like this one; the legend is hidden since the
    x-axis labels already identify each bar, so a legend would be pure
    redundancy (removing it also frees up chart width for the bars)."""
    if not modules:
        return None
    df = pd.DataFrame({c("weekday"): [_weekday_label(m) for m in modules]})
    order = _weekday_labels_in_order()
    fig = px.bar(
        df,
        x=c("weekday"),
        color=c("weekday"),
        color_discrete_sequence=color_sequence,
        title=t("chart.weekday_title"),
        category_orders={c("weekday"): order},
    )
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=40, b=10), yaxis_title=t("chart.yaxis_items"), showlegend=False)
    return _apply_chart_theme(fig)


def _overlap_bar_figure(summary_df: pd.DataFrame, color_scale: str = "Reds"):
    """Horizontal bar chart of the top 12 most-overlapping modules (from
    _calculate_module_overlap_summary), colored by overlap percentage so
    both absolute minutes and relative severity are visible at once. Chart
    height scales with the number of bars shown so labels stay readable.

    `color_scale`: a Plotly continuous-scale name (see
    CONTINUOUS_COLOR_SCALES) - unlike the other charts this one colors by a
    numeric value (overlap %), not a category, so it needs a *continuous*
    scale rather than a qualitative palette."""
    if summary_df.empty:
        return None
    top = summary_df.head(12).copy()
    fig = px.bar(
        top,
        x=c("overlap_total_min"),
        y=c("module"),
        orientation="h",
        title=t("chart.overlap_title"),
        color=c("overlap_pct"),
        color_continuous_scale=color_scale,
    )
    fig.update_layout(height=max(440, 32 * len(top) + 140), margin=dict(l=10, r=10, t=40, b=10))
    return _apply_chart_theme(fig)


def _render_chart_toolbar(
    settings_key: str,
    modules: List[Any],
    *,
    continuous: bool = False,
    show_weekday_filter: bool = True,
    extra_options: dict[str, list[tuple[str, str]]] | None = None,
) -> tuple[List[Any], Any, dict[str, str]]:
    """
    Renders one chart's "🎨 Diagramm-Einstellungen" panel (collapsed by
    default - progressive disclosure, see the design-concept discussion:
    advanced controls shouldn't clutter the default view) and returns
    everything the caller needs to (re-)build that chart accordingly:

        filtered_modules, palette, extra_choices = _render_chart_toolbar(...)

    - filtered_modules: `modules` narrowed down by the weekday multiselect
      (identical to `modules` if show_weekday_filter=False or nothing was
      deselected) - lets a chart be explored without leaving the dashboard
      or touching the guided-planning filters.
    - palette: a list[str] of hex colors when continuous=False (pass to a
      px.* call's `color_discrete_sequence`), or a single scale-name string
      when continuous=True (pass to `color_continuous_scale`).
    - extra_choices: a dict of {option_key: chosen_value} for every entry
      in `extra_options` (e.g. a "color by module/type" selector) - chart
      functions that need one of these read it from here rather than the
      toolbar hard-coding chart-specific UI itself, so this helper stays
      reusable across charts with different extra controls.

    All widget keys are namespaced with `settings_key` so each chart's
    settings (palette, filter, extra choices) persist independently across
    reruns - picking a palette for one chart never resets another's.
    """
    with st.expander(t("chart.settings_toggle"), expanded=False):
        cols = st.columns(2) if show_weekday_filter else [st.container()]

        with cols[0]:
            if continuous:
                palette = st.selectbox(
                    t("chart.settings_color_scale"),
                    options=CONTINUOUS_COLOR_SCALES,
                    key=f"{settings_key}_scale",
                )
            else:
                palette_name = st.selectbox(
                    t("chart.settings_palette"),
                    options=list(CHART_PALETTES.keys()),
                    format_func=lambda k: t(f"chart.palette.{k}"),
                    key=f"{settings_key}_palette",
                )
                palette = CHART_PALETTES[palette_name]

        filtered = list(modules)
        if show_weekday_filter and modules:
            with cols[1]:
                all_weekdays_in_order = _weekday_labels_in_order()
                present = {_weekday_label(m) for m in modules}
                present_weekdays = [d for d in all_weekdays_in_order if d in present]
                selected_weekdays = st.multiselect(
                    t("chart.settings_weekday_filter"),
                    options=present_weekdays,
                    default=present_weekdays,
                    key=f"{settings_key}_weekdays",
                )
                filtered = [m for m in modules if _weekday_label(m) in selected_weekdays]

        extra_choices: dict[str, str] = {}
        for option_key, choices in (extra_options or {}).items():
            labels = [label for label, _value in choices]
            values_by_label = dict(choices)
            chosen_label = st.radio(
                t(f"chart.settings_{option_key}"),
                options=labels,
                key=f"{settings_key}_{option_key}",
                horizontal=True,
            )
            extra_choices[option_key] = values_by_label[chosen_label]

    return filtered, palette, extra_choices


def render_guided_planning(all_modules: List[Any]) -> List[Any]:
    """
    Guided, German-first course planning assistant with dynamic questions.
    This is the main interactive tab where a student narrows the full
    uploaded schedule (`all_modules`) down to their actual course selection.
    Returns the final selected module list, which the caller also stores in
    st.session_state.selected_modules (this function has that side effect
    itself, right before returning) so it drives the other tabs (dashboard,
    timetable, conflicts, export) on subsequent reruns.

    Overall flow (rendered top-to-bottom as numbered "step" sections):
      Step 1 - Absence rules: three yes/no questions (period / individual
        dates / recurring blocked weekdays) that populate the
        st.session_state.absence_* keys read by _absence_settings()
        elsewhere. These rules don't filter what's selectable here; they
        drive the absence-risk warnings shown in the dashboard/conflicts
        tabs and the blocked-day overlay in the timetable chart.
      Step 2 - Search/filter widgets: free-text and structured filters
        (Modul-Nr, Kurs-Nr, keyword, module type, weekday, lecturer) that
        narrow `all_modules` down to a working set `filtered` before any
        selection UI is shown - this keeps large catalogs manageable.
      Step 3 - Selection mode: the student picks one of three granularities
        for making their selection (radio "selection_mode"):
          - "module" mode: select whole modules (grouped by Modul-Nr /
            base title via _module_group_key), then, per selected module,
            resolve mandatory vs. choice course components (see the
            variant-family logic below - this is the most complex path).
          - "course" mode: select whole base courses (grouped by
            _split_course_variant's base title), including all their
            variants at once - coarser-grained than "module" mode.
          - "row" mode: select individual schedule rows directly via a
            checkbox data_editor - the finest-grained, most manual option.
      Step 4/5 (only in "module" mode): a per-module component breakdown
        expander, followed by a status table summarizing completeness
        (any open mandatory choices?) and conflicts per module.

    Because Streamlit reruns this whole function on every widget
    interaction, all cross-rerun choices (selected keys, filter values) are
    read from / written back to st.session_state via widget `key=` bindings
    or explicit session_state assignments, so the UI stays consistent across
    reruns rather than resetting.
    """
    st.subheader(t("guided.subheader"))

    if not all_modules:
        st.info(t("guided.no_data"))
        return []

    st.markdown(t("guided.intro"))

    semester_start, semester_end = _semester_date_bounds(all_modules)
    absence_period_valid = True

    with card("guided-step1", "🧭", t("guided.step1").strip("*")):
        if semester_start and semester_end:
            st.caption(
                t(
                    "guided.semester_range",
                    start=semester_start.strftime("%d.%m.%Y"),
                    end=semester_end.strftime("%d.%m.%Y"),
                )
            )

        has_absence_period = st.radio(
            t("guided.q.absence_period"),
            options=[t("guided.no"), t("guided.yes")],
            horizontal=True,
            key="q_absence_period",
        )

        absence_start = None
        absence_end = None
        if has_absence_period == t("guided.yes"):
            if "absence_start_prev" not in st.session_state:
                st.session_state.absence_start_prev = None

            if semester_start and "absence_start" not in st.session_state:
                st.session_state.absence_start = semester_start

            current_start = st.session_state.get("absence_start") or semester_start or date.today()
            if "absence_end" not in st.session_state:
                st.session_state.absence_end = _default_absence_end(current_start, semester_end)

            col1, col2 = st.columns(2)
            with col1:
                absence_start = st.date_input(
                    t("guided.absence_from"),
                    key="absence_start",
                    min_value=semester_start,
                    max_value=semester_end,
                )

            # Auto-advance the "to" date whenever the student picks a new
            # "from" date that would otherwise leave an invalid/stale range
            # (end <= start). "absence_start_prev" tracks the previously
            # seen start date across reruns so this only re-defaults the end
            # date on an actual change of the start date, not on every
            # rerun - otherwise a manually chosen end date further in the
            # future would keep getting silently overwritten back to
            # start+1 day on each script rerun.
            previous_start = st.session_state.get("absence_start_prev")
            current_end = st.session_state.get("absence_end")
            if previous_start != absence_start and (current_end is None or current_end <= absence_start):
                st.session_state.absence_end = _default_absence_end(absence_start, semester_end)
            st.session_state.absence_start_prev = absence_start

            with col2:
                absence_end = st.date_input(
                    t("guided.absence_to"),
                    key="absence_end",
                    min_value=absence_start or semester_start,
                    max_value=semester_end,
                )

            if absence_start and absence_end and absence_start > absence_end:
                st.error(t("guided.absence_invalid_order"))
                absence_period_valid = False

            if semester_start and semester_end and absence_start and absence_end:
                if absence_start < semester_start or absence_end > semester_end:
                    st.error(
                        t(
                            "guided.absence_out_of_range",
                            start=semester_start.strftime("%d.%m.%Y"),
                            end=semester_end.strftime("%d.%m.%Y"),
                        )
                    )
                    absence_period_valid = False

        st.session_state.absence_period_enabled = has_absence_period == t("guided.yes")
        st.session_state.absence_period_start = absence_start
        st.session_state.absence_period_end = absence_end

        has_absent_dates = st.radio(
            t("guided.q.absent_dates"),
            options=[t("guided.no"), t("guided.yes")],
            horizontal=True,
            key="q_absent_dates",
        )

        absent_dates = []
        if has_absent_dates == t("guided.yes"):
            available_dates = sorted(
                {m.datum for m in all_modules if getattr(m, "datum", None) is not None}
            )
            if available_dates:
                absent_dates = st.multiselect(
                    t("guided.absent_dates_select"),
                    options=available_dates,
                    format_func=lambda d: d.strftime("%d.%m.%Y"),
                    key="absent_dates",
                )
            else:
                st.caption(t("guided.no_dates_found"))

        st.session_state.absence_dates_enabled = has_absent_dates == t("guided.yes")
        st.session_state.absence_dates_values = absent_dates

        has_blocked_days = st.radio(
            t("guided.q.blocked_days"),
            options=[t("guided.no"), t("guided.yes")],
            horizontal=True,
            key="q_blocked_days",
        )

        blocked_days = []
        blocked_halfday = t("guided.full_day")
        if has_blocked_days == t("guided.yes"):
            blocked_days = st.multiselect(
                t("guided.blocked_days"),
                options=_blocking_weekday_keys(),
                format_func=lambda day_key: t(f"weekday.{day_key}"),
                key="blocked_days",
            )
            blocked_halfday = st.selectbox(
                t("guided.blocked_range"),
                options=[t("guided.full_day"), t("guided.morning"), t("guided.afternoon")],
                key="blocked_halfday",
            )

        st.session_state.absence_blocked_enabled = has_blocked_days == t("guided.yes")
        st.session_state.absence_blocked_days_values = blocked_days
        st.session_state.absence_blocked_halfday_value = blocked_halfday

    with card("guided-step2", "🔍", t("guided.step2").strip("*")):
        modul_nr_search = st.text_input(
            t("guided.search.modul_nr"),
            placeholder=t("guided.search.modul_nr_placeholder"),
            key="filter_modul_nr",
        ).strip().lower()

        kurs_nr_search = st.text_input(
            t("guided.search.kurs_nr"),
            placeholder=t("guided.search.kurs_nr_placeholder"),
            key="filter_kurs_nr",
        ).strip().lower()

        search_text = st.text_input(
            t("guided.search.text"),
            placeholder=t("guided.search.text_placeholder"),
            key="filter_search",
        ).strip().lower()

        base_search_text = st.text_input(
            t("guided.search.base"),
            placeholder=t("guided.search.base_placeholder"),
            key="filter_base_search",
        ).strip().lower()

        module_types = sorted({str(getattr(m, "modultyp", t("common.na"))) for m in all_modules if getattr(m, "modultyp", None)})
        selected_types = st.multiselect(
            t("guided.filter.types"),
            options=module_types,
            key="filter_module_types",
        )

        weekdays_present = sorted({_weekday_label(m) for m in all_modules})
        selected_weekdays = st.multiselect(
            t("guided.filter.weekdays"),
            options=weekdays_present,
            key="filter_weekdays",
        )

        lecturers = sorted(
            {
                str(getattr(m, "dozierende", "N/A"))
                for m in all_modules
                if getattr(m, "dozierende", None)
            }
        )
        selected_lecturers = st.multiselect(
            t("guided.filter.lecturers"),
            options=lecturers,
            key="filter_lecturers",
        )

        sort_mode = st.selectbox(
            t("guided.sort"),
            options=[t("guided.sort.date"), t("guided.sort.weekday"), t("guided.sort.name")],
            key="filter_sort_mode",
        )

    filtered: List[Any] = []
    absent_date_set = set(absent_dates)
    for module in all_modules:
        datum_value = getattr(module, "datum", None)
        day_label = _weekday_label(module)
        modul_nr_value = str(getattr(module, "modul_nr", "") or "").lower()
        kurs_nr_value = str(getattr(module, "kurs_nr", "") or "").lower()

        if modul_nr_search and modul_nr_search not in modul_nr_value:
            continue

        if kurs_nr_search and kurs_nr_search not in kurs_nr_value:
            continue

        if selected_types and str(module.modultyp) not in selected_types:
            continue

        if selected_weekdays and day_label not in selected_weekdays:
            continue

        if selected_lecturers and str(module.dozierende) not in selected_lecturers:
            continue

        if base_search_text:
            base_name, _, _ = _split_course_variant(module.modulname)
            if base_search_text not in base_name.lower():
                continue

        if search_text:
            haystack = " ".join([
                str(module.modulname),
                str(module.dozierende),
                str(module.modultyp),
            ]).lower()
            if search_text not in haystack:
                continue

        filtered.append(module)

    if sort_mode == t("guided.sort.date"):
        filtered.sort(key=lambda m: ((getattr(m, "datum", None) is None), getattr(m, "datum", date.max), m.startzeit))
    elif sort_mode == t("guided.sort.weekday"):
        day_order = {day: idx for idx, day in enumerate(_weekday_labels_in_order())}
        filtered.sort(key=lambda m: (day_order.get(_weekday_label(m), 99), m.startzeit))
    else:
        filtered.sort(key=lambda m: str(m.modulname).lower())

    st.markdown(t("guided.step3_title", count=len(filtered)))
    if not filtered:
        st.warning(t("guided.no_matches"))
        st.session_state.selected_modules = []
        return []

    selection_mode = st.radio(
        t("guided.selection_mode"),
        options=[t("guided.mode.module"), t("guided.mode.course"), t("guided.mode.row")],
        horizontal=True,
        key="selection_mode",
        help=t("guided.selection_mode_help"),
    )

    include_exams = st.checkbox(
        t("guided.include_exams"),
        value=False,
        key="include_exams",
    )

    # Object identity (id()) rather than value equality is used throughout
    # this function to track "is this specific row selected/filtered",
    # because ZHAWModule is a Pydantic model with value-based equality - two
    # distinct rows that happen to share identical field values (e.g. two
    # genuinely identical-looking timetable entries) would otherwise be
    # indistinguishable from each other. `modules_with_id` pairs each row
    # with its position in the master `all_modules` list purely so the
    # "row" selection mode below can round-trip a data_editor's checked rows
    # back to module objects via that positional id.
    modules_with_id = list(enumerate(all_modules))
    selected_lookup = {id(m): True for m in st.session_state.get("selected_modules", [])}
    filtered_ids = set(id(m) for m in filtered)

    filtered_with_ids = [(idx, m) for idx, m in modules_with_id if id(m) in filtered_ids]

    if selection_mode == t("guided.mode.module"):
        # "module" mode, part A: build one row per module-group (see
        # _module_group_key - prefers Modul-Nr, falls back to base title) in
        # a checkbox table, so the student first picks *which modules*
        # they're taking before drilling into per-component variant choices
        # further below.
        grouped_modules: dict[str, list[Any]] = {}
        for _, module in filtered_with_ids:
            key = _module_group_key(module)
            grouped_modules.setdefault(key, []).append(module)

        module_rows = []
        selected_keys_prev = set(st.session_state.get("selected_course_bases", []))
        for key, items in sorted(grouped_modules.items(), key=lambda pair: _module_group_display(pair[0], pair[1]).lower()):
            courses = sorted({str(getattr(m, "kurs_nr", "") or "") for m in items if getattr(m, "kurs_nr", None)})
            exam_count = sum(1 for m in items if getattr(m, "ist_pruefung", False))
            dates = sorted({m.datum for m in items if getattr(m, "datum", None) is not None})
            first_date = dates[0].strftime("%Y-%m-%d") if dates else ""
            last_date = dates[-1].strftime("%Y-%m-%d") if dates else ""
            date_range = f"{first_date} - {last_date}" if first_date and last_date else ""
            label = _module_group_display(key, items)
            module_rows.append(
                {
                    c("select"): key in selected_keys_prev,
                    c("module_group"): label,
                    c("module_key"): key,
                    c("courses"): len(courses),
                    c("rows"): len(items),
                    c("exam_dates"): exam_count,
                    c("period"): date_range,
                }
            )

        module_df = pd.DataFrame(module_rows)
        edited_module_df = st.data_editor(
            module_df,
            hide_index=True,
            width="stretch",
            disabled=[c("module_group"), c("module_key"), c("courses"), c("rows"), c("exam_dates"), c("period")],
            column_config={c("select"): st.column_config.CheckboxColumn(c("select"))},
            key="module_group_selector_editor",
        )

        selected_keys = set(edited_module_df.loc[edited_module_df[c("select")] == True, c("module_key")].tolist())
        st.session_state.selected_course_bases = sorted(selected_keys)

        selected_modules = []
        selected_by_module_key: dict[str, list[Any]] = {}
        module_status_rows = []

        st.markdown(t("guided.step4"))

        # "module" mode, part B: for every module the student checked above,
        # resolve its internal structure into "mandatory" vs. "choice"
        # course components:
        #   - Exams are pulled out separately (exam_items) and only added
        #     back in if the "include_exams" checkbox is on - they're never
        #     part of the mandatory/choice resolution below.
        #   - The remaining (non-exam) rows are grouped into "families" by
        #     _module_course_family_key() - roughly "one lecture", "one
        #     seminar", etc. within the module.
        #   - Within each family, rows are further grouped by
        #     _module_variant_label() (the "/Gruppe A" style suffix parsed
        #     by _split_course_variant). If a family has exactly ONE
        #     distinct variant label, there is nothing to choose - it's
        #     auto-included as "mandatory" (this also covers the common case
        #     of a component with no group/run suffix at all, which
        #     normalizes to the single label "STANDARD"). If a family has
        #     TWO OR MORE distinct variant labels (e.g. "GRUPPE A" vs.
        #     "GRUPPE B"), that's genuinely a choice the student must make -
        #     these are mutually exclusive alternative deliveries of the
        #     same component, not separate things to attend simultaneously -
        #     so a selectbox is rendered and nothing is added until the
        #     student actively picks one ("not selected" leaves it as an
        #     open_choices count, surfaced in the step-5 status table below).
        for key, items in sorted(grouped_modules.items(), key=lambda pair: _module_group_display(pair[0], pair[1]).lower()):
            if key not in selected_keys:
                continue

            label = _module_group_display(key, items)
            non_exam_items = [m for m in items if not getattr(m, "ist_pruefung", False)]
            exam_items = [m for m in items if getattr(m, "ist_pruefung", False)]

            families: dict[str, list[Any]] = {}
            for module in non_exam_items:
                fam_key = _module_course_family_key(module)
                families.setdefault(fam_key, []).append(module)

            module_selected = []
            open_choices = 0
            family_rows = []

            with st.expander(t("guided.module_components_expander", module=label), expanded=False):
                for fam_key, fam_items in sorted(families.items(), key=lambda pair: pair[0]):
                    variants: dict[str, list[Any]] = {}
                    for fam_item in fam_items:
                        variants.setdefault(_module_variant_label(fam_item), []).append(fam_item)

                    variant_names = sorted(variants.keys())
                    if len(variant_names) == 1:
                        # Single variant -> nothing to choose; auto-include
                        # every row of this component ("mandatory").
                        only_variant = variant_names[0]
                        module_selected.extend(variants[only_variant])
                        family_rows.append(
                            {
                                c("course_component"): fam_key,
                                c("component_type"): t("guided.component_mandatory"),
                                c("selection"): only_variant,
                                c("variants"): ", ".join(variant_names),
                            }
                        )
                    else:
                        # 2+ variants -> mutually exclusive alternatives;
                        # require an explicit selectbox choice. The selector
                        # key is namespaced by module key + family key so
                        # each component's choice persists independently
                        # across reruns and doesn't collide with same-named
                        # components in a different module.
                        selector_key = f"variant_select::{key}::{fam_key}"
                        options = [t("guided.not_selected")] + variant_names
                        choice = st.selectbox(
                            t("guided.variant_select_label", family=fam_key),
                            options=options,
                            key=selector_key,
                            help=t("guided.variant_select_help"),
                        )
                        if choice != t("guided.not_selected"):
                            module_selected.extend(variants[choice])
                        else:
                            open_choices += 1

                        family_rows.append(
                            {
                                c("course_component"): fam_key,
                                c("component_type"): t("guided.component_choice"),
                                c("selection"): choice,
                                c("variants"): ", ".join(variant_names),
                            }
                        )

                if include_exams:
                    module_selected.extend(exam_items)

                if family_rows:
                    st.dataframe(pd.DataFrame(family_rows), hide_index=True, width="stretch")
                st.caption(
                    t("guided.module_caption", exams=len(exam_items), open=open_choices)
                )

            selected_by_module_key[key] = module_selected
            selected_modules.extend(module_selected)
            module_status_rows.append(
                {
                    c("module_group"): label,
                    c("open_choice_components"): open_choices,
                    c("selected_rows"): len(module_selected),
                    c("status"): t("guided.status.incomplete") if open_choices > 0 else t("guided.status.complete"),
                }
            )

        # Deduplicate selected modules by object identity. A single row can
        # end up added to `selected_modules` more than once here because the
        # per-module loop above extends it once per module-group iteration -
        # if the same underlying row object were ever reachable from two
        # different module groups (e.g. an edge case in the grouping), this
        # collapses it back to one entry. seen_ids uses id() rather than
        # value equality for the same reason as elsewhere in this function
        # (see the "modules_with_id" comment above): value-equal-but-
        # distinct rows must NOT be collapsed into each other.
        unique_selected = []
        seen_ids = set()
        for module in selected_modules:
            mid = id(module)
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            unique_selected.append(module)
        selected_modules = unique_selected

        # Enrich module status with conflict information: run the real
        # scheduler.find_time_conflicts() over the final selection (not the
        # local _calculate_* overlap helpers - this reuses the same
        # conflict definition the Conflicts tab uses) and back-annotate each
        # module's status row with how many of ITS OWN selected rows
        # participate in at least one conflict. matching_key re-derives
        # which grouped_modules key a status row belongs to by comparing
        # display labels (module_status_rows only stored the display label,
        # not the key itself, when it was built above) so we can look up
        # that module's selected rows in selected_by_module_key.
        selected_conflicts = find_time_conflicts(selected_modules)
        conflict_module_ids = {id(left) for left, _ in selected_conflicts} | {id(right) for _, right in selected_conflicts}
        for row in module_status_rows:
            matching_key = None
            for key, items in grouped_modules.items():
                if _module_group_display(key, items) == row[c("module_group")]:
                    matching_key = key
                    break
            module_conflicts = 0
            if matching_key is not None:
                module_conflicts = sum(1 for m in selected_by_module_key.get(matching_key, []) if id(m) in conflict_module_ids)

            row[c("conflict_rows")] = module_conflicts
            if module_conflicts > 0 and row[c("status")] == t("guided.status.complete"):
                row[c("status")] = t("guided.status.complete_conflicts")
            elif module_conflicts > 0 and row[c("status")] == t("guided.status.incomplete"):
                row[c("status")] = t("guided.status.incomplete_conflicts")

        if module_status_rows:
            st.markdown(t("guided.step5"))
            status_tones = {
                t("guided.status.complete"): "success",
                t("guided.status.incomplete"): "warning",
                t("guided.status.complete_conflicts"): "warning",
                t("guided.status.incomplete_conflicts"): "danger",
            }
            st.dataframe(
                _style_status_column(pd.DataFrame(module_status_rows), c("status"), status_tones),
                hide_index=True,
                width="stretch",
            )

    elif selection_mode == t("guided.mode.course"):
        # "course" mode: coarser-grained than "module" mode - groups purely
        # by the base course title from _split_course_variant() (ignoring
        # Modul-Nr/Kurs-Nr structure entirely) and selects/deselects ALL
        # rows of a base course at once, including every group/run variant.
        # There is no mandatory-vs-choice component resolution here - that
        # nuance only exists in "module" mode; this mode is meant for
        # students who just want "give me everything under this course
        # name" without picking between parallel group offerings.
        grouped: dict[str, list[tuple[int, Any, str, bool]]] = {}
        for module_id, module in filtered_with_ids:
            base, variant, name_exam_flag = _split_course_variant(module.modulname)
            is_exam = bool(getattr(module, "ist_pruefung", False) or name_exam_flag)
            grouped.setdefault(base, []).append((module_id, module, variant, is_exam))

        group_rows = []
        selected_bases_prev = set(st.session_state.get("selected_course_bases", []))
        for base, items in sorted(grouped.items(), key=lambda item: item[0].lower()):
            dates = sorted({it[1].datum for it in items if getattr(it[1], "datum", None) is not None})
            variants = sorted({it[2] for it in items if it[2]})
            exam_count = sum(1 for it in items if it[3])
            first_date = dates[0].strftime("%Y-%m-%d") if dates else ""
            last_date = dates[-1].strftime("%Y-%m-%d") if dates else ""
            date_range = f"{first_date} - {last_date}" if first_date and last_date else ""
            default_selected = base in selected_bases_prev

            group_rows.append(
                {
                    c("select"): default_selected,
                    c("base_course"): base,
                    c("rows"): len(items),
                    c("variants_count"): len(variants),
                    c("exam_dates"): exam_count,
                    c("period"): date_range,
                }
            )

        df_groups = pd.DataFrame(group_rows)
        edited_groups = st.data_editor(
            df_groups,
            hide_index=True,
            width="stretch",
            disabled=[c("base_course"), c("rows"), c("variants_count"), c("exam_dates"), c("period")],
            column_config={c("select"): st.column_config.CheckboxColumn(c("select"))},
            key="course_group_selector_editor",
        )

        selected_bases = set(edited_groups.loc[edited_groups[c("select")] == True, c("base_course")].tolist())
        st.session_state.selected_course_bases = sorted(selected_bases)

        selected_modules = []
        for base, items in grouped.items():
            if base not in selected_bases:
                continue
            for _, module, _, is_exam in items:
                if (not include_exams) and is_exam:
                    continue
                selected_modules.append(module)

        with st.expander(t("guided.course_details_expander")):
            for base, items in sorted(grouped.items(), key=lambda item: item[0].lower()):
                variant_labels = sorted({it[2] if it[2] else "STANDARD" for it in items})
                exam_count = sum(1 for it in items if it[3])
                st.markdown(f"**{base}**")
                st.caption(t("guided.course_details_caption", variants=", ".join(variant_labels), exams=exam_count))

    else:
        # "row" mode: the finest-grained option - every individual filtered
        # schedule row gets its own checkbox in a flat data_editor table, no
        # grouping/variant logic at all. `module_id` (the row's position in
        # the master all_modules list, from filtered_with_ids) is stashed in
        # the table itself (c("id") column) purely so the edited table can
        # be mapped back to module objects below via `selected_ids`/
        # `modules_with_id`, since data_editor returns a plain DataFrame,
        # not the original objects.
        rows = []
        excluded_exam_rows = 0
        for module_id, module in filtered_with_ids:
            _, _, is_exam = _split_course_variant(module.modulname)
            if (not include_exams) and is_exam:
                excluded_exam_rows += 1
                continue
            rows.append(_module_to_row(module, module_id, selected_lookup.get(id(module), False)))

        if excluded_exam_rows:
            st.caption(t("guided.exams_hidden_caption", count=excluded_exam_rows))

        df_choice = pd.DataFrame(rows)
        edited = st.data_editor(
            df_choice,
            hide_index=True,
            width="stretch",
            disabled=[
                c("id"),
                c("module_no"),
                c("course_no"),
                c("module"),
                c("weekday"),
                c("date"),
                c("start"),
                c("end"),
                c("exam"),
                c("type"),
                c("lecturers"),
                c("ects"),
            ],
            column_config={
                c("select"): st.column_config.CheckboxColumn(c("select")),
                # Explicit typed columns instead of leaving these as plain
                # text: consistent locale-aware formatting, right-alignment
                # for the numeric column, and a narrower default width than
                # a free-text column would get (this table gets wide fast
                # with 12+ columns, so every column that doesn't need full
                # text width helps keep it scannable without horizontal
                # scrolling).
                c("date"): st.column_config.DateColumn(c("date"), format="DD.MM.YYYY", width="small"),
                c("start"): st.column_config.TimeColumn(c("start"), format="HH:mm", width="small"),
                c("end"): st.column_config.TimeColumn(c("end"), format="HH:mm", width="small"),
                c("ects"): st.column_config.NumberColumn(c("ects"), width="small"),
            },
            key="course_selector_editor",
        )

        selected_ids = set(edited.loc[edited[c("select")] == True, c("id")].tolist())
        selected_modules = [m for idx, m in modules_with_id if idx in selected_ids]

    st.info(t("guided.current_selection", selected=len(selected_modules), filtered=len(filtered)))
    st.session_state.selected_modules = selected_modules
    return selected_modules


# ==========================================
# 4. MAIN UI COMPONENTS
# ==========================================
# Im Abschnitt # 4. MAIN UI COMPONENTS die render_sidebar anpassen:

def render_sidebar() -> None:
    """
    Renders the sidebar: UI language switch, file upload, target-ECTS
    setting, and (once data exists) the export section.

    Side effects on st.session_state: ui_language (from the language
    selectbox), target_ects (from the number input, read by render_dashboard
    to show progress against a goal), and - indirectly, via
    handle_file_upload()/the "file removed" branch below - raw_data,
    processed_modules, conflicts, selected_modules and
    selected_course_bases.
    """
    with st.sidebar:
        st.header(t("sidebar.header"))
        st.markdown(t("sidebar.description"))

        with card("sidebar-data", "📁", t("sidebar.section.data")):
            language_options = {
                t("sidebar.language_option.de"): "de",
                t("sidebar.language_option.en"): "en",
                t("sidebar.language_option.fr"): "fr",
            }
            selected_language = st.selectbox(
                t("sidebar.language"),
                options=list(language_options.keys()),
                index=["de", "en", "fr"].index(st.session_state.get("ui_language", "de")),
                key="sidebar_language_selector",
            )
            st.session_state.ui_language = language_options[selected_language]

            # Light/Dark toggle: only writes st.session_state.ui_theme here;
            # _inject_design_system_css() (called unconditionally at the top
            # of every script run, before this function even executes) is
            # what actually re-renders the CSS on the *next* rerun that this
            # toggle triggers - there's nothing else to "apply" here.
            dark_mode = st.toggle(
                t("sidebar.theme_dark_toggle"),
                value=st.session_state.get("ui_theme", "dark") == "dark",
                key="sidebar_theme_toggle",
                help=t("sidebar.theme_help"),
            )
            st.session_state.ui_theme = "dark" if dark_mode else "light"

            uploaded_file = st.file_uploader(
                t("sidebar.upload_label"),
                type=["csv", "xlsx", "xls"],
                help=t("sidebar.upload_help")
            )

            if uploaded_file is not None:
                # Only trigger processing if a new file is uploaded or state is empty.
                # Streamlit reruns this function on every interaction (including
                # ones unrelated to the uploader, e.g. toggling a checkbox
                # elsewhere), and st.file_uploader keeps returning the same
                # UploadedFile on every rerun as long as the widget still shows
                # it - so without this guard we'd re-parse the file on every
                # single rerun. `uploaded_file.name not in str(st.session_state.
                # raw_data)` is an intentionally cheap heuristic: stringifying
                # the cached raw dataframe and substring-checking the new
                # file's name against it is enough to detect "this is a
                # different file than what we already parsed" without storing
                # a separate filename field in session state.
                if st.session_state.raw_data is None or uploaded_file.name not in str(st.session_state.raw_data):
                    with st.spinner(t("sidebar.parsing")):
                        handle_file_upload(uploaded_file)
            else:
                # Reset state if file is removed
                st.session_state.raw_data = None
                st.session_state.processed_modules = []
                st.session_state.conflicts = []
                st.session_state.selected_modules = []
                st.session_state.selected_course_bases = []

        with card("sidebar-settings", "🎯", t("sidebar.section.settings")):
            target_ects = st.number_input(t("sidebar.target_ects"), min_value=0, max_value=60, value=30, step=1)
            st.session_state.target_ects = target_ects

        if st.session_state.processed_modules:
            st.divider()
            modules_for_export = st.session_state.get("selected_modules") or st.session_state.processed_modules
            render_export_section(modules_for_export)


def render_dashboard(modules: List, target_ects: int, all_modules: List[Any]) -> None:
    """
    Render the Dashboard tab: headline metrics, absence-rule impact, and
    analysis charts/tables for the student's current selection.

    Args:
        modules: the student's currently selected modules (drives most
            metrics/charts - this is "their" data).
        target_ects: the ECTS goal from the sidebar's number_input, used
            only to compute the ECTS metric's delta (over/under target).
        all_modules: the full uploaded dataset (unfiltered/unselected),
            used only for the "all data" absence-impact table so the
            student can see absence conflicts across everything on offer,
            not just what they've already picked.

    Renders (in order): a KPI metrics row, an absence-rules summary with
    per-rule conflict tables, weekday/overlap/semester-timeline/daily-load
    charts, and finally a KPI/exam-status/overlap-rate tables section. Pure
    rendering - does not mutate st.session_state.
    """
    st.subheader(t("dashboard.subheader"))

    if not modules:
        st.info(t("dashboard.no_modules"))
        return

    st.caption(t("dashboard.caption"))

    total_ects = sum(m.ects for m in modules)
    total_modules = len(modules)
    unique_days = len(set(_weekday_label(m) for m in modules))
    total_pruefungen = sum(1 for m in modules if getattr(m, "ist_pruefung", False))
    conflict_pairs = find_time_conflicts(modules)
    selected_base_count = len({_module_group_title(m) for m in modules})
    lessons_per_week, hours_per_week, observed_weeks = _lessons_per_week(modules)
    absence_settings = _absence_settings()
    absence_rules = _absence_rules_summary(absence_settings)
    absence_selected_df = _absence_conflict_dataframe(modules, absence_settings)
    absence_all_df = _absence_conflict_dataframe(all_modules, absence_settings)
    absence_course_df = _absence_course_impact_dataframe(modules, absence_settings)

    with card("dash-metrics", "📊", t("dashboard.section.metrics")):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(t("dashboard.metric.ects"), total_ects, delta=total_ects - target_ects)
            # A single-glance "how full is the semester" bar alongside the
            # raw number/delta - the classic "workload balance" visual from
            # student-planner apps (progress toward a goal is one of the
            # few metrics here that's a pure 0..100% magnitude with one
            # good direction, exactly what st.progress()/a ProgressColumn
            # is for - unlike overlap%/absence% below, which are severity
            # metrics and stay on the red-toned Styler treatment instead).
            if target_ects > 0:
                progress_ratio = min(total_ects / target_ects, 1.0)
                st.progress(progress_ratio, text=t("dashboard.metric.ects_progress", pct=round(progress_ratio * 100)))
        with col2:
            st.metric(t("dashboard.metric.rows"), total_modules)
        with col3:
            st.metric(t("dashboard.metric.base_courses"), selected_base_count)
        with col4:
            st.metric(t("dashboard.metric.exams"), total_pruefungen)

        col5, col6 = st.columns(2)
        with col5:
            st.metric(t("dashboard.metric.weekdays"), unique_days)
        with col6:
            st.metric(t("dashboard.metric.lessons"), lessons_per_week)
            st.caption(t("dashboard.metric.lessons_caption", hours=hours_per_week, weeks=observed_weeks))

        col7, col8 = st.columns(2)
        with col7:
            st.metric(t("dashboard.metric.absence_rules"), len(absence_rules))
        with col8:
            st.metric(t("dashboard.metric.absence_rows"), len(absence_selected_df))

    with card("dash-absence", "🧭", t("dashboard.section.absence")):
        if not absence_rules:
            st.info(t("dashboard.absence.none"))
        else:
            st.caption(t("dashboard.absence.active"))
            for rule in absence_rules:
                st.markdown(f"- {rule}")

            st.markdown(t("dashboard.absence.current_selection"))
            if absence_selected_df.empty:
                st.success(t("dashboard.absence.current_selection_none"))
            else:
                st.warning(t("dashboard.absence.current_selection_conflicts", count=len(absence_selected_df)))
                st.dataframe(_style_absence_rows(absence_selected_df, c("reason")), hide_index=True, width="stretch")

            st.markdown(t("dashboard.absence.course_impact_title"))
            if absence_course_df.empty:
                st.info(t("dashboard.absence.course_impact_none"))
            else:
                st.caption(t("dashboard.absence.course_impact_caption"))
                st.dataframe(_style_risk_rows(absence_course_df), hide_index=True, width="stretch")

            st.markdown(t("dashboard.absence.all_data"))
            if absence_all_df.empty:
                st.info(t("dashboard.absence.all_data_none"))
            else:
                st.caption(t("dashboard.absence.all_data_caption", count=len(absence_all_df)))
                st.dataframe(absence_all_df.head(50), hide_index=True, width="stretch")

    overlap_summary = _calculate_module_overlap_summary(modules)
    exam_df = _calculate_exam_feasibility(modules)

    # --- Visuals: each chart gets its own collapsed "settings" panel
    # (palette/scale, weekday filter, extra chart-specific options) via
    # _render_chart_toolbar() - see that function's docstring for the
    # rationale (progressive disclosure: advanced controls stay out of the
    # way until opened, but every chart is genuinely user-customizable
    # rather than a fixed, one-size-fits-all image). ------------------
    with card("dash-visuals", "📈", t("dashboard.section.visuals")):
        chart_col1, chart_col2 = st.columns([1.2, 1])
        with chart_col1:
            st.markdown(t("dashboard.chart.weekday_title"))
            st.caption(t("dashboard.chart.weekday_caption"))
            weekday_modules, weekday_palette, _ = _render_chart_toolbar(
                "dash_weekday", modules, show_weekday_filter=True
            )
            fig = _weekday_bar_figure(weekday_modules, color_sequence=weekday_palette)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
        with chart_col2:
            st.markdown(t("dashboard.chart.overlap_title"))
            st.caption(t("dashboard.chart.overlap_caption"))
            _, overlap_scale, _ = _render_chart_toolbar(
                "dash_overlap", modules, continuous=True, show_weekday_filter=False
            )
            fig = _overlap_bar_figure(overlap_summary, color_scale=overlap_scale)
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.markdown(t("dashboard.section.semester_timeline"))
        st.caption(t("dashboard.chart.semester_caption"))
        timeline_modules, timeline_palette, timeline_choices = _render_chart_toolbar(
            "dash_timeline",
            modules,
            show_weekday_filter=True,
            extra_options={
                "color_by": [
                    (t("chart.color_by_module"), "module"),
                    (t("chart.color_by_type"), "type"),
                ]
            },
        )
        semester_timeline = _semester_timeline_figure(
            timeline_modules, color_sequence=timeline_palette, color_by=timeline_choices.get("color_by", "module")
        )
        if semester_timeline is not None:
            st.plotly_chart(semester_timeline, use_container_width=True)
        else:
            st.info(t("dashboard.chart.no_dated_rows"))

        st.divider()
        st.markdown(t("dashboard.section.daily_load"))
        st.caption(t("dashboard.chart.daily_load_caption"))
        load_modules, load_palette, load_choices = _render_chart_toolbar(
            "dash_load",
            modules,
            show_weekday_filter=True,
            extra_options={
                "view_mode": [
                    (t("chart.view_total"), "total"),
                    (t("chart.view_by_module"), "split"),
                ]
            },
        )
        daily_load = _daily_load_figure(
            load_modules, color_sequence=load_palette, split_by_module=load_choices.get("view_mode") == "split"
        )
        if daily_load is not None:
            st.plotly_chart(daily_load, use_container_width=True)
        else:
            st.info(t("dashboard.chart.no_dated_rows"))

    with card("dash-kpis", "🧮", t("dashboard.section.kpis").strip("*")):
        summary_table = pd.DataFrame(
            [
                {c("metric"): t("dashboard.kpi.conflict_pairs"), c("value"): len(conflict_pairs)},
                {c("metric"): t("dashboard.kpi.modules_overlap"), c("value"): int((overlap_summary[c("overlap_total_min")] > 0).sum()) if not overlap_summary.empty else 0},
                {c("metric"): t("dashboard.kpi.avg_overlap"), c("value"): round(overlap_summary[c("overlap_total_min")].mean(), 1) if not overlap_summary.empty else 0},
            ]
        )
        st.dataframe(summary_table, hide_index=True, width="stretch")

        if not exam_df.empty:
            st.markdown(t("dashboard.section.exam_status"))
            exam_status_tones = {
                t("exam.status_ok"): "success",
                t("exam.status_conflict"): "danger",
                t("exam.status_unknown"): "warning",
            }
            st.dataframe(
                _style_status_column(exam_df, c("status"), exam_status_tones),
                hide_index=True,
                width="stretch",
                column_config={c("date"): st.column_config.DateColumn(c("date"), format="DD.MM.YYYY")},
            )

        if not overlap_summary.empty:
            st.markdown(t("dashboard.section.overlap_rate"))
            st.dataframe(
                # Same sequential-red severity encoding as the detailed
                # conflict table in render_conflict_analysis (higher
                # overlap % = darker red) - one visual language for
                # "how bad is this overlap" across every tab, not a
                # different treatment per table.
                _style_sequential_red(overlap_summary, c("overlap_pct")),
                hide_index=True,
                width="stretch",
                column_config={
                    c("duration_min"): st.column_config.NumberColumn(c("duration_min"), format="%d min"),
                    c("overlap_total_min"): st.column_config.NumberColumn(c("overlap_total_min"), format="%d min"),
                    c("overlap_pct"): st.column_config.NumberColumn(c("overlap_pct"), format="%.1f %%"),
                },
            )

def render_timetable(modules: List) -> None:
    """
    Render the Timetable tab: a "typical week" Gantt chart
    (_weekly_timeline_figure, with any blocked-weekday absence overlay)
    followed by a day-by-day text breakdown of every selected module,
    ordered Monday-first.

    A day's expander is shown even when it has zero selected modules, as
    long as it's a currently blocked weekday (day_blocked) - the point is to
    surface "you have marked yourself unavailable on this day" even with no
    scheduled entries yet, not just to list existing rows. `expanded=
    day_blocked` additionally auto-opens (rather than collapses) any blocked
    day's expander by default, since that's the information most worth a
    student's immediate attention.
    """
    st.subheader(t("timetable.subheader"))

    if not modules:
        st.warning(t("timetable.no_modules"))
        return

    with card("timetable-chart", "🗓️", t("timetable.section.chart")):
        st.caption(t("timetable.caption"))
        fig = _weekly_timeline_figure(modules)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

    with card("timetable-daily", "📋", t("timetable.section.daily_details")):
        settings = _absence_settings()
        blocked_days = settings.get("blocked_days", set()) if settings.get("blocked_enabled") else set()
        day_order = _weekday_labels_in_order()
        for day in day_order:
            daily_mods = sorted([m for m in modules if _weekday_label(m) == day], key=lambda x: x.startzeit)
            day_key = _weekday_keys_in_order()[day_order.index(day)]
            day_blocked = day_key in blocked_days
            if not daily_mods and not day_blocked:
                continue

            with st.expander(t("timetable.day_expander", day=day, count=len(daily_mods)), expanded=day_blocked):
                if day_blocked:
                    st.error(t("timetable.blocked_day_warning", halfday=settings.get("blocked_halfday", t("guided.full_day"))))

                if daily_mods:
                    # A real table instead of stacked markdown/caption lines
                    # per entry: same information, but scannable as a grid
                    # (per this app's table-design principles - see
                    # docs/TESTING-README.md and the "column_config"
                    # conventions used throughout this file) rather than
                    # read top-to-bottom one field at a time. Absence
                    # conflicts get the same red row-tint used everywhere
                    # else in the app (_style_absence_rows), replacing the
                    # old one-off "🔴 " text prefix - one consistent visual
                    # language for "this row has an absence conflict"
                    # instead of a different convention per tab. The reason
                    # itself stays in its own column (not just the tint),
                    # so the signal is never color-alone.
                    day_rows = [
                        {
                            c("start"): mod.startzeit.strftime("%H:%M"),
                            c("end"): mod.endzeit.strftime("%H:%M"),
                            c("module"): mod.modulname,
                            c("exam"): t("guided.yes") if getattr(mod, "ist_pruefung", False) else t("guided.no"),
                            c("type"): mod.modultyp,
                            c("room"): mod.raum,
                            c("lecturers"): mod.dozierende,
                            c("reason"): ", ".join(_absence_reasons_for_module(mod, settings)),
                        }
                        for mod in daily_mods
                    ]
                    st.dataframe(
                        _style_absence_rows(pd.DataFrame(day_rows), c("reason")),
                        hide_index=True,
                        width="stretch",
                        column_config={
                            c("start"): st.column_config.TimeColumn(c("start"), format="HH:mm", width="small"),
                            c("end"): st.column_config.TimeColumn(c("end"), format="HH:mm", width="small"),
                        },
                    )

def render_conflict_analysis(conflicts: List[Tuple], selected_modules: List[Any], all_modules: List[Any]) -> None:
    """
    Render the Conflicts tab: time-overlap conflicts within the student's
    selection, plus absence-rule impact both for the selection and across
    the full dataset.

    Args:
        conflicts: pre-computed scheduler.find_time_conflicts() pairs for
            `selected_modules` (computed once by the caller in main() so it
            isn't recomputed here).
        selected_modules: the student's current selection.
        all_modules: the full uploaded dataset, used only for the "all
            data" absence-conflict table at the bottom (see
            render_dashboard for the same all_modules vs. modules split).

    When conflicts exist, renders a course-pair summary table
    (_summarize_conflicts), a per-conflict detail table, and three charts:
    top conflicting pairs (bar), overlap-by-weekday (pie), overlap-by-date
    (bar). Always renders the absence-impact section afterwards regardless
    of whether time conflicts were found, since absence rules are an
    orthogonal concern to time overlaps.
    """
    st.subheader(t("conflicts.subheader"))

    absence_settings = _absence_settings()
    absence_selected_df = _absence_conflict_dataframe(selected_modules, absence_settings)
    absence_all_df = _absence_conflict_dataframe(all_modules, absence_settings)
    absence_course_df = _absence_course_impact_dataframe(selected_modules, absence_settings)

    if not selected_modules and not conflicts and absence_all_df.empty:
        st.info(t("conflicts.empty_hint"))
        return

    if conflicts:
        st.error(t("conflicts.found", count=len(conflicts)))
    else:
        if absence_selected_df.empty:
            st.success(t("conflicts.none"))
        else:
            st.warning(t("conflicts.none_time_but_absence"))

    if conflicts:
        conflict_summary_df = _summarize_conflicts(conflicts)
        conflict_rows = []
        for left, right in conflicts:
            overlap = _minutes_overlap(left, right)
            left_duration = max(1, left.duration_minutes)
            right_duration = max(1, right.duration_minutes)
            conflict_rows.append(
                {
                    c("date"): _conflict_date_label(left),
                    c("weekday"): _weekday_label(left),
                    c("module_1"): _module_label(left),
                    c("module_2"): _module_label(right),
                    c("time_1"): f"{left.startzeit.strftime('%H:%M')} - {left.endzeit.strftime('%H:%M')}",
                    c("time_2"): f"{right.startzeit.strftime('%H:%M')} - {right.endzeit.strftime('%H:%M')}",
                    c("overlap_min"): overlap,
                    c("overlap_pct_module_1"): round((overlap / left_duration) * 100, 1),
                    c("overlap_pct_module_2"): round((overlap / right_duration) * 100, 1),
                }
            )

        conflict_df = pd.DataFrame(conflict_rows).sort_values([c("date"), c("overlap_min"), c("weekday")], ascending=[True, False, True])

        with card("conflicts-summary", "📊", t("conflicts.summary_title").strip("*")):
            if not conflict_summary_df.empty:
                st.dataframe(
                    conflict_summary_df,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        c("overlap_total_min"): st.column_config.NumberColumn(c("overlap_total_min"), format="%d min"),
                        c("conflict_days_count"): st.column_config.NumberColumn(c("conflict_days_count"), width="small"),
                    },
                )

            if not conflict_df.empty:
                top_conflicts = conflict_df.head(8).copy()
                fig = px.bar(
                    top_conflicts,
                    x=c("overlap_min"),
                    y=c("module_1"),
                    color=c("module_2"),
                    orientation="h",
                    title=t("chart.conflict_top"),
                )
                fig.update_layout(height=max(420, 44 * len(top_conflicts) + 120), margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(_apply_chart_theme(fig), use_container_width=True)

                by_day = conflict_df.groupby(c("weekday"), as_index=False)[c("overlap_min")].sum()
                fig_day = px.pie(by_day, values=c("overlap_min"), names=c("weekday"), title=t("conflicts.chart.by_weekday"))
                fig_day.update_layout(height=360, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(_apply_chart_theme(fig_day), use_container_width=True)

                by_date = conflict_df.groupby(c("date"), as_index=False)[c("overlap_min")].sum()
                fig_date = px.bar(by_date, x=c("date"), y=c("overlap_min"), title=t("conflicts.chart.by_date"))
                fig_date.update_layout(height=340, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(_apply_chart_theme(fig_date), use_container_width=True)

        with card("conflicts-details", "🔬", t("conflicts.details_title").strip("*")):
            st.dataframe(
                _style_sequential_red(conflict_df, c("overlap_min")),
                hide_index=True,
                width="stretch",
                column_config={
                    c("overlap_min"): st.column_config.NumberColumn(c("overlap_min"), format="%d min"),
                    c("overlap_pct_module_1"): st.column_config.NumberColumn(c("overlap_pct_module_1"), format="%.1f %%"),
                    c("overlap_pct_module_2"): st.column_config.NumberColumn(c("overlap_pct_module_2"), format="%.1f %%"),
                },
            )
            st.markdown(t("conflicts.interpretation_title"))
            st.caption(t("conflicts.interpretation_text"))

    with card("conflicts-absence", "🧭", t("conflicts.absence_title").strip("*")):
        if absence_all_df.empty:
            st.info(t("conflicts.absence_none"))
        else:
            if absence_selected_df.empty:
                st.success(t("conflicts.absence_selected_none"))
            else:
                st.warning(t("conflicts.absence_selected_found", count=len(absence_selected_df)))
                st.dataframe(_style_absence_rows(absence_selected_df, c("reason")), hide_index=True, width="stretch")

            st.markdown(t("conflicts.absence_course_title"))
            if absence_course_df.empty:
                st.info(t("conflicts.absence_course_none"))
            else:
                st.dataframe(_style_risk_rows(absence_course_df), hide_index=True, width="stretch")

            st.caption(t("conflicts.absence_all_caption", count=len(absence_all_df)))
            st.dataframe(_style_absence_rows(absence_all_df.head(80), c("reason")), hide_index=True, width="stretch")

def render_raw_data() -> None:
    """
    Render the "Raw Data" tab: the originally uploaded data exactly as
    st.session_state.raw_data holds it (post header-detection, pre
    validation - see handle_file_upload/data_loader.load_schedule_from_
    dataframe), next to the currently selected modules in their cleaned,
    localized form. Lets a student cross-check "what did I actually upload"
    against "what did the app understand from it".
    """
    st.subheader(t("raw.subheader"))
    if st.session_state.raw_data is None:
        st.info(t("raw.no_data"))
        return

    raw_df = st.session_state.raw_data.copy()
    # Columns can be non-string labels here (raw_data may still have its
    # original header row promoted with mixed types, e.g. datetime/int
    # column names from an Excel sheet read with header=None before
    # data_loader's header-detection ran) - stringify both column labels and
    # any "object" dtype cell values so st.dataframe() never chokes on
    # unhashable/unrenderable raw types from the original upload.
    raw_df.columns = [str(col) for col in raw_df.columns]
    for col in raw_df.columns:
        if raw_df[col].dtype == "object":
            raw_df[col] = raw_df[col].astype(str)

    col1, col2 = st.columns([1.1, 0.9])
    with col1:
        with card("raw-original", "🗄️", t("raw.original").strip("*")):
            st.dataframe(raw_df, width="stretch", hide_index=True)

    with col2:
        with card("raw-help", "💡", t("raw.help_title").strip("*")):
            st.write(t("raw.help_text"))

        if st.session_state.get("selected_modules"):
            with card("raw-selected", "✅", t("raw.selected").strip("*")):
                sel_df = pd.DataFrame([_module_to_ui_row(m) for m in st.session_state.selected_modules])
                st.dataframe(sel_df, width="stretch", hide_index=True)

# ==========================================
# 5. MAIN APPLICATION CONTROLLER
# ==========================================
def main() -> None:
    """
    Main application loop - Streamlit calls this (via the __main__ guard
    below) once per script rerun, i.e. on every user interaction. Assembles
    the whole page: sidebar, title, and the five main tabs, wiring the
    guided-planning tab's returned selection into the other four tabs so
    they all stay consistent within a single rerun.

    Tab order/dependency: render_guided_planning() must run first (inside
    tab_guided) because its return value - the student's current selection -
    is what the dashboard/timetable/conflicts tabs render; `selected_modules`
    starts out defaulting to the full processed_modules list (so tabs have
    something sensible to show even before guided planning has run once) and
    is overwritten with the guided-planning result immediately after.
    Dashboard and conflicts additionally receive st.session_state.
    processed_modules (the full unfiltered dataset) so they can show
    "impact across everything on offer" alongside "impact on your
    selection" (see render_dashboard/render_conflict_analysis docstrings).
    """
    # Ensure backend modules are loaded before rendering the app
    if not MODULES_AVAILABLE:
        st.stop()

    # Render Sidebar
    render_sidebar()

    st.title(t("app.title"))
    st.markdown(t("app.subtitle"))

    with card("app-quickstart", "🚀", t("app.quickstart_title")):
        st.caption(t("app.quickstart_text"))

    selected_modules = st.session_state.processed_modules

    # Create UI Tabs for a cleaner application state
    tab_guided, tab_dashboard, tab_timetable, tab_conflicts, tab_data = st.tabs([
        t("app.tab.guided"),
        t("app.tab.dashboard"),
        t("app.tab.timetable"),
        t("app.tab.conflicts"),
        t("app.tab.raw")
    ])

    with tab_guided:
        # This call also writes its result to st.session_state.selected_modules
        # (see render_guided_planning's docstring); the local variable here is
        # what feeds the remaining tabs within this same script run.
        selected_modules = render_guided_planning(st.session_state.processed_modules)

    # Render Content in Tabs
    with tab_dashboard:
        render_dashboard(selected_modules, st.session_state.get('target_ects', 30), st.session_state.processed_modules)

    with tab_timetable:
        if selected_modules:
            render_timetable(selected_modules)
        else:
            st.info(t("app.info.no_selection_guided"))

    with tab_conflicts:
        if selected_modules:
            # Recompute conflicts here (rather than reusing
            # st.session_state.conflicts, which was computed against the full
            # upload in handle_file_upload) since this needs conflicts
            # specifically within the student's current selection.
            selected_conflicts = find_time_conflicts(selected_modules)
            render_conflict_analysis(selected_conflicts, selected_modules, st.session_state.processed_modules)
        else:
            render_conflict_analysis([], selected_modules, st.session_state.processed_modules)

    with tab_data:
        render_raw_data()

# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    main()