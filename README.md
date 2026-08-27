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
- Design-System (durchgängig auf allen 5 Tabs plus Sidebar, Light/Dark umschaltbar über eine eigene "Darstellung"-Sektion in der Sidebar):
	- einheitliche Karten-Sektionen (Icon + Titel + Trennlinie) statt reiner Whitespace-Trennung
	- konsistente Semantikfarben (Erfolg/Warnung/Kritisch/Info) über die ganze App, sowohl als Badges/Zeilenfärbung in Tabellen als auch in Charts
	- Tabellen mit typisierten Spalten (`st.column_config`): formatierte Datum-/Zeit-/Zahlenspalten statt Rohstrings, Status-Spalten farbcodiert, Überlappungs-/Risikowerte als sequenzieller Rot-Verlauf (abhängigkeitsfrei implementiert, siehe Troubleshooting)
	- **ZHAW Corporate Design**: Titel/Akzentfarbe (aktiver Tab, Steuerelemente) und die Standard-Diagrammpalette nutzen offizielle ZHAW-CI-Farben statt generischer Plotly-/UI-Töne, Schriftfamilie orientiert sich an der ZHAW-Hausschrift (Helvetica-Neue-Fallback-Stack, lizenzbedingt keine echte Einbindung möglich). Details und die Gründe hinter der konkreten Farbauswahl siehe die Kommentare über `THEME_TOKENS`/`CHART_PALETTES_LIGHT`/`CHART_PALETTES_DARK` in `src/app.py`
	- Wochenplan-Tab als Tabelle statt Fliesstext (Datum/Zeit/Modul/Typ/Raum/Dozierende/Grund je Wochentag)
- Visualisierung (Dashboard-Charts sind interaktiv anpassbar über ein "🎨 Diagramm-Einstellungen"-Panel):
	- Wochen-Timeline im Wochenplan-Tab ("typische Woche" nach Uhrzeit statt Kalenderdatum): mehrfach wiederkehrende Termine am selben Wochentag/derselben Uhrzeit werden zu einem Balken zusammengefasst (statt mehrerer deckungsgleicher Balken), Kursname direkt auf dem Balken sichtbar (nicht nur im Hover), Prüfungstermine zusätzlich zur Farbe mit Schraffur markiert, Hover zeigt Anzahl Termine und Datumsbereich; darüber eine "Wochenübersicht auf einen Blick" (Termine/Woche, Stunden/Woche, dichtester Tag)
	- Semester-Timeline (Farbe wählbar nach Modul oder Modulart)
	- Tageslast über den gesamten Zeitraum (Gesamt- oder nach Modul aufgeschlüsselte Ansicht)
	- Wochentagsverteilung mit automatischem Hinweis auf den dichtesten Tag ("📌 Freitag ist dein dichtester Tag mit X Terminen")
	- pro Chart: Farbpalette (inkl. farbenblind-sicher) bzw. Farbskala wählbar, Wochentage ein-/ausblendbar, native Plotly-Werkzeugleiste (Zoom, Pan, PNG-Export)
	- einheitlicher, theme-abhängiger Chart-Hintergrund (transparent, folgt Light/Dark) über alle Tabs hinweg
- Übersichtlichkeit für Einsteiger:innen: positiv formulierte Erfolgsmeldung bei konfliktfreier Auswahl ("🎉 Keine Zeitkonflikte..."), sichtbarer Hinweis wenn eine Grafik/Tabelle aus Platzgründen nur einen Ausschnitt zeigt (z. B. "Zeigt die 8 grössten von X Konflikten"), Dashboard zeigt bei Abwesenheitskonflikten nur den Status der aktuellen Auswahl und verweist für die volle Aufschlüsselung auf den Konfliktanalyse-Tab statt dieselbe Tabelle doppelt anzuzeigen
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

- **Dunkles/Helles Design** (Toggle "🌙 Dunkles Design") in der eigenen "Darstellung"-Sektion ganz oben in der Sidebar, **Sprache** (de/en/fr) direkt darunter in "Daten und Sprache" - beides jederzeit umschaltbar, wirkt sofort (auch die Sidebar-Beschriftung selbst) ohne zusätzlichen Reload
- Im Dashboard-Tab hat jedes Diagramm ein einklappbares "🎨 Diagramm-Einstellungen"-Panel: Farbpalette bzw. Farbskala wählen, einzelne Wochentage aus-/einblenden, und je nach Chart zusätzlich Farbmodus oder Ansicht umschalten. Die native Plotly-Werkzeugleiste über jedem Diagramm erlaubt zusätzlich Zoomen, Verschieben und PNG-Export

## Zusatzmodule für Passerellen-Studierende

Für Studierende, die laut individuellem Studienplan zusätzliche Module aus einem anderen Studiengang/einer anderen Hochschule belegen müssen (z. B. Passerelle: zusätzliche Bachelor-Module), gibt es in der Sidebar unterhalb von "Daten und Sprache" eine eigene, optionale Karte **"🎓 Zusatzmodule"** mit einem zweiten Datei-Upload. Die dort hochgeladene Liste wird automatisch mit der Hauptplanung zu einer gemeinsamen, konfliktgeprüften Liste zusammengeführt:

- Module aus der Zusatzliste sind in allen Tabellen (geführte Planung, Rohdaten, Wochenplan, Konfliktanalyse) an der Spalte/Markierung "Quelle" (🎓 Zusatzmodul) erkennbar.
- Kollisionen zwischen einem Hauptmodul und einem Zusatzmodul werden genau wie Kollisionen innerhalb der Hauptliste erkannt - es gibt keinen separaten Prüfpfad.
- Fehlt in der hochgeladenen Zusatzliste eine Wochentag-Spalte (nur Datum vorhanden, wie bei manchen Bachelor-Exporten), wird der Wochentag automatisch aus dem Datum abgeleitet.
- Bietet eine Zeitperiode mehrere parallele Angebote mit unterschiedlichen Dozierenden, ohne dass die Zuteilung (z. B. Halbklasse) im Export schon erkennbar ist, werden alle Angebote vorerst übernommen und mit einem Hinweis in Schritt 4 der geführten Planung sichtbar markiert, statt die Mehrdeutigkeit stillschweigend zu verstecken.
- Wird nur die Zusatzliste wieder entfernt, bleibt die Hauptplanung unverändert bestehen; wird die Hauptdatei entfernt, wird die gesamte Planung (inkl. Zusatzmodule) zurückgesetzt.
- In Schritt 2 der geführten Planung erscheint (nur wenn eine Zusatzliste hochgeladen wurde) ein zusätzlicher Filter "Alle anzeigen"/"Nur Zusatzmodule"/"Zusatzmodule ausblenden".
- Das Dashboard zeigt (ebenfalls nur bei vorhandener Zusatzliste) eine zusätzliche Kennzahl "Zusatzmodule ausgewählt".
- Export: die ICS-Beschreibung bekommt eine Zeile "Zusatzmodul (Passerelle)"; die Excel-Datei eine Spalte "Quelle" ("Hauptliste"/"Zusatzmodul").

Details und der volle Umsetzungsplan: [docs/planung/KONZEPT-passerelle-zusatzmodule.md](docs/planung/KONZEPT-passerelle-zusatzmodule.md).

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
- Fehlt die Wochentag-Spalte komplett, aber ein Datum ist vorhanden, wird der Wochentag automatisch daraus abgeleitet (nicht nur für Zusatzmodule relevant, siehe oben - hilft jedem Export ohne eigene Wochentag-Spalte).

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

188 Tests über 6 Dateien (`tests/test_models.py`, `tests/test_scheduler.py`, `tests/test_export.py`, `tests/test_i18n.py`, `tests/test_data_loader.py`, `tests/test_zusatzmodule_fixtures.py`), inkl. Konsistenzcheck der de/en/fr-Übersetzungen, Fehlerpfaden (fehlende Pflichtspalten, komplett ungültige Daten), zweier Regressionstests für real gefundene Bugs (NaT-Datumsabsturz, ICS-Export liess Termine ohne Datum verschwinden) und der umfangreichen Zusatzmodul-/Passerellen-Tests gegen realistisch grosse, aus den echten HS26-Katalogen fiktionalisierte Testdaten (Wochentag-Ableitung, `ist_zusatzmodul`-Kennzeichnung, Konflikterkennung über Haupt- und Zusatzliste hinweg, Modul-Nr.-Kollisionsszenario, Export bei realistischem Umfang). Volle Details, welche Datei was abdeckt und was bewusst nicht getestet ist: [docs/TESTING-README.md](docs/TESTING-README.md).

## Testdaten

Es gibt zwei getrennte Ordner für Testdaten:

- [tests/fixtures/vorlesungsverzeichnis_fiktiv.xlsx](tests/fixtures/vorlesungsverzeichnis_fiktiv.xlsx): ein vollständig **fiktiver** Beispieldatensatz (erfundene Module, Kursnummern und Dozierendennamen) mit derselben Struktur wie ein echter ZHAW-Export (Titel-/Hinweiszeilen über der echten Kopfzeile, `N.N.`-Platzhalter, Mehrfachdozierende mit „&", wöchentlich wechselnde Zeiten, PRÜFUNG-Zeilen). Plus [tests/fixtures/edge_cases_fiktiv.csv](tests/fixtures/edge_cases_fiktiv.csv) für Grenzfälle (alternative Spaltennamen, gemischte Datumsformate, fehlendes Datum) und [tests/fixtures/vorlesungsverzeichnis_passerelle_fiktiv.xlsx](tests/fixtures/vorlesungsverzeichnis_passerelle_fiktiv.xlsx) für die Zusatzmodul-/Passerellen-Funktion (fiktiver Bachelor-Katalog ohne Wochentag-Spalte, inkl. zweier Parallelgruppen-Muster - siehe [docs/planung/KONZEPT-passerelle-zusatzmodule.md](docs/planung/KONZEPT-passerelle-zusatzmodule.md)).
- Zusätzlich sechs **umfangreiche, realitätsnahe Testdaten** speziell für die Zusatzmodul-/Passerellen-Funktion, erzeugt durch [tests/fixtures/generate_fictional_fixtures.py](tests/fixtures/generate_fictional_fixtures.py):
	- [vorlesungsverzeichnis_bsc_vollstaendig_fiktiv.xlsx](tests/fixtures/vorlesungsverzeichnis_bsc_vollstaendig_fiktiv.xlsx) / [vorlesungsverzeichnis_msc_vollstaendig_fiktiv.xlsx](tests/fixtures/vorlesungsverzeichnis_msc_vollstaendig_fiktiv.xlsx): **vollständig fiktionalisierte** Nachbildungen der echten Bachelor- (1182 Zeilen) bzw. Master-Vorlesungsverzeichnisse (343 Zeilen) in Originalgrösse - jede Lehrperson, Modul-/Kurs-Nr. und jeder Kurstitel ist erfunden (deterministisches Mapping, siehe Skript-Docstring), Datum/Zeit/Modulart/Semester bleiben unverändert, da das keine personenbezogenen Daten sind und genau diese Vielfalt/Grösse der Zweck dieser Fixtures ist.
	- [vorlesungsverzeichnis_konflikt_hauptliste_fiktiv.xlsx](tests/fixtures/vorlesungsverzeichnis_konflikt_hauptliste_fiktiv.xlsx) + `..._zusatzliste_fiktiv.xlsx`: von Hand erstelltes Mini-Szenario mit einer garantierten Zeitüberschneidung zwischen einem Haupt- und einem Zusatzmodul (plus einem garantiert nicht überschneidenden Paar), um die Konflikterkennung end-to-end zu testen.
	- [vorlesungsverzeichnis_modulnr_kollision_hauptliste_fiktiv.xlsx](tests/fixtures/vorlesungsverzeichnis_modulnr_kollision_hauptliste_fiktiv.xlsx) + `..._zusatzliste_fiktiv.xlsx`: von Hand erstelltes Mini-Szenario, bei dem Haupt- und Zusatzliste zufällig dieselbe Modul-Nr. verwenden (siehe Konzeptdokument Abschnitt 8, Risiko 2).

  Alle Fixtures werden von den pytest-Tests verwendet und können auch manuell im Streamlit-Upload zum Ausprobieren genutzt werden. Dieser Ordner wird eingecheckt - die generierten Dateien enthalten keinerlei echte Personen- oder Curriculumsdaten (siehe das Generator-Skript für die Fiktionalisierungsregeln und wie das verifiziert wurde).
- `data/real/`: Ablageort für deine **echte** Excelliste zum lokalen Testen. Dieser Ordner ist per eigenem `.gitignore` vollständig von Git ausgeschlossen (nur `.gitkeep`/`.gitignore` selbst werden getrackt) und landet nie im Repository. `generate_fictional_fixtures.py` liest optional daraus, um die beiden "vollstaendig"-Fixtures bei Bedarf neu zu generieren.

Details zu Testdatenpolitik und wie man neue Testdaten ergänzt: [docs/TESTING-README.md](docs/TESTING-README.md#test-data).

## Projektstruktur

```text
zhaw-msc-psy_timetable-planner/
├── .streamlit/
│   └── config.toml        (primaryColor fuer native Streamlit-Widgets, siehe Troubleshooting)
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
- Warum kein `matplotlib` als Abhängigkeit: die farbig hinterlegten Überlappungs-/Risikowerte in den Tabellen sehen aus wie pandas' `Styler.background_gradient()`, sind aber bewusst selbst gebaut (`_style_sequential_red` in `src/app.py`) – `background_gradient()` bricht sonst beim ersten Zugriff mit `ImportError: background_gradient requires matplotlib.` ab, da `matplotlib` nirgends in `requirements.txt`/`environment.yaml` steht. Beim Ergänzen neuer farbcodierter Tabellen bitte diese Funktion wiederverwenden statt `background_gradient()` neu einzuführen
- `.streamlit/config.toml` (setzt `primaryColor` auf ZHAW Blau, damit native Streamlit-Steuerelemente wie Radio-Buttons/Checkboxen/Toggles/Buttons nicht mehr Streamlits Standard-Rot verwenden) wird nur erkannt, wenn es relativ zum **Arbeitsverzeichnis der Shell** beim Start liegt – also im Repo-Root, wenn wie dokumentiert per `streamlit run src/app.py` **aus dem Repo-Root** gestartet wird. Ein Start via `cd src && streamlit run app.py` (Arbeitsverzeichnis wäre dann `src/`) findet die Datei nicht und die Steuerelemente fallen zurück auf Streamlits Standardfarbe – falls Buttons/Radios plötzlich wieder rot statt ZHAW-blau erscheinen, zuerst das Arbeitsverzeichnis beim Start prüfen, nicht den Farbwert
- Farben/Kontraste stimmen für ein bestimmtes UI-Element (Button, Tabelle, Dropdown, Chart-Text) nach einem Theme-Wechsel nicht: `_inject_design_system_css()` in `src/app.py` deckt Streamlits native Widgets nur ab, wenn sie dort explizit per CSS-Selektor angesprochen werden (`.stButton`, `.stTextInput input`, `[data-baseweb="select"]` usw.) – ein neuer, noch nicht dort erfasster Widget-Typ fällt sonst auf Streamlits eigenes, vom App-Theme-Toggle unabhängiges natives Erscheinungsbild zurück. Bei einem neuen Widget-Typ in der UI immer in beiden Themes im Browser gegenprüfen, nicht nur im Code lesen (siehe auch "What isn't covered" in [docs/TESTING-README.md](docs/TESTING-README.md))

## Datenschutz

- Verarbeitung erfolgt in der laufenden Session (in-memory)
- keine persistente Datenbank notwendig
- hochgeladene persönliche Planungsdaten sollten nicht ins Repository eingecheckt werden
