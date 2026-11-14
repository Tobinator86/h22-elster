# ELSTER-Übermittlung (Home-Assistant-App)

Holt Steueranmeldungen (zurzeit die Umsatzsteuer-Voranmeldung) von einer Website ab,
prüft bzw. sendet sie mit **ERiC** an ELSTER und meldet das Ergebnis (Transferticket,
ELSTER-Protokoll als PDF, Fehlermeldungen) zurück.

- Die App fragt nur nach außen – am Router muss nichts geöffnet werden.
- ERiC selbst, das ELSTER-Zertifikat und die PIN liegen nur auf dem Home-Assistant-Server,
  nie in diesem Repository (ERiC darf nicht weitergegeben werden).

Installation und Einstellungen: siehe [elster/DOCS.md](elster/DOCS.md).
