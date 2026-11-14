"""Prova della finestra WebView2 su un Windows vero (GitHub Actions): avvia LagDoctor da sorgente con la finestra
sperimentale accesa, controlla ogni secondo se la finestra risponde, fa foto dello schermo e raccoglie i registri.
Uso: python .github/ci/finestra_test.py <cartella_risultati> [secondi]"""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.abspath(sys.argv[1])
SECONDS = int(sys.argv[2]) if len(sys.argv) > 2 else 60
DATA = os.path.join(OUT, "dati")
os.makedirs(DATA, exist_ok=True)
os.environ["LAGDOCTOR_DATA"] = DATA
with open(os.path.join(DATA, "impostazioni.json"), "w") as f:
    json.dump({"autostart": False, "minimized": True, "animations": True, "new_window": True}, f)

import psutil
from PIL import ImageGrab

u32 = ctypes.windll.user32
proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def windows():
    found = []

    def cb(h, _):
        n = u32.GetWindowTextLengthW(h)
        if u32.IsWindowVisible(h) and n:
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(h, buf, n + 1)
            if buf.value.startswith("LagDoctor"):
                pid = wintypes.DWORD()
                u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                try:
                    name = psutil.Process(pid.value).name()
                except psutil.Error:
                    name = "?"
                found.append((buf.value, pid.value, name, bool(u32.IsHungAppWindow(h))))
        return True
    u32.EnumWindows(proto(cb), 0)
    return found


log = open(os.path.join(OUT, "andamento.txt"), "w", encoding="utf-8")
console = open(os.path.join(DATA, "server-console.txt"), "w", encoding="utf-8")
srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "packaging", "lagdoctor_gui.py")], cwd=ROOT,
                       stdout=console, stderr=console)
t0 = time.time()
for i in range(SECONDS):
    time.sleep(1)
    w = windows()
    line = "%5.1fs %s" % (time.time() - t0, w or "nessuna finestra LagDoctor")
    print(line, flush=True)
    log.write(line + "\n"); log.flush()
    if i % 3 == 0 or any(x[3] for x in w):
        try:
            ImageGrab.grab().save(os.path.join(OUT, "schermo_%03d.png" % i))
        except Exception as e:
            log.write("foto non riuscita: %s\n" % e)
for p in psutil.process_iter(["pid", "cmdline"]):
    cmd = " ".join(p.info["cmdline"] or [])
    if "lagdoctor_gui.py" in cmd or "--finestra" in cmd:
        try:
            p.kill()
        except psutil.Error:
            pass
srv.kill()
print("fatto")
