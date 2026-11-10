"""Voci del catalogo per il Pannello di controllo NVIDIA e AMD Software Adrenalin.

Compaiono solo se nel PC c'e' una scheda di quella marca. Ogni modifica salva il valore precedente.
"""
from . import gpu_driver as GD
from . import tweaks as T


def _refresh():
    return T.CONTEXT.get("refresh_hz") or 0


def _raw(vendor):
    r = GD.read(vendor, _refresh() or None)
    return r.get("raw") if r.get("ok") else None


# ------------------------------------------------------------------ NVIDIA

class NvTweak(T.Tweak):
    """value: numero da impostare, "default" = torna al predefinito del driver, oppure funzione() -> numero."""

    def __init__(self, *a, key, value, ok=None, **kw):
        super().__init__(*a, **kw)
        self.vendor, self.key, self.value, self.ok = "nvidia", key, value, ok

    def _val(self):
        return self.value() if callable(self.value) else self.value

    def status(self):
        raw = _raw("nvidia")
        if raw is None:
            return None
        if self.ok:
            return bool(self.ok(raw))
        cur = raw.get(self.key, [None, None])[0]
        return cur == self._val()

    def apply(self):
        drs = GD.NvDrs()
        if not drs.ok:
            raise RuntimeError(drs.error)
        try:
            sid = GD.NV[self.key]
            prev, loc = drs.get(sid)
            backup = {"prev": prev if (prev is not None and loc != 3) else None}
            v = self._val()
            if v == "default":
                drs.reset(sid)
            elif v is None:
                raise RuntimeError("frequenza del monitor sconosciuta: impossibile calcolare il valore")
            else:
                drs.set(sid, v)
        finally:
            drs.close()
            GD.invalidate()
        return backup

    def revert(self, backup):
        drs = GD.NvDrs()
        if not drs.ok:
            raise RuntimeError(drs.error)
        try:
            sid = GD.NV[self.key]
            if backup.get("prev") is None:
                drs.reset(sid)
            else:
                drs.set(sid, backup["prev"])
        finally:
            drs.close()
            GD.invalidate()


def _nv(raw, k, d):
    v = raw.get(k, [None, None])[0]
    return d if v is None else v


def NVF(tid, name, desc, key, value, ok, eff="alta", **kw):
    return NvTweak(tid, "Driver NVIDIA", name, desc, eff, kind="fix", key=key, value=value, ok=ok, **kw)


def NVT(tid, name, desc, key, value, eff, **kw):
    return NvTweak(tid, "Driver NVIDIA", name, desc, eff, key=key, value=value, **kw)


NVIDIA = [
    NVF("nvfix_vsync_half", "Togli il V-Sync a mezza frequenza", "Il Pannello forza il V-Sync a 1/2, 1/3 o 1/4 della "
        "frequenza del monitor.", "VSYNCMODE", "default", lambda r: _nv(r, "VSYNCMODE", 0) not in GD.VSYNC_HALF),
    NVF("nvfix_fpscap_low", "Togli il limite FPS globale troppo basso", "Il Pannello limita tutti i giochi a molto "
        "meno della frequenza del monitor.", "FRL_FPS", "default",
        lambda r: not (_nv(r, "FRL_FPS", 0) and _refresh() and _nv(r, "FRL_FPS", 0) < _refresh() * 0.8)),
    NVF("nvfix_minpower", "Gestione energia NVIDIA: togli 'consumo minimo'", "La GPU e' tenuta a frequenze basse.",
        "PREFERRED_PSTATE", "default", lambda r: _nv(r, "PREFERRED_PSTATE", 5) != 4),
    NVF("nvfix_shadercache", "Riattiva la cache shader NVIDIA", "La cache shader del driver e' disattivata.",
        "SHADERCACHE", 1, lambda r: _nv(r, "SHADERCACHE", 1) != 0),
    NVF("nvfix_vrr_blocked", "Sblocca G-SYNC nel profilo globale", "G-SYNC e' bloccato per tutte le app.",
        "VRR_APP_OVERRIDE", "default", lambda r: _nv(r, "VRR_APP_OVERRIDE", 0) not in (1, 2, 4), eff="media"),
    NVF("nvfix_fxaa", "Togli l'FXAA forzato", "Il driver forza l'FXAA su tutti i giochi.", "FXAA_ENABLE", "default",
        lambda r: not _nv(r, "FXAA_ENABLE", 0), eff="media"),
    NVF("nvfix_thread", "Riattiva 'Ottimizzazione thread'", "Ottimizzazione thread e' disattivata.",
        "OGL_THREAD_CONTROL", "default", lambda r: _nv(r, "OGL_THREAD_CONTROL", 0) != 2, eff="media"),
    NVF("nvfix_prerender", "Riduci i frame pre-renderizzati", "Il driver prepara troppi frame in anticipo (input lag).",
        "PRERENDERLIMIT", 1, lambda r: not (_nv(r, "PRERENDERLIMIT", 0) > 3 and r.get("LOW_LATENCY_CPL", [None])[0] is None)),

    NVT("nv_lowlat_on", "Modalita' bassa latenza: Attivata", "Il driver prepara al massimo 1 frame in anticipo.",
        "PRERENDERLIMIT", 1, "media",
        source="NVIDIA System Latency Optimization Guide",
        ok=lambda r: _nv(r, "PRERENDERLIMIT", 0) == 1 or r.get("LOW_LATENCY_CPL", [None])[0] in (1, 2)),
    NVT("nv_shadercache_unlimited", "Cache shader: Illimitata", "Nessun limite alla cache degli shader compilati.",
        "SHADERCACHE_SIZE", 0xFFFFFFFF, "media", source="Guide NVIDIA Control Panel (PC Invasion, Prima Games)"),
    NVT("nv_refresh_highest", "Frequenza preferita: la piu' alta disponibile",
        "I giochi a schermo intero usano sempre la frequenza massima del monitor.", "REFRESH_RATE_OVERRIDE", 1, "media"),
    NVT("nv_power_max", "Gestione energia: Prediligi prestazioni massime (globale)",
        "La GPU resta sempre alle frequenze alte.", "PREFERRED_PSTATE", 1, "bassa", recommend=lambda s: None),
    NVT("nv_gsync_windowed", "G-SYNC anche in finestra e borderless", "G-SYNC attivo anche nei giochi in finestra.",
        "VRR_MODE", 2, "media", risk=1, recommend=lambda s: None),
    NVT("nv_vsync_on", "V-Sync: Attivato (da usare con G-SYNC)", "Il V-Sync del Pannello resta attivo: con G-SYNC "
        "elimina il tearing residuo.", "VSYNCMODE", 0x47814940, "media", recommend=lambda s: None,
        source="Blur Busters G-SYNC 101"),
    NVT("nv_fps_cap", "Limite FPS globale 3 sotto la frequenza del monitor", "Frequenza fotogrammi massima = Hz - 3.",
        "FRL_FPS", lambda: max(30, _refresh() - 3) if _refresh() else None, "media", recommend=lambda s: None,
        source="Blur Busters G-SYNC 101"),
    NVT("nv_texture_perf", "Filtro texture - Qualita': Prestazioni elevate",
        "Il driver usa ottimizzazioni piu' aggressive del filtro delle texture.", "QUALITY_ENHANCEMENTS", 0x14, "bassa"),
]


# ------------------------------------------------------------------ AMD

class AmdTweak(T.Tweak):
    def __init__(self, *a, key, action, value, ok, **kw):
        super().__init__(*a, **kw)
        self.vendor, self.key, self.action, self.value, self.ok = "amd", key, action, value, ok

    def status(self):
        raw = _raw("amd")
        if raw is None:
            return None
        if raw.get(self.key) is None:
            return None  # non supportato da questa scheda
        return bool(self.ok(raw))

    def _val(self):
        return self.value() if callable(self.value) else self.value

    def apply(self):
        raw = _raw("amd") or {}
        cur = raw.get(self.key) or {}
        backup = {"enabled": cur.get("enabled"), "mode": cur.get("mode"), "fps": cur.get("fps")}
        if self._val() is None:
            raise RuntimeError("frequenza del monitor sconosciuta: impossibile calcolare il valore")
        if self.action == "frtc_cap":
            GD.amd_set(self.key, "frtc_fps", self._val())
            GD.amd_set(self.key, "enabled", True)
        else:
            GD.amd_set(self.key, self.action, self._val())
        GD.invalidate()
        return backup

    def revert(self, backup):
        if self.action == "vsync_mode" and backup.get("mode") is not None:
            GD.amd_set(self.key, "vsync_mode", backup["mode"])
        else:
            if self.action == "frtc_cap" and backup.get("fps"):
                GD.amd_set(self.key, "frtc_fps", backup["fps"])
            if backup.get("enabled") is not None:
                GD.amd_set(self.key, "enabled", backup["enabled"])
        GD.invalidate()


def _en(r, k):
    return bool((r.get(k) or {}).get("enabled"))


def AMF(tid, name, desc, key, action, value, ok, eff="alta", **kw):
    return AmdTweak(tid, "Driver AMD", name, desc, eff, kind="fix", key=key, action=action, value=value, ok=ok, **kw)


def AMT(tid, name, desc, key, action, value, ok, eff, **kw):
    return AmdTweak(tid, "Driver AMD", name, desc, eff, key=key, action=action, value=value, ok=ok, **kw)


AMD = [
    AMF("amdfix_chill", "Disattiva Radeon Chill", "Chill cambia continuamente gli FPS (micro-stutter).", "chill",
        "enabled", False, lambda r: not _en(r, "chill")),
    AMF("amdfix_esync", "Disattiva Enhanced Sync", "Enhanced Sync con FreeSync e' una causa nota di stutter.", "esync",
        "enabled", False, lambda r: not _en(r, "esync")),
    AMF("amdfix_vsync_always", "V-Sync: non forzarlo sempre attivo", "Il V-Sync forzato aggiunge input lag.", "vsync",
        "vsync_mode", 1, lambda r: (r.get("vsync") or {}).get("mode") != 3, eff="media"),
    AMF("amdfix_frtc_low", "Togli il limite FPS globale troppo basso", "Adrenalin limita tutti i giochi molto sotto "
        "la frequenza del monitor.", "frtc", "enabled", False,
        lambda r: not (_en(r, "frtc") and _refresh() and ((r.get("frtc") or {}).get("fps") or 999) < _refresh() * 0.8)),
    AMF("amdfix_mlaa", "Disattiva l'antialiasing morfologico", "L'MLAA forzato sfoca l'immagine e costa FPS.", "mlaa",
        "enabled", False, lambda r: not _en(r, "mlaa"), eff="media"),

    AMT("amd_antilag_on", "Attiva Radeon Anti-Lag", "Riduce l'input lag quando la GPU e' al limite.", "antilag",
        "enabled", True, lambda r: _en(r, "antilag"), "media", risk=1,
        warning="Nel 2023 la variante 'Anti-Lag+' causava ban VAC in Counter-Strike 2 ed e' stata ritirata da AMD. "
                "L'Anti-Lag attuale del driver e Anti-Lag 2 (integrato nei giochi) sono considerati sicuri.",
        source="AMD; PC Gamer / Tom's Hardware sul caso Anti-Lag+"),
    AMT("amd_boost_off", "Disattiva Radeon Boost", "Boost abbassa la risoluzione nei movimenti veloci.", "boost",
        "enabled", False, lambda r: not _en(r, "boost"), "bassa"),
    AMT("amd_afmf_off", "Disattiva AMD Fluid Motion Frames", "AFMF genera frame intermedi aggiungendo latenza.", "afmf",
        "enabled", False, lambda r: not _en(r, "afmf"), "media", recommend=lambda s: None),
    AMT("amd_fps_cap", "Limite FPS (FRTC) 3 sotto la frequenza del monitor", "Controllo obiettivo frequenza "
        "fotogrammi = Hz - 3.", "frtc", "frtc_cap", lambda: max(30, _refresh() - 3) if _refresh() else None,
        lambda r: _en(r, "frtc") and (r.get("frtc") or {}).get("fps") == max(30, _refresh() - 3),
        "media", recommend=lambda s: None),
]
