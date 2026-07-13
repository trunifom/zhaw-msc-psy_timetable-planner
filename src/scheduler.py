"""
ZHAW MSc Psychology - Timetable Planner (GUI Layer)
Author: HealthData CodeArchitect
Description: Main entry point for the Streamlit GUI. 
Provides a highly interactive, error-resilient, and user-friendly interface 
for managing academic schedules. Built with strict separation of concerns,
state management, and comprehensive error handling.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import time, datetime
from typing import Iterable
from pydantic import ValidationError

# Import the strictly validated domain model and enum from our data layer
from models import ZHAWModule, Weekday


def _weekday_key(module: ZHAWModule) -> str:
    """Return a normalized weekday key for robust comparison."""
    value = getattr(module.wochentag, "value", module.wochentag)
    return str(value).strip().lower()


def _to_minutes(value: time) -> int:
    """Convert a time object to minutes since midnight."""
    return value.hour * 60 + value.minute


def _same_occurrence(left: ZHAWModule, right: ZHAWModule) -> bool:
    """Return True when two rows refer to the same schedulable occurrence."""
    left_date = getattr(left, "datum", None)
    right_date = getattr(right, "datum", None)
    if left_date is not None and right_date is not None:
        return left_date == right_date
    return _weekday_key(left) == _weekday_key(right)


def _semantic_signature(module: ZHAWModule) -> tuple:
    """Stable signature to suppress exact duplicate rows in conflict results."""
    return (
        getattr(module, "datum", None),
        _weekday_key(module),
        _to_minutes(module.startzeit),
        _to_minutes(module.endzeit),
        str(getattr(module, "modul_nr", "") or "").strip(),
        str(getattr(module, "kurs_nr", "") or "").strip(),
        str(getattr(module, "modulname", "") or "").strip(),
        str(getattr(module, "raum", "") or "").strip(),
    )


def find_time_conflicts(modules: Iterable[ZHAWModule]) -> list[tuple[ZHAWModule, ZHAWModule]]:
    """
    Detect overlapping modules on the same weekday.

    Returns:
        list[tuple[ZHAWModule, ZHAWModule]]: Pairs of conflicting modules.
    """
    module_list = list(modules or [])
    conflicts: list[tuple[ZHAWModule, ZHAWModule]] = []
    seen_pairs: set[tuple[tuple, tuple]] = set()

    for i, left in enumerate(module_list):
        left_start = _to_minutes(left.startzeit)
        left_end = _to_minutes(left.endzeit)
        left_signature = _semantic_signature(left)

        for right in module_list[i + 1 :]:
            if not _same_occurrence(left, right):
                continue

            right_signature = _semantic_signature(right)
            if left_signature == right_signature:
                continue

            right_start = _to_minutes(right.startzeit)
            right_end = _to_minutes(right.endzeit)

            # Intervals [a,b) and [c,d) overlap iff a < d and c < b.
            if left_start < right_end and right_start < left_end:
                pair_key = tuple(sorted((left_signature, right_signature)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                conflicts.append((left, right))

    return conflicts

# ==========================================
# 1. APPLICATION CONFIGURATION & STATE
# ==========================================

def setup_page_config():
    """
    Initializes the Streamlit page configuration.
    Sets a wide layout for better data visualization and UX.
    """
    st.set_page_config(
        page_title="ZHAW Schedule Architect",
        page_icon="📅",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS to improve UI aesthetics (cleaner padding, better typography)
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        h1 { color: #1E3A8A; font-weight: 700; }
        h2, h3 { color: #2563EB; }
        .stAlert { border-radius: 8px; }
        </style>
    """, unsafe_allow_html=True)


def init_session_state():
    """
    Initializes the reactive session state for the application.
    This ensures data persists across widget interactions and reruns.
    """
    if 'modules' not in st.session_state:
        # Pre-populate with a sample module for demonstration UX
        try:
            sample_module = ZHAWModule(
                modulname="Biostatistik & Epidemiologie",
                wochentag=Weekday.MONDAY,
                startzeit="08:15",
                endzeit="11:45",
                ects=5,
                modultyp="Vorlesung",
                dozierende="Dr. Müller",
                raum="Hörsaal 1"
            )
            st.session_state.modules = [sample_module]
        except ValidationError:
            st.session_state.modules = []


# ==========================================
# 2. UI COMPONENTS: SIDEBAR (INPUTS)
# ==========================================

def render_sidebar():
    """
    Renders the sidebar interface containing the form to add new modules.
    Implements robust error handling by catching Pydantic ValidationErrors
    and translating them into user-friendly UI alerts.
    """
    with st.sidebar:
        st.header("➕ Add New Module")
        st.markdown("Enter the module details below. Times must be logical.")

        with st.form("add_module_form", clear_on_submit=True):
            # Input fields logically grouped
            name = st.text_input("Module Name*", max_chars=150)
            
            col1, col2 = st.columns(2)
            with col1:
                # Use Enum values for safe selection, formatted nicely
                day = st.selectbox("Day*", [d.value.capitalize() for d in Weekday])
                ects = st.number_input("ECTS*", min_value=0, max_value=60, value=3)
            with col2:
                # Using standard time inputs to prevent format errors natively
                start = st.time_input("Start Time*", value=time(8, 15))
                end = st.time_input("End Time*", value=time(10, 0))

            st.divider()
            
            # Optional fields
            mod_type = st.text_input("Type (e.g., Seminar)", value="N/A")
            lecturer = st.text_input("Lecturer(s)", value="N/A")
            room = st.text_input("Room/Location", value="N/A")

            submitted = st.form_submit_button("Save Module", use_container_width=True)

            if submitted:
                handle_form_submission(name, day, start, end, ects, mod_type, lecturer, room)


def handle_form_submission(name, day, start, end, ects, mod_type, lecturer, room):
    """
    Processes the form data, attempts to instantiate a Pydantic model,
    and updates the session state or displays validation errors.
    """
    if not name.strip():
        st.error("Error: Module Name is strictly required.")
        return

    try:
        # Pydantic V2 will rigorously validate these inputs.
        # If 'end' is before 'start', our custom validator in models.py will raise an error.
        new_module = ZHAWModule(
            modulname=name,
            wochentag=day,
            startzeit=start,
            endzeit=end,
            ects=ects,
            modultyp=mod_type,
            dozierende=lecturer,
            raum=room
        )
        st.session_state.modules.append(new_module)
        st.success(f"Successfully added '{name}'!")
        
    except ValidationError as e:
        # Elegant error unrolling: Extract specific Pydantic errors for the UI
        for err in e.errors():
            field = err.get('loc')[0] if err.get('loc') else 'Validation'
            msg = err.get('msg')
            st.error(f"**{field.capitalize()} Error:** {msg}")
    except ValueError as ve:
        # Catch custom logical errors (e.g., end time <= start time)
        st.error(f"**Logic Error:** {str(ve)}")


# ==========================================
# 3. UI COMPONENTS: MAIN DASHBOARD (VIEWS)
# ==========================================

def render_kpi_dashboard():
    """
    Renders Key Performance Indicators (KPIs) at the top of the dashboard.
    Calculates metrics dynamically based on the current session state.
    """
    modules = st.session_state.modules
    
    total_modules = len(modules)
    total_ects = sum(m.ects for m in modules)
    total_minutes = sum(m.duration_minutes for m in modules)
    total_hours = round(total_minutes / 60, 1)

    # Use Streamlit metrics for a clean, high-level overview
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Total Modules", value=total_modules)
    with col2:
        st.metric(label="Total ECTS Credits", value=total_ects)
    with col3:
        st.metric(label="Weekly Contact Hours", value=f"{total_hours} h")


def render_timetable_visualization():
    """
    Generates an interactive Gantt-style timeline using Plotly Express.
    This provides an excellent UX for visualizing schedule overlaps and gaps.
    """
    modules = st.session_state.modules
    if not modules:
        st.info("No modules scheduled yet. Use the sidebar to add your classes.")
        return

    st.subheader("📊 Visual Timetable")

    # Data preparation for Plotly Timeline
    # We use a dummy date (1970-01-01) to solely focus on the time-of-day aspect
    dummy_date = "1970-01-01 "
    plot_data = []
    
    # Sort order to ensure days appear chronologically top-to-bottom on the Y-axis
    day_order = [d.value.capitalize() for d in Weekday]

    for m in modules:
        plot_data.append({
            "Module": m.modulname,
            "Day": m.wochentag.value.capitalize(),
            "Start": pd.to_datetime(dummy_date + m.startzeit.strftime("%H:%M:%S")),
            "End": pd.to_datetime(dummy_date + m.endzeit.strftime("%H:%M:%S")),
            "Lecturer": m.dozierende,
            "Room": m.raum
        })

    df = pd.DataFrame(plot_data)

    # Create Gantt chart
    fig = px.timeline(
        df, 
        x_start="Start", 
        x_end="End", 
        y="Day", 
        color="Module",
        hover_data=["Lecturer", "Room"],
        category_orders={"Day": day_order} # Enforce strict chronological day sorting
    )
    
    # Refine Plotly layout for better aesthetics
    fig.update_yaxes(autorange="reversed") # Standard Gantt behavior (Monday at top)
    fig.update_layout(
        xaxis_title="Time of Day",
        yaxis_title="",
        xaxis_tickformat="%H:%M", # Only show hours and minutes on X-axis
        margin=dict(l=20, r=20, t=30, b=20),
        height=400,
        plot_bgcolor="rgba(0,0,0,0)", # Transparent background
        paper_bgcolor="rgba(0,0,0,0)"
    )

    # Render interactive chart
    st.plotly_chart(fig, use_container_width=True)


def render_data_table():
    """
    Displays the raw data in an interactive Streamlit dataframe.
    Leverages the `to_ui_dict()` method from the domain model for clean serialization.
    """
    modules = st.session_state.modules
    if not modules:
        return

    st.subheader("📋 Data Overview & Export")
    
    # Convert list of Pydantic models to a list of dicts formatted for the UI
    ui_dicts = [m.to_ui_dict() for m in modules]
    df = pd.DataFrame(ui_dicts)
    
    # Interactive dataframe (allows sorting, column resizing, and CSV download natively)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )
    
    # Provide a simple export mechanism to CSV for UX completeness
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Schedule as CSV",
        data=csv,
        file_name='zhaw_schedule.csv',
        mime='text/csv',
    )


# ==========================================
# 4. MAIN EXECUTION FLOW
# ==========================================

def main():
    """
    The main orchestrator function. Sets up the environment, initializes state,
    and calls the UI rendering functions in logical order.
    """
    # 1. Setup Phase
    setup_page_config()
    init_session_state()

    # 2. Header
    st.title("🎓 ZHAW MSc Psychology - Schedule Architect")
    st.markdown("Plan, visualize, and analyze your semester timetable seamlessly.")
    st.divider()

    # 3. Sidebar Input
    render_sidebar()

    # 4. Main Views
    render_kpi_dashboard()
    st.write("") # Spacer
    render_timetable_visualization()
    st.write("") # Spacer
    render_data_table()


if __name__ == "__main__":
    # Standard Python guard ensuring the app runs cleanly via `streamlit run`
    main()