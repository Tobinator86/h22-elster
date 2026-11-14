"""
ELSTER-Übermittlung – holt Aufträge bei einer Website ab, prüft bzw. sendet sie mit ERiC an ELSTER
und meldet das Ergebnis zurück. Läuft als Home-Assistant-App (Einstellungen in /data/options.json).

ERiC-Aufrufe nach der ERiC-API-Referenz 44.3 (ericapi.h, eric_types.h):
  EricInitialisiere(pluginPfad, logPfad), EricBeende()
  EricBearbeiteVorgang(datenpuffer, datenartVersion, flags, druckParameter*, cryptoParameter*, rueckgabePuffer, serverantwortPuffer)
  EricGetHandleToCertificate(&handle, &pinSupport, pfad), EricCloseHandleToCertificate(handle)
  EricMakeElsterStnr(bescheid, landesnr, bufanr, puffer), EricHoleFehlerText(rc, puffer), EricVersion(puffer)
"""
import base64
import ctypes
import html
import json
import os
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
import zipfile

VERSION = "0.2.0"
OPTIONS = "/data/options.json"
ERIC_ROOT = "/data/eric"
LOG_DIR = "/data/log"
TMP_DIR = "/data/tmp"
TEST_HERSTELLER = "74931"     # allgemeine Test-Hersteller-ID aus der ERiC-Dokumentation
TEST_PIN = "123456"           # PIN der Testzertifikate, die ERiC mitbringt
TESTMERKER = "700000004"

ERIC_VALIDIERE = 1 << 1
ERIC_SENDE = 1 << 2
ERIC_DRUCKE = 1 << 5


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


def load_options():
    with open(OPTIONS, encoding="utf-8") as f:
        o = json.load(f)
    o["website_url"] = str(o.get("website_url", "")).rstrip("/")
    o["intervall"] = max(20, int(o.get("intervall") or 60))
    return o


# ---------------------------------------------------------------- ERiC entpacken und laden

def unpack_eric(jar):
    """Entpackt das ERiC-Paket (.jar = ZIP) einmalig nach /data/eric/<Name>; gibt den Ordner mit libericapi.so zurück."""
    if not os.path.isfile(jar):
        raise SystemExit(f"ERiC-Paket nicht gefunden: {jar} – bitte die .jar-Datei nach /share legen und den Pfad in der Konfiguration prüfen.")
    name = os.path.splitext(os.path.basename(jar))[0]
    target = os.path.join(ERIC_ROOT, name)
    done = os.path.join(target, ".entpackt")
    if not os.path.isfile(done):
        log(f"Entpacke {jar} … (einmalig, dauert etwas)")
        tmp = target + ".tmp"
        if os.path.isdir(tmp):
            import shutil
            shutil.rmtree(tmp)
        with zipfile.ZipFile(jar) as z:
            z.extractall(tmp)
        if os.path.isdir(target):
            import shutil
            shutil.rmtree(target)
        os.rename(tmp, target)
        open(done, "w").close()
        log("ERiC entpackt.")
    for d, _dirs, files in os.walk(target):
        if "libericapi.so" in files:
            return d
    raise SystemExit("libericapi.so nicht im ERiC-Paket gefunden – ist es die Linux-x86_64-Fassung?")


def ensure_library_path(libdir):
    """ERiC lädt weitere Bibliotheken aus seinem Ordner – LD_LIBRARY_PATH muss vor dem Programmstart stehen, darum Neustart des Prozesses."""
    cur = os.environ.get("LD_LIBRARY_PATH", "")
    if cur.split(":")[0] != libdir:
        os.environ["LD_LIBRARY_PATH"] = libdir + (":" + cur if cur else "")
        os.execv(sys.executable, [sys.executable, "-u"] + sys.argv)


class DruckParameter(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("vorschau", ctypes.c_uint32), ("duplexDruck", ctypes.c_uint32),
                ("pdfName", ctypes.c_char_p), ("fussText", ctypes.c_char_p),
                ("pdfCallback", ctypes.c_void_p), ("pdfCallbackBenutzerdaten", ctypes.c_void_p)]


class VerschluesselungsParameter(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("zertifikatHandle", ctypes.c_uint32), ("pin", ctypes.c_char_p)]


class Eric:
    def __init__(self, libdir):
        self.libdir = libdir
        L = self.lib = ctypes.CDLL(os.path.join(libdir, "libericapi.so"))
        vp, cp, u32 = ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32
        L.EricRueckgabepufferErzeugen.restype = vp
        L.EricRueckgabepufferErzeugen.argtypes = []
        L.EricRueckgabepufferInhalt.restype = cp
        L.EricRueckgabepufferInhalt.argtypes = [vp]
        L.EricRueckgabepufferFreigeben.argtypes = [vp]
        L.EricInitialisiere.argtypes = [cp, cp]
        L.EricBeende.argtypes = []
        L.EricBearbeiteVorgang.argtypes = [cp, cp, u32, ctypes.POINTER(DruckParameter), ctypes.POINTER(VerschluesselungsParameter), vp, vp]
        L.EricGetHandleToCertificate.argtypes = [ctypes.POINTER(u32), ctypes.POINTER(u32), cp]
        L.EricCloseHandleToCertificate.argtypes = [u32]
        L.EricHoleFehlerText.argtypes = [ctypes.c_int, vp]
        L.EricMakeElsterStnr.argtypes = [cp, cp, cp, vp]
        L.EricVersion.argtypes = [vp]
        L.EricHoleTestfinanzaemter.argtypes = [vp]
        os.makedirs(LOG_DIR, exist_ok=True)
        rc = L.EricInitialisiere(None, LOG_DIR.encode())
        if rc != 0:
            # Plugins ausdrücklich im Bibliotheksordner suchen
            rc = L.EricInitialisiere(libdir.encode(), LOG_DIR.encode())
        if rc != 0:
            raise RuntimeError(f"EricInitialisiere fehlgeschlagen ({rc}) – Protokoll in {LOG_DIR}")

    def close(self):
        try:
            self.lib.EricBeende()
        except Exception:
            pass

    def _buf_call(self, fn, *args):
        b = self.lib.EricRueckgabepufferErzeugen()
        try:
            rc = fn(*args, b)
            raw = self.lib.EricRueckgabepufferInhalt(b)
            return rc, (raw.decode("utf-8", "replace") if raw else "")
        finally:
            self.lib.EricRueckgabepufferFreigeben(b)

    def fehlertext(self, rc):
        try:
            return self._buf_call(self.lib.EricHoleFehlerText, rc)[1].strip()
        except Exception:
            return ""

    def version(self):
        rc, xml = self._buf_call(self.lib.EricVersion)
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)", xml)
        return m.group(1) if m else "?"

    def testfinanzaemter(self):
        return self._buf_call(self.lib.EricHoleTestfinanzaemter)[1]

    def elster_stnr(self, bescheid, landesnr):
        rc, out = self._buf_call(self.lib.EricMakeElsterStnr, bescheid.encode(), landesnr.encode(), None)
        if rc != 0:
            raise ValueError(f"Steuernummer {bescheid} passt nicht zur Landesnummer {landesnr}: {self.fehlertext(rc)} ({rc})")
        return out.strip()

    def bearbeite(self, xml, datenart, flags, pdf_path=None, vorschau=True, cert=None, pin=""):
        druck = None
        if flags & ERIC_DRUCKE:
            druck = DruckParameter(4, 1 if vorschau else 0, 0, pdf_path.encode(), None, None, None)
        crypto = None
        handle = ctypes.c_uint32(0)
        if cert:
            pin_support = ctypes.c_uint32(0)
            rc = self.lib.EricGetHandleToCertificate(ctypes.byref(handle), ctypes.byref(pin_support), cert.encode())
            if rc != 0:
                return rc, f"Zertifikat lässt sich nicht öffnen: {self.fehlertext(rc)}", "", ""
            crypto = VerschluesselungsParameter(3, handle.value, pin.encode())
        rb = self.lib.EricRueckgabepufferErzeugen()
        sb = self.lib.EricRueckgabepufferErzeugen()
        try:
            rc = self.lib.EricBearbeiteVorgang(xml.encode("utf-8"), datenart.encode(), flags,
                                               ctypes.byref(druck) if druck else None,
                                               ctypes.byref(crypto) if crypto else None, rb, sb)
            r = self.lib.EricRueckgabepufferInhalt(rb)
            s = self.lib.EricRueckgabepufferInhalt(sb)
            return rc, (self.fehlertext(rc) if rc else ""), (r.decode("utf-8", "replace") if r else ""), (s.decode("utf-8", "replace") if s else "")
        finally:
            self.lib.EricRueckgabepufferFreigeben(rb)
            self.lib.EricRueckgabepufferFreigeben(sb)
            if cert and handle.value:
                self.lib.EricCloseHandleToCertificate(handle.value)


# ---------------------------------------------------------------- Website

class Website:
    def __init__(self, o, info):
        self.url = o["website_url"] + "/elster/api"
        self.key = o["schluessel"]
        self.info = info

    def call(self, schritt, **data):
        body = json.dumps({"schritt": schritt, "app": self.info, **data}).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Authorization": "Bearer " + self.key, "Content-Type": "application/json", "User-Agent": f"elster-uebermittlung/{VERSION}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8", "replace")
            try:
                return json.loads(raw or "{}")
            except ValueError:
                raise RuntimeError("Website antwortet nicht wie erwartet – hat die Seite die ELSTER-Schnittstelle (/elster/api)? Adresse prüfen.")
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("fehler", "")
            except Exception:
                msg = ""
            raise RuntimeError(f"Website antwortet {e.code}: {msg or e.reason}")


# ---------------------------------------------------------------- Aufträge

def meldungen(*xmls):
    """Lesbare Meldungen (Fehler/Hinweise) aus Rückgabe- und Serverantwort-XML"""
    out = []
    for x in xmls:
        for t in re.findall(r"<Text>(.*?)</Text>", x or "", re.S):
            t = html.unescape(re.sub(r"\s+", " ", t)).strip()
            if t and t not in out:
                out.append(t)
    return out[:50]


def transferticket(*xmls):
    for x in xmls:
        m = re.search(r"<TransferTicket>([^<]+)</TransferTicket>", x or "")
        if m:
            return m.group(1).strip()
    return ""


def find_test_cert(eric_dir):
    found = []
    for d, _dirs, files in os.walk(eric_dir):
        for f in files:
            if f.lower().endswith(".pfx"):
                found.append(os.path.join(d, f))
    found.sort(key=lambda p: (("softorg" not in p.lower()), ("test" not in p.lower()), p))
    return found


def handle(job, o, eric, eric_dir):
    """Bearbeitet einen Auftrag; gibt das Ergebnis für die Website zurück."""
    jid, modus = int(job["id"]), job["modus"]
    test = bool(job.get("test"))
    if not test and o["testbetrieb"]:
        return {"ok": False, "text": "Die App ist im Testbetrieb, der Auftrag aber nicht – nichts gesendet. Erst in der App den Testbetrieb ausschalten (Konfiguration)."}
    xml = job["xml"]
    if test and "<Testmerker>" not in xml:
        return {"ok": False, "text": "Testauftrag ohne Testmerker – aus Sicherheitsgründen nichts gesendet."}
    if not test and "<Testmerker>" in xml:
        return {"ok": False, "text": "Echter Auftrag mit Testmerker – bitte neu anlegen."}

    hersteller = (o.get("hersteller_id") or "").strip() or (TEST_HERSTELLER if test else "")
    if not hersteller:
        return {"ok": False, "text": "Keine Hersteller-ID eingetragen (App-Konfiguration)."}
    if test:
        stnr = o.get("test_steuernummer") or "1096081508187"
    else:
        bescheid, land = str(job.get("steuernummer") or ""), str(job.get("landesnr") or "")
        try:
            stnr = eric.elster_stnr(bescheid, land)
        except ValueError as e:
            digits = re.sub(r"\D", "", bescheid)
            if len(digits) == 10:   # führende 0 fehlt oft (z. B. Hessen 0FF BBB UUUUP)
                stnr = eric.elster_stnr("0" + digits, land)
            else:
                return {"ok": False, "text": str(e)}
    xml = (xml.replace("{HERSTELLER_ID}", hersteller).replace("{STNR}", stnr)
              .replace("{BUFA}", stnr[:4]).replace("{TICKET}", str(jid)))

    os.makedirs(TMP_DIR, exist_ok=True)
    pdf = os.path.join(TMP_DIR, f"auftrag-{jid}.pdf")
    if os.path.exists(pdf):
        os.remove(pdf)
    cert, pin = None, o.get("pin") or ""
    if modus == "senden":
        cert = o.get("zertifikat") or ""
        if not os.path.isfile(cert):
            if not test:
                return {"ok": False, "text": f"Zertifikat nicht gefunden: {cert} – bitte die .pfx-Datei aus Mein ELSTER in den App-Ordner legen."}
            tc = find_test_cert(eric_dir)
            if not tc:
                return {"ok": False, "text": "Kein Testzertifikat (.pfx) im ERiC-Paket gefunden."}
            cert, pin = tc[0], (pin or TEST_PIN)
            log(f"Testzertifikat: {cert}")
        flags = ERIC_VALIDIERE | ERIC_SENDE | ERIC_DRUCKE
    else:
        flags = ERIC_VALIDIERE | ERIC_DRUCKE

    log(f"Auftrag {jid}: {modus} {job.get('datenart')} {job.get('zeitraum')}{' (Test)' if test else ''}")
    rc, text, antwort, server = eric.bearbeite(xml, job["datenart"], flags, pdf, vorschau=(modus != "senden"), cert=cert, pin=pin)
    res = {"ok": rc == 0, "rc": rc, "text": text, "meldungen": meldungen(antwort, server),
           "ticket": transferticket(antwort, server), "antwort": antwort[:400000], "server": server[:400000]}
    if os.path.isfile(pdf):
        with open(pdf, "rb") as f:
            res["pdf"] = base64.b64encode(f.read()).decode("ascii")
        os.remove(pdf)
    log(f"Auftrag {jid}: {'ok' if rc == 0 else 'Fehler ' + str(rc)} {text} {res['ticket']}".strip())
    return res


def main():
    o = load_options()
    libdir = unpack_eric(o["eric_datei"])
    ensure_library_path(libdir)
    eric_dir = os.path.dirname(os.path.dirname(libdir)) if os.path.basename(libdir) == "lib" else libdir
    eric = Eric(libdir)
    ever = eric.version()
    log(f"ELSTER-Übermittlung {VERSION}, ERiC {ever}, {'Testbetrieb' if o['testbetrieb'] else 'ECHTBETRIEB'}, Website {o['website_url']}")
    try:
        tf = eric.testfinanzaemter()
        log("Testfinanzämter (Auszug): " + re.sub(r"\s+", " ", tf)[:600])
    except Exception as e:
        log(f"Testfinanzämter nicht abrufbar: {e}")
    certs = find_test_cert(eric_dir)
    log("Zertifikate im ERiC-Paket: " + (", ".join(os.path.relpath(c, eric_dir) for c in certs[:6]) or "keine"))
    if not o["website_url"].startswith("https://"):
        log("Keine Adresse der Website eingetragen (https://…) – bitte in der App-Konfiguration ergänzen.")
    if not o.get("schluessel"):
        log("Kein Schlüssel eingetragen – bitte auf der Website erzeugen und in der App-Konfiguration eintragen.")
    own_cert = o.get("zertifikat") or ""
    info = {"version": VERSION, "eric": ever, "test": bool(o["testbetrieb"]),
            "hersteller": bool(o.get("hersteller_id")), "zertifikat": os.path.isfile(own_cert)}
    at = Website(o, info)
    try:
        r = at.call("hallo")
        log(f"Website erreicht ({'Beta, ' if r.get('beta') else ''}{'Testbetrieb' if r.get('test') else 'Echtbetrieb'}).")
    except Exception as e:
        log(f"Website nicht erreichbar: {e}")

    while True:
        try:
            r = at.call("holen")
            job = r.get("auftrag")
            if job:
                try:
                    res = handle(job, o, eric, eric_dir)
                except Exception as e:
                    traceback.print_exc()
                    res = {"ok": False, "text": f"Fehler in der App: {e}"}
                at.call("ergebnis", id=job["id"], **res)
                continue
        except Exception as e:
            log(f"Fehler: {e}")
        time.sleep(o["intervall"])


if __name__ == "__main__":
    main()
