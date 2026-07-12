"""
ZHAW MSc Psychology - Timetable Planner (Presentation Layer)
Author: HealthData CodeArchitect
Description: Advanced Streamlit GUI focusing on state-of-the-art UI/UX, 
robust error handling, and separation of concerns.
"""

import streamlit as st
import pandas as pd
from typing import List, Tuple, Any
from export import prepare_timetable_for_export, generate_excel_download

# Assuming these are available from the previously defined business/data logic layers
try:
    from data_loader import load_schedule_from_dataframe
    from scheduler import find_time_conflicts
    from models import ZHAWModule
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    st.error(f"System Error: Backend modules missing. {e}")

# ==========================================
# 1. PAGE CONFIGURATION & CUSTOM STYLING
# ==========================================
st.set_page_config(
    page_title="ZHAW Planner Pro",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Optional: Inject minimal custom CSS for cleaner metric cards and dataframe styling
st.markdown("""
    <style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 1px 1px 5px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SESSION STATE INITIALIZATION
# ==========================================
def init_session_state() -> None:
    """Initializes default variables in Streamlit's session state."""
    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'processed_modules' not in st.session_state:
        st.session_state.processed_modules = []
    if 'conflicts' not in st.session_state:
        st.session_state.conflicts = []

init_session_state()

# ==========================================
# 3. HELPER FUNCTIONS (UI LOGIC)
# ==========================================
def handle_file_upload(uploaded_file: Any) -> None:
    """
    Handles the parsing of the uploaded file with comprehensive error handling.
    Supports CSV and Excel files.
    """
    try:
        # Determine file type and parse accordingly
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif uploaded_file.name.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Unsupported file format. Please upload a CSV or Excel file.")
            return

        # Check if the dataframe is empty
        if df.empty:
            st.warning("The uploaded file is empty. Please provide a valid dataset.")
            return

        # Store raw data in session state
        st.session_state.raw_data = df
        
        # Process data through the data loader (validation layer)
        st.session_state.processed_modules = load_schedule_from_dataframe(df)
        
        # Run business logic (conflict detection)
        st.session_state.conflicts = find_time_conflicts(st.session_state.processed_modules)
        
        # User feedback
        st.toast("Data successfully loaded and validated!", icon="✅")

    except ValueError as ve:
        # Catch specific Pydantic validation errors from the data layer
        st.error(f"Data Validation Error: {ve}")
        st.info("Please check your file format. Ensure columns like 'Startzeit' and 'Endzeit' are formatted correctly.")
    except Exception as e:
        # Catch unforeseen errors (e.g., corrupted file)
        st.error(f"An unexpected error occurred during processing: {e}")

# ==========================================
# 4. MAIN UI COMPONENTS
# ==========================================
def render_sidebar() -> None:
    """Renders the sidebar for data upload and global settings."""
    with st.sidebar:
        st.header("⚙️ Control Panel")
        st.markdown("Upload your module schedule here.")
        
        # File uploader widget
        uploaded_file = st.file_uploader(
            "Select Timetable File", 
            type=["csv", "xlsx", "xls"],
            help="Upload the official ZHAW export or a properly formatted CSV/Excel sheet."
        )
        
        if uploaded_file is not None:
            # Only trigger processing if a new file is uploaded or state is empty
            if st.session_state.raw_data is None or uploaded_file.name not in str(st.session_state.raw_data):
                with st.spinner('Parsing and validating data...'):
                    handle_file_upload(uploaded_file)
        else:
            # Reset state if file is removed
            st.session_state.raw_data = None
            st.session_state.processed_modules = []
            st.session_state.conflicts = []

        st.divider()
        st.subheader("Target Configuration")
        # Example of adding interactive UI settings for user preferences
        target_ects = st.number_input("Target ECTS for this semester", min_value=0, max_value=60, value=30, step=1)
        st.session_state.target_ects = target_ects

def render_dashboard(modules: List, target_ects: int) -> None:
    """Renders the high-level metrics and overview dashboard."""
    st.subheader("📈 Semester Overview")
    
    if not modules:
        st.info("Awaiting data. Please upload your module schedule via the sidebar.")
        return

    # Calculate key metrics
    total_ects = sum(m.ects for m in modules)
    unique_days = len(set(m.wochentag for m in modules))
    total_modules = len(modules)
    
    # Display metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Delta shows difference to user's target
        ects_delta = total_ects - target_ects
        st.metric("Total ECTS", f"{total_ects}", delta=ects_delta, help="Green delta means exceeding target, red means below.")
    with col2:
        st.metric("Total Modules", total_modules)
    with col3:
        st.metric("Days on Campus", unique_days)
    with col4:
        # Example of a derived metric: Average ECTS per module
        avg_ects = round(total_ects / total_modules, 1) if total_modules > 0 else 0
        st.metric("Avg. ECTS / Module", avg_ects)

def render_timetable(modules: List) -> None:
    """Renders a structured, day-by-day view of the schedule."""
    st.subheader("📅 Weekly Schedule")
    
    if not modules:
        st.warning("No validated modules available to display.")
        return

    # Group modules by day
    days_order = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    modules_by_day = {day: [] for day in days_order}
    
    for mod in modules:
        if mod.wochentag in modules_by_day:
            modules_by_day[mod.wochentag].append(mod)
        else:
            # Fallback for unexpected day strings
            modules_by_day.setdefault("Other", []).append(mod)

    # Display schedule using Streamlit Expanders for clean UI
    for day in days_order + ["Other"]:
        daily_mods = modules_by_day.get(day, [])
        if daily_mods:
            # Sort chronologically
            daily_mods.sort(key=lambda x: x.startzeit)
            
            with st.expander(f"📌 {day} ({len(daily_mods)} Modules)", expanded=True):
                for mod in daily_mods:
                    st.markdown(
                        f"**{mod.startzeit.strftime('%H:%M')} - {mod.endzeit.strftime('%H:%M')}** | "
                        f"*{mod.modultyp}* | "
                        f"**{mod.modulname}** (ECTS: {mod.ects})"
                    )
                    if mod.dozierende and mod.dozierende != "nan":
                        st.caption(f"👨‍🏫 Lecturer: {mod.dozierende}")

def render_conflict_analysis(conflicts: List[Tuple]) -> None:
    """Renders the algorithmic conflict detection results."""
    st.subheader("⚠️ Conflict Analysis")
    
    if not conflicts:
        st.success("Excellent! The algorithm detected **0** time conflicts in your current schedule.")
        # Render a celebratory graphic/animation (optional but good for UX)
        st.balloons()
        return
    
    st.error(f"Critical Scheduling Error: Detected {len(conflicts)} overlapping modules!")
    
    # Iterate through conflicts and present them clearly
    for i, (mod1, mod2) in enumerate(conflicts, 1):
        st.warning(f"**Conflict #{i} - {mod1.wochentag}**")
        
        colA, colB = st.columns(2)
        with colA:
            st.markdown(f"🔴 **Module 1:** {mod1.modulname}")
            st.markdown(f"🕒 Time: `{mod1.startzeit.strftime('%H:%M')} - {mod1.endzeit.strftime('%H:%M')}`")
        with colB:
            st.markdown(f"🔴 **Module 2:** {mod2.modulname}")
            st.markdown(f"🕒 Time: `{mod2.startzeit.strftime('%H:%M')} - {mod2.endzeit.strftime('%H:%M')}`")
        
        st.divider()

def render_raw_data() -> None:
    """Displays the raw dataframe for transparency and debugging."""
    st.subheader("🗄️ Raw Data Source")
    if st.session_state.raw_data is not None:
        st.dataframe(
            st.session_state.raw_data, 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("No data loaded.")

# ==========================================
# 5. MAIN APPLICATION CONTROLLER
# ==========================================
def main() -> None:
    """Main application loop."""
    # Ensure backend modules are loaded before rendering the app
    if not MODULES_AVAILABLE:
        st.stop()

    st.title("🎓 ZHAW MSc Psychology Planner")
    st.markdown("Advanced algorithmic scheduling and conflict detection for modular study paths.")
    
    # Render Sidebar
    render_sidebar()

    # Create UI Tabs for a cleaner application state
    tab_dashboard, tab_timetable, tab_conflicts, tab_data = st.tabs([
        "📊 Dashboard", 
        "📅 Weekly Schedule", 
        "⚠️ Conflict Analysis", 
        "🗄️ Raw Data"
    ])
    
    # Render Content in Tabs
    with tab_dashboard:
        render_dashboard(st.session_state.processed_modules, st.session_state.get('target_ects', 30))
        
    with tab_timetable:
        if st.session_state.processed_modules:
            render_timetable(st.session_state.processed_modules)
        else:
            st.info("Upload data to view your schedule.")
            
    with tab_conflicts:
        if st.session_state.processed_modules:
            render_conflict_analysis(st.session_state.conflicts)
        else:
            st.info("Upload data to run the conflict algorithm.")
            
    with tab_data:
        render_raw_data()

# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    main()