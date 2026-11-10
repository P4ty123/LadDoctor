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


def migrate():
    """Prima volta: copia i dati della vecchia versione (cartella del programma) nella cartella dati.
    Copia e non sposta: i vecchi file restano dove sono, per sicurezza."""
    os.makedirs(DATA_DIR, exist_ok=True)
    marker = data(".migrato")
    if os.path.normcase(DATA_DIR) == os.path.normcase(SRC_ROOT) or os.path.exists(marker) or FROZEN:
        return False
    copied = False
    for n in _OLD_FILES:
        src = os.path.join(SRC_ROOT, n)
        if os.path.isfile(src) and not os.path.exists(data(n)):
            shutil.copy2(src, data(n))
            copied = True
    old_rep = os.path.join(SRC_ROOT, "report")
    if os.path.isdir(old_rep):
        os.makedirs(REPORTS, exist_ok=True)
        for n in os.listdir(old_rep):
            s, d = os.path.join(old_rep, n), os.path.join(REPORTS, n)
            if os.path.isfile(s) and not os.path.exists(d):
                shutil.copy2(s, d)
                copied = True
    with open(marker, "w") as f:
        f.write("dati copiati da " + SRC_ROOT)
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
