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
# Minecraft Java: conta solo il processo del GIOCO, non quello del launcher (TLauncher, Legacy Launcher... sono
# anche loro Java e stanno nella cartella .minecraft). Il gioco si riconosce dagli argomenti che ogni launcher gli
# passa (--gameDir, --assetsDir, --accessToken) o dalla sua classe principale (vanilla, Fabric, Forge, Quilt...).
MC_CLIENT = ("--gamedir", "--assetsdir", "--accesstoken", "net.minecraft.client.main", "knotclient",
             "bootstraplauncher", "cpw.mods.modlauncher", "net.minecraftforge", "neoforge", "com.moonsworth",
             "lunarclient", "badlion")
MC_LAUNCHER = ("tlauncher.exe", "tlauncher.jar", "org.tlauncher", "legacylauncher", "legacy-launcher",
               "minecraft-launcher", "sklauncher", "atlauncher", "technic", "launcher.jar")


def is_minecraft_client(cmd):
    cmd = (cmd or "").lower()
    if not any(k in cmd for k in MC_CLIENT):
        return False
    # un launcher puo' avere --gamedir solo se e' lui il gioco: se manca la classe del gioco e c'e' il launcher, no
    return not (any(k in cmd for k in MC_LAUNCHER) and "--accesstoken" not in cmd and "net.minecraft" not in cmd
                and "knotclient" not in cmd and "modlauncher" not in cmd)


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
        if game.get("id") == "minecraft:java":
            return is_minecraft_client(cmd)
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


# ---------------------------------------------------------------- cartelle dei giochi (per Defender)
def too_generic(path):
    """Motivo per cui una cartella e' troppo ampia per un'esclusione di Defender, oppure None."""
    p = os.path.normcase(os.path.abspath(path)).rstrip("\\/")
    if re.match(r"^[a-z]:$", p, re.I) or re.match(r"^\\\\[^\\]+\\[^\\]+$", p) or p in ("", os.sep):
        return "e' un disco intero"
    env = os.environ.get
    sysroot = os.path.normcase(os.path.abspath(env("SystemRoot") or r"C:\Windows")).rstrip("\\/")
    risky = [env("SystemRoot"), env("ProgramFiles"), env("ProgramFiles(x86)"), env("ProgramW6432"),
             env("ProgramData"), env("USERPROFILE"), env("APPDATA"), env("LOCALAPPDATA"), env("TEMP"),
             os.path.join(os.path.splitdrive(env("SystemRoot") or "C:")[0] + os.sep, "Users")]
    for r in filter(None, risky):
        r = os.path.normcase(os.path.abspath(r)).rstrip("\\/")
        if p == r:
            return "e' una cartella di sistema (%s)" % r
    if p.startswith(sysroot + os.sep):
        return "e' dentro la cartella di Windows"
    return None


# ---------------------------------------------------------------- ricerca su tutti i dischi (giochi senza launcher)
# File che si trovano quasi solo nella cartella principale di un gioco (motori e SDK per giochi)
# Motore Unity: bastano da soli
GAME_ENGINE_FILES = {"unityplayer.dll", "gameassembly.dll"}
# SDK per giochi: contano solo se nella cartella ci sono anche un .exe e i dati di un gioco (archivi o cartelle
# tipiche). Da soli si trovano anche in strumenti ed emulatori (Goldberg, Nemirtingas, bypass, Nucleus Co-op...).
# Le DLL di DLSS / FSR / XeSS non contano: le hanno anche le mod di upscaling come OptiScaler.
GAME_SDK_FILES = {"steam_api64.dll", "steam_api.dll", "eossdk-win64-shipping.dll", "galaxy64.dll", "bink2w64.dll",
                  "binkw64.dll", "fmod.dll", "fmodstudio.dll", "physx3_x64.dll", "physx_64.dll",
                  "discord_game_sdk.dll", "uplay_r1_loader64.dll", "upc_r2_loader64.dll", "easyanticheat_x64.dll",
                  "beclient_x64.dll"}
GAME_DATA_EXT = (".pak", ".pck", ".arc", ".rpf", ".forge", ".bundle", ".assets", ".wad", ".vpk", ".big", ".bnk",
                 ".wem", ".bik", ".bk2", ".archive", ".cpk", ".bdt", ".ucas", ".utoc", ".gpk", ".upk", ".rgssad",
                 ".ba2", ".bsa", ".esm", ".tfc", ".xnb", ".vfs", ".nxa")
GAME_DATA_DIRS = {"data", "content", "assets", "paks", "resources", "packs", "archive", "base", "movies", "sound",
                  "audio", "maps", "levels", "videos", "bin", "binaries", "game", "localization", "shaders"}
# launcher, client e strumenti: non sono giochi (nome della cartella o di una cartella che la contiene)
NOT_GAME_DIR = re.compile(r"launcher|^galaxy|gog galaxy|battle\.net|ea desktop|^origin$|riot client|"
                          r"ubisoft connect|^uplay$|optiscaler|reshade|special ?k|goldberg|\bemu\b|emu$|"
                          r"bypass|trainer|cheat ?engine|nucleus|^utils?$|^tools?$|^redist", re.I)
# cartelle da non visitare (sistema, programmi che non sono giochi, dati)
SCAN_SKIP = re.compile(r"^(windows|\$.*|system volume information|recovery|perflogs|config\.msi|programdata|"
                       r"msocache|intel|amd|nvidia|drivers|windowsapps|common files|microsoft.*|windows .*|"
                       r"internet explorer|reference assemblies|dotnet|modifiablewindowsapps|appdata|"
                       r"node_modules|\..*|__pycache__|site-packages|python\d*|java|jdk.*|jre.*|android|"
                       r"onedrive|dropbox|google drive|icloud.*|steamapps|steam)$", re.I)
# nome di una cartella che raccoglie giochi (si propone lei invece del singolo gioco)
# (non i nomi dei client come "GOG Galaxy": li' dentro ci sono il programma e i suoi file, non i giochi)
GAME_LIB = re.compile(r"games?|giochi|gioco|gaming|juegos|spiele|jeux|steamlibrary|xboxgames|emulat|roms", re.I)

_SCAN_CACHE = {"t": 0, "data": None}


def _fixed_drives():
    """Dischi fissi (interni e SSD/HDD esterni sempre collegati): niente lettori, chiavette o dischi di rete."""
    if os.name != "nt":
        return []
    import ctypes
    import string
    out = []
    for d in string.ascii_uppercase:
        root = d + ":\\"
        try:
            if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) == 3:  # DRIVE_FIXED
                out.append(root)
        except Exception:
            pass
    return out


def _looks_like_game(path, real_names):
    """real_names: nomi (come sono sul disco) dentro la cartella."""
    names = {n.lower() for n in real_names}
    if GAME_ENGINE_FILES & names:
        return True
    if GAME_SDK_FILES & names and any(n.endswith(".exe") for n in names):
        if any(n.endswith(GAME_DATA_EXT) for n in names) or GAME_DATA_DIRS & names:
            return True
    # Unreal Engine: <gioco>\Engine + <gioco>\<Progetto>\Binaries\Win64
    if "engine" in names:
        for n in real_names:
            if n.lower() != "engine" and os.path.isdir(os.path.join(path, n, "Binaries", "Win64")):
                return True
    return False


def scan_drives(max_depth=4, budget_s=12.0, roots=None):
    """Cerca le cartelle dei giochi su TUTTI i dischi fissi, anche giochi senza launcher (copiati, installati a
    mano, emulatori...). Riconosce un gioco dai file tipici dei motori (Unity, Unreal) e degli SDK per giochi.
    Non entra nelle cartelle di sistema e si ferma dopo budget_s secondi."""
    import time
    t0 = time.time()
    found = []
    stack = [(r, 0) for r in reversed(roots if roots is not None else _fixed_drives())]
    while stack:
        if time.time() - t0 > budget_s:
            break
        path, depth = stack.pop()
        try:
            with os.scandir(path) as it:
                entries = list(it)
        except OSError:
            continue
        if depth > 0 and NOT_GAME_DIR.search(os.path.basename(path)):
            continue  # launcher o strumento: ne' lui ne' le sue sottocartelle
        if depth > 0 and _looks_like_game(path, [e.name for e in entries]):
            found.append(dict(id=_id("disco", path), name=os.path.basename(path), source="disco", dir=path,
                              match="dir"))
            continue  # niente sottocartelle: e' gia' un gioco
        if depth >= max_depth:
            continue
        for e in sorted(entries, key=lambda e: e.name.lower(), reverse=True):
            try:
                if e.is_dir(follow_symlinks=False) and not SCAN_SKIP.match(e.name):
                    stack.append((e.path, depth + 1))
            except OSError:
                pass
    return found


def scan_drives_cached(max_age=600):
    import time
    if _SCAN_CACHE["data"] is None or time.time() - _SCAN_CACHE["t"] > max_age:
        _SCAN_CACHE.update(t=time.time(), data=scan_drives())
    return _SCAN_CACHE["data"]


def all_game_dirs(scan=True):
    """Giochi dei launcher + giochi trovati sui dischi (senza doppioni, ne' giochi dentro altri giochi)."""
    games = [g for g in detect() if g.get("dir") and not NOT_GAME_DIR.search(os.path.basename(os.path.normpath(g["dir"])))
             and not (g.get("source") == "xbox" and NOT_GAME_DIR.search(g.get("name") or ""))]
    if scan:
        known = [os.path.normcase(g["dir"]) for g in games]
        for g in scan_drives_cached():
            d = os.path.normcase(g["dir"])
            if not any(d == k or d.startswith(k + os.sep) or k.startswith(d + os.sep) for k in known):
                games.append(g)
                known.append(d)
    return games


def _root_for(g):
    """Cartella "libreria" che contiene il gioco: steamapps\\common, XboxGames, la cartella del launcher
    (es. E:\\Epic Games), oppure la cartella del gioco se quella sopra e' troppo ampia (es. Programmi)."""
    d = os.path.normpath(g["dir"])
    low = os.path.normcase(d)
    i = low.find(os.path.normcase(os.path.join("steamapps", "common")) + os.sep)
    if i >= 0:
        return d[:i + len(os.path.join("steamapps", "common"))]
    i = low.find(os.sep + "xboxgames" + os.sep)
    if i >= 0:
        return d[:i + len(os.sep + "XboxGames")]
    parent = os.path.dirname(d)
    if not parent or parent == d or too_generic(parent) or not GAME_LIB.search(os.path.basename(parent)):
        return d  # es. D:\\Download\\Gioco: escludo solo il gioco, non tutta la cartella Download
    return parent


def library_folders(found=None):
    """Le cartelle da proporre per l'esclusione da Defender: una per libreria di giochi, su tutti i dischi.
    Lista di dict: path, drive, games (nomi), sources (launcher o "disco")."""
    roots = {}
    for g in (found if found is not None else all_game_dirs()):
        if not g.get("dir"):
            continue
        r = _root_for(g)
        if too_generic(r):
            continue
        e = roots.setdefault(os.path.normcase(r), {"path": r, "games": [], "sources": []})
        e["games"].append(g["name"])
        e["sources"].append(g.get("source") or "")
    # tolgo le cartelle gia' contenute in un'altra proposta
    keys = sorted(roots, key=len)
    keep = []
    for k in keys:
        parent = next((p for p in keep if k.startswith(p + os.sep)), None)
        if parent:
            roots[parent]["games"] += roots[k]["games"]
            roots[parent]["sources"] += roots[k]["sources"]
        else:
            keep.append(k)
    out = [dict(roots[k], drive=os.path.splitdrive(roots[k]["path"])[0].upper()) for k in keep]
    for o in out:
        o["games"] = sorted(set(o["games"]), key=str.lower)
        o["sources"] = sorted(set(o["sources"]) - {""})
    return sorted(out, key=lambda o: o["path"].lower())
