# UX/Dataviz-Optimierungen — Umsetzungsplan

Diese Datei dokumentiert eine umfassende Analyse (Codebase-Review + Multi-Agenten-Recherche zu
Best Practices bei grossen Anbietern und UX-Forschungsorganisationen) vom **2026-10-12/13**,
durchgeführt mit Claude Code. Ziel: konkrete, priorisierte Verbesserungen an Darstellung,
Ausgabe, Menüführung und Diagrammen der Stundenplan-Planungssoftware für ZHAW MSc
Psychologie-Studierende.

**Zielgruppe der App (Erinnerung):** Psychologie-Masterstudierende ohne Programmier-/
Data-Science-Hintergrund. Design-Entscheidungen sollen immer an "was muss in 5 Sekunden
verstanden werden" gemessen werden, nicht an einer technischen/analytischen Zielgruppe.

**Wie diese Datei benutzt wird:** Jeder Punkt ist einzeln abarbeitbar. Nach Fertigstellung
eines Punkts wird im jeweiligen Abschnitt ein **"✅ Erledigt am"**-Eintrag mit Datum, Uhrzeit
und Commit-Hash ergänzt. Offene Punkte bleiben mit ⬜ markiert.

---

## Quellenlage (Kurzübersicht)

Die Empfehlungen stützen sich auf vier parallele Recherche-/Analyse-Durchläufe:

1. **Codebase-Analyse** — vollständige Bestandsaufnahme von App-Flow (Sidebar, 5 Tabs,
   geführte Planung in 3 Schritten), allen Plotly-Charts, Tabellen, Design-System
   (`THEME_TOKENS`, `card()`, `CHART_PALETTES_*`), Export (`export.py`), i18n und Docs.
2. **Recherche: Kalender-/Stundenplan-UX** — Google Calendar, Outlook, Apple Calendar,
   FullCalendar, York University Visual Schedule Builder, Coursicle, NN/g, W3C WCAG, Tufte.
3. **Recherche: Dataviz/Dashboard für Laien** — Microsoft Power BI, IBM Carbon Design System,
   Tableau, NN/g, GOV.UK Analysis Function (GSS), Datawrapper, W3C WAI, Streamlit-Blog.
4. **Recherche: Menü/Navigation/Wizard-UX** — NN/g (Wizards, Tabs, Progressive Disclosure),
   GOV.UK Design System (Start Pages, Check Answers, Task List), Baymard Institute,
   Calendly/Doodle/When2meet, universitäre Schedule-Builder (York, Calgary, Houston, Iowa).

Quellen-URLs sind bei den einzelnen Punkten angegeben, wo sie unmittelbar leitend waren.

---

## Priorisierte Liste (1 = höchster Impact)

### 1. Konflikte am Ort der Auswahl sichtbar machen, nicht nur im Konfliktanalyse-Tab

**Status:** ⬜ Offen

**Problem:** `find_time_conflicts()`-Ergebnisse werden aktuell nur in `render_conflict_analysis()`
(Tab 4 "Konfliktanalyse") vollständig angezeigt. Ein Student, der in Schritt 2 der geführten
Planung (`render_guided_planning()`) eine Auswahl trifft, die einen Konflikt erzeugt, bekommt
das nicht unmittelbar an der Auswahlzeile selbst angezeigt — er müsste aktiv in einen anderen
Tab wechseln, um es zu bemerken.

**Empfehlung:**
- Pro Kurszeile in der Auswahltabelle (Schritt 2) ein Warnsymbol/Badge anzeigen, sobald diese
  Zeile mit einer anderen ausgewählten Zeile kollidiert (Vorbild: York University Visual
  Schedule Builder — Warnsymbol direkt am verursachenden Kurs, nicht nur generischer Fehler).
- Zusätzlich ein kompaktes Banner auf Dashboard und Wochenplan ("⚠ 2 Konflikte betreffen deine
  aktuelle Auswahl") mit Link/Sprung zum Konfliktanalyse-Tab für die Details.
- Harte Konflikte (echte Zeitüberschneidung) von weichen Warnungen (z.B. sehr knappe
  Raumwechsel) farblich/iconografisch unterscheiden (Vorbild: York VSB, Event Cadence).

**Ansatzpunkt im Code:** `render_guided_planning()` Schritt 2 (`src/app.py`, Selektionstabellen
via `_dataframe_row_selection()`), Ergebnis von `find_time_conflicts()` bereits dort verfügbar
machen statt nur in `render_conflict_analysis()`.

**Quellen:** York University VSB (registrar.yorku.ca/node/511), Google Calendar "Find a time"
(workspaceupdates.googleblog.com/2016/09), NN/g "Visibility of System Status"
(nngroup.com/articles/visibility-system-status).

**Aufwand:** Mittel (Datenfluss bereits vorhanden, UI-Ergänzung an mehreren Stellen).

---

### 2. Wochenplan: echte Kalender-Spalten statt gestapelter Marker bei Überschneidungen

**Status:** ✅ Erledigt am 2026-10-13, 00:40 (Commit `b45f6aa`)

**Umsetzung:** Neue, eigenständige Chart-Funktion `_weekly_timeline_lanes_figure()` plus
`_assign_weekday_lanes()` (Greedy-Lane-Packing, siehe deren Docstrings) in `src/app.py`. Im
Wochenplan-Tab über den bestehenden "🎨 Diagramm-Einstellungen"-Toolbar per neuem
"Darstellung bei Überschneidungen"-Umschalter wählbar: "Gestapelt (bisherige Ansicht)"
(Default, unverändert) vs. "Nebeneinander (wie im Kalender)" (neu). **Die alte gestapelte
Ansicht (`_weekly_timeline_figure()`) wurde bewusst nicht entfernt** — auf expliziten
Wunsch, damit beide Varianten zuerst im Team verglichen und besprochen werden können, bevor
über das Löschen der alten Ansicht entschieden wird.

Verifiziert: `py_compile` + `pytest -q` (250/250 grün) im korrekten Conda-Env
(`zhaw_planner_env` — Achtung, siehe `project-conventions`-Memory zum zweiten,
abweichenden System-Python auf dieser Maschine), sowie Live-Test per Playwright mit einem
echten Haupt+Zusatzmodule-Konfliktszenario (`vorlesungsverzeichnis_konflikt_hauptliste_fiktiv.xlsx`
+ `..._zusatzliste_fiktiv.xlsx`, Konflikt KFH1-1 vs. KFZ1-1, Dienstag 10:15-12:00 vs.
10:15-11:45) in Hell- und Dunkelmodus sowie Mehrfarbig- und Einfarbig-Darstellung.

**Problem:** `_weekly_timeline_figure()` nutzt `px.timeline` mit `pattern_shape`-Hatching für
Prüfungen — gut für Einzelblöcke, aber bei echten Zeitüberschneidungen (dem Kernproblem der
App) fehlt die Seite-an-Seite-Darstellung, die aus jedem gängigen Kalendertool bekannt ist.

**Empfehlung:** Lane-Packing-Algorithmus implementieren (Konvention von Google Calendar,
Outlook, FullCalendar, Apple Calendar):
1. Ereignisse nach Startzeit sortieren (bei Gleichstand: längeres zuerst).
2. Jedes Ereignis der ersten freien "Spalte" zuweisen, deren letztes Ereignis bereits beendet ist.
3. Breite = 100% / Anzahl Spalten; horizontal versetzt nach Spaltenindex zeichnen.
4. Nicht überlappende Ereignisse behalten volle Spaltenbreite.

Alternative/Ergänzung: zusätzlich roter Rahmen oder ⚠-Badge auf kollidierenden Blöcken, damit
der Konflikt auch ohne genaues Hinschauen auffällt.

**Ansatzpunkt im Code:** `_weekly_timeline_figure()` (`src/app.py`, ca. Zeile 2914).

**Quellen:** Skedulo Calendar Docs (auhealthcare.docs.skedulo.com), FullCalendar
`slotEventOverlap`/`eventOverlap` Docs (fullcalendar.io/docs), Apple Community (Überlappung als
bekanntes Lesbarkeitsproblem, wenn Blöcke übereinander statt nebeneinander gezeichnet werden).

**Aufwand:** Mittel bis gross (neue Layout-Logik für Plotly-Figure, Testabdeckung nötig).

---

### 3. Semester-Timeline: Wochen-Heatmap oder gruppierte Wochenliste statt/ergänzend zum Scatter-Plot

**Status:** ✅ Vollständig erledigt am 2026-10-13, 09:45 (Commits `c3f5cd0`, `bb0c627`)

**Umsetzung Teil 1 (Wochen-Heatmap, Commit `c3f5cd0`):** Neue, eigenständige Chart-Funktion
`_semester_heatmap_figure()` in `src/app.py`: eine Zelle pro Kalenderdatum (Kalenderwoche ×
Wochentag), Farbe/Zahl = Anzahl Termine an diesem Tag, Konflikttage zusätzlich mit ⚠-Symbol
markiert (nie nur Farbe). Im Dashboard-Tab über den bestehenden
"🎨 Diagramm-Einstellungen"-Toolbar der Semesterübersicht per "Ansicht"-Umschalter wählbar:
"Punkte (bisherige Ansicht)" (Default, unverändert) vs. "Heatmap (Wochenübersicht)" (neu).

Verifiziert: `py_compile` + `pytest -q` im korrekten Conda-Env (`zhaw_planner_env`), sowie
Live-Test per Playwright mit einem echten Haupt+Zusatzmodule-Konfliktszenario in Hell- und
Dunkelmodus. Dabei einen echten Darstellungsfehler gefunden und behoben: Ohne expliziten
`zmin=0` landete ein Tag mit nur einem Termin am unteren Ende der Farbskala und war (v.a. im
Dark Mode) nahezu weiss/unsichtbar — jetzt per `zmin`/`zmax`-Fixierung auf der Skala immer
sichtbar tingiert.

**Umsetzung Teil 2 (gruppierte Wochenliste als Drill-down, Commit `bb0c627`):** Neue, reine
(Streamlit-unabhängige) Funktion `_semester_week_groups()` gruppiert datierte Module nach
Kalenderwoche (chronologisch nach tatsächlichem Montagsdatum, gleiche Jahreswechsel-Logik wie
`_semester_grid_figure()`/`_semester_heatmap_figure()`). `_render_semester_week_list()` zeigt
pro Woche einen `st.expander` ("KW 38 (14.09. - 20.09.) · 4 Termine · ⚠ 1 Konflikt(e)"),
automatisch aufgeklappt nur bei einer Woche mit echtem Konflikt, mit einer Tabelle der
Wochentermine darin (neue Konflikt-Spalte, rot getönt). Im selben "Ansicht"-Umschalter als
dritte Option "Liste (nach Woche)" wählbar.

**Beide neuen Ansichten (Heatmap und Liste) sowie die alte Scatter-Ansicht
(`_semester_timeline_figure()`) bestehen unverändert nebeneinander** — auf expliziten Wunsch,
damit alle drei im Team verglichen werden können, bevor über das Entfernen einer Variante
entschieden wird.

Verifiziert: `py_compile` + `pytest -q` (256/256 grün, davon 6 neu für
`_semester_week_groups()`: Sortierung nach echtem Montagsdatum über den Jahreswechsel hinweg,
Ausschluss undatierter Zeilen, Zählung von Terminen/distinkten Konflikttagen, Sortierung
innerhalb einer Woche, Label-Format) im korrekten Conda-Env (`zhaw_planner_env`), sowie
Live-Test per Playwright mit einem echten Haupt+Zusatzmodule-Konfliktszenario in Hell- und
Dunkelmodus (Woche korrekt automatisch aufgeklappt, Konflikt-Termine rot getönt mit
"⚠ Überschneidung"-Text, nicht-konfliktierende Termine ungetönt). Die reine
UI-Rendering-Hälfte (`_render_semester_week_list`) bleibt gemäss bestehender Projekt-Policy
(`docs/TESTING-README.md`) der manuellen/Playwright-Verifikation vorbehalten, nicht
unit-getestet.

**Problem:** `_semester_timeline_figure()` nutzt `px.scatter` über einen ca. 4-monatigen
Zeitstrahl. Alle drei Recherche-Agenten kamen unabhängig zum selben Schluss: Für diese
Datenform (viele kurze Ereignisse über eine lange Zeitachse) gilt sowohl ein Gantt-Chart
(bereits verworfen, siehe Memory) als auch ein reiner Scatter-Plot als suboptimal (Tufte,
van Wijk/van Selow zu Calendar-Heatmaps).

**Empfehlung (zwei Varianten, ggf. kombinierbar):**
- **Wochen-Heatmap:** Kalenderwoche × Wochentag als Raster, Zellwert = Anzahl Sessions an
  diesem Tag, zusätzliches Konflikt-Icon/roter Rahmen auf betroffenen Zellen. Zeigt
  Prüfungswochen und Belastungsspitzen auf einen Blick.
- **Nach Kalenderwoche gruppierte Liste** als Drill-down ("KW 42 · 3 Termine · 1 Konflikt"),
  anklickbar zur Detailansicht der jeweiligen Woche. Diese Variante ist zugleich die
  mobile-taugliche Alternative zum dichten Scatter-Plot (siehe Punkt 8).

**Ansatzpunkt im Code:** `_semester_timeline_figure()` (`src/app.py`, ca. Zeile 2409), ggf. als
zusätzliche Ansicht statt kompletten Ersatz, umschaltbar über `_render_chart_toolbar()`.

**Quellen:** van Wijk & van Selow, "Cluster and Calendar-based Visualization" (InfoVis 1999);
Edward Tufte, "Project Management Graphics or Gantt Charts" (edwardtufte.com/notebook);
GitHub-Style Calendar-Heatmap-Konvention.

**Aufwand:** Gross (neuer Chart-Typ, Interaktionslogik für Drill-down).

---

### 4. Sichtbarer, benannter Schritt-Fortschritt statt reiner Tab-Struktur

**Status:** ✅ Teilweise erledigt am 2026-10-13, 13:30 (Commit `7582dcb1`)

**Umsetzung (erster, risikoarmer Teil):** Ein kompakter, benannter Fortschrittsindikator
("✓ 1 Datei hochladen → ▶ 2 Module wählen → 3 Plan prüfen → 4 Exportieren") erscheint jetzt
direkt unter der Schnellstart-Karte, rein additiv — er verändert oder sperrt nichts an der
bestehenden Tab-Navigation. Per neuem Flag `settings.SHOW_STEP_PROGRESS_INDICATOR` (Default
`True`) umschaltbar — siehe `docs/SETTINGS-README.md`, inklusive eines dabei live gefundenen
und behobenen Rerun-Timing-Bugs (`st.empty()`-Platzhalter-Lösung).

**Noch offen (zweiter, aufwändigerer Teil):** Das Einklappen abgeschlossener Schritte zu
einem editierbaren Einzeiler mit "Ändern"-Link (GOV.UK "Check answers"-Stil) sowie das
Zurückführen zur passenden Stelle beim Bearbeiten eines früheren Schritts — das würde eine
grössere Restrukturierung der bestehenden, historisch fehleranfälligen Geführte-Planung-Logik
bedeuten und wurde bewusst zurückgestellt (höheres Regressionsrisiko, siehe
`project-conventions`-Memory zu wiederholten Selection-Persistence-Bugs in genau diesem
Bereich).

**Problem (Ausgangslage):** 3 unnummerierte bzw. nur implizit nummerierte Abschnitte innerhalb
von "Geführte Planung" (Schritt 1/2/3), danach 5 gleichrangige `st.tabs()`. Kein
durchgängiger, benannter Fortschrittsindikator über den gesamten Ablauf (Upload → Auswahl →
Prüfen → Export).

**Empfehlung:**
- Kompakter, benannter Schritt-Indikator: "1 Datei hochladen → 2 Module wählen → 3 Plan
  prüfen → 4 Exportieren" statt nackter Nummern oder reiner Tab-Leiste.
- Abgeschlossene Schritte zu Einzeiler mit "Ändern"-Link einklappen (z.B. "✓ Datei:
  Modulliste_HS26.xlsx · 142 Kurse — Ändern"), analog GOV.UK "Check answers"-Pattern.
- Beim Bearbeiten eines früheren Schritts den Nutzer zur vorherigen Stelle zurückführen,
  ohne spätere Auswahl zu verwerfen (Baymard: 68% der untersuchten Checkout-Flows machen das
  falsch).

**Quellen:** NN/g "Wizards: Definition and Design Recommendations" (nngroup.com/articles/wizards),
NN/g "Progress Indicators" (nngroup.com/articles/progress-indicators), GOV.UK "Check answers"
(design-system.service.gov.uk/patterns/check-answers), Baymard "Accordion Checkout Usability"
(baymard.com/blog/accordion-checkout-usability).

**Aufwand:** Mittel (primär UI-Restrukturierung, bestehende Logik bleibt erhalten).

---

### 5. Sprachumschalter aus der Sidebar an eine immer sichtbare Stelle

**Status:** ✅ Erledigt am 2026-10-13, 14:10 (Commit `8b68098a`)

**Umsetzung:** Der Sprachumschalter (de/en/fr) sitzt jetzt oben rechts neben dem Titel im
Hauptbereich (`_render_header_language_switcher()`, neue Spalten-Layout in `main()`) statt in
der Sidebar — immer sichtbar, unabhängig vom Sidebar-Zustand. Die Sidebar-Karte
"🌐 Sprache" wurde entfernt; der Theme-Toggle bleibt wie empfohlen in der Sidebar. Der Widget-
Key wurde von `sidebar_language_selector` zu `header_language_selector` umbenannt — der
bestehende `t()`-vor-Widget-Rerun-Fix (frühes Session-State-Sync vor der CSS-Generierung)
wurde entsprechend mitaktualisiert, nicht entfernt.

Verifiziert: `py_compile` + `pytest -q` (278/278 grün, keine Regressionen) im korrekten
Conda-Env, sowie Live-Test per Playwright — Sprachwechsel zu Englisch funktioniert korrekt
(Header, Sidebar, Quickstart-Karte alle übersetzt), Position bleibt in Hell- und Dunkelmodus
stabil und gut lesbar.

**Problem:** Streamlit-Sidebars sind auf Mobilgeräten standardmässig eingeklappt (bestätigtes,
dokumentiertes Verhalten, siehe Streamlit-Forum). Die Sprachwahl ist aber die erste Entscheidung
eines neuen Nutzers — sie sollte nicht hinter einem einklappbaren Pfeil verschwinden.

**Empfehlung:** Sprachumschalter (de/en/fr) an eine immer sichtbare Stelle im Hauptbereich
verschieben (z.B. oben rechts neben dem Titel), mit nativen Sprachnamen beschriftet
("Deutsch · English · Français"), nicht nur Flaggen/Icons. Theme-Toggle kann in der Sidebar
bleiben (niedrigere Priorität, siehe Punkt "Zusatzempfehlungen").

**Ansatzpunkt im Code:** `render_sidebar()` (`src/app.py`, ca. Zeile 4857) — Sprach-Card
herauslösen, im Bereich um `main()`s Titel-Rendering neu platzieren. Achtung: bestehender
`t()`-vor-Widget-Rerun-Bug (siehe `project-conventions`-Memory) beachten, wenn die
Platzierung im Skriptfluss verschoben wird.

**Quellen:** NN/g "Language Switching" (nngroup.com/articles/language-switching-ecommerce),
Streamlit-Forum-Thread zu eingeklappter Mobile-Sidebar (discuss.streamlit.io).

**Aufwand:** Klein (Quick Win) — primär Platzierung, nicht neue Logik.

---

### 6. Export als eigenen, sichtbaren Abschluss-Schritt statt Sidebar-Anhängsel

**Status:** ✅ Erledigt am 2026-10-13, 14:45 (Commit `<wird nach Commit ergänzt>`)

**Umsetzung:** Der Export-Bereich erscheint jetzt standardmässig als eigene, gut sichtbare
"4 Exportieren"-Karte im Hauptbereich, direkt nach den Ergebnis-Tabs — statt unterhalb der
Upload-Karten in der Sidebar. Bestehende Gating-Logik (Export erst nach "Planung
abgeschlossen"-Checkbox) unverändert übernommen; `render_export_section()` selbst wurde nicht
verändert, nur die Aufrufstelle. Per neuem Flag `settings.EXPORT_SECTION_PLACEMENT`
(`"main" | "sidebar"`, Default `"main"`) umschaltbar — siehe `docs/SETTINGS-README.md`.

Verifiziert: `py_compile` + `pytest -q` (278/278 grün, keine Regressionen) im korrekten
Conda-Env, sowie Live-Test per Playwright für beide Werte — Export-Karte erscheint korrekt an
der jeweils erwarteten Stelle, Checkbox-Gating und beide Download-Buttons funktionieren, keine
Dopplung in beiden Fällen.

**Problem:** `render_export_section()` sitzt aktuell in der Sidebar unterhalb der
Upload-Karten — leicht zu übersehen, obwohl Export (XLSX/ICS) das eigentliche Ziel der
gesamten Nutzung ist.

**Empfehlung:** Export als klar erkennbaren "Schritt 4: Exportieren" im Hauptbereich
platzieren (z.B. eigene Karte nach den Ergebnis-Tabs oder als permanent sichtbarer
Call-to-Action-Button), analog zum "Add to calendar"-Payoff-Moment bei Calendly.
Bestehende Gating-Logik (Export erst nach "Planung finalisieren"-Checkbox) beibehalten.

**Ansatzpunkt im Code:** `render_export_section()` (`src/app.py`, Zeile 1091), Aufrufstelle
von der Sidebar in den Hauptbereich verschieben.

**Quellen:** Calendly Blog (calendly.com/blog/new-scheduling-page-ui), Appcues GoodUX
(goodux.appcues.com/blog/calendlys-scheduling-experience).

**Aufwand:** Klein (Quick Win) — primär Platzierung/visuelle Prominenz.

---

### 7. KPI-Kacheln mit Kontext/Vergleich statt nackter Zahl

**Status:** ⬜ Offen

**Problem:** Dashboard-KPI-Metriken (Zeilen/Basiskurse/Prüfungen/Wochentage/
Lektionen-pro-Woche) zeigen aktuell primär reine Zahlen ohne Vergleichswert.

**Empfehlung:** `st.metric()` bereits im Einsatz — `delta`/`delta_color`/`help`-Parameter
konsequent nutzen:
- Konflikt-Kachel mit `delta_color="inverse"` (weniger ist besser) und Vorperioden-/
  Zielvergleich, wo sinnvoll.
- `help=`-Tooltip an jeder Kachel mit kurzer Erklärung, was die Zahl bedeutet.
- `st.container(horizontal=True)` für KPI-Reihen nutzen, damit sie auf schmalen
  Bildschirmen automatisch umbrechen (siehe auch Punkt 8, Mobile).

**Ansatzpunkt im Code:** `render_dashboard()` (`src/app.py`, Zeile 5014), KPI-Metrik-Card.

**Quellen:** Microsoft Power BI "Tips for designing a great Power BI dashboard"
(learn.microsoft.com/power-bi/create-reports/service-dashboards-design-tips), NN/g
"Choosing Chart Types" (nngroup.com/articles/choosing-chart-types — "Zahlen sind ohne
Kontext bedeutungslos").

**Aufwand:** Klein (Quick Win).

---

### 8. Jeder Chart bekommt eine Daten-Tabelle als Fallback/Alternative

**Status:** ⬜ Offen

**Problem:** Charts haben aktuell keine systematische tabellarische Alternative/Fallback
(abgesehen vom separaten Rohdaten-Tab, der nicht pro Chart kontextualisiert ist).

**Empfehlung:** Unter jedem Chart einen `st.expander("Als Tabelle anzeigen")` mit den
zugrunde liegenden Daten ergänzen — passt zum bereits etablierten Expander-Pattern der App.
Wichtig (GOV.UK "Details"-Komponenten-Guidance): die eigentliche Kernaussage/Caption muss
weiterhin sichtbar bleiben und darf nicht im Expander "versteckt" werden — nur die Rohdaten
selbst wandern hinein.

**Ansatzpunkt im Code:** Jede der Chart-Builder-Funktionen in `src/app.py`
(`_semester_timeline_figure`, `_weekly_timeline_figure`, `_daily_load_figure`,
`_weekday_bar_figure`, `_overlap_bar_figure`, Konfliktanalyse-Inline-Charts) bzw. deren
jeweilige Aufrufstellen in `render_dashboard()`/`render_timetable()`/
`render_conflict_analysis()`.

**Quellen:** Microsoft Power BI Accessibility ("Show data table" als Screenreader-Fallback,
learn.microsoft.com/power-bi/create-reports/desktop-accessibility-creating-reports),
Material 3 Accessibility Blog (m3.material.io/blog/data-visualization-accessibility), W3C WAI
"Complex Images" (w3.org/WAI/tutorials/images/complex).

**Aufwand:** Klein bis mittel (Quick Win, aber an mehreren Stellen zu wiederholen).

---

## Zusatzempfehlungen (kleiner, aber leicht nachzuziehen)

### A. Kurzer Start-Screen vor Schritt 1

**Status:** ✅ Erledigt am 2026-10-13, 11:15 (Commit `cf0041b9`)

**Umsetzung:** Die bestehende Quickstart-Karte (`app.purpose_text`/`app.quickstart_text`)
wurde um drei GOV.UK-Start-Seiten-Elemente ergänzt: geschätzte Dauer ("ca. 5-10 Minuten"),
benötigte Datei + Bezugsquelle ("offizielle ZHAW-Kursliste ... über dein
Studiengangsekretariat"), und ein als `st.info` hervorgehobener Hinweis, dass die Planung
hier **keine Kursanmeldung** ersetzt. Per neuem Flag `settings.SHOW_EXTENDED_QUICKSTART`
(Default `True`) ein-/ausblendbar — siehe `docs/SETTINGS-README.md`.

Verifiziert: `py_compile` + `pytest -q` (258/258 grün) im korrekten Conda-Env, sowie
Live-Test per Playwright in Hell- und Dunkelmodus — alle drei neuen Zeilen gut lesbar.

**Quellen:** GOV.UK "Start using a service"
(design-system.service.gov.uk/patterns/start-using-a-service).

---

### B. Theme-Default auf OS-Einstellung statt festem "light"-Default

**Status:** ✅ Erledigt am 2026-10-13, 11:50 (Commit `6e59e6d9`)

**Umsetzung:** Neue, pure Funktion `app._resolve_default_theme()` plus Flag
`settings.DEFAULT_THEME` (`"light" | "dark" | "auto"`, Default `"auto"`) - bei `"auto"` wird
Streamlits `st.context.theme.type` (die vom Browser/OS übernommene Hell/Dunkel-Präferenz)
verwendet, mit Fallback auf `"light"`, falls dieses Signal noch nicht verfügbar ist. Beide
bisherigen Bootstrap-Stellen für `ui_theme` (früher Block vor dem CSS-Setup,
`init_session_state()`) rufen jetzt diese Funktion auf, statt den String `"light"` hart zu
verdrahten. Der manuelle Sidebar-Umschalter bleibt unverändert immer verfügbar.

Verifiziert: `py_compile` + `pytest -q` (262/262 grün, 4 neue Tests für
`_resolve_default_theme()`) im korrekten Conda-Env, sowie Live-Test per Playwright mit
Browser-Emulation (`color_scheme="dark"`/`"light"`) — die App startet bei `DEFAULT_THEME=
"auto"` jeweils im passenden Theme, und bei einem fest gesetzten Wert (z.B. `"dark"`) auch
unabhängig von der Browser-Präferenz.

**Quellen:** NN/g "Dark Mode: Users' Issues" (nngroup.com/articles/dark-mode-users-issues).

---

### C. Chart-Titel als Aussage statt Label

**Status:** ✅ Erledigt am 2026-10-13, 12:40 (Commit `7992e0be`)

**Umsetzung:** Alle vier Dashboard-Chart-/Abschnittsüberschriften (Wochentagsverteilung,
Top-Überlappungen, Semesterübersicht, Gesamte Vorlesungsdauer) zeigen jetzt standardmässig
eine datengetriebene Aussage statt eines neutralen Labels — z.B. "📌 Dienstag ist dein
dichtester Tag (2 Termine)" statt "Verteilung nach Wochentagen". Per neuem Flag
`settings.CHART_TITLE_STYLE` (`"label" | "headline"`, Default `"headline"`) umschaltbar; der
genaue Wortlaut jeder Headline liegt als normaler i18n-Text in `src/i18n.py`
(`dashboard.chart.*_headline`-Keys) und ist dort unabhängig vom Flag anpassbar — siehe
`docs/SETTINGS-README.md`.

Verifiziert: `py_compile` + `pytest -q` (273/273 grün, 11 neue Tests für die Umschalt-Logik
und die vier Headline-Helfer) im korrekten Conda-Env, sowie Live-Test per Playwright mit
echtem Konfliktszenario — alle vier Überschriften zeigen die korrekt berechnete Aussage.

**Quellen:** GOV.UK Analysis Function "Data visualisation: charts"
(analysisfunction.civilservice.gov.uk/policy-store/data-visualisation-charts), Storytelling
with Data / Stephanie Evergreen (aktive Titel statt beschreibender Label).

---

## Hinweise zur Abarbeitung

- Vor jeder Änderung: `git status`/`git diff` prüfen, `python -m py_compile` + `pytest -q`
  nach jeder Änderung (siehe `project-conventions`-Memory).
- UI-/Layout-Änderungen immer live im Browser in **beiden Themes** (hell/dunkel) testen, nicht
  nur per Code-Review — mehrfach dokumentierte Quelle realer Bugs in diesem Projekt.
- Bei grösseren, mehrdeutigen Design-Entscheidungen (Farbwahl, Umfang einer Restrukturierung)
  kurz Rücksprache halten, bevor geraten wird (bestehende Projekt-Konvention).
- Nach Fertigstellung eines Punkts: Abschnitt mit **"✅ Erledigt am [Datum] [Uhrzeit] (Commit
  `<hash>`)"** ergänzen, Status-Zeile von ⬜ auf ✅ ändern.
