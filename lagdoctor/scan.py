"""Scansione completa del sistema: hardware, Windows, driver, impostazioni, errori.

Raccoglie tutto con un unico script PowerShell (piu' veloce) + letture dirette in Python,
poi cerca i problemi e crea un report HTML.
"""
import ctypes
import datetime
import html
import json
import os
import re
import subprocess
import tempfile
import time

import psutil

from . import gpu as gpumod
from . import tweaks
from .checks import SECURITY_SERVICES

CREATE_NO_WINDOW = 0x08000000

PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$r = @{}
function T($n, [scriptblock]$b) { try { $r[$n] = & $b } catch { $r[$n] = $null } }
$cv = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
T os { $o = Get-CimInstance Win32_OperatingSystem; @{ caption = $o.Caption; version = $o.Version; build = $o.BuildNumber;
       ubr = $cv.UBR; display = $cv.DisplayVersion; installed = $o.InstallDate.ToString('yyyy-MM-dd');
       boot = $o.LastBootUpTime.ToString('yyyy-MM-dd HH:mm'); lang = $o.MUILanguages -join ',' } }
T cpu { Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed,
       L2CacheSize, L3CacheSize, VirtualizationFirmwareEnabled }
T board { Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product, Version }
T bios { $b = Get-CimInstance Win32_BIOS; @{ version = $b.SMBIOSBIOSVersion; date = $b.ReleaseDate.ToString('yyyy-MM-dd');
       maker = $b.Manufacturer } }
T ram { @(Get-CimInstance Win32_PhysicalMemory | Select-Object Manufacturer, PartNumber, Capacity, Speed,
       ConfiguredClockSpeed, DeviceLocator, SMBIOSMemoryType) }
T pagefile { @{ auto = (Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile;
       files = @(Get-CimInstance Win32_PageFileUsage | Select-Object Name, AllocatedBaseSize, CurrentUsage, PeakUsage) } }
T gpus { @(Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion,
       @{n = 'DriverDate'; e = { $_.DriverDate.ToString('yyyy-MM-dd') } }, CurrentHorizontalResolution,
       CurrentVerticalResolution, CurrentRefreshRate, MaxRefreshRate, PNPDeviceID) }
T monitors { @(Get-CimInstance -Namespace root\wmi WmiMonitorID | ForEach-Object {
       @{ name = (($_.UserFriendlyName | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ }) -join '');
          maker = (($_.ManufacturerName | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ }) -join '');
          year = $_.YearOfManufacture } }) }
T disks { @(Get-PhysicalDisk | ForEach-Object { $c = $_ | Get-StorageReliabilityCounter
       @{ name = $_.FriendlyName; media = "$($_.MediaType)"; bus = "$($_.BusType)"; size = $_.Size;
          health = "$($_.HealthStatus)"; temp = $c.Temperature; wear = $c.Wear; hours = $c.PowerOnHours } }) }
T volumes { @(Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel, Size, SizeRemaining,
       FileSystem) }
T net { @(Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Select-Object Name, InterfaceDescription, LinkSpeed,
       MediaType, PhysicalMediaType, DriverVersion, DriverDate) }
T wifi { (netsh wlan show interfaces) -join "`n" }
T startup { @(Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location) }
T services_running { @(Get-Service | Where-Object Status -eq 'Running').Count }
T services3p { @(Get-CimInstance Win32_Service | Where-Object { $_.State -eq 'Running' -and $_.PathName -and
       $_.PathName -notmatch '\\Windows\\' } | Select-Object Name, DisplayName) }
T av { @(Get-CimInstance -Namespace root\SecurityCenter2 AntiVirusProduct | Select-Object displayName, productState) }
T apps { @(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
       'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
       'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' | Where-Object DisplayName |
       Select-Object DisplayName, DisplayVersion, Publisher | Sort-Object DisplayName -Unique) }
T secureboot { Confirm-SecureBootUEFI }
T tpm { $t = Get-Tpm; @{ present = $t.TpmPresent; ready = $t.TpmReady } }
T devguard { $d = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard Win32_DeviceGuard
       @{ vbs = $d.VirtualizationBasedSecurityStatus; running = @($d.SecurityServicesRunning) } }
T pending_reboot { (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') -or
       (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') }
T last_update { (Get-HotFix | Where-Object InstalledOn | Sort-Object InstalledOn -Descending |
       Select-Object -First 1).InstalledOn.ToString('yyyy-MM-dd') }
$since = (Get-Date).AddDays(-30)
T ev_tdr { @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 4101; StartTime = $since }).Count }
T ev_whea { @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-WHEA-Logger';
       StartTime = $since }).Count }
T ev_kp41 { @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-Kernel-Power';
       Id = 41; StartTime = $since }).Count }
T ev_bsod { @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 1001; ProviderName = 'Microsoft-Windows-WER-SystemErrorReporting';
       StartTime = $since }).Count }
T ev_appcrash { @(Get-WinEvent -FilterHashtable @{ LogName = 'Application'; ProviderName = 'Application Error'; Id = 1000;
       StartTime = $since } |
       ForEach-Object { $_.Properties[0].Value } | Group-Object | Sort-Object Count -Descending |
       Select-Object -First 8 Name, Count) }
T bcd { (bcdedit /enum '{current}') -join "`n" }
T gpu_prefs { $k = Get-ItemProperty 'HKCU:\Software\Microsoft\DirectX\UserGpuPreferences'
       if ($k) { $h = @{}; $k.PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } |
       ForEach-Object { $h[$_.Name] = "$($_.Value)" }; $h } }
T power_plans { (powercfg /list) -join "`n" }
$r | ConvertTo-Json -Depth 6 -Compress
"""


def run_powershell_scan():
    path = os.path.join(tempfile.gettempdir(), "lagdoctor_scan.ps1")
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write(PS_SCRIPT)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path],
                           capture_output=True, timeout=300, creationflags=CREATE_NO_WINDOW)
        out = r.stdout.decode("utf-8", errors="replace").strip()
        start = out.find("{")
        return json.loads(out[start:]) if start >= 0 else {}
    except Exception:
        return {}
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------- monitor e frequenze (API Windows)

class _POINTL(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class DEVMODEW(ctypes.Structure):
    _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", ctypes.c_ushort),
                ("dmDriverVersion", ctypes.c_ushort), ("dmSize", ctypes.c_ushort),
                ("dmDriverExtra", ctypes.c_ushort), ("dmFields", ctypes.c_ulong),
                ("dmPosition", _POINTL), ("dmDisplayOrientation", ctypes.c_ulong),
                ("dmDisplayFixedOutput", ctypes.c_ulong), ("dmColor", ctypes.c_short),
                ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
                ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short),
                ("dmFormName", ctypes.c_wchar * 32), ("dmLogPixels", ctypes.c_ushort),
                ("dmBitsPerPel", ctypes.c_ulong), ("dmPelsWidth", ctypes.c_ulong),
                ("dmPelsHeight", ctypes.c_ulong), ("dmDisplayFlags", ctypes.c_ulong),
                ("dmDisplayFrequency", ctypes.c_ulong), ("dmICMMethod", ctypes.c_ulong),
                ("dmICMIntent", ctypes.c_ulong), ("dmMediaType", ctypes.c_ulong),
                ("dmDitherType", ctypes.c_ulong), ("dmReserved1", ctypes.c_ulong),
                ("dmReserved2", ctypes.c_ulong), ("dmPanningWidth", ctypes.c_ulong),
                ("dmPanningHeight", ctypes.c_ulong)]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("DeviceName", ctypes.c_wchar * 32), ("DeviceString", ctypes.c_wchar * 128),
                ("StateFlags", ctypes.c_ulong), ("DeviceID", ctypes.c_wchar * 128), ("DeviceKey", ctypes.c_wchar * 128)]


ENUM_CURRENT_SETTINGS = -1
DM_DISPLAYFREQUENCY = 0x400000
CDS_UPDATEREGISTRY = 0x1


def displays():
    """Ogni schermo attivo: risoluzione, frequenza attuale e massima disponibile a quella risoluzione."""
    res = []
    try:
        user32 = ctypes.windll.user32
    except Exception:
        return res
    i = 0
    while True:
        dd = DISPLAY_DEVICEW()
        dd.cb = ctypes.sizeof(dd)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not dd.StateFlags & 0x1:  # non collegato al desktop
            continue
        cur = DEVMODEW()
        cur.dmSize = ctypes.sizeof(cur)
        if not user32.EnumDisplaySettingsW(dd.DeviceName, ENUM_CURRENT_SETTINGS, ctypes.byref(cur)):
            continue
        best = cur.dmDisplayFrequency
        j = 0
        while True:
            m = DEVMODEW()
            m.dmSize = ctypes.sizeof(m)
            if not user32.EnumDisplaySettingsW(dd.DeviceName, j, ctypes.byref(m)):
                break
            j += 1
            if m.dmPelsWidth == cur.dmPelsWidth and m.dmPelsHeight == cur.dmPelsHeight:
                best = max(best, m.dmDisplayFrequency)
        res.append({"device": dd.DeviceName, "gpu": dd.DeviceString, "primary": bool(dd.StateFlags & 0x4),
                    "width": cur.dmPelsWidth, "height": cur.dmPelsHeight, "hz": cur.dmDisplayFrequency,
                    "max_hz": best, "bits": cur.dmBitsPerPel})
    return res


def set_refresh(device, hz):
    user32 = ctypes.windll.user32
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(dm)
    user32.EnumDisplaySettingsW(device, ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
    dm.dmDisplayFrequency = hz
    dm.dmFields = DM_DISPLAYFREQUENCY
    r = user32.ChangeDisplaySettingsExW(device, ctypes.byref(dm), None, CDS_UPDATEREGISTRY, None)
    return r == 0


# ---------------------------------------------------------------- NVIDIA extra

def nvidia_extra():
    q = ("pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current,pcie.link.width.max,"
         "power.limit,power.max_limit,clocks.max.graphics,clocks.max.memory,temperature.gpu")
    out = {}
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=" + q, "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=15, creationflags=CREATE_NO_WINDOW)
        vals = [v.strip() for v in r.stdout.splitlines()[0].split(",")]
        for k, v in zip(q.split(","), vals):
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
        r = subprocess.run(["nvidia-smi", "-q", "-d", "MEMORY"], capture_output=True, text=True, timeout=15,
                           creationflags=CREATE_NO_WINDOW)
        m = re.search(r"BAR1 Memory Usage\s*\n\s*Total\s*:\s*(\d+)\s*MiB", r.stdout)
        if m:
            out["bar1_mb"] = int(m.group(1))
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- raccolta completa

def collect(sysinfo, progress=print):
    progress("  Leggo hardware, Windows, driver ed errori (30-90 secondi)...")
    d = run_powershell_scan()
    progress("  Leggo schermi e scheda video...")
    d["displays"] = displays()
    g = (sysinfo or {}).get("gpu") or gpumod.gpu_info() or {}
    d["gpu_main"] = g
    if g.get("vendor") == "nvidia":
        d["nvidia"] = nvidia_extra()
    progress("  Controllo lo stato di tutte le impostazioni, app preinstallate e driver...")
    applied = tweaks.applied_by_us()
    d["tweaks"] = []
    for t in tweaks.for_vendor(tweaks.CONTEXT.get("vendor") or (g or {}).get("vendor")):
        try:
            st = t.status()
        except Exception:
            st = None
        d["tweaks"].append({"id": t.id, "nome": t.name, "cat": t.cat, "stato": st, "da_lagdoctor": t.id in applied})
    progress("  Leggo processi e memoria...")
    procs = []
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            procs.append((p.info["name"], p.info["memory_info"].rss / 2**20))
        except Exception:
            pass
    agg = {}
    for n, m in procs:
        agg[n] = agg.get(n, 0) + m
    d["proc_count"] = len(procs)
    d["proc_top_ram"] = sorted(agg.items(), key=lambda x: -x[1])[:15]
    vm = psutil.virtual_memory()
    d["ram_used_pct"] = vm.percent
    d["uptime_h"] = (time.time() - psutil.boot_time()) / 3600
    return d


def is_integrated(name):
    """Scheda video integrata nel processore (es. 'AMD Radeon(TM) Graphics', 'Intel UHD Graphics')."""
    n = (name or "").lower()
    if re.search(r"\b(rx|rtx|gtx|gt|quadro|radeon pro)\b|arc(\(tm\))?\s*[ab]\d", n):
        return False
    return "graphics" in n or "uhd" in n or "iris" in n


def dedicated_gpus(d):
    return [g for g in _list(d.get("gpus")) if g and not is_integrated(g.get("Name"))
            and "microsoft" not in (g.get("Name") or "").lower()]


def _list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


# ---------------------------------------------------------------- regole

def problems(d, sysinfo):
    P = []

    def add(g, t, s, sol, fix=None):
        P.append(dict(gravita=g, titolo=t, spiegazione=s, soluzione=sol, auto_fix=fix))

    # schermi
    dgpus = dedicated_gpus(d)
    for disp in d.get("displays", []):
        if dgpus and is_integrated(disp.get("gpu")):
            add(3, "Monitor collegato alla scheda madre invece che alla scheda video",
                "Lo schermo %s e' collegato all'uscita video della scheda madre (%s). Cosi' i giochi vengono "
                "disegnati dalla scheda video e poi copiati sulla grafica integrata: meno FPS, piu' latenza e "
                "stutter." % (disp["device"].replace("\\\\.\\", ""), disp.get("gpu")),
                "Sposta il cavo del monitor nelle uscite della SCHEDA VIDEO (quelle in basso, in orizzontale, "
                "sul retro del case).")
        # solo differenze grandi (es. 60 Hz su un monitor da 144/165): pochi Hz in meno possono essere voluti
        if disp["max_hz"] >= 100 and disp["hz"] < disp["max_hz"] * 0.8:
            add(3, "Monitor impostato a %d Hz ma supporta %d Hz" % (disp["hz"], disp["max_hz"]),
                "Lo schermo %s (%dx%d) sta usando una frequenza molto piu' bassa del suo massimo: il gioco sembra "
                "meno fluido anche con FPS alti." % (disp["device"].replace("\\\\.\\", ""), disp["width"],
                                                     disp["height"]),
                "Lo posso impostare io a %d Hz. Usa un cavo DisplayPort o HDMI 2.1 se il monitor e' ad alta "
                "frequenza." % disp["max_hz"],
                ("set_refresh", [disp["device"], disp["max_hz"]]))
    hzs = {disp["hz"] for disp in d.get("displays", [])}
    if len(hzs) > 1:
        add(1, "Monitor con frequenze diverse",
            "Hai piu' schermi a frequenze diverse (%s Hz). In borderless questo puo' causare scatti, specie con "
            "un video o Discord aperto sull'altro schermo." % ", ".join(str(h) for h in sorted(hzs)),
            "Gioca in schermo intero vero, oppure prova l'ottimizzazione 'Disattiva MPO'.")

    # GPU / PCIe
    nv = d.get("nvidia") or {}
    wc, wm = nv.get("pcie.link.width.current"), nv.get("pcie.link.width.max")
    if isinstance(wc, float) and isinstance(wm, float) and wc < wm:
        add(2, "La scheda video usa x%d linee PCIe invece di x%d" % (wc, wm),
            "La GPU non sta usando tutte le linee del suo slot. Succede se e' montata nello slot sbagliato, "
            "con un riser, o se uno slot M.2 condivide le linee.",
            "Controlla che la scheda video sia nel primo slot PCIe x16 (quello piu' vicino alla CPU) e "
            "rileggi il manuale della scheda madre per le linee condivise con gli M.2.")
    if "bar1_mb" in nv and nv["bar1_mb"] <= 256:
        add(1, "Resizable BAR disattivato",
            "La CPU vede solo 256 MB della memoria della GPU alla volta. In alcuni giochi attivarlo "
            "aumenta gli FPS di qualche %, in altri non cambia.",
            "Nel BIOS attiva 'Above 4G Decoding' e 'Re-Size BAR Support' (servono BIOS in modalita' UEFI e "
            "CSM disattivato).")
    for gp in (dgpus or _list(d.get("gpus"))):
        dd = gp.get("DriverDate")
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(dd)).days
        except Exception:
            continue
        if age > 240 and "microsoft" not in (gp.get("Name") or "").lower() and not is_integrated(gp.get("Name")):
            add(1, "Driver video vecchio (%s)" % gp.get("Name"),
                "Il driver e' del %s (%d mesi fa). I driver nuovi spesso correggono stutter e bug dei giochi "
                "recenti." % (dd, age // 30),
                "Aggiorna da nvidia.com / amd.com / intel.com (o dall'app NVIDIA / AMD Adrenalin).")

    # stabilita'
    if (d.get("ev_whea") or 0) > 0:
        add(3, "Errori hardware registrati da Windows (WHEA): %d negli ultimi 30 giorni" % d["ev_whea"],
            "Windows ha registrato errori corretti dall'hardware. Di solito sono causati da overclock della RAM "
            "(EXPO/XMP instabile), undervolt della CPU (Curve Optimizer/PBO) o overclock della GPU. Possono "
            "causare stutter, crash e freeze.",
            "Se hai overclock/undervolt, tornali ai valori di default e verifica se gli errori spariscono. "
            "Aggiorna il BIOS. Se usi EXPO, prova la velocita' un gradino piu' bassa.")
    if (d.get("ev_tdr") or 0) > 0:
        add(2, "Il driver video si e' bloccato e riavviato %d volte negli ultimi 30 giorni" % d["ev_tdr"],
            "Ogni volta lo schermo diventa nero per un attimo o il gioco va in crash.",
            "Togli eventuali overclock della GPU, reinstalla il driver pulito (DDU in modalita' provvisoria) e "
            "controlla che i cavi di alimentazione della scheda siano ben inseriti.")
    if (d.get("ev_kp41") or 0) > 0:
        add(2, "Spegnimenti improvvisi: %d negli ultimi 30 giorni" % d["ev_kp41"],
            "Il PC si e' riavviato o spento senza chiudere Windows (crash, blocco o mancanza di corrente).",
            "Se non hai premuto tu il tasto o staccato la corrente: controlla temperature, alimentatore e "
            "togli gli overclock.")
    if (d.get("ev_bsod") or 0) > 0:
        add(3, "Schermate blu (BSOD): %d negli ultimi 30 giorni" % d["ev_bsod"],
            "Windows e' andato in crash.", "Togli overclock/undervolt e aggiorna BIOS, chipset e driver video.")
    crashes = [c for c in _list(d.get("ev_appcrash")) if c and c.get("Count", 0) >= 3]
    if crashes:
        add(1, "Programmi che vanno spesso in crash",
            "Negli ultimi 30 giorni: " + ", ".join("%s (%d volte)" % (c["Name"], c["Count"]) for c in crashes),
            "Se sono giochi: verifica i file del gioco dal launcher e aggiorna i driver.")

    # dischi
    for dk in _list(d.get("disks")):
        if dk.get("health") and dk["health"] not in ("Healthy", "0", "Integro"):
            add(3, "Disco con problemi di salute: %s" % dk.get("name"),
                "Windows segnala lo stato '%s'. Il disco potrebbe rompersi." % dk["health"],
                "Fai subito un backup dei dati importanti e valuta la sostituzione.")
        if isinstance(dk.get("wear"), (int, float)) and dk["wear"] >= 80:
            add(2, "SSD molto consumato: %s (%d%%)" % (dk.get("name"), dk["wear"]),
                "L'SSD ha usato gran parte della sua vita utile.", "Fai un backup e valuta la sostituzione.")
        if isinstance(dk.get("temp"), (int, float)) and dk["temp"] >= 70:
            add(1, "SSD molto caldo: %s (%d C)" % (dk.get("name"), dk["temp"]),
                "Sopra i 70-75 C gli SSD NVMe rallentano per proteggersi (stutter nei caricamenti).",
                "Usa il dissipatore M.2 della scheda madre e migliora il flusso d'aria.")
    for v in _list(d.get("volumes")):
        try:
            free = v["SizeRemaining"] / v["Size"] * 100
        except Exception:
            continue
        if v.get("Size", 0) > 20e9 and free < 10:
            add(2, "Disco %s: quasi pieno (%.0f%% libero)" % (v["DriveLetter"], free),
                "Un disco quasi pieno rallenta, soprattutto gli SSD.",
                "Libera spazio fino ad avere almeno il 15% libero.")

    # memoria virtuale
    pf = d.get("pagefile") or {}
    if pf and not pf.get("auto") and not _list(pf.get("files")):
        add(2, "File di paging disattivato",
            "Senza file di paging, quando la RAM si riempie i giochi vanno in crash invece di rallentare.",
            "Impostazioni di sistema > Sistema avanzate > Prestazioni > Avanzate > Memoria virtuale > "
            "'Gestisci automaticamente'.")

    # rete
    for n in _list(d.get("net")):
        desc = (n.get("InterfaceDescription") or "").lower()
        wifi = "802.11" in str(n.get("PhysicalMediaType")) or "wi-fi" in desc or "wireless" in desc or "wlan" in desc
        speed = str(n.get("LinkSpeed") or "")
        if wifi:
            sig = re.search(r"(?:Signal|Segnale)\s*:\s*(\d+)%", d.get("wifi") or "")
            s = (" Segnale: %s%%." % sig.group(1)) if sig else ""
            add(2 if sig and int(sig.group(1)) < 70 else 1, "Stai usando il Wi-Fi",
                "Il Wi-Fi ha piu' latenza e soprattutto picchi di ping e perdita di pacchetti rispetto al cavo."
                + s,
                "Se puoi, usa un cavo di rete. In alternativa: rete a 5 GHz, router vicino, niente muri in mezzo.")
        elif re.match(r"^(10|100)\s*Mbps", speed):
            add(2, "Rete via cavo a %s" % speed,
                "La scheda di rete va a %s invece di 1 Gbps: di solito e' un cavo rovinato o vecchio (Cat5)." % speed,
                "Cambia il cavo di rete con un Cat5e/Cat6 e controlla la porta del router.")

    # Windows
    if d.get("pending_reboot"):
        add(1, "Riavvio in sospeso per aggiornamenti",
            "Windows ha aggiornamenti installati a meta' che aspettano un riavvio.", "Riavvia il PC.")
    if d.get("uptime_h", 0) > 24 * 7:
        add(1, "PC acceso da %d giorni senza riavvio" % (d["uptime_h"] // 24),
            "Con l'avvio rapido 'spegni' non azzera Windows: memoria e driver accumulano problemi nel tempo.",
            "Fai un Riavvia (non Arresta) ogni tanto, o attiva 'Disattiva ibernazione e avvio rapido'.")
    avs = [a.get("displayName") for a in _list(d.get("av")) if a and "defender" not in str(a.get("displayName")).lower()]
    if avs:
        add(1, "Antivirus di terze parti: " + ", ".join(avs),
            "Alcuni antivirus (soprattutto le suite complete) scansionano i file del gioco durante i caricamenti "
            "e aggiungono overlay o servizi pesanti.",
            "Aggiungi la cartella dei giochi alle esclusioni dell'antivirus o usa Microsoft Defender.")
    st = _list(d.get("startup"))
    if len(st) > 12:
        add(1, "Molti programmi all'avvio (%d)" % len(st),
            "Ogni programma all'avvio resta in background mentre giochi.",
            "Gestione attivita' > App di avvio: disattiva quelli che non ti servono subito.")
    if d.get("secureboot") is False or (d.get("tpm") or {}).get("ready") is False:
        add(1, "Secure Boot o TPM disattivati",
            "Non cambiano le prestazioni, ma alcuni anti-cheat recenti (es. Valorant, Battlefield 6, Call of "
            "Duty) li richiedono per giocare.",
            "Attivali nel BIOS solo se un gioco te li chiede.")
    return P


# ---------------------------------------------------------------- report

def _rows(pairs):
    return "".join("<tr><td>%s</td><td>%s</td></tr>" % (html.escape(str(k)), html.escape(str(v))) for k, v in pairs)


def _table(headers, rows):
    h = "".join("<th>%s</th>" % html.escape(x) for x in headers)
    b = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % html.escape("" if c is None else str(c)) for c in r)
                for r in rows)
    return "<table><tr>%s</tr>%s</table>" % (h, b)


def gb(x):
    try:
        return "%.0f GB" % (float(x) / 1e9)
    except (TypeError, ValueError):
        return "?"


def build_report(path, d, probs):
    from .report import SEV
    os_ = d.get("os") or {}
    cpu = (_list(d.get("cpu")) or [{}])[0]
    board = (_list(d.get("board")) or [{}])[0]
    bios = d.get("bios") or {}
    nv = d.get("nvidia") or {}
    g = d.get("gpu_main") or {}
    sec = []

    sec.append(("Sistema operativo", "<table>" + _rows([
        ("Windows", "%s %s (build %s.%s)" % (os_.get("caption"), os_.get("display"), os_.get("build"), os_.get("ubr"))),
        ("Installato il", os_.get("installed")), ("Ultimo avvio", os_.get("boot")),
        ("Acceso da", "%.0f ore" % d.get("uptime_h", 0)), ("Ultimo aggiornamento", d.get("last_update")),
        ("Riavvio in sospeso", "si" if d.get("pending_reboot") else "no"),
        ("Secure Boot", d.get("secureboot")), ("TPM pronto", (d.get("tpm") or {}).get("ready")),
        ("VBS (piattaforma)", {0: "disattivato", 1: "abilitato ma non attivo", 2: "attivo"}.get((d.get("devguard") or {}).get("vbs"), "?")),
        ("Servizi VBS in esecuzione", ", ".join(SECURITY_SERVICES.get(int(x), str(x)) for x in _list((d.get("devguard") or {}).get("running"))
                                               if str(x).isdigit() and int(x)) or "nessuno"),
        ("Integrita' della memoria (Isolamento core)", "ATTIVA" if 2 in [int(x) for x in _list((d.get("devguard") or {}).get("running")) if str(x).isdigit()] else "disattivata"),
        ("Processi / servizi attivi", "%s / %s" % (d.get("proc_count"), d.get("services_running"))),
        ("RAM usata ora", "%.0f%%" % d.get("ram_used_pct", 0)),
    ]) + "</table>"))
    sec.append(("Processore e scheda madre", "<table>" + _rows([
        ("CPU", cpu.get("Name")), ("Core / thread", "%s / %s" % (cpu.get("NumberOfCores"), cpu.get("NumberOfLogicalProcessors"))),
        ("Frequenza base", "%s MHz" % cpu.get("MaxClockSpeed")), ("Cache L3", "%s MB" % ((cpu.get("L3CacheSize") or 0) // 1024)),
        ("Virtualizzazione (BIOS)", cpu.get("VirtualizationFirmwareEnabled")),
        ("Scheda madre", "%s %s" % (board.get("Manufacturer"), board.get("Product"))),
        ("BIOS", "%s del %s" % (bios.get("version"), bios.get("date"))),
    ]) + "</table>"))
    sec.append(("Memoria RAM", _table(["Slot", "Marca", "Modello", "Capacita'", "Velocita' max", "Velocita' attuale"],
                                     [(r.get("DeviceLocator"), r.get("Manufacturer"), (r.get("PartNumber") or "").strip(),
                                       gb(r.get("Capacity")), r.get("Speed"), r.get("ConfiguredClockSpeed"))
                                      for r in _list(d.get("ram"))])
                + "<p class='mut'>File di paging: %s</p>" % ("automatico" if (d.get("pagefile") or {}).get("auto")
                                                            else ", ".join("%s (%s MB)" % (f.get("Name"), f.get("AllocatedBaseSize"))
                                                                           for f in _list((d.get("pagefile") or {}).get("files"))) or "DISATTIVATO")))
    gpu_rows = [(x.get("Name"), x.get("DriverVersion"), x.get("DriverDate")) for x in _list(d.get("gpus"))]
    extra = ""
    if nv:
        extra = "<table>" + _rows([
            ("PCIe", "Gen %s (max %s), x%s (max x%s)" % tuple(
                int(nv[k]) if isinstance(nv.get(k), float) else nv.get(k) for k in
                ("pcie.link.gen.current", "pcie.link.gen.max", "pcie.link.width.current", "pcie.link.width.max"))),
            ("Limite di potenza", "%s W (max %s W)" % (nv.get("power.limit"), nv.get("power.max_limit"))),
            ("Frequenze massime", "GPU %s MHz, memoria %s MHz" % (nv.get("clocks.max.graphics"), nv.get("clocks.max.memory"))),
            ("Resizable BAR", ("attivo (%s MB)" % nv["bar1_mb"]) if nv.get("bar1_mb", 0) > 256 else "disattivato"
             if "bar1_mb" in nv else "?"),
        ]) + "</table><p class='mut'>Nota: a riposo la GPU abbassa la generazione PCIe per risparmiare: e' normale.</p>"
    sec.append(("Scheda video (%s, %s MB VRAM)" % (g.get("name", "?"), g.get("vram_mb", "?")),
                _table(["Scheda", "Driver", "Data driver"], gpu_rows) + extra))
    sec.append(("Schermi", _table(["Schermo", "Collegato a", "Risoluzione", "Frequenza attuale", "Frequenza massima"],
                                  [(x["device"].replace("\\\\.\\", "") + (" (principale)" if x["primary"] else ""),
                                    x["gpu"], "%dx%d" % (x["width"], x["height"]), "%d Hz" % x["hz"], "%d Hz" % x["max_hz"])
                                   for x in d.get("displays", [])])
                + "<p class='mut'>Modelli: %s</p>" % html.escape(", ".join(
                    (m.get("maker") or "") + " " + (m.get("name") or "") for m in _list(d.get("monitors"))))))
    sec.append(("Dischi", _table(["Disco", "Tipo", "Collegamento", "Capacita'", "Salute", "Temp", "Usura", "Ore accensione"],
                                 [(x.get("name"), x.get("media"), x.get("bus"), gb(x.get("size")), x.get("health"),
                                   x.get("temp"), x.get("wear"), x.get("hours")) for x in _list(d.get("disks"))])
                + _table(["Unita'", "Nome", "Capacita'", "Libero"],
                         [(x.get("DriveLetter"), x.get("FileSystemLabel"), gb(x.get("Size")), gb(x.get("SizeRemaining")))
                          for x in _list(d.get("volumes"))])))
    sec.append(("Rete", _table(["Scheda", "Velocita'", "Tipo", "Driver"],
                               [(x.get("InterfaceDescription"), x.get("LinkSpeed"), x.get("PhysicalMediaType"),
                                 x.get("DriverVersion")) for x in _list(d.get("net"))])))
    sec.append(("Errori ultimi 30 giorni", "<table>" + _rows([
        ("Errori hardware (WHEA)", d.get("ev_whea")), ("Blocchi driver video (TDR)", d.get("ev_tdr")),
        ("Spegnimenti improvvisi", d.get("ev_kp41")), ("Schermate blu", d.get("ev_bsod")),
    ]) + "</table>" + _table(["Programma in crash", "Volte"], [(c.get("Name"), c.get("Count"))
                                                              for c in _list(d.get("ev_appcrash")) if c])))
    tw_rows = [(t["cat"], t["nome"], {True: "ATTIVA", False: "-", None: "?"}[t["stato"]] +
                (" (LagDoctor)" if t["da_lagdoctor"] else "")) for t in d.get("tweaks", [])]
    sec.append(("Stato delle %d ottimizzazioni" % len(tw_rows), _table(["Categoria", "Ottimizzazione", "Stato"], tw_rows)))
    sec.append(("Programmi all'avvio (%d)" % len(_list(d.get("startup"))),
                _table(["Nome", "Comando"], [(x.get("Name"), x.get("Command")) for x in _list(d.get("startup"))])))
    sec.append(("Servizi di terze parti attivi", _table(["Servizio", "Nome"], [(x.get("Name"), x.get("DisplayName"))
                                                                              for x in _list(d.get("services3p"))])))
    sec.append(("Processi che usano piu' RAM", _table(["Processo", "RAM"], [(n, "%.0f MB" % m)
                                                                          for n, m in d.get("proc_top_ram", [])])))
    sec.append(("Antivirus", _table(["Prodotto"], [(a.get("displayName"),) for a in _list(d.get("av")) if a])))
    prefs = d.get("gpu_prefs") or {}
    if prefs:
        sec.append(("Impostazioni grafiche per app (Windows)", _table(["Programma / globale", "Valore"], sorted(prefs.items()))))
    sec.append(("Programmi installati (%d)" % len(_list(d.get("apps"))),
                _table(["Nome", "Versione", "Produttore"], [(a.get("DisplayName"), a.get("DisplayVersion"), a.get("Publisher"))
                                                           for a in _list(d.get("apps"))])))

    prob_html = ""
    for p in sorted(probs, key=lambda x: -x["gravita"]):
        label, color = SEV[p["gravita"]]
        prob_html += ('<div class="prob" style="border-left-color:%s"><div class="ph"><span class="sev" style="background:%s">'
                      '%s</span><b>%s</b>%s</div><p>%s</p><p class="fix"><b>Come risolvere:</b> %s</p></div>'
                      % (color, color, label, html.escape(p["titolo"]),
                         ' <span class="auto">Correzione automatica disponibile</span>' if p.get("auto_fix") else "",
                         html.escape(p["spiegazione"]), html.escape(p["soluzione"])))
    if not probs:
        prob_html = '<div class="prob" style="border-left-color:#46c37b"><b>Nessun problema trovato.</b></div>'
    body = "".join("<details %s><summary>%s</summary><div class='card'>%s</div></details>"
                   % ("open" if i < 5 else "", html.escape(t), c) for i, (t, c) in enumerate(sec))
    page = """<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LagDoctor - Scansione</title><style>
body{margin:0;background:#0f1115;color:#e8eaf0;font:14px/1.5 "Segoe UI",system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{margin:0 0 4px}.mut{color:#9aa3b2}
summary{cursor:pointer;font-size:17px;font-weight:600;margin:18px 0 8px}
.card{background:#181b22;border-radius:10px;padding:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%%;margin-bottom:8px}td,th{padding:5px 8px;border-bottom:1px solid #2a2f3a;text-align:left;vertical-align:top}
th{color:#9aa3b2;font-weight:600}
.prob{background:#181b22;border-left:5px solid;border-radius:8px;padding:12px 14px;margin-bottom:10px}.prob p{margin:6px 0}
.fix{color:#cfe3ff}.ph{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.sev{color:#000;font-size:11px;font-weight:700;padding:2px 7px;border-radius:5px}
.auto{font-size:12px;color:#46c37b;border:1px solid #46c37b;border-radius:5px;padding:1px 6px}
</style></head><body><main><h1>Scansione completa del sistema</h1><div class="mut">%s</div>
<h2>Problemi trovati (%d)</h2>%s<h2>Dettagli del sistema</h2>%s</main></body></html>""" % (
        datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), len(probs), prob_html, body)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
