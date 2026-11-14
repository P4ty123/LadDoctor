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


class RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


def hwnd_of(pid):
    out = []

    def cb(h, _):
        p = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        n = u32.GetWindowTextLengthW(h)
        if p.value == pid and u32.IsWindowVisible(h) and n:
            out.append(h)
        return True
    u32.EnumWindows(proto(cb), 0)
    return out[0] if out else None


def rect(h):
    r = RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    return (r.l, r.t, r.r - r.l, r.b - r.t)


def look(h):
    """Contenuto della finestra: luminosita' media e % di pixel chiari (testo, pulsanti). Tutta nera = ~0%."""
    x, y, w, hh = rect(h)
    img = ImageGrab.grab(bbox=(x, y, x + w, y + hh)).convert("L")
    px = list(img.getdata())
    bright = sum(1 for v in px if v > 110) * 100.0 / max(len(px), 1)
    return "luminosita' media %.1f, pixel chiari %.2f%%" % (sum(px) / max(len(px), 1), bright)


def click(x, y):
    u32.SetCursorPos(int(x), int(y)); time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.08); u32.mouse_event(0x0004, 0, 0, 0, 0)


def drag(x, y, dx, dy):
    u32.SetCursorPos(int(x), int(y)); time.sleep(0.2)
    u32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.15)
    for i in range(1, 16):
        u32.SetCursorPos(int(x + dx * i / 15), int(y + dy * i / 15)); time.sleep(0.04)
    time.sleep(0.2); u32.mouse_event(0x0004, 0, 0, 0, 0)


log = open(os.path.join(OUT, "andamento.txt"), "w", encoding="utf-8")
console = open(os.path.join(DATA, "server-console.txt"), "w", encoding="utf-8")
srv = subprocess.Popen([sys.executable, os.path.join(ROOT, "packaging", "lagdoctor_gui.py")], cwd=ROOT,
                       stdout=console, stderr=console)
t0 = time.time()
tested = False
for i in range(SECONDS):
    time.sleep(1)
    w = windows()
    line = "%5.1fs %s" % (time.time() - t0, w or "nessuna finestra LagDoctor")
    print(line, flush=True)
    log.write(line + "\n"); log.flush()
    wv = [x for x in w if x[2].lower() in ("pythonw.exe", "python.exe")]
    if wv and i % 3 == 0:
        h = hwnd_of(wv[0][1])
        if h:
            line = "%5.1fs   aspetto: %s" % (time.time() - t0, look(h))
            print(line, flush=True); log.write(line + "\n")
    if wv and not tested and time.time() - t0 > 12:
        tested = True
        h = hwnd_of(wv[0][1])
        if h:
            def step(name, fn):
                before = rect(h)
                fn()
                time.sleep(1.5)
                after = rect(h)
                ok = not u32.IsHungAppWindow(h)
                line = "PROVA %-28s prima %s dopo %s | risponde: %s" % (name, before, after, ok)
                print(line, flush=True); log.write(line + "\n")
            x, y, ww, hh = rect(h)
            step("trascina la barra", lambda: drag(x + 700, y + 18, 120, 60))
            x, y, ww, hh = rect(h)
            step("ridimensiona bordo sinistro", lambda: drag(x + 2, y + hh // 2, 200, 0))
            x, y, ww, hh = rect(h)
            step("riporta in alto a sinistra", lambda: drag(x + 400, y + 18, 20 - x, 20 - y))
            x, y, ww, hh = rect(h)
            step("ingrandisci (tasto)", lambda: click(x + ww - 69, y + 19))
            x, y, ww, hh = rect(h)
            step("ripristina (tasto)", lambda: click(x + ww - 69, y + 19))
            x, y, ww, hh = rect(h)
            step("ridimensiona bordo destro", lambda: drag(x + ww - 2, y + hh // 2, 80, 0))
            x, y, ww, hh = rect(h)
            step("ridimensiona bordo in alto", lambda: drag(x + ww // 2, y + 1, 0, 140))
            x, y, ww, hh = rect(h)
            step("porta in alto (sopra la barra)", lambda: drag(x + 400, y + 18, 0, -y))
            x, y, ww, hh = rect(h)
            step("ridimensiona bordo in basso", lambda: drag(x + ww // 2, y + hh - 2, 0, 60))
            x, y, ww, hh = rect(h)
            step("ridimensiona angolo", lambda: drag(x + ww - 3, y + hh - 3, -40, -30))
            x, y, ww, hh = rect(h)
            step("doppio clic sulla barra", lambda: (click(x + 700, y + 18), time.sleep(0.05), click(x + 700, y + 18)))
            x, y, ww, hh = rect(h)
            step("doppio clic di nuovo", lambda: (click(x + 700, y + 18), time.sleep(0.05), click(x + 700, y + 18)))
            ImageGrab.grab().save(os.path.join(OUT, "dopo_prove.png"))
    if i % 3 == 0 or any(x[3] for x in w):
        try:
            ImageGrab.grab().save(os.path.join(OUT, "schermo_%03d.png" % i))
        except Exception as e:
            log.write("foto non riuscita: %s\n" % e)
for p in psutil.process_iter(["pid", "cmdline"]):
    cmd = " ".join(p.info["cmdline"] or [])
    if "lagdoctor_gui.py" in cmd or "--finestra" in cmd or DATA.lower() in cmd.lower():
        try:
            p.kill()
        except psutil.Error:
            pass
srv.kill()
time.sleep(2)
for name in ("errore-finestra.txt", "finestra-console.txt", "errore.txt", "server-console.txt"):
    p = os.path.join(DATA, name)
    if os.path.isfile(p):
        print("\n========== %s ==========" % name)
        print(open(p, encoding="utf-8", errors="replace").read()[-20000:])
print("fatto")
