# H22 ELSTER

Übermittelt die Umsatzsteuer-Voranmeldung der Galerie H22 über ERiC an ELSTER.
Das Atelier legt die Aufträge an (Finanzen → Umsatzsteuer → „Direkt an ELSTER“); diese App holt sie ab,
prüft bzw. sendet sie und meldet Transferticket, ELSTER-Protokoll (PDF) und Fehlermeldungen zurück.

## Einrichten

1. **ERiC ablegen:** Die Datei `ERiC-<Version>-Linux-x86_64.jar` aus dem ELSTER-Entwicklerbereich nach `/share`
   legen (z. B. mit Studio Code Server). Die App entpackt sie beim ersten Start selbst.
2. **Schlüssel:** Im Atelier unter Finanzen → Umsatzsteuer → „Verbindung zur ELSTER-App“ (nur Super-Admin)
   „Schlüssel erzeugen“, hier bei **Schlüssel** eintragen, **Adresse des Ateliers** dazu (z. B. `https://beta.galerieh22.de`).
3. **Starten** und im Protokoll prüfen: „ERiC …“, „Atelier erreicht“.

## Testbetrieb (Standard)

- Nur Aufträge mit Testmerker; Test-Hersteller-ID 74931, Test-Steuernummer, Testzertifikat aus dem ERiC-Paket.
- ELSTER prüft und quittiert, beim Finanzamt kommt nichts an.
- Die Beta des Ateliers erzeugt immer nur Testaufträge.

## Echtbetrieb

Erst wenn die eigene Hersteller-ID bestätigt ist und ein Testversand geklappt hat:

1. **Hersteller-ID** eintragen.
2. **ELSTER-Zertifikat** (.pfx aus Mein ELSTER) in den Ordner dieser App legen
   (in Studio Code Server: `/addon_configs/…_h22_elster/zertifikat.pfx`) und die **PIN** eintragen.
3. Hier **Testbetrieb** ausschalten – und im Atelier ebenfalls (Super-Admin, gleiche Stelle wie der Schlüssel).

Beide Seiten müssen zusammenpassen: Ein echter Auftrag wird von einer App im Testbetrieb abgelehnt
und umgekehrt – es geht also nie versehentlich etwas ans Finanzamt.

## Sicherheit

- Die App fragt nur nach außen (HTTPS zum Atelier, ERiC zu ELSTER); am Router muss nichts geöffnet werden.
- Zertifikat und PIN bleiben auf diesem Server. ERiC selbst liegt nicht im Repository (Lizenz).
- ERiC schreibt sein Protokoll nach `/data/log` (in der App).
