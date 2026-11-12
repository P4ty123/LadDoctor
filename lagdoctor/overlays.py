"""Overlay: programmi che si 'agganciano' al gioco per disegnarci sopra (FPS, chat, notifiche, registrazione).

Per ogni programma installato LagDoctor controlla, dove e' possibile leggerlo, se il suo overlay e' acceso:
  - dalle impostazioni salvate dal programma (Steam, Ubisoft Connect)
  - dal processo dell'overlay in esecuzione (NVIDIA, AMD, RivaTuner, Overwolf: girano solo se l'overlay e' acceso)
Queste voci non si cambiano da LagDoctor (le impostazioni sono dentro i singoli programmi e verrebbero
sovrascritte): la voce spiega dove spegnerlo.

Le voci di Windows che riguardano gli overlay (Game Bar, registrazione in background, MPO) sono normali
ottimizzazioni e vengono spostate in questa categoria.
"""
import glob
import os
import re
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
    """Un overlay di un programma. status(): True = overlay spento (bene), False = acceso, None = non leggibile."""

    manual = True

    def __init__(self, id, name, desc, how, installed, procs=(), setting=None, by_process=False,
                 efficacy="bassa", warning=""):
        super().__init__(id, CAT, name, desc, efficacy, risk=0, warning=warning, recommend=lambda s: False,
                         kind="overlay")
        self.how = how
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
        raise RuntimeError("Questo overlay si spegne dal suo programma: apri i dettagli per sapere dove.")

    def revert(self, backup):
        return None


ITEMS = [
    OverlayItem(
        "ov_steam", "Overlay di Steam",
        "Il menu Maiusc+Tab di Steam dentro i giochi",
        "Steam > menu Steam (in alto a sinistra) > Impostazioni > In gioco > disattiva \"Abilita l'overlay di Steam "
        "durante il gioco\". Per un solo gioco: Libreria > tasto destro sul gioco > Proprieta' > Generali.",
        lambda: _steam_dir(), procs=("gameoverlayui.exe", "gameoverlayui64.exe"), setting=steam_overlay_enabled,
        warning="Senza overlay non funzionano chat, guida e browser di Steam dentro il gioco, e in alcuni giochi "
                "i controller configurati con Steam Input."),
    OverlayItem(
        "ov_nvidia", "Overlay NVIDIA (NVIDIA App / GeForce Experience)",
        "Alt+Z: statistiche, filtri, screenshot e Instant Replay",
        "NVIDIA App > Impostazioni (ingranaggio) > Funzionalita' > disattiva \"Overlay NVIDIA\". Con GeForce "
        "Experience: Impostazioni > Generale > \"Overlay di gioco\". Se vuoi tenere l'overlay, spegni almeno "
        "Instant Replay (Alt+Maiusc+F10), che registra di continuo.",
        lambda: _exists(_pf("NVIDIA Corporation", "NVIDIA app"), _pf("NVIDIA Corporation", "NVIDIA GeForce Experience")),
        procs=("nvidia overlay.exe", "nvidia share.exe"), by_process=True, efficacy="media"),
    OverlayItem(
        "ov_amd", "Overlay di AMD Software (Adrenalin)",
        "Alt+R / Ctrl+Maiusc+O: metriche, registrazione e replay istantaneo",
        "AMD Software > ingranaggio in alto a destra > Preferenze > disattiva \"Overlay di gioco\". In Prestazioni > "
        "Metriche disattiva l'overlay delle metriche; in Registrazione spegni \"Replay istantaneo\".",
        lambda: _exists(_pf("AMD", "CNext", "CNext", "RadeonSoftware.exe")), procs=("amdow.exe",)),
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
        procs=("rtss.exe", "rtsshooksloader64.exe"), by_process=True),
    OverlayItem(
        "ov_overwolf", "Overwolf (Outplayed, Porofessor e altre app overlay)",
        "Piattaforma di app che si disegnano sopra i giochi",
        "Chiudi Overwolf quando non ti serve e togli il suo avvio con Windows (pagina Avvio automatico). Nelle "
        "impostazioni di Overwolf puoi spegnere l'overlay gioco per gioco.",
        lambda: _exists(_pf86("Overwolf")), procs=("overwolf.exe",), by_process=True, efficacy="media"),
    OverlayItem(
        "ov_ea", "Overlay dell'app EA",
        "Menu Maiusc+F1 dentro i giochi EA",
        "App EA > menu (tre linee in alto a sinistra) > Impostazioni > Applicazione > disattiva \"Overlay in gioco\".",
        lambda: _exists(_pf("Electronic Arts", "EA Desktop")), procs=("igoproxy64.exe", "igoproxy.exe")),
    OverlayItem(
        "ov_ubisoft", "Overlay di Ubisoft Connect",
        "Menu Maiusc+F2 dentro i giochi Ubisoft",
        "Ubisoft Connect > menu (tre linee) > Impostazioni > Generale > disattiva \"Abilita overlay in gioco per i "
        "giochi supportati\".",
        lambda: _exists(_pf86("Ubisoft", "Ubisoft Game Launcher")), setting=ubisoft_overlay_enabled),
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
