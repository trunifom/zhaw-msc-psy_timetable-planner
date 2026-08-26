# ZHAW MSc Psychology Timetable Planner

Interaktive Streamlit-Anwendung für die modulbasierte Semesterplanung im MSc Psychologie (ZHAW) mit Fokus auf:

- robuste Excel/CSV-Imports
- geführte Studienplanung
- konfliktsichere Terminwahl
- Visualisierung über Woche und Semester
- Export als Excel und ICS

## Ziel des Tools

Die App hilft Studierenden, aus ZHAW-Exportdaten einen realistisch belegbaren Stundenplan zusammenzustellen.
Besonders unterstützt werden:

- Modul- und Kurslogik mit Varianten/Gruppen
- Konflikterkennung mit Datumskontext
- Prüfungsprüfung gegen gewählte Termine
- transparente Rohdatenansicht

## Feature-Überblick

- Geführte Planung mit dynamischen Fragen (Abwesenheit, Tage, Halbtage, Filter)
- Auswahlmodi:
	- modulbasiert (empfohlen)
	- kursbasiert
	- zeilenbasiert
- Konfliktanalyse mit:
	- Paar-Zusammenfassung
	- Detailansicht nach Datum und Uhrzeit
	- Überlappungsminuten und Prozentwerten
- Design-System (durchgängig, Light/Dark umschaltbar über die Sidebar):
	- einheitliche Karten-Sektionen (Icon + Titel + Trennlinie) statt reiner Whitespace-Trennung
	- konsistente Semantikfarben (Erfolg/Warnung/Kritisch/Info) über die ganze App
	- aktuell als Pilot im Dashboard-Tab umgesetzt, Rollout auf die restlichen Tabs folgt
- Visualisierung (Dashboard-Charts sind interaktiv anpassbar über ein "🎨 Diagramm-Einstellungen"-Panel):
	- Wochen-Timeline
	- Semester-Timeline (Farbe wählbar nach Modul oder Modulart)
	- Tageslast über den gesamten Zeitraum (Gesamt- oder nach Modul aufgeschlüsselte Ansicht)
	- Wochentagsverteilung
	- pro Chart: Farbpalette (inkl. farbenblind-sicher) bzw. Farbskala wählbar, Wochentage ein-/ausblendbar, native Plotly-Werkzeugleiste (Zoom, Pan, PNG-Export)
- Export:
	- XLSX
	- ICS (alle aktuell ausgewählten Termine, chronologisch sortiert):
		- Titel bleibt schlank, nur Prüfungen (⚠️) und Termine ohne Datum (❓) werden optisch markiert
		- Beschreibung mit Dozent:in, Modul-/Kurs-Nr, Modulart, ECTS, Anwesenheitspflicht
		- Prüfungen: 2 Erinnerungen (1 Tag + 2 Std. vorher), reguläre Termine ohne zusätzliche Erinnerung (nutzt den Kalender-Standard)
		- Kategorien pro Kursnummer für automatische Farbcodierung in Outlook/Apple Kalender
		- Termine ohne erkennbares Datum werden als ganztägiger, nicht-blockierender Platzhalter markiert statt stillschweigend zu fehlen
		- stabile UIDs: erneuter Export derselben Auswahl aktualisiert bestehende Kalendereinträge statt Duplikate zu erzeugen
- Mehrsprachigkeit (de/en/fr) über zentrale i18n-Keys

## Architektur

- Präsentation: [src/app.py](src/app.py)
- Import/Bereinigung: [src/data_loader.py](src/data_loader.py)
- Domänenmodell: [src/models.py](src/models.py)
- Konfliktlogik: [src/scheduler.py](src/scheduler.py)
- Exportlogik: [src/export.py](src/export.py)
- Übersetzungen: [src/i18n.py](src/i18n.py)
- i18n-Konventionen: [docs/i18n-README.md](docs/i18n-README.md)
- Test-Suite im Detail: [docs/TESTING-README.md](docs/TESTING-README.md)

## Schnellstart

### 1. Environment vorbereiten

Variante A: Conda mit environment.yaml

```bash
conda env create -f environment.yaml
conda activate zhaw_planner_env
```

Variante B: vorhandenes Python-Environment

```bash
pip install -r requirements.txt
```

### 2. App starten

Im Repository-Root ausführen:

```bash
streamlit run src/app.py
```

## Bedienung (empfohlener Ablauf)

1. Datei hochladen (CSV/XLS/XLSX)
2. Im Tab "Geführte Planung" Filter setzen und Module/Kurse wählen
3. Im Tab "Dashboard" Semesterüberblick prüfen
4. Im Tab "Wochenplan" Verteilung pro Tag prüfen
5. Im Tab "Konfliktanalyse" Kollisionen auflösen
6. Export am Ende freischalten und als XLSX/ICS herunterladen

Zusätzliche Einstellungen in der Sidebar bzw. im Dashboard:

- **Sprache** (de/en/fr) und **Dunkles/Helles Design** (Toggle "🌙 Dunkles Design") oben in der Sidebar, jederzeit umschaltbar
- Im Dashboard-Tab hat jedes Diagramm ein einklappbares "🎨 Diagramm-Einstellungen"-Panel: Farbpalette bzw. Farbskala wählen, einzelne Wochentage aus-/einblenden, und je nach Chart zusätzlich Farbmodus oder Ansicht umschalten. Die native Plotly-Werkzeugleiste über jedem Diagramm erlaubt zusätzlich Zoomen, Verschieben und PNG-Export

## Dateninput und Annahmen

Die Importlogik ist tolerant gegenüber Header-Varianten und Metadatenzeilen. Zentral sind u. a.:

- Wochentag
- Startzeit
- Endzeit
- Modulname
- optional Datum, Modul-Nr, Kurs-Nr, Prüfungsflag

Hinweis:

- Wenn Datum vorhanden ist, werden Konflikte datumsgenau berechnet.
- Ohne Datum erfolgt Konfliktprüfung auf Wochentag+Zeit.

## Konfliktlogik (wichtig)

In [src/scheduler.py](src/scheduler.py) gilt:

- Konflikte nur bei Zeitüberlappung
- bei vorhandenen Datumswerten nur innerhalb desselben Datums
- exakte Duplikatzeilen werden unterdrückt

Dadurch werden künstliche Mehrfachkonflikte über verschiedene Wochen minimiert.

## Internationalisierung (i18n)

Alle sichtbaren UI-Texte und Tabellenlabels laufen über Keys in [src/i18n.py](src/i18n.py).

- UI-Text: `t("...")`
- Spaltenlabels: `c("...")` -> `col.*`

Details und Regeln siehe [docs/i18n-README.md](docs/i18n-README.md).

## Fehlerbehandlung und Logging

Zwei getrennte Kanäle, mit Absicht unterschiedlich:

- **UI-Meldungen** (`st.error`/`st.warning`/`st.info`/`st.toast`): kurz, auf Deutsch/Englisch/Französisch übersetzt, für Studierende gedacht. Technische Pydantic-Fehler werden dabei automatisch zu lesbaren "Feld: Meldung"-Zeilen zusammengefasst statt als rohe mehrzeilige Fehlerdumps angezeigt zu werden.
- **Server-seitiges Logging** (Python `logging`, in `src/app.py`, `src/data_loader.py`, `src/export.py`, `src/i18n.py`): ausführlicher, mit Zeitstempel, Modulname und bei unerwarteten Fehlern vollständigem Traceback. **Erscheint nicht in der Streamlit-Oberfläche**, sondern ausschliesslich im Terminal, in dem `streamlit run src/app.py` läuft (bzw. im Log der Deployment-Umgebung).

Wenn eine Nutzer:in eine Fehlermeldung meldet, steht die kurze Version in der UI – die Details für die Diagnose stehen im Terminal-Log. Log-Level: `INFO` (normaler Ablauf, z. B. welches Excel-Sheet erkannt wurde), `WARNING` (erwartete Datenprobleme, z. B. eine Zeile ohne gültiges Datum), `ERROR`/Traceback (unerwartete Fehler).

## Tests und Checks

Syntaxcheck:

```bash
python -m py_compile src/app.py src/data_loader.py src/models.py src/scheduler.py src/export.py src/i18n.py
```

pytest:

```bash
pytest -q
```

146 Tests über 5 Dateien (`tests/test_models.py`, `tests/test_scheduler.py`, `tests/test_export.py`, `tests/test_i18n.py`, `tests/test_data_loader.py`), inkl. Konsistenzcheck der de/en/fr-Übersetzungen, Fehlerpfaden (fehlende Pflichtspalten, komplett ungültige Daten) und zweier Regressionstests für real gefundene Bugs (NaT-Datumsabsturz, ICS-Export liess Termine ohne Datum verschwinden). Volle Details, welche Datei was abdeckt und was bewusst nicht getestet ist: [docs/TESTING-README.md](docs/TESTING-README.md).

## Testdaten

Es gibt zwei getrennte Ordner für Testdaten:

- [tests/fixtures/vorlesungsverzeichnis_fiktiv.xlsx](tests/fixtures/vorlesungsverzeichnis_fiktiv.xlsx): ein vollständig **fiktiver** Beispieldatensatz (erfundene Module, Kursnummern und Dozierendennamen) mit derselben Struktur wie ein echter ZHAW-Export (Titel-/Hinweiszeilen über der echten Kopfzeile, `N.N.`-Platzhalter, Mehrfachdozierende mit „&", wöchentlich wechselnde Zeiten, PRÜFUNG-Zeilen). Plus [tests/fixtures/edge_cases_fiktiv.csv](tests/fixtures/edge_cases_fiktiv.csv) für Grenzfälle (alternative Spaltennamen, gemischte Datumsformate, fehlendes Datum). Beide werden von den pytest-Tests verwendet und können auch manuell im Streamlit-Upload zum Ausprobieren genutzt werden. Dieser Ordner wird eingecheckt.
- `data/real/`: Ablageort für deine **echte** Excelliste zum lokalen Testen. Dieser Ordner ist per eigenem `.gitignore` vollständig von Git ausgeschlossen (nur `.gitkeep`/`.gitignore` selbst werden getrackt) und landet nie im Repository.

Details zu Testdatenpolitik und wie man neue Testdaten ergänzt: [docs/TESTING-README.md](docs/TESTING-README.md#test-data).

## Projektstruktur

```text
zhaw-msc-psy_timetable-planner/
├── data/
│   └── real/              (git-ignoriert, fuer deine echte Excelliste)
├── docs/
│   ├── i18n-README.md
│   └── TESTING-README.md
├── src/
│   ├── app.py
│   ├── data_loader.py
│   ├── export.py
│   ├── i18n.py
│   ├── models.py
│   └── scheduler.py
├── tests/
│   ├── fixtures/
│   │   └── vorlesungsverzeichnis_fiktiv.xlsx  (fiktive Testdaten, eingecheckt)
│   ├── conftest.py
│   ├── test_data_loader.py
│   ├── test_export.py
│   ├── test_i18n.py
│   ├── test_models.py
│   └── test_scheduler.py
├── environment.yaml
├── requirements.txt
└── README.md
```

## Troubleshooting

- App startet nicht:
	- prüfen, ob das richtige Environment aktiv ist
	- `streamlit`, `pandas`, `plotly`, `pydantic`, `openpyxl` installiert?
	- Fehlermeldung direkt im Terminal (nicht im Browser) geprüft? Ein fehlgeschlagener Import der Backend-Module (`data_loader`/`scheduler`/`models`/`export`) wird dort mit vollständigem Traceback protokolliert
- Excel wird nicht gelesen:
	- anderes Sheet im Export versuchen
	- Header-Zeilen im Input prüfen
	- im Terminal-Log nachsehen, welches Sheet warum abgelehnt wurde (`INFO`-Zeilen pro Sheet, siehe "Fehlerbehandlung und Logging")
- Konflikte wirken unplausibel:
	- sind Datumswerte vorhanden?
	- in der Konfliktansicht zuerst Paar-Zusammenfassung, dann Detailtabelle prüfen
- ICS wirkt unvollständig oder Termine fehlen im Kalender:
	- der ICS-Export enthält immer alle aktuell ausgewählten Termine
	- prüfen, ob nach dem Upload ein Hinweis "kein Datum gefunden" erschienen ist – solche Zeilen werden als ganztägiger Platzhalter mit Warnhinweis exportiert, da in der Quelldatei pro Zeile ein Datum erwartet wird
	- Zeiten wirken falsch: ICS-Zeiten werden als UTC exportiert (Europe/Zurich-Umrechnung inkl. Sommer-/Winterzeit); der Kalenderclient sollte sie automatisch in die lokale Zeitzone umrechnen
- Eine Fehlermeldung in der App ist zu knapp, um das Problem zu verstehen:
	- im Terminal-Log nachsehen (siehe "Fehlerbehandlung und Logging") – dort steht bei unerwarteten Fehlern der vollständige Python-Traceback, bei erwarteten Datenproblemen (z. B. eine fehlgeschlagene Zeilenvalidierung) eine genauere Meldung inkl. Zeilennummer

## Datenschutz

- Verarbeitung erfolgt in der laufenden Session (in-memory)
- keine persistente Datenbank notwendig
- hochgeladene persönliche Planungsdaten sollten nicht ins Repository eingecheckt werden
