"""Temperatura della CPU, nei limiti di quello che Windows permette senza driver aggiuntivi.

Windows non ha un'API per la temperatura della CPU. Fonti usate, in ordine di precisione:
  1. LibreHardwareMonitor / OpenHardwareMonitor, se aperti: pubblicano i sensori via WMI (preciso: Tctl/Tdie sui
     Ryzen, Package sugli Intel)
  2. sensore ACPI "Thermal Zone" della scheda madre (contatore di Windows): su molti PC segue la CPU, su altri e'
     fisso o assente. Se in 2 minuti non cambia mai, lo considero non affidabile e non lo mostro.
Lettura in un thread a parte (PowerShell solo per LibreHardwareMonitor, ogni 5 secondi): l'interfaccia non aspetta.
"""
import subprocess
import threading
import time

from . import pdh

CREATE_NO_WINDOW = 0x08000000
_LHM_PS = ("$s = $null; foreach ($ns in 'root/LibreHardwareMonitor','root/OpenHardwareMonitor') { try { "
           "$s = Get-CimInstance -Namespace $ns -ClassName Sensor -ErrorAction Stop | Where-Object { "
           "$_.SensorType -eq 'Temperature' -and $_.Name -match 'Tctl|Tdie|Package|CPU Core|Core \\(Tctl' } | "
           "Sort-Object Value -Descending | Select-Object -First 1; if ($s) { break } } catch {} }; "
           "if ($s) { 'T=' + [math]::Round($s.Value, 1) + ';' + $s.Name } else { 'NONE' }")


class CpuTemp:
    def __init__(self):
        self.value, self.source = None, None
        self._lhm_ok = None          # None = da provare
        self._lhm_next = 0
        self._acpi = None
        self._acpi_hist = []         # (tempo, valore) per capire se il sensore ACPI e' "fermo"
        self._acpi_bad = False
        self._stop = threading.Event()
        self._t = None
        self.last_read = time.time()

    def start(self):
        if self._t is None:
            self._t = threading.Thread(target=self._run, daemon=True)
            self._t.start()

    def stop(self):
        self._stop.set()

    def _lhm(self):
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _LHM_PS],
                               capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL,
                               creationflags=CREATE_NO_WINDOW)
            out = (r.stdout or "").strip().splitlines()[-1:] or [""]
            if out[0].startswith("T="):
                v, name = out[0][2:].split(";", 1)
                return float(v.replace(",", ".")), name
        except Exception:
            pass
        return None

    def _acpi_read(self):
        if self._acpi is None:
            self._acpi = pdh.Query({"hp": r"\Thermal Zone Information(*)\High Precision Temperature",
                                    "t": r"\Thermal Zone Information(*)\Temperature"})
            self._acpi.collect()
        if not self._acpi.ok:
            return None
        c = self._acpi.collect()
        vals = [v / 10.0 - 273.15 for _n, v in (c.get("hp") or []) if v] or \
               [v - 273.15 for _n, v in (c.get("t") or []) if v]
        vals = [v for v in vals if 15 <= v <= 115]
        return round(max(vals), 1) if vals else None

    def _run(self):
        while not self._stop.is_set():
            now = time.time()
            got = None
            if self._lhm_ok is not False or now >= self._lhm_next:
                r = self._lhm()
                self._lhm_ok = r is not None
                if r:
                    got = (r[0], "LibreHardwareMonitor (" + r[1] + ")")
                else:
                    self._lhm_next = now + 60  # riprovo tra un minuto (magari l'utente lo apre)
            if got is None and not self._acpi_bad:
                try:
                    v = self._acpi_read()
                except Exception:
                    v = None
                if v is not None:
                    self._acpi_hist = [(t, x) for t, x in self._acpi_hist if now - t < 120] + [(now, v)]
                    span = now - self._acpi_hist[0][0]
                    if span > 110 and len({x for _t, x in self._acpi_hist}) == 1:
                        self._acpi_bad = True   # sempre lo stesso valore per 2 minuti: sensore finto
                    else:
                        got = (v, "sensore ACPI della scheda madre (indicativo)")
            self.value, self.source = got if got else (None, None)
            self._stop.wait(5 if self._lhm_ok else 2)
