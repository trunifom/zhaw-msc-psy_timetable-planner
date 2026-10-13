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
