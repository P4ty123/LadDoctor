"""Contatori di prestazione di Windows (PDH) con nomi inglesi, validi in ogni lingua di Windows."""
import ctypes

PDH_FMT_DOUBLE = 0x00000200
PDH_FMT_NOCAP100 = 0x00008000
PDH_MORE_DATA = 0x800007D2


class _FmtValue(ctypes.Structure):
    _fields_ = [("CStatus", ctypes.c_ulong), ("doubleValue", ctypes.c_double)]


class _FmtItem(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _FmtValue)]


class Query:
    """Raccoglie piu' contatori insieme. Chiamare collect() a intervalli regolari."""

    def __init__(self, paths):
        """paths: dict nome -> percorso inglese, es. {"dpc": r"\\Processor(_Total)\\% DPC Time"}."""
        self.ok = False
        self.counters = {}
        try:
            self.pdh = ctypes.windll.pdh
            self.q = ctypes.c_void_p()
            if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(self.q)) != 0:
                return
            for name, path in paths.items():
                c = ctypes.c_void_p()
                if self.pdh.PdhAddEnglishCounterW(self.q, path, None, ctypes.byref(c)) == 0:
                    self.counters[name] = (c, "*" in path)
            self.ok = bool(self.counters)
            if self.ok:
                self.pdh.PdhCollectQueryData(self.q)
        except Exception:
            self.ok = False

    def _array(self, counter):
        size, count = ctypes.c_ulong(0), ctypes.c_ulong(0)
        flags = PDH_FMT_DOUBLE | PDH_FMT_NOCAP100
        r = self.pdh.PdhGetFormattedCounterArrayW(counter, flags, ctypes.byref(size), ctypes.byref(count), None)
        if (r & 0xFFFFFFFF) != PDH_MORE_DATA or size.value == 0:
            return []
        buf = ctypes.create_string_buffer(size.value)
        if self.pdh.PdhGetFormattedCounterArrayW(counter, flags, ctypes.byref(size), ctypes.byref(count), buf) != 0:
            return []
        items = ctypes.cast(buf, ctypes.POINTER(_FmtItem))
        return [(items[i].szName, items[i].FmtValue.doubleValue) for i in range(count.value)
                if items[i].FmtValue.CStatus in (0, 1)]

    def collect(self):
        """Restituisce dict nome -> valore (contatori singoli) o lista (nome_istanza, valore) (con *)."""
        if not self.ok or self.pdh.PdhCollectQueryData(self.q) != 0:
            return {}
        out = {}
        for name, (c, wildcard) in self.counters.items():
            arr = self._array(c)
            if wildcard:
                out[name] = arr
            elif arr:
                out[name] = arr[0][1]
        return out
