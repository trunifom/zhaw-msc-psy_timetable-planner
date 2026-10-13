# Settings / Feature Flags (`src/settings.py`)

Dieses Dokument beschreibt jedes Flag in `src/settings.py` - der zentralen
Datei, mit der sich Pilot-/Test-Varianten der App einschalten lassen, ohne
in `app.py` nach der richtigen Stelle suchen zu müssen.

**Hintergrund:** Die App wird mit mehreren Testgruppen erprobt. Einige
UI/UX-Entscheidungen sind noch nicht endgültig entschieden (siehe
`docs/UX-OPTIMIERUNGEN-README.md`) - z.B. ob der Rohdaten-Tab sichtbar sein
soll, oder ob Chart-Titel als neutrales Label oder als zugespitzte Aussage
("Dienstag ist dein vollster Tag") formuliert werden. Statt für jede
Testrunde Code zu ändern, wird so ein offenes Detail als Flag in
`src/settings.py` abgelegt.

**Anwendung:** Wert in `src/settings.py` ändern, speichern, App neu starten
(`streamlit run src/app.py`). Ein Flag wird pro Skript-Rerun einmal
gelesen - kein Cache-Leeren nötig. Um zwei Varianten gleichzeitig mit zwei
Testgruppen zu vergleichen: zwei ausgecheckte Kopien des Repos mit
unterschiedlichem `settings.py`-Inhalt betreiben (z.B. über zwei
Git-Branches), nicht `app.py` duplizieren.

**Wenn eine Frage entschieden ist:** Flag aus `settings.py` entfernen und
das gewählte Verhalten direkt in `app.py` fest verdrahten, statt eine
Konfigurationsoption dauerhaft stehen zu lassen, die sich nie wieder ändert.
Diese Datei ist für aktive, noch offene Entscheidungen gedacht - kein
allgemeines Konfigurationssystem.

---

## Übersicht aller Flags

| Flag | Typ | Default | Wirkung |
|---|---|---|---|
| `FEEDBACK_EMAIL` | `str` | `"trug@zhaw.ch"` | Empfänger-Adresse des Feedback-Widgets (🐞-Tab). |
| `SHOW_RAW_DATA_TAB` | `bool` | `True` | Zeigt/versteckt den "🗄️ Rohdaten"-Tab komplett. |
| `SHOW_EXTENDED_QUICKSTART` | `bool` | `True` | Zeigt Dauer/Voraussetzungen/Anmeldungs-Hinweis in der Schnellstart-Karte zusätzlich an. |
| `DEFAULT_THEME` | `"light" \| "dark" \| "auto"` | `"auto"` | Start-Theme für neue Besucher:innen (Sidebar-Umschalter bleibt immer verfügbar). |
| `CHART_TITLE_STYLE` | `"label" \| "headline"` | `"headline"` | Dashboard-Chart-Überschriften als neutrales Label oder als datengetriebene Aussage. |
| `SHOW_STEP_PROGRESS_INDICATOR` | `bool` | `True` | Zeigt den benannten Schritt-Fortschritt ("1 Datei hochladen → …") unter der Schnellstart-Karte. |

*(Diese Tabelle wächst mit jedem weiteren Flag - siehe die einzelnen
Abschnitte unten für Details. Neue Einträge werden in dem Commit ergänzt,
der das jeweilige Flag einführt.)*

---

## `FEEDBACK_EMAIL`

**Was:** Die einzige Adresse, an die das Feedback-Widget (mailto-Link + QR-Code,
siehe `_render_feedback_widget()` in `app.py`) Nachrichten schickt. Kein
Mailserver beteiligt.

**Warum ein Flag statt fest im Code:** Muss z.B. pro Semester oder bei
Zuständigkeitswechsel angepasst werden - soll dafür in Sekunden änderbar
sein, ohne die Rendering-Logik des Widgets zu verstehen/anzufassen.

**Nicht Teil der eigentlichen A/B-Test-Logik** (es gibt dafür nur einen
richtigen Wert), liegt aber trotzdem hier, damit "welche einzelne Konstante
ändere ich für die nächste Testrunde/das nächste Semester" an einem Ort
beantwortet wird.

---

## `SHOW_RAW_DATA_TAB`

**Was:** Ganzer "🗄️ Rohdaten"-Tab (Originaldaten + bereinigte/ausgewählte
Termine als reine Tabellen) sichtbar (`True`, Default) oder komplett
ausgeblendet (`False`).

**Warum:** Rückmeldungen aus dem Pilotbetrieb deuten darauf hin, dass die
meisten Studierenden diesen Tab im Alltag nicht brauchen - er bleibt aber
nützlich, um bei Rückfragen den Datenimport einer bestimmten Person zu
überprüfen. Deshalb ausblendbar statt gelöscht.

**Code-Stelle:** `app._main_tab_specs()` baut die Liste der sichtbaren Tabs;
`app.main()` rendert nur die Tabs aus dieser Liste. Bei `False` existiert
der Tab in der laufenden Session gar nicht (kein verstecktes/leeres
Tab-Element) - `render_raw_data()` wird dann nicht aufgerufen.

**Tests:** `tests/test_app_helpers.py::test_main_tab_specs_includes_raw_tab_by_default`
und `::test_main_tab_specs_drops_raw_tab_when_disabled`.

---

## `SHOW_EXTENDED_QUICKSTART`

**Was:** Ob die "🚀 Schnellstart"-Karte ganz oben (das Allererste, was eine
Besucherin/ein Besucher sieht, noch vor jedem Upload) drei zusätzliche
Zeilen über den ursprünglichen kurzen Zweck-/3-Schritte-Text hinaus zeigt:
geschätzte Dauer, benötigte Datei + Bezugsquelle, und einen expliziten
"das ist keine Kursanmeldung"-Hinweis.

**Warum:** Folgt dem GOV.UK-"Start-Seite"-Muster (siehe
`docs/UX-OPTIMIERUNGEN-README.md`, Zusatzempfehlung A) - vor dem Start
grob die Dauer und die Voraussetzungen nennen, und unmissverständlich
klarstellen, was das Tool NICHT tut (keine echte Kursanmeldung).
Als Flag (statt fest ergänzt), damit sich im Pilotbetrieb vergleichen
lässt, ob der zusätzliche Text tatsächlich gelesen/hilfreich ist oder nur
zusätzliches Scrollen bedeutet.

**Code-Stelle:** `app.main()`, direkt nach dem bestehenden Quickstart-Text
in der `"app-quickstart"`-Karte. Bei `False` bleibt die Karte exakt im
bisherigen, kürzeren Zustand.

**Live verifiziert:** Playwright-Screenshot in Hell- und Dunkelmodus mit
`SHOW_EXTENDED_QUICKSTART=True` - alle drei neuen Zeilen lesbar, der
Disclaimer als eigener `st.info`-Hinweis hervorgehoben.

---

## `DEFAULT_THEME`

**Was:** Welches Theme eine neue Besucherin/ein neuer Besucher beim allerersten
Laden sieht, bevor sie/er den Hell/Dunkel-Umschalter in der Sidebar
überhaupt angefasst hat. Der manuelle Umschalter selbst bleibt **immer**
verfügbar, unabhängig von diesem Flag - es wird nur der Startpunkt
bestimmt.

- `"light"`: immer hell starten (ursprüngliches, festes Verhalten).
- `"dark"`: immer dunkel starten.
- `"auto"` (Default): versucht, die Hell/Dunkel-Einstellung des
  Betriebssystems/Browsers über Streamlits `st.context.theme.type` zu
  übernehmen; fällt auf `"light"` zurück, falls dieses Signal (noch) nicht
  verfügbar ist (bekannte Streamlit-Einschränkung beim allerersten
  Skript-Durchlauf einer Session).

**Warum `"auto"` empfohlen wird:** UX-Recherche (siehe
`docs/UX-OPTIMIERUNGEN-README.md`, Zusatzempfehlung B, NN/g-Quelle) zeigt,
dass Nutzer:innen Dark Mode als systemweite Einstellung erwarten, nicht als
etwas, das sie pro App erneut einstellen müssen.

**Code-Stelle:** `app._resolve_default_theme()` liest dieses Flag und
`st.context.theme.type`; aufgerufen an beiden Bootstrap-Stellen für
`st.session_state.ui_theme` (dem frühen CSS-Bootstrap-Block am
Dateianfang und in `init_session_state()` - beide müssen bei einer
künftigen Änderung konsistent gehalten werden, siehe dortige Kommentare).

**Tests:** `tests/test_app_helpers.py::test_resolve_default_theme_*`
(deckt alle drei Flag-Werte sowie den Fallback ab, wenn `st.context.theme.type`
`None` ist).

**Live verifiziert:** Playwright mit `color_scheme="dark"`/`"light"`
Browser-Emulation bei `DEFAULT_THEME="auto"` - App startet jeweils im
passenden Theme. Zusätzlich mit `DEFAULT_THEME="dark"` bei einem
hell-präferierenden Browser - App startet trotzdem dunkel (fester Wert
gewinnt über die Browser-Präferenz).

---

## `CHART_TITLE_STYLE`

**Was:** Wie die vier Dashboard-Diagramm-/Abschnittsüberschriften
(Wochentagsverteilung, Top-Überlappungen, Semesterübersicht, Gesamte
Vorlesungsdauer) formuliert sind:

- `"label"`: die ursprüngliche, statische, beschreibende Überschrift
  (z.B. "Top-Überlappungen pro Modul") - was der Abschnitt IST.
- `"headline"` (Default): eine datengetriebene Aussage für die aktuelle
  Auswahl (z.B. "Grösste Überlappung: AS1 (45 Min.)") - was die Daten des
  Abschnitts tatsächlich AUSSAGEN. Fällt automatisch auf die statische
  Variante zurück, wenn (noch) keine Aussage berechnet werden kann (z.B.
  keine datierten Termine).

**Warum:** Folgt der "aktiver Titel statt beschreibendes Label"-Praxis
(Storytelling with Data/Evergreen) sowie der GOV.UK Analysis
Function-Empfehlung "Headline + Untertitel" für Diagramme (siehe
`docs/UX-OPTIMIERUNGEN-README.md`, Zusatzempfehlung C).

**Wortlaut einfach anpassbar:** Die genaue Formulierung jeder Headline
liegt NICHT in diesem Flag, sondern als normaler, übersetzbarer Text in
`src/i18n.py` unter den Keys `dashboard.chart.*_headline` (je einer pro
Sprache, z.B. `dashboard.chart.weekday_headline`,
`dashboard.chart.overlap_headline`, `dashboard.chart.semester_headline`,
`dashboard.chart.daily_load_headline`). Nur der WORTLAUT dort muss
angepasst werden, um den Text zu ändern - dieses Flag schaltet nur
zwischen Label- und Headline-Stil um.

**Code-Stelle:** `app._chart_section_title()` (die generische
Umschalt-Logik) plus vier kleine, reine Helper-Funktionen, die je eine
Headline aus den aktuellen Daten berechnen:
`_weekday_distribution_headline()`, `_overlap_headline()`,
`_semester_timeline_headline()`, `_daily_load_headline()`. Aufgerufen aus
`render_dashboard()` an den vier `st.markdown(...)`-Überschriften-Stellen.

**Tests:** `tests/test_app_helpers.py` - `test_chart_section_title_*` (die
Umschalt-Logik selbst) sowie je 2 Tests pro Headline-Helper (korrekte
Aussage berechnet / `None` ohne Daten).

**Live verifiziert:** Playwright-Screenshot mit echtem
Haupt+Zusatzmodule-Konfliktszenario - alle vier Überschriften zeigen
korrekt die berechnete Aussage (z.B. "📌 Dienstag ist dein dichtester Tag
(2 Termine)", "📌 Grösste Überlappung: KFH1 (90 Min.)").

---

## `SHOW_STEP_PROGRESS_INDICATOR`

**Was:** Ob direkt unter der Schnellstart-Karte ein kompakter, benannter
Fortschrittsindikator für den gesamten Ablauf erscheint: "✓ 1 Datei
hochladen → ▶ 2 Module wählen → 3 Plan prüfen → 4 Exportieren". Jeder
Schritt wird anhand des bestehenden Session-Zustands (Datei hochgeladen?
Module ausgewählt? Planung abgeschlossen?) als erledigt (✓, grün),
aktuell (▶, blau) oder noch offen (grau, kein Icon) markiert.

**Wichtig:** Rein ein Orientierungshinweis — es wird dadurch **nichts** an
der bestehenden Navigation gesperrt oder verändert. Ein Studierender kann
weiterhin jederzeit frei zwischen allen Tabs wechseln.

**Warum:** Folgt NN/g "Progress Indicators" (benannte Schritte statt nackter
Prozentzahl) und ist der erste, risikoarme Teil von Hauptpunkt 4 aus
`docs/UX-OPTIMIERUNGEN-README.md`. Der aufwändigere, riskantere Teil dieser
Empfehlung (abgeschlossene Schritte zu einem editierbaren Einzeiler mit
"Ändern"-Link einklappen, GOV.UK "Check answers"-Stil) ist **bewusst nicht**
Teil dieses Flags — siehe den Status-Hinweis beim entsprechenden Punkt in
`docs/UX-OPTIMIERUNGEN-README.md`.

**Technische Besonderheit (wichtig bei künftigen Änderungen):** Der
Indikator wird über ein `st.empty()`-Platzhalter-Element gerendert, das
früh (direkt nach der Schnellstart-Karte) reserviert, aber erst NACH
`render_guided_planning()` mit Inhalt gefüllt wird (`app.main()`). Ohne
diesen Umweg wäre der Status für "Module wählen" immer einen Rerun
veraltet, da `render_guided_planning()` erst weiter unten im Skript läuft
und `st.session_state.selected_modules` erst dort aktualisiert — ein
klassisches, in diesem Projekt bereits an anderer Stelle (Theme-/
Sprachumschalter) dokumentiertes Streamlit-Timing-Problem. Live mit
Playwright gefunden und mit `st.empty()` behoben, nicht nur dokumentiert.

**Code-Stelle:** `app._guided_flow_step_statuses()` (reine Logik, nimmt die
drei Status als einfache Booleans entgegen statt `st.session_state` selbst
zu lesen — dadurch sowohl Timing-sicher als auch ohne Mocking testbar) und
`app._render_step_progress_indicator()` (befüllt den `st.empty()`-Slot).

**Tests:** `tests/test_app_helpers.py::test_guided_flow_step_statuses_*`
(alle vier Stadien plus Label-Reihenfolge).

**Live verifiziert:** Playwright-Durchlauf durch alle vier Zustände (vor
Upload, nach Upload, nach Auswahl, nach Finalisieren) - Indikator aktualisiert
sich jedes Mal sofort korrekt, kein Rerun-Lag.
