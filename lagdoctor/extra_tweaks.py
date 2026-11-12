"""Debloat, Timer Resolution, impostazioni di Windows e 'miti' (tweak non affidabili) attivabili."""
import ctypes
import os
import re
import subprocess
import sys
import time

from . import tweaks as T
from .tweaks import DWORD, SZ, CmdTweak, RegTweak, Tweak, ps, run

# ============================================================================ DEBLOAT (app preinstallate)

_APPX_CACHE = {"t": 0, "names": None}


_APPX_LOCK = __import__("threading").Lock()


def installed_appx():
    """Nomi dei pacchetti Store installati per l'utente (una sola chiamata, in cache 20 s)."""
    with _APPX_LOCK:
        return _installed_appx()


def _installed_appx():
    if _APPX_CACHE["names"] is not None and time.time() - _APPX_CACHE["t"] < 20:
        return _APPX_CACHE["names"]
    code, out = ps("Get-AppxPackage | ForEach-Object Name", timeout=90)
    names = {line.strip().lower() for line in out.splitlines() if line.strip()} if code == 0 else None
    _APPX_CACHE.update(t=time.time(), names=names)
    return names


class AppxTweak(Tweak):
    """Rimuove un'app dello Store solo per l'utente: resta la copia di sistema, quindi Annulla la reinstalla."""

    def __init__(self, *a, packages, **kw):
        super().__init__(*a, **kw)
        self.packages = packages

    def status(self):
        names = installed_appx()
        if names is None:
            return None
        return not any(p.lower() in names for p in self.packages)

    def apply(self):
        for p in self.packages:
            ps("Get-AppxPackage -Name '%s' | Remove-AppxPackage -ErrorAction SilentlyContinue" % p, timeout=180)
        _APPX_CACHE["names"] = None
        return {"packages": self.packages}

    def revert(self, backup):
        for p in backup.get("packages", self.packages):
            ps("$m = @(Get-AppxPackage -AllUsers -Name '%s' | ForEach-Object { Join-Path $_.InstallLocation "
               "'AppxManifest.xml' }) + @(Get-AppxProvisionedPackage -Online | Where-Object DisplayName -eq '%s' | "
               "ForEach-Object { Join-Path $_.InstallLocation 'AppxManifest.xml' }); "
               "foreach ($x in $m) { if (Test-Path $x) { Add-AppxPackage -DisableDevelopmentMode -Register $x "
               "-ErrorAction SilentlyContinue; break } }" % (p, p), timeout=300)
        _APPX_CACHE["names"] = None


DEB = "Debloat (app preinstallate)"
_W11D = "Win11Debloat (Raphire): app classificate 'safe'"


def _app(tid, name, pkgs, what, eff="bassa", risk=0, rec=True, **kw):
    return AppxTweak(tid, DEB, name, what, eff, risk=risk, packages=pkgs, source=_W11D,
                     recommend=(None if rec is None else (lambda s: rec)), **kw)


DEBLOAT = [
    _app("app_bing", "Rimuovi Meteo, Notizie, Sport, Finanza (Bing)",
         ["Microsoft.BingWeather", "Microsoft.BingNews", "Microsoft.BingSports", "Microsoft.BingFinance",
          "Microsoft.BingTravel", "Microsoft.BingFoodAndDrink", "Microsoft.BingHealthAndFitness",
          "Microsoft.BingTranslator"],
         "App di Bing che scaricano notizie e meteo in background."),
    _app("app_solitaire", "Rimuovi Microsoft Solitaire Collection", ["Microsoft.MicrosoftSolitaireCollection"],
         "Il solitario con pubblicita' e servizi Xbox in background."),
    _app("app_candy", "Rimuovi giochi e app sponsorizzate (Candy Crush, TikTok, Spotify...)",
         ["king.com.CandyCrushSaga", "king.com.CandyCrushSodaSaga", "king.com.BubbleWitch3Saga",
          "BytedancePte.Ltd.TikTok", "SpotifyAB.SpotifyMusic", "Facebook.Instagram", "FACEBOOK.FACEBOOK",
          "Disney.37853FC22B2CE", "4DF9E0F8.Netflix", "AmazonVideo.PrimeVideo", "7EE7776C.LinkedInforWindows",
          "LinkedInforWindows"],
         "Collegamenti e giochi promozionali installati da Windows."),
    _app("app_clipchamp", "Rimuovi Clipchamp", ["Clipchamp.Clipchamp"], "Editor video online di Microsoft."),
    _app("app_officehub", "Rimuovi 'Microsoft 365 (Office)' (app promozionale)", ["Microsoft.MicrosoftOfficeHub"],
         "App che pubblicizza Microsoft 365. NON tocca Office se lo hai installato."),
    _app("app_getstarted", "Rimuovi Suggerimenti (Get Started)", ["Microsoft.Getstarted"],
         "L'app dei suggerimenti di Windows."),
    _app("app_feedback", "Rimuovi Hub di Feedback", ["Microsoft.WindowsFeedbackHub"],
         "Serve solo per inviare segnalazioni a Microsoft."),
    _app("app_maps", "Rimuovi Mappe", ["Microsoft.WindowsMaps"], "L'app Mappe di Windows (aggiorna le mappe offline)."),
    _app("app_todo", "Rimuovi Microsoft To Do", ["Microsoft.Todos"], "App per elenchi di attivita'."),
    _app("app_powerautomate", "Rimuovi Power Automate", ["Microsoft.PowerAutomateDesktop"],
         "Strumento di automazione per aziende."),
    _app("app_devhome", "Rimuovi Dev Home", ["Microsoft.Windows.DevHome"], "Pannello per sviluppatori (dismesso)."),
    _app("app_mixedreality", "Rimuovi Portale realta' mista e 3D Viewer",
         ["Microsoft.MixedReality.Portal", "Microsoft.Microsoft3DViewer", "Microsoft.3DBuilder", "Microsoft.Print3D"],
         "Funzioni per visori di realta' mista Windows (dismessi) e modelli 3D."),
    _app("app_teams", "Rimuovi Microsoft Teams (versione personale)", ["MicrosoftTeams", "MSTeams"],
         "Teams preinstallato, che parte con Windows.", eff="media"),
    _app("app_skype_people", "Rimuovi Skype, Contatti e Posta/Calendario vecchi",
         ["Microsoft.SkypeApp", "Microsoft.People", "Microsoft.windowscommunicationsapps", "Microsoft.Messaging"],
         "App dismesse o sostituite da Outlook."),
    _app("app_family", "Rimuovi Microsoft Family", ["MicrosoftCorporationII.MicrosoftFamily"],
         "Controllo genitori: tienila se la usi per gli account dei figli."),
    _app("app_journal_sway", "Rimuovi Journal, Sway, OneNote (app), Power BI",
         ["Microsoft.MicrosoftJournal", "Microsoft.Office.Sway", "Microsoft.Office.OneNote",
          "Microsoft.MicrosoftPowerBIForWindows"], "App di produttivita' raramente usate."),
    _app("app_zunevideo", "Rimuovi Film e TV", ["Microsoft.ZuneVideo"],
         "Il vecchio lettore 'Film e TV' (il Lettore multimediale resta)."),
    _app("app_xboxold", "Rimuovi la vecchia 'Xbox Console Companion'", ["Microsoft.XboxApp"],
         "La VECCHIA app Xbox. La nuova app Xbox, Game Bar e i servizi Xbox NON vengono toccati."),
    _app("app_pcmanager", "Rimuovi Microsoft PC Manager e AI Hub",
         ["Microsoft.PCManager", "Microsoft.MicrosoftPCManager", "Microsoft.Windows.AIHub"],
         "'Ottimizzatore' di Microsoft e vetrina AI."),
    _app("app_cortana", "Rimuovi Cortana", ["Microsoft.549981C3F5F10"], "L'assistente dismesso."),
    _app("app_alarms_recorder", "Rimuovi Sveglie e Registratore di suoni",
         ["Microsoft.WindowsAlarms", "Microsoft.WindowsSoundRecorder"],
         "Orologio/sveglie e registratore audio.", eff="comfort", rec=None),
    _app("app_stickynotes", "Rimuovi Sticky Notes", ["Microsoft.MicrosoftStickyNotes"], "Note adesive.",
         eff="comfort", rec=None),
    _app("app_outlook_new", "Rimuovi il nuovo Outlook", ["Microsoft.OutlookForWindows"],
         "Il nuovo Outlook gratuito preinstallato.", eff="comfort", rec=None),
    _app("app_phonelink", "Rimuovi Collegamento al telefono", ["Microsoft.YourPhone", "MicrosoftWindows.CrossDevice"],
         "Collega lo smartphone al PC; resta in background.", rec=None),
    CmdTweak("app_onedrive", DEB, "Disinstalla OneDrive",
             "OneDrive sincronizza i file in background (disco e rete) e parte con Windows.", "media", risk=1,
             on="winget uninstall --id Microsoft.OneDrive --silent --accept-source-agreements; "
                "Stop-Process -Name OneDrive -ErrorAction SilentlyContinue",
             off="winget install --id Microsoft.OneDrive --silent --accept-package-agreements --accept-source-agreements",
             check="-not (Test-Path \"$env:LOCALAPPDATA\\Microsoft\\OneDrive\\OneDrive.exe\") -and "
                   "-not (Test-Path \"$env:ProgramFiles\\Microsoft OneDrive\\OneDrive.exe\")",
             warning="Se usi OneDrive per backup o sincronizzazione, smette di funzionare. I file gia' presenti nella "
                     "cartella OneDrive restano sul PC.",
             recommend=lambda s: None, source="Win11Debloat (opzionale)"),
]


# ============================================================================ TIMER RESOLUTION

TIMER_TASK = "LagDoctor TimerResolution"


def timer_now_ms():
    """Risoluzione attuale del timer di Windows in ms (es. 0.5, 1.0, 15.625), o None."""
    try:
        import ctypes
        mn, mx, cur = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
        ctypes.windll.ntdll.NtQueryTimerResolution(ctypes.byref(mn), ctypes.byref(mx), ctypes.byref(cur))
        return cur.value / 10000.0
    except Exception:
        return None
TIMER_SCRIPT = r'''# LagDoctor - Timer Resolution: tiene il timer di Windows a 0,5 ms finche' il PC e' acceso.
import ctypes, time
from ctypes import wintypes
k32 = ctypes.windll.kernel32
class PPT(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]
# Windows 11 ignora le richieste dei processi senza finestra visibile: chiediamo di non essere ignorati.
s = PPT(1, 0x4, 0)
k32.SetProcessInformation(k32.GetCurrentProcess(), 4, ctypes.byref(s), ctypes.sizeof(s))
cur = wintypes.ULONG()
ctypes.windll.ntdll.NtSetTimerResolution(%d, True, ctypes.byref(cur))
while True:
    time.sleep(3600)
'''


class TimerResTweak(Tweak):
    def __init__(self, *a, units=5000, **kw):
        super().__init__(*a, **kw)
        self.units = units  # unita' da 100 ns: 5000 = 0,5 ms

    def _cmd(self):
        """Comando che tiene il timer: LagDoctor.exe --timer (installato) o uno script Python (AVVIA.bat)."""
        from . import paths
        if paths.FROZEN:
            return paths.gui_cmd("--timer", str(self.units))
        tools = os.path.join(T.ROOT or ".", "strumenti")
        os.makedirs(tools, exist_ok=True)
        script = os.path.join(tools, "timer_resolution.pyw")
        with open(script, "w", encoding="utf-8") as f:
            f.write(TIMER_SCRIPT % self.units)
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        return [pyw if os.path.isfile(pyw) else sys.executable, script]

    def status(self):
        """Attiva se GlobalTimerResolutionRequests = 1 e il timer di Windows e' davvero a ~0,5 ms, chiunque lo tenga
        (LagDoctor, EXM, TimerResolution, ISLC...): conta lo stato reale, non chi l'ha impostato."""
        glob = T.reg_read("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel",
                          "GlobalTimerResolutionRequests")[0]
        code, out = run(["schtasks", "/Query", "/TN", TIMER_TASK])
        ours = code == 0
        cur = timer_now_ms()
        self.note = None
        if glob == 1 and ours and (cur is None or cur <= 0.55):
            return True
        if glob == 1 and ours:  # attivita' presente ma il processo non tiene il timer (es. si e' chiuso con un errore)
            self.note = "attivita' presente ma il timer e' a %.2f ms: riavvia il PC o riapplica la voce" % cur
            return False
        if glob == 1 and cur is not None and cur <= 0.55:
            self.note = "attivo: timer a %.2f ms tenuto da un altro programma" % cur
            return True
        return False

    def apply(self):
        from . import paths
        cmd = self._cmd()
        prev, _ = T.reg_read("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel",
                             "GlobalTimerResolutionRequests")
        T.reg_write("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel",
                    "GlobalTimerResolutionRequests", DWORD, 1)
        code, out = run(["schtasks", "/Create", "/TN", TIMER_TASK, "/TR", paths.quote(cmd),
                         "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"])
        if code != 0:
            raise RuntimeError("non riesco a creare l'attivita' all'avvio: " + out[-200:])
        subprocess.Popen(cmd, creationflags=0x08000000 | 0x00000008)  # nessuna finestra, staccato
        return {"global_prev": prev}

    def revert(self, backup):
        run(["schtasks", "/Delete", "/TN", TIMER_TASK, "/F"])
        ps("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*timer_resolution.pyw*' -or "
           "$_.CommandLine -like '*LagDoctor.exe* --timer*' } | "
           "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
        if backup.get("global_prev") is None:
            T.reg_delete("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel",
                         "GlobalTimerResolutionRequests")
        else:
            T.reg_write("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel",
                        "GlobalTimerResolutionRequests", DWORD, backup["global_prev"])


def repair_timer():
    """Se il Timer Resolution e' attivo, riscrive l'avvio automatico con il percorso attuale del programma
    (dopo l'installazione o lo spostamento della cartella il vecchio percorso non esiste piu')."""
    if run(["schtasks", "/Query", "/TN", TIMER_TASK])[0] != 0:
        return False
    t = TIMER[0]
    cmd = t._cmd()
    from . import paths
    run(["schtasks", "/Create", "/TN", TIMER_TASK, "/TR", paths.quote(cmd), "/SC", "ONLOGON", "/RL", "HIGHEST", "/F"])
    return True


TIMER = [TimerResTweak("timer_res", "CPU ed energia",
                       "Timer Resolution 0,5 ms + GlobalTimerResolutionRequests (automatico, parte con Windows)",
                       "LagDoctor imposta il timer di sistema a 0,5 ms e lo mantiene con un piccolo processo "
                       "invisibile che parte a ogni accesso (come il famoso tool TimerResolution).", "media",
                       reboot=True, group="timer", recommend=lambda s: None,
                       source="valleyofdoom/TimerResolution; Blur Busters")]


# ============================================================================ IMPOSTAZIONI DI WINDOWS (app Impostazioni)

class _GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]


def _guid(text):
    import uuid
    u = uuid.UUID(text)
    g = _GUID(u.fields[0], u.fields[1], u.fields[2])
    for i, b in enumerate(u.bytes[8:]):
        g.d4[i] = b
    return g


class PowerOverlayTweak(Tweak):
    """Impostazioni > Sistema > Alimentazione > Modalita' risparmio energia = Prestazioni migliori.
    Esiste solo con il piano Bilanciato: con altri piani Windows nasconde l'opzione."""
    BEST = "ded574b5-45a0-4f42-8737-46345c09c238"
    BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
    note = None

    def _current(self):
        code, out = run(["powercfg", "/getactiveoverlayscheme"])
        m = re.search(r"[0-9a-f]{8}-[0-9a-f-]{27}", out.lower()) if code == 0 else None
        if m:
            return m.group(0)
        v, _ = T.reg_read("HKLM", T.POWER_KEY + "\\User\\PowerSchemes", "ActiveOverlayAcPowerScheme")
        return (v or "00000000-0000-0000-0000-000000000000").lower()  # assente = Bilanciato normale

    def status(self):
        if T._active_scheme() != self.BALANCED:
            self.note = "non disponibile: il piano energetico attivo non e' Bilanciato"
            return None
        self.note = None
        return self._current() == self.BEST

    def _set(self, guid):
        if run(["powercfg", "/overlaysetactive", guid])[0] == 0:
            return True
        try:
            return ctypes.windll.powrprof.PowerSetActiveOverlayScheme(_guid(guid)) == 0
        except Exception:
            return False

    def apply(self):
        if T._active_scheme() != self.BALANCED:
            raise RuntimeError("questa modalita' esiste solo con il piano energetico Bilanciato (ora ne usi un altro)")
        prev = self._current()
        if not self._set(self.BEST):
            raise RuntimeError("Windows non ha accettato la modalita' Prestazioni migliori")
        return {"prev": prev}

    def revert(self, backup):
        self._set(backup.get("prev") or "00000000-0000-0000-0000-000000000000")


WINSET = [
    PowerOverlayTweak("power_mode_best", "CPU ed energia", "Modalita' risparmio energia: Prestazioni migliori",
                      "Impostazioni > Sistema > Alimentazione: la CPU usa il profilo piu' reattivo del piano "
                      "Bilanciato.", "bassa"),
    RegTweak("start_web_off", "Interfaccia e input", "Ricerca nel menu Start senza risultati web (Bing)",
             "La ricerca del menu Start non interroga piu' Bing: piu' veloce e senza traffico in background.",
             "bassa", values=[("HKCU", r"Software\Policies\Microsoft\Windows\Explorer",
                               "DisableSearchBoxSuggestions", DWORD, 1)]),
    RegTweak("wu_active_hours", "Interfaccia e input", "Windows Update: ore attive 10:00-02:00",
             "Windows non riavvia il PC per gli aggiornamenti tra le 10 e le 2 di notte.", "comfort",
             values=[("HKLM", r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", "SmartActiveHoursState", DWORD, 0),
                     ("HKLM", r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", "ActiveHoursStart", DWORD, 10),
                     ("HKLM", r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", "ActiveHoursEnd", DWORD, 2)]),
    RegTweak("usb_notify_off", "Interfaccia e input", "Disattiva le notifiche USB",
             "Impostazioni > Bluetooth e dispositivi > USB: niente popup per problemi di connessione USB.",
             "comfort", values=[("HKCU", r"Software\Microsoft\Shell\USB", "NotifyOnUsbErrors", DWORD, 0)],
             recommend=lambda s: None),
    RegTweak("metered_drivers", "Interfaccia e input", "Non scaricare app dei dispositivi automaticamente",
             "Impostazioni > Bluetooth e dispositivi: Windows non installa da solo le app dei produttori (es. "
             "Razer, Logitech) quando colleghi un dispositivo.", "bassa",
             values=[("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Device Metadata",
                      "PreventDeviceMetadataFromNetwork", DWORD, 1)], source="WinUtil"),
    RegTweak("mouse_pointer_6", "Interfaccia e input", "Velocita' puntatore a 6/11 (1:1)",
             "Riporta la velocita' del puntatore di Windows al valore neutro (nessuna moltiplicazione del "
             "movimento del mouse).", "comfort",
             values=[("HKCU", r"Control Panel\Mouse", "MouseSensitivity", SZ, "10")], recommend=lambda s: None),
]


# ============================================================================ NON AFFIDABILI (miti attivabili)

MYTH = "Non affidabili (miti)"


def _myth(cls, tid, name, desc, risk=1, **kw):
    kw.setdefault("recommend", lambda s: False)
    return cls(tid, MYTH, name, desc, "sconsigliata", risk=risk, kind="myth", **kw)


MYTHS_TWEAKS = [
    _myth(CmdTweak, "myth_pagefile_off", "Disattiva il file di paging",
          "Togli del tutto la memoria virtuale su disco.", risk=2, reboot=True, group="pagefile",
          on="$c = Get-CimInstance Win32_ComputerSystem; Set-CimInstance -InputObject $c -Property "
             "@{AutomaticManagedPagefile = $false}; Get-CimInstance Win32_PageFileSetting | Remove-CimInstance",
          off="$c = Get-CimInstance Win32_ComputerSystem; Set-CimInstance -InputObject $c -Property "
              "@{AutomaticManagedPagefile = $true}",
          check="-not ((Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile -or "
                "@(Get-CimInstance Win32_PageFileSetting).Count -gt 0)"),
    _myth(CmdTweak, "myth_hpet_on", "Forza HPET (bcdedit useplatformclock)",
          "Obbliga Windows a usare il timer HPET della scheda madre.", risk=2, reboot=True, group="hpet",
          on="bcdedit /set '{current}' useplatformclock true", off="bcdedit /deletevalue '{current}' useplatformclock",
          check="[bool]((bcdedit /enum '{current}') -match 'useplatformclock\\s+(Yes|Si|Sì)')"),
    _myth(CmdTweak, "myth_autotuning_off", "Disattiva TCP Auto-Tuning", "Blocca l'adattamento della finestra TCP.",
          group="autotune", on="netsh int tcp set global autotuninglevel=disabled",
          off="netsh int tcp set global autotuninglevel=normal",
          check="(Get-NetTCPSetting -SettingName Internet).AutoTuningLevelLocal -eq 'Disabled'"),
    _myth(RegTweak, "myth_largecache", "LargeSystemCache = 1", "Cache di sistema in modalita' server.",
          group="largecache", values=[("HKLM", T.MEM_KEY, "LargeSystemCache", DWORD, 1)]),
    _myth(CmdTweak, "myth_trim_off", "Disattiva il TRIM degli SSD", "Windows smette di inviare il TRIM all'SSD.",
          group="trim", on="fsutil behavior set DisableDeleteNotify 1", off="fsutil behavior set DisableDeleteNotify 0",
          check="[bool]((fsutil behavior query DisableDeleteNotify) -match 'NTFS DisableDeleteNotify\\s*=\\s*1')"),
    _myth(CmdTweak, "myth_defrag_off", "Disattiva 'Ottimizza unita'' pianificato",
          "Ferma l'ottimizzazione settimanale dei dischi.",
          on="schtasks /Change /TN '\\Microsoft\\Windows\\Defrag\\ScheduledDefrag' /Disable",
          off="schtasks /Change /TN '\\Microsoft\\Windows\\Defrag\\ScheduledDefrag' /Enable",
          check="(Get-ScheduledTask -TaskPath '\\Microsoft\\Windows\\Defrag\\' -TaskName 'ScheduledDefrag').State "
                "-eq 'Disabled'"),
    _myth(RegTweak, "myth_qos", "'Libera il 20% di banda' (NonBestEffortLimit = 0)",
          "Criterio QoS famoso nelle guide di rete.", risk=0,
          values=[("HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Psched", "NonBestEffortLimit", DWORD, 0)]),
    _myth(RegTweak, "myth_irq8", "IRQ8Priority = 1", "Priorita' all'orologio di sistema (tweak di Windows XP).",
          risk=0, values=[("HKLM", r"SYSTEM\CurrentControlSet\Control\PriorityControl", "IRQ8Priority", DWORD, 1)]),
    _myth(RegTweak, "myth_conservative_swap", "ConservativeSwapfileUsage = 1",
          "Chiede a Windows di usare meno il file di paging (tweak di Windows XP).", risk=0,
          values=[("HKLM", T.MEM_KEY, "ConservativeSwapfileUsage", DWORD, 1)]),
    _myth(CmdTweak, "myth_dns", "DNS Cloudflare (1.1.1.1) 'per abbassare il ping'",
          "Imposta il DNS 1.1.1.1 sulle schede di rete attive.", risk=0,
          on="Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Set-DnsClientServerAddress "
             "-ServerAddresses 1.1.1.1,1.0.0.1",
          off="Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Set-DnsClientServerAddress -ResetServerAddresses",
          check="$a = Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Get-DnsClientServerAddress "
                "-AddressFamily IPv4; if (-not $a) { 'unknown' } else { [bool]($a.ServerAddresses -contains '1.1.1.1') }"),
]
for _t in T.CATALOG:  # i miti e le relative correzioni si escludono a vicenda
    if _t.id == "fix_pagefile":
        _t.group = "pagefile"
    elif _t.id == "fix_hpet":
        _t.group = "hpet"
    elif _t.id == "fix_autotuning":
        _t.group = "autotune"
    elif _t.id == "fix_largecache":
        _t.group = "largecache"
    elif _t.id == "fix_trim":
        _t.group = "trim"

# Miti che non si possono "attivare" in modo sensato: restano solo come spiegazione
NOT_TOGGLEABLE = [
    ("Programmi 'pulisci RAM' / svuota memoria standby", "Windows usa la RAM libera come cache: svuotarla fa "
     "ricaricare i dati dal disco e puo' CAUSARE stutter. Puo' aiutare solo con bug specifici di alcuni giochi "
     "che 'perdono' memoria, e in quel caso basta riavviare il gioco."),
    ("Disattivare decine di servizi a caso", "Rompe Windows Update, audio, Bluetooth, Xbox/Game Pass e anti-cheat, "
     "con guadagni non misurabili. LagDoctor propone solo servizi specifici con i loro effetti spiegati."),
    ("Forzare la modalita' MSI per la scheda video", "I driver NVIDIA e AMD moderni la usano gia'. Cambiarla sul "
     "dispositivo sbagliato puo' impedire l'avvio di Windows."),
]


def register():
    T.CATALOG.extend(DEBLOAT + TIMER + WINSET + MYTHS_TWEAKS)
    for cat in (DEB, MYTH):
        if cat not in T.CAT_ORDER:
            T.CAT_ORDER.append(cat)
    # il vecchio GlobalTimerResolutionRequests da solo e' alternativo al Timer Resolution completo
    for t in T.CATALOG:
        if t.id == "timer_global":
            t.group = "timer"
    T.CATALOG.sort(key=lambda t: T.CAT_ORDER.index(t.cat))
    T.BY_ID.clear()
    T.BY_ID.update({t.id: t for t in T.CATALOG})
