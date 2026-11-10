"""LagDoctor - AUTODIAGNOSI (programma separato, SOLO LETTURA).

Controlla che ogni funzione di LagDoctor funzioni davvero su questo PC, senza cambiare NIENTE:
  - legge lo stato di tutte le ottimizzazioni (come fa il programma)
  - legge le impostazioni del driver video, i sensori, i contatori di Windows
  - fa una breve registrazione di prova con PresentMon (sulla finestra del desktop, nessun gioco)
  - controlla che i comandi usati per applicare/annullare le modifiche ESISTANO e siano scritti bene,
    analizzandoli come testo, SENZA eseguirli
  - controlla i permessi di scrittura del registro aprendo le chiavi, SENZA scrivere niente

Protezione: prima di iniziare vengono BLOCCATE tutte le funzioni che possono modificare il PC (scrittura del
registro, comandi di modifica, impostazioni del driver). Se per errore qualcosa provasse a cambiare il sistema,
viene fermato e segnalato nel risultato.

Alla fine crea un file .zip nella cartella "autodiagnosi": e' quello da mandare.
"""
import base64
import ctypes
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from lagdoctor import paths as _paths  # noqa: E402  (solo percorsi: non modifica niente)
OUT_DIR = os.path.join(_paths.DATA_DIR, "autodiagnosi")
STAMP = time.strftime("%Y%m%d-%H%M%S")
WORK = os.path.join(OUT_DIR, "prova-" + STAMP)
os.makedirs(WORK, exist_ok=True)

RESULTS = []        # un elemento per ogni controllo
TRACE = []          # ogni comando eseguito con il suo output (troncato)
BLOCKED = []        # tentativi di modifica fermati dalla protezione
CURRENT = {"test": ""}


# ====================================================================== PROTEZIONE: niente modifiche
class Blocked(RuntimeError):
    pass


def _block(what):
    BLOCKED.append({"test": CURRENT["test"], "azione": str(what)[:500]})
    raise Blocked("BLOCCATO dall'autodiagnosi (sola lettura): " + str(what)[:200])


# Comandi che modificano il sistema. Tutto il resto (letture) e' permesso.
_PS_WRITE = re.compile(
    r"\b(set|remove|add|disable|enable|new|stop|start|restart|clear|register|unregister|install|uninstall|"
    r"rename|move|copy|reset|suspend|resume|mount|dismount|update|checkpoint|invoke|import|export)-[a-z]"
    r"|\.(delete|put|create|setvalue|change|terminate)\s*\("
    r"|\b(reg(\.exe)?\s+(add|delete|import|copy|restore|load|unload))\b"
    r"|\bwinget\b|\bvssadmin\b|\bwmic\b.*\bcall\b|\bdism\b|\bsfc\b"
    r"|\bbcdedit\s+/(?!enum\b)|\bschtasks\s+/(?!query\b)|\bnetsh\b[^;|]*\b(set|add|delete|reset)\b"
    r"|\bfsutil\b[^;|]*\bset\b|\bsc(\.exe)?\s+(stop|start|config|delete|create)\b"
    r"|\bpowercfg\s+[/-](?!(query|q|qh|getactivescheme|list|l|getactiveoverlayscheme)\b)",
    re.I)


def _cmd_is_write(args):
    if isinstance(args, (list, tuple)):
        parts = [str(a) for a in args]
    else:
        parts = str(args).split()
    if not parts:
        return False
    exe = os.path.basename(parts[0]).lower().replace(".exe", "")
    rest = " ".join(parts[1:]).lower()
    if exe in ("powershell", "pwsh"):
        if "-file" in rest:
            return False  # solo la scansione di LagDoctor (script di sola lettura, controllato a parte)
        return bool(_PS_WRITE.search(rest))
    if exe == "powercfg":
        return not re.match(r"^\s*[/-](query|q|qh|getactivescheme|list|l|getactiveoverlayscheme|a|availablesleepstates)\b",
                            rest)
    if exe == "bcdedit":
        return not re.match(r"^\s*/enum\b", rest)
    if exe == "schtasks":
        return not re.match(r"^\s*/query\b", rest)
    if exe == "sc":
        return not re.match(r"^\s*(query|qc|queryex)\b", rest)
    if exe == "netsh":
        return bool(re.search(r"\b(set|add|delete|reset|install|uninstall)\b", rest))
    if exe == "fsutil":
        return "query" not in rest
    if exe in ("reg",):
        return not re.match(r"^\s*query\b", rest)
    if exe in ("nvidia-smi",):
        return bool(re.search(r"(^|\s)-(pl|lgc|rgc|lmc|rmc|pm|e|r|ac|rac|acp|c|am|caa)\b|--(power-limit|lock|reset|"
                              r"applications-clocks|persistence|ecc|compute-mode|auto-boost)", rest))
    if "presentmon" in exe:
        # registrazione di prova: solo con il nome di sessione dell'autodiagnosi
        return "lagdoctorautotest" not in rest
    if exe == "cmd" and rest.strip() in ("/c ver", "/c ver.exe"):
        return False  # versione di Windows
    if exe == "lagdoctorhelper" and rest.strip() == "--probe":
        return False  # sonda di latenza della versione installata
    if exe in ("python", "python3", "pythonw", "py"):
        return not (len(parts) >= 3 and parts[1] == "-c")  # solo la sonda di latenza
    if exe in ("explorer",):
        return False
    return True  # qualsiasi altro programma: non serve all'autodiagnosi


_RealPopen = subprocess.Popen


class GuardedPopen(_RealPopen):
    def __init__(self, args, *a, **kw):
        if _cmd_is_write(args):
            _block(args if isinstance(args, str) else " ".join(str(x) for x in args))
        super().__init__(args, *a, **kw)


subprocess.Popen = GuardedPopen
_real_run = subprocess.run


def _logged_run(args, *a, **kw):
    t0 = time.time()
    cmd_s = (args if isinstance(args, str) else " ".join(map(str, args)))[:600]
    try:
        r = _real_run(args, *a, **kw)
    except Exception as e:
        TRACE.append({"test": CURRENT["test"], "cmd": cmd_s, "code": None, "s": round(time.time() - t0, 2),
                      "out": "ECCEZIONE: %s" % e})
        raise
    out = r.stdout if r.stdout is not None else ""
    err = r.stderr if r.stderr is not None else ""
    if isinstance(out, bytes):
        out = out.decode("utf-8", "replace")
    if isinstance(err, bytes):
        err = err.decode("utf-8", "replace")
    TRACE.append({"test": CURRENT["test"], "cmd": cmd_s,
                  "code": r.returncode, "s": round(time.time() - t0, 2), "out": (out + err)[-1500:]})
    return r


subprocess.run = _logged_run
os.startfile = lambda *a, **k: _block("os.startfile %s" % (a,))

try:
    import winreg
except ImportError:
    winreg = None
if winreg is not None:
    for _fn in ("SetValueEx", "SetValue", "DeleteValue", "DeleteKey", "DeleteKeyEx", "CreateKey", "CreateKeyEx",
                "SaveKey", "LoadKey", "FlushKey"):
        if hasattr(winreg, _fn):
            setattr(winreg, _fn, (lambda name: (lambda *a, **k: _block("registro: winreg.%s %s" % (name, a[1:3]))))(_fn))

# ====================================================================== moduli di LagDoctor
IMPORT_ERR = None
try:
    import psutil
    from lagdoctor import tweaks as T
    from lagdoctor import extra_tweaks as XT  # noqa: F401  (registra le voci nel catalogo)
    from lagdoctor import driver_tweaks as DT  # noqa: F401
    from lagdoctor import gpu_driver as GD, checks, scan, capture, pdh, stutter, analysis
    from lagdoctor import gpu as gpumod
    T.init(_paths.DATA_DIR)
    # ulteriori blocchi alle funzioni di modifica di LagDoctor
    T.reg_write = lambda *a, **k: _block("registro: %s\\%s -> %s" % (a[0], a[1], a[2]))
    T.reg_delete = lambda *a, **k: _block("registro (cancella): %s\\%s -> %s" % (a[0], a[1], a[2]))
    T.set_startup = lambda *a, **k: _block("avvio automatico")
    T.create_restore_point = lambda *a, **k: _block("punto di ripristino")
    GD.amd_set = lambda *a, **k: _block("impostazione AMD %s" % (a,))
    GD.NvDrs.set = lambda self, *a, **k: _block("impostazione NVIDIA %s" % (a,))
    GD.NvDrs.reset = lambda self, *a, **k: _block("reset impostazione NVIDIA %s" % (a,))
    scan.set_refresh = lambda *a, **k: _block("frequenza monitor")
    for _t in T.CATALOG:
        _t.apply = (lambda tid: (lambda *a, **k: _block("applica " + tid)))(_t.id)
        _t.revert = (lambda tid: (lambda *a, **k: _block("annulla " + tid)))(_t.id)
except Exception:
    IMPORT_ERR = traceback.format_exc()


# ====================================================================== utilita'
def say(msg=""):
    print(msg, flush=True)


def test(name, fn, *a, **kw):
    """Esegue un controllo: fn restituisce (esito, dettagli) con esito 'OK' / 'ATTENZIONE' / 'ERRORE'."""
    CURRENT["test"] = name
    say("  - %s..." % name)
    t0 = time.time()
    try:
        esito, det = fn(*a, **kw)
    except Blocked as e:
        esito, det = "BLOCCATO", str(e)
    except Exception:
        esito, det = "ERRORE", traceback.format_exc()[-2500:]
    dt = time.time() - t0
    RESULTS.append({"test": name, "esito": esito, "secondi": round(dt, 1), "dettagli": det})
    mark = {"OK": "ok", "ATTENZIONE": "ATTENZIONE", "ERRORE": "ERRORE", "BLOCCATO": "BLOCCATO"}.get(esito, esito)
    say("      -> %s (%.1f s)" % (mark, dt))
    return esito, det


def jsonable(x):
    try:
        json.dumps(x)
        return x
    except (TypeError, ValueError):
        if isinstance(x, dict):
            return {str(k): jsonable(v) for k, v in x.items()}
        if isinstance(x, (list, tuple, set)):
            return [jsonable(v) for v in x]
        if isinstance(x, bytes):
            return x.hex()
        return repr(x)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return None


# ====================================================================== controlli
STATE = {}


def t_env():
    try:
        wv = sys.getwindowsversion()
        win = "%d.%d build %d" % (wv.major, wv.minor, wv.build)
    except AttributeError:
        win = sys.platform
    d = {"windows": win, "python": sys.version,
         "admin": is_admin(), "cartella": ROOT, "psutil": getattr(psutil, "__version__", None)}
    try:
        import locale
        d["lingua"] = locale.getlocale()
        d["lingua_ui"] = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except Exception:
        pass
    d["comandi"] = {c: bool(shutil.which(c)) for c in ("powershell", "powercfg", "bcdedit", "schtasks", "sc",
                                                       "netsh", "fsutil", "winget", "nvidia-smi")}
    missing = [c for c, ok in d["comandi"].items() if not ok and c != "nvidia-smi"]
    if not d["admin"]:
        return "ERRORE", dict(d, problema="Non e' avviato come amministratore: usa AUTODIAGNOSI.bat")
    return ("ATTENZIONE" if missing else "OK"), d


def t_checks():
    info, probs = checks.run_all()
    STATE["sysinfo"] = info
    T.CONTEXT.update(refresh_hz=info.get("refresh_hz"), vendor=(info.get("gpu") or {}).get("vendor"))
    empty = [k for k in ("cpu", "gpu", "ram", "refresh_hz") if not info.get(k)]
    return ("ATTENZIONE" if empty else "OK"), {"sysinfo": info, "problemi": [p.get("titolo") for p in probs],
                                               "campi_vuoti": empty}


def t_gpu():
    ad = gpumod.list_adapters()
    gi = gpumod.gpu_info()
    STATE["gpu"] = gi
    return ("OK" if gi and gi.get("vendor") in ("nvidia", "amd", "intel") else "ATTENZIONE"), {"schede": ad,
                                                                                                "principale": gi}


def t_scan_ps():
    d = scan.run_powershell_scan()
    STATE["scan"] = d
    if not d:
        return "ERRORE", "La scansione PowerShell non ha restituito dati"
    empty = sorted(k for k, v in d.items() if v in (None, "", [], {}))
    errs = {k: v for k, v in d.items() if isinstance(v, dict) and "error" in v}
    summary = {k: (v if len(json.dumps(jsonable(v))) < 400 else "(%d caratteri)" % len(json.dumps(jsonable(v))))
               for k, v in d.items()}
    return ("ATTENZIONE" if (empty or errs) else "OK"), {"sezioni": len(d), "vuote": empty, "errori": errs,
                                                         "contenuto": summary}


def t_displays():
    ds = scan.displays()
    return ("OK" if ds else "ATTENZIONE"), ds


def t_driver():
    vendor = (STATE.get("gpu") or {}).get("vendor")
    if vendor not in ("nvidia", "amd"):
        return "ATTENZIONE", "Scheda non NVIDIA/AMD: lettura del driver non disponibile"
    r = GD.read(vendor, (STATE.get("sysinfo") or {}).get("refresh_hz"), max_age=0)
    out = {"ok": r.get("ok"), "errore": r.get("error"), "raw": r.get("raw"),
           "errori_lettura": r.get("read_errors"), "salvate_nel_profilo": r.get("stored_count"),
           "elenco_salvate": r.get("stored"),
           "righe": [(x.get("name"), x.get("value"), x.get("level")) for x in r.get("rows", [])],
           "problemi": [p.get("titolo") for p in r.get("problems", [])]}
    if not r.get("ok"):
        return "ERRORE", out
    raw = r.get("raw") or {}
    # "non impostata" (valore predefinito del driver) e' normale; un errore di lettura no
    out["al_predefinito"] = [k for k, v in raw.items() if v is None or (isinstance(v, list) and v and v[0] is None)]
    return ("ERRORE" if r.get("read_errors") else "OK"), out


def t_nvidia_extra():
    if (STATE.get("gpu") or {}).get("vendor") != "nvidia":
        return "OK", "non NVIDIA"
    d = scan.nvidia_extra()
    return ("OK" if d else "ATTENZIONE"), d


def t_catalog():
    vendor = (STATE.get("gpu") or {}).get("vendor")
    rows, none, err = [], [], []
    for t in T.for_vendor(vendor):
        CURRENT["test"] = "Stato ottimizzazioni: " + t.id
        t0 = time.time()
        try:
            st = t.status()
            e = None
        except Blocked:
            raise
        except Exception as ex:
            st, e = None, "%s: %s" % (type(ex).__name__, ex)
        extra = {}
        try:
            if hasattr(t, "values") and callable(getattr(t, "values")):
                extra["registro"] = [[h, p, n, T.reg_read(h, p, n)[0], v] for h, p, n, _ty, v in (t.values() or [])]
            if hasattr(t, "service"):
                extra["servizio_start"] = T.reg_read("HKLM", T.ServiceTweak.KEY + "\\" + t.service, "Start")[0]
        except Exception as ex:
            extra["errore_lettura"] = str(ex)
        rows.append({"id": t.id, "tipo": type(t).__name__, "cat": t.cat, "stato": st, "errore": e,
                     "nota": getattr(t, "note", None),
                     "s": round(time.time() - t0, 2), **jsonable(extra)})
        if e:
            err.append(t.id)
        elif st is None and type(t).__name__ != "DefenderExclusionTweak" and not getattr(t, "note", None):
            none.append(t.id)
    CURRENT["test"] = "Stato di tutte le ottimizzazioni"
    STATE["catalog"] = rows
    esito = "ERRORE" if err else ("ATTENZIONE" if none else "OK")
    return esito, {"voci": len(rows), "attive": sum(1 for r in rows if r["stato"] is True),
                   "non_attive": sum(1 for r in rows if r["stato"] is False),
                   "non_verificabili": none, "errori": err, "dettaglio": rows}


def t_appx():
    names = XT.installed_appx()
    if names is None:
        return "ERRORE", "Get-AppxPackage non ha funzionato"
    found = {}
    for t in T.CATALOG:
        if type(t).__name__ == "AppxTweak":
            found[t.id] = [p for p in t.packages if p.lower() in names]
    return "OK", {"pacchetti_installati": len(names), "voci_debloat_trovate": found}


def t_startup():
    items = T.startup_items()
    return "OK", [{"nome": i["name"], "attivo": i["enabled"], "hive": i["hive"]} for i in items]


def t_timer():
    d = {}
    try:
        mn, mx, cur = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
        ctypes.windll.ntdll.NtQueryTimerResolution(ctypes.byref(mn), ctypes.byref(mx), ctypes.byref(cur))
        d["risoluzione_attuale_ms"] = cur.value / 10000.0
        d["minima_ms"], d["massima_ms"] = mn.value / 10000.0, mx.value / 10000.0
    except Exception as e:
        d["errore_lettura"] = str(e)
    code, out = T.run(["schtasks", "/Query", "/TN", XT.TIMER_TASK])
    d["attivita_presente"] = code == 0
    d["pythonw"] = os.path.isfile(os.path.join(os.path.dirname(sys.executable), "pythonw.exe"))
    d["GlobalTimerResolutionRequests"] = T.reg_read(
        "HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel", "GlobalTimerResolutionRequests")[0]
    return ("OK" if d["pythonw"] and "errore_lettura" not in d else "ATTENZIONE"), d


def t_restore():
    code, out = T.ps("$r = @(Get-ComputerRestorePoint -ErrorAction SilentlyContinue); "
                     "'punti=' + $r.Count; "
                     "$v = Get-CimInstance -Namespace root\\default -ClassName SystemRestoreConfig "
                     "-ErrorAction SilentlyContinue; 'config=' + [bool]$v; "
                     "(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore' "
                     "-ErrorAction SilentlyContinue | Select-Object RPSessionInterval,DisableSR | Out-String)")
    d = {"output": out, "codice": code}
    on = "punti=0" not in out
    return ("OK" if on else "ATTENZIONE"), dict(d, nota=None if on else
                                                "Nessun punto di ripristino: la Protezione sistema su C: potrebbe "
                                                "essere disattivata (LagDoctor prova ad attivarla, da verificare).")


def t_permissions():
    """Apre in scrittura (SENZA scrivere) le chiavi del registro usate dalle ottimizzazioni."""
    if winreg is None:
        return "ERRORE", "winreg non disponibile"
    keys = set()
    for t in T.CATALOG:
        try:
            if hasattr(t, "values") and callable(getattr(t, "values")):
                for h, p, *_ in (t.values() or []):
                    keys.add((h, p))
            if hasattr(t, "service"):
                keys.add(("HKLM", T.ServiceTweak.KEY + "\\" + t.service))
        except Exception:
            pass
    ok, missing, denied = [], [], []
    for h, p in sorted(keys):
        hive = winreg.HKEY_CURRENT_USER if h == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        try:
            k = winreg.OpenKey(hive, p, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
            k.Close()
            ok.append(h + "\\" + p)
        except FileNotFoundError:
            missing.append(h + "\\" + p)  # verra' creata quando si applica: normale
        except PermissionError:
            denied.append(h + "\\" + p)
        except OSError as e:
            denied.append("%s\\%s (%s)" % (h, p, e))
    return ("ATTENZIONE" if denied else "OK"), {"scrivibili": len(ok), "da_creare": missing, "negate": denied}


def t_scripts():
    """Analizza come testo (senza eseguirli) i comandi PowerShell di applica/annulla e controlla che esistano."""
    scripts = {}
    for t in T.CATALOG:
        for attr in ("on", "off", "check"):
            s = getattr(t, attr, None)
            if isinstance(s, str) and s.strip():
                scripts["%s.%s" % (t.id, attr)] = s
    payload = base64.b64encode(json.dumps(scripts).encode("utf-8")).decode("ascii")
    ps_code = (
        "$j = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" + payload + "')) | ConvertFrom-Json; "
        "$res = @{}; $cmds = @{}; "
        "foreach ($p in $j.PSObject.Properties) { $e = $null; "
        "$tok = [System.Management.Automation.PSParser]::Tokenize($p.Value, [ref]$e); "
        "if ($e.Count -gt 0) { $res[$p.Name] = ($e | ForEach-Object { $_.Message }) -join ' | ' }; "
        "foreach ($t in $tok) { if ($t.Type -eq 'Command') { $cmds[$t.Content] = 1 } } }; "
        "$miss = @(); foreach ($c in $cmds.Keys) { if (-not (Get-Command $c -ErrorAction SilentlyContinue)) "
        "{ $miss += $c } }; "
        "@{ errori = $res; comandi = @($cmds.Keys); mancanti = $miss } | ConvertTo-Json -Depth 4 -Compress")
    code, out = T.ps(ps_code, timeout=120)
    start = out.find("{")
    if start < 0:
        return "ERRORE", {"output": out[-2000:]}
    d = json.loads(out[start:])
    d["script_controllati"] = len(scripts)
    bad = d.get("errori") or {}
    return ("ERRORE" if bad else ("ATTENZIONE" if d.get("mancanti") else "OK")), d


def t_pdh():
    q = pdh.Query(capture.PDH_PATHS)
    missing = [k for k in capture.PDH_PATHS if k not in q.counters]
    q.collect()
    time.sleep(1.0)
    v = q.collect()
    vals = {k: (x if not isinstance(x, list) else x[:6]) for k, x in v.items()}
    return ("ERRORE" if not q.ok else ("ATTENZIONE" if missing else "OK")), {"mancanti": missing, "valori": vals}


def t_gpu_monitor():
    gi = STATE.get("gpu")
    m = gpumod.make_monitor(gi)
    m.start()
    time.sleep(4)
    latest = dict(m.latest)
    m.stop()
    want = ["gpu_util", "gpu_temp", "vram_used"]
    miss = [k for k in want if latest.get(k) is None]
    return ("ATTENZIONE" if miss else "OK"), {"tipo": type(m).__name__, "disponibile": getattr(m, "available", None),
                                              "valori": latest, "mancanti": miss}


def t_latency():
    p = capture.LatencyProbe()
    p.start()
    time.sleep(4)
    p.stop()
    pts = p.points[2:]  # i primi campioni servono a stabilizzarsi
    if not pts:
        return "ERRORE", "La sonda di latenza non ha prodotto dati"
    lat = sorted(x["lat_max"] for x in pts)
    d = {"campioni": len(pts), "ritardo_max_ms": lat[-1], "ritardo_mediano_ms": lat[len(lat) // 2]}
    # se il timer dei processi in background non viene sbloccato vedremmo ritardi fissi di ~14 ms
    return ("ATTENZIONE" if d["ritardo_mediano_ms"] > 10 else "OK"), d


def t_foreground():
    u32 = ctypes.windll.user32
    hwnd = u32.GetForegroundWindow()
    pid = ctypes.c_ulong(0)
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    name = None
    try:
        name = psutil.Process(pid.value).name()
    except Exception:
        pass
    return ("OK" if pid.value else "ATTENZIONE"), {"finestra_attiva": name, "pid": pid.value}


def _spinner(stop):
    i = 0
    while not stop.is_set():
        print("\r      registrazione di prova " + "|/-\\"[i % 4] + "  ", end="", flush=True)
        i += 1
        time.sleep(0.03)
    print("\r" + " " * 40 + "\r", end="", flush=True)


def t_presentmon():
    pm = capture.find_presentmon(_paths.TOOLS)
    if not pm:
        return "ERRORE", "PresentMon non trovato nella cartella strumenti"
    dwm = next((p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "dwm.exe"), None)
    if not dwm:
        return "ERRORE", "dwm.exe non trovato"
    csv_path = os.path.join(WORK, "presentmon_prova.csv")
    cmd = [pm, "--process_id", str(dwm.pid), "--output_file", csv_path, "--timed", "6", "--terminate_after_timed",
           "--terminate_on_proc_exit", "--no_console_stats", "--stop_existing_session",
           "--session_name", "LagDoctorAutoTest"]
    stop = threading.Event()
    th = threading.Thread(target=_spinner, args=(stop,), daemon=True)  # fa ridisegnare lo schermo: crea frame
    th.start()
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    stop.set()
    th.join()
    d = {"exe": pm, "codice": r.returncode, "secondi": round(time.time() - t0, 1),
         "messaggi": (r.stdout + r.stderr)[-1500:], "csv": os.path.exists(csv_path)}
    if not d["csv"]:
        return "ERRORE", d
    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        header = f.readline().strip()
        nlines = sum(1 for _ in f)
    d["colonne"] = header.split(",")
    d["righe"] = nlines
    frames = stutter.load_frames(csv_path)
    d["frame_letti"] = len(frames)
    if frames:
        f0 = frames[len(frames) // 2]
        d["esempio_frame"] = {k: f0.get(k) for k in sorted(f0)}
        d["campi_vuoti"] = sorted(k for k in f0 if all(fr.get(k) is None for fr in frames))
    cols = {h.strip().strip('"').lower() for h in d["colonne"]}
    d["colonne_mancanti"] = [k for k in ("ft", "cpu_busy", "gpu_busy", "present_mode", "displayed")
                             if not any(a in cols for a in stutter.ALIASES[k])]
    STATE["csv"] = csv_path
    if d["colonne_mancanti"]:
        return "ERRORE", d
    if not frames:
        return "ATTENZIONE", dict(d, nota="Nessun frame: normale se lo schermo era fermo")
    return "OK", d


def t_presentmon_stop():
    """Verifica il pulsante 'Ferma': avvia una registrazione lunga e la chiude dopo 3 secondi."""
    pm = capture.find_presentmon(_paths.TOOLS)
    dwm = next((p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "dwm.exe"), None)
    if not pm or not dwm:
        return "ERRORE", "PresentMon o dwm.exe non trovati"
    csv_path = os.path.join(WORK, "presentmon_stop.csv")
    p = subprocess.Popen([pm, "--process_id", str(dwm.pid), "--output_file", csv_path, "--timed", "60",
                          "--terminate_after_timed", "--no_console_stats", "--stop_existing_session",
                          "--session_name", "LagDoctorAutoTest"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    time.sleep(3)
    t0 = time.time()
    r = subprocess.run([pm, "--terminate_existing_session", "--session_name", "LagDoctorAutoTest"],
                       capture_output=True, text=True, timeout=15)
    try:
        p.wait(timeout=10)
        stopped = True
    except subprocess.TimeoutExpired:
        p.kill()
        stopped = False
    d = {"chiusa": stopped, "secondi_per_chiudere": round(time.time() - t0, 1), "codice": r.returncode,
         "messaggi": (r.stdout + r.stderr)[-800:], "csv": os.path.exists(csv_path)}
    return ("OK" if stopped and d["csv"] else "ERRORE"), d


def t_analysis():
    csv_path = STATE.get("csv")
    if not csv_path:
        return "ATTENZIONE", "nessun file di prova"
    res = analysis.analyze_session(csv_path, "dwm.exe", [], STATE.get("sysinfo") or {},
                                   refresh_hz=(STATE.get("sysinfo") or {}).get("refresh_hz"))
    keys = sorted(res.keys()) if isinstance(res, dict) else type(res).__name__
    return "OK", {"chiavi": keys, "troppo_corta": (res or {}).get("too_few"),
                  "frame": (res or {}).get("total_frames")}


def t_drive():
    return "OK", jsonable(checks.check_game_drive(sys.executable))


def t_edge():
    paths = [os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
             os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")]
    found = [p for p in paths if os.path.isfile(p)]
    return ("OK" if found else "ATTENZIONE"), {"edge": found}


def t_blocked():
    if BLOCKED:
        return "ERRORE", BLOCKED
    return "OK", "Nessuna funzione ha provato a modificare il PC."


# ====================================================================== main
def main():
    os.system("")  # abilita i colori/ritorno a capo nella console
    say("=" * 70)
    say(" LagDoctor - AUTODIAGNOSI (sola lettura: non cambia niente nel PC)")
    say("=" * 70)
    say(" Durata: 2-5 minuti. Non aprire giochi durante il controllo.")
    say("")
    if IMPORT_ERR:
        RESULTS.append({"test": "Caricamento di LagDoctor", "esito": "ERRORE", "dettagli": IMPORT_ERR})
        say(IMPORT_ERR)
    else:
        steps = [
            ("Ambiente (Windows, Python, permessi)", t_env),
            ("Controllo rapido del PC (avvio del programma)", t_checks),
            ("Schede video", t_gpu),
            ("Scansione completa (PowerShell)", t_scan_ps),
            ("Monitor e frequenze", t_displays),
            ("Impostazioni del driver video (lettura)", t_driver),
            ("Dati extra NVIDIA", t_nvidia_extra),
            ("Stato di tutte le ottimizzazioni", t_catalog),
            ("App preinstallate (debloat)", t_appx),
            ("Programmi all'avvio", t_startup),
            ("Timer Resolution", t_timer),
            ("Punti di ripristino", t_restore),
            ("Permessi di scrittura del registro (senza scrivere)", t_permissions),
            ("Comandi di applica/annulla (analisi senza eseguirli)", t_scripts),
            ("Contatori di Windows (DPC, memoria, VRAM)", t_pdh),
            ("Sensori della scheda video", t_gpu_monitor),
            ("Sonda di latenza", t_latency),
            ("Rilevamento finestra attiva", t_foreground),
            ("Registrazione di prova con PresentMon", t_presentmon),
            ("Pulsante Ferma di PresentMon", t_presentmon_stop),
            ("Analisi della registrazione di prova", t_analysis),
            ("Disco del gioco", t_drive),
            ("Finestra del programma (Edge)", t_edge),
            ("Protezione: tentativi di modifica bloccati", t_blocked),
        ]
        for name, fn in steps:
            test(name, fn)

    data = {"versione_autodiagnosi": 2, "data": datetime.datetime.now().isoformat(timespec="seconds"),
            "risultati": RESULTS, "comandi": TRACE, "bloccati": BLOCKED}
    jpath = os.path.join(WORK, "risultato.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(jsonable(data), f, ensure_ascii=False, indent=1)
    tpath = os.path.join(WORK, "riepilogo.txt")
    with open(tpath, "w", encoding="utf-8") as f:
        for r in RESULTS:
            f.write("[%s] %s\n" % (r["esito"], r["test"]))
    zpath = os.path.join(OUT_DIR, "autodiagnosi-%s.zip" % STAMP)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in os.listdir(WORK):
            z.write(os.path.join(WORK, fn), fn)

    say("")
    say("=" * 70)
    count = {}
    for r in RESULTS:
        count[r["esito"]] = count.get(r["esito"], 0) + 1
    say(" RISULTATO: " + ", ".join("%s %d" % (k, v) for k, v in sorted(count.items())))
    for r in RESULTS:
        if r["esito"] != "OK":
            say("   [%s] %s" % (r["esito"], r["test"]))
    say("")
    say(" Il PC non e' stato modificato.")
    say(" File da mandare:  " + zpath)
    say("=" * 70)
    try:
        subprocess.Popen(["explorer", "/select,", zpath])
    except Exception:
        pass


if __name__ == "__main__":
    main()
