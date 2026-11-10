"""Correzioni automatiche. Sono tutte sicure e reversibili; ogni modifica viene salvata nel backup."""
import json
import os
import datetime

import psutil

try:
    import winreg
except ImportError:
    winreg = None

DESCRIPTIONS = {
    "disable_game_dvr": "Disattivare la registrazione in background di Xbox Game Bar",
    "enable_game_mode": "Attivare la Modalita' Gioco di Windows",
    "close_processes": "Chiudere i programmi in background: {arg}",
    "set_refresh": "Impostare lo schermo alla frequenza massima: {arg}",
}

TWEAK_MAP = {"disable_game_dvr": "game_dvr", "enable_game_mode": "game_mode"}

# vecchio formato (versioni precedenti), usato solo per annullare backup esistenti
REG_VALUES = {
    "disable_game_dvr": [
        (r"System\GameConfigStore", "GameDVR_Enabled", 0),
        (r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0),
    ],
    "enable_game_mode": [
        (r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1),
        (r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1),
    ],
}


def describe(fix):
    name, arg = fix
    if name == "set_refresh":
        return DESCRIPTIONS[name].format(arg="%s a %d Hz" % (arg[0].replace("\\\\.\\", ""), arg[1]))
    return DESCRIPTIONS[name].format(arg=", ".join(arg) if isinstance(arg, list) else arg)


def _backup(backup_file, entry):
    data = []
    if os.path.exists(backup_file):
        try:
            with open(backup_file, encoding="utf-8") as f:
                data = json.load(f)
        except ValueError:
            data = []
    entry["data"] = datetime.datetime.now().isoformat(timespec="seconds")
    data.append(entry)
    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _set_reg(values, backup_file, fix_name):
    old = []
    for path, name, val in values:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
            try:
                prev = winreg.QueryValueEx(k, name)[0]
            except OSError:
                prev = None
            old.append([path, name, prev])
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)
    _backup(backup_file, {"fix": fix_name, "registro_HKCU_valori_precedenti": old})


def apply(fix, backup_file):
    name, arg = fix
    if name in TWEAK_MAP:
        from . import tweaks
        return "Fatto: " + tweaks.apply_one(TWEAK_MAP[name])
    if name == "set_refresh":
        from . import scan
        device, hz = arg
        return ("Fatto: ora lo schermo va a %d Hz." % hz) if scan.set_refresh(device, hz) else \
            "Windows non ha accettato la frequenza: impostala da Impostazioni > Schermo > Schermo avanzato."
    if name == "close_processes":
        targets = {a.lower() for a in arg}
        closed = []
        for p in psutil.process_iter(["name"]):
            if (p.info["name"] or "").lower() in targets:
                try:
                    p.terminate()
                    closed.append(p.info["name"])
                except psutil.Error:
                    pass
        return "Chiusi: " + (", ".join(sorted(set(closed))) or "nessuno (forse erano gia' chiusi)")
    return "Correzione sconosciuta."


def undo_all(backup_file):
    """Ripristina i valori del registro salvati nel backup."""
    if not os.path.exists(backup_file):
        return "Nessun backup trovato: non c'e' niente da ripristinare."
    with open(backup_file, encoding="utf-8") as f:
        data = json.load(f)
    for entry in reversed(data):
        for path, name, prev in entry.get("registro_HKCU_valori_precedenti", []):
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_WRITE) as k:
                if prev is None:
                    try:
                        winreg.DeleteValue(k, name)
                    except OSError:
                        pass
                else:
                    winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, prev)
    os.replace(backup_file, backup_file + ".ripristinato")
    return "Impostazioni originali ripristinate."
