"""Catalogo delle ottimizzazioni di Windows.

Ogni ottimizzazione sa:
  - controllare se e' gia' attiva (status)
  - applicarsi salvando i valori precedenti (apply -> backup)
  - annullarsi usando il backup (revert)

Livelli di rischio: 0 sicura, 1 moderata, 2 rischiosa, 3 pericolosa.
Efficacia: quanto aiuta DAVVERO nei giochi secondo test indipendenti.
"""
import datetime
import json
import os
import re
import subprocess

try:
    import winreg
except ImportError:
    winreg = None

CREATE_NO_WINDOW = 0x08000000
CONTEXT = {}  # refresh_hz, vendor: impostati all'avvio
RISK = {0: "SICURA", 1: "MODERATA", 2: "RISCHIOSA", 3: "PERICOLOSA"}
STATE_FILE = None  # impostato da init()


# ================================================================ helper di sistema

def ps(command, timeout=60):
    """PowerShell: restituisce (codice_uscita, output)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                           capture_output=True, text=True, encoding=("oem" if os.name == "nt" else None), errors="replace", timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def run(args, timeout=60):
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding=("oem" if os.name == "nt" else None), errors="replace", timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def _hive(name):
    return {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKU": winreg.HKEY_USERS}[name]


def reg_read(hive, path, name):
    """Restituisce (valore, tipo) oppure (None, None) se non esiste."""
    try:
        with winreg.OpenKey(_hive(hive), path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            v, t = winreg.QueryValueEx(k, name)
            return v, t
    except OSError:
        return None, None


def reg_write(hive, path, name, typ, value):
    with winreg.CreateKeyEx(_hive(hive), path, 0, winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY) as k:
        winreg.SetValueEx(k, name, 0, typ, value)


def reg_delete(hive, path, name):
    try:
        with winreg.OpenKey(_hive(hive), path, 0, winreg.KEY_WRITE | winreg.KEY_WOW64_64KEY) as k:
            winreg.DeleteValue(k, name)
    except OSError:
        pass


DWORD = 4  # winreg.REG_DWORD
SZ = 1     # winreg.REG_SZ


# ================================================================ tipi di ottimizzazione

class Tweak:
    def __init__(self, id, cat, name, desc, efficacy, risk=0, reboot=False, warning="", recommend=None,
                 group=None, source="", kind="tweak", harm_if_off=False):
        self.group, self.source, self.kind, self.harm_if_off = group, source, kind, harm_if_off
        self.vendor = None  # "nvidia"/"amd" per le voci del driver video
        self.id, self.cat, self.name, self.desc = id, cat, name, desc
        self.efficacy, self.risk, self.reboot, self.warning = efficacy, risk, reboot, warning
        self._recommend = recommend  # funzione(sysinfo) -> True/False/None

    def recommended(self, sysinfo):
        if self.vendor and ((sysinfo or {}).get("gpu") or {}).get("vendor") != self.vendor:
            return False
        if self._recommend is None:
            return self.risk == 0 and self.efficacy in ("alta", "media")
        return self._recommend(sysinfo or {})

    def status(self):
        return None

    def apply(self):
        raise NotImplementedError

    def revert(self, backup):
        raise NotImplementedError


class RegTweak(Tweak):
    """values: lista di (hive, path, name, tipo, valore) oppure funzione che la restituisce."""

    def __init__(self, *a, values=(), absent_ok=False, **kw):
        super().__init__(*a, **kw)
        self._values = values
        self.absent_ok = absent_ok

    def values(self):
        return self._values() if callable(self._values) else self._values

    active = None  # funzione(leggi) -> True/False: stato per EFFETTO, se diverso dal semplice confronto dei valori

    def status(self):
        if self.active is not None:
            try:
                return self.active(lambda h, p, n: reg_read(h, p, n)[0])
            except Exception:
                return None
        vals = self.values()
        if not vals:
            return None
        def ok(h, p, n, v):
            cur = reg_read(h, p, n)[0]
            return cur == v or (cur is None and self.absent_ok)
        return all(ok(h, p, n, v) for h, p, n, t, v in vals)

    def apply(self):
        old = []
        for h, p, n, t, v in self.values():
            prev, ptype = reg_read(h, p, n)
            old.append([h, p, n, ptype, prev])
            reg_write(h, p, n, t, v)
        return {"reg": old}

    def revert(self, backup):
        for h, p, n, ptype, prev in backup.get("reg", []):
            if prev is None:
                reg_delete(h, p, n)
            else:
                reg_write(h, p, n, ptype, prev)


class ServiceTweak(Tweak):
    """Imposta il tipo di avvio di un servizio (4 = disabilitato) e lo ferma."""
    KEY = r"SYSTEM\CurrentControlSet\Services"

    def __init__(self, *a, service, start=4, **kw):
        super().__init__(*a, **kw)
        self.service, self.start = service, start

    def status(self):
        v, _ = reg_read("HKLM", self.KEY + "\\" + self.service, "Start")
        return None if v is None else v == self.start

    def apply(self):
        prev, _ = reg_read("HKLM", self.KEY + "\\" + self.service, "Start")
        if prev is None:
            raise RuntimeError("servizio %s non presente su questo PC" % self.service)
        reg_write("HKLM", self.KEY + "\\" + self.service, "Start", DWORD, self.start)
        if self.start == 4:
            run(["sc", "stop", self.service])
        return {"start": prev}

    def revert(self, backup):
        reg_write("HKLM", self.KEY + "\\" + self.service, "Start", DWORD, backup["start"])
        if backup["start"] in (2, 3):
            run(["sc", "start", self.service])


POWER_KEY = r"SYSTEM\CurrentControlSet\Control\Power"


def _powercfg_reg(sub, setting):
    """Valore dal registro: quello salvato nel piano attivo, altrimenti il predefinito di Windows per quel piano."""
    code, out = run(["powercfg", "/getactivescheme"])
    m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", out)
    if not m:
        return None
    scheme = m.group(0).lower()
    base = POWER_KEY + "\\User\\PowerSchemes\\%s\\%s\\%s" % (scheme, sub, setting)
    ac, dc = reg_read("HKLM", base, "ACSettingIndex")[0], reg_read("HKLM", base, "DCSettingIndex")[0]
    if ac is None:
        d = POWER_KEY + "\\PowerSettings\\%s\\%s\\DefaultPowerSchemeValues\\%s" % (sub, setting, scheme)
        ac, dc = reg_read("HKLM", d, "ACSettingIndex")[0], reg_read("HKLM", d, "DCSettingIndex")[0]
    if ac is None:
        return None
    return ac, (dc if dc is not None else ac)


def _powercfg_query(sub, setting):
    # /query non mostra le impostazioni NASCOSTE (core parking, boost, idle...): allora /qh e infine il registro
    for opt in ("/query", "/qh"):
        code, out = run(["powercfg", opt, "SCHEME_CURRENT", sub, setting])
        hexes = re.findall(r":\s*(0x[0-9a-fA-F]+)\s*$", out, re.M)
        if code == 0 and len(hexes) >= 2:
            return int(hexes[-2], 16), int(hexes[-1], 16)  # (AC, DC)
    return _powercfg_reg(sub, setting)


class PowerSettingTweak(Tweak):
    def __init__(self, *a, sub, setting, value, **kw):
        super().__init__(*a, **kw)
        self.sub, self.setting, self.value = sub, setting, value

    def status(self):
        q = _powercfg_query(self.sub, self.setting)
        return None if q is None else q[0] == self.value

    def _set(self, ac, dc):
        run(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", self.sub, self.setting, str(ac)])
        run(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", self.sub, self.setting, str(dc)])
        run(["powercfg", "/setactive", "SCHEME_CURRENT"])

    def apply(self):
        q = _powercfg_query(self.sub, self.setting)
        if q is None:
            raise RuntimeError("impostazione energetica non disponibile")
        self._set(self.value, self.value)
        return {"ac": q[0], "dc": q[1]}

    def revert(self, backup):
        self._set(backup["ac"], backup["dc"])


def _active_scheme():
    code, out = run(["powercfg", "/getactivescheme"])
    m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", out)
    return m.group(0).lower() if m else None


class PowerPlanTweak(Tweak):
    def __init__(self, *a, guid, duplicate=False, **kw):
        super().__init__(*a, **kw)
        self.guid, self.duplicate = guid, duplicate

    def _find(self):
        """Per Ultimate Performance Windows crea una copia con un GUID nuovo: la cerco per nome."""
        if not self.duplicate:
            return self.guid
        code, out = run(["powercfg", "/list"])
        for line in out.splitlines():
            if "ultimate" in line.lower() or "ottimal" in line.lower() or self.guid in line.lower():
                m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", line)
                if m:
                    return m.group(0).lower()
        return None

    def status(self):
        g = self._find()
        return g is not None and _active_scheme() == g

    def apply(self):
        prev = _active_scheme()
        g = self._find()
        if g is None and self.duplicate:
            code, out = run(["powercfg", "-duplicatescheme", self.guid])
            m = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", out)
            g = m.group(0) if m else None
        if not g or run(["powercfg", "/setactive", g])[0] != 0:
            raise RuntimeError("non riesco ad attivare il piano energetico")
        return {"prev": prev}

    def revert(self, backup):
        if backup.get("prev"):
            run(["powercfg", "/setactive", backup["prev"]])


class CmdTweak(Tweak):
    """Comandi PowerShell. check deve stampare True se l'ottimizzazione e' attiva."""

    def __init__(self, *a, on, off, check, after_check=None, **kw):
        super().__init__(*a, **kw)
        self.on, self.off, self.check, self.after_check = on, off, check, after_check

    def status(self):
        code, out = ps(self.check)
        last = out.strip().splitlines()[-1].strip().lower() if out.strip() else ""
        if last in ("true", "false"):
            return last == "true"
        return None

    def apply(self):
        code, out = ps(self.on, timeout=120)
        if self.status() is False:
            raise RuntimeError(self.after_check or ("comando non riuscito: " + out[-300:]))
        return {}

    def revert(self, backup):
        ps(self.off, timeout=120)


class BcdTweak(Tweak):
    def __init__(self, *a, option, value, **kw):
        super().__init__(*a, **kw)
        self.option, self.value = option, value

    def status(self):
        code, out = run(["bcdedit", "/enum", "{current}"])
        if code != 0:
            return None
        for line in out.splitlines():
            parts = line.split()
            if parts and parts[0].lower() == self.option:
                v, want = parts[-1].lower(), self.value.lower()
                if want in ("yes", "true"):  # bcdedit in italiano scrive "Si'" (anche con l'accento rovinato)
                    return v in ("yes", "true") or v.startswith("s")
                return v == want
        return False

    def apply(self):
        code, out = run(["bcdedit", "/set", "{current}", self.option, self.value])
        if code != 0:
            raise RuntimeError(out)
        return {}

    def revert(self, backup):
        run(["bcdedit", "/deletevalue", "{current}", self.option])


class DxUserSettingTweak(Tweak):
    """Modifica una voce dentro DirectXUserGlobalSettings (stringa tipo 'A=1;B=0;')."""
    PATH = r"Software\Microsoft\DirectX\UserGpuPreferences"
    NAME = "DirectXUserGlobalSettings"

    def __init__(self, *a, key, value, **kw):
        super().__init__(*a, **kw)
        self.key, self.value = key, value

    def _parse(self):
        v, _ = reg_read("HKCU", self.PATH, self.NAME)
        items = {}
        for part in (v or "").split(";"):
            if "=" in part:
                k, val = part.split("=", 1)
                items[k.strip()] = val.strip()
        return v, items

    def status(self):
        return self._parse()[1].get(self.key) == self.value

    def apply(self):
        raw, items = self._parse()
        items[self.key] = self.value
        reg_write("HKCU", self.PATH, self.NAME, SZ, "".join("%s=%s;" % kv for kv in items.items()))
        return {"raw": raw}

    def revert(self, backup):
        if backup.get("raw") is None:
            reg_delete("HKCU", self.PATH, self.NAME)
        else:
            reg_write("HKCU", self.PATH, self.NAME, SZ, backup["raw"])


class DefenderExclusionTweak(Tweak):
    """Esclude la cartella dei giochi dalla scansione in tempo reale di Defender."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.path = None  # impostato dall'interfaccia prima di apply

    def status(self):
        """Attiva se almeno una cartella di giochi trovata sul PC e' gia' esclusa da Defender (da chiunque)."""
        code, out = ps("(Get-MpPreference -ErrorAction Stop).ExclusionPath; 'FINE'", timeout=30)
        if "FINE" not in out:
            return None
        excl = [os.path.normcase(l.strip().rstrip("\\")) for l in out.splitlines()
                if l.strip() and l.strip() != "FINE" and ":" in l]
        try:
            from . import games
            dirs = [os.path.normcase(g["dir"]) for g in games.detect() if g.get("dir")]
        except Exception:
            dirs = []
        if not excl:
            return False
        if not dirs:
            return None
        return any(d == e or d.startswith(e + os.sep) for d in dirs for e in excl)

    def apply(self):
        if not self.path or not os.path.isdir(self.path):
            raise RuntimeError("cartella non valida")
        code, out = ps("Add-MpPreference -ExclusionPath '%s'" % self.path.replace("'", "''"))
        if code != 0:
            raise RuntimeError(out[-300:])
        return {"path": self.path}

    def revert(self, backup):
        ps("Remove-MpPreference -ExclusionPath '%s'" % backup["path"].replace("'", "''"))


def _nagle_values():
    """Le interfacce di rete con un indirizzo IP (quelle davvero in uso)."""
    base = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
    vals = []
    if winreg is None:
        return vals
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
    except OSError:
        return vals
    i = 0
    while True:
        try:
            sub = winreg.EnumKey(k, i)
        except OSError:
            break
        i += 1
        ip = reg_read("HKLM", base + "\\" + sub, "DhcpIPAddress")[0] or reg_read("HKLM", base + "\\" + sub,
                                                                                 "IPAddress")[0]
        if isinstance(ip, list):
            ip = ip[0] if ip else None
        if ip and ip != "0.0.0.0":
            vals.append(("HKLM", base + "\\" + sub, "TcpAckFrequency", DWORD, 1))
            vals.append(("HKLM", base + "\\" + sub, "TCPNoDelay", DWORD, 1))
    return vals


# ================================================================ il catalogo

MM = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
SUB_PROC = "54533251-82be-4824-96c1-47b60b740d00"
SUB_USB = "2a737441-1930-4402-8d77-b2bebba308a3"


def _ram_gb(s):
    return s.get("ram_gb") or 0


def _vendor(s):
    return ((s.get("gpu") or {}).get("vendor"))


def _nvidia_40plus(s):
    n = ((s.get("gpu") or {}).get("name") or "").lower()
    return _vendor(s) == "nvidia" and bool(re.search(r"rtx\s*(40|50)\d\d", n))


_TCPIP6 = r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters"

CATALOG = [
    # ------------------------------------------------------------ GIOCO
    RegTweak("game_dvr", "Gioco", "Disattiva registrazione Xbox Game Bar",
             "Windows registra in continuo gli ultimi secondi di gioco usando GPU e disco. Causa nota di "
             "micro-scatti.", "media",
             values=[("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", DWORD, 0),
                     ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", DWORD, 0)],
             harm_if_off=True),
    RegTweak("game_mode", "Gioco", "Attiva Modalita' Gioco",
             "Windows da' priorita' al gioco e rimanda aggiornamenti e attivita' in background.", "media",
             values=[("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", DWORD, 1),
                     ("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", DWORD, 1)],
             harm_if_off=True),
    DxUserSettingTweak("windowed_opt", "Gioco", "Ottimizzazioni per giochi in finestra",
                       "Fa usare il 'flip model' moderno ai giochi DX10/DX11 in finestra/borderless: meno "
                       "latenza e frame pacing migliore, supporto a VRR.", "media",
                       key="SwapEffectUpgradeEnable", value="1"),
    RegTweak("hags", "Gioco", "Attiva HAGS (pianificazione GPU hardware)",
             "La GPU gestisce da sola la coda dei frame. Necessaria per DLSS Frame Generation. In alcuni "
             "giochi migliora, in altri peggiora: provala con il test prima/dopo.", "media", risk=1, reboot=True,
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", DWORD, 2)],
             group="hags", recommend=lambda s: True if _nvidia_40plus(s) else None),
    RegTweak("fso_off", "Gioco", "Disattiva ottimizzazioni schermo intero (globale)",
             "Forza il vero schermo intero esclusivo nei giochi che lo usano. Effetto molto variabile, puo' "
             "rompere Auto HDR e l'Alt+Tab veloce.", "dubbia", risk=1,
             values=[("HKCU", r"System\GameConfigStore", "GameDVR_FSEBehaviorMode", DWORD, 2),
                     ("HKCU", r"System\GameConfigStore", "GameDVR_HonorUserFSEBehaviorMode", DWORD, 1),
                     ("HKCU", r"System\GameConfigStore", "GameDVR_FSEBehavior", DWORD, 2),
                     ("HKCU", r"System\GameConfigStore", "GameDVR_DXGIHonorFSEWindowsCompatible", DWORD, 1)]),
    RegTweak("mpo_off", "Gioco", "Disattiva MPO (Multiplane Overlay)",
             "Correzione nota per sfarfallii e scatti in borderless, soprattutto con piu' monitor o con "
             "monitor a frequenze diverse. Se non hai questi problemi non serve. Su alcune versioni recenti "
             "di Windows 11 potrebbe non avere effetto.", "media", risk=1, reboot=True,
             values=[("HKLM", r"SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", DWORD, 5)],
             group="mpo", recommend=lambda s: None),
    RegTweak("mmcss_games", "Gioco", "Priorita' alta ai giochi (MMCSS)",
             "Alza la priorita' CPU/GPU dei giochi che si registrano al servizio multimediale di Windows. "
             "Molti giochi non lo usano.", "dubbia", risk=1,
             values=[("HKLM", MM + r"\Tasks\Games", "GPU Priority", DWORD, 8),
                     ("HKLM", MM + r"\Tasks\Games", "Priority", DWORD, 6),
                     ("HKLM", MM + r"\Tasks\Games", "Scheduling Category", SZ, "High"),
                     ("HKLM", MM + r"\Tasks\Games", "SFIO Priority", SZ, "High")]),

    # ------------------------------------------------------------ CPU / ENERGIA
    PowerPlanTweak("plan_high", "CPU ed energia", "Piano energetico 'Prestazioni elevate'",
                   "La CPU resta a frequenze alte. Sui Ryzen recenti il piano Bilanciato va gia' bene: "
                   "differenza piccola.", "bassa", guid="8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", group="plan"),
    PowerPlanTweak("plan_ultimate", "CPU ed energia", "Piano energetico 'Prestazioni ottimali' (Ultimate)",
                   "Come Prestazioni elevate ma senza alcun risparmio. Consuma di piu' anche a riposo.",
                   "bassa", risk=1, guid="e9a42b02-d5df-448d-aa00-03f14749eb61", duplicate=True, group="plan",
                   recommend=lambda s: None),
    PowerSettingTweak("core_parking", "CPU ed energia", "Disattiva core parking",
                      "Tiene sempre attivi tutti i core invece di 'parcheggiarli'. Utile soprattutto su "
                      "CPU Intel ibride vecchie e laptop.", "bassa",
                      sub=SUB_PROC, setting="0cc5b647-c1df-4637-891a-dec35c318583", value=100),
    RegTweak("power_throttling", "CPU ed energia", "Disattiva Power Throttling",
             "Impedisce a Windows di rallentare i processi in background (es. Discord, OBS) per "
             "risparmiare energia.", "bassa",
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling",
                      "PowerThrottlingOff", DWORD, 1)]),
    PowerSettingTweak("usb_suspend", "CPU ed energia", "Disattiva sospensione selettiva USB",
                      "Evita che mouse, tastiera o cuffie USB vengano messi in risparmio energetico (puo' "
                      "causare micro-blocchi dell'input).", "media",
                      sub=SUB_USB, setting="48e6b7a6-50f5-4782-a5d4-53bb8f07e226", value=0),
    RegTweak("prio_sep", "CPU ed energia", "Win32PrioritySeparation = 26 (hex)",
             "Da' piu' tempo CPU alla finestra in primo piano. Tweak molto diffuso ma con benefici non "
             "dimostrati su Windows 11.", "dubbia", risk=1,
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\PriorityControl",
                      "Win32PrioritySeparation", DWORD, 0x26)], group="w32ps"),
    RegTweak("sys_resp", "CPU ed energia", "SystemResponsiveness = 10",
             "Riduce la CPU riservata alle attivita' di sottofondo del servizio multimediale (default 20%).",
             "dubbia", risk=1, values=[("HKLM", MM, "SystemResponsiveness", DWORD, 10)]),
    BcdTweak("dynamic_tick", "CPU ed energia", "Disattiva dynamic tick",
             "Il timer di sistema scatta sempre invece che solo quando serve. Effetti misurati minimi, "
             "a volte negativi.", "dubbia", risk=2, reboot=True,
             warning="Modifica il boot di Windows. Se usi BitLocker, al riavvio potrebbe chiederti la chiave "
                     "di ripristino: assicurati di averla.",
             option="disabledynamictick", value="yes"),

    # ------------------------------------------------------------ MEMORIA E DISCO
    CmdTweak("mem_compress", "Memoria e disco", "Disattiva compressione della memoria",
             "Windows non comprime piu' la RAM: meno lavoro CPU. Ha senso solo con 32 GB o piu'.", "bassa",
             risk=1, reboot=True,
             on="Disable-MMAgent -MemoryCompression", off="Enable-MMAgent -MemoryCompression",
             check="-not (Get-MMAgent).MemoryCompression",
             recommend=lambda s: True if _ram_gb(s) >= 31 else False),
    ServiceTweak("sysmain", "Memoria e disco", "Disattiva SysMain (Superfetch)",
                 "Smette di precaricare programmi in RAM. Su SSD il beneficio e' minimo; riduce attivita' "
                 "di disco in background.", "bassa", risk=1, service="SysMain"),
    ServiceTweak("wsearch", "Memoria e disco", "Disattiva indicizzazione di Windows Search",
                 "Niente piu' indicizzazione in background. La ricerca nel menu Start e in Esplora file "
                 "diventa piu' lenta.", "bassa", risk=1, service="WSearch"),
    CmdTweak("hibernation", "Memoria e disco", "Disattiva ibernazione e avvio rapido",
             "Libera spazio (file hiberfil.sys grande quanto la RAM) e fa ripartire Windows 'pulito' a ogni "
             "accensione, utile se dopo giorni di uso il PC scatta di piu'.", "bassa",
             on="powercfg -h off", off="powercfg -h on",
             check="-not (Test-Path \"$env:SystemDrive\\hiberfil.sys\" -ErrorAction SilentlyContinue)"),
    DefenderExclusionTweak("defender_excl", "Memoria e disco", "Escludi la cartella dei giochi da Defender",
                           "Defender non scansiona i file del gioco mentre vengono caricati: meno stutter da "
                           "streaming e caricamenti piu' veloci.", "media", risk=1,
                           warning="I file in quella cartella non vengono piu' controllati in tempo reale: "
                                   "metti solo cartelle di giochi da store ufficiali.",
                           recommend=lambda s: None),

    # ------------------------------------------------------------ RETE
    RegTweak("delivery_opt", "Rete", "Disattiva condivisione aggiornamenti P2P",
             "Windows non usa la tua connessione per inviare aggiornamenti ad altri PC su Internet.",
             "media", values=[("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization",
                               "DODownloadMode", DWORD, 0)]),
    CmdTweak("nic_power", "Rete", "Disattiva risparmio energetico della scheda di rete",
             "Evita che la scheda di rete (soprattutto Wi-Fi) vada in risparmio causando picchi di ping.",
             "media",
             on="Get-NetAdapter -Physical | Disable-NetAdapterPowerManagement -NoRestart",
             off="Get-NetAdapter -Physical | Enable-NetAdapterPowerManagement -NoRestart",
             check="$a = Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Get-NetAdapterPowerManagement "
                   "-ErrorAction SilentlyContinue; if (-not $a) { 'unknown' } else "
                   "{ -not ($a | Where-Object { $_.AllowComputerToTurnOffDevice -eq 'Enabled' }) }"),
    RegTweak("nagle", "Rete", "Disattiva algoritmo di Nagle",
             "Invia subito i piccoli pacchetti TCP. Aiuta solo i giochi che usano TCP (alcuni MMO, vecchi "
             "giochi); la maggior parte degli sparatutto usa UDP e non cambia nulla.", "bassa", risk=1,
             values=_nagle_values, recommend=lambda s: None),
    RegTweak("net_throttle", "Rete", "Disattiva Network Throttling",
             "Toglie il limite ai pacchetti di rete mentre riproduci audio/video. In un test pubblicato e' "
             "stato l'unico tweak di rete a ridurre il ping (Marvel Rivals); in altri giochi nessun effetto.", "bassa", risk=1,
             values=[("HKLM", MM, "NetworkThrottlingIndex", DWORD, 0xFFFFFFFF)]),

    # ------------------------------------------------------------ INTERFACCIA
    RegTweak("mouse_accel", "Interfaccia e input", "Disattiva accelerazione del mouse",
             "La mira dipende solo da quanto muovi il mouse, non dalla velocita'. Fondamentale negli "
             "sparatutto. Effetto dopo il riavvio o la disconnessione.", "alta", reboot=True,
             values=[("HKCU", r"Control Panel\Mouse", "MouseSpeed", SZ, "0"),
                     ("HKCU", r"Control Panel\Mouse", "MouseThreshold1", SZ, "0"),
                     ("HKCU", r"Control Panel\Mouse", "MouseThreshold2", SZ, "0")],
             harm_if_off=True),
    RegTweak("bg_apps", "Interfaccia e input", "Blocca le app in background (Store)",
             "Le app dello Store non girano piu' in background.", "bassa",
             values=[("HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                      "GlobalUserDisabled", DWORD, 1)]),
    RegTweak("transparency", "Interfaccia e input", "Disattiva effetti di trasparenza",
             "Meno lavoro per il compositore di Windows. Nessun effetto dentro i giochi a schermo intero.",
             "bassa", values=[("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                               "EnableTransparency", DWORD, 0)]),
    ServiceTweak("diagtrack", "Interfaccia e input", "Disattiva telemetria (servizio DiagTrack)",
                 "Ferma l'invio di dati diagnostici a Microsoft e la relativa attivita' in background.",
                 "bassa", risk=1, service="DiagTrack"),

    # ------------------------------------------------------------ PERICOLOSE
    RegTweak("vbs_off", "Sicurezza (PERICOLOSE)", "Disattiva VBS / Integrita' della memoria",
             "Spegne la sicurezza basata su virtualizzazione: +0-10% FPS in alcuni giochi.", "media",
             risk=3, reboot=True,
             warning="Riduce la protezione da malware a livello kernel. Alcuni anti-cheat o funzioni "
                     "aziendali potrebbero richiederla. Se il blocco e' impostato dal BIOS/UEFI potrebbe "
                     "non avere effetto.",
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\DeviceGuard",
                      "EnableVirtualizationBasedSecurity", DWORD, 0),
                     ("HKLM", r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios"
                              r"\HypervisorEnforcedCodeIntegrity", "Enabled", DWORD, 0)],
             recommend=lambda s: None),
    RegTweak("mitigations_off", "Sicurezza (PERICOLOSE)", "Disattiva protezioni Spectre/Meltdown",
             "Toglie le mitigazioni software delle vulnerabilita' della CPU. Sui Ryzen recenti il guadagno "
             "e' quasi nullo; sulle CPU Intel piu' vecchie puo' essere qualche %.", "bassa",
             risk=3, reboot=True,
             warning="Il PC diventa vulnerabile ad attacchi che leggono la memoria (anche da siti web "
                     "malevoli). Sconsigliato se usi il PC per banca, lavoro o dati importanti.",
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
                      "FeatureSettingsOverride", DWORD, 3),
                     ("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
                      "FeatureSettingsOverrideMask", DWORD, 3)],
             recommend=lambda s: None),
    CmdTweak("defender_rt_off", "Sicurezza (PERICOLOSE)", "Disattiva protezione in tempo reale di Defender",
             "Defender smette di scansionare i file mentre vengono aperti. Per i giochi e' meglio "
             "l'esclusione della cartella (piu' sicura).", "bassa", risk=3,
             warning="Il PC non e' piu' protetto dai virus in tempo reale. Windows potrebbe riattivarla da "
                     "solo dopo un po' o al riavvio.",
             on="Set-MpPreference -DisableRealtimeMonitoring $true",
             off="Set-MpPreference -DisableRealtimeMonitoring $false",
             check="-not (Get-MpComputerStatus).RealTimeProtectionEnabled",
             after_check="Windows ha bloccato la modifica: disattiva prima 'Protezione antimanomissione' in "
                         "Sicurezza di Windows > Protezione da virus e minacce > Gestisci impostazioni, "
                         "poi riprova.",
             recommend=lambda s: None),
    RegTweak("wu_auto_off", "Sicurezza (PERICOLOSE)", "Blocca gli aggiornamenti automatici di Windows",
             "Windows non scarica ne' installa aggiornamenti da solo (niente download durante le partite). "
             "Dovrai aggiornare a mano da Impostazioni > Windows Update.", "media", risk=3,
             warning="Senza aggiornamenti le falle di sicurezza restano aperte. Ricordati di aggiornare a "
                     "mano almeno una volta al mese.",
             values=[("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", "NoAutoUpdate", DWORD, 1)],
             recommend=lambda s: None),
]

BY_ID = {t.id: t for t in CATALOG}

# Ottimizzazioni famose che NON applico perche' peggiorano le cose o sono inutili
MYTHS = [
    ("Disattivare il file di paging", "Con meno RAM libera i giochi vanno in crash invece di rallentare. "
     "Nessun guadagno di FPS."),
    ("Forzare l'HPET (bcdedit useplatformclock)", "Aumenta la latenza del timer: e' dimostrato che "
     "PEGGIORA FPS e stutter sui PC moderni."),
    ("Programmi 'pulisci RAM' / svuota standby", "Windows usa la RAM libera come cache: svuotarla fa "
     "ricaricare dati dal disco e puo' causare piu' stutter."),
    ("Disattivare decine di servizi a caso", "Rompe Windows Update, audio, Bluetooth, Xbox/Game Pass e "
     "anti-cheat, con guadagni non misurabili."),
    ("TCP autotuning disattivato / 'ottimizzatori di rete'", "Peggiora la velocita' di download e non "
     "riduce il ping dei giochi."),
    ("Forzare la modalita' MSI per la scheda video", "I driver NVIDIA e AMD moderni la usano gia'. "
     "Cambiarla sul dispositivo sbagliato puo' impedire l'avvio di Windows."),
]


# ================================================================ TWEAK FAMOSI (community)
# Efficacia valutata in base ai test pubblici trovati: la maggior parte non ha benchmark seri.
# Il modo giusto per sapere se servono sul TUO PC e' il test prima/dopo.

MEM = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
MEM_KEY = MEM
SUB_PCIE = "501a4d13-42af-4429-9fd1-a8218c268e20"


class VisualFxTweak(Tweak):
    """Effetti visivi come in 'Impostazioni di sistema avanzate > Prestazioni > Effetti visivi': tutte le caselle
    spente tranne 'Smussa gli angoli dei caratteri' e 'Mostra anteprime anziche' icone'.

    Le caselle sono salvate quasi tutte in UserPreferencesMask: le cambio con SystemParametersInfo (come fa la
    finestra di Windows), cosi' l'effetto e' immediato e il valore viene salvato. Il resto e' nel registro.
    Annulla rimette ogni casella com'era (e anche il valore UserPreferencesMask originale)."""
    # (nome, SPI_GET, SPI_SET, modo): "pv" = valore in pvParam, "ui" = valore in uiParam
    SPI = [("animazioni dentro le finestre", 0x1042, 0x1043, "pv"),
           ("dissolvenza/scorrimento dei menu", 0x1002, 0x1003, "pv"),
           ("dissolvenza dei menu", 0x1012, 0x1013, "pv"),
           ("dissolvenza delle voci dopo il clic", 0x1014, 0x1015, "pv"),
           ("descrizioni comandi animate", 0x1016, 0x1017, "pv"),
           ("dissolvenza delle descrizioni", 0x1018, 0x1019, "pv"),
           ("caselle combinate a scorrimento", 0x1004, 0x1005, "pv"),
           ("scorrimento fluido degli elenchi", 0x1006, 0x1007, "pv"),
           ("ombra sotto il puntatore", 0x101A, 0x101B, "pv"),
           ("ombre sotto le finestre", 0x1024, 0x1025, "pv"),
           ("contenuto della finestra durante il trascinamento", 0x0026, 0x0025, "ui")]
    ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
    REG = [("HKCU", ADV, "ListviewAlphaSelect", DWORD, 0),          # rettangolo di selezione trasparente
           ("HKCU", ADV, "ListviewShadow", DWORD, 0),               # ombre sotto le etichette del desktop
           ("HKCU", ADV, "TaskbarAnimations", DWORD, 0),            # animazioni della barra
           ("HKCU", ADV, "IconsOnly", DWORD, 0),                    # anteprime: RESTANO attive
           ("HKCU", r"Software\Microsoft\Windows\DWM", "EnableAeroPeek", DWORD, 0),
           ("HKCU", r"Software\Microsoft\Windows\DWM", "AlwaysHibernateThumbnails", DWORD, 0),
           ("HKCU", r"Control Panel\Desktop\WindowMetrics", "MinAnimate", SZ, "0"),
           ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", DWORD, 3)]

    def _u32(self):
        import ctypes
        u = ctypes.windll.user32
        u.SystemParametersInfoW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        return ctypes, u

    def _get(self, get_id):
        ctypes, u = self._u32()
        v = ctypes.c_int(0)
        if not u.SystemParametersInfoW(get_id, 0, ctypes.byref(v), 0):
            return None
        return bool(v.value)

    def _set(self, set_id, mode, value):
        ctypes, u = self._u32()
        flags = 0x01 | 0x02  # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE: salva e applica subito
        if mode == "ui":
            return bool(u.SystemParametersInfoW(set_id, int(value), None, flags))
        return bool(u.SystemParametersInfoW(set_id, 0, ctypes.c_void_p(1 if value else 0), flags))

    def _min_animate(self, value=None):
        ctypes, u = self._u32()

        class AI(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("iMinAnimate", ctypes.c_int)]
        a = AI(ctypes.sizeof(AI), 0)
        if value is None:
            return bool(a.iMinAnimate) if u.SystemParametersInfoW(0x0048, a.cbSize, ctypes.byref(a), 0) else None
        a.iMinAnimate = 1 if value else 0
        return bool(u.SystemParametersInfoW(0x0049, a.cbSize, ctypes.byref(a), 0x03))

    def status(self):
        """Attiva se gli effetti sono davvero spenti in Windows (animazioni, ombre, dissolvenze, trascinamento...),
        comunque siano stati spenti: a mano dalla finestra di Windows, da un altro programma o da LagDoctor.
        Le caselle che LagDoctor lascia accese (caratteri smussati, anteprime) non contano."""
        try:
            states = [self._get(g) for _n, g, _s, _m in self.SPI] + [self._min_animate()]
        except Exception:
            return None
        if any(x is None for x in states):
            return None
        return not any(states)

    def apply(self):
        upm, _t = reg_read("HKCU", r"Control Panel\Desktop", "UserPreferencesMask")
        backup = {"spi": {}, "min": self._min_animate(), "reg": [], "upm": upm.hex() if isinstance(upm, bytes) else None}
        for _n, g, s, m in self.SPI:
            backup["spi"][str(s)] = [self._get(g), m]
        for h, p, n, t, v in self.REG:
            prev, ptype = reg_read(h, p, n)
            backup["reg"].append([h, p, n, ptype, prev])
        failed = [n for n, _g, s, m in self.SPI if not self._set(s, m, False)]
        self._min_animate(False)
        for h, p, n, t, v in self.REG:
            reg_write(h, p, n, t, v)
        if failed:
            raise RuntimeError("Windows non ha accettato: " + ", ".join(failed))
        return backup

    def revert(self, backup):
        if "spi" not in backup:  # voce applicata con una versione precedente (solo registro)
            RegTweak.revert(self, backup)
            return
        for s, (prev, m) in backup.get("spi", {}).items():
            if prev is not None:
                self._set(int(s), m, prev)
        if backup.get("min") is not None:
            self._min_animate(backup["min"])
        for h, p, n, ptype, prev in backup.get("reg", []):
            if prev is None:
                reg_delete(h, p, n)
            else:
                reg_write(h, p, n, ptype, prev)
        if backup.get("upm"):
            reg_write("HKCU", r"Control Panel\Desktop", "UserPreferencesMask", 3, bytes.fromhex(backup["upm"]))


def installed_ram_kb():
    """RAM INSTALLATA in KB (es. 32 GB = 33554432 = 0x2000000), non quella utilizzabile (un po' meno)."""
    try:
        import ctypes
        kb = ctypes.c_ulonglong(0)
        if ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(kb)) and kb.value:
            return int(kb.value)
    except Exception:
        pass
    try:  # riserva: arrotondo la RAM utilizzabile al GB pieno superiore
        import math
        import psutil
        return int(math.ceil(psutil.virtual_memory().total / 2**30)) * 1024 * 1024
    except Exception:
        return None


def _svchost_values():
    kb = installed_ram_kb()
    if not kb:
        return []
    return [("HKLM", r"SYSTEM\CurrentControlSet\Control", "SvcHostSplitThresholdInKB", DWORD, min(kb, 0xFFFFFFFF))]


class SvcHostTweak(RegTweak):
    """Attiva se la soglia e' uguale o MAGGIORE della RAM installata (Windows raggruppa i servizi)."""

    def status(self):
        kb = installed_ram_kb()
        if not kb:
            return None
        cur = reg_read("HKLM", r"SYSTEM\CurrentControlSet\Control", "SvcHostSplitThresholdInKB")[0]
        return isinstance(cur, int) and cur >= kb


def _nic_prop(keyword, value):
    """Comandi PowerShell per una proprieta' avanzata standard delle schede di rete cablate/Wi-Fi."""
    sel = ("Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Get-NetAdapterAdvancedProperty "
           "-RegistryKeyword '%s' -ErrorAction SilentlyContinue" % keyword)
    return dict(
        on="%s | Set-NetAdapterAdvancedProperty -RegistryValue %s -NoRestart" % (sel, value),
        off="%s | Reset-NetAdapterAdvancedProperty -NoRestart" % sel,
        check="$p = @(%s); if ($p.Count -eq 0) { 'unknown' } else { -not ($p | Where-Object "
              "{ $_.RegistryValue -ne '%s' }) }" % (sel, value))


FAMOUS = [
    # ---------------------------------------------------- GPU e schermo
    PowerSettingTweak("pcie_aspm", "Gioco", "Disattiva risparmio energetico PCI Express (ASPM)",
                      "La scheda video e gli SSD NVMe non entrano in risparmio energetico sul bus PCIe. "
                      "Correzione nota per micro-scatti e 'risvegli' lenti della GPU.", "media",
                      sub=SUB_PCIE, setting="ee12f906-d277-404b-b6da-e5fa1a576df5", value=0,
                      source="Consigliato da molte guide di tuning e da NVIDIA per alcuni problemi di stutter"),
    RegTweak("mpo_full", "Gioco", "Disattiva MPO completamente (anche overlay del driver)",
             "Versione completa della disattivazione MPO usata da WinUtil (Chris Titus Tech).", "dubbia",
             risk=1, reboot=True, group="mpo",
             values=[("HKLM", r"SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", DWORD, 5),
                     ("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "DisableOverlays", DWORD, 1)],
             recommend=lambda s: None, source="WinUtil"),
    RegTweak("gamedvr_policy", "Gioco", "Blocca Game DVR anche a livello di sistema (criterio)",
             "Come 'Disattiva registrazione Xbox Game Bar' ma per tutti gli utenti e non riattivabile "
             "dall'app Xbox.", "media",
             values=[("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR", DWORD, 0)]),
    RegTweak("gamebar_shortcut", "Gioco", "Disattiva l'apertura di Game Bar con Win+G / tasto Xbox",
             "Evita che la Game Bar si apra per sbaglio durante il gioco (con i controller Xbox succede "
             "spesso).", "comfort",
             values=[("HKCU", r"Software\Microsoft\GameBar", "UseNexusForGameBarEnabled", DWORD, 0)]),
    RegTweak("timer_global", "CPU ed energia", "GlobalTimerResolutionRequests",
             "Da Windows 11 la risoluzione del timer vale solo per il programma che la chiede. Con questo "
             "valore torna globale (come su Windows 7). Serve solo se usi tool tipo TimerResolution; "
             "aumenta un po' i consumi.", "dubbia", risk=1, reboot=True,
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel",
                      "GlobalTimerResolutionRequests", DWORD, 1)],
             recommend=lambda s: None, source="valleyofdoom/TimerResolution, forum Blur Busters"),
    RegTweak("prio_sep_2a", "CPU ed energia", "Win32PrioritySeparation = 2A (hex)",
             "Variante popolare (quanti brevi e fissi, massimo boost alla finestra in primo piano). Scegli "
             "26 o 2A: si escludono a vicenda. Gli unici test pubblici sono di singoli utenti.", "dubbia",
             risk=1, group="w32ps",
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\PriorityControl",
                      "Win32PrioritySeparation", DWORD, 0x2A)]),
    PowerSettingTweak("boost_aggr", "CPU ed energia", "Modalita' boost processore: Aggressiva",
                      "La CPU sale di frequenza appena serve. Sui desktop spesso e' gia' cosi'.", "bassa",
                      sub=SUB_PROC, setting="be337238-0d82-4146-a960-4f3749d470c7", value=2),
    PowerSettingTweak("min_cpu_100", "CPU ed energia", "Stato minimo processore al 100%",
                      "La CPU non scende mai di frequenza. Piu' calore e consumi; sui Ryzen moderni il "
                      "guadagno e' minimo perche' la frequenza la gestisce la CPU stessa.", "bassa", risk=1,
                      sub=SUB_PROC, setting="893dee8e-2bef-41e0-89c6-b55d0929964c", value=100,
                      recommend=lambda s: None),
    PowerSettingTweak("idle_off", "CPU ed energia", "Disattiva l'idle della CPU (C-states)",
                      "La CPU non va mai in riposo: latenza minima, usato nei setup competitivi estremi. "
                      "La CPU resta SEMPRE al 100% di utilizzo apparente e scalda molto.", "dubbia", risk=2,
                      warning="Temperature e consumi molto piu' alti anche a riposo. Sui Ryzen puo' ridurre il "
                              "boost (meno margine termico) e quindi gli FPS. Non lasciarlo attivo se non "
                              "vedi benefici nel test prima/dopo.",
                      sub=SUB_PROC, setting="5d76a2ca-e8c0-402f-a133-2158492d58ad", value=1,
                      recommend=lambda s: None),
    BcdTweak("hypervisor_off", "CPU ed energia", "Disattiva l'hypervisor di Windows (Hyper-V)",
             "Spegne la virtualizzazione di Windows: elimina il costo di VBS e Hyper-V. Disattiva anche "
             "WSL2, Sandbox, le macchine virtuali e l'Integrita' della memoria.", "media", risk=2, reboot=True,
             warning="Smettono di funzionare WSL2, Docker, Windows Sandbox e alcuni emulatori Android. "
                     "Se usi BitLocker tieni a portata la chiave di ripristino.",
             option="hypervisorlaunchtype", value="off", recommend=lambda s: None,
             source="Tom's Hardware: VBS costa fino al 10% di FPS"),

    # ---------------------------------------------------- memoria, disco, file system
    RegTweak("paging_exec", "Memoria e disco", "DisablePagingExecutive",
             "Tiene driver e kernel sempre in RAM invece di spostarli nel file di paging. Con 16 GB o piu' "
             "non fa danni; benefici non misurati.", "dubbia", risk=1, reboot=True,
             values=[("HKLM", MEM, "DisablePagingExecutive", DWORD, 1)],
             recommend=lambda s: None),
    RegTweak("prefetch_off", "Memoria e disco", "Disattiva Prefetcher",
             "Windows smette di preparare in anticipo i file dei programmi che usi spesso. Famoso dai tempi "
             "di Windows XP; su SSD l'effetto e' praticamente nullo, i programmi possono aprirsi piu' "
             "lentamente.", "dubbia", risk=1, reboot=True,
             values=[("HKLM", MEM + r"\PrefetchParameters", "EnablePrefetcher", DWORD, 0)],
             recommend=lambda s: None),
    SvcHostTweak("svchost_split", "Memoria e disco", "Riduci i processi svchost (SvcHostSplitThresholdInKB)",
                 "Imposta la soglia uguale alla RAM installata (es. 32 GB = 2000000 esadecimale): Windows "
                 "raggruppa i servizi in meno processi (da 80+ a ~30). Meno processi nel Task Manager, effetto "
                 "sulle prestazioni non dimostrato.", "dubbia", risk=1, reboot=True,
                 values=_svchost_values, recommend=lambda s: None, source="WinUtil (avanzati)"),
    RegTweak("ntfs_lastaccess", "Memoria e disco", "Disattiva aggiornamento 'ultimo accesso' NTFS",
             "Windows non scrive sul disco l'ora di ultimo accesso a ogni file letto. Meno scritture "
             "inutili quando un gioco legge migliaia di file.", "bassa",
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\FileSystem",
                      "NtfsDisableLastAccessUpdate", DWORD, 0x80000001)]),
    RegTweak("ntfs_83", "Memoria e disco", "Disattiva nomi file corti 8.3",
             "Non crea piu' i nomi tipo PROGRA~1 per ogni file. Piccolo risparmio nelle cartelle con molti "
             "file; qualche vecchio installer potrebbe non funzionare.", "bassa", risk=1,
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\FileSystem",
                      "NtfsDisable8dot3NameCreation", DWORD, 1)], recommend=lambda s: None),
    RegTweak("storage_sense_off", "Memoria e disco", "Disattiva Sensore memoria",
             "Windows non fa pulizie automatiche del disco (che possono partire mentre giochi).", "bassa",
             values=[("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy",
                      "01", DWORD, 0)]),

    # ---------------------------------------------------- rete
    CmdTweak("nic_intmod", "Rete", "Disattiva Interrupt Moderation della scheda di rete",
             "La scheda di rete avvisa subito la CPU per ogni pacchetto invece di raggrupparli: meno "
             "latenza, un po' piu' di uso CPU. Microsoft e Intel lo indicano per la latenza minima.",
             "bassa", risk=1, recommend=lambda s: None,
             source="Documentazione Microsoft e Intel sulla bassa latenza", **_nic_prop("*InterruptModeration", 0)),
    CmdTweak("nic_eee", "Rete", "Disattiva Energy Efficient Ethernet",
             "Il cavo di rete non va in risparmio energetico tra un pacchetto e l'altro. Su alcuni driver "
             "causa disconnessioni brevi o picchi di ping.", "media", **_nic_prop("*EEE", 0)),
    CmdTweak("nic_flow", "Rete", "Disattiva Flow Control della scheda di rete",
             "La scheda non mette in pausa la trasmissione quando il router e' sotto carico. Consigliato "
             "da molte guide, effetto non misurato.", "dubbia", risk=1, recommend=lambda s: None,
             **_nic_prop("*FlowControl", 0)),
    RegTweak("ipv4_pref", "Rete", "Preferisci IPv4 a IPv6",
             "Le connessioni usano IPv4 quando possibile. Utile se il tuo IPv6 e' instabile o 'tunnellato'; "
             "altrimenti nessun effetto.", "bassa", risk=1, reboot=True,
             # DisabledComponents e' una maschera di bit (Microsoft KB929852): si aggiunge solo 0x20 = preferisci
             # IPv4, senza cancellare gli altri bit gia' presenti (es. 0x01 tunnel IPv6 spenti).
             values=lambda: [("HKLM", _TCPIP6, "DisabledComponents", DWORD,
                              ((_int(reg_read("HKLM", _TCPIP6, "DisabledComponents")[0], 0) or 0) | 0x20) & 0xFFFFFFFF)],
             recommend=lambda s: None, source="WinUtil / Microsoft KB929852"),
    CmdTweak("teredo_off", "Rete", "Disattiva Teredo",
             "Spegne il tunnel IPv6 Teredo. Alcuni giochi Xbox/Game Pass lo usano per il multiplayer: se "
             "hai problemi di NAT nell'app Xbox, annulla.", "bassa", risk=1,
             on="netsh interface teredo set state disabled", off="netsh interface teredo set state default",
             check="(Get-NetTeredoConfiguration).Type -eq 'Disabled'", recommend=lambda s: None,
             source="WinUtil"),

    # ---------------------------------------------------- interfaccia, input, sfondo
    VisualFxTweak("visual_fx", "Interfaccia e input",
                  "Effetti visivi: prestazioni migliori (testo smussato e anteprime restano)",
                  "Come 'Impostazioni di sistema avanzate > Prestazioni > Effetti visivi': spegne animazioni, "
                  "ombre, dissolvenze, scorrimento fluido, trasparenze e Peek, tenendo attivi 'Smussa gli angoli dei "
                  "caratteri' e 'Mostra anteprime anziche' icone'. Effetto immediato (barra delle applicazioni e "
                  "desktop al prossimo accesso).", "bassa",
                  source="Microsoft (Opzioni prestazioni); XDA Developers; WinUtil"),
    RegTweak("menu_delay", "Interfaccia e input", "MenuShowDelay = 0",
             "I menu di Windows si aprono subito. Puramente estetico, nessun effetto sui giochi.", "comfort",
             values=[("HKCU", r"Control Panel\Desktop", "MenuShowDelay", SZ, "0")]),
    RegTweak("sticky_keys", "Interfaccia e input", "Disattiva la scorciatoia Tasti permanenti",
             "Premere Shift 5 volte non apre piu' la finestra dei Tasti permanenti (che ti butta fuori dal "
             "gioco).", "comfort",
             values=[("HKCU", r"Control Panel\Accessibility\StickyKeys", "Flags", SZ, "506")]),
    RegTweak("keyboard_fast", "Interfaccia e input", "Ripetizione tastiera piu' rapida",
             "Ritardo minimo e velocita' massima di ripetizione dei tasti tenuti premuti.", "comfort",
             values=[("HKCU", r"Control Panel\Keyboard", "KeyboardDelay", SZ, "0"),
                     ("HKCU", r"Control Panel\Keyboard", "KeyboardSpeed", SZ, "31")]),
    RegTweak("wait_kill_svc", "Interfaccia e input", "Spegnimento piu' rapido (WaitToKillServiceTimeout = 2000)",
             "Allo spegnimento Windows aspetta al massimo 2 secondi (invece di 5) che i servizi si chiudano da soli "
             "prima di chiuderli lui.", "comfort", risk=1, reboot=True,
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control", "WaitToKillServiceTimeout", SZ, "2000")],
             recommend=lambda s: None, source="XDA Developers; documentazione Microsoft"),
    RegTweak("startup_delay", "Interfaccia e input", "Elimina il ritardo dei programmi all'avvio",
             "Windows avvia subito i programmi di avvio invece di aspettare qualche secondo.", "comfort",
             values=[("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize",
                      "StartupDelayInMSec", DWORD, 0)]),
    RegTweak("notifications_off", "Interfaccia e input", "Disattiva le notifiche popup",
             "Niente popup di Windows e delle app sopra il gioco.", "comfort",
             values=[("HKCU", r"Software\Microsoft\Windows\CurrentVersion\PushNotifications",
                      "ToastEnabled", DWORD, 0)], recommend=lambda s: None),
    RegTweak("widgets_off", "Interfaccia e input", "Disattiva i Widget (notizie e meteo)",
             "Il pannello Widget non resta in background a scaricare notizie.", "bassa",
             values=[("HKLM", r"SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", DWORD, 0)]),
    RegTweak("edge_bg_off", "Interfaccia e input", "Impedisci a Edge di restare aperto in background",
             "Edge non si precarica all'avvio e non resta in memoria dopo la chiusura.", "bassa",
             values=[("HKLM", r"SOFTWARE\Policies\Microsoft\Edge", "StartupBoostEnabled", DWORD, 0),
                     ("HKLM", r"SOFTWARE\Policies\Microsoft\Edge", "BackgroundModeEnabled", DWORD, 0)]),
    RegTweak("recall_off", "Interfaccia e input", "Disattiva Recall / analisi AI degli screenshot",
             "Sui PC Copilot+ Windows salva e analizza screenshot continui. Su PC normali non fa nulla.",
             "bassa", values=[("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
                               "DisableAIDataAnalysis", DWORD, 1)]),
    RegTweak("telemetry_policy", "Interfaccia e input", "Telemetria e pubblicita' al minimo (criteri)",
             "Riduce raccolta dati, cronologia attivita', ID pubblicitario e app suggerite. Pochi effetti "
             "sulle prestazioni, meno attivita' in background.", "bassa", risk=1,
             values=[("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection",
                      "AllowTelemetry", DWORD, 0),
                     ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "EnableActivityFeed", DWORD, 0),
                     ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "PublishUserActivities", DWORD, 0),
                     ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "UploadUserActivities", DWORD, 0),
                     ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", DWORD, 0),
                     ("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\CloudContent",
                      "DisableWindowsConsumerFeatures", DWORD, 1)],
             source="WinUtil"),
    ServiceTweak("wersvc", "Interfaccia e input", "Disattiva Segnalazione errori Windows",
                 "Quando un programma va in crash Windows non raccoglie e invia il rapporto.", "bassa", risk=1,
                 service="WerSvc"),
    ServiceTweak("spooler", "Interfaccia e input", "Disattiva lo spooler di stampa",
                 "Da usare SOLO se non hai una stampante: dopo non potrai stampare.", "bassa", risk=1,
                 service="Spooler", recommend=lambda s: None),

    # ---------------------------------------------------- pericolose
    CmdTweak("bitlocker_off", "Sicurezza (PERICOLOSE)", "Disattiva BitLocker sul disco di sistema",
             "Decritta il disco: elimina il piccolo costo della crittografia software sugli SSD. La "
             "decrittazione richiede da minuti a ore.", "bassa", risk=3, reboot=False,
             warning="Se il PC viene rubato chiunque puo' leggere i tuoi file. Per riattivarla servira' "
                     "di nuovo la crittografia completa del disco.",
             on="Disable-BitLocker -MountPoint $env:SystemDrive",
             off="Enable-BitLocker -MountPoint $env:SystemDrive -TpmProtector",
             check="(Get-BitLockerVolume -MountPoint $env:SystemDrive).ProtectionStatus -eq 'Off'",
             recommend=lambda s: None, source="WinUtil"),
    RegTweak("uac_dimmed_off", "Sicurezza (PERICOLOSE)", "UAC senza oscuramento dello schermo",
             "Le richieste di amministratore non oscurano piu' lo schermo (niente cambio di desktop che "
             "puo' far uscire i giochi a schermo intero). La richiesta resta.", "comfort", risk=2,
             warning="Le finestre di conferma diventano piu' facili da falsificare da un malware.",
             values=[("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
                      "PromptOnSecureDesktop", DWORD, 0)], recommend=lambda s: None),
]

CATALOG.extend(FAMOUS)
CAT_ORDER = ["Gioco", "CPU ed energia", "Memoria e disco", "Rete", "Interfaccia e input", "Sicurezza (PERICOLOSE)"]
CATALOG.sort(key=lambda t: CAT_ORDER.index(t.cat))
BY_ID = {t.id: t for t in CATALOG}

MYTHS += [
    ("'Liberare il 20% di banda riservata da Windows' (NonBestEffortLimit / QoS)", "Windows non riserva banda "
     "se nessun programma usa il QoS: il tweak non cambia niente."),
    ("Cambiare DNS per abbassare il ping", "Il DNS serve solo a trovare l'indirizzo del server all'inizio: "
     "non cambia il ping durante la partita."),
    ("IRQ8Priority, LargeSystemCache=1, ConservativeSwapfileUsage", "Tweak di Windows XP: su Windows 10/11 "
     "le chiavi vengono ignorate o (LargeSystemCache) sono pensate per i server."),
]


# ================================================================ CORREZIONI
# Impostazioni che, se presenti, TOLGONO prestazioni o stabilita'. status() = True vuol dire "tutto a posto".

class ServiceEnableFix(ServiceTweak):
    """Riattiva un servizio importante se qualcuno lo ha disabilitato."""

    def status(self):
        v, _ = reg_read("HKLM", self.KEY + "\\" + self.service, "Start")
        return None if v is None else v != 4


class PowerSaverFix(PowerPlanTweak):
    def status(self):
        a = _active_scheme()
        return None if a is None else a != "a1841308-3541-4fab-bc81-f71556f20b4a"


FIX = "Correzioni (impostazioni che tolgono prestazioni)"

CORRECTIONS = [
    CmdTweak("fix_hpet", FIX, "Togli HPET forzato (useplatformclock)",
             "Qualcuno (o un 'ottimizzatore') ha forzato il timer HPET: sui PC moderni aumenta la latenza e "
             "PEGGIORA FPS e stutter.", "alta", reboot=True, kind="fix",
             on="bcdedit /deletevalue '{current}' useplatformclock",
             off="bcdedit /set '{current}' useplatformclock true",
             check="-not ((bcdedit /enum '{current}') -match 'useplatformclock')"),
    CmdTweak("fix_pagefile", FIX, "Riattiva il file di paging (gestione automatica)",
             "Il file di paging e' disattivato: quando la RAM si riempie i giochi vanno in crash o si "
             "bloccano invece di rallentare.", "alta", reboot=True, kind="fix",
             on="$c = Get-CimInstance Win32_ComputerSystem; Set-CimInstance -InputObject $c -Property "
                "@{AutomaticManagedPagefile = $true}",
             off="$c = Get-CimInstance Win32_ComputerSystem; Set-CimInstance -InputObject $c -Property "
                 "@{AutomaticManagedPagefile = $false}",
             check="(Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile -or "
                   "@(Get-CimInstance Win32_PageFileSetting).Count -gt 0"),
    CmdTweak("fix_autotuning", FIX, "Ripristina TCP Auto-Tuning",
             "L'auto-tuning della finestra TCP e' stato disattivato o limitato (tweak 'di rete' famoso): "
             "rallenta download e aggiornamenti senza migliorare il ping.", "media", kind="fix",
             on="netsh int tcp set global autotuninglevel=normal",
             off="netsh int tcp set global autotuninglevel=disabled",
             check="(Get-NetTCPSetting -SettingName Internet).AutoTuningLevelLocal -eq 'Normal'"),
    RegTweak("fix_largecache", FIX, "LargeSystemCache = 0",
             "La cache di sistema e' impostata in modalita' server: toglie RAM ai programmi.", "media",
             kind="fix", absent_ok=True,
             values=[("HKLM", MEM_KEY, "LargeSystemCache", DWORD, 0)]),
    RegTweak("fix_clearpagefile", FIX, "Non svuotare il file di paging allo spegnimento",
             "ClearPageFileAtShutdown e' attivo (tweak da vecchie guide): spegnimento molto piu' lento, "
             "nessun beneficio nei giochi.", "bassa", kind="fix", absent_ok=True,
             values=[("HKLM", MEM_KEY, "ClearPageFileAtShutdown", DWORD, 0)]),
    PowerSaverFix("fix_powersaver", FIX, "Esci dal piano 'Risparmio energia'",
                  "Il piano Risparmio energia limita CPU e GPU. Passa al piano Bilanciato.", "alta",
                  kind="fix", guid="381b4222-f694-41f0-9685-ff5bb260df2e"),
    RegTweak("fix_hags_off_40", FIX, "Attiva HAGS (la tua scheda lo richiede)",
             "Con le RTX 40/50 HAGS serve per DLSS Frame Generation e in genere riduce la latenza.", "media",
             kind="fix", reboot=True, group="hags",
             values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", DWORD, 2)],
             recommend=lambda s: True if _nvidia_40plus(s) else False),
]
for _svc, _name, _start, _why in [
        ("wuauserv", "Windows Update", 3, "Senza Windows Update non si aggiornano driver, giochi Xbox/Game Pass e "
                                          "componenti DirectX."),
        ("BITS", "Servizio trasferimento intelligente (BITS)", 3, "Serve a Windows Update, Xbox App ed Epic."),
        ("Audiosrv", "Audio di Windows", 2, "Senza questo servizio non c'e' audio."),
        ("AudioEndpointBuilder", "Generatore endpoint audio", 2, "Serve all'audio di Windows."),
        ("GamingServices", "Gaming Services (Xbox / Game Pass)", 2, "Senza, i giochi Game Pass non partono."),
        ("XblAuthManager", "Xbox Live Auth Manager", 3, "Serve per l'accesso Xbox nei giochi Game Pass."),
        ("Dnscache", "Client DNS", 2, "Senza cache DNS ogni connessione e' piu' lenta."),
        ("mpssvc", "Windows Firewall", 2, "Alcuni giochi e anti-cheat si rifiutano di partire senza firewall."),
        ("Schedule", "Utilita' di pianificazione", 2, "Serve a molti launcher e driver (NVIDIA, AMD)."),
        ("Themes", "Temi", 2, "Disattivarlo non migliora i giochi e rompe l'aspetto di Windows."),
]:
    CORRECTIONS.append(ServiceEnableFix("fix_svc_" + _svc.lower(), FIX, "Riattiva il servizio " + _name,
                                        "Il servizio e' DISATTIVATO (spesso da script 'debloat'). " + _why,
                                        "media", kind="fix", service=_svc, start=_start))

CATALOG[:0] = CORRECTIONS
CAT_ORDER.insert(0, FIX)
CATALOG.sort(key=lambda t: CAT_ORDER.index(t.cat))
BY_ID = {t.id: t for t in CATALOG}


# ================================================================ AGGIUNTE (ricerca: Microsoft, NVIDIA, Blur Busters, TechSpot)

DG_PS = ("$d = Get-CimInstance -Namespace root\\Microsoft\\Windows\\DeviceGuard Win32_DeviceGuard "
         "-ErrorAction SilentlyContinue; ")


class RuntimeRegTweak(RegTweak):
    """Si applica con il registro, ma lo stato si legge da Windows mentre gira (piu' affidabile)."""

    def __init__(self, *a, check, **kw):
        super().__init__(*a, **kw)
        self.check = check

    def status(self):
        code, out = ps(self.check)
        last = out.strip().splitlines()[-1].strip().lower() if out.strip() else ""
        return {"true": True, "false": False}.get(last)


CATALOG[:] = [t for t in CATALOG if t.id != "vbs_off"]

ADDED = [
    RuntimeRegTweak("hvci_off", "Sicurezza (PERICOLOSE)", "Disattiva Integrita' della memoria (Isolamento core)",
                    "Spegne l'Integrita' della memoria (HVCI), la parte di 'Isolamento core' che controlla i driver. "
                    "E' la parte del VBS che costa di piu' nei giochi.", "media", risk=3, reboot=True,
                    warning="Riduce la protezione contro driver e malware a livello kernel. Alcuni anti-cheat "
                            "recenti potrebbero richiederla.",
                    values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios"
                                     r"\HypervisorEnforcedCodeIntegrity", "Enabled", DWORD, 0)],
                    check=DG_PS + "if (-not $d) { 'unknown' } else { -not ($d.SecurityServicesRunning -contains 2) }",
                    recommend=lambda s: None, source="Microsoft: 'Options to optimize gaming performance in Windows 11'"),
    RuntimeRegTweak("vbs_off", "Sicurezza (PERICOLOSE)", "Disattiva tutto il VBS (sicurezza basata su virtualizzazione)",
                    "Spegne l'intera piattaforma VBS, non solo l'Integrita' della memoria. Serve se il VBS resta "
                    "attivo anche con l'Isolamento core gia' spento (Credential Guard, criteri aziendali...).",
                    "media", risk=3, reboot=True,
                    warning="Si disattivano anche Credential Guard e le altre protezioni basate su VBS. Se il VBS "
                            "e' attivo per colpa di Hyper-V, WSL o della Piattaforma macchina virtuale, serve anche "
                            "spegnere quelli (voci 'hypervisor' e 'Piattaforma macchina virtuale').",
                    values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\DeviceGuard",
                             "EnableVirtualizationBasedSecurity", DWORD, 0),
                            ("HKLM", r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios"
                                     r"\HypervisorEnforcedCodeIntegrity", "Enabled", DWORD, 0),
                            ("HKLM", r"SYSTEM\CurrentControlSet\Control\Lsa", "LsaCfgFlags", DWORD, 0)],
                    check=DG_PS + "if (-not $d) { 'unknown' } else { $d.VirtualizationBasedSecurityStatus -ne 2 }",
                    recommend=lambda s: None, source="Tom's Hardware: VBS costa fino al 10% di FPS"),
    CmdTweak("vmp_off", "Sicurezza (PERICOLOSE)", "Disattiva la Piattaforma macchina virtuale (VMP)",
             "Spegne la funzione di Windows usata da WSL2, dalle app Android e da alcune macchine virtuali. "
             "Microsoft la indica tra le cose da disattivare per giocare.", "media", risk=2, reboot=True,
             warning="Smettono di funzionare WSL2, Windows Subsystem for Android e alcuni emulatori. Non ha "
                     "effetti sulla sicurezza.",
             on="Disable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart",
             off="Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart",
             check="(Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform).State -ne 'Enabled'",
             recommend=lambda s: None, source="Microsoft: 'Options to optimize gaming performance in Windows 11'"),
    DxUserSettingTweak("vrr_opt", "Gioco", "Attiva 'Frequenza di aggiornamento variabile' di Windows",
                       "Permette a G-SYNC/FreeSync di funzionare anche nei giochi DirectX 11 che non lo "
                       "supportano da soli.", "media", key="VRROptimizeEnable", value="1",
                       source="Microsoft, impostazioni grafiche di Windows 11"),
    RegTweak("access_keys", "Interfaccia e input", "Disattiva le scorciatoie Filtro tasti e Tasti di alternanza",
             "Tenere premuto Shift destro 8 secondi o Bloc Num 5 secondi non apre piu' le finestre di "
             "accessibilita' durante il gioco.", "comfort",
             values=[("HKCU", r"Control Panel\Accessibility\Keyboard Response", "Flags", SZ, "122"),
                     ("HKCU", r"Control Panel\Accessibility\ToggleKeys", "Flags", SZ, "58")]),
    RegTweak("copilot_off", "Interfaccia e input", "Disattiva Copilot di Windows",
             "Copilot non resta pronto in background.", "bassa",
             values=[("HKCU", r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot",
                      DWORD, 1)]),
    RegTweak("maintenance_off", "Memoria e disco", "Disattiva la Manutenzione automatica",
             "Windows non esegue piu' la manutenzione giornaliera (scansioni, ottimizzazione dischi, "
             "aggiornamenti app) da solo.", "dubbia", risk=1,
             warning="Microsoft consiglia di lasciarla attiva: dovrai ottimizzare i dischi e fare le pulizie a "
                     "mano. Di solito parte solo quando il PC e' inattivo, quindi non durante i giochi.",
             values=[("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\Maintenance",
                      "MaintenanceDisabled", DWORD, 1)], recommend=lambda s: None, source="Eleven Forum"),
    CmdTweak("nic_lso", "Rete", "Disattiva Large Send Offload della scheda di rete",
             "La CPU divide da sola i pacchetti grandi invece di farlo fare alla scheda di rete. Consigliato "
             "da molte guide di gaming, ma Microsoft dice che gli offload in genere aiutano.", "dubbia", risk=1,
             recommend=lambda s: None, **_nic_prop("*LsoV2IPv4", 0)),
    CmdTweak("fix_trim", FIX, "Riattiva il TRIM degli SSD",
             "Il TRIM e' disattivato: l'SSD rallenta e si consuma di piu' col tempo (succede con alcuni vecchi "
             "'ottimizzatori').", "alta", kind="fix",
             on="fsutil behavior set DisableDeleteNotify 0", off="fsutil behavior set DisableDeleteNotify 1",
             check="[bool]((fsutil behavior query DisableDeleteNotify) -match 'NTFS DisableDeleteNotify\\s*=\\s*0')"),
]
CATALOG.extend(ADDED)
CATALOG.sort(key=lambda t: CAT_ORDER.index(t.cat))
BY_ID = {t.id: t for t in CATALOG}

MYTHS += [
    ("Disattivare 'Ottimizza unita'' o la deframmentazione sugli SSD", "Sugli SSD Windows non deframmenta: "
     "esegue il TRIM, che mantiene l'SSD veloce. Disattivarlo lo rallenta col tempo."),
]

# Cose utili che un programma esterno non puo' impostare: si fanno a mano.
MANUAL_TIPS = [
    ("NVIDIA Reflex / AMD Anti-Lag", "Nei giochi che lo hanno, attiva NVIDIA Reflex (On; 'On + Boost' cambia poco). "
     "Se il gioco non lo ha: Pannello NVIDIA > 'Modalita' bassa latenza' = Ultra (non funziona nei giochi DX12), "
     "oppure Radeon Anti-Lag in AMD Adrenalin.", "NVIDIA System Latency Optimization Guide; TechSpot"),
    ("G-SYNC / FreeSync + V-Sync + limite FPS", "Con un monitor G-SYNC/FreeSync: attiva G-SYNC, V-Sync ON nel "
     "Pannello NVIDIA (OFF nel gioco) e limita gli FPS ad almeno 3 sotto la frequenza del monitor (es. 162 su 165 Hz). "
     "Niente tearing e latenza minima.", "Blur Busters, G-SYNC 101"),
    ("Accelerazione hardware di Discord", "Discord > Impostazioni > Avanzate > Accelerazione hardware: se senti "
     "stutter con Discord aperto, prova a spegnerla. Nei giochi molto pesanti sulla CPU puo' andare peggio: "
     "verificalo col test prima/dopo.", "Test di utenti (risultati misti)"),
    ("EXPO / XMP nel BIOS", "Attiva il profilo EXPO/XMP della RAM: con la RAM alla velocita' base gli 1% low "
     "peggiorano molto (LagDoctor lo controlla da solo).", "AMD, Intel"),
    ("Resizable BAR / Smart Access Memory", "Nel BIOS: 'Above 4G Decoding' + 'Re-Size BAR' attivi.", "NVIDIA, AMD"),
    ("Cache shader del driver", "Pannello NVIDIA > Dimensione cache shader = 10 GB o Illimitata; AMD Adrenalin > "
     "Cache shader = Ottimizzata AMD. Riduce gli scatti da compilazione shader.", "NVIDIA, AMD"),
    ("Modalita' di gestione energia NVIDIA", "Pannello NVIDIA > Gestisci impostazioni 3D > 'Modalita' di "
     "gestione dell'alimentazione' = Prediligi prestazioni massime, solo per i giochi che scattano quando la "
     "GPU 'si addormenta' (es. giochi leggeri).", "Community NVIDIA"),
    ("Cavo di rete e Wi-Fi", "Per il ping il cavo batte qualsiasi impostazione. Con il Wi-Fi usa i 5/6 GHz e "
     "stai vicino al router.", "—"),
    ("Driver puliti", "Quando cambi scheda video o hai problemi strani, disinstalla il driver con DDU in "
     "modalita' provvisoria e reinstallalo.", "Wagnardsoft (DDU)"),
]


# ================================================================ PROGRAMMI ALL'AVVIO

RUN_KEYS = [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run",
             r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
            ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
            ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32")]


def _enum_values(hive, path):
    out = []
    try:
        with winreg.OpenKey(_hive(hive), path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumValue(k, i))
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return out


def startup_items():
    """Programmi all'avvio (come in Gestione attivita'). Ogni voce: hive, nome, comando, attivo."""
    items = []
    if winreg is None:
        return items
    for hive, run, approved in RUN_KEYS:
        for name, cmd, _ in _enum_values(hive, run):
            st, _t = reg_read(hive, approved, name)
            enabled = not (isinstance(st, bytes) and len(st) > 0 and st[0] in (1, 3))
            items.append({"hive": hive, "approved": approved, "name": name, "cmd": str(cmd), "enabled": enabled})
    return items


def set_startup(item, enabled):
    """Attiva/disattiva come fa Gestione attivita' (non cancella niente, si puo' riattivare da li')."""
    data = bytes([2 if enabled else 3]) + bytes(11)
    reg_write(item["hive"], item["approved"], item["name"], 3, data)  # 3 = REG_BINARY
    state = load_state()
    key = "startup::%s::%s" % (item["hive"], item["name"])
    if not enabled:
        state.setdefault("_startup", {})[key] = item
    else:
        state.get("_startup", {}).pop(key, None)
    save_state(state)


# ================================================================ stato e backup

ROOT = None


def init(root):
    global STATE_FILE, ROOT
    ROOT = root
    STATE_FILE = os.path.join(root, "modifiche_applicate.json")


def load_state():
    if STATE_FILE and os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except ValueError:
            pass
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _ignored_file():
    return os.path.join(ROOT or ".", "ignorate.json")


def ignored():
    """Voci che l'utente ha deciso di ignorare (non contano tra 'da correggere' ne' nel punteggio)."""
    try:
        with open(_ignored_file(), encoding="utf-8") as f:
            return set(json.load(f))
    except (OSError, ValueError, TypeError):
        return set()


def set_ignored(tid, ignore=True):
    ids = ignored()
    if ignore:
        ids.add(tid)
    else:
        ids.discard(tid)
    with open(_ignored_file(), "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=1)
    return ids


def applied_by_us():
    return [k for k in load_state().keys() if not k.startswith("_")]


def apply_one(tid):
    t = BY_ID[tid]
    state = load_state()
    if tid in state:
        if hasattr(t, "reapply"):  # overlay spento da LagDoctor ma riaperto: lo richiudo
            return t.reapply(state[tid].get("backup") or {})
        return "gia' applicata"
    if t.group:  # annulla prima l'alternativa dello stesso gruppo (es. due valori per la stessa chiave)
        for other in [o for o in state if BY_ID.get(o) and BY_ID[o].group == t.group]:
            revert_one(other)
        state = load_state()
    backup = t.apply()
    state[tid] = {"backup": backup, "data": datetime.datetime.now().isoformat(timespec="seconds"),
                  "nome": t.name}
    save_state(state)
    return "applicata" + (" (serve il riavvio)" if t.reboot else "")


def revert_one(tid):
    state = load_state()
    if tid not in state:
        return "non applicata da LagDoctor: niente da annullare"
    BY_ID[tid].revert(state[tid]["backup"])
    del state[tid]
    save_state(state)
    return "annullata" + (" (serve il riavvio)" if BY_ID[tid].reboot else "")


def revert_all():
    msgs = []
    st = load_state().get("_startup", {})
    for item in list(st.values()):
        set_startup(item, True)
        msgs.append("Riattivato all'avvio: %s" % item["name"])
    for tid in reversed(applied_by_us()):
        try:
            msgs.append("%s: %s" % (BY_ID[tid].name, revert_one(tid)))
        except Exception as e:
            msgs.append("%s: ERRORE %s" % (BY_ID[tid].name, e))
    return msgs


def create_restore_point():
    """Crea un punto di ripristino di Windows. Restituisce (ok, messaggio)."""
    try:
        reg_write("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore",
                  "SystemRestorePointCreationFrequency", DWORD, 0)
    except Exception:
        pass
    code, out = ps("Enable-ComputerRestore -Drive \"$env:SystemDrive\\\" -ErrorAction SilentlyContinue; "
                   "Checkpoint-Computer -Description 'LagDoctor' -RestorePointType 'MODIFY_SETTINGS' "
                   "-ErrorAction Stop; 'OK'", timeout=300)
    return out.strip().endswith("OK"), out[-300:]


# ================================================================ DRIVER VIDEO (NVIDIA / AMD)
from . import driver_tweaks as _dt  # noqa: E402

CATALOG.extend(_dt.NVIDIA + _dt.AMD)
CAT_ORDER.insert(CAT_ORDER.index("Gioco"), "Driver NVIDIA")
CAT_ORDER.insert(CAT_ORDER.index("Gioco"), "Driver AMD")
CATALOG.sort(key=lambda t: CAT_ORDER.index(t.cat))
BY_ID = {t.id: t for t in CATALOG}


def for_vendor(vendor):
    """Il catalogo senza le voci del driver di altre marche e senza gli overlay di programmi non installati."""
    return [t for t in CATALOG if (not t.vendor or t.vendor == vendor) and
            (not hasattr(t, "available") or t.available())]


# ================================================================ DEBLOAT, TIMER RESOLUTION, IMPOSTAZIONI, MITI
from . import extra_tweaks as _et  # noqa: E402

_et.register()
NOT_TOGGLEABLE = _et.NOT_TOGGLEABLE

# ================================================================ VIRTUALIZZAZIONE: una sola voce per VBS/HVCI/Hyper-V
from . import virt_tweak as _vt  # noqa: E402

_vt.register()

# ================================================================ OVERLAY: categoria a parte
from . import overlays as _ov  # noqa: E402

_ov.register()

# GlobalTimerResolutionRequests e' ora parte di "Timer Resolution 0,5 ms": tolgo la voce separata dall'elenco
# (resta annullabile se era stata applicata; applicando il Timer Resolution viene sostituita, stesso gruppo).
CATALOG[:] = [t for t in CATALOG if t.id != "timer_global"]

# Consigliate anche se non sono "alta/media efficacia": utili su qualsiasi PC, nessuna controindicazione pratica,
# tutte annullabili. Cosi' "Seleziona consigliate" le applica tutte insieme.
RECOMMENDED_EXTRA = {
    "telemetry_policy",   # telemetria e pubblicita' al minimo
    "visual_fx",          # effetti visivi (caratteri smussati e anteprime restano)
    "timer_res",          # Timer Resolution 0,5 ms + GlobalTimerResolutionRequests
    "widgets_off",        # niente widget notizie/meteo in background
    "edge_bg_off",        # Edge non resta aperto in background
    "recall_off",         # niente analisi AI degli screenshot
    "start_web_off",      # ricerca del menu Start senza Bing
    "ntfs_lastaccess",    # meno scritture inutili sul disco
    "sticky_keys",        # Shift premuto 5 volte non apre piu' Tasti permanenti durante il gioco
    "access_keys",        # idem per Filtro tasti / Tasti di alternanza
    "startup_delay",      # programmi di avvio senza attesa
    "menu_delay",         # menu istantanei
}
for _t in CATALOG:
    if _t.id in RECOMMENDED_EXTRA:
        _t._recommend = lambda s: True


# ---------------------------------------------------------------- stato per EFFETTO
# Queste voci si possono ottenere anche con valori o chiavi diverse (a mano, dalle Impostazioni di Windows, con altri
# programmi di ottimizzazione): conta l'effetto reale, non il valore esatto che scriverebbe LagDoctor.
def _int(v, default=None):
    try:
        return int(str(v), 0) if not isinstance(v, int) else v
    except (TypeError, ValueError):
        return default


_ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
_ACC = r"Control Panel\Accessibility"
ACTIVE_CHECKS = {
    # "Migliora precisione puntatore" spenta = MouseSpeed 0 (le soglie non contano)
    "mouse_accel": lambda r: _int(r("HKCU", r"Control Panel\Mouse", "MouseSpeed"), 1) == 0,
    # scorciatoie di accessibilita': conta solo il bit "scorciatoia attiva" (0x4)
    "sticky_keys": lambda r: not (_int(r("HKCU", _ACC + r"\StickyKeys", "Flags"), 510) & 0x4),
    "access_keys": lambda r: not (_int(r("HKCU", _ACC + r"\Keyboard Response", "Flags"), 126) & 0x4) and
                             not (_int(r("HKCU", _ACC + r"\ToggleKeys", "Flags"), 62) & 0x4),
    # NTFS "ultimo accesso": disattivato se il bit basso e' 1 (1 = utente, 0x80000001 = sistema)
    "ntfs_lastaccess": lambda r: (_int(r("HKLM", r"SYSTEM\CurrentControlSet\Control\FileSystem",
                                          "NtfsDisableLastAccessUpdate"), 0x80000002) & 1) == 1,
    # Game DVR: basta l'interruttore delle Impostazioni o il criterio
    "game_dvr": lambda r: _int(r("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled"), 1) == 0
                          or _int(r("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR"), 1) == 0,
    # Modalita' Gioco: se il valore non c'e' Windows la considera ACCESA
    "game_mode": lambda r: _int(r("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled"), 1) != 0,
    # Widget: criterio oppure pulsante tolto dalla barra (Impostazioni > Personalizzazione > Barra delle applicazioni)
    "widgets_off": lambda r: _int(r("HKLM", r"SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests"), 1) == 0
                             or _int(r("HKCU", _ADV, "TaskbarDa"), 1) == 0,
    # Copilot: criterio dell'utente o del computer
    "copilot_off": lambda r: _int(r("HKCU", r"Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot"), 0) == 1
                             or _int(r("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot"), 0) == 1,
    # ricerca del menu Start senza Bing: criterio oppure BingSearchEnabled = 0
    "start_web_off": lambda r: _int(r("HKCU", r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions"), 0) == 1
                               or _int(r("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled"), 1) == 0,
    # Ottimizzazione recapito senza scambio con altri PC: criterio 0/99/100 o impostazione di Windows 0
    "delivery_opt": lambda r: _int(r("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode"), -1) in (0, 99, 100)
                              or _int(r("HKU", r"S-1-5-20\Software\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Settings",
                                        "DownloadMode"), -1) == 0,
    # telemetria: 0 o 1 (su Home/Pro lo 0 vale come 1) + pubblicita' personalizzata spenta
    # AllowTelemetry: Windows lo legge sia dai Criteri di gruppo sia da CurrentVersion\Policies (dove lo scrive LagDoctor)
    "telemetry_policy": lambda r: min(_int(r("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry"), 3),
                                      _int(r("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection",
                                             "AllowTelemetry"), 3)) <= 1
                                  and _int(r("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled"), 1) == 0,
    # SystemResponsiveness: 10 o meno (0 ha lo stesso effetto, anzi piu' forte)
    "sys_resp": lambda r: _int(r("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
                                 "SystemResponsiveness"), 20) <= 10,
    # nomi 8.3: 1 = spenti su tutti i dischi, 3 = spenti su tutti tranne quello di sistema
    "ntfs_83": lambda r: _int(r("HKLM", r"SYSTEM\CurrentControlSet\Control\FileSystem",
                                "NtfsDisable8dot3NameCreation"), 2) in (1, 3),
    # spegnimento rapido: qualsiasi attesa di 2 secondi o meno
    "wait_kill_svc": lambda r: _int(r("HKLM", r"SYSTEM\CurrentControlSet\Control", "WaitToKillServiceTimeout"), 5000) <= 2000,
    # ottimizzazioni schermo intero spente: basta il valore principale
    "fso_off": lambda r: _int(r("HKCU", r"System\GameConfigStore", "GameDVR_FSEBehaviorMode"), 0) == 2,
    # Recall: criterio del computer o dell'utente
    "recall_off": lambda r: _int(r("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsAI", "DisableAIDataAnalysis"), 0) == 1
                            or _int(r("HKCU", r"Software\Policies\Microsoft\Windows\WindowsAI", "DisableAIDataAnalysis"), 0) == 1,
    # app in background: impostazione dell'utente o criterio "nega" (2)
    "bg_apps": lambda r: _int(r("HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                                "GlobalUserDisabled"), 0) == 1
                         or _int(r("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsRunInBackground"), 0) == 2,
    # Sensore memoria spento: impostazione dell'utente o criterio
    "storage_sense_off": lambda r: _int(r("HKCU", r"Software\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy",
                                          "01"), 0) == 0
                                   or _int(r("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\StorageSense", "AllowStorageSenseGlobal"), 1) == 0,
    # menu: qualsiasi ritardo breve
    "menu_delay": lambda r: _int(r("HKCU", r"Control Panel\Desktop", "MenuShowDelay"), 400) <= 50,
    # IPv4 preferito: bit 0x20, oppure IPv6 tutto disattivato (0xFF)
    "ipv4_pref": lambda r: bool(_int(r("HKLM", r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters", "DisabledComponents"), 0) & 0x20)
                           or _int(r("HKLM", r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters", "DisabledComponents"), 0) == 0xFF,
}
for _t in CATALOG:
    if _t.id in ACTIVE_CHECKS and isinstance(_t, RegTweak):
        _t.active = ACTIVE_CHECKS[_t.id]


def force_off(tid):
    """Disattiva un 'mito' attivo anche se non l'ha applicato LagDoctor (torna al valore di Windows)."""
    t = BY_ID[tid]
    if t.kind != "myth":
        raise RuntimeError("solo per le voci 'non affidabili'")
    if isinstance(t, CmdTweak):
        ps(t.off, timeout=120)
    elif isinstance(t, RegTweak):
        for h, p, n, typ, v in t.values():
            reg_delete(h, p, n)
    state = load_state()
    state.pop(tid, None)
    save_state(state)
    return "disattivata (valore predefinito di Windows)" + (" - serve il riavvio" if t.reboot else "")
