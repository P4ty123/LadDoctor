"""Lettura dati della scheda video per tutte le marche.

- NVIDIA: nvidia-smi (incluso nel driver), che da' anche temperatura e throttling.
- AMD / Intel (o NVIDIA senza nvidia-smi): contatori di prestazione di Windows,
  gli stessi usati dal Task Manager (utilizzo GPU e VRAM usata).
"""
import ctypes
import re
import subprocess
import threading
import time

try:
    import winreg
except ImportError:
    winreg = None

CREATE_NO_WINDOW = 0x08000000
GPU_CLASS_KEY = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


# ---------------------------------------------------------------- info scheda

def _vendor(text):
    t = (text or "").lower()
    if "nvidia" in t:
        return "nvidia"
    if "amd" in t or "advanced micro" in t or "radeon" in t or "ati " in t:
        return "amd"
    if "intel" in t:
        return "intel"
    return "altro"


def list_adapters():
    """Schede video installate, lette dal registro di Windows."""
    res = []
    if winreg is None:
        return res
    try:
        cls = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, GPU_CLASS_KEY)
    except OSError:
        return res
    i = 0
    while True:
        try:
            sub = winreg.EnumKey(cls, i)
        except OSError:
            break
        i += 1
        if not sub.isdigit():
            continue
        try:
            with winreg.OpenKey(cls, sub) as k:
                def get(name):
                    try:
                        return winreg.QueryValueEx(k, name)[0]
                    except OSError:
                        return None
                desc = get("DriverDesc")
                if not desc or "basic" in desc.lower() or "remote" in desc.lower():
                    continue
                mem = get("HardwareInformation.qwMemorySize") or get("HardwareInformation.MemorySize")
                if isinstance(mem, bytes):
                    mem = int.from_bytes(mem, "little")
                res.append({
                    "name": desc,
                    "vendor": _vendor((get("ProviderName") or "") + " " + desc),
                    "driver": get("RadeonSoftwareVersion") or get("DriverVersion"),
                    "vram_mb": int(mem / 2**20) if mem else None,
                })
        except OSError:
            continue
    return res


def gpu_info():
    """La scheda principale (quella con piu' VRAM, cioe' la dedicata)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
        name, drv, mem = [x.strip() for x in out.stdout.strip().splitlines()[0].split(",")]
        return {"name": name, "vendor": "nvidia", "driver": drv, "vram_mb": int(float(mem))}
    except Exception:
        pass
    ads = list_adapters()
    if not ads:
        return None
    from .scan import is_integrated
    dedicated = [a for a in ads if not is_integrated(a.get("name"))]
    best = dict(max(dedicated or ads, key=lambda a: a.get("vram_mb") or 0))
    # grafica integrata (mini PC, portatili): non ha VRAM propria, usa la RAM del sistema
    best["integrated"] = not dedicated
    return best


# ---------------------------------------------------------------- NVIDIA

class NvidiaMonitor(threading.Thread):
    BASE = "utilization.gpu,memory.used,memory.total,temperature.gpu,clocks.gr,power.draw"

    def __init__(self):
        super().__init__(daemon=True)
        self.latest = {}
        self.proc = None
        self.fields = None
        for extra in (",clocks_event_reasons.active", ",clocks_throttle_reasons.active", ""):
            try:
                r = subprocess.run(["nvidia-smi", "--query-gpu=" + self.BASE + extra,
                                    "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW)
                if r.returncode == 0 and r.stdout.strip():
                    self.fields = self.BASE + extra
                    break
            except Exception:
                break
        self.available = self.fields is not None

    def run(self):
        if not self.available:
            return
        self.proc = subprocess.Popen(
            ["nvidia-smi", "--query-gpu=" + self.fields, "--format=csv,noheader,nounits", "-lms", "500"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, creationflags=CREATE_NO_WINDOW)
        for line in self.proc.stdout:
            parts = [p.strip() for p in line.split(",")]
            try:
                d = {"gpu_util": float(parts[0]), "vram_used": float(parts[1]), "vram_total": float(parts[2]),
                     "gpu_temp": float(parts[3]), "gpu_clock": float(parts[4])}
            except (ValueError, IndexError):
                continue
            try:
                d["gpu_power"] = float(parts[5])
            except (ValueError, IndexError):
                pass
            if len(parts) > 6:
                try:
                    bits = int(parts[6], 16)
                    # 0x8 HW slowdown, 0x20 SW thermal, 0x40 HW thermal, 0x80 HW power brake
                    d["thr_thermal"] = bool(bits & (0x8 | 0x20 | 0x40 | 0x80))
                    d["thr_power"] = bool(bits & 0x4)
                except ValueError:
                    pass
            self.latest = d

    def stop(self):
        if self.proc:
            self.proc.terminate()


# ---------------------------------------------------------------- Windows PDH (tutte le marche)

class _FmtValue(ctypes.Structure):
    _fields_ = [("CStatus", ctypes.c_ulong), ("doubleValue", ctypes.c_double)]


class _FmtItem(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _FmtValue)]


PDH_FMT_DOUBLE = 0x00000200
PDH_FMT_NOCAP100 = 0x00008000
PDH_MORE_DATA = 0x800007D2
LUID_RE = re.compile(r"luid_0x[0-9a-f]+_0x[0-9a-f]+", re.I)
ENG_RE = re.compile(r"engtype_([a-z0-9]+)", re.I)


class PdhGpuMonitor(threading.Thread):
    """Usa i contatori 'GPU Engine' e 'GPU Adapter Memory' di Windows (nomi inglesi, validi in ogni lingua)."""

    def __init__(self, vram_total_mb=None, extra=None, integrated=False):
        super().__init__(daemon=True)
        self.latest = {}
        self.integrated = integrated  # grafica integrata: la "VRAM" e' RAM condivisa, niente limite fisso
        self.extra = extra  # lettore aggiuntivo (es. AdlReader per le Radeon)
        self.vram_total = vram_total_mb
        self._stop_event = threading.Event()
        self.available = False
        try:
            self.pdh = ctypes.windll.pdh
            self.query = ctypes.c_void_p()
            if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(self.query)) != 0:
                return
            self.c_eng = ctypes.c_void_p()
            self.c_mem = ctypes.c_void_p()
            r1 = self.pdh.PdhAddEnglishCounterW(self.query, r"\GPU Engine(*)\Utilization Percentage",
                                                None, ctypes.byref(self.c_eng))
            r2 = self.pdh.PdhAddEnglishCounterW(self.query, r"\GPU Adapter Memory(*)\Dedicated Usage",
                                                None, ctypes.byref(self.c_mem))
            self.c_sh = ctypes.c_void_p()
            if integrated and self.pdh.PdhAddEnglishCounterW(self.query, r"\GPU Adapter Memory(*)\Shared Usage",
                                                             None, ctypes.byref(self.c_sh)) != 0:
                self.c_sh = None
            self.available = (r1 == 0 and r2 == 0)
        except Exception:
            self.available = False

    def _read(self, counter, flags):
        size = ctypes.c_ulong(0)
        count = ctypes.c_ulong(0)
        r = self.pdh.PdhGetFormattedCounterArrayW(counter, flags, ctypes.byref(size), ctypes.byref(count), None)
        if (r & 0xFFFFFFFF) != PDH_MORE_DATA or size.value == 0:
            return []
        buf = ctypes.create_string_buffer(size.value)
        r = self.pdh.PdhGetFormattedCounterArrayW(counter, flags, ctypes.byref(size), ctypes.byref(count), buf)
        if r != 0:
            return []
        items = ctypes.cast(buf, ctypes.POINTER(_FmtItem))
        return [(items[i].szName, items[i].FmtValue.doubleValue) for i in range(count.value)
                if items[i].FmtValue.CStatus in (0, 1)]

    def run(self):
        if not self.available:
            return
        self.pdh.PdhCollectQueryData(self.query)
        while not self._stop_event.wait(1.0):
            if self.pdh.PdhCollectQueryData(self.query) != 0:
                continue
            # Memoria dedicata per scheda (luid): la scheda dedicata e' quella che ne usa di piu'
            mem = {}
            counters = [self.c_mem] + ([self.c_sh] if self.integrated and self.c_sh else [])
            for c in counters:  # integrata: memoria dedicata (piccola) + condivisa (la RAM che usa davvero)
                for name, v in self._read(c, PDH_FMT_DOUBLE):
                    m = LUID_RE.search(name or "")
                    if m:
                        mem[m.group(0).lower()] = mem.get(m.group(0).lower(), 0) + v
            if not mem:
                continue
            luid = max(mem, key=mem.get)
            # Utilizzo: somma dei processi per ogni tipo di motore, poi il motore piu' carico (come Task Manager)
            eng = {}
            for name, v in self._read(self.c_eng, PDH_FMT_DOUBLE | PDH_FMT_NOCAP100):
                if luid not in (name or "").lower():
                    continue
                e = ENG_RE.search(name)
                key = e.group(1).lower() if e else "?"
                eng[key] = eng.get(key, 0) + v
            d = {"gpu_util": min(100.0, max(eng.values())) if eng else None,
                 "vram_used": mem[luid] / 2**20}
            if self.vram_total and not self.integrated:
                d["vram_total"] = self.vram_total
            if self.extra is not None:
                try:
                    d.update(self.extra.read())
                except Exception:
                    pass
            self.latest = d

    def stop(self):
        self._stop_event.set()


# ---------------------------------------------------------------- AMD ADL (temperatura e throttling Radeon)

ADL_MAX_PATH = 256
PMLOG_CLK_GFXCLK = 1
PMLOG_TEMPERATURE_EDGE = 8
PMLOG_ASIC_POWER = 23
PMLOG_TEMPERATURE_HOTSPOT = 27
PMLOG_THROTTLER_STATUS = 35
ADL_THROTTLE_POWER = 1 << 0
ADL_THROTTLE_THERMAL = 1 << 1
ADL_THROTTLE_CURRENT = 1 << 2


class _AdapterInfo(ctypes.Structure):
    _fields_ = [("iSize", ctypes.c_int), ("iAdapterIndex", ctypes.c_int),
                ("strUDID", ctypes.c_char * ADL_MAX_PATH), ("iBusNumber", ctypes.c_int),
                ("iDeviceNumber", ctypes.c_int), ("iFunctionNumber", ctypes.c_int), ("iVendorID", ctypes.c_int),
                ("strAdapterName", ctypes.c_char * ADL_MAX_PATH), ("strDisplayName", ctypes.c_char * ADL_MAX_PATH),
                ("iPresent", ctypes.c_int), ("iExist", ctypes.c_int),
                ("strDriverPath", ctypes.c_char * ADL_MAX_PATH), ("strDriverPathExt", ctypes.c_char * ADL_MAX_PATH),
                ("strPNPString", ctypes.c_char * ADL_MAX_PATH), ("iOSDisplayIndex", ctypes.c_int)]


class _SensorData(ctypes.Structure):
    _fields_ = [("supported", ctypes.c_int), ("value", ctypes.c_int)]


class _PMLogDataOutput(ctypes.Structure):
    _fields_ = [("size", ctypes.c_int), ("sensors", _SensorData * 256)]


class AdlReader:
    """Legge i sensori della Radeon tramite atiadlxx.dll (installata con il driver AMD)."""

    def __init__(self, target_name=None):
        self.ok = False
        try:
            self.dll = ctypes.CDLL("atiadlxx.dll")
            crt = ctypes.CDLL("msvcrt")
            crt.malloc.restype = ctypes.c_void_p
            crt.malloc.argtypes = [ctypes.c_size_t]
            self._malloc = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int)(lambda n: crt.malloc(n))
            self.ctx = ctypes.c_void_p()
            if self.dll.ADL2_Main_Control_Create(self._malloc, 1, ctypes.byref(self.ctx)) != 0:
                return
            n = ctypes.c_int(0)
            self.dll.ADL2_Adapter_NumberOfAdapters_Get(self.ctx, ctypes.byref(n))
            if n.value <= 0:
                return
            infos = (_AdapterInfo * n.value)()
            for a in infos:
                a.iSize = ctypes.sizeof(_AdapterInfo)
            if self.dll.ADL2_Adapter_AdapterInfo_Get(self.ctx, infos, ctypes.sizeof(infos)) != 0:
                return
            cands = []
            for a in infos:
                if a.iVendorID != 1002:
                    continue
                active = ctypes.c_int(0)
                self.dll.ADL2_Adapter_Active_Get(self.ctx, a.iAdapterIndex, ctypes.byref(active))
                name = a.strAdapterName.decode(errors="ignore")
                score = (2 if target_name and name.lower() == target_name.lower() else 0) \
                    + (1 if active.value else 0) - (1 if "radeon(tm) graphics" in name.lower() else 0)
                cands.append((score, a.iAdapterIndex, name))
            for score, idx, name in sorted(cands, key=lambda c: -c[0]):
                self.index = idx
                d = self.read()
                if d.get("gpu_temp") is not None:
                    self.name = name
                    self.ok = True
                    return
        except Exception:
            self.ok = False

    def read(self):
        out = _PMLogDataOutput()
        out.size = ctypes.sizeof(_PMLogDataOutput)
        if self.dll.ADL2_New_QueryPMLogData_Get(self.ctx, self.index, ctypes.byref(out)) != 0:
            return {}
        s = out.sensors

        def val(i):
            if not s[i].supported:
                return None
            v = s[i].value
            return v / 1000.0 if v > 1000 and i in (PMLOG_TEMPERATURE_EDGE, PMLOG_TEMPERATURE_HOTSPOT) else v
        d = {"gpu_temp": val(PMLOG_TEMPERATURE_EDGE), "gpu_hotspot": val(PMLOG_TEMPERATURE_HOTSPOT),
             "gpu_clock": val(PMLOG_CLK_GFXCLK), "gpu_power": val(PMLOG_ASIC_POWER)}
        thr = val(PMLOG_THROTTLER_STATUS)
        if thr is not None:
            d["thr_thermal"] = bool(thr & ADL_THROTTLE_THERMAL)
            d["thr_power"] = bool(thr & (ADL_THROTTLE_POWER | ADL_THROTTLE_CURRENT))
        # Le Radeon RDNA si limitano quando il punto piu' caldo (hotspot) arriva a ~110 C
        if d["gpu_hotspot"] is not None and d["gpu_hotspot"] >= 105:
            d["thr_thermal"] = True
        return {k: v for k, v in d.items() if v is not None}


def make_monitor(info):
    """Sceglie il metodo migliore per la scheda installata."""
    if info and info.get("vendor") == "nvidia":
        m = NvidiaMonitor()
        if m.available:
            return m
    extra = None
    if info and info.get("vendor") == "amd":
        adl = AdlReader(info.get("name"))
        if adl.ok:
            extra = adl
        else:
            print("  (Non riesco a leggere temperatura e throttling della Radeon: aggiorna il driver AMD.)")
    return PdhGpuMonitor(info.get("vram_mb") if info else None, extra,
                         integrated=bool(info and info.get("integrated")))
