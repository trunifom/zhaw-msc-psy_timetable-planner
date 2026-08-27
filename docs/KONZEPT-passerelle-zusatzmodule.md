# Konzept: Zusatzmodule für Passerellen-Studierende

Status: **Konzept / noch nicht implementiert.** Dieses Dokument beschreibt eine geplante Erweiterung, aber keine Zeile Code dazu wurde bisher geschrieben (Ausnahme: die Testdaten in [tests/fixtures/vorlesungsverzeichnis_passerelle_fiktiv.xlsx](../tests/fixtures/vorlesungsverzeichnis_passerelle_fiktiv.xlsx), siehe Abschnitt 9). Ziel ist, dass eine künftige Umsetzung dieses Dokument direkt als Arbeitsgrundlage nehmen kann.

## 1. Ausgangslage

Ein kleiner Teil der MSc-Psychologie-Studierenden kommt über eine **Passerelle** von einer anderen Hochschule oder aus einem anderen Studiengang und muss laut individuellem Studienplan in bestimmten Semestern **zusätzliche Module** absolvieren, um fehlende fachliche Grundlagen nachzuholen. Diese Zusatzmodule stammen in der Regel **nicht** aus dem MSc-Vorlesungsverzeichnis, sondern aus einem separaten Verzeichnis - im vom Nutzer bereitgestellten Beispiel konkret aus dem **Bachelor-Vorlesungsverzeichnis** Angewandte Psychologie.

Aktuell unterstützt das Tool genau **einen** Excel-/CSV-Upload (`st.session_state.raw_data`/`processed_modules`, siehe [src/app.py](../src/app.py) `render_sidebar()`/`handle_file_upload()`). Eine Passerellen-Studentin müsste die zwei Listen also entweder:

- manuell in Excel zusammenführen, bevor sie sie hochlädt (genau die Arbeit, die dieses Tool eigentlich abnehmen soll), oder
- nur eine der beiden Listen hochladen und die andere komplett manuell im Kopf/auf Papier verwalten - mit dem Risiko, Kollisionen zwischen Haupt- und Zusatzmodulen gar nicht erst zu bemerken.

**Ziel dieses Konzepts:** ein zweiter, optionaler Upload-Slot für eine "Zusatzmodule"-Liste, die mit der Hauptliste zu **einem** konfliktgeprüften Stundenplan zusammengeführt wird, wobei jederzeit klar erkennbar bleibt, welche Termine aus welcher Quelle stammen.

## 2. Kompatibilitätsanalyse der Beispieldaten

Das ist der wichtigste Teil dieses Konzepts, weil er entscheidet, wie viel *neue* Logik überhaupt nötig ist. Die Spalten der vom Nutzer bereitgestellten Beispieldatei wurden direkt gegen die bestehende Normalisierungs-Pipeline geprüft (`_normalize_columns`/`COLUMN_ALIASES`/`_try_reheader_from_rows` in [src/data_loader.py](../src/data_loader.py)).

### 2.1 Spaltenvergleich

| Spalte (Beispiel Bachelor/Passerelle) | Kanonischer Name | Bereits abgedeckt? |
|---|---|---|
| `SG` | *(kein kanonisches Feld)* | Ja - wird über `ZHAWModule`s `extra="ignore"` automatisch verworfen, genau wie in der Hauptliste heute schon (dort steht `MSc`, hier `BSc`) |
| `Semester` | *(kein kanonisches Feld)* | Wird ebenfalls verworfen (`extra="ignore"`) - Inhalt geht im MVP verloren, siehe Abschnitt 3 für eine optionale spätere Erweiterung |
| `Lehrperson` | `dozierende` | Ja, direkt (bereits ein Alias) |
| `Datum` | `datum` | Ja, direkt |
| `von` / `bis` | `startzeit` / `endzeit` | Ja, direkt (bereits Aliase) |
| `Modul-Nr.` | `modul_nr` | Ja, direkt - der Punkt in "Modul-Nr." wird von `_normalize_label()` bereits zu `modul_nr` normalisiert |
| `Kurs-Nr.` | `kurs_nr` | Ja, direkt |
| `Anlassbezeichnung` | `modulname` (Fallback) | Ja - `load_schedule_from_dataframe()` nutzt `anlassbezeichnung` bereits als Fallback-Quelle für `modulname`, wenn keine eigene `Modul`-Spalte existiert |
| `Prüfung` | `pruefung_flag` | Ja, direkt |
| `Modulart` | `modultyp` | Ja, direkt |
| **`Tag` (Wochentag)** | `wochentag` | **Nein - fehlt komplett in der Beispieldatei** |

**Befund:** Bis auf eine einzige Spalte deckt die bestehende Alias-/Normalisierungslogik die zweite Datenquelle bereits vollständig ab, ohne dass `COLUMN_ALIASES` erweitert werden müsste. Das wurde konkret nachgewiesen: die neu angelegte Testdatei (Abschnitt 9) durchläuft `_try_reheader_from_rows()` und `_normalize_columns()` bereits fehlerfrei; erst der anschliessende Pflichtspalten-Check schlägt fehl:

```
ERROR - Invalid dataset format. Missing critical columns: ects, wochentag.
Detected columns: sg, semester, dozierende, datum, startzeit, endzeit,
modul_nr, kurs_nr, modulname, pruefung_flag, modultyp
```

(`ects` fehlt hier nur als Folgefehler - die bestehende "ECTS ist die einzige fehlende Pflichtspalte -> auf 0 setzen"-Regel in `load_schedule_from_dataframe()` greift nicht, weil gleichzeitig auch `wochentag` fehlt.)

### 2.2 Notwendige Erweiterung: Wochentag aus Datum ableiten

Die Bachelor-Exportvorlage scheint (zumindest im vorliegenden Beispiel) **keine separate Wochentagsspalte** zu führen, sondern nur ein Datum. Das ist mit der aktuellen `HEADER_REQUIRED_COLUMNS = {"wochentag", "startzeit", "endzeit"}`-Regel unvereinbar.

**Vorschlag:** In `load_schedule_from_dataframe()` (nach `_normalize_columns()`, vor dem Pflichtspalten-Check) eine neue Regel ergänzen: *Wenn `datum` vorhanden ist, aber `wochentag` fehlt, wird `wochentag` automatisch aus `datum` abgeleitet* (Pythons `date.weekday()` bzw. das bereits vorhandene `Weekday`-Enum in [src/models.py](../src/models.py)). Das ist unabhängig vom `datum`-Zelltyp machbar, da `_sanitize_dataframe()` `datum` ohnehin schon vor der Validierung robust parst.

Das ist bewusst **keine Passerellen-spezifische Sonderregel**, sondern eine allgemeine Robustheitsverbesserung der Importpipeline - sie würde jeder hochgeladenen Datei zugutekommen, die (aus welchem Grund auch immer) keine separate Wochentagsspalte mitbringt, nicht nur der Zusatzmodul-Liste. Mit dieser einen Änderung lädt die in Abschnitt 9 angelegte Testdatei bereits vollständig durch, ohne dass sonst irgendetwas an der Kernpipeline angepasst werden müsste.

### 2.3 Beobachtung: "Parallelgruppen"-Muster

Im vom Nutzer bereitgestellten Beispiel (Kurs "F1-1 Quantitative Methoden 1") teilen sich mehrere Zeilen exakt denselben Termin (gleiches Datum, gleiche Zeit), unterscheiden sich aber in der Lehrperson - erkennbar an sechs verschiedenen Namen für denselben Slot. Das ist vermutlich keine gemeinsame Ko-Dozentur (wie das bestehende `"Name A & Name B"`-Muster im Hauptdatensatz), sondern **mehrere parallele, alternative Gruppen** desselben Kurses, von denen eine Studentin nur **eine** besucht.

Das ist in der neu angelegten Testdatei bewusst nachgebildet (Modul `PF3`, zwei Termine à 6 "parallele" Zeilen) - **nicht um es zu lösen**, sondern um es beim Implementieren testbar zu machen. Siehe Abschnitt 8 (offene Fragen) für die Konsequenz: das könnte je nach genauer Funktionsweise von `find_time_conflicts()`/`_module_signature()` in [src/scheduler.py](../src/scheduler.py) zu falsch-positiven Konflikten führen, wenn alle Parallelgruppen-Zeilen unverändert importiert werden.

## 3. Datenmodell-Erweiterung

Ein neues, optionales Feld auf `ZHAWModule` ([src/models.py](../src/models.py)):

```python
ist_zusatzmodul: bool = Field(default=False, description="True fuer Module aus einer separat hochgeladenen Zusatzmodul-/Passerellen-Liste.")
```

**Wichtig:** Dieses Feld wird **nicht** aus der Exceldatei gelesen - keine der beiden Quelldateien braucht dafür eine eigene Spalte. Es wird von der Ladefunktion gesetzt, abhängig davon, **über welchen Upload-Slot** die Datei hochgeladen wurde: `load_schedule_from_dataframe(df, ist_zusatzmodul=True)` für den zweiten Uploader, `ist_zusatzmodul=False` (Default) für den bestehenden Haupt-Upload. Der neue Parameter setzt das Feld pro Zeile, bevor `ZHAWModule(**row_dict)` aufgerufen wird.

**Warum nicht einfach die vorhandene `SG`-Spalte** (`MSc` vs. `BSc`) **als Unterscheidungsmerkmal nutzen**, statt ein neues Feld einzuführen? Weil das den Dateiinhalt zur Business-Logik machen würde: es setzt voraus, dass `SG` in beiden Dateien immer zuverlässig und mit genau diesen beiden Werten befüllt ist. Ein von der Applikation selbst gesetztes Tag (abhängig vom Upload-Slot, nicht vom Zellinhalt) ist robuster und unabhängig davon, was konkret in der Datei steht - passt auch besser zum bestehenden Grundsatz der App, Datenqualitätsprobleme in der Quelldatei nicht in Business-Logik einfliessen zu lassen (vgl. `data_loader.py`s ganze defensive Sanitizing-Philosophie).

**Optional, nicht Teil des MVP:** ein zweites Feld `herkunfts_semester: Optional[str]`, um den Inhalt der `Semester`-Spalte ("1. Semester VZ") informativ mitzuführen und z. B. in der Detailansicht anzuzeigen. Aktuell würde dieser Spalteninhalt via `extra="ignore"` stillschweigend verworfen. Siehe Abschnitt 10 (Phase 2).

## 4. UI/UX-Konzept

### 4.1 Zweiter Upload

Neue, eigene Karte in der Sidebar (im bestehenden Card-Design-System, siehe `card()`-Helper in [src/app.py](../src/app.py)), z. B. **"🎓 Zusatzmodule"**, unterhalb der bestehenden "Daten und Sprache"-Karte. Standardmässig sichtbar, aber bewusst als **eigener, klar abgegrenzter Bereich** gestaltet statt in den Haupt-Uploader integriert - das betrifft nur eine Minderheit der Nutzer:innen, und die grosse Mehrheit soll dadurch keine zusätzliche Verwirrung im Hauptablauf erleben (progressive disclosure, siehe [[ux-clarity-patterns]] aus der letzten Session). Kurzer Erklärtext direkt an der Karte: *"Nur nötig, falls du laut Studienplan zusätzliche Module aus einem anderen Studiengang/einer anderen Hochschule besuchen musst (z. B. Passerelle)."*

Gleiche Ladepipeline wie beim Hauptupload (`load_schedule_from_dataframe`, inkl. Multi-Sheet-Versuch bei Excel), nur mit `ist_zusatzmodul=True`. Ergebnis landet in einem eigenen Session-State-Key (z. B. `st.session_state.processed_modules_zusatz`), wird aber **sofort** mit der Hauptliste zu einer kombinierten `processed_modules`-Liste zusammengeführt - alle nachgelagerten Komponenten (Konfliktanalyse, geführte Planung, Dashboard, Export) kennen weiterhin nur **eine** flache Modulliste und müssen dafür nicht angepasst werden; sie müssen nur das neue `ist_zusatzmodul`-Feld für Anzeige/Filterung auswerten, wo sinnvoll.

**Konfliktprüfung über beide Listen hinweg ist zwingend** - eine Passerellen-Studentin braucht genau zu wissen, ob ein Zusatzmodul mit einem MSc-Pflichtmodul kollidiert. Da `find_time_conflicts()` ([src/scheduler.py](../src/scheduler.py)) ohnehin nur eine flache Modulliste entgegennimmt, ist das automatisch der Fall, sobald die Listen wie oben beschrieben zusammengeführt werden - keine Änderung an der Konfliktlogik selbst nötig.

### 4.2 Visuelle Kennzeichnung

Der bestehende `badge()`-Helper (kleine farbcodierte Pille, siehe [src/app.py](../src/app.py)) ist genau für diesen Zweck gebaut und kann direkt wiederverwendet werden - z. B. ein Badge **"🎓 Zusatzmodul"** überall dort, wo Modulzeilen tabellarisch dargestellt werden:

- geführte Planung (Auswahltabelle, Schritt 3/4)
- Rohdaten-Tab ("Ausgewählte Termine"-Tabelle)
- Wochenplan-Tab ("Details pro Wochentag")
- Konfliktanalyse-Detailtabelle

In Diagrammen (Wochenplan-Gantt, Semesterübersicht) könnte "Zusatzmodul" als eigene Farbcodierungs-Option ergänzt werden - Detailentscheidung für die Umsetzungsphase, nicht Teil dieses Konzepts.

### 4.3 Filter in der geführten Planung

Zusätzlicher Filter (analog zu den bestehenden Filtern nach Modultyp/Wochentag/Dozierenden in Schritt 2, siehe `render_guided_planning()`): **"Nur Zusatzmodule"**/**"Zusatzmodule ausblenden"**, damit eine Passerellen-Studentin gezielt nur ihre Zusatzmodule sehen kann, wenn sie diese separat durchgehen will.

### 4.4 Dashboard

Optionale, **nur sichtbare KPI-Kachel**, wenn tatsächlich eine Zusatzliste hochgeladen wurde (z. B. "Zusatzmodule ausgewählt: N") - bei keinem Zusatz-Upload bleibt das Dashboard exakt wie heute (vollständige Rückwärtskompatibilität, kein UI-Rauschen für die grosse Mehrheit ohne Passerellen-Hintergrund).

### 4.5 Export

- **ICS:** Die bestehende, bereits reichhaltige Ereignisbeschreibung (Dozent:in, Modul-/Kurs-Nr., Modulart, ECTS, Anwesenheitspflicht, siehe [src/export.py](../src/export.py)) bekommt eine zusätzliche Zeile "Zusatzmodul (Passerelle)", wenn `ist_zusatzmodul=True`.
- **Excel:** eine zusätzliche Spalte "Quelle" mit den Werten "Hauptliste"/"Zusatzmodul".

## 5. Datenfluss (Übersicht)

```
Haupt-Upload (bestehend)              Zusatz-Upload (neu)
        |                                     |
load_schedule_from_dataframe(         load_schedule_from_dataframe(
    df, ist_zusatzmodul=False)            df, ist_zusatzmodul=True)
        |                                     |
        +------------------+------------------+
                           |
                 kombinierte Modulliste
              (ein `ist_zusatzmodul`-Feld
                 pro Zeile, sonst identisch)
                           |
        +------------------+------------------+
        |                  |                  |
find_time_conflicts   geführte Planung   Dashboard/Wochenplan/
(unveraendert)        (+ neuer Filter)   Konfliktanalyse/Export
                                          (+ Badge-Anzeige)
```

Der entscheidende Architekturpunkt: **alles unterhalb der kombinierten Liste bleibt eine einzige, flache `List[ZHAWModule]`** - es gibt bewusst keine zwei parallelen Datenpfade durch die App. Das minimiert das Risiko, dass Zusatzmodule an einer der vielen bestehenden Stellen (Charts, Tabellen, Export) "vergessen" gehen, weil dort ohnehin schon einfach über `modules`/`selected_modules` iteriert wird.

## 6. Auswirkungen auf bestehenden Code (Übersicht)

| Datei | Änderung |
|---|---|
| [src/models.py](../src/models.py) | Neues Feld `ist_zusatzmodul: bool = False` auf `ZHAWModule` |
| [src/data_loader.py](../src/data_loader.py) | Neuer Parameter `ist_zusatzmodul: bool = False` an `load_schedule_from_dataframe()`; neue "Wochentag aus Datum ableiten"-Regel (siehe 2.2) |
| [src/app.py](../src/app.py) | Neuer Upload-Widget + Session-State (`processed_modules_zusatz` o. ä.); Merge-Logik beim Hochladen; Badge-Anzeige an den in 4.2 genannten Stellen; neuer Filter in `render_guided_planning()`; optionale Dashboard-Kachel |
| [src/export.py](../src/export.py) | Quelle-Hinweis in ICS-Beschreibung; Excel-Spalte "Quelle" |
| [src/i18n.py](../src/i18n.py) | ~15-20 neue Keys (DE/EN/FR) für Upload-Label/-Hilfetext, Badge-Text, Filter-Label, KPI-Titel, Export-Spalten-/Beschreibungstext |
| [README.md](../README.md) | Neuer Abschnitt zur Zusatzmodul-Funktion |
| [docs/TESTING-README.md](TESTING-README.md) | Neue Fixture-Datei dokumentieren (siehe Abschnitt 9), neue Tests auflisten |

Bewusst **nicht** angefasst: `src/scheduler.py`s Kernlogik (`find_time_conflicts`) - sie braucht keine Änderung, solange die Parallelgruppen-Frage aus Abschnitt 8 vor der Umsetzung geklärt ist (die Lösung dafür liegt eher in der Datenaufbereitung als im Konfliktalgorithmus selbst).

## 7. Test-/Rollout-Strategie

- Neue Fixture-Datei bereits angelegt (Abschnitt 9); zusätzliche narrow Unit-Tests in `tests/test_data_loader.py` für: Wochentag-Ableitung aus Datum, korrektes Setzen von `ist_zusatzmodul` je nach Upload-Pfad, Merge-Verhalten (Zusatzmodule tauchen in der kombinierten Liste auf, Hauptmodule bleiben unverändert).
- Neuer Test in `tests/test_scheduler.py`: Konflikt zwischen einem Haupt- und einem Zusatzmodul wird erkannt (End-to-End über `find_time_conflicts()`).
- **Kritisches Abnahmekriterium:** Ohne Zusatz-Upload verhält sich die App exakt wie heute - bestehende 146 Tests müssen unverändert grün bleiben, keine bestehende Funktion darf sich für die grosse Mehrheit ohne Passerellen-Hintergrund verändern.
- Manuelle Browser-Verifikation (wie bei allen bisherigen UI-Änderungen in diesem Projekt Standard, siehe [docs/TESTING-README.md](TESTING-README.md) "What isn't covered") nötig für: Badge-Darstellung, neuen Filter, ggf. Diagramm-Anpassungen - das sind UI-Aspekte, die die Testsuite strukturell nicht abdeckt.

## 8. Offene Fragen / Risiken

Bewusst hier aufgeführt statt stillschweigend übergangen, damit sie vor der Umsetzung geklärt werden können:

1. **Parallelgruppen und Konflikterkennung** (siehe 2.3): Wenn mehrere Zeilen mit identischem Termin, aber unterschiedlicher Lehrperson tatsächlich *alternative* Gruppen sind, könnten sie fälschlich als sich gegenseitig überlappende Module gewertet werden, sobald mehr als eine davon ausgewählt wird - oder schon beim reinen Import, falls `find_time_conflicts()` unabhängig von der Auswahl auf der Gesamtliste rechnet. Muss vor der Umsetzung am echten Verhalten von `_module_signature()`/`find_time_conflicts()` überprüft werden; falls nötig, braucht es eine Deduplizierungs-/Gruppierungsregel für "gleicher Termin, gleiches Modul, andere Lehrperson" ähnlich der bestehenden Varianten-Logik (`_split_course_variant`) für Gruppen-Suffixe.
2. **Modul-Nr.-Kollision zwischen den beiden Listen:** Falls (unwahrscheinlich, aber nicht ausgeschlossen) dieselbe Modul-Nr. in Haupt- und Zusatzliste vorkommt, gibt es im MVP keine besondere Deduplizierung - beide Zeilen bleiben bestehen, unterschieden nur durch `ist_zusatzmodul`. In der Praxis sollten Bachelor- und Master-Modulnummern ohnehin unterschiedliche Namensräume/Präfixe verwenden (im Beispiel z. B. keine "Z"-Präfixe wie im MSc-Datensatz), das Risiko ist also eher theoretisch.
3. **Verhalten beim Entfernen der Zusatzdatei:** Sollte nur die Zusatzmodule aus der kombinierten Liste entfernen, die Hauptliste unangetastet lassen (analog zum bestehenden "Datei entfernt"-Verhalten des Haupt-Uploaders, das aktuell die ganze Session zurücksetzt - hier braucht es eine differenziertere Reset-Logik nur für den Zusatzmodul-Teil).
4. **Semesterzeitraum:** `_semester_date_bounds()` (in `src/app.py`) berechnet aktuell ein gemeinsames Semesterfenster über alle Module für die "Bist du in einem Zeitraum abwesend?"-Frage in Schritt 1 der geführten Planung. Bei zusammengeführten Listen mit ggf. leicht unterschiedlichem Datumsbereich (Bachelor- vs. Master-Semester starten/enden nicht zwingend am exakt gleichen Tag) vergrössert sich dieses Fenster einfach entsprechend - funktional unproblematisch, aber gut zu wissen, falls das Verhalten überrascht.
5. **Repräsentativität der Beispieldatei:** Es liegt nur ein Beispiel vor. Ob *jeder* Bachelor-Export keine Wochentagsspalte hat, oder das beim Zusammenstellen des Beispiels nur verloren ging, ist nicht sicher. Die vorgeschlagene "Wochentag aus Datum ableiten"-Regel (2.2) deckt so oder so beide Fälle robust ab (mit und ohne `Tag`-Spalte), das Risiko ist also gering.

## 9. Testdaten (bereits umgesetzt)

[tests/fixtures/vorlesungsverzeichnis_passerelle_fiktiv.xlsx](../tests/fixtures/vorlesungsverzeichnis_passerelle_fiktiv.xlsx) wurde neu angelegt - ein vollständig **fiktiver** Datensatz (erfundene Modultitel, Personennamen, Modul-/Kursnummern; keine echten ZHAW-Curriculum- oder Personendaten), der die Struktur der vom Nutzer bereitgestellten Beispieldatei nachbildet:

- Gleiches Spaltenschema: `SG`, `Semester`, `Lehrperson`, `Datum`, `von`, `bis`, `Modul-Nr.`, `Kurs-Nr.`, `Anlassbezeichnung`, `Pruefung`, `Modulart`.
- Gleicher Aufbau wie die bestehende Hauptfixture ([tests/fixtures/vorlesungsverzeichnis_fiktiv.xlsx](../tests/fixtures/vorlesungsverzeichnis_fiktiv.xlsx)): Titelbanner-Zeile + Hinweiszeile über der echten Kopfzeile, um dieselbe `_try_reheader_from_rows()`-Erkennungslogik auch für diese Dateistruktur zu testen.
- Zwei fiktive Module: ein "normales" Modul mit wöchentlichen Terminen, einer Halbklassen-Teilung (zwei Parallelgruppen am selben Datum mit `- Halbklasse 1`/`- Halbklasse 2`-Suffix) und einem Prüfungstermin; ein zweites Modul, das bewusst das in 2.3 beschriebene Parallelgruppen-Muster nachbildet (sechs Zeilen mit identischem Termin, sechs unterschiedlichen, fiktiven Lehrpersonen).
- **Enthält bewusst keine `Tag`-Spalte**, exakt wie im Nutzerbeispiel - lädt mit dem aktuellen, unveränderten `data_loader.py` daher (erwartungsgemäss) noch **nicht** erfolgreich (siehe der zitierte Fehler in Abschnitt 2.1). Das ist beabsichtigt: die Datei ist als Testfall für die in Abschnitt 2.2 vorgeschlagene "Wochentag aus Datum ableiten"-Regel gedacht, nicht als bereits heute funktionierende Datei.

## 10. Empfohlene Umsetzungsreihenfolge

**Phase 1 (MVP):**
1. Wochentag-aus-Datum-Ableitung in `data_loader.py` (generelle Robustheit, unabhängig von Passerelle nützlich).
2. `ist_zusatzmodul`-Feld auf `ZHAWModule` + Parameter an `load_schedule_from_dataframe()`.
3. Zweiter Upload-Slot in der Sidebar + Merge-Logik.
4. Konfliktprüfung über die kombinierte Liste (keine Codeänderung an `scheduler.py` nötig, siehe Abschnitt 6) - aber Abklärung von Risiko 1 aus Abschnitt 8 **vor** dem Merge scharfschalten.
5. Badge-Anzeige in den bestehenden Tabellen (4.2).
6. Neue Tests + Dokumentation.

**Phase 2:**
- Filter "nur Zusatzmodule" in der geführten Planung.
- Dashboard-KPI-Kachel.
- Export-Kennzeichnung (ICS-Beschreibung, Excel-Spalte).

**Phase 3 (optional, nur falls gewünscht):**
- `herkunfts_semester`-Feld zur Anzeige der `Semester`-Spalte.
- Eigene Farbcodierung/Filterung nach Herkunft in den Diagrammen (Wochenplan, Semesterübersicht).
