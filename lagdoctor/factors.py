"""Collega le cause di stutter trovate nella registrazione alle impostazioni del PC.

Per ogni causa:
  - "peggiora": impostazioni attive ora che sono note per causare proprio quel problema
  - "aiuta":    ottimizzazioni non ancora attive che possono ridurlo
Le associazioni seguono le fonti usate nel catalogo (Microsoft, NVIDIA, AMD, Blur Busters, Tom's Hardware, test
della community) e le spiegazioni di ogni voce.
"""
from . import tweak_docs
from . import tweaks as T

# kind: "fix" = dannosa se status False | "myth" = dannosa se status True | "harm" = harm_if_off, dannosa se False
#       "help" = puo' aiutare se status False
# kind: "fix"    = correzione: il problema c'e' se status False
#       "myth"   = mito: il problema c'e' se e' attivo (status True)
#       "harm"   = impostazione che fa danno se NON attiva (harm_if_off)
#       "on_bad" = ottimizzazione che, se attiva (anche applicata da LagDoctor), PEGGIORA proprio questa causa
#       "help"   = ottimizzazione non attiva che puo' ridurre questa causa
_BG = [("game_dvr", "harm"), ("game_mode", "harm"), ("defender_excl", "help"), ("bg_apps", "help"),
       ("wsearch", "help"), ("sysmain", "help"), ("diagtrack", "help"), ("telemetry_policy", "help"),
       ("widgets_off", "help"), ("edge_bg_off", "help"), ("app_teams", "help"), ("app_onedrive", "help"),
       ("power_throttling", "help"), ("notifications_off", "help"), ("copilot_off", "help")]
_CPU = [("fix_powersaver", "fix"), ("game_mode", "harm"), ("power_mode_best", "help"), ("virt_off", "help"),
        ("timer_res", "help"), ("bg_apps", "help"), ("app_teams", "help"),
        ("edge_bg_off", "help"), ("widgets_off", "help"), ("plan_high", "help")]
CAUSES = {
    "background": ("Programmi e attivita' in background", _BG),
    "disk": ("Stutter da lettura dal disco (streaming dei dati del gioco)", [
        ("fix_trim", "fix"), ("myth_trim_off", "myth"), ("myth_defrag_off", "myth"), ("fix_pagefile", "fix"),
        ("myth_pagefile_off", "myth"), ("defender_excl", "help"), ("ntfs_lastaccess", "help"),
        ("app_onedrive", "help"), ("storage_sense_off", "help"), ("pcie_aspm", "help"), ("sysmain", "help")]),
    "ram": ("RAM quasi piena", [
        ("fix_largecache", "fix"), ("myth_largecache", "myth"), ("fix_pagefile", "fix"), ("myth_pagefile_off", "myth"),
        ("app_teams", "help"), ("edge_bg_off", "help"), ("widgets_off", "help"), ("app_onedrive", "help")]),
    "paging": ("Memoria spostata sul disco (paging)", [
        ("fix_pagefile", "fix"), ("myth_pagefile_off", "myth"), ("fix_largecache", "fix"), ("myth_largecache", "myth"),
        ("mem_compress", "on_bad"), ("fix_trim", "fix"), ("myth_trim_off", "myth"), ("app_teams", "help"),
        ("edge_bg_off", "help"), ("widgets_off", "help"), ("app_onedrive", "help"), ("defender_excl", "help")]),
    "vram": ("VRAM piena", [
        ("edge_bg_off", "help"), ("widgets_off", "help"), ("app_teams", "help"), ("game_dvr", "harm")]),
    "shader": ("Compilazione degli shader / motore del gioco", [
        ("nvfix_shadercache", "fix"), ("nv_shadercache_unlimited", "help"), ("defender_excl", "help"),
        ("fix_trim", "fix"), ("myth_trim_off", "myth")]),
    "main_thread": ("Thread principale della CPU al limite", _CPU),
    "cpu_bound": ("Gioco limitato dalla CPU", _CPU),
    "cpu_throttle": ("CPU che rallenta (energia o calore)", [
        ("fix_powersaver", "fix"), ("power_mode_best", "help"), ("plan_high", "help"), ("idle_off", "on_bad"),
        ("min_cpu_100", "on_bad"), ("plan_ultimate", "on_bad")]),
    "throttle": ("GPU che rallenta (calore o energia)", [
        ("fix_powersaver", "fix"), ("nvfix_minpower", "fix"), ("nv_power_max", "on_bad")]),
    "gpu_bound": ("GPU al limite (frame pacing e input lag)", [
        ("nvfix_prerender", "fix"), ("nv_lowlat_on", "help"), ("nv_fps_cap", "help"), ("amd_antilag_on", "help"),
        ("amd_fps_cap", "help"), ("hags", "help"), ("fix_hags_off_40", "fix"), ("amd_afmf_off", "help")]),
    "fps_over_refresh": ("FPS sopra la frequenza del monitor", [
        ("nv_fps_cap", "help"), ("amd_fps_cap", "help"), ("vrr_opt", "help"), ("nvfix_vrr_blocked", "fix")]),
    "dpc": ("Driver che bloccano il sistema (latenza DPC/ISR)", [
        ("myth_hpet_on", "myth"), ("fix_hpet", "fix"), ("nic_intmod", "on_bad"), ("idle_off", "on_bad"),
        ("usb_suspend", "help"), ("pcie_aspm", "help"), ("nic_power", "help"), ("nic_eee", "help"),
        ("virt_off", "help"), ("metered_drivers", "help")]),
    "present": ("Presentazione dei frame (schermo intero / borderless / compositore)", [
        ("game_dvr", "harm"), ("windowed_opt", "help"), ("vrr_opt", "help"), ("mpo_off", "help"),
        ("nv_gsync_windowed", "help"), ("nvfix_vrr_blocked", "fix"), ("amdfix_esync", "fix")]),
    "vsync": ("V-Sync", [
        ("nvfix_vsync_half", "fix"), ("amdfix_vsync_always", "fix"), ("amdfix_esync", "fix"),
        ("nvfix_vrr_blocked", "fix"), ("nv_fps_cap", "help"), ("amd_fps_cap", "help"), ("vrr_opt", "help"),
        ("nv_gsync_windowed", "help")]),
    "pacing": ("Stutter e frame pacing in generale", [
        ("fix_hpet", "fix"), ("myth_hpet_on", "myth"), ("fix_powersaver", "fix"), ("nvfix_vsync_half", "fix"),
        ("nvfix_fpscap_low", "fix"), ("nvfix_vrr_blocked", "fix"), ("amdfix_chill", "fix"), ("amdfix_esync", "fix"),
        ("amdfix_frtc_low", "fix"), ("amdfix_vsync_always", "fix"), ("game_dvr", "harm"), ("virt_off", "help"),
        ("timer_res", "help"), ("windowed_opt", "help"), ("vrr_opt", "help"), ("pcie_aspm", "help"),
        ("usb_suspend", "help"), ("mpo_off", "help")]),
    "input": ("Input lag e mira", [("mouse_accel", "harm"), ("nv_lowlat_on", "help"), ("amd_antilag_on", "help")]),
}

def causes_from(problems, stutter_per_min):
    found = []
    for p in problems:
        c = p.get("cause")
        if c in CAUSES and c not in found:
            found.append(c)
            continue
        for prefix, cause in TITLE_TO_CAUSE:
            if p["titolo"].startswith(prefix) and cause and cause not in found:
                found.append(cause)
    if stutter_per_min >= 2 and "pacing" not in found:
        found.append("pacing")
    if "pacing" in found:  # la causa generica va per ultima
        found.remove("pacing")
        found.append("pacing")
    if "input" not in found:
        found.append("input")
    return found


def _harmful(t, kind, st, applied=False):
    if kind == "on_bad":
        return st is True or applied
    if kind == "myth":
        return st is True
    if kind in ("fix", "harm"):
        return st is False
    return False


def analyze(problems, stutter_per_min, statuses, applied, vendor, sysinfo, capped=False):
    """Restituisce una lista di sezioni: {causa, titolo, peggiora:[...], aiuta:[...]}."""
    allowed = {t.id for t in T.for_vendor(vendor)}
    out = []
    shown = set()  # ogni impostazione compare una volta sola, nella causa piu' specifica (le cause sono in ordine)
    for cause in causes_from(problems, stutter_per_min):
        title, items = CAUSES[cause]
        worse, help_ = [], []
        for tid, kind in sorted(items, key=lambda x: x[1] != "myth"):
            t = T.BY_ID.get(tid)
            if not t or tid not in allowed or (tid in applied and kind != "on_bad"):
                continue
            if t.kind == "fix" and t.recommended(sysinfo) is False:
                continue
            if tid in shown or (t.group and ("g:" + t.group) in shown):
                continue
            st = statuses.get(tid)
            d = tweak_docs.get(tid) or {}
            if _harmful(t, kind, st, tid in applied):
                if t.group and any(w.get("group") == t.group for w in worse):
                    continue  # stesso problema gia' elencato (mito + sua correzione)
                label = ("ATTIVO: " + t.name) if kind in ("myth", "on_bad") else t.desc
                worse.append({"id": tid, "name": t.name, "label": label, "group": t.group,
                              "why": d.get("problemi") if kind in ("myth", "on_bad") else (d.get("perche") or t.desc),
                              "myth": kind == "myth", "kind": kind, "undo": kind == "on_bad" and tid in applied})
            elif kind == "help" and st is False and t.efficacy in ("alta", "media") and \
                    not (capped and tid in ("nv_fps_cap", "amd_fps_cap")):  # il limite FPS c'e' gia' nel gioco
                help_.append({"id": tid, "name": t.name, "why": d.get("perche") or t.desc, "risk": T.RISK[t.risk]})
        shown.update(x["id"] for x in worse + help_)
        shown.update("g:" + T.BY_ID[x["id"]].group for x in worse + help_ if T.BY_ID[x["id"]].group)
        if worse or help_:
            out.append({"causa": cause, "titolo": title, "peggiora": worse, "aiuta": help_})
    return out


def harmful_now(statuses, applied, vendor, sysinfo):
    """Tutte le impostazioni dannose attive ora (indipendentemente dalla registrazione)."""
    res, groups = [], set()
    for t in sorted(T.for_vendor(vendor), key=lambda x: x.kind != "myth"):
        if t.id in applied or (t.group and t.group in groups):
            continue
        st = statuses.get(t.id)
        if t.kind == "myth" and st is True:
            res.append(t)
        elif t.kind == "fix" and st is False and t.recommended(sysinfo) is not False:
            res.append(t)
        elif t.harm_if_off and st is False:
            res.append(t)
        else:
            continue
        if t.group:
            groups.add(t.group)
    return res
