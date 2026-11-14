# ELSTER-Übermittlung

Holt Steueranmeldungen (zurzeit die Umsatzsteuer-Voranmeldung) von einer Website ab,
prüft bzw. sendet sie mit ERiC an ELSTER und meldet Transferticket, ELSTER-Protokoll (PDF)
und Fehlermeldungen zurück. Die Website legt die Aufträge an; die App fragt sie über
`POST <Adresse>/elster/api` ab (Schlüssel als Bearer-Token).

## Einrichten

1. **ERiC ablegen:** Die Datei `ERiC-<Version>-Linux-x86_64.jar` aus dem ELSTER-Entwicklerbereich nach `/share`
   legen (z. B. mit Studio Code Server). Die App entpackt sie beim ersten Start selbst.
2. **Konfiguration:** Adresse der Website und den dort erzeugten Schlüssel eintragen.
3. **Starten** und im Protokoll prüfen: „ERiC …“, „Website erreicht“.

## Testbetrieb (Standard)

- Nur Aufträge mit Testmerker; Test-Hersteller-ID 74931, Test-Steuernummer, Testzertifikat aus dem ERiC-Paket.
- ELSTER prüft und quittiert, beim Finanzamt kommt nichts an.

## Echtbetrieb

Erst wenn die eigene Hersteller-ID bestätigt ist und ein Testversand geklappt hat:

1. **Hersteller-ID** eintragen.
2. **ELSTER-Zertifikat** (.pfx aus Mein ELSTER) in den Ordner dieser App legen
   (in Studio Code Server: `/addon_configs/…_elster_uebermittlung/zertifikat.pfx`) und die **PIN** eintragen.
3. **Testbetrieb** ausschalten – hier und auf der Website.

Beide Seiten müssen zusammenpassen: Ein echter Auftrag wird von einer App im Testbetrieb abgelehnt
und umgekehrt – es geht also nie versehentlich etwas ans Finanzamt.

## Sicherheit

- Die App fragt nur nach außen (HTTPS zur Website, ERiC zu ELSTER); am Router muss nichts geöffnet werden.
- Zertifikat und PIN bleiben auf diesem Server. ERiC selbst liegt nicht im Repository (Lizenz).
- ERiC schreibt sein Protokoll nach `/data/log` (in der App).
