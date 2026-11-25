# Zeitgesteuerter Besuch der Streamlit-App

Während der Planungsphase besucht ein GitHub-Actions-Runner die öffentliche
App täglich um **05:23 und 11:27 Uhr in Europe/Zurich**. Der Headless-Browser
erkennt die dokumentierte Streamlit-Schlafseite, betätigt deren Aufweckknopf
höchstens einmal und wartet auf die tatsächliche Oberfläche. Die Morgenzeit
bietet Reserve für beobachtete Aufweckzeiten bis zu 20 Minuten.

## Dateien und Konfiguration

- [Workflow](../.github/workflows/wake-streamlit.yml): Auslöser, Runner und Installation.
- [Browser-Skript](../scripts/wake_streamlit.py): Prüfung und Fehlerdiagnose.
- [Separate Abhängigkeit](../scripts/requirements-wake.txt): Playwright nur für den Runner.
- [Tests](../tests/test_wake_streamlit.py): lokale Tests ohne Besuch der veröffentlichten App.

In GitHub unter **Settings → Secrets and variables → Actions → Variables**
eine **Repository variable** namens `STREAMLIT_APP_URL` anlegen und als Wert
die öffentliche App-Adresse eintragen:

```text
https://zhaw-msc-psy-timetable-planner.streamlit.app/
```

Diese vom Betreiber angegebene Adresse wurde noch nicht im Live-Betrieb geprüft.
Keine Zugangsdaten oder Tokens in die Adresse aufnehmen. Ein Secret
ist für eine öffentliche Adresse nicht nötig. Fehlende, ungültige oder
offensichtliche Platzhalter-Adressen führen zum Fehler vor dem Browserstart.
Die App muss ohne Anmeldung erreichbar sein; Anmeldungen, CAPTCHAs und andere
Zugriffsbeschränkungen werden nicht umgangen.

Der Workflow muss auf dem **Standardbranch** liegen, damit GitHub ihn zeitgesteuert
ausführt und über die Oberfläche manuell anbietet. Actions müssen im Repository
zugelassen sein. Die Änderungen werden nicht automatisch veröffentlicht;
die Freigabe und Veröffentlichung bleiben eine separate Entscheidung.

## Erster manueller Test

1. Nach Freigabe und Veröffentlichung auf dem Standardbranch die obige Variable setzen.
2. Auf GitHub **Actions → Streamlit-App aufwecken → Run workflow** öffnen,
   den Standardbranch wählen und den Lauf starten.
3. Den Lauf öffnen: Ein grüner Status und die Job-Summary bestätigen, dass
   die Bereitschaftsprüfung bestanden wurde. Das Log zeigt, ob ein Aufweckversuch
   nötig war; bei einem Fehler die einzelnen Schritte und das gegebenenfalls
   hochgeladene Artefakt `streamlit-wake-diagnostic` prüfen.
4. Ein Test einer bereits aktiven App belegt **nicht**, dass das Aufwecken
   funktioniert. Den Schlafzustand bei einer späteren Gelegenheit gesondert
   testen, ohne künstliche wiederholte Aufweckversuche zu erzeugen.

Die Prüfung bestätigt in einer frischen Sitzung die sichtbare Registerkarte
„🧭 Geführte Planung“ und den Hinweis „Bitte zuerst eine Planungsdatei
hochladen.“ nach dem Start der wesentlichen Oberfläche. Sichtbare Streamlit-
Ausnahmen verhindern Erfolg. Es werden weder Dateien hochgeladen noch
Stundenpläne, Exporte oder Formulare verändert. Die Prüfung testet keine
vollständigen Planungsfunktionen, Exporte oder Datenquellen. Ändern sich die
deutsche Standardsprache oder diese Texte, muss das Skript angepasst werden.

Das Skript begrenzt die Browserprüfung auf 25 Minuten, prüft etwa alle
12 Sekunden und versucht eine fehlgeschlagene Navigation höchstens einmal
erneut. Bei einem Navigationstimeout wartet es ohne Neuladen weiter; der
Job hat 35 Minuten Zeit. Bei Fehlern kann ein Screenshot der aktuellen Seite
für sieben Tage als Actions-Artefakt gespeichert werden. Er kann angezeigte
Seiteninhalte enthalten: Zugriff auf Actions-Artefakte entsprechend beschränken
und keine persönlichen Daten oder Zugangsdaten in der getesteten Sitzung
verwenden. Cookies, Browserprofile und vollständiges HTML werden nicht gespeichert;
URLs und Fehlermeldungen des Browsers werden nicht in die Logs übernommen.

## Zeiten ändern oder abschalten

Im [Workflow](../.github/workflows/wake-streamlit.yml) stehen unter `schedule`
die Cron-Ausdrücke `23 5 * * *` und `27 11 * * *` mit
`timezone: "Europe/Zurich"`. GitHub berücksichtigt damit Sommer- und Winterzeit.
Zum Ändern die gewünschten lokalen Minuten/Stunden in den Ausdrücken anpassen
und die Zeitzone beibehalten. Nach der Nutzungsphase den gesamten Block
`schedule:` samt seinen beiden Einträgen entfernen und `workflow_dispatch:`
stehen lassen: Nach Veröffentlichung bleibt die manuelle Ausführung erhalten.
Den gesamten Workflow in GitHub zu deaktivieren würde auch manuelle Starts
verhindern.

## Grenzen

- GitHub plant Startzeiten, garantiert aber keine sekundengenaue Ausführung;
  geplante Läufe können sich verzögern oder ausfallen.
- In öffentlichen Repositories kann GitHub geplante Workflows nach 60 Tagen
  ohne Repository-Aktivität deaktivieren. Den Status regelmässig prüfen.
- GitHub lässt jeweils nur einen Lauf dieser Concurrency-Gruppe gleichzeitig
  laufen; ein laufender Versuch wird nicht abgebrochen, ein bereits wartender
  Lauf kann durch einen neueren ersetzt werden.
- Streamlit kann die Schlafseite oder ihren Knopf ändern. Browserautomation ist
  keine garantierte Wake-up-API; auch ist nicht garantiert, dass automatisierter
  Verkehr als Aktivität gezählt wird.
- Die Lösung garantiert keine Verfügbarkeit und behebt keine Ursache langer
  Startzeiten. Eine tatsächliche Nutzung kann die App nachts wachhalten;
  Einschlafen wird nicht erzwungen.

Quellen: [GitHub-Zeitpläne](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule),
[GitHub-Workflow-Deaktivierung](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows),
[Streamlit-App-Hibernation](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app),
[Playwright Python](https://playwright.dev/python/docs/intro).
