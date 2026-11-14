# H22 ELSTER (Home-Assistant-App)

Übermittelt die Umsatzsteuer-Voranmeldung der Galerie H22 über **ERiC** an ELSTER.
Das Atelier (galerieh22.de) legt Aufträge an; diese App holt sie ab, prüft bzw. sendet sie mit ERiC
und meldet das Ergebnis (Transferticket, ELSTER-Protokoll als PDF, Fehlermeldungen) zurück.

- Die App fragt nur nach außen – am Router muss nichts geöffnet werden.
- ERiC selbst, das ELSTER-Zertifikat und die PIN liegen **nur auf dem Home-Assistant-Server**,
  nie in diesem Repository (ERiC darf nicht weitergegeben werden).

Installation und Einstellungen: siehe [elster/DOCS.md](elster/DOCS.md).
