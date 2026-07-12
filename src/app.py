import streamlit as st
import pandas as pd
from data_loader import load_schedule_from_dataframe
from scheduler import find_time_conflicts

# --- Page Configuration ---
st.set_page_config(page_title="ZHAW MSc Psychology Planner", page_icon="📅", layout="wide")

st.title("🎓 ZHAW MSc Psychology - Timetable Planner")
st.markdown("Automatisierte Konfliktanalyse und Planung für flexible Studienmodelle.")

# --- File Upload (In-Memory Processing) ---
uploaded_file = st.file_uploader("Lade deinen Modulplan hoch (Excel/CSV)", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        # Abhängig vom Dateityp in Pandas laden
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success("Datei erfolgreich geladen und im Arbeitsspeicher gesichert.")
        
        # --- Data Layer Integration ---
        modules = load_schedule_from_dataframe(df)
        
        # --- Business Logic Integration ---
        conflicts = find_time_conflicts(modules)
        
        # --- Presentation Layer ---
        st.subheader("📊 Aktueller Stundenplan")
        st.dataframe(df, use_container_width=True)
        
        st.subheader("⚠️ Konfliktanalyse")
        if conflicts:
            st.error(f"Es wurden {len(conflicts)} zeitliche Überschneidungen gefunden!")
            for mod1, mod2 in conflicts:
                st.warning(f"**Überschneidung am {mod1.wochentag}:** \n"
                           f"- {mod1.modulname} ({mod1.startzeit.strftime('%H:%M')} - {mod1.endzeit.strftime('%H:%M')})\n"
                           f"- {mod2.modulname} ({mod2.startzeit.strftime('%H:%M')} - {mod2.endzeit.strftime('%H:%M')})")
        else:
            st.success("Perfekt! Es gibt keine zeitlichen Überschneidungen in deinem Plan.")

        # ECTS Counter
        total_ects = sum(m.ects for m in modules)
        st.metric(label="Geplante ECTS in diesem Semester", value=total_ects)

    except Exception as e:
        st.error(f"Fehler bei der Verarbeitung der Datei: {e}")

else:
    st.info("Bitte lade eine Datei hoch, um die Analyse zu starten.")