"""Game mode di LagDoctor.

Un piccolo programma invisibile (parte con Windows, con i permessi di amministratore) controlla ogni 5 secondi se
e' partito uno dei giochi scelti. Quando un gioco parte:
  - priorita' CPU e GPU del gioco piu' alte (Alta o Superiore al normale, scelta per ogni gioco)
  - priorita' piu' bassa per i programmi in background dell'utente (non per chat vocale, overlay, launcher...)
  - chiude componenti di Windows inutili mentre giochi, come fa la modalita' Xbox (widget, Collegamento al
    telefono, aggiornamenti di Edge/Google, OneDrive), e facoltativamente anche Esplora risorse
  - ferma servizi non necessari (indicizzazione, SysMain, telemetria, Windows Update e download in background)
  - libera la RAM dei programmi in background, timer di sistema a 0,5 ms, rete: pacchetti del gioco in priorita'
Quando l'ultimo gioco si chiude, TUTTO torna esattamente com'era. Ogni modifica viene scritta prima in un
"diario" su disco: se il PC si spegne o il programma si chiude a meta', all'avvio successivo viene annullata.
"""
import ctypes
import json
import re
import os
import subprocess
import sys
import threading
import time
import traceback

import psutil

from . import cputopo
from . import games as G

from . import paths

ROOT = paths.DATA_DIR
CONFIG = os.path.join(ROOT, "gamemode.json")
STATUS = os.path.join(ROOT, "gamemode_stato.json")
JOURNAL = os.path.join(ROOT, "gamemode_attiva.json")
IFEO_FILE = os.path.join(ROOT, "gamemode_priorita_windows.json")  # priorita' impostate tramite Windows (anti-cheat)
IFEO = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
IFEO_CLASS = {"high": 3, "above": 6}  # valori di CpuPriorityClass
LOG = os.path.join(ROOT, "gamemode.log")
TASK = "LagDoctor GameMode"
LAUNCH_TASK = "LagDoctor Avvio utente"
CREATE_NO_WINDOW = 0x08000000
POLL = 5.0  # secondi tra un controllo e l'altro dei processi aperti
GRACE = 6.0  # secondi senza giochi prima di spegnere (alcuni giochi si riavviano da soli all'avvio)
AC_WAIT = 8.0  # secondi di attesa prima di toccare un gioco nuovo (per vedere se parte un anti-cheat)

PRIORITY = {"high": ("Alta", 0x00000080, 4), "above": ("Superiore al normale", 0x00008000, 3),
            "normal": ("Normale", 0x00000020, 2)}  # nome, classe CPU, classe GPU (D3DKMT)

# ------------------------------------------------------------------ opzioni (con spiegazioni per l'interfaccia)
OPTIONS = [
    ("priority", True, "Priorita' del gioco",
     "Il processo del gioco riceve la priorita' scelta (Alta o Superiore al normale) come in Gestione attivita' > "
     "Dettagli > Imposta priorita'. Windows gli da' la CPU prima che agli altri programmi. Per i giochi con "
     "anti-cheat (Easy Anti-Cheat, BattlEye, Vanguard...) LagDoctor non tocca il processo protetto: chiede a "
     "Windows di dargli la priorita' da solo all'avvio del gioco (metodo sicuro, valido dalla volta successiva).",
     "Nessuno con Alta. 'In tempo reale' non e' offerta: puo' bloccare mouse, tastiera e audio."),
    ("gpu_priority", True, "Priorita' della GPU per il gioco",
     "Anche la scheda video esegue prima il lavoro del gioco rispetto a browser, Discord, overlay (stessa API usata "
     "da Windows per la priorita' GPU dei processi).",
     "Gli overlay (Discord, Steam) possono aggiornarsi un po' piu' lentamente."),
    ("affinity", True, "Affinita' dei core automatica (decide LagDoctor in base al processore)",
     "LagDoctor guarda come e' fatto il processore (CCD, 3D V-Cache, core P/E) e fissa i core del gioco solo "
     "quando aiuta davvero: Ryzen con due CCD (il gioco sul CCD con la 3D V-Cache o sul primo CCD), Intel ibridi "
     "con almeno 8 core P (il gioco solo sui core P). Sugli altri processori non tocca nulla.",
     "Se un gioco usa piu' di 16 thread pesanti (rarissimo) potrebbe avere meno FPS: in quel caso spegnila."),
    ("bg_priority", True, "Priorita' bassa ai programmi in background",
     "Browser, app di sistema e programmi aperti passano a 'Inferiore al normale': usano la CPU solo quando il "
     "gioco non ne ha bisogno. Esclusi chat vocale (Discord, TeamSpeak), OBS, overlay, launcher, software di "
     "mouse/tastiera/audio e anti-cheat.",
     "Un video aperto nel browser sull'altro schermo potrebbe scattare se il gioco usa tutta la CPU."),
    ("close_apps", True, "Chiudi componenti di Windows inutili (come la modalita' Xbox)",
     "Chiude Widget, Collegamento al telefono, Copilot e gli aggiornamenti automatici di Edge/Google. La "
     "modalita' Xbox di Windows libera RAM proprio non caricando questi componenti.",
     "Nessuno: Windows li riapre da solo quando servono."),
    ("close_onedrive", True, "Metti in pausa OneDrive",
     "OneDrive viene chiuso durante il gioco (niente sincronizzazioni che usano disco e rete) e riaperto alla fine.",
     "I file non si sincronizzano mentre giochi."),
    ("stop_services", True, "Ferma i servizi non necessari",
     "Ferma temporaneamente indicizzazione della ricerca, SysMain (Superfetch), telemetria, segnalazione errori, "
     "mappe offline e Assistente compatibilita' programmi. Ripartono quando chiudi il gioco.",
     "La ricerca di Windows puo' essere piu' lenta durante il gioco."),
    ("stop_updates", True, "Blocca aggiornamenti e download in background",
     "Ferma Windows Update, BITS, Ottimizzazione recapito e gli aggiornamenti di Edge, Google, Firefox e Adobe: "
     "niente download che rubano banda e disco mentre giochi. Ripartono alla fine.",
     "Gli aggiornamenti vengono scaricati dopo la partita."),
    ("trim_ram", True, "Libera la RAM dei programmi in background",
     "All'avvio del gioco Windows sposta su disco la memoria non usata dei programmi in background (come fa la "
     "modalita' Xbox): piu' RAM libera per il gioco.",
     "Tornando a quei programmi possono esserci 1-2 secondi di lentezza. Con 32 GB il guadagno in FPS e' minimo."),
    ("timer", True, "Timer di sistema a 0,5 ms",
     "Mentre giochi il timer di Windows resta alla risoluzione massima: frame limiter e input piu' regolari.",
     "Consumo leggermente piu' alto, solo durante il gioco."),
    ("qos", True, "Priorita' di rete al gioco (QoS)",
     "I pacchetti del gioco vengono marcati con priorita' massima (DSCP 46, come le chiamate VoIP). Insieme al "
     "blocco dei download in background, la connessione resta tutta per il gioco.",
     "La marcatura aiuta solo se il router rispetta la QoS/DSCP; non fa mai danni."),
    ("power_plan", False, "Piano energetico Prestazioni elevate durante il gioco",
     "Attiva il piano 'Prestazioni elevate' solo mentre giochi e rimette il tuo piano alla fine.",
     "Se usi gia' un piano energetico personalizzato (di un programma di ottimizzazione o creato da te), lascialo disattivato."),
    ("close_shell", False, "Chiudi Esplora risorse (modalita' Xbox completa)",
     "Come la modalita' Xbox: chiude Esplora risorse, barra delle applicazioni, Start e ricerca mentre giochi "
     "(circa 150-400 MB di RAM e qualche processo in meno). Vengono riaperti quando chiudi il gioco.",
     "Niente barra delle applicazioni e notifiche durante il gioco. Alt+Tab e Ctrl+Shift+Esc funzionano."),
]
DEFAULT_OPTS = {k: v for k, v, *_ in OPTIONS}

APPS = ["widgets.exe", "widgetservice.exe", "phoneexperiencehost.exe", "yourphone.exe", "crossdeviceresume.exe",
        "copilot.exe", "cortana.exe", "microsoftedgeupdate.exe", "googleupdate.exe"]
SHELL = ["explorer.exe", "startmenuexperiencehost.exe", "searchhost.exe", "shellexperiencehost.exe",
         "widgets.exe"]
SERVICES = {
    "stop_services": ["WSearch", "SysMain", "DiagTrack", "WerSvc", "MapsBroker", "PcaSvc"],
    "stop_updates": ["wuauserv", "UsoSvc", "BITS", "DoSvc", "edgeupdate", "edgeupdatem", "gupdate", "gupdatem",
                     "MozillaMaintenance", "AdobeARMservice"],
}
# mai toccati (priorita' e chiusura)
PROTECT = {
    "explorer.exe", "dwm.exe", "csrss.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe", "smss.exe",
    "audiodg.exe", "ctfmon.exe", "textinputhost.exe", "sihost.exe", "taskhostw.exe", "runtimebroker.exe",
    "applicationframehost.exe", "startmenuexperiencehost.exe", "searchhost.exe", "shellexperiencehost.exe",
    "lockapp.exe", "conhost.exe", "fontdrvhost.exe", "taskmgr.exe", "system", "registry", "memory compression",
    "python.exe", "pythonw.exe", "py.exe", "presentmon-2.4.1-x64.exe", "msmpeng.exe", "securityhealthsystray.exe",
    "steam.exe", "steamwebhelper.exe", "steamservice.exe", "epicgameslauncher.exe", "eadesktop.exe",
    "eabackgroundservice.exe", "battle.net.exe", "agent.exe", "galaxyclient.exe", "upc.exe", "uplaywebcore.exe",
    "riotclientservices.exe", "riotclientux.exe", "xboxpcapp.exe", "gamingservices.exe", "gameinputsvc.exe",
    "discord.exe", "teamspeak.exe", "ts3client_win64.exe", "mumble.exe", "obs64.exe", "obs32.exe",
    "streamlabs obs.exe", "nvcontainer.exe", "nvidia overlay.exe", "nvidia app.exe", "nvsphelper64.exe",
    "nvidia share.exe", "radeonsoftware.exe", "amdrsserv.exe", "amdow.exe", "rtss.exe", "msiafterburner.exe",
    "rtsshooksloader64.exe", "icue.exe", "lghub.exe", "lghub_agent.exe", "lghub_system_tray.exe",
    "steelseriesgg.exe", "steelseriesengine.exe", "wootility.exe", "vgtray.exe", "vgc.exe", "faceit.exe",
    "faceitclient.exe", "medal.exe", "overwolf.exe", "parsecd.exe", "moonlight.exe", "sunshine.exe",
}
PROTECT_PREFIX = ("discord", "voicemeeter", "razer", "lghub", "steelseries", "obs", "nvidia", "nv", "amd", "radeon",
                  "easyanticheat", "beservice", "battleye", "faceit", "vanguard", "spotify", "corsair", "asus",
                  "armoury", "msi", "elgato", "wave link", "nahimic", "realtek", "sonic")


# ------------------------------------------------------------------ file
def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def log(msg):
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 500000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def load_config():
    c = _load(CONFIG, {})
    c.setdefault("enabled", False)
    c.setdefault("games", [])
    c.setdefault("removed", [])
    opts = dict(DEFAULT_OPTS)
    opts.update(c.get("opts") or {})
    c["opts"] = opts
    return c


def save_config(c):
    _save(CONFIG, c)


def refresh_games(c):
    """Aggiunge alla configurazione i giochi appena installati (quelli gia' presenti mantengono le scelte)."""
    have = {g["id"] for g in c["games"]}
    added = 0
    for g in G.detect():
        if g["id"] in have or g["id"] in c["removed"]:
            continue
        g = dict(g, on=not g.get("optional"), priority="high")
        g.pop("optional", None)
        c["games"].append(g)
        added += 1
    for g in c["games"]:  # anti-cheat (anche per i giochi gia' in elenco)
        if g.get("match") == "dir" and "anticheat" not in g:
            try:
                g["anticheat"] = G.anticheat_in_dir(g.get("dir"))
            except Exception:
                g["anticheat"] = None
    # giochi disinstallati (cartella sparita): li tolgo, tranne quelli aggiunti a mano
    before = len(c["games"])
    c["games"] = [g for g in c["games"] if g.get("match") != "dir" or os.path.isdir(g.get("dir") or "")
                  or g.get("source") == "manuale"]
    c["games"].sort(key=lambda g: g["name"].lower())
    return max(0, added - (before - len(c["games"])))


# ------------------------------------------------------------------ priorita' tramite Windows (giochi con anti-cheat)
def _ifeo_get(exe):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, IFEO + "\\" + exe + "\\PerfOptions", 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, "CpuPriorityClass")[0]
    except Exception:
        return None


def ifeo_set(exe, prio):
    """Windows dara' da solo questa priorita' al gioco ogni volta che parte (nessun accesso al processo)."""
    import winreg
    exe = exe.lower()
    data = _load(IFEO_FILE, {})
    val = IFEO_CLASS.get(prio)
    if val is None:
        return ifeo_remove(exe)
    if exe not in data:
        data[exe] = {"prev": _ifeo_get(exe)}
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, IFEO + "\\" + exe + "\\PerfOptions", 0,
                            winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY) as k:
        winreg.SetValueEx(k, "CpuPriorityClass", 0, winreg.REG_DWORD, val)
    data[exe]["value"] = val
    _save(IFEO_FILE, data)
    return True


def ifeo_remove(exe):
    import winreg
    exe = exe.lower()
    data = _load(IFEO_FILE, {})
    if exe not in data:
        return False
    prev = data[exe].get("prev")
    path = IFEO + "\\" + exe + "\\PerfOptions"
    try:
        if prev is not None:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0,
                                    winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY) as k:
                winreg.SetValueEx(k, "CpuPriorityClass", 0, winreg.REG_DWORD, prev)
        else:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0,
                                winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY) as k:
                winreg.DeleteValue(k, "CpuPriorityClass")
                left = winreg.QueryInfoKey(k)[1]
            if not left:  # chiavi vuote create da LagDoctor
                for sub in (path, IFEO + "\\" + exe):
                    try:
                        winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE, sub, winreg.KEY_WOW64_64KEY, 0)
                    except OSError:
                        break
    except OSError:
        pass
    del data[exe]
    _save(IFEO_FILE, data)
    return True


def ifeo_sync(cfg):
    """Allinea le priorita' 'tramite Windows' alle scelte attuali (gioco spento/tolto/priorita' cambiata)."""
    data = _load(IFEO_FILE, {})
    if not data:
        return
    want = {}
    if cfg.get("enabled") and cfg["opts"].get("priority"):
        for g in cfg["games"]:
            for exe in g.get("ac_exes") or []:
                if g.get("on"):
                    want[exe.lower()] = g.get("priority") or "high"
    for exe in list(data):
        try:
            if exe not in want or IFEO_CLASS.get(want[exe]) is None:
                ifeo_remove(exe)
            elif data[exe].get("value") != IFEO_CLASS[want[exe]]:
                ifeo_set(exe, want[exe])
        except Exception as e:
            log("priorita' Windows non aggiornata per %s: %s" % (exe, e))


def ifeo_clear():
    for exe in list(_load(IFEO_FILE, {})):
        try:
            ifeo_remove(exe)
        except Exception:
            pass


# ------------------------------------------------------------------ helper di sistema
def _run(args, timeout=60):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def _ps(cmd, timeout=120):
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], timeout)


def launch_as_user(exe, args=""):
    """Avvia un programma con i permessi NORMALI dell'utente (non da amministratore), es. Esplora risorse."""
    tr = '"%s" %s' % (exe, args) if args else '"%s"' % exe
    code, out = _run(["schtasks", "/Create", "/TN", LAUNCH_TASK, "/TR", tr, "/SC", "ONCE", "/ST", "23:59",
                      "/RL", "LIMITED", "/F"])
    if code == 0:
        _run(["schtasks", "/Run", "/TN", LAUNCH_TASK])
        time.sleep(1.5)
        _run(["schtasks", "/Delete", "/TN", LAUNCH_TASK, "/F"])
        return True
    try:  # ripiego
        subprocess.Popen([exe] + ([args] if args else []), creationflags=0x00000008)
        return True
    except Exception:
        return False


def _open(pid, access):
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = ctypes.c_void_p
    k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    return k32, k32.OpenProcess(access, False, pid)


def _enable_privilege(name="SeIncreaseBasePriorityPrivilege"):
    """Attiva un privilegio dell'amministratore (di solito presente ma spento): serve ad alzare le priorita'."""
    try:
        from ctypes import wintypes
        adv, k32 = ctypes.windll.advapi32, ctypes.windll.kernel32

        class LUID(ctypes.Structure):
            _fields_ = [("Low", wintypes.DWORD), ("High", wintypes.LONG)]

        class TP(ctypes.Structure):
            _fields_ = [("Count", wintypes.DWORD), ("Luid", LUID), ("Attr", wintypes.DWORD)]
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        tok = wintypes.HANDLE()
        if not adv.OpenProcessToken(k32.GetCurrentProcess(), 0x0020 | 0x0008, ctypes.byref(tok)):
            return False
        luid = LUID()
        if not adv.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            return False
        tp = TP(1, luid, 0x2)  # SE_PRIVILEGE_ENABLED
        adv.AdjustTokenPrivileges(tok, False, ctypes.byref(tp), 0, None, None)
        ok = k32.GetLastError() == 0
        k32.CloseHandle(tok)
        return ok
    except Exception:
        return False


def _set_gpu_priority(pid, cls):
    try:
        k32, h = _open(pid, 0x0200 | 0x1000)  # SET_INFORMATION | QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            f = ctypes.windll.gdi32.D3DKMTSetProcessSchedulingPriorityClass
            f.argtypes = [ctypes.c_void_p, ctypes.c_int]
            return f(h, cls) == 0
        finally:
            k32.CloseHandle(h)
    except Exception:
        return False


def _trim(pid):
    try:
        k32, h = _open(pid, 0x0100 | 0x0400)  # SET_QUOTA | QUERY_INFORMATION
        if not h:
            return False
        try:
            f = ctypes.windll.psapi.EmptyWorkingSet
            f.argtypes = [ctypes.c_void_p]
            return bool(f(h))
        finally:
            k32.CloseHandle(h)
    except Exception:
        return False


def _timer(on):
    try:
        cur = ctypes.c_ulong()
        ctypes.windll.ntdll.NtSetTimerResolution(5000, bool(on), ctypes.byref(cur))
        return True
    except Exception:
        return False


def _active_scheme():
    import re
    code, out = _run(["powercfg", "/getactivescheme"])
    m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", out)
    return m.group(0).lower() if m else None


KIND_TEXT = {"ryzen_x3d_2ccd": "CCD con 3D V-Cache", "ryzen_2ccd": "primo CCD del Ryzen",
             "intel_ibrido": "solo core P"}


def _cpus_text(cpus):
    """[0,1,2,3,8,9] -> '0-3, 8-9'"""
    out, start, prev = [], None, None
    for c in sorted(cpus) + [None]:
        if start is None:
            start = prev = c
        elif c is not None and c == prev + 1:
            prev = c
        else:
            out.append(str(start) if start == prev else "%d-%d" % (start, prev))
            start = prev = c
    return ", ".join(out)


def _protected(name):
    n = (name or "").lower()
    return n in PROTECT or n.startswith(PROTECT_PREFIX)


# ------------------------------------------------------------------ motore
class Engine:
    def __init__(self):
        self.j = _load(JOURNAL, None)  # diario delle modifiche in corso
        self.game_pids = {}  # pid -> {"game", "create", "prev_prio", "name"}
        self.actions = []
        self.errors = []
        self.my_user = None
        self.bg_seen = {}  # pid -> create_time gia' valutati (per non rileggere tutto a ogni controllo)
        self.new_ac_exes = []  # (id gioco, exe, anti-cheat) da salvare nella configurazione
        try:
            self.cpu = cputopo.decide()
        except Exception:
            self.cpu = {"apply": False}
        try:
            self.my_user = psutil.Process().username()
        except Exception:
            pass

    # -------- diario
    def _jsave(self):
        _save(JOURNAL, self.j)

    @property
    def active(self):
        return self.j is not None

    def act(self, msg):
        self.actions.append(msg)
        log(msg)

    def err(self, msg):
        self.errors.append(msg)
        log("ERRORE " + msg)

    # -------- attivazione globale (una volta, al primo gioco)
    def activate(self, opts, names):
        _enable_privilege()
        self.actions, self.errors = [], []
        self.j = {"since": time.time(), "games": names, "services": [], "explorer": False, "restart": [],
                  "power_prev": None, "qos": [], "bg": {}, "timer": False}
        self._jsave()
        self.act("Game mode ATTIVA per: " + ", ".join(names))
        if opts.get("power_plan"):
            prev = _active_scheme()
            if prev and _run(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"])[0] == 0:
                self.j["power_prev"] = prev
                self._jsave()
                self.act("Piano energetico: Prestazioni elevate")
        if opts.get("timer") and _timer(True):
            self.j["timer"] = True
            self._jsave()
            self.act("Timer di sistema a 0,5 ms")
        svcs = []
        for k in ("stop_services", "stop_updates"):
            if opts.get(k):
                svcs += SERVICES[k]
        if svcs:
            self._stop_services(svcs)
        self._close_processes(opts)
        if opts.get("trim_ram"):
            self._trim_background()

    def _stop_services(self, names):
        lst = ",".join("'%s'" % n for n in names)
        code, out = _ps("foreach ($n in @(%s)) { $s = Get-Service -Name $n -ErrorAction SilentlyContinue; "
                        "if ($s -and $s.Status -eq 'Running') { try { Stop-Service -Name $n -Force -ErrorAction Stop; "
                        "'STOP:' + $n } catch { 'ERR:' + $n } } }; 'FINE'" % lst, timeout=120)
        stopped = [l[5:].strip() for l in out.splitlines() if l.startswith("STOP:")]
        self.j["services"] = stopped
        self._jsave()
        if stopped:
            self.act("Servizi fermati: " + ", ".join(stopped))
        bad = [l[4:].strip() for l in out.splitlines() if l.startswith("ERR:")]
        if bad:
            log("servizi non fermati (protetti da Windows): " + ", ".join(bad))

    def _close_processes(self, opts):
        targets = set()
        if opts.get("close_apps"):
            targets.update(APPS)
        if opts.get("close_onedrive"):
            targets.add("onedrive.exe")
        if opts.get("close_shell"):
            targets.update(SHELL)
        if not targets:
            return
        closed, restart = [], []
        for p in psutil.process_iter(["pid", "name", "exe"]):
            n = (p.info["name"] or "").lower()
            if n not in targets:
                continue
            try:
                if n == "onedrive.exe" and p.info["exe"] and p.info["exe"] not in restart:
                    restart.append(p.info["exe"])
                if n == "explorer.exe":
                    self.j["explorer"] = True
                    self._jsave()  # prima di chiudere: se qualcosa va storto all'avvio dopo lo riapro
                p.kill()
                closed.append(p.info["name"])
            except psutil.Error:
                pass
        self.j["restart"] = restart
        self.j["closed"] = sorted({c.lower() for c in closed})
        self._jsave()
        if closed:
            self.act("Chiusi: " + ", ".join(sorted(set(closed))))

    def _user_bg(self, only_new=False):
        """Processi dell'utente in background (non protetti, non giochi)."""
        for p in psutil.process_iter(["pid", "name"]):
            if p.pid in self.game_pids or p.pid == os.getpid() or _protected(p.info["name"]):
                continue
            if only_new:
                try:
                    ct = p.create_time()
                except psutil.Error:
                    continue
                if self.bg_seen.get(p.pid) == ct:
                    continue
                self.bg_seen[p.pid] = ct
            try:
                if self.my_user and p.username() != self.my_user:
                    continue
            except psutil.Error:
                continue
            yield p

    def _trim_background(self):
        n = 0
        before = psutil.virtual_memory().available
        for p in self._user_bg():
            if _trim(p.pid):
                n += 1
        freed = (psutil.virtual_memory().available - before) / 2**20
        self.act("RAM liberata dai programmi in background: %d processi, circa %.0f MB" % (n, max(freed, 0)))

    # -------- per ogni processo del gioco
    def add_game_process(self, proc, game, opts, running_names=()):
        try:
            info = {"game": game["name"], "create": proc.create_time(), "name": proc.name(), "prev_prio": None,
                    "prev_aff": None, "prio_key": game.get("priority") or "high", "game_id": game.get("id")}
        except psutil.Error:
            return
        self.game_pids[proc.pid] = info
        ac = game.get("anticheat") or self._ac_now(game, running_names)
        if ac:
            info["anticheat"] = ac
            self._anticheat_game(proc, game, opts, info, ac)
        else:
            self._direct(proc, game, opts, info)
        if opts.get("qos"):
            self._qos_add(info["name"])

    @staticmethod
    def _ac_now(game, running_names):
        """Anti-cheat partito insieme al gioco (quelli che girano solo durante la partita)."""
        names = {n.lower() for n in running_names or ()}
        for nm, procs in (("Easy Anti-Cheat", ("easyanticheat.exe", "easyanticheat_eos.exe")),
                          ("BattlEye", ("beservice.exe", "beservice_x64.exe")),
                          ("EA Javelin", ("eaanticheat.gameservice.exe",)),
                          ("ACE (Tencent)", ("sguard64.exe",))):
            if names & set(procs):
                return nm
        if "counter-strike" in game["name"].lower() and names & {"faceit.exe", "faceitservice.exe"}:
            return "FACEIT"
        return None

    def _anticheat_game(self, proc, game, opts, info, ac):
        """Gioco protetto: nessun accesso al processo. La priorita' la da' Windows stesso all'avvio (IFEO)."""
        self.act("%s: anti-cheat %s rilevato: non tocco il processo del gioco" % (game["name"], ac))
        exe = info["name"].lower()
        if game.get("ac_exes") is None or exe not in game["ac_exes"]:
            self.new_ac_exes.append((game["id"], exe, ac))
        prio = game.get("priority") or "high"
        if opts.get("priority") and prio in IFEO_CLASS:
            label = PRIORITY[prio][0]
            already = _ifeo_get(exe) == IFEO_CLASS[prio]
            try:
                ifeo_set(exe, prio)
                if already:
                    self.act("%s: priorita' %s data da Windows all'avvio (metodo sicuro per l'anti-cheat)"
                             % (info["name"], label))
                else:
                    self.act("%s: priorita' %s impostata tramite Windows: vale dalla PROSSIMA apertura del gioco "
                             "(cosi' l'anti-cheat non viene toccato)" % (info["name"], label))
            except Exception as e:
                self.err("%s: priorita' tramite Windows non impostata (%s)" % (info["name"], e))
        if opts.get("affinity") and self.cpu.get("apply"):
            self.act("%s: affinita' dei core non applicata (con l'anti-cheat %s non e' sicuro)" % (info["name"], ac))

    def _direct(self, proc, game, opts, info):
        if opts.get("affinity") and self.cpu.get("apply"):
            try:
                info["prev_aff"] = proc.cpu_affinity()
                proc.cpu_affinity(self.cpu["cpus"])
                self.act("%s: affinita' sui core %s (%s)" % (info["name"], _cpus_text(self.cpu["cpus"]),
                                                             KIND_TEXT.get(self.cpu["kind"], "")))
            except psutil.AccessDenied:
                self.err("%s: Windows non permette di cambiare l'affinita'" % info["name"])
            except (psutil.Error, ValueError, OSError):
                pass
        if opts.get("priority"):
            label, cls, gcls = PRIORITY.get(game.get("priority") or "high", PRIORITY["high"])
            if cls != PRIORITY["normal"][1]:
                try:
                    info["prev_prio"] = proc.nice()
                    proc.nice(cls)
                    self.act("%s (%s): priorita' %s" % (game["name"], info["name"], label))
                except psutil.AccessDenied:
                    self.err("%s: Windows (o l'anti-cheat) non permette di cambiare la priorita'" % info["name"])
                except psutil.Error:
                    pass
                if opts.get("gpu_priority"):
                    info["gpu_set"] = _set_gpu_priority(proc.pid, gcls)
                    if info["gpu_set"]:
                        self.act("%s: priorita' GPU %s" % (info["name"], label))
                    else:
                        self.err("%s: Windows non ha accettato la priorita' GPU" % info["name"])
        if opts.get("qos"):
            self._qos_add(info["name"])

    def _qos_add(self, exe_name):
        pol = "LagDoctor-" + exe_name
        if pol in self.j["qos"]:
            return
        _run(["reg", "add", r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\QoS", "/v", "Do not use NLA",
              "/t", "REG_SZ", "/d", "1", "/f"])
        code, out = _ps("Remove-NetQosPolicy -Name '%s' -Confirm:$false -ErrorAction SilentlyContinue; "
                        "New-NetQosPolicy -Name '%s' -AppPathNameMatchCondition '%s' -DSCPAction 46 "
                        "-NetworkProfile All -IPProtocolMatchCondition Both -ErrorAction Stop | Out-Null; 'OK'"
                        % (pol, pol, exe_name), timeout=60)
        if out.strip().endswith("OK"):
            self.j["qos"].append(pol)
            self._jsave()
            self.act("Rete: priorita' QoS per %s" % exe_name)
        else:
            log("QoS non applicata: " + out[-200:])

    def keep_services_stopped(self, every=15):
        """Windows Update (wuauserv, UsoSvc...) riparte da solo dopo poco: finche' la game mode e' attiva lo fermo
        di nuovo (controllo ogni 15 secondi, comando solo se e' davvero ripartito)."""
        now = time.time()
        if now - getattr(self, "_svc_check", 0) < every or not self.j or not self.j.get("services"):
            return
        self._svc_check = now
        for name in self.j["services"]:
            try:
                if psutil.win_service_get(name).status() == "running":
                    _run(["sc", "stop", name], timeout=20)
                    self.j.setdefault("restops", {})[name] = self.j.get("restops", {}).get(name, 0) + 1
                    self._jsave()
                    log("servizio %s ripartito da solo: fermato di nuovo" % name)
            except Exception:
                continue

    def lower_background(self):
        """Chiamata a ogni giro: abbassa anche i programmi aperti dopo l'avvio del gioco."""
        changed = 0
        for p in self._user_bg(only_new=True):
            key = str(p.pid)
            if key in self.j["bg"]:
                continue
            try:
                prev = p.nice()
                if prev != 0x20:  # solo quelli a priorita' Normale
                    continue
                p.nice(0x4000)    # BELOW_NORMAL
                self.j["bg"][key] = [p.create_time(), prev, p.info.get("name") or p.name()]
                changed += 1
            except psutil.Error:
                continue
        if changed:
            self._jsave()
        return changed

    # -------- disattivazione
    def deactivate(self, reason="nessun gioco aperto"):
        if self.j is None:
            return
        j = self.j
        log("Disattivo la game mode (%s)" % reason)
        # priorita' e affinita' dei giochi ancora aperti (se la game mode viene spenta durante il gioco)
        for pid, info in list(self.game_pids.items()):
            try:
                p = psutil.Process(pid)
                if abs(p.create_time() - info["create"]) >= 1:
                    continue
                if info.get("prev_prio") is not None:
                    p.nice(info["prev_prio"])
                    _set_gpu_priority(pid, 2)
                if info.get("prev_aff"):
                    p.cpu_affinity(info["prev_aff"])
            except (psutil.Error, ValueError, OSError):
                pass
        self.game_pids.clear()
        self.bg_seen.clear()
        for key, rec in list(j.get("bg", {}).items()):
            ct, prev = rec[0], rec[1]
            try:
                p = psutil.Process(int(key))
                if abs(p.create_time() - ct) < 1:
                    p.nice(prev)
            except (psutil.Error, ValueError):
                pass
        for pol in j.get("qos", []):
            _ps("Remove-NetQosPolicy -Name '%s' -Confirm:$false -ErrorAction SilentlyContinue" % pol, timeout=60)
        if j.get("services"):
            lst = ",".join("'%s'" % n for n in j["services"])
            _ps("foreach ($n in @(%s)) { Start-Service -Name $n -ErrorAction SilentlyContinue }" % lst, timeout=180)
        if j.get("explorer") and not any((p.info["name"] or "").lower() == "explorer.exe"
                                         for p in psutil.process_iter(["name"])):
            launch_as_user(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "explorer.exe"))
        for exe in j.get("restart", []):
            if os.path.isfile(exe):
                launch_as_user(exe, "/background")
        if j.get("power_prev"):
            _run(["powercfg", "/setactive", j["power_prev"]])
        if j.get("timer"):
            _timer(False)
        self.j = None
        try:
            os.remove(JOURNAL)
        except OSError:
            pass
        log("Tutto ripristinato")


# ------------------------------------------------------------------ ciclo principale (programma invisibile)
class Watcher:
    def __init__(self):
        self.engine = Engine()
        self.cfg, self.cfg_mtime = load_config(), None
        self.cache = {}  # pid -> (create_time, game or None)
        self.last_seen = 0
        self.stop = threading.Event()
        self.last_status = 0

    def _reload(self):
        try:
            m = os.path.getmtime(CONFIG)
        except OSError:
            m = None
        if m != self.cfg_mtime:
            self.cfg, self.cfg_mtime = load_config(), m
            try:
                ifeo_sync(self.cfg)
            except Exception as e:
                log("sync priorita' Windows: %s" % e)

    def _match(self, p, games):
        try:
            ct = p.create_time()
        except psutil.Error:
            return None
        c = self.cache.get(p.pid)
        if c and c[0] == ct:
            return c[1]
        found = None
        try:
            name, exe = p.name(), None
            try:
                exe = p.exe()
            except psutil.Error:
                pass
            for g in games:
                if G.matches(g, name, exe, lambda: " ".join(p.cmdline())):
                    found = g
                    break
        except psutil.Error:
            pass
        self.cache[p.pid] = (ct, found)
        return found

    def _remember_ac(self, items):
        """Salva nella configurazione quali eseguibili hanno l'anti-cheat (servono per la priorita' tramite Windows)."""
        c = load_config()
        for gid, exe, ac in items:
            for g in c["games"]:
                if g["id"] == gid:
                    g["anticheat"] = g.get("anticheat") or ac
                    g["ac_exes"] = sorted(set((g.get("ac_exes") or []) + [exe]))
        save_config(c)
        self.cfg, self.cfg_mtime = c, os.path.getmtime(CONFIG)

    def write_status(self, running_games, force=False):
        now = time.time()
        if not force and now - self.last_status < 10:
            return
        self.last_status = now
        e = self.engine
        procs = {str(pid): {k: i.get(k) for k in ("name", "game", "create", "prio_key", "anticheat", "gpu_set")}
                 for pid, i in e.game_pids.items()}
        _save(STATUS, {"pid": os.getpid(), "updated": now, "active": e.active, "cpu": e.cpu, "procs": procs,
                       "games": sorted({i["game"] for i in e.game_pids.values()}) or running_games,
                       "since": (e.j or {}).get("since"), "actions": e.actions[-40:], "errors": e.errors[-20:]})

    def tick(self):
        self._reload()
        cfg = self.cfg
        games = [g for g in cfg["games"] if g.get("on")]
        opts = cfg["opts"]
        alive = set()
        running = {}
        names = []
        for p in psutil.process_iter():
            alive.add(p.pid)
            try:
                names.append(p.name())
            except psutil.Error:
                pass
            g = self._match(p, games) if games else None
            if g:
                running[p.pid] = (p, g)
        for pid in list(self.cache):
            if pid not in alive:
                del self.cache[pid]
        e = self.engine
        if running:
            self.last_seen = time.time()
            if not e.active:
                e.activate(opts, sorted({g["name"] for _, g in running.values()}))
                self.write_status([], force=True)
            for pid, (p, g) in running.items():
                if pid not in e.game_pids:
                    try:  # l'anti-cheat puo' partire qualche secondo dopo il gioco: aspetto prima di toccarlo
                        if not g.get("anticheat") and time.time() - p.create_time() < AC_WAIT:
                            continue
                    except psutil.Error:
                        continue
                    e.add_game_process(p, g, opts, names)
                    self.write_status([], force=True)
            if e.new_ac_exes:
                self._remember_ac(e.new_ac_exes)
                e.new_ac_exes = []
            for pid in [x for x in e.game_pids if x not in running]:
                del e.game_pids[pid]
            if opts.get("bg_priority"):
                e.lower_background()
            e.keep_services_stopped()
        elif e.active and time.time() - self.last_seen > GRACE:
            e.deactivate()
            self.write_status([], force=True)
        self.write_status([])

    def run(self):
        log("Game mode avviata (pid %d)" % os.getpid())
        if self.engine.active:  # modifiche rimaste da una sessione interrotta (PC spento, crash)
            self.engine.deactivate("ripristino dopo un'interruzione")
        try:
            os.remove(STOP_FLAG)
        except OSError:
            pass
        while not self.stop.is_set():
            self._reload()
            if not self.cfg.get("enabled") or os.path.exists(STOP_FLAG):
                break
            try:
                self.tick()
            except Exception:
                log("ERRORE nel ciclo: " + traceback.format_exc()[-1500:])
            self.stop.wait(POLL)
        self.engine.deactivate("game mode spenta")
        _save(STATUS, {"pid": None, "updated": time.time(), "active": False, "games": [], "actions": [],
                       "errors": []})
        log("Game mode chiusa")


def _single_instance():
    try:
        h = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\LagDoctorGameMode")
        return h and ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def main():
    if not _single_instance():
        return
    w = Watcher()
    try:
        import signal
        signal.signal(signal.SIGTERM, lambda *a: w.stop.set())
    except Exception:
        pass
    try:
        w.run()
    except Exception:
        log("ERRORE fatale: " + traceback.format_exc()[-2000:])
        w.engine.deactivate("errore")


# ------------------------------------------------------------------ gestione dall'interfaccia


def daemon_pid():
    st = _load(STATUS, {})
    pid = st.get("pid")
    if pid and psutil.pid_exists(pid):
        try:
            if "gamemode" in " ".join(psutil.Process(pid).cmdline()).lower():
                return pid
        except psutil.Error:
            pass
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        if (p.info["name"] or "").lower() in ("python.exe", "pythonw.exe", "lagdoctor.exe") and \
                re.search(r"gamemode\.pyw|--gamemode", " ".join(p.info["cmdline"] or []).lower()):
            return p.info["pid"]
    return None


def _pythonw():
    pw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return pw if os.path.isfile(pw) else sys.executable


def enable():
    """Crea l'attivita' che parte con Windows (con i permessi di amministratore) e avvia subito la game mode."""
    c = load_config()
    c["enabled"] = True
    save_config(c)
    cmd = paths.gui_cmd("--gamemode")
    code, out = _run(["schtasks", "/Create", "/TN", TASK, "/TR", paths.quote(cmd),
                      "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"])
    if code != 0:
        raise RuntimeError("non riesco a creare l'avvio automatico: " + out[-200:])
    if not daemon_pid():
        subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW | 0x00000008, cwd=paths.APP_DIR)
    return True


def disable():
    c = load_config()
    c["enabled"] = False
    save_config(c)  # il programma invisibile se ne accorge, ripristina tutto e si chiude
    _run(["schtasks", "/Delete", "/TN", TASK, "/F"])
    try:
        ifeo_clear()
    except Exception:
        pass
    for _ in range(20):
        if not daemon_pid():
            break
        time.sleep(0.5)
    pid = daemon_pid()
    if pid:
        try:
            psutil.Process(pid).kill()
        except psutil.Error:
            pass
    recover()
    return True


STOP_FLAG = os.path.join(ROOT, "gamemode_ferma.flag")


def stop_for_update(timeout=15):
    """Ferma il programma invisibile (ripristinando tutto) senza spegnere la game mode: serve per aggiornare."""
    if not daemon_pid():
        return
    with open(STOP_FLAG, "w") as f:
        f.write("aggiornamento")
    for _ in range(int(timeout * 2)):
        if not daemon_pid():
            break
        time.sleep(0.5)
    pid = daemon_pid()
    if pid:
        try:
            psutil.Process(pid).kill()
        except psutil.Error:
            pass
    recover()


def ensure_running():
    """All'avvio di LagDoctor: se la game mode e' accesa, ricrea l'avvio automatico (il percorso del programma
    puo' essere cambiato, es. dopo l'installazione) e la riavvia se non gira (es. dopo un aggiornamento)."""
    c = load_config()
    if not c.get("enabled"):
        return False
    cmd = paths.gui_cmd("--gamemode")
    _run(["schtasks", "/Create", "/TN", TASK, "/TR", paths.quote(cmd), "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"])
    if not daemon_pid():
        subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW | 0x00000008, cwd=paths.APP_DIR)
    return True


def recover():
    """Se il programma invisibile non gira ma ci sono modifiche rimaste (crash, PC spento), le annulla."""
    if os.path.exists(JOURNAL) and not daemon_pid():
        Engine().deactivate("ripristino da LagDoctor")
        return True
    return False


# ------------------------------------------------------------------ verifica dal vivo
def _gpu_priority_of(pid):
    try:
        k32, h = _open(pid, 0x0400 | 0x1000)  # QUERY_INFORMATION (serve per leggerla) | QUERY_LIMITED
        if not h:
            return None
        try:
            f = ctypes.windll.gdi32.D3DKMTGetProcessSchedulingPriorityClass
            f.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            v = ctypes.c_int(-1)
            return v.value if f(h, ctypes.byref(v)) == 0 else None
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def _timer_now_ms():
    try:
        mn, mx, cur = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
        ctypes.windll.ntdll.NtQueryTimerResolution(ctypes.byref(mn), ctypes.byref(mx), ctypes.byref(cur))
        return cur.value / 10000.0
    except Exception:
        return None


def _service_state(name):
    try:
        return psutil.win_service_get(name).status()
    except Exception:
        return None


CPU_SHORT = {"uniforme": "non serve: tutti i core sono uguali",
             "sconosciuto": "struttura del processore non leggibile",
             "ryzen_2ccd_piccolo": "non serve: il gioco ha bisogno di tutti i core",
             "intel_ibrido_pochi_p": "non serve: pochi core P", "ryzen_ibrido": "non serve su questo Ryzen",
             "molti core": "Windows li gestisce gia'"}


def verify():
    """Controlla lo stato REALE di Windows mentre la game mode e' attiva: per ogni ottimizzazione ok / no / da
    sapere, con il dettaglio. Non si fida di quello che la game mode dice di aver fatto: va a guardare."""
    st = _load(STATUS, {})
    j = _load(JOURNAL, None)
    cfg = load_config()
    opts = cfg["opts"]
    running = bool(st.get("pid")) and psutil.pid_exists(st["pid"])
    if not (running and st.get("active") and j):
        return {"active": False, "items": []}
    items = []

    def add(group, name, ok, detail=""):
        items.append({"group": group, "name": name, "ok": ok, "detail": detail})

    cpu = st.get("cpu") or {}
    names_running = {}
    for p in psutil.process_iter(["name"]):
        names_running.setdefault((p.info["name"] or "").lower(), []).append(p)
    # ---------------- il gioco
    for pid_s, info in (st.get("procs") or {}).items():
        pid = int(pid_s)
        try:
            p = psutil.Process(pid)
            if abs(p.create_time() - (info.get("create") or 0)) >= 1:
                continue
        except psutil.Error:
            continue
        exe = info.get("name") or "?"
        label, cls, gcls = PRIORITY.get(info.get("prio_key") or "high", PRIORITY["high"])
        if opts.get("priority") and cls != PRIORITY["normal"][1]:
            try:
                cur = p.nice()
            except psutil.Error:
                cur = None
            cur_name = {v[1]: v[0] for v in PRIORITY.values()}.get(cur, {0x40: "Bassa", 0x4000: "Inferiore al normale",
                                                                          0x100: "In tempo reale"}.get(cur, "?"))
            if info.get("anticheat"):
                reg = _ifeo_get(exe)
                if cur == cls:
                    add("Gioco", "Priorita' CPU di %s" % exe, True, "%s (anti-cheat %s: data da Windows)" % (label, info["anticheat"]))
                elif reg == IFEO_CLASS.get(info.get("prio_key") or "high"):
                    add("Gioco", "Priorita' CPU di %s" % exe, None,
                        "%s dalla PROSSIMA apertura (anti-cheat %s)" % (label, info["anticheat"]))
                else:
                    add("Gioco", "Priorita' CPU di %s" % exe, False, "ora: %s (anti-cheat %s)" % (cur_name, info["anticheat"]))
            else:
                add("Gioco", "Priorita' CPU di %s" % exe, cur == cls,
                    label if cur == cls else "ora: %s, attesa: %s" % (cur_name, label))
                if opts.get("gpu_priority"):
                    g = _gpu_priority_of(pid)
                    gnames = {0: "Inattiva", 1: "Inferiore al normale", 2: "Normale", 3: "Superiore al normale",
                              4: "Alta", 5: "Tempo reale"}
                    if g is not None:
                        add("Gioco", "Priorita' GPU di %s" % exe, g == gcls, label if g == gcls else "ora: %s" % gnames.get(g, g))
                    elif info.get("gpu_set") is True:
                        add("Gioco", "Priorita' GPU di %s" % exe, True, "%s (accettata da Windows)" % label)
                    elif info.get("gpu_set") is False:
                        add("Gioco", "Priorita' GPU di %s" % exe, False, "Windows non l'ha accettata")
                    else:
                        add("Gioco", "Priorita' GPU di %s" % exe, None, "Windows non permette di leggerla")
        if opts.get("affinity") and cpu.get("apply") and not info.get("anticheat"):
            try:
                aff = sorted(p.cpu_affinity())
            except psutil.Error:
                aff = None
            want = sorted(cpu.get("cpus") or [])
            add("Gioco", "Affinita' dei core di %s" % exe, None if aff is None else aff == want,
                "core %s" % _cpus_text(want) if aff == want else "ora: core %s" % _cpus_text(aff or []))
    if not any(i["group"] == "Gioco" for i in items):
        add("Gioco", "Processo del gioco", None, "in attesa (la priorita' arriva 8-10 secondi dopo l'avvio)")
    if opts.get("affinity") and not cpu.get("apply"):
        add("Gioco", "Affinita' dei core", None, CPU_SHORT.get(cpu.get("kind"), "non utile su questo processore"))
    # ---------------- servizi
    restops = j.get("restops") or {}
    for name in j.get("services") or []:
        s = _service_state(name)
        again = " (ripartito da solo %d volte: fermato di nuovo)" % restops[name] if restops.get(name) else ""
        if s == "stopped":
            add("Servizi in pausa", name, True, "fermo" + again)
        elif s is None:
            add("Servizi in pausa", name, None, "non leggibile")
        else:
            add("Servizi in pausa", name, False, "ripartito: lo fermo di nuovo entro 15 secondi")
    if (opts.get("stop_services") or opts.get("stop_updates")) and not j.get("services"):
        add("Servizi in pausa", "Servizi", True, "erano gia' tutti fermi")
    # ---------------- app chiuse (una riga per programma)
    for n in j.get("closed") or []:
        back = n in names_running
        add("App chiuse", n, True if not back else None, "chiuso" if not back else "riaperto da Windows (usa poca CPU)")
    if (opts.get("close_apps") or opts.get("close_onedrive") or opts.get("close_shell")) and not j.get("closed"):
        add("App chiuse", "Componenti di Windows", True, "nessuno era aperto")
    # ---------------- programmi in background (raggruppati per nome)
    if opts.get("bg_priority"):
        groups = {}
        for key, rec in (j.get("bg") or {}).items():
            ct = rec[0]
            try:
                p = psutil.Process(int(key))
                if abs(p.create_time() - ct) >= 1:
                    continue
                name = rec[2] if len(rec) > 2 else p.name()
                g = groups.setdefault(name, [0, 0])
                g[0] += 1
                g[1] += p.nice() == 0x4000
            except (psutil.Error, ValueError, IndexError):
                continue
        for name in sorted(groups, key=str.lower):
            tot, low = groups[name]
            add("Programmi a priorita' bassa", name + (" ×%d" % tot if tot > 1 else ""), low == tot,
                "Inferiore al normale" if low == tot else "%d su %d" % (low, tot))
        if not groups:
            add("Programmi a priorita' bassa", "Programmi in background", None, "nessun programma da abbassare")
    # ---------------- sistema e rete
    if opts.get("timer"):
        t = _timer_now_ms()
        add("Sistema", "Timer di sistema", None if t is None else t <= 0.51,
            "non leggibile" if t is None else "%.3f ms" % t)
    if opts.get("power_plan"):
        a = _active_scheme()
        add("Sistema", "Piano Prestazioni elevate", a == "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", a or "non leggibile")
    if opts.get("trim_ram"):
        msg = next((a for a in reversed(st.get("actions") or []) if a.startswith("RAM liberata")), None)
        add("Sistema", "RAM liberata all'avvio del gioco", True if msg else None,
            msg.replace("RAM liberata dai programmi in background: ", "") if msg else "non risulta eseguita")
    if opts.get("qos") and j.get("qos"):
        code, out = _ps("Get-NetQosPolicy -ErrorAction SilentlyContinue | Where-Object Name -like 'LagDoctor-*' | "
                        "ForEach-Object { $_.Name + '=' + $_.DSCPAction }", timeout=30)
        have = dict(l.strip().split("=", 1) for l in out.splitlines() if "=" in l)
        for pol in j["qos"]:
            add("Rete", "Priorita' QoS per " + pol.replace("LagDoctor-", ""), have.get(pol) == "46",
                "DSCP 46" if have.get(pol) == "46" else "regola non trovata")
    return {"active": True, "games": st.get("games"), "items": items,
            "ok": sum(1 for i in items if i["ok"] is True), "ko": sum(1 for i in items if i["ok"] is False)}


def quick_status():
    """Per la Panoramica: accesa? attiva su quali giochi? cosa ha fatto? (lettura veloce, solo file)."""
    c = load_config()
    st = _load(STATUS, {})
    running = bool(st.get("pid")) and psutil.pid_exists(st["pid"]) if st.get("pid") else False
    return {"enabled": bool(c.get("enabled")), "running": running, "active": bool(running and st.get("active")),
            "games": st.get("games") or [], "actions": (st.get("actions") or [])[-12:],
            "n_games": sum(1 for g in c.get("games", []) if g.get("on"))}


def status():
    st = _load(STATUS, {})
    pid = daemon_pid()
    st["running"] = bool(pid)
    if not pid:
        st["active"] = False
    task = _run(["schtasks", "/Query", "/TN", TASK])[0] == 0
    st["autostart"] = task
    return st


if __name__ == "__main__":
    main()
