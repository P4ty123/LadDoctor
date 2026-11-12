"""Overlay: programmi che si 'agganciano' al gioco per disegnarci sopra (FPS, chat, notifiche, registrazione).

Per ogni programma installato LagDoctor controlla, dove e' possibile leggerlo, se il suo overlay e' acceso:
  - dalle impostazioni salvate dal programma (Steam, Ubisoft Connect)
  - dal processo dell'overlay in esecuzione (NVIDIA, AMD, RivaTuner, Overwolf: girano solo se l'overlay e' acceso)
Come LagDoctor li spegne (ogni modifica si annulla):
  - "impostazione": scrive l'impostazione del programma nel suo file (Steam, app EA, Ubisoft Connect). Il programma
    deve essere chiuso, altrimenti la sovrascrive uscendo: LagDoctor lo chiude prima.
  - "processo": l'overlay e' un programma a parte (NVIDIA, AMD, RivaTuner, Overwolf). LagDoctor lo chiude, ne toglie
    l'avvio con Windows e la Game mode lo richiude a ogni partita.
  - Discord, Intel e GOG non hanno un'impostazione modificabile dall'esterno: la voce spiega dove spegnerlo.

Le voci di Windows che riguardano gli overlay (Game Bar, registrazione in background, MPO) sono normali
ottimizzazioni e vengono spostate in questa categoria.
"""
import glob
import json
import os
import re
import subprocess
import threading
import time

from . import tweak_docs
from . import tweaks as T

CAT = "Overlays"
# voci di Windows gia' esistenti che lavorano sugli overlay: passano nella categoria Overlays
MOVE_IDS = ("game_dvr", "gamedvr_policy", "gamebar_shortcut", "mpo_off", "mpo_full")

# processi che indicano un overlay in esecuzione ADESSO
LIVE = {
    "gameoverlayui.exe": "Overlay di Steam",
    "gameoverlayui64.exe": "Overlay di Steam",
    "nvidia overlay.exe": "Overlay NVIDIA",
    "nvidia share.exe": "Overlay NVIDIA (GeForce Experience)",
    "amdow.exe": "Overlay AMD Software",
    "rtss.exe": "RivaTuner Statistics Server",
    "rtsshooksloader64.exe": "RivaTuner Statistics Server",
    "overwolf.exe": "Overwolf",
    "eosoverlayrenderer-win64-shipping.exe": "Overlay di Epic Games",
    "igoproxy64.exe": "Overlay dell'app EA",
    "igoproxy.exe": "Overlay dell'app EA",
    "gamebar.exe": "Xbox Game Bar",
    "gamebarftserver.exe": "Xbox Game Bar",
    "medal.exe": "Medal",
}

_snap = {"t": 0.0, "names": frozenset()}
_lock = threading.Lock()


def running_names(max_age=3.0):
    """Nomi (minuscoli) dei processi in esecuzione, letti al massimo ogni pochi secondi."""
    with _lock:
        if time.time() - _snap["t"] > max_age:
            try:
                import psutil
                names = set()
                for p in psutil.process_iter(["name"]):
                    n = (p.info.get("name") or "").lower()
                    if n:
                        names.add(n)
                _snap["names"] = frozenset(names)
            except Exception:
                _snap["names"] = frozenset()
            _snap["t"] = time.time()
        return _snap["names"]


def live():
    """Overlay in esecuzione adesso: [{"name": ..., "process": ...}] senza doppioni."""
    names = running_names(0)
    out, seen = [], set()
    for proc, label in LIVE.items():
        if proc in names and label not in seen:
            seen.add(label)
            out.append({"name": label, "process": proc})
    return out


def _env(name, default=""):
    return os.environ.get(name) or default


def _pf(*parts):
    return os.path.join(_env("ProgramFiles", r"C:\Program Files"), *parts)


def _pf86(*parts):
    return os.path.join(_env("ProgramFiles(x86)", r"C:\Program Files (x86)"), *parts)


def _local(*parts):
    return os.path.join(_env("LOCALAPPDATA"), *parts) if _env("LOCALAPPDATA") else ""


def _exists(*paths):
    return any(p and os.path.exists(p) for p in paths)


# ---------------------------------------------------------------- chiudere e riaprire i programmi

def kill(names, prefixes=()):
    """Chiude i processi con questi nomi. Restituisce [(nome, percorso exe)] di quelli chiusi."""
    import psutil
    names = {n.lower() for n in names}
    out = []
    for p in psutil.process_iter(["name", "exe"]):
        n = (p.info.get("name") or "").lower()
        if n in names or any(n.startswith(x) for x in prefixes):
            try:
                out.append((n, p.info.get("exe") or ""))
                p.kill()
            except Exception:
                pass
    _snap["t"] = 0.0
    return out


def wait_gone(names, timeout=25):
    names = {n.lower() for n in names}
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not names & running_names(0):
            return True
        time.sleep(0.5)
    return False


def relaunch(exes):
    for exe in exes or []:
        if exe and os.path.isfile(exe):
            try:
                subprocess.Popen([exe], close_fds=True, creationflags=0x00000008 | 0x00000200)  # DETACHED, NEW_GROUP
            except Exception:
                pass


def _read(f):
    with open(f, encoding="utf-8", errors="replace", newline="") as fh:
        return fh.read()


def _write(f, txt):
    tmp = f + ".lagdoctor.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(txt)
    os.replace(tmp, f)


# ---------------------------------------------------------------- impostazioni lette dai file dei programmi

def _steam_dir():
    p = T.reg_read("HKCU", r"Software\Valve\Steam", "SteamPath")[0]
    if p and os.path.isdir(p):
        return p
    p = _pf86("Steam")
    return p if os.path.isdir(p) else None


def steam_overlay_enabled():
    """True/False dall'impostazione dell'account Steam usato piu' di recente; None se non leggibile."""
    d = _steam_dir()
    if not d:
        return None
    files = glob.glob(os.path.join(d, "userdata", "*", "config", "localconfig.vdf"))
    if not files:
        return None
    f = max(files, key=os.path.getmtime)
    try:
        with open(f, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
    except OSError:
        return None
    m = re.search(r'"EnableGameOverlay"\s+"(\d)"', txt)
    if m:
        return m.group(1) != "0"
    return True  # mai cambiata: l'overlay di Steam e' acceso di serie


def _steam_files():
    d = _steam_dir()
    return glob.glob(os.path.join(d, "userdata", "*", "config", "localconfig.vdf")) if d else []


_STEAM_KEY = re.compile(r'("EnableGameOverlay"\s+")(\d)(")')


def _steam_set(txt, value):
    """Imposta EnableGameOverlay nel blocco "system" (lo crea se manca). value None = toglie la riga."""
    if _STEAM_KEY.search(txt):
        if value is None:
            return re.sub(r'[ \t]*"EnableGameOverlay"\s+"\d"[^\n]*\n', "", txt, count=1)
        return _STEAM_KEY.sub(lambda m: m.group(1) + value + m.group(3), txt, count=1)
    if value is None:
        return txt
    nl = "\r\n" if "\r\n" in txt else "\n"
    m = re.search(r'(?m)^([ \t]*)"system"\s*\{[^\n]*\n', txt)
    if m:
        ind = m.group(1) + "\t"
        return txt[:m.end()] + '%s"EnableGameOverlay"\t\t"%s"%s' % (ind, value, nl) + txt[m.end():]
    m = re.search(r'"UserLocalConfigStore"\s*\{[^\n]*\n', txt)
    if not m:
        raise RuntimeError("file delle impostazioni di Steam non riconosciuto")
    block = '\t"system"%s\t{%s\t\t"EnableGameOverlay"\t\t"%s"%s\t}%s' % (nl, nl, value, nl, nl)
    return txt[:m.end()] + block + txt[m.end():]


def steam_close():
    """Chiude Steam come fa il suo menu Esci (steam.exe -shutdown), poi forzando se non risponde."""
    if "steam.exe" not in running_names(0):
        return False
    d = _steam_dir()
    exe = os.path.join(d, "steam.exe") if d else ""
    if exe and os.path.isfile(exe):
        try:
            subprocess.Popen([exe, "-shutdown"], close_fds=True, creationflags=0x08000000)
        except Exception:
            pass
    if not wait_gone(["steam.exe"], 30):
        kill(["steam.exe", "steamwebhelper.exe"])
        wait_gone(["steam.exe"], 10)
    return True


def steam_disable():
    files = _steam_files()
    if not files:
        raise RuntimeError("non trovo le impostazioni di Steam (hai mai effettuato l'accesso?)")
    was_open = steam_close()
    old = {}
    for f in files:
        txt = _read(f)
        m = _STEAM_KEY.search(txt)
        old[f] = m.group(2) if m else None
        _write(f, _steam_set(txt, "0"))
    return {"files": old, "reopen": was_open}


def steam_restore(b):
    steam_close()
    for f, v in (b.get("files") or {}).items():
        if os.path.isfile(f):
            _write(f, _steam_set(_read(f), v))


def _ea_files():
    d = _local("Electronic Arts", "EA Desktop")
    return glob.glob(os.path.join(d, "user_*.ini")) if d else []


def ea_overlay_enabled():
    files = _ea_files()
    if not files:
        return None
    try:
        txt = _read(max(files, key=os.path.getmtime))
    except OSError:
        return None
    m = re.search(r"(?mi)^user\.igoenabled\s*=\s*(\S+)", txt)
    return True if not m else m.group(1).strip().lower() not in ("0", "false")


def _ea_set(txt, value):
    if re.search(r"(?mi)^user\.igoenabled\s*=", txt):
        if value is None:
            return re.sub(r"(?mi)^user\.igoenabled\s*=[^\n]*\n?", "", txt, count=1)
        return re.sub(r"(?mi)^(user\.igoenabled\s*=)[^\r\n]*", lambda m: m.group(1) + value, txt, count=1)
    if value is None:
        return txt
    nl = "\r\n" if "\r\n" in txt else "\n"
    return txt + ("" if txt.endswith(("\n", "\r")) or not txt else nl) + "user.igoenabled=" + value + nl


EA_PROCS = ("eadesktop.exe", "eabackgroundservice.exe", "ealocalhostsvc.exe")


def ea_disable():
    files = _ea_files()
    if not files:
        raise RuntimeError("non trovo le impostazioni dell'app EA (apri l'app EA ed effettua l'accesso una volta)")
    closed = kill(["eadesktop.exe"])
    wait_gone(["eadesktop.exe"], 10)
    old = {}
    for f in files:
        txt = _read(f)
        m = re.search(r"(?mi)^user\.igoenabled\s*=\s*([^\r\n]*)", txt)
        old[f] = m.group(1).strip() if m else None
        _write(f, _ea_set(txt, "0"))
    return {"files": old, "reopen": [e for _n, e in closed]}


def ea_restore(b):
    kill(["eadesktop.exe"])
    wait_gone(["eadesktop.exe"], 10)
    for f, v in (b.get("files") or {}).items():
        if os.path.isfile(f):
            _write(f, _ea_set(_read(f), v))


_UBI_RE = re.compile(r"(?m)^(overlay:[ \t]*\r?\n(?:[ \t]+.*\r?\n)*?[ \t]+enabled:[ \t]*)(true|false)")


def _ubi_file():
    return _local("Ubisoft Game Launcher", "settings.yml")


def ubisoft_disable():
    f = _ubi_file()
    if not f or not os.path.isfile(f):
        raise RuntimeError("non trovo le impostazioni di Ubisoft Connect (aprilo ed effettua l'accesso una volta)")
    closed = kill(["upc.exe", "ubisoftconnect.exe", "uplaywebcore.exe"])
    wait_gone(["upc.exe"], 10)
    txt = _read(f)
    m = _UBI_RE.search(txt)
    if m:
        old = m.group(2)
        txt = _UBI_RE.sub(lambda x: x.group(1) + "false", txt, count=1)
    else:
        old = None
        nl = "\r\n" if "\r\n" in txt else "\n"
        txt = txt + ("" if txt.endswith("\n") or not txt else nl) + "overlay:" + nl + "  enabled: false" + nl
    _write(f, txt)
    return {"old": old, "reopen": [e for n, e in closed if n == "upc.exe"]}


def ubisoft_restore(b):
    f = _ubi_file()
    if not f or not os.path.isfile(f):
        return
    kill(["upc.exe", "ubisoftconnect.exe", "uplaywebcore.exe"])
    wait_gone(["upc.exe"], 10)
    txt = _read(f)
    if b.get("old"):
        txt = _UBI_RE.sub(lambda x: x.group(1) + b["old"], txt, count=1)
    else:
        txt = re.sub(r"(?m)^overlay:[ \t]*\r?\n[ \t]+enabled:[ \t]*false[ \t]*\r?\n?", "", txt, count=1)
    _write(f, txt)


def ubisoft_overlay_enabled():
    f = _local("Ubisoft Game Launcher", "settings.yml")
    if not f or not os.path.isfile(f):
        return None
    try:
        with open(f, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
    except OSError:
        return None
    m = re.search(r"(?m)^overlay:\s*\n(?:[ \t]+.*\n)*?[ \t]+enabled:\s*(true|false)", txt)
    return None if not m else m.group(1) == "true"


# ---------------------------------------------------------------- la voce

class OverlayItem(T.Tweak):
    """Un overlay di un programma. status(): True = overlay spento (bene), False = acceso, None = non leggibile.

    off/on: funzioni che lo spengono da LagDoctor (restituiscono il backup) e lo riaccendono.
    block: processi dell'overlay che LagDoctor chiude (e la Game mode richiude a ogni partita).
    startup: parole che riconoscono il suo avvio con Windows (viene disattivato).
    closes: programma che LagDoctor deve chiudere per cambiare l'impostazione (mostrato prima di applicare)."""

    def __init__(self, id, name, desc, how, installed, procs=(), setting=None, by_process=False,
                 efficacy="bassa", warning="", off=None, on=None, block=(), startup=(), closes=None, how_ld=None):
        super().__init__(id, CAT, name, desc, efficacy, risk=0, warning=warning, recommend=lambda s: False,
                         kind="overlay")
        self.how = how
        self._off, self._on, self.block, self.startup = off, on, tuple(block), tuple(startup)
        self.closes = closes
        self.how_ld = how_ld  # cosa fa LagDoctor quando lo spegni
        self.manual = off is None and not block
        self._installed = installed
        self.procs = tuple(procs)
        self._setting = setting
        self._by_process = by_process  # il processo gira solo se l'overlay e' acceso
        self.note = None

    def available(self):
        try:
            return bool(self._installed())
        except Exception:
            return False

    def running(self):
        names = running_names()
        return [p for p in self.procs if p in names]

    def status(self):
        run = self.running()
        if self._setting is not None:
            v = self._setting()
            if v is not None:
                self.note = None
                return not v
        if run:
            return False
        if self._by_process:
            return True
        self.note = "da controllare nel programma"
        return None

    def apply(self):
        if self.manual:
            raise RuntimeError("Questo overlay si spegne solo dal suo programma: apri i dettagli per sapere dove.")
        b = {}
        if self._off:
            b["cfg"] = self._off()
        if self.block:
            b["block"] = list(self.block)
            closed = kill(self.block)
            b["reopen"] = sorted({e for _n, e in closed if e})
        if self.startup:
            b["startup"] = []
            for it in T.startup_items():
                cmd = (it.get("name", "") + " " + it.get("cmd", "")).lower()
                if it.get("enabled") and any(w in cmd for w in self.startup):
                    T.set_startup(it, False)
                    b["startup"].append(it)
        return b

    def revert(self, backup):
        backup = backup or {}
        if self._on and backup.get("cfg") is not None:
            self._on(backup["cfg"])
        for it in backup.get("startup") or []:
            try:
                T.set_startup(it, True)
            except Exception:
                pass
        relaunch(backup.get("reopen"))
        cfg = backup.get("cfg") or {}
        if cfg.get("reopen") is True and self.id == "ov_steam":
            d = _steam_dir()
            relaunch([os.path.join(d, "steam.exe")] if d else [])
        elif isinstance(cfg.get("reopen"), list):
            relaunch(cfg["reopen"])
        _snap["t"] = 0.0
        return "riacceso"


def blocked_processes():
    """Processi degli overlay spenti da LagDoctor (letti dal suo file delle modifiche: li usa la Game mode)."""
    try:
        from . import paths
        with open(paths.data("modifiche_applicate.json"), encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        return []
    out = []
    for k, v in st.items():
        if k.startswith("ov_") and isinstance(v, dict):
            out += (v.get("backup") or {}).get("block") or []
    return sorted(set(out))


ITEMS = [
    OverlayItem(
        "ov_steam", "Overlay di Steam",
        "Il menu Maiusc+Tab di Steam dentro i giochi",
        "Steam > menu Steam (in alto a sinistra) > Impostazioni > In gioco > disattiva \"Abilita l'overlay di Steam "
        "durante il gioco\". Per un solo gioco: Libreria > tasto destro sul gioco > Proprieta' > Generali.",
        lambda: _steam_dir(), procs=("gameoverlayui.exe", "gameoverlayui64.exe"), setting=steam_overlay_enabled,
        warning="Senza overlay non funzionano chat, guida e browser di Steam dentro il gioco, e in alcuni giochi "
                "i controller configurati con Steam Input.",
        off=steam_disable, on=steam_restore, closes="Steam", efficacy="bassa",
        how_ld="LagDoctor chiude Steam (come dal menu Esci) e spegne l'overlay nelle sue impostazioni per tutti i giochi. Riapri Steam quando vuoi: l'impostazione resta."),
    OverlayItem(
        "ov_nvidia", "Overlay NVIDIA (NVIDIA App / GeForce Experience)",
        "Alt+Z: statistiche, filtri, screenshot e Instant Replay",
        "NVIDIA App > Impostazioni (ingranaggio) > Funzionalita' > disattiva \"Overlay NVIDIA\". Con GeForce "
        "Experience: Impostazioni > Generale > \"Overlay di gioco\". Se vuoi tenere l'overlay, spegni almeno "
        "Instant Replay (Alt+Maiusc+F10), che registra di continuo.",
        lambda: _exists(_pf("NVIDIA Corporation", "NVIDIA app"), _pf("NVIDIA Corporation", "NVIDIA GeForce Experience")),
        procs=("nvidia overlay.exe", "nvidia share.exe"), by_process=True, efficacy="media",
        block=("nvidia overlay.exe", "nvidia share.exe"),
        how_ld="LagDoctor chiude l'overlay NVIDIA (e con lui Instant Replay). L'app NVIDIA lo riapre al prossimo avvio di Windows: con la Game mode attiva LagDoctor lo richiude a ogni partita. Per spegnerlo per sempre usa anche il punto qui sopra nell'app NVIDIA."),
    OverlayItem(
        "ov_amd", "Overlay di AMD Software (Adrenalin)",
        "Alt+R / Ctrl+Maiusc+O: metriche, registrazione e replay istantaneo",
        "AMD Software > ingranaggio in alto a destra > Preferenze > disattiva \"Overlay di gioco\". In Prestazioni > "
        "Metriche disattiva l'overlay delle metriche; in Registrazione spegni \"Replay istantaneo\".",
        lambda: _exists(_pf("AMD", "CNext", "CNext", "RadeonSoftware.exe")), procs=("amdow.exe",),
        block=("amdow.exe",),
        how_ld="LagDoctor chiude l'overlay di AMD Software. AMD Software lo riapre al prossimo avvio: con la Game mode attiva LagDoctor lo richiude a ogni partita. Per spegnerlo per sempre usa anche il punto qui sopra."),
    OverlayItem(
        "ov_intel", "Overlay Intel (Intel Graphics Software / Arc Control)",
        "Overlay delle prestazioni e registrazione della scheda video Intel",
        "Apri Intel Graphics Software (o Arc Control) e nelle impostazioni disattiva l'overlay delle prestazioni, "
        "la sua scorciatoia da tastiera e la registrazione.",
        lambda: _exists(_pf("Intel", "Intel Graphics Software"), _pf("Intel", "Intel Arc Control"))),
    OverlayItem(
        "ov_discord", "Overlay di Discord",
        "Chi sta parlando e notifiche disegnati sopra il gioco",
        "Discord > Impostazioni utente (ingranaggio) > Overlay di gioco > disattiva \"Abilita overlay in gioco\". "
        "Oppure lascialo acceso e spegnilo solo per i giochi in Attivita' registrate.",
        lambda: _exists(_local("Discord"), _local("DiscordPTB"), _local("DiscordCanary"))),
    OverlayItem(
        "ov_rtss", "RivaTuner Statistics Server (overlay di MSI Afterburner)",
        "FPS e temperature sopra il gioco; si aggancia a tutti i giochi finche' e' aperto",
        "Se lo usi solo per vedere FPS e temperature, chiudilo (icona vicino all'orologio > Esci) o in MSI Afterburner "
        "> Impostazioni > Monitoraggio togli \"Mostra nell'On-Screen Display\". Se lo usi come limitatore di FPS "
        "lascialo pure: in quel caso premi Ignora su questa voce.",
        lambda: _exists(_pf86("RivaTuner Statistics Server", "RTSS.exe")),
        procs=("rtss.exe", "rtsshooksloader64.exe"), by_process=True,
        block=("rtss.exe", "rtsshooksloader64.exe", "rtsshooksloader.exe"), startup=("rtss", "rivatuner"),
        how_ld="LagDoctor chiude RivaTuner, ne toglie l'avvio con Windows e la Game mode lo richiude a ogni partita. Se MSI Afterburner lo riapre da solo, togli anche l'avvio di Afterburner (pagina Avvio automatico)."),
    OverlayItem(
        "ov_overwolf", "Overwolf (Outplayed, Porofessor e altre app overlay)",
        "Piattaforma di app che si disegnano sopra i giochi",
        "Chiudi Overwolf quando non ti serve e togli il suo avvio con Windows (pagina Avvio automatico). Nelle "
        "impostazioni di Overwolf puoi spegnere l'overlay gioco per gioco.",
        lambda: _exists(_pf86("Overwolf")), procs=("overwolf.exe",), by_process=True, efficacy="media",
        block=("overwolf.exe", "overwolfbrowser.exe", "overwolfhelper.exe", "overwolfhelper64.exe"), startup=("overwolf",),
        how_ld="LagDoctor chiude Overwolf, ne toglie l'avvio con Windows e la Game mode lo richiude a ogni partita."),
    OverlayItem(
        "ov_ea", "Overlay dell'app EA",
        "Menu Maiusc+F1 dentro i giochi EA",
        "App EA > menu (tre linee in alto a sinistra) > Impostazioni > Applicazione > disattiva \"Overlay in gioco\".",
        lambda: _exists(_pf("Electronic Arts", "EA Desktop")), procs=("igoproxy64.exe", "igoproxy.exe"),
        setting=ea_overlay_enabled, off=ea_disable, on=ea_restore, closes="app EA",
        how_ld="LagDoctor chiude l'app EA e spegne l'overlay nel suo file delle impostazioni (user.igoenabled=0). Dopo un aggiornamento l'app EA potrebbe riaccenderlo: LagDoctor te lo segnala qui."),
    OverlayItem(
        "ov_ubisoft", "Overlay di Ubisoft Connect",
        "Menu Maiusc+F2 dentro i giochi Ubisoft",
        "Ubisoft Connect > menu (tre linee) > Impostazioni > Generale > disattiva \"Abilita overlay in gioco per i "
        "giochi supportati\".",
        lambda: _exists(_pf86("Ubisoft", "Ubisoft Game Launcher")), setting=ubisoft_overlay_enabled,
        off=ubisoft_disable, on=ubisoft_restore, closes="Ubisoft Connect",
        how_ld="LagDoctor chiude Ubisoft Connect e spegne l'overlay nelle sue impostazioni."),
    OverlayItem(
        "ov_gog", "Overlay di GOG Galaxy",
        "Menu Maiusc+Tab dentro i giochi GOG",
        "GOG Galaxy > ingranaggio in alto a sinistra > Impostazioni > Funzioni in gioco > disattiva \"Overlay\".",
        lambda: _exists(_pf86("GOG Galaxy"))),
]

_DOCS = {
    "ov_steam": ("L'overlay di Steam si carica dentro ogni gioco avviato da Steam per mostrare chat, guida, browser, "
                 "screenshot e contatore FPS (Maiusc+Tab).",
                 "Ogni overlay disegna sopra ogni frame del gioco e aggiunge un passaggio prima che il frame arrivi "
                 "allo schermo. Su alcuni giochi provoca micro-scatti o conflitti con altri overlay."),
    "ov_nvidia": ("L'overlay NVIDIA (Alt+Z) gestisce statistiche, filtri, screenshot e registrazione. Con Instant Replay "
                  "attivo registra di continuo gli ultimi minuti di gioco.",
                  "La registrazione continua usa l'encoder video e un po' di memoria video; l'overlay resta agganciato "
                  "al gioco anche quando non lo apri."),
    "ov_amd": ("L'overlay di AMD Software (Alt+R) mostra metriche, registrazione e replay istantaneo dentro il gioco.",
               "Il replay istantaneo registra di continuo; l'overlay si aggancia a ogni gioco."),
    "ov_intel": ("L'overlay di Intel Graphics Software / Arc Control mostra le prestazioni e gestisce la registrazione.",
                 "Come gli altri overlay si aggancia al gioco e la registrazione usa la scheda video."),
    "ov_discord": ("L'overlay di Discord mostra chi sta parlando, i messaggi e le notifiche sopra il gioco.",
                   "Si aggancia a ogni gioco. E' uno degli overlay piu' spesso indicati come causa di micro-scatti e "
                   "di conflitti con altri overlay."),
    "ov_rtss": ("RivaTuner Statistics Server disegna l'OSD di MSI Afterburner (FPS, temperature, uso) e puo' limitare gli FPS.",
                "Finche' e' aperto si aggancia a TUTTI i programmi 3D, anche quando non ti serve."),
    "ov_overwolf": ("Overwolf fa girare app (statistiche, registrazione clip) che si disegnano sopra i giochi.",
                    "Le app Overwolf sono basate su un browser: usano CPU e memoria e si agganciano al gioco."),
    "ov_ea": ("L'overlay dell'app EA (Maiusc+F1) mostra amici e chat dentro i giochi EA.",
              "Si aggancia ai giochi EA; spegnerlo toglie un livello in piu' sopra il gioco."),
    "ov_ubisoft": ("L'overlay di Ubisoft Connect (Maiusc+F2) mostra amici, sfide e FPS dentro i giochi Ubisoft.",
                   "Si aggancia ai giochi Ubisoft; spegnerlo toglie un livello in piu' sopra il gioco."),
    "ov_gog": ("L'overlay di GOG Galaxy (Maiusc+Tab) mostra amici e obiettivi dentro i giochi GOG.",
               "Si aggancia ai giochi GOG; spegnerlo toglie un livello in piu' sopra il gioco."),
}


def register():
    for t in ITEMS:
        cosa, perche = _DOCS[t.id]
        tweak_docs.doc(t.id, cosa, perche, t.warning or "Perdi le funzioni dell'overlay dentro il gioco: puoi "
                       "riaccenderlo quando vuoi dallo stesso punto.")
    for t in T.CATALOG:
        if t.id in MOVE_IDS:
            t.cat = CAT
    for t in T.BY_ID.values():
        if t.id in MOVE_IDS:
            t.cat = CAT
    if CAT not in T.CAT_ORDER:
        T.CAT_ORDER.insert(T.CAT_ORDER.index("Gioco") + 1, CAT)
    T.CATALOG.extend(ITEMS)
    T.CATALOG.sort(key=lambda t: T.CAT_ORDER.index(t.cat))
    T.BY_ID.update({t.id: t for t in ITEMS})
