# Prompt für den nächsten Chat: Umsetzung Passerelle-Zusatzmodule

Dieses Dokument ist zum **Kopieren in einen neuen Claude-Code-Chat** gedacht (der aktuelle Chat wird zu gross / erreicht die Tokenlimite). Es enthält den vollständigen Projektkontext plus den konkreten nächsten Auftrag. Alles unterhalb der Trennlinie kann 1:1 als erste Nachricht in den neuen Chat eingefügt werden.

---

## Projektidee und Ziel

Ich baue ein Streamlit-Tool, das ZHAW-MSc-Psychologie-Studierenden hilft, aus dem hochgeladenen ZHAW-Vorlesungsverzeichnis (Excel) einen kollisionsfreien, exportierbaren Stundenplan (XLSX/ICS) zu erstellen. Zielgruppe: Psychologie-Studierende **ohne** Programmier-/Datenkenntnisse — alle Design- und UX-Entscheidungen sollen darauf optimiert sein, dass man Tabellen/Grafiken in Sekunden versteht.

**Kern-Fachannahme:** Jede Zeile in der Exceldatei ist ein konkreter Kurstermin mit eigenem Datum — **kein** wiederkehrendes Wochenmuster. Ein Kurs kann Wochentag/Zeit/Raum von Woche zu Woche wechseln. Das ist der ganze Grund, warum es dieses Tool braucht.

## Tech-Stack und Ausführung

- Python 3.11, Streamlit, pandas, Pydantic v2, Plotly Express, openpyxl.
- Conda-Env: `zhaw_planner_env`.
- Start: `streamlit run src/app.py` **vom Repo-Root aus** (flache Imports — `src/` muss Working Directory sein, kein `python -m src.app`).
- Tests: `pytest -q` (aktuell 146 Tests, alle grün).
- `.streamlit/config.toml` muss im Repo-Root liegen (nicht unter `src/`), sonst wird `primaryColor` ignoriert.

## Architektur / Dateistruktur

| Datei | Zweck |
|---|---|
| `src/app.py` (~3400 Zeilen) | Reine Präsentationsschicht: Streamlit-Widgets, Layout, Session-State, Charts. Keine Business-Logik. |
| `src/data_loader.py` | Excel/CSV → validierte `ZHAWModule`-Liste (Header-Autodetection, Spalten-Alias-Mapping, Datum/Zeit-Parsing, Sanitizing). |
| `src/models.py` | Pydantic-Domänenmodell `ZHAWModule` + `Weekday`-Enum. |
| `src/scheduler.py` | `find_time_conflicts()` ist der einzig aktive Code; der Rest (~250 Zeilen) ist bewusst belassener toter Legacy-Code aus einem früheren Standalone-Prototyp (im Modul-Docstring so dokumentiert). |
| `src/export.py` | Excel- (XLSX) und ICS-Kalenderexport. |
| `src/i18n.py` | DE/EN/FR-Übersetzungen via `get_text()`/`t()`. |
| `src/__init__.py` | Veraltet/kaputt (importiert nicht mehr existierende Klassen), harmlos, da `app.py` flach importiert wird — bewusst nicht angefasst. |

**Datenfluss:** Upload → `handle_file_upload()` → `load_schedule_from_dataframe()` (Reheader → Spalten normalisieren → sanitizen → Zeile-für-Zeile `ZHAWModule`-Validierung) → `find_time_conflicts()` → `render_guided_planning()` → Dashboard/Wochenplan/Konfliktanalyse/Rohdaten-Tabs → `render_export_section()` → `export.py`.

**Doku:** `README.md` (Projektübersicht, Deutsch), `docs/i18n-README.md` und `docs/TESTING-README.md` (technische Referenzen, Englisch), `docs/planung/` (dieser neue Planungsordner, Deutsch).

**Tests:** `tests/` mit pytest-Suite; Fixtures in `tests/fixtures/` — **ausschliesslich fiktive Daten** (erfundene Namen/Module), niemals echte ZHAW-Personendaten. `data/real/` ist ein git-ignoriertes Dropbox-Verzeichnis für echte (nicht-fiktive) Exportdateien des Nutzers und darf nie ins Repo gelangen.

## Was in diesem Projekt bisher gemacht wurde (chronologisch, alles committed auf `main`)

1. **7 UI/UX-Bugfixes:** Markdown-Parsing-Glitch im Quickstart-Text, i18n-Lücken/hartcodierte englische Fehlermeldungen, Kontrastprobleme im hellen Design, zu viele Schriftgrössen, Theme-Toggle-Platzierung, ECTS-Ziel-Tracking entfernt (kann aktuell nicht sinnvoll berechnet werden — nicht ohne Rückfrage wieder einbauen), Datum-Spalte im Wochenplan ergänzt.
2. **ZHAW-Corporate-Design:** Farbpalette gegen die `dataviz`-Skill validiert (Colorblind-Check via `validate_palette.js`) — von 12 offiziellen ZHAW-CI-Farben sind nur 5 als kategorische Chart-Palette geeignet (ZHAW Blau, Himmel Blau, Koralle, Ozean, Pflaume, Eukalyptus, Nacht Dunkelblau überlebten teilweise; Fuchsia/Sakura Rosa/Gras/Honig/Yuzu Gelb nicht — nicht ohne erneute Validierung wieder als Chart-Farben verwenden). Helvetica-Schriftstack, `.streamlit/config.toml` für native Widget-Akzentfarbe.
3. **Sprachwechsel-Bug behoben** (gleiche Ursache wie ein früherer Dark/Light-Toggle-Bug: ein `t()`-Aufruf, der VOR dem Widget liegt, das den zugehörigen Session-State setzt, zeigt für einen Rerun den alten Wert), dunkel-auf-dunkel-Button-Kontrast gefixt, Hoverlabel-Theming für Charts ergänzt.
4. **Doku-/Kommentar-Catch-up:** README.md/docs/TESTING-README.md/docs/i18n-README.md aktualisiert, WHY-Kommentare an unklaren Stellen ergänzt, per AST-Diff verifiziert, dass es reine Kommentar-Änderungen waren.
5. **UX/Dataviz-Recherche und -Umsetzung** für die Zielgruppe "Psychologiestudentin ohne Programmierkenntnisse": Occurrence-Bundling im Wochenplan-Gantt-Chart, direkte Balkenbeschriftung, Prüfungs-Textur, reichhaltigere Hover-Infos, wöchentliche Summenzeile, "verkehrsreichster Tag"-Insight auf dem Dashboard, Dashboard-Karte gegen Konfliktanalyse-Tab entduplifiziert, feiernde Empty-States, Transparenz-Captions bei Kürzungen.
6. **6 weitere Feedback-Punkte:** Standard-Theme auf Hell, "Studienplanung" → "Semesterplanung" umbenannt, ECTS-Total-Kachel ausgeblendet, Top-Überlappungen-Chart und Semesterübersicht-Chart neu gestaltet (Kurs-Aggregation statt Rohzeilen; `px.scatter` statt `px.timeline`, da Balken bei kurzen Terminen über ein ganzes Semester unsichtbar dünn wurden), Tages-Verlaufschart standardmässig nach Modul aufgeteilt, Einfarbig/Mehrfarbig-Farbmodus-Toggle im Wochenplan-Chart ergänzt.
7. **Konzept für Passerellen-Zusatzmodule** geschrieben (siehe unten) — reine Konzeptphase, kein Implementierungscode.

**Wiederkehrende Learnings (falls relevant für die nächste Arbeit):**
- Jeder neue Streamlit-Input-Widget-Typ braucht eine explizite CSS-Regel in `_inject_design_system_css()` (`app.py`), sonst fällt er auf Streamlit-Standardtheme zurück statt der `--zp-*`-Tokens.
- Nach jeder nicht-trivialen Änderung: `python -m py_compile` + `pytest -q`, und für UI-Änderungen den Browser tatsächlich öffnen und in Hell **und** Dunkel durchklicken (Playwright ist in der Conda-Env installiert) — reine Code-Review hat in der Vergangenheit reale Bugs übersehen (z. B. `Styler.background_gradient()` braucht matplotlib, das keine Projektabhängigkeit ist — nie verwenden, stattdessen `_style_sequential_red()`).
- Neue Exceptions aus `data_loader.py`, die den Nutzer erreichen, brauchen `i18n_key`/`i18n_kwargs`, keine hartcodierten englischen Strings.
- Commit-Messages: ausführlich, nach Thema gegliedert, auf Deutsch, mit Co-Authored-By-Zeile für Claude — **immer am Ende einer Arbeitseinheit committen**, das ist eine stehende Präferenz.
- Vor grösseren, mehrdeutigen Design-Entscheidungen kurz nachfragen statt zu raten; bei mechanischen Bugfixes nicht nötig.

## Aktueller Stand: Konzept für Passerellen-Zusatzmodule

**Ausgangslage:** Ein kleiner Teil der Studierenden kommt über eine Passerelle von einer anderen Hochschule und muss laut individuellem Studienplan in bestimmten Semestern **zusätzliche Module aus einem anderen Curriculum** (im Beispielfall: Bachelor-Vorlesungsverzeichnis) absolvieren. Das Tool unterstützt aktuell nur **einen** Excel-/CSV-Upload. Ziel: ein zweiter, optionaler Upload für eine "Zusatzmodule"-Liste, die mit der Hauptliste zu einem konfliktgeprüften Stundenplan zusammengeführt wird, wobei die Zusatzmodule klar erkennbar bleiben (Badge/Farbe).

**Das vollständige, detaillierte Konzept liegt bereits vor:** [docs/planung/KONZEPT-passerelle-zusatzmodule.md](KONZEPT-passerelle-zusatzmodule.md) — bitte im neuen Chat **zuerst lesen**, bevor mit der Umsetzung begonnen wird. Es enthält (10 Abschnitte):

1. Ausgangslage/Problem
2. Konkrete Kompatibilitätsanalyse der Beispieldaten gegen die bestehende Ladepipeline (welche Spalten schon funktionieren, welche zwei nicht — `wochentag` fehlt komplett in der Bachelor-Beispieldatei, `ects` fehlt als Folge davon)
3. Datenmodell-Erweiterung (neues Feld `ist_zusatzmodul: bool` auf `ZHAWModule`, App-seitig gesetzt, nicht aus der Datei gelesen)
4. UI/UX-Konzept (zweiter Upload, Badge-Kennzeichnung, Filter, Dashboard-Kachel, Export)
5. Datenfluss-Skizze
6. Konkrete Auswirkungen auf bestehenden Code (Datei-für-Datei-Tabelle)
7. Test-/Rollout-Strategie
8. **Offene Fragen/Risiken** (explizit ausformuliert, u. a. das "Parallelgruppen"-Muster: mehrere Zeilen mit identischem Termin aber unterschiedlicher Lehrperson = alternative Wahlgruppen, keine echte Kollision — muss vor der Umsetzung geklärt werden, sonst drohen False-Positive-Konflikte)
9. Bereits angelegte fiktive Testdaten (siehe unten)
10. Empfohlene Phasenreihenfolge (Phase 1 MVP: Wochentag-Ableitung + zweiter Upload + Merge + Tag-Feld + Badges + Konfliktprüfung über die Gesamtliste; Phase 2: Filter/Dashboard/Export; Phase 3 optional: Herkunfts-Semester-Feld, eigene Chart-Farbcodierung)

**Bereits vorhandene fiktive Testfixture** (bewusst noch nicht ladbar mit dem heutigen `data_loader.py`, siehe Konzept Abschnitt 9): `tests/fixtures/vorlesungsverzeichnis_passerelle_fiktiv.xlsx` — bildet die Struktur der vom Nutzer bereitgestellten echten Beispieldatei nach (Spalten `SG, Semester, Lehrperson, Datum, von, bis, Modul-Nr., Kurs-Nr., Anlassbezeichnung, Prüfung, Modulart`), mit rein erfundenen Modulen/Namen (`PDI2`/"Grundlagen der Testtheorie", `PF3`/"Statistische Grundmethoden", Lehrpersonen wie "Muster Kevin"/"Beispiel Rea"/"Demo Fabienne" nach der im Projekt etablierten Fiktionalisierungs-Konvention). Liegt neben der bestehenden Hauptfixture `tests/fixtures/vorlesungsverzeichnis_fiktiv.xlsx`.

## Auftrag für den neuen Chat

**Jetzt mit der Umsetzung beginnen.** Ich werde im neuen Chat eine **neue, echte Exceldatei** für Passerellen-Studierende bereitstellen (kleine Gruppe von Studierenden mit Zusatzkursen) — vermutlich eine vollständigere/andere Version der Beispieldaten aus der Konzeptphase.

**Wichtige Standing-Regel, unbedingt einhalten:** Jede vom Nutzer bereitgestellte Datei mit **echten** Namen/Modulinhalten darf **nicht** unverändert als Testdaten verwendet oder committed werden. Vor dem Speichern als Fixture in `tests/fixtures/` muss sie in **fiktive** Daten umgewandelt werden — nach der im Projekt etablierten Konvention (offensichtlich erfundene Nachnamen wie Muster/Beispiel/Demo/Platzhalter/Fiktiv/Vorlage, erfundene Modul-Nr./Kurstitel), analog zu den bereits vorhandenen Fixtures. Die umgewandelte Datei dann **neben** die bestehenden Testdaten in `tests/fixtures/` legen (gleicher Ordner wie `vorlesungsverzeichnis_fiktiv.xlsx` und `vorlesungsverzeichnis_passerelle_fiktiv.xlsx`). Die Originaldatei mit echten Daten selbst gehört nicht ins Repo (ggf. `data/real/`, git-ignoriert, falls lokal referenziert werden muss).

Bitte als ersten Schritt im neuen Chat [docs/planung/KONZEPT-passerelle-zusatzmodule.md](KONZEPT-passerelle-zusatzmodule.md) lesen, dann die neue Exceldatei entgegennehmen, fiktionalisieren, ablegen, und mit Phase 1 (MVP) der Umsetzung gemäss Konzept-Abschnitt 10 beginnen — inklusive Klärung der in Abschnitt 8 offen gelassenen Fragen (insbesondere das Parallelgruppen-/Konflikterkennungs-Risiko), bevor die Merge-Logik scharfgeschaltet wird.
