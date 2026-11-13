"""Controlli della configurazione di Windows e dell'hardware (prima di giocare)."""
import json
import os
import subprocess

try:
    import winreg
except ImportError:  # non Windows (solo per test)
    winreg = None

CREATE_NO_WINDOW = 0x08000000

# Programmi noti per causare stutter (polling sensori, overlay, RGB, sync)
KNOWN_BAD = {
    "armourycrate.service.exe": "ASUS Armoury Crate (noto per causare micro-scatti)",
    "armourycrate.usersessionhelper.exe": "ASUS Armoury Crate",
    "lightingservice.exe": "ASUS Aura (RGB)",
    "icue.exe": "Corsair iCUE (polling dei sensori)",
    "nzxt cam.exe": "NZXT CAM (polling dei sensori)",
    "signalrgb.exe": "SignalRGB",
    "hwinfo64.exe": "HWiNFO (polling dei sensori: aumenta l'intervallo a 2000 ms o chiudilo)",
    "aida64.exe": "AIDA64 (polling dei sensori)",
    "wallpaper64.exe": "Wallpaper Engine",
    "wallpaper32.exe": "Wallpaper Engine",
    "razer synapse 3.exe": "Razer Synapse",
    "razer synapse service.exe": "Razer Synapse",
    "msi.centralserver.exe": "MSI Center",
    "msi_dragon_center.exe": "MSI Dragon Center",
    "onedrive.exe": "OneDrive (se sta sincronizzando usa disco e CPU)",
    "steamwebhelper.exe": None,  # normale, ignorato
}


def _ps(command, timeout=20):
    """Esegue un comando PowerShell e restituisce l'output (o None)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, encoding=("oem" if os.name == "nt" else None), errors="replace", timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return out.stdout.strip() or None
    except Exception:
        return None


def _ps_json(command):
    out = _ps(command + " | ConvertTo-Json -Compress")
    if not out:
        return None
    try:
        data = json.loads(out)
        return data if isinstance(data, list) else [data]
    except ValueError:
        return None


def _reg_get(root, path, name):
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def ram_info():
    sticks = _ps_json("Get-CimInstance Win32_PhysicalMemory | "
                      "Select-Object Capacity,Speed,ConfiguredClockSpeed,SMBIOSMemoryType")
    return sticks or []


def gpu_info():
    from . import gpu
    return gpu.gpu_info()


def refresh_rate():
    data = _ps_json("Get-CimInstance Win32_VideoController | Select-Object Name,CurrentRefreshRate")
    rates = [d.get("CurrentRefreshRate") for d in (data or []) if d.get("CurrentRefreshRate")]
    return max(rates) if rates else None


def cpu_name():
    data = _ps_json("Get-CimInstance Win32_Processor | Select-Object Name")
    return data[0]["Name"].strip() if data else "?"


def power_plan():
    try:
        out = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, encoding=("oem" if os.name == "nt" else None), errors="replace",
                             timeout=10, creationflags=CREATE_NO_WINDOW).stdout
        return out.split("(")[-1].rstrip(") \r\n") if "(" in out else out.strip()
    except Exception:
        return None


def drive_info(path):
    """Tipo di disco (SSD/HDD, NVMe) e spazio libero per il disco dove si trova `path`."""
    drive = os.path.splitdrive(path)[0].rstrip(":") or "C"
    res = {"lettera": drive}
    try:
        import shutil
        u = shutil.disk_usage(drive + ":\\")
        res["libero_pct"] = u.free / u.total * 100
        res["libero_gb"] = u.free / 1e9
    except Exception:
        pass
    data = _ps_json("$n=(Get-Partition -DriveLetter %s | Get-Disk).Number; "
                    "Get-PhysicalDisk | Where-Object DeviceId -eq $n | "
                    "Select-Object FriendlyName,MediaType,BusType" % drive)
    if data:
        d = data[0]
        media = {3: "HDD", 4: "SSD", "HDD": "HDD", "SSD": "SSD"}.get(d.get("MediaType"), str(d.get("MediaType")))
        bus = {17: "NVMe", 11: "SATA", 7: "USB", "NVMe": "NVMe", "SATA": "SATA", "USB": "USB"}.get(
            d.get("BusType"), str(d.get("BusType")))
        res.update(nome=d.get("FriendlyName"), tipo=media, bus=bus)
    return res


def game_dvr_enabled():
    if winreg is None:
        return None
    a = _reg_get(winreg.HKEY_CURRENT_USER, r"System\GameConfigStore", "GameDVR_Enabled")
    b = _reg_get(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\GameDVR",
                 "AppCaptureEnabled")
    # Se la chiave non esiste Windows la considera attiva
    return (a is None or a == 1) or (b is None or b == 1)


def game_mode_enabled():
    if winreg is None:
        return None
    v = _reg_get(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar", "AutoGameModeEnabled")
    return v is None or v == 1  # di default attiva


def hags_enabled():
    if winreg is None:
        return None
    v = _reg_get(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode")
    return v == 2


SECURITY_SERVICES = {1: "Credential Guard", 2: "Integrita' della memoria (HVCI)", 3: "System Guard Secure Launch",
                     4: "SMM Firmware Measurement", 5: "Protezione stack hardware in modalita' kernel",
                     7: "Hypervisor-Enforced Paging Translation"}


def vbs_state():
    """Stato REALE del VBS (non solo il registro).

    Restituisce dict(vbs=True/False, hvci=True/False, services=[nomi], causes=[funzioni che lo tengono acceso])
    oppure None se non si riesce a leggere.
    """
    data = _ps_json("$d = Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\\Microsoft\\Windows\\DeviceGuard; "
                    "$f = @(Get-WindowsOptionalFeature -Online -ErrorAction SilentlyContinue | Where-Object { "
                    "$_.FeatureName -in 'VirtualMachinePlatform','Microsoft-Hyper-V-All','Microsoft-Windows-Subsystem-Linux',"
                    "'Containers-DisposableClientVM','HypervisorPlatform' -and $_.State.ToString() -eq 'Enabled' } | "
                    "ForEach-Object FeatureName); "
                    "[pscustomobject]@{ vbs = $d.VirtualizationBasedSecurityStatus; running = @($d.SecurityServicesRunning); "
                    "features = $f; hv = [bool]((bcdedit /enum '{current}') -match 'hypervisorlaunchtype\\s+(Auto|Automatico)') }")
    if not data:
        return None
    d = data[0]
    running = [int(x) for x in (d.get("running") or []) if str(x).isdigit()]
    names = {"VirtualMachinePlatform": "Piattaforma macchina virtuale", "Microsoft-Hyper-V-All": "Hyper-V",
             "Microsoft-Windows-Subsystem-Linux": "WSL", "Containers-DisposableClientVM": "Windows Sandbox",
             "HypervisorPlatform": "Piattaforma hypervisor Windows"}
    feats = d.get("features") or []
    feats = [feats] if isinstance(feats, str) else feats
    return {"vbs": d.get("vbs") == 2, "hvci": 2 in running,
            "services": [SECURITY_SERVICES.get(x, "servizio %d" % x) for x in running if x],
            "causes": [names.get(f, f) for f in feats], "hypervisor": bool(d.get("hv"))}


DPC_SUSPECTS = ("realtek", "killer", "wi-fi", "wifi", "wireless", "nahimic", "sonic", "bluetooth", "asmedia",
                "high definition audio", "usb audio", "intel(r) ethernet", "rgb", "aura", "icue")


def suspect_drivers():
    """Driver di rete, audio, Bluetooth e USB installati, ordinati: prima quelli piu' spesso colpevoli di latenza DPC."""
    data = _ps_json("Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceClass -in "
                    "'NET','MEDIA','BLUETOOTH','USB' -and $_.DeviceName } | Select-Object DeviceName,DriverVersion,"
                    "DriverDate,DeviceClass")
    out = []
    for d in data or []:
        name = d.get("DeviceName") or ""
        low = name.lower()
        if any(x in low for x in ("root hub", "generic", "composite", "microsoft", "wan miniport", "virtual",
                                  "kernel debug", "teredo", "hyper-v")):
            continue
        date = str(d.get("DriverDate") or "")[:8]
        score = sum(1 for k in DPC_SUSPECTS if k in low)
        out.append((score, "%s (driver %s%s)" % (name, d.get("DriverVersion") or "?",
                                                   (", " + date[:4]) if date[:4].isdigit() else "")))
    out.sort(key=lambda x: -x[0])
    seen, res = set(), []
    for _, txt in out:
        if txt not in seen:
            seen.add(txt)
            res.append(txt)
    return res


def running_known_bad():
    import psutil
    found = {}
    for p in psutil.process_iter(["name"]):
        n = (p.info["name"] or "").lower()
        if KNOWN_BAD.get(n):
            found[p.info["name"]] = KNOWN_BAD[n]
    return found


HW_FILE = None  # impostato dal server: file dove salvare l'hardware dopo il primo avvio


def hw_fingerprint():
    """Impronta veloce dell'hardware (registro + RAM totale): se cambia, l'hardware va riletto."""
    import psutil
    from . import cputopo
    from . import gpu as gpumod
    try:
        ads = sorted("%s|%s" % (a.get("name"), a.get("driver")) for a in gpumod.list_adapters())
    except Exception:
        ads = []
    return "%s|%d|%s" % (cputopo.cpu_name(), round(psutil.virtual_memory().total / 2**30), ";".join(ads))


def read_hardware():
    """Lettura completa dell'hardware (lenta: WMI). Si fa solo al primo avvio o se l'hardware cambia."""
    import psutil
    sticks = ram_info()
    total_gb = sum(int(s.get("Capacity") or 0) for s in sticks) / 2**30 if sticks \
        else psutil.virtual_memory().total / 2**30
    speed = max((s.get("ConfiguredClockSpeed") or 0 for s in sticks), default=0)
    ddr5 = any(s.get("SMBIOSMemoryType") == 34 for s in sticks)
    return {"cpu": cpu_name(), "gpu": gpu_info(), "ram_gb": total_gb, "ram_sticks": len(sticks),
            "ram_speed": speed, "ram_ddr5": ddr5, "refresh_hz": refresh_rate(),
            "ram": "%.0f GB, %d banchi, %s MT/s%s" % (total_gb, len(sticks), speed or "?", " DDR5" if ddr5 else "")}


def cached_hardware():
    """Hardware salvato al primo avvio, se il PC e' lo stesso (altrimenti None)."""
    if not HW_FILE or not os.path.exists(HW_FILE):
        return None
    try:
        with open(HW_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("fingerprint") == hw_fingerprint() and d.get("hw", {}).get("cpu"):
            return d["hw"]
    except (OSError, ValueError):
        pass
    return None


def save_hardware(hw):
    if not HW_FILE:
        return
    try:
        with open(HW_FILE, "w", encoding="utf-8") as f:
            json.dump({"fingerprint": hw_fingerprint(), "hw": hw}, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def run_all(hw=None):
    """Esegue tutti i controlli. Restituisce (sysinfo, lista_problemi).

    hw: hardware gia' letto (dal file salvato): in quel caso si rileggono solo le impostazioni.
    """
    info = {}
    problems = []
    if hw is None:
        hw = read_hardware()
        save_hardware(hw)
    else:
        hw = dict(hw)
        hz = refresh_rate()  # la frequenza del monitor e' un'impostazione: si rilegge sempre
        if hz:
            hw["refresh_hz"] = hz
    info.update({k: hw.get(k) for k in ("cpu", "gpu", "refresh_hz", "ram_gb", "ram")})
    info["power_plan"] = power_plan()
    speed, ddr5, nsticks = hw.get("ram_speed") or 0, hw.get("ram_ddr5"), hw.get("ram_sticks") or 0

    if ddr5 and 0 < speed <= 5200:
        problems.append(dict(
            gravita=3, titolo="RAM non sta usando il profilo EXPO/XMP",
            spiegazione="Le tue DDR5 girano a %d MT/s, cioe' la velocita' base. I kit da gaming sono "
                        "venduti per 6000 MT/s o simili, ma vanno attivati nel BIOS. Con un Ryzen la RAM "
                        "lenta peggiora soprattutto gli 1%% low (cioe' gli scatti)." % speed,
            soluzione="Riavvia, entra nel BIOS (tasto CANC/DEL all'avvio), cerca 'EXPO' (o 'XMP' / "
                      "'DOCP') e attiva il Profilo 1. Salva ed esci (F10). Il primo avvio puo' durare "
                      "1-2 minuti per l'allenamento della memoria: e' normale.",
            auto_fix=None))
    if nsticks == 1:
        problems.append(dict(
            gravita=3, titolo="Un solo banco di RAM (single channel)",
            spiegazione="Con un solo banco la banda della memoria e' dimezzata.",
            soluzione="Usa due banchi uguali negli slot indicati dal manuale (di solito A2 e B2).",
            auto_fix=None))
    elif nsticks == 4 and ddr5:
        problems.append(dict(
            gravita=1, titolo="4 banchi di DDR5",
            spiegazione="Con 4 banchi DDR5 spesso la RAM non regge le velocita' EXPO ed e' meno stabile.",
            soluzione="Se possibile, usa 2 banchi (es. 2x16 o 2x32 GB).",
            auto_fix=None))

    if game_dvr_enabled():
        problems.append(dict(
            gravita=2, titolo="Registrazione in background Xbox Game Bar attiva",
            spiegazione="Windows registra continuamente gli ultimi secondi di gioco: usa GPU e disco "
                        "ed e' una causa nota di micro-scatti.",
            soluzione="Lo posso disattivare io (correzione automatica).",
            auto_fix=("disable_game_dvr", None)))
    if game_mode_enabled() is False:
        problems.append(dict(
            gravita=1, titolo="Modalita' Gioco di Windows disattivata",
            spiegazione="La Modalita' Gioco riduce le attivita' in background mentre giochi.",
            soluzione="La posso attivare io (correzione automatica).",
            auto_fix=("enable_game_mode", None)))
    vendor = (info.get("gpu") or {}).get("vendor")
    if vendor == "amd":
        problems.append(dict(
            gravita=1, titolo="Impostazioni Radeon da controllare in AMD Software Adrenalin",
            spiegazione="Alcune funzioni del driver AMD sono cause comuni di scatti. Il programma non puo' "
                        "leggerle, quindi controllale tu una volta.",
            soluzione="1) Registrazione > 'Replay istantaneo' e 'Registra desktop' = Disattivati. "
                      "2) Gaming > Grafica: 'Radeon Chill' = Disattivato (usa il limite FPS al suo posto), "
                      "'Cache shader' = Ottimizzata AMD. 3) Prestazioni > Ottimizzazione: niente "
                      "undervolt/overclock automatici mentre fai le prove. 4) Nel BIOS attiva 'Re-Size BAR' "
                      "/ 'Smart Access Memory' e 'Above 4G Decoding' (se la scheda madre lo supporta). "
                      "5) Driver aggiornato da amd.com (per cambiare marca o se hai problemi strani, prima "
                      "pulisci con DDU).",
            auto_fix=None))
    if (info.get("gpu") or {}).get("integrated"):
        problems.append(dict(
            gravita=1, titolo="Grafica integrata: usa la RAM del sistema come memoria video",
            spiegazione="Questo PC non ha una scheda video dedicata: la grafica integrata nel processore usa la "
                        "RAM al posto della VRAM. Per questo la velocita' della RAM e il dual channel contano "
                        "moltissimo per gli FPS, e la RAM libera e' anche la memoria per le texture.",
            soluzione="Due banchi di RAM (dual channel), profilo XMP/EXPO attivo nel BIOS, driver grafico aggiornato "
                      "dal sito del produttore. Nei giochi: texture basse/medie e upscaling (XeSS / FSR) attivo.",
            auto_fix=None))
    if vendor is None:
        problems.append(dict(
            gravita=1, titolo="Scheda video non riconosciuta",
            spiegazione="Non riesco a leggere le informazioni della scheda video.",
            soluzione="Installa o aggiorna il driver ufficiale della scheda (nvidia.com, amd.com o intel.com).",
            auto_fix=None))

    vbs = vbs_state()
    info["vbs"] = vbs
    if vbs and vbs["hvci"]:
        problems.append(dict(
            gravita=1, titolo="Integrita' della memoria (Isolamento core) attiva",
            spiegazione="L'Integrita' della memoria controlla ogni driver con la virtualizzazione: nei test di Tom's "
                        "Hardware puo' costare fino al 5-10% di FPS e peggiorare gli 1% low in alcuni giochi.",
            soluzione="Opzionale: Sicurezza di Windows > Sicurezza dispositivi > Isolamento core > Integrita' della "
                      "memoria = Disattivato, poi riavvia (o usa la voce 'Disattiva tutta la virtualizzazione' in "
                      "Ottimizzazioni). E' una scelta tra "
                      "sicurezza e prestazioni.",
            auto_fix=None))
    elif vbs and vbs["vbs"]:
        why = []
        if vbs["services"]:
            why.append("servizi attivi: " + ", ".join(vbs["services"]))
        if vbs["causes"]:
            why.append("funzioni di Windows che usano la virtualizzazione: " + ", ".join(vbs["causes"]))
        reg_on = winreg is not None and _reg_get(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\DeviceGuard",
                                                 "EnableVirtualizationBasedSecurity") == 1
        if why:
            sol = ("Se non usi WSL, macchine virtuali, Sandbox o app Android: Ottimizzazioni > 'Disattiva tutta la "
                   "virtualizzazione' (spegne tutto insieme), poi riavvia. Altrimenti puoi ignorare questo avviso.")
        else:
            why.append("nessuna funzione lo usa: e' acceso solo perche' " + (
                "nel registro e' attivato (EnableVirtualizationBasedSecurity = 1, impostazione predefinita di "
                "Windows 11)" if reg_on else "Windows 11 lo attiva di default"))
            sol = ("Ottimizzazioni > 'Disattiva tutta la virtualizzazione' (categoria Sicurezza), poi riavvia. Le "
                   "Funzionalita' di Windows le hai gia' spente: resta da spegnere il VBS nel registro.")
        problems.append(dict(
            gravita=1, titolo="VBS attivo (ma l'Isolamento core e' gia' spento)",
            spiegazione="L'Integrita' della memoria e' disattivata correttamente, ma la piattaforma VBS e' comunque "
                        "accesa (" + "; ".join(why) + "). Costa meno dell'Integrita' della memoria, ma l'hypervisor "
                        "resta attivo.",
            soluzione=sol, auto_fix=None))
    info["hags"] = hags_enabled()
    pp = (info["power_plan"] or "").lower()
    if pp and ("risparmio" in pp or "saver" in pp):
        problems.append(dict(
            gravita=2, titolo="Piano energetico 'Risparmio energia'",
            spiegazione="La CPU viene limitata per risparmiare corrente.",
            soluzione="Pannello di controllo > Opzioni risparmio energia > 'Bilanciato' (per i Ryzen e' "
                      "quello consigliato da AMD).",
            auto_fix=None))

    bad = running_known_bad()
    if bad:
        problems.append(dict(
            gravita=2, titolo="Programmi in background noti per causare scatti",
            spiegazione="Sono attivi: " + "; ".join("%s = %s" % (k, v) for k, v in bad.items()),
            soluzione="Chiudili prima di giocare e toglili dall'avvio automatico (Gestione attivita' > "
                      "App di avvio). Posso chiuderli io adesso.",
            auto_fix=("close_processes", list(bad.keys()))))

    return info, problems


def check_game_drive(exe_path):
    """Controlli sul disco dove e' installato il gioco."""
    problems = []
    d = drive_info(exe_path)
    if d.get("tipo") == "HDD":
        problems.append(dict(
            gravita=3, titolo="Il gioco e' installato su un hard disk meccanico (HDD)",
            spiegazione="Disco %s: (%s). I giochi moderni caricano dati in continuo: su HDD scattano."
                        % (d["lettera"], d.get("nome")),
            soluzione="Sposta il gioco su un SSD (da Steam: Proprieta' > File installati > Sposta cartella).",
            auto_fix=None))
    if d.get("libero_pct") is not None and d["libero_pct"] < 10:
        problems.append(dict(
            gravita=2, titolo="Disco del gioco quasi pieno",
            spiegazione="Sul disco %s: resta il %.0f%% libero (%.0f GB). Un SSD quasi pieno rallenta molto."
                        % (d["lettera"], d["libero_pct"], d["libero_gb"]),
            soluzione="Libera spazio fino ad avere almeno il 15% libero.",
            auto_fix=None))
    return d, problems
