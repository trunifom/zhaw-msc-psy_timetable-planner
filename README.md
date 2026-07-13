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
- Visualisierung:
	- Wochen-Timeline
	- Semester-Timeline
	- Tageslast über den gesamten Zeitraum
	- Wochentagsverteilung
- Export:
	- XLSX
	- ICS (nur Termine mit Datum)
- Mehrsprachigkeit (de/en/fr) über zentrale i18n-Keys

## Architektur

- Präsentation: [src/app.py](src/app.py)
- Import/Bereinigung: [src/data_loader.py](src/data_loader.py)
- Domänenmodell: [src/models.py](src/models.py)
- Konfliktlogik: [src/scheduler.py](src/scheduler.py)
- Exportlogik: [src/export.py](src/export.py)
- Übersetzungen: [src/i18n.py](src/i18n.py)
- i18n-Konventionen: [docs/i18n-README.md](docs/i18n-README.md)

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

## Tests und Checks

Syntaxcheck:

```bash
python -m py_compile src/app.py src/data_loader.py src/models.py src/scheduler.py src/i18n.py
```

pytest (falls vorhanden):

```bash
pytest -q
```

## Projektstruktur

```text
zhaw-msc-psy_timetable-planner/
├── data/
├── docs/
│   ├── HealthData-CodeArchitect.md
│   └── i18n-README.md
├── src/
│   ├── app.py
│   ├── data_loader.py
│   ├── export.py
│   ├── i18n.py
│   ├── models.py
│   └── scheduler.py
├── tests/
├── environment.yaml
├── requirements.txt
└── README.md
```

## Troubleshooting

- App startet nicht:
	- prüfen, ob das richtige Environment aktiv ist
	- `streamlit`, `pandas`, `plotly`, `pydantic`, `openpyxl` installiert?
- Excel wird nicht gelesen:
	- anderes Sheet im Export versuchen
	- Header-Zeilen im Input prüfen
- Konflikte wirken unplausibel:
	- sind Datumswerte vorhanden?
	- in der Konfliktansicht zuerst Paar-Zusammenfassung, dann Detailtabelle prüfen
- ICS wirkt unvollständig:
	- nur Termine mit Datum werden exportiert

## Datenschutz

- Verarbeitung erfolgt in der laufenden Session (in-memory)
- keine persistente Datenbank notwendig
- hochgeladene persönliche Planungsdaten sollten nicht ins Repository eingecheckt werden
