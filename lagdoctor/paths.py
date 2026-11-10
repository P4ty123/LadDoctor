"""Dove stanno i file di LagDoctor.

- Programma (sola lettura): la cartella installata (LagDoctor.exe) oppure la cartella sorgente (AVVIA.bat).
- Dati (backup delle modifiche, report, configurazione della game mode...): C:\\ProgramData\\LagDoctor.
  Restano li' anche quando il programma viene aggiornato o reinstallato, cosi' le modifiche si possono sempre
  annullare. La versione installata e quella avviata con AVVIA.bat usano gli stessi dati.
"""
import os
import shutil
import sys

FROZEN = bool(getattr(sys, "frozen", False))  # True nella versione installata (LagDoctor.exe)
SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.dirname(sys.executable) if FROZEN else SRC_ROOT       # dove sono gli eseguibili
RES_DIR = getattr(sys, "_MEIPASS", SRC_ROOT) if FROZEN else SRC_ROOT    # risorse incluse (strumenti, ui)
TOOLS = os.path.join(RES_DIR, "strumenti")                              # PresentMon


def _data_dir():
    if os.environ.get("LAGDOCTOR_DATA"):
        return os.environ["LAGDOCTOR_DATA"]
    if os.name == "nt":
        return os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "LagDoctor")
    return SRC_ROOT


DATA_DIR = _data_dir()
REPORTS = os.path.join(DATA_DIR, "report")
DATA_TOOLS = os.path.join(DATA_DIR, "strumenti")  # file creati dal programma (profilo della finestra, script)

# file di dati che le versioni precedenti tenevano nella cartella del programma
_OLD_FILES = ["modifiche_applicate.json", "backup_impostazioni.json", "riavvio_necessario.json", "hardware.json",
              "gamemode.json", "gamemode_attiva.json", "gamemode_priorita_windows.json", "gamemode_stato.json",
              "esperimento_in_corso.json"]


def data(name):
    return os.path.join(DATA_DIR, name)


def find_old_folders(max_depth=3):
    """Cartelle della vecchia versione (avviata con AVVIA.bat) con dati da recuperare: Desktop, Download, Documenti."""
    home = os.path.expanduser("~")
    starts = [os.path.join(home, d) for d in ("Desktop", "Downloads", "Documents", "Documenti")]
    starts += [os.path.join(home, "OneDrive", d) for d in ("Desktop", "Documents", "Documenti")]
    found = []
    for start in starts:
        if not os.path.isdir(start):
            continue
        base = start.rstrip("\\/").count(os.sep)
        for root, dirs, files in os.walk(start):
            if root.count(os.sep) - base >= max_depth:
                dirs[:] = []
            if "AVVIA.bat" in files and os.path.isdir(os.path.join(root, "lagdoctor")) and \
                    any(n in files for n in _OLD_FILES):
                found.append(root)
                dirs[:] = []
    # la piu' recente per prima
    found.sort(key=lambda d: max(os.path.getmtime(os.path.join(d, n)) for n in _OLD_FILES
                                 if os.path.isfile(os.path.join(d, n))), reverse=True)
    return found


def migrate():
    """Prima volta: copia i dati della vecchia versione nella cartella dati.
    Avvio con AVVIA.bat: dalla cartella del programma. Versione installata: dalla vecchia cartella trovata su
    Desktop / Download / Documenti. Copia e non sposta: i vecchi file restano dove sono, per sicurezza."""
    os.makedirs(DATA_DIR, exist_ok=True)
    marker = data(".migrato")
    if os.path.exists(marker):
        return False
    if FROZEN:
        if os.path.exists(data("modifiche_applicate.json")):
            return False
        try:
            old = find_old_folders()
        except OSError:
            old = []
        if not old:
            return False
        src_root = old[0]
    elif os.path.normcase(DATA_DIR) == os.path.normcase(SRC_ROOT):
        return False
    else:
        src_root = SRC_ROOT
    copied = False
    for n in _OLD_FILES:
        src = os.path.join(src_root, n)
        if os.path.isfile(src) and not os.path.exists(data(n)):
            shutil.copy2(src, data(n))
            copied = True
    old_rep = os.path.join(src_root, "report")
    if os.path.isdir(old_rep):
        os.makedirs(REPORTS, exist_ok=True)
        for n in os.listdir(old_rep):
            s, d = os.path.join(old_rep, n), os.path.join(REPORTS, n)
            if os.path.isfile(s) and not os.path.exists(d):
                shutil.copy2(s, d)
                copied = True
    with open(marker, "w") as f:
        f.write("dati copiati da " + src_root)
    return copied


def gui_cmd(*args):
    """Comando per avviare LagDoctor in una modalita' senza finestra (game mode, timer)."""
    if FROZEN:
        return [os.path.join(APP_DIR, "LagDoctor.exe")] + list(args)
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.isfile(pyw) else sys.executable
    return [exe, os.path.join(SRC_ROOT, "packaging", "lagdoctor_gui.py")] + list(args)


def helper_cmd(*args):
    """Comando per l'eseguibile di supporto con console (sonda di latenza, autodiagnosi)."""
    if FROZEN:
        return [os.path.join(APP_DIR, "LagDoctorHelper.exe")] + list(args)
    return [sys.executable, os.path.join(SRC_ROOT, "packaging", "lagdoctor_helper.py")] + list(args)


def quote(cmd):
    """Lista -> riga di comando per schtasks."""
    return " ".join('"%s"' % c if (" " in c or not c.startswith("-")) else c for c in cmd)
