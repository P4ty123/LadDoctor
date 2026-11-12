"""Processi in background che partono con Windows: servizi e attivita' pianificate (quelli che Gestione attivita' >
Avvio non mostra).

Fermarli senza che si riaprano: non si chiude il processo a ripetizione, si toglie il suo avvio alla fonte.
  - servizio: tipo di avvio -> Disattivato (prima viene salvato quello di prima), poi fermato una volta
  - attivita' pianificata: disattivata, poi fermata una volta (e chiuso il suo programma se era aperto)
Riattivando si rimette esattamente com'era. Le modifiche sono salvate in avvio_processi.json.
"""
import json
import os
import subprocess

from . import paths

FILE = paths.data("avvio_processi.json")
CREATE_NO_WINDOW = 0x08000000

# ------------------------------------------------------------------ riconoscimento e consigli
GROUPS = [
    ("upd", "Aggiornamenti automatici"),
    ("vendor", "Programmi del produttore"),
    ("game", "Giochi e launcher"),
    ("driver", "Driver e hardware"),
    ("other", "Altri programmi"),
    ("win", "Componenti di Windows"),
]
_UPD = ("update", "updater", "upd.exe", "autoupdate", "maintenanceservice", "armsvc", "adobearm", "gupdate",
        "edgeupdate", "googleupdate", "brave update", "zoom update", "softwareupdate", "agsservice")
_VENDOR = ("asus", "armoury", "aura", "msi", "mystic", "dragon center", "razer", "corsair", "icue", "logitech", "lghub",
           "steelseries", "gigabyte", "aorus", "rgb fusion", "dell", "supportassist", "hp ", "hpsupport", "hpanalytics",
           "touchpoint", "lenovo", "vantage", "nzxt", "cam ", "cooler master", "masterplus", "signalrgb", "openrgb",
           "afterburner", "rivatuner", "rtss", "acer", "predator", "alienware", "wallpaper engine", "hyperx", "ngenuity")
_GAME = ("steam", "epic", "eos", "ea ", "eadesktop", "eabackground", "origin", "ubisoft", "uplay", "battle.net", "blizzard",
         "riot", "vanguard", "vgc", "gog", "galaxy", "rockstar", "easyanticheat", "battleye", "beservice", "faceit",
         "javelin", "xbox", "gamingservices", "minecraft", "playnite")
_DRIVER = ("nvidia", "nvdisplay", "nvcontainer", "amd", "radeon", "intel", "igfx", "realtek", "rtk", "nahimic", "dolby",
           "dts", "waves", "maxx", "synaptics", "elan", "wacom", "bluetooth", "thunderbolt", "chipset", "audio")
# da non toccare: senza questi si perdono video, audio, periferiche, sicurezza o la possibilita' di giocare online
_KEEP = {
    "driver": (("nvdisplay.container", "nvdisplay", "amd external events", "amdfendr", "amd crash defender",
                "rtkaudiouniversalservice", "realtek audio", "intel(r) graphics", "igfxcui", "intelaudioservice",
                "intel(r) content protection", "wacom", "synaptics", "elan service", "thunderbolt", "dolby dax"),
               "driver: lascialo attivo"),
    "security": (("avast", "avg ", "kaspersky", "eset", "ekrn", "bitdefender", "malwarebytes", "mbamservice", "norton",
                  "mcafee", "sophos", "trend micro", "f-secure", "panda", "webroot", "windefend", "security health",
                  "securityhealth"),
                 "sicurezza: lascialo attivo"),
    "anticheat": (("vgc", "vanguard", "faceit", "javelin", "eaanticheat", "easyanticheat", "battleye", "beservice",
                   "nprotect", "xigncode", "mhyprot"),
                  "anti-cheat: serve per giocare online"),
}
_HINTS = [
    (("afterburner",), "curve ventole / overclock"),
    (("armoury", "armourycrate", "lightingservice", "icue", "nzxt", "signalrgb", "razer synapse", "msi.centralserver",
      "dragon center", "hwinfo", "aida64", "wallpaper"), "!noto per causare scatti"),
]


def _match(text, words):
    t = " " + text.lower() + " "
    return any(w in t for w in words)


def classify(name, display, exe, company, windows):
    """(gruppo, etichette, motivo per cui l'interruttore e' bloccato o None)."""
    text = " ".join([name or "", display or "", os.path.basename(exe or ""), company or ""])
    badges, lock = [], None
    for _k, (words, why) in _KEEP.items():
        if _match(text, words):
            lock = why
            break
    if windows:
        return "win", badges, lock or "componente di Windows"
    if _match(text, _UPD):
        group = "upd"
        if not lock:
            badges.append("si puo' disattivare")
    elif _match(text, _VENDOR):
        group = "vendor"
    elif _match(text, _GAME):
        group = "game"
    elif lock and lock.startswith("driver") or _match(text, _DRIVER):
        group = "driver"
    else:
        group = "other"
    for words, label in _HINTS:
        if _match(text, words):
            badges.append(label)
    return group, badges, lock


# ------------------------------------------------------------------ lettura
PS_LIST = r"""
$ErrorActionPreference = 'SilentlyContinue'
$win = $env:WINDIR.ToLower()
function Exe($cmd) {
  if (-not $cmd) { return '' }
  $c = [Environment]::ExpandEnvironmentVariables($cmd.Trim())
  if ($c.StartsWith('"')) { return $c.Split('"')[1] }
  $i = $c.ToLower().IndexOf('.exe'); if ($i -gt 0) { return $c.Substring(0, $i + 4) }
  return $c.Split(' ')[0]
}
$comp = @{}
function Company($exe) {
  if (-not $exe) { return '' }
  $k = $exe.ToLower(); if ($comp.ContainsKey($k)) { return $comp[$k] }
  $v = ''; try { $v = (Get-Item -LiteralPath $exe).VersionInfo.CompanyName } catch {}
  if (-not $v) { $v = '' }; $comp[$k] = $v.Trim(); return $comp[$k]
}
$out = @()
foreach ($s in Get-CimInstance Win32_Service) {
  $exe = Exe $s.PathName
  $reg = Get-ItemProperty ('HKLM:\SYSTEM\CurrentControlSet\Services\' + $s.Name)
  $out += [pscustomobject]@{ kind='svc'; id=$s.Name; name=$s.DisplayName; exe=$exe; company=(Company $exe);
    start=[int]$reg.Start; delayed=[int]$reg.DelayedAutostart; state=$s.State; pid=[int]$s.ProcessId;
    desc=$s.Description; inwin=($exe.ToLower().StartsWith($win)); mstask=$false }
}
foreach ($t in Get-ScheduledTask) {
  $a = $t.Actions | Where-Object { $_.Execute } | Select-Object -First 1
  $exe = Exe $a.Execute
  $tr = @($t.Triggers | ForEach-Object {
    $n = $_.CimClass.CimClassName -replace 'MSFT_Task', '' -replace 'Trigger', ''
    if ($_.Repetition -and $_.Repetition.Interval) { $n + '|' + $_.Repetition.Interval } else { $n } })
  $out += [pscustomobject]@{ kind='task'; id=($t.TaskPath + $t.TaskName); name=$t.TaskName; exe=$exe;
    company=(Company $exe); state=[string]$t.State; triggers=$tr; desc=$t.Description;
    inwin=($exe.ToLower().StartsWith($win)); mstask=($t.TaskPath -like '\Microsoft\Windows\*') }
}
$out | ConvertTo-Json -Depth 4 -Compress
"""


def _ps(script, timeout=180):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True,
                           text=True, timeout=timeout, creationflags=CREATE_NO_WINDOW)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except Exception as e:
        return 1, "", str(e)


def _load():
    try:
        with open(FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(d):
    os.makedirs(paths.DATA_DIR, exist_ok=True)
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)


START_TXT = {0: "avvio (driver)", 1: "sistema", 2: "automatico", 3: "manuale", 4: "disattivato"}


def _trigger_text(trs):
    names = {"Logon": "all'accesso", "Boot": "all'accensione", "Time": "a orario", "Daily": "ogni giorno",
             "Weekly": "ogni settimana", "Idle": "quando il PC e' inattivo", "Event": "a un evento di Windows",
             "SessionStateChange": "al cambio di sessione", "Registration": "alla creazione"}
    out = []
    for t in trs or []:
        n, _, rep = str(t).partition("|")
        s = names.get(n, n.lower() or "a richiesta")
        if rep:
            s += " + ogni " + _iso_dur(rep)
        out.append(s)
    return ", ".join(dict.fromkeys(out)) or "a richiesta"


def _iso_dur(s):
    import re
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?", s or "")
    if not m:
        return s
    d, h, mi = (int(x) if x else 0 for x in m.groups())
    if d:
        return "%d giorni" % d if d > 1 else "giorno"
    if h:
        return "%d ore" % h if h > 1 else "ora"
    return "%d minuti" % mi if mi else s


def _running():
    """exe (minuscolo) -> MB usati da tutti i suoi processi; pid -> MB."""
    import psutil
    by_exe, by_pid = {}, {}
    for p in psutil.process_iter(["pid", "exe", "memory_info"]):
        try:
            mb = (p.info["memory_info"].rss if p.info["memory_info"] else 0) / 2**20
        except Exception:
            mb = 0
        by_pid[p.info["pid"]] = mb
        if p.info.get("exe"):
            k = p.info["exe"].lower()
            by_exe[k] = by_exe.get(k, 0) + mb
    return by_exe, by_pid


def list_items(include_windows=False):
    code, out, err = _ps(PS_LIST)
    try:
        raw = json.loads(out) if out else []
    except ValueError:
        raw = []
    if isinstance(raw, dict):
        raw = [raw]
    mine = _load()
    by_exe, by_pid = _running()
    items = []
    for r in raw:
        comp = (r.get("company") or "").lower()
        # componente di Windows: attivita' di \Microsoft\Windows\ o programma di Microsoft dentro C:\Windows
        # (i servizi dei driver NVIDIA/AMD/Realtek stanno in C:\Windows ma non sono di Microsoft: li mostro)
        windows = bool(r.get("mstask")) or (bool(r.get("inwin", r.get("windows"))) and ("microsoft" in comp or not comp))
        exe = r.get("exe") or ""
        key = "%s:%s" % (r["kind"], r["id"])
        ours = key in mine
        if r["kind"] == "svc":
            start = r.get("start")
            if start not in (2, 3, 4) and not ours:
                continue  # driver di sistema e simili: non sono programmi
            if start == 3 and r.get("state") != "Running" and not ours and windows:
                continue
            on = start in (2, 3)
            origin = "Servizio (%s%s)" % ("automatico" if start == 2 else START_TXT.get(start, "?"),
                                          ", ritardato" if start == 2 and r.get("delayed") else "")
            if ours and start == 4:
                origin = "Servizio (disattivato da LagDoctor)"
            run_mb = by_pid.get(r.get("pid") or -1) if r.get("state") == "Running" and r.get("pid") else None
            manual = start == 3
        else:
            st = r.get("state") or ""
            on = st != "Disabled"
            trs = r.get("triggers") or []
            origin = "Attivita' " + _trigger_text(trs)
            if ours and not on:
                origin = "Attivita' (disattivata da LagDoctor)"
            run_mb = by_exe.get(exe.lower()) if exe else None
            manual = False
        if windows and not include_windows and not ours:
            continue
        group, badges, lock = classify(r["id"], r.get("name"), exe, r.get("company"), windows)
        if manual and on and not lock:
            badges.append("parte solo quando serve")
        items.append({"kind": r["kind"], "id": r["id"], "name": r.get("name") or r["id"], "exe": os.path.basename(exe),
                      "path": exe, "company": r.get("company") or "", "desc": (r.get("desc") or "")[:300],
                      "origin": origin, "on": on, "running": run_mb is not None and run_mb > 0,
                      "mb": round(run_mb) if run_mb else 0, "group": group, "badges": badges, "lock": lock,
                      "ours": ours})
    order = {g: i for i, (g, _n) in enumerate(GROUPS)}
    items.sort(key=lambda x: (order.get(x["group"], 9), not x["running"], x["name"].lower()))
    return {"items": items, "groups": [{"id": g, "name": n} for g, n in GROUPS], "error": None if raw else (err or "lettura non riuscita")[-300:]}


# ------------------------------------------------------------------ modifica
def _svc_set(name, start, delayed=0):
    mode = {2: "delayed-auto" if delayed else "auto", 3: "demand", 4: "disabled"}[start]
    r = subprocess.run(["sc", "config", name, "start=", mode], capture_output=True, text=True, timeout=30,
                       creationflags=CREATE_NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError("Windows non permette di cambiarlo (%s)" % (r.stdout + r.stderr).strip()[-160:])


def set_enabled(kind, ident, enabled):
    """Spegne o riaccende l'avvio di un servizio o di un'attivita'. Restituisce un messaggio."""
    mine = _load()
    key = "%s:%s" % (kind, ident)
    q = ident.replace("'", "''")
    if kind == "svc":
        if not enabled:
            code, out, _e = _ps("$r = Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\%s'; "
                                "'' + [int]$r.Start + '|' + [int]$r.DelayedAutostart" % q, timeout=30)
            try:
                start, delayed = (int(x) for x in out.strip().split("|"))
            except ValueError:
                raise RuntimeError("servizio non trovato")
            if key not in mine:
                mine[key] = {"start": start, "delayed": delayed}
                _save(mine)
            _svc_set(ident, 4)
            _ps("Stop-Service -Name '%s' -Force -ErrorAction SilentlyContinue" % q, timeout=60)
            return "non partira' piu' con Windows (fermato)"
        prev = mine.get(key) or {"start": 2, "delayed": 0}
        _svc_set(ident, prev.get("start", 2) if prev.get("start", 2) in (2, 3) else 2, prev.get("delayed", 0))
        if prev.get("start", 2) == 2:
            _ps("Start-Service -Name '%s' -ErrorAction SilentlyContinue" % q, timeout=60)
        mine.pop(key, None)
        _save(mine)
        return "riattivato come prima"
    # attivita' pianificata
    i = ident.rfind("\\")
    tp, tn = ident[:i + 1].replace("'", "''"), ident[i + 1:].replace("'", "''")
    if not enabled:
        code, out, err = _ps("$t = Get-ScheduledTask -TaskPath '%s' -TaskName '%s' -ErrorAction Stop; "
                             "$a = ($t.Actions | Where-Object { $_.Execute } | Select-Object -First 1).Execute; "
                             "Stop-ScheduledTask -TaskPath '%s' -TaskName '%s' -ErrorAction SilentlyContinue; "
                             "Disable-ScheduledTask -TaskPath '%s' -TaskName '%s' -ErrorAction Stop | Out-Null; "
                             "'OK|' + [Environment]::ExpandEnvironmentVariables($a)" % (tp, tn, tp, tn, tp, tn), 60)
        if not out.startswith("OK|"):
            raise RuntimeError("Windows non permette di disattivarla (%s)" % (err or out)[-160:])
        mine[key] = {"enabled": True}
        _save(mine)
        exe = out[3:].strip().strip('"')
        closed = _close_exe(exe)
        return "non partira' piu' con Windows" + (" (chiuso %s)" % os.path.basename(exe) if closed else "")
    code, out, err = _ps("Enable-ScheduledTask -TaskPath '%s' -TaskName '%s' -ErrorAction Stop | Out-Null; 'OK'"
                         % (tp, tn), 60)
    if "OK" not in out:
        raise RuntimeError("Windows non permette di riattivarla (%s)" % (err or out)[-160:])
    mine.pop(key, None)
    _save(mine)
    return "riattivata come prima"


def _close_exe(exe):
    if not exe or not exe.lower().endswith(".exe"):
        return False
    import psutil
    n = 0
    for p in psutil.process_iter(["exe"]):
        if (p.info.get("exe") or "").lower() == exe.lower():
            try:
                p.kill()
                n += 1
            except psutil.Error:
                pass
    return n > 0


def restore_all():
    """Per 'Ripristina tutto': rimette com'erano tutti i servizi e le attivita' spenti da LagDoctor."""
    msgs = []
    for key in list(_load()):
        kind, _, ident = key.partition(":")
        try:
            set_enabled(kind, ident, True)
            msgs.append("Riattivato all'avvio: %s" % ident)
        except Exception as e:
            msgs.append("%s: ERRORE %s" % (ident, e))
    return msgs
