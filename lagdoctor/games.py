"""Trova i giochi installati sul PC (Steam, Epic, GOG, Xbox/Game Pass, Ubisoft, EA, Battle.net, Riot, Rockstar,
Minecraft Java e Bedrock) e riconosce i loro processi quando partono.

Ogni gioco e' un dict:
  id, name, source, dir (cartella di installazione), match:
    "dir"  = qualsiasi .exe dentro la cartella del gioco (gestisce giochi con piu' eseguibili)
    "java" = java.exe/javaw.exe con una parola chiave nella riga di comando (Minecraft Java e simili)
    "name" = nome esatto dell'eseguibile
"""
import glob
import ntpath
import json
import os
import re

try:
    import winreg
except ImportError:
    winreg = None

# eseguibili dentro la cartella del gioco che NON sono il gioco
NOT_GAME_EXE = re.compile(r"crash|unins|setup|redist|vc_?redist|dxsetup|directx|easyanticheat|beservice|battleye|"
                          r"eac_launcher|reporter|report|updater|update|webhelper|cefprocess|helper|"
                          r"prereq|install|dotnet|vcrun|physx|oalinst|ue4prereq|benchmark", re.I)
STEAM_SKIP = re.compile(r"redistributable|steamworks|proton|steam linux runtime|dedicated server|sdk|"
                        r"soundtrack|wallpaper engine", re.I)


def _reg(root, path, name):
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def _subkeys(root, path):
    out = []
    if winreg is None:
        return out
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(k, i))
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return out


def _id(source, key):
    return (source + ":" + re.sub(r"[^a-z0-9]+", "-", str(key).lower())).strip("-")


def _game(source, key, name, path, match="dir", **kw):
    if not name or not path:
        return None
    path = os.path.normpath(path)
    if match == "dir" and not os.path.isdir(path):
        return None
    return dict(id=_id(source, key), name=name.strip(), source=source, dir=path, match=match, **kw)


# ---------------------------------------------------------------- Steam
def _vdf_values(text, key):
    return re.findall(r'"%s"\s+"([^"]*)"' % re.escape(key), text, re.I)


def steam():
    games = []
    base = None
    if winreg is not None:
        base = (_reg(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath") or
                _reg(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"))
    if not base:
        return games
    libs = {os.path.normpath(base)}
    try:
        with open(os.path.join(base, "steamapps", "libraryfolders.vdf"), encoding="utf-8", errors="ignore") as f:
            for p in _vdf_values(f.read(), "path"):
                libs.add(os.path.normpath(p.replace("\\\\", "\\")))
    except OSError:
        pass
    for lib in libs:
        for acf in glob.glob(os.path.join(lib, "steamapps", "appmanifest_*.acf")):
            try:
                with open(acf, encoding="utf-8", errors="ignore") as f:
                    t = f.read()
            except OSError:
                continue
            name = (_vdf_values(t, "name") or [""])[0]
            inst = (_vdf_values(t, "installdir") or [""])[0]
            appid = (_vdf_values(t, "appid") or [""])[0]
            if not name or not inst or STEAM_SKIP.search(name) or appid == "228980":
                continue
            g = _game("steam", appid, name, os.path.join(lib, "steamapps", "common", inst))
            if g:
                games.append(g)
    return games


# ---------------------------------------------------------------- Epic Games
def epic():
    games = []
    pd = os.environ.get("ProgramData", r"C:\ProgramData")
    for item in glob.glob(os.path.join(pd, "Epic", "EpicGamesLauncher", "Data", "Manifests", "*.item")):
        try:
            with open(item, encoding="utf-8", errors="ignore") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        cats = [c.lower() for c in d.get("AppCategories") or []]
        if cats and "games" not in cats:
            continue
        g = _game("epic", d.get("AppName") or d.get("DisplayName"), d.get("DisplayName"), d.get("InstallLocation"))
        if g:
            games.append(g)
    return games


# ---------------------------------------------------------------- GOG
def gog():
    games = []
    if winreg is None:
        return games
    base = r"SOFTWARE\WOW6432Node\GOG.com\Games"
    for k in _subkeys(winreg.HKEY_LOCAL_MACHINE, base):
        p = base + "\\" + k
        g = _game("gog", k, _reg(winreg.HKEY_LOCAL_MACHINE, p, "gameName"), _reg(winreg.HKEY_LOCAL_MACHINE, p, "path"))
        if g:
            games.append(g)
    return games


# ---------------------------------------------------------------- Ubisoft
def ubisoft():
    games = []
    if winreg is None:
        return games
    base = r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"
    for k in _subkeys(winreg.HKEY_LOCAL_MACHINE, base):
        d = _reg(winreg.HKEY_LOCAL_MACHINE, base + "\\" + k, "InstallDir")
        if d:
            g = _game("ubisoft", k, os.path.basename(os.path.normpath(d)), d)
            if g:
                games.append(g)
    return games


# ---------------------------------------------------------------- Xbox / Game Pass (cartelle XboxGames)
def _drives():
    if os.name != "nt":
        return ["/"]
    import string
    return [d + ":\\" for d in string.ascii_uppercase if os.path.isdir(d + ":\\")]


def xbox():
    games = []
    for drv in _drives():
        for cfg in glob.glob(os.path.join(drv, "XboxGames", "*", "Content", "MicrosoftGame.config")):
            content = os.path.dirname(cfg)
            name = os.path.basename(os.path.dirname(content))
            try:
                with open(cfg, encoding="utf-8", errors="ignore") as f:
                    m = re.search(r'DefaultDisplayName="([^"]+)"', f.read())
                if m and not m.group(1).startswith("ms-resource"):
                    name = m.group(1)
            except OSError:
                pass
            g = _game("xbox", name, name, content)
            if g:
                games.append(g)
    return games


# ---------------------------------------------------------------- programmi installati (EA, Battle.net, Riot, Rockstar)
PUBLISHERS = re.compile(r"electronic arts|blizzard|riot games|rockstar games|bethesda|square enix|bandai|"
                        r"capcom|cd projekt|2k|activision|sega|warner bros|focus|giants software|paradox|"
                        r"techland|mojang|hoyoverse|cognosphere|nexon|wargaming|embark", re.I)
LAUNCHERS = re.compile(r"\b(launcher|app|client|desktop|battle\.net|ea app|origin|riot client|social club)\s*$", re.I)


def installed_programs():
    games = []
    if winreg is None:
        return games
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for base in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
            for k in _subkeys(root, base):
                p = base + "\\" + k
                pub = _reg(root, p, "Publisher") or ""
                name = _reg(root, p, "DisplayName") or ""
                loc = _reg(root, p, "InstallLocation") or ""
                if not loc or not PUBLISHERS.search(pub) or LAUNCHERS.search(name):
                    continue
                if re.search(r"redistributable|runtime|anti-?cheat|vanguard|update", name, re.I):
                    continue
                g = _game("pc", k, name, loc.strip('"'))
                if g:
                    games.append(g)
    return games


# ---------------------------------------------------------------- Minecraft
def minecraft():
    games = []
    appdata = os.environ.get("APPDATA", "")
    launchers = [os.path.join(appdata, ".minecraft"), os.path.join(appdata, "PrismLauncher"),
                 os.path.join(appdata, "MultiMC"), os.path.join(os.environ.get("USERPROFILE", ""), "curseforge"),
                 os.path.join(appdata, ".lunarclient"), os.path.join(appdata, ".tlauncher")]
    if any(os.path.isdir(p) for p in launchers):
        games.append(dict(id="minecraft:java", name="Minecraft Java Edition", source="java", dir="", match="java",
                          keywords=["minecraft", "net.minecraft", "lunar", "badlion", "prismlauncher", "multimc",
                                    "fabric", "forge", "quilt"]))
    games.append(dict(id="minecraft:bedrock", name="Minecraft (Bedrock / Windows)", source="xbox", dir="",
                      match="name", exe_names=["minecraft.windows.exe"], optional=True))
    return games


def detect():
    """Tutti i giochi trovati, senza doppioni (stessa cartella)."""
    found, seen = [], set()
    for fn in (steam, epic, gog, xbox, ubisoft, installed_programs, minecraft):
        try:
            items = fn()
        except Exception:
            items = []
        for g in items:
            key = g["dir"].lower() if g["dir"] else g["id"]
            if key in seen:
                continue
            seen.add(key)
            found.append(g)
    found.sort(key=lambda g: g["name"].lower())
    return found


def manual(exe_path):
    """Gioco aggiunto a mano: la cartella dell'eseguibile (o l'eseguibile stesso se e' in una cartella comune)."""
    exe_path = ntpath.normpath(exe_path)
    d = ntpath.dirname(exe_path)
    name = ntpath.splitext(ntpath.basename(exe_path))[0]
    generic = re.search(r"\\(windows|system32|program files( \(x86\))?|users\\[^\\]+)$", d, re.I)
    if ntpath.basename(exe_path).lower() in ("java.exe", "javaw.exe"):
        return dict(id=_id("manual", "java"), name="Gioco Java", source="manuale", dir="", match="java",
                    keywords=["minecraft"])
    if generic:
        return dict(id=_id("manual", name), name=name, source="manuale", dir="", match="name",
                    exe_names=[ntpath.basename(exe_path).lower()])
    return dict(id=_id("manual", d), name=name, source="manuale", dir=d, match="dir")


# ---------------------------------------------------------------- riconoscimento dei processi
def matches(game, name, exe, cmdline_fn):
    """name/exe del processo; cmdline_fn() restituisce la riga di comando (chiamata solo se serve)."""
    name = (name or "").lower()
    m = game.get("match")
    if m == "dir":
        if not exe or not game.get("dir"):
            return False
        d = os.path.normcase(os.path.normpath(game["dir"])).rstrip("\\/") + os.sep
        return os.path.normcase(os.path.normpath(exe)).lower().startswith(d.lower()) and not NOT_GAME_EXE.search(name)
    if m == "name":
        return name in [n.lower() for n in game.get("exe_names") or []]
    if m == "java":
        if name not in ("java.exe", "javaw.exe"):
            return False
        cmd = (cmdline_fn() or "").lower()
        return any(k in cmd for k in game.get("keywords") or [])
    return False


# ---------------------------------------------------------------- anti-cheat
# (nome, file/cartelle nella cartella del gioco, processi che girano col gioco, parole nel percorso del gioco)
# Sono tutti anti-cheat a livello kernel che PROTEGGONO il processo del gioco: aprirlo per cambiare priorita' o
# affinita' viene bloccato e, in teoria, potrebbe essere segnalato. VAC di Steam non protegge il processo: non e' qui.
ANTICHEATS = [
    ("Easy Anti-Cheat", ["easyanticheat", "start_protected_game.exe", "easyanticheat_eos_setup.exe"],
     ["easyanticheat.exe", "easyanticheat_eos.exe"], []),
    ("BattlEye", ["battleye", "beservice.exe", "beservice_x64.exe"], ["beservice.exe", "beservice_x64.exe"], []),
    ("Riot Vanguard", [], ["vgc.exe"], ["riot games"]),
    ("EA Javelin", ["eaanticheat.installer.exe", "eaanticheat.gameservicelauncher.exe"],
     ["eaanticheat.gameservice.exe"], []),
    ("Ricochet (Call of Duty)", ["randgrid.sys"], [], ["call of duty"]),
    ("nProtect GameGuard", ["gameguard"], ["gamemon.des", "gamemon64.des"], []),
    ("XIGNCODE3", ["xigncode", "x3.xem"], ["xxd-0.xem"], []),
    ("ACE (Tencent)", ["anticheatexpert", "ace-base"], ["sguard64.exe", "ace-tray.exe"], []),
    ("HoYoverse (mhyprot)", ["mhypbase.dll"], [], []),
    ("FACEIT", [], ["faceit.exe", "faceitservice.exe"], []),
    ("Denuvo Anti-Cheat", ["denuvo-anti-cheat", "denuvo anti-cheat"], [], []),
]


def anticheat_in_dir(path, depth=4):
    """Nome dell'anti-cheat trovato nella cartella del gioco (o None)."""
    if not path or not os.path.isdir(path):
        return None
    low = path.lower()
    for name, files, _procs, words in ANTICHEATS:
        if any(w in low for w in words):
            return name
    base = len(path.rstrip("\\/").split(os.sep))
    names = set()
    for root, dirs, fs in os.walk(path):
        names.update(x.lower() for x in dirs + fs)
        if len(root.rstrip("\\/").split(os.sep)) - base >= depth:
            dirs[:] = []
        if len(names) > 20000:
            break
    for name, files, _procs, _words in ANTICHEATS:
        if any(f in names for f in files):
            return name
    return None


def anticheat_running(proc_names):
    """Anti-cheat attivo in questo momento (dai nomi dei processi aperti)."""
    s = {n.lower() for n in proc_names if n}
    for name, _files, procs, _words in ANTICHEATS:
        if any(p in s for p in procs):
            return name
    return None
