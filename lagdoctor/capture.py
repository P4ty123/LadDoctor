"""Registrazione: PresentMon (frame time) + monitor di sistema (CPU, RAM, disco, GPU)."""
import os
import subprocess
import threading
import time
import urllib.request

import psutil

from . import gpu as gpumod

PRESENTMON_VERSION = "2.4.1"
PRESENTMON_URL = ("https://github.com/GameTechDev/PresentMon/releases/download/v{0}/PresentMon-{0}-x64.exe"
                  .format(PRESENTMON_VERSION))
CREATE_NO_WINDOW = 0x08000000

IGNORE_PROCS = {"system idle process", "system", "idle", "presentmon", "nvidia-smi.exe", "typeperf.exe", "python.exe",
                "pythonw.exe", "py.exe", "conhost.exe", "windowsterminal.exe", "openconsole.exe", "cmd.exe"}


PRESENTMON_PAGE = "https://github.com/GameTechDev/PresentMon/releases"
MIN_SIZE = 400_000  # PresentMon 2.4.1 x64 pesa circa 0,9 MB


class PresentMonMissing(RuntimeError):
    pass


def _valid(p):
    """File esistente, abbastanza grande e che sia davvero un programma Windows (inizia con 'MZ')."""
    try:
        if not (os.path.isfile(p) and os.path.getsize(p) > MIN_SIZE):
            return False
        with open(p, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def find_presentmon(tools_dir):
    """Un PresentMon gia' presente: nella cartella strumenti o scaricato a mano in Download (qualsiasi versione 2.x)."""
    import glob
    import shutil
    path = os.path.join(tools_dir, "PresentMon-%s-x64.exe" % PRESENTMON_VERSION)
    if _valid(path):
        return path
    for p in sorted(glob.glob(os.path.join(tools_dir, "PresentMon*.exe")), reverse=True):
        if _valid(p) and "x64" in os.path.basename(p).lower():
            return p
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    for p in sorted(glob.glob(os.path.join(downloads, "PresentMon*x64*.exe")), reverse=True):
        if _valid(p):
            dest = os.path.join(tools_dir, os.path.basename(p))
            shutil.copy2(p, dest)
            return dest
    return None


def ensure_presentmon(tools_dir, progress=None, stop=None, attempts=3, timeout=20):
    """Restituisce il percorso di PresentMon, scaricandolo se serve.

    Download a pezzi con tempo limite, avanzamento, tentativi e possibilita' di annullare (stop.set()).
    Se non riesce solleva PresentMonMissing con le istruzioni per scaricarlo a mano.
    """
    def say(m):
        (progress or print)(m)
    os.makedirs(tools_dir, exist_ok=True)
    found = find_presentmon(tools_dir)
    if found:
        return found
    path = os.path.join(tools_dir, "PresentMon-%s-x64.exe" % PRESENTMON_VERSION)
    tmp = path + ".part"
    last_err = None
    for attempt in range(1, attempts + 1):
        if stop is not None and stop.is_set():
            raise RuntimeError("Registrazione annullata.")
        say("Scarico PresentMon (strumento gratuito di Intel per misurare i frame), tentativo %d di %d..."
            % (attempt, attempts))
        try:
            req = urllib.request.Request(PRESENTMON_URL, headers={"User-Agent": "LagDoctor"})
            with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done, last_note = 0, 0.0
                while True:
                    if stop is not None and stop.is_set():
                        raise RuntimeError("Registrazione annullata.")
                    chunk = r.read(256 * 1024)  # ogni lettura ha il suo tempo limite
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if time.time() - last_note > 1.0:
                        last_note = time.time()
                        say("Scaricati %.1f%s MB..." % (done / 1e6, (" di %.1f" % (total / 1e6)) if total else ""))
            if total and done < total:
                raise IOError("download interrotto (%d di %d byte)" % (done, total))
            if done < MIN_SIZE:
                raise IOError("file scaricato troppo piccolo (%d byte)" % done)
            with open(tmp, "rb") as f:
                if f.read(2) != b"MZ":
                    raise IOError("il file scaricato non e' un programma (forse una pagina di errore della rete)")
            os.replace(tmp, path)
            time.sleep(1.5)  # l'antivirus a volte cancella subito i file appena scaricati
            if not _valid(path):
                raise PresentMonMissing(
                    "PresentMon e' stato scaricato ma poi e' sparito: probabilmente l'antivirus o Windows lo hanno "
                    "bloccato. Controlla 'Sicurezza di Windows > Protezione da virus e minacce > Cronologia "
                    "protezione' e consenti il file, oppure scaricalo a mano (vedi sotto).\n" + manual_help(tools_dir))
            say("PresentMon pronto.")
            return path
        except PresentMonMissing:
            raise
        except RuntimeError:
            raise
        except Exception as e:  # rete, tempo scaduto, proxy, SSL...
            last_err = e
            try:
                os.remove(tmp)
            except OSError:
                pass
            say("Download non riuscito (%s)." % (str(e)[:120] or e.__class__.__name__))
            time.sleep(2)
    raise PresentMonMissing("Non riesco a scaricare PresentMon da GitHub (ultimo errore: %s).\n%s"
                            % (str(last_err)[:150], manual_help(tools_dir)))


def manual_help(tools_dir):
    return ("Scaricalo a mano: apri %s, nella versione piu' recente scarica il file 'PresentMon-...-x64.exe' "
            "(NON 'PresentMon-...-x64.msi' o i file 'Source code') e lascialo nella cartella Download, oppure "
            "copialo in: %s. Poi riprova: LagDoctor lo trova da solo." % (PRESENTMON_PAGE, tools_dir))


# Sonda di latenza: processo separato ad alta priorita' che chiede di dormire 1 ms e misura quanto ritarda il
# risveglio. Ritardi di molti ms mentre il PC non e' saturo indicano blocchi di sistema (driver DPC/ISR, SMI).
LATENCY_PROBE = r"""
import ctypes, json, sys, time
k32 = ctypes.windll.kernel32
ctypes.windll.winmm.timeBeginPeriod(1)
k32.SetPriorityClass(k32.GetCurrentProcess(), 0x80)          # HIGH_PRIORITY_CLASS
# Windows 11 rallenta il timer dei processi senza finestra (risvegli ogni 15,6 ms): lo disattiviamo, altrimenti la
# sonda vedrebbe falsi ritardi di ~14 ms. ControlMask = EXECUTION_SPEED | IGNORE_TIMER_RESOLUTION, StateMask = 0.
class _PPT(ctypes.Structure):
    _fields_ = [("Version", ctypes.c_ulong), ("ControlMask", ctypes.c_ulong), ("StateMask", ctypes.c_ulong)]
_s = _PPT(1, 0x1 | 0x4, 0)
k32.SetProcessInformation(k32.GetCurrentProcess(), 4, ctypes.byref(_s), ctypes.sizeof(_s))
k32.SetThreadPriority(k32.GetCurrentThread(), 15)            # TIME_CRITICAL
pc = time.perf_counter
while True:
    end = pc() + 0.25
    worst = 0.0
    over = 0
    while pc() < end:
        t0 = pc()
        k32.Sleep(1)
        late = (pc() - t0) * 1000 - 1.0
        worst = max(worst, late)
        if late > 2.0:
            over += 1
    sys.stdout.write(json.dumps({"t": time.time(), "lat_max": round(worst, 3), "lat_over2": over}) + "\n")
    sys.stdout.flush()
"""

PDH_PATHS = {
    "dpc_pct": r"\Processor(_Total)\% DPC Time",
    "isr_pct": r"\Processor(_Total)\% Interrupt Time",
    "dpc_rate": r"\Processor(_Total)\DPCs Queued/sec",
    "cpu_perf": r"\Processor Information(_Total)\% Processor Performance",
    "cpu_maxfreq": r"\Processor Information(_Total)\% of Maximum Frequency",
    "hard_faults": r"\Memory\Pages Input/sec",
    "avail_mb": r"\Memory\Available MBytes",
    "gpu_shared": r"\GPU Adapter Memory(*)\Shared Usage",
    "gpu_dedicated": r"\GPU Adapter Memory(*)\Dedicated Usage",
}


class LatencyProbe(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.points = []
        self.proc = None

    def run(self):
        import json
        import sys
        from . import paths
        cmd = paths.helper_cmd("--probe") if paths.FROZEN else [sys.executable, "-c", LATENCY_PROBE]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, text=True, creationflags=CREATE_NO_WINDOW)
        except Exception:
            return
        for line in self.proc.stdout:
            try:
                self.points.append(json.loads(line))
            except ValueError:
                pass

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass

    def window(self, t0, t1):
        pts = [p for p in self.points if t0 < p["t"] <= t1]
        if not pts:
            return None, None
        return max(p["lat_max"] for p in pts), sum(p["lat_over2"] for p in pts)


class SystemMonitor(threading.Thread):
    """Ogni 0,25 s registra lo stato del sistema; ogni secondo anche processi in background e thread del gioco."""
    TICK = 0.25

    def __init__(self, game_pid, gpu, csv_path):
        super().__init__(daemon=True)
        self.game_pid = game_pid
        self.gpu = gpu
        self.csv_path = csv_path
        self.samples = []
        self.first_frame_wall = None
        self._stop_event = threading.Event()
        self.ncpu = psutil.cpu_count() or 1
        self.own_pid = os.getpid()
        self.probe = LatencyProbe()

    def _wait_first_frame(self):
        if self.first_frame_wall is None:
            try:
                if os.path.getsize(self.csv_path) > 1500:  # header + almeno un frame
                    self.first_frame_wall = time.time()
            except OSError:
                pass

    @staticmethod
    def _luid_sum(arr, luid=None):
        import re
        tot = {}
        for name, v in arr or []:
            m = re.search(r"luid_0x[0-9a-f]+_0x[0-9a-f]+", (name or "").lower())
            if m:
                tot[m.group(0)] = tot.get(m.group(0), 0) + v
        return tot

    def run(self):
        try:
            psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except Exception:
            pass
        from . import pdh
        counters = pdh.Query(PDH_PATHS)
        self.probe.start()
        try:
            game = psutil.Process(self.game_pid)
        except psutil.Error:
            game = None
        procs, threads_prev = {}, {}
        psutil.cpu_percent(percpu=True)
        last_disk = psutil.disk_io_counters()
        last_gio = None
        last_t = time.time()
        tick = 0
        while not self._stop_event.wait(self.TICK):
            tick += 1
            self._wait_first_frame()
            now = time.time()
            dt = max(now - last_t, 0.001)
            cores = psutil.cpu_percent(percpu=True)
            vm = psutil.virtual_memory()
            disk = psutil.disk_io_counters()
            smp = {
                "wall": now,
                "cpu_total": sum(cores) / len(cores),
                "cpu_max_core": max(cores),
                "cores_busy": sum(1 for c in cores if c > 90),
                "ram_pct": vm.percent,
                "disk_read_mb": (disk.read_bytes - last_disk.read_bytes) / dt / 1e6 if disk else None,
                "disk_write_mb": (disk.write_bytes - last_disk.write_bytes) / dt / 1e6 if disk else None,
            }
            last_disk = disk
            # contatori di Windows
            c = counters.collect() if counters.ok else {}
            for k in ("dpc_pct", "isr_pct", "dpc_rate", "cpu_perf", "cpu_maxfreq", "hard_faults", "avail_mb"):
                if k in c:
                    smp[k] = c[k]
            ded, sh = self._luid_sum(c.get("gpu_dedicated")), self._luid_sum(c.get("gpu_shared"))
            if ded and not getattr(self.gpu, "integrated", False):  # integrata: la memoria condivisa e' normale
                luid = max(ded, key=ded.get)
                smp["vram_shared_mb"] = sh.get(luid, 0) / 2**20
            # letture dal disco del SOLO gioco
            if game is not None:
                try:
                    gio = game.io_counters()
                    if last_gio is not None:
                        smp["game_read_mb"] = (gio.read_bytes - last_gio.read_bytes) / dt / 1e6
                    last_gio = gio
                except psutil.Error:
                    game = None
            # latenza di sistema (sonda)
            lat_max, lat_over = self.probe.window(last_t, now)
            if lat_max is not None:
                smp["lat_max"], smp["lat_over2"] = lat_max, lat_over
            last_t = now

            if tick % 4 == 0:  # ogni secondo: processi in background e thread del gioco
                self._slow(smp, procs, game, threads_prev)
            smp["fg"] = self._foreground()  # il gioco e' la finestra attiva? (Alt+Tab, menu di Windows...)
            smp.update(self.gpu.latest)
            self.samples.append(smp)

    def _foreground(self):
        try:
            import ctypes
            u32 = ctypes.windll.user32
            hwnd = u32.GetForegroundWindow()
            pid = ctypes.c_ulong(0)
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value == self.game_pid
        except Exception:
            return None  # non verificabile

    def _slow(self, smp, procs, game, threads_prev):
        bg = []
        seen = set()
        for p in psutil.process_iter(["name"]):
            seen.add(p.pid)
            if p.pid == self.own_pid:
                continue
            if p.pid not in procs:
                procs[p.pid] = p
                try:
                    p.cpu_percent(None)
                except psutil.Error:
                    pass
                continue
            try:
                c = procs[p.pid].cpu_percent(None) / self.ncpu
            except psutil.Error:
                continue
            if p.pid == self.game_pid:
                smp["game_cpu"] = c
                continue
            name = p.info["name"] or "?"
            if name.lower() in IGNORE_PROCS:
                continue
            if c >= 1.0:
                bg.append((name, round(c, 1)))
        for pid in list(procs):
            if pid not in seen:
                del procs[pid]
        bg.sort(key=lambda x: -x[1])
        smp["bg_top"] = bg[:5]
        # thread piu' carico del gioco (thread principale / render): % di UN core
        if game is not None:
            try:
                now = time.time()
                cur = {t.id: t.user_time + t.system_time for t in game.threads()}
                if threads_prev.get("t"):
                    span = now - threads_prev["t"]
                    deltas = [cur[i] - threads_prev["v"].get(i, cur[i]) for i in cur]
                    if deltas and span > 0:
                        smp["game_top_thread"] = min(100.0, max(deltas) / span * 100)
                threads_prev.update(t=now, v=cur)
            except psutil.Error:
                pass

    def stop(self):
        self._stop_event.set()
        self.probe.stop()

    def finalize(self):
        """Converte i tempi in 'secondi dal primo frame' per allinearli a PresentMon."""
        base = self.first_frame_wall or (self.samples[0]["wall"] if self.samples else 0)
        for s in self.samples:
            s["t"] = s["wall"] - base
        return [s for s in self.samples if s["t"] >= 0]


def live_reader(csv_path):
    """Generatore che restituisce i nuovi frame time scritti nel CSV (per le statistiche dal vivo)."""
    pos = 0
    col = None
    while True:
        new = []
        try:
            with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(pos)
                chunk = f.read()
                last_nl = chunk.rfind("\n")
                if last_nl >= 0:
                    pos += len(chunk[:last_nl + 1].encode("utf-8"))
                    for line in chunk[:last_nl].splitlines():
                        parts = line.split(",")
                        if col is None:
                            low = [p.strip().lower() for p in parts]
                            for c in ("frametime", "msbetweenappstart", "msbetweenpresents"):
                                if c in low:
                                    col = low.index(c)
                                    break
                            continue
                        try:
                            new.append(float(parts[col]))
                        except (ValueError, IndexError):
                            pass
        except OSError:
            pass
        yield new


def _stop_presentmon(presentmon, pm):
    """Chiude la sessione in modo pulito (cosi' il CSV viene salvato fino all'ultimo frame)."""
    try:
        subprocess.run([presentmon, "--terminate_existing_session", "--session_name", "LagDoctor"],
                       capture_output=True, timeout=15)
        pm.wait(timeout=10)
    except Exception:
        pm.terminate()


def record(presentmon, game, csv_path, seconds, gpu_info=None, stop_event=None, on_progress=None):
    """Avvia la registrazione e restituisce i campioni di sistema.

    Console: Ctrl+C la ferma prima.  Interfaccia: stop_event.set() la ferma prima e on_progress(dict)
    riceve ogni secondo i dati dal vivo (FPS, frame time recenti, secondi rimanenti).
    """
    if os.path.exists(csv_path):
        os.remove(csv_path)
    gpu = gpumod.make_monitor(gpu_info)
    if not gpu.available and on_progress is None:
        print("  (Non riesco a leggere i dati della scheda video: misuro solo i frame e il resto del PC.)")
    gpu.start()
    cmd = [presentmon, "--process_id", str(game.pid), "--output_file", csv_path,
           "--timed", str(seconds), "--terminate_after_timed", "--terminate_on_proc_exit",
           "--no_console_stats", "--stop_existing_session", "--session_name", "LagDoctor"]
    pm = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                          creationflags=CREATE_NO_WINDOW if on_progress else 0)
    mon = SystemMonitor(game.pid, gpu, csv_path)
    mon.start()

    start = time.time()
    reader = live_reader(csv_path)
    recent = []
    interval = 1 if on_progress else 2
    try:
        while pm.poll() is None:
            if stop_event is not None and stop_event.wait(interval):
                _stop_presentmon(presentmon, pm)
                break
            if stop_event is None:
                time.sleep(interval)
            frames = next(reader)
            recent = (recent + frames)[-600:]
            left = max(0, seconds - (time.time() - start))
            if on_progress:
                g = dict(gpu.latest)
                on_progress({"left": left, "elapsed": time.time() - start,
                             "fps": (1000.0 / (sum(recent) / len(recent))) if recent else None,
                             "worst": max(recent) if recent else None, "frames": recent[-300:],
                             "gpu_util": g.get("gpu_util"), "gpu_temp": g.get("gpu_temp"),
                             "vram_used": g.get("vram_used"), "vram_total": g.get("vram_total")})
                continue
            if recent:
                fps = 1000.0 / (sum(recent) / len(recent))
                worst = max(recent)
                msg = "  Registrazione... %3d s rimanenti | FPS ~%4.0f | frame peggiore recente %5.1f ms" % (
                    left, fps, worst)
            else:
                msg = "  Registrazione... %3d s rimanenti | in attesa dei primi frame (sei nel gioco?)" % left
            print(msg.ljust(95), end="\r", flush=True)
    except KeyboardInterrupt:
        print("\n  Fermo la registrazione...")
        try:
            pm.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pm.terminate()
    if on_progress is None:
        print()
    mon.stop()
    gpu.stop()
    mon.join(timeout=5)
    err = pm.stderr.read() if pm.stderr else ""
    if not os.path.exists(csv_path):
        raise RuntimeError("PresentMon non ha prodotto dati. Messaggio: " + (err.strip() or "nessuno"))
    return mon.finalize()
