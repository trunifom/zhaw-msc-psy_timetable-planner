# zhaw-msc-psy_timetable-planner
Ein interaktives, Python-basiertes Planungstool zur systematischen und überschneidungsfreien Modul- und Stundenplanplanung für den Masterstudiengang Psychologie an der ZHAW. Bietet algorithmische Konflikterkennung und lokales, datenschutzkonformes In-Memory-Processing via Streamlit.

# ZHAW MSc Psychology - Timetable Planner 📅

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B.svg)](https://streamlit.io/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📚 Spezifikationen

- HealthData CodeArchitect (KI-Assistent): siehe `docs/HealthData-CodeArchitect.md`

## 📌 Über das Projekt

Der **ZHAW MSc Psychology Timetable Planner** ist eine massgeschneiderte Webapplikation zur effizienten Semesterplanung. Der Masterstudiengang Psychologie erfordert oft die Koordination flexibler Studienmodelle (Vollzeit vs. Teilzeit) sowie die Abstimmung diverser Wahlpflichtmodule. 

Dieses Tool automatisiert den Abgleich von Modulzeiten, identifiziert Vorlesungsüberschneidungen auf algorithmischer Ebene und visualisiert den resultierenden Stundenplan übersichtlich in einem interaktiven Dashboard.

## ✨ Hauptfunktionen

*   **Datenintegration & Bereinigung:** Automatisierter Upload von Modulplänen via Excel/CSV mit strenger Datentyp-Validierung (`pandas`, `pydantic`).
*   **Algorithmische Konfliktanalyse:** Systematische Prüfung von Zeitfenstern zur Vermeidung von Doppelbelegungen und zur Sicherstellung von minimalen Pausenzeiten.
*   **Interaktives GUI:** Benutzerfreundliches Frontend via Streamlit mit dynamischen Filtern (z.B. nach Vertiefungsrichtung, Dozierenden, Wochentagen).
*   **Export & Reporting:** Generierung exportierbarer, publikationsreifer Stundenpläne zur nahtlosen Integration in den akademischen Alltag.

## 🏗 Systemarchitektur (Separation of Concerns)

Das Projekt ist modular aufgebaut, um Skalierbarkeit und Testbarkeit zu maximieren:

1.  **Data Layer:** Zuständig für das Einlesen und Validieren der Rohdaten. Hier wird sichergestellt, dass fehlende Werte (NAs) und inkonsistente Datums-/Zeitformate systematisch bereinigt werden.
2.  **Business Logic Layer:** Kapselt die Logik der Konflikterkennung. Unabhängig vom Frontend, vollständig modular und Unit-Test-fähig.
3.  **Presentation Layer:** Das Streamlit-Frontend steuert das State-Management (`st.session_state`) und die Visualisierung, ohne direkte Datenmanipulationen vorzunehmen.

## 🔒 Datenschutz & Datensicherheit

Akademische Planungsdaten können potenziell sensible Informationen (Namen von Dozierenden, interne Raumzuweisungen) enthalten. Das System ist nach dem *Privacy by Design*-Prinzip konzipiert:
*   **In-Memory Processing:** Hochgeladene Dateien werden ausschliesslich im RAM der aktiven Nutzersession verarbeitet und nach dem Schliessen des Browsers rückstandslos verworfen.
*   **Keine Datenbank-Persistenz:** Es werden serverseitig keine Stundenpläne oder Nutzerprofile gespeichert.
*   **Repository-Richtlinien:** Reale Planungsdaten (`*.xlsx`, `*.csv`) sind strikt von der Versionskontrolle ausgeschlossen (`.gitignore`).

## 🚀 Lokales Setup (Development Environment)

Um Reproduzierbarkeit zu gewährleisten, nutzen wir **Anaconda** für das Environment-Management.

**1. Repository klonen:**
```bash
git clone [https://github.com/DEIN_USERNAME/zhaw-msc-psy_timetable-planner.git](https://github.com/DEIN_USERNAME/zhaw-msc-psy_timetable-planner.git)
cd zhaw-msc-psy_timetable-planner

**2. Conda-Umgebung initialisieren:**
conda create -n zhaw_planner_env python=3.10
conda activate zhaw_planner_env

**3. Abhängigkeiten installieren:**
pip install -r requirements.txt

**4. Applikation lokal starten:**
streamlit run app.py

## Projektstruktur
zhaw-msc-psy_timetable-planner/
│
├── data/                  # Lokale Rohdaten (von Git ignoriert)
├── src/                   # Quellcode-Verzeichnis
│   ├── app.py             # Streamlit Entry-Point
│   ├── data_loader.py     # Pandas Import-Logik
│   ├── models.py          # Pydantic Datenmodelle
│   └── scheduler.py       # Algorithmen zur Konfliktprüfung
│
├── tests/                 # Unit-Tests (pytest)
├── .gitignore             # Git Ignore-Regeln
├── requirements.txt       # Python-Abhängigkeiten
└── README.md              # Projektdokumentation
