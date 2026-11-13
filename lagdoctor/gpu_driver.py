"""Lettura (e modifica) delle impostazioni del driver video.

NVIDIA: Pannello di controllo NVIDIA -> database del driver (DRS) tramite NVAPI (nvapi64.dll, installata con il
        driver). ID e strutture presi dagli header ufficiali NVIDIA/nvapi (nvapi_interface.h, NvApiDriverSettings.h).
AMD:    Software Adrenalin -> impostazioni 3D globali tramite ADLX (amdadlx64.dll, installata con il driver).
        Ordine dei metodi preso dagli header C ufficiali GPUOpen ADLX.
"""
import ctypes
import time

# ============================================================================ NVIDIA (NVAPI DRS)

NVAPI_IDS = {
    "Initialize": 0x0150E828, "Unload": 0xD22BDD7E,
    "DRS_CreateSession": 0x0694D52E, "DRS_DestroySession": 0xDAD9CFF8,
    "DRS_LoadSettings": 0x375DBD6B, "DRS_SaveSettings": 0xFCBC7E14,
    "DRS_GetCurrentGlobalProfile": 0x617BFF9F, "DRS_GetSetting": 0x73BF8338,
    "DRS_SetSetting": 0x577DD202, "DRS_DeleteProfileSetting": 0xE4A26362,
    "DRS_EnumSettings": 0xAE3039DA,
}
NVAPI_OK, NVAPI_SETTING_NOT_FOUND = 0, -160
LOCATIONS = {0: "profilo", 1: "globale", 2: "base", 3: "predefinito del driver"}

# ID ufficiali (NvApiDriverSettings.h)
NV = {
    "PRERENDERLIMIT": 0x007BA09E, "VSYNCMODE": 0x00A879CF, "FRL_FPS": 0x10835002, "PREFERRED_PSTATE": 0x1057EB71,
    "SHADERCACHE": 0x00198FFF, "SHADERCACHE_SIZE": 0x00AC8497, "VRR_MODE": 0x1194F158,
    "VRR_APP_OVERRIDE": 0x10A879CF, "REFRESH_RATE_OVERRIDE": 0x0064B541, "QUALITY_ENHANCEMENTS": 0x00CE2691,
    "OGL_THREAD_CONTROL": 0x20C1221E, "FXAA_ENABLE": 0x1074C972, "VSYNCTEARCONTROL": 0x005A375C,
    "IDLE_FRL": 0x10835016,
    # Non presente negli header pubblici: e' lo stato della "Modalita' bassa latenza" mostrato nel Pannello
    # (0 Off, 1 On, 2 Ultra). Se il driver non lo ha, si usa PRERENDERLIMIT.
    "LOW_LATENCY_CPL": 0x0005F543,
}
VSYNC = {0x60925292: "Usa l'impostazione dell'applicazione", 0x08416747: "Disattivato", 0x47814940: "Attivato",
         0x32610244: "Mezza frequenza (1/2)", 0x71271021: "Un terzo della frequenza (1/3)",
         0x13245256: "Un quarto della frequenza (1/4)", 0x18888888: "Veloce (Fast Sync)"}
VSYNC_HALF = {0x32610244, 0x71271021, 0x13245256}
PSTATE = {0: "Adattiva", 1: "Prediligi prestazioni massime", 2: "Controllata dal driver",
          3: "Prestazioni costanti", 4: "Prediligi consumo minimo", 5: "Normale (alimentazione ottimale)"}
VRR_MODE = {0: "Disattivato", 1: "Solo schermo intero", 2: "Schermo intero e in finestra"}
VRR_OVR = {0: "Consentito", 1: "Forzato disattivato", 2: "Non consentito", 3: "ULMB", 4: "Frequenza fissa"}
QUALITY = {0xFFFFFFF6: "Alta qualita'", 0: "Qualita'", 0x0A: "Prestazioni", 0x14: "Prestazioni elevate"}


class _NvBin(ctypes.Structure):
    _fields_ = [("valueLength", ctypes.c_uint32), ("valueData", ctypes.c_uint8 * 4096)]


class _NvVal(ctypes.Union):
    # Come in nvapi.h: solo u32 / binario / stringa. Un campo a 64 bit qui allineerebbe l'unione a 8 byte e
    # sposterebbe "current" di 4 byte (offset 8224 invece di 8220): si leggerebbero e scriverebbero valori sbagliati
    # (es. 'Prediligi prestazioni massime' letto come 0 = Adattiva).
    _fields_ = [("u32", ctypes.c_uint32), ("bin", _NvBin), ("wsz", ctypes.c_uint16 * 2048)]


class NVDRS_SETTING(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("settingName", ctypes.c_uint16 * 2048),
                ("settingId", ctypes.c_uint32), ("settingType", ctypes.c_uint32),
                ("settingLocation", ctypes.c_uint32), ("isCurrentPredefined", ctypes.c_uint32),
                ("isPredefinedValid", ctypes.c_uint32), ("predef", _NvVal), ("current", _NvVal)]


assert ctypes.sizeof(NVDRS_SETTING) == 12320 and NVDRS_SETTING.current.offset == 8220, "layout NVDRS_SETTING_V1 errato"
NVDRS_SETTING_VER = ctypes.sizeof(NVDRS_SETTING) | (1 << 16)


class NvDrs:
    """Sessione sul profilo globale del Pannello di controllo NVIDIA."""

    def __init__(self):
        self.ok = False
        self.error = None
        try:
            dll = ctypes.CDLL("nvapi64.dll")
            qi = dll.nvapi_QueryInterface
            qi.restype = ctypes.c_void_p
            qi.argtypes = [ctypes.c_uint32]
            P, U = ctypes.c_void_p, ctypes.c_uint32
            sig = {"Initialize": [], "Unload": [], "DRS_CreateSession": [ctypes.POINTER(P)],
                   "DRS_DestroySession": [P], "DRS_LoadSettings": [P], "DRS_SaveSettings": [P],
                   "DRS_GetCurrentGlobalProfile": [P, ctypes.POINTER(P)],
                   "DRS_GetSetting": [P, P, U, ctypes.POINTER(NVDRS_SETTING)],
                   "DRS_SetSetting": [P, P, ctypes.POINTER(NVDRS_SETTING)],
                   "DRS_DeleteProfileSetting": [P, P, U],
                   "DRS_EnumSettings": [P, P, U, ctypes.POINTER(U), ctypes.POINTER(NVDRS_SETTING)]}
            self.f = {}
            for name, args in sig.items():
                addr = qi(NVAPI_IDS[name])
                if not addr:
                    if name == "DRS_EnumSettings":
                        continue  # serve solo alla diagnosi
                    raise RuntimeError("funzione NVAPI mancante: " + name)
                self.f[name] = ctypes.CFUNCTYPE(ctypes.c_int, *args)(addr)
            if self.f["Initialize"]() != NVAPI_OK:
                raise RuntimeError("NVAPI non inizializzata (driver NVIDIA assente?)")
            self.session = P()
            self._chk(self.f["DRS_CreateSession"](ctypes.byref(self.session)), "CreateSession")
            self._chk(self.f["DRS_LoadSettings"](self.session), "LoadSettings")
            self.profile = P()
            self._chk(self.f["DRS_GetCurrentGlobalProfile"](self.session, ctypes.byref(self.profile)), "GlobalProfile")
            self.ok = True
        except Exception as e:
            self.error = str(e)

    @staticmethod
    def _chk(r, what):
        if r != NVAPI_OK:
            raise RuntimeError("NVAPI %s ha restituito %d" % (what, r))

    def get(self, sid):
        """Restituisce (valore, posizione) oppure (None, None) se l'impostazione non e' impostata."""
        s = NVDRS_SETTING()
        s.version = NVDRS_SETTING_VER
        r = self.f["DRS_GetSetting"](self.session, self.profile, sid, ctypes.byref(s))
        if r == NVAPI_SETTING_NOT_FOUND:
            return None, None
        self._chk(r, "GetSetting")
        return s.current.u32, s.settingLocation

    def enum(self, limit=400):
        """Tutte le impostazioni salvate nel profilo globale: lista di (id, valore, posizione)."""
        out = []
        if "DRS_EnumSettings" not in self.f:
            return None
        for i in range(limit):
            s = NVDRS_SETTING()
            s.version = NVDRS_SETTING_VER
            n = ctypes.c_uint32(1)
            r = self.f["DRS_EnumSettings"](self.session, self.profile, i, ctypes.byref(n), ctypes.byref(s))
            if r != NVAPI_OK or n.value == 0:
                break
            out.append((s.settingId, s.current.u32, s.settingLocation))
        return out

    def set(self, sid, value):
        s = NVDRS_SETTING()
        s.version = NVDRS_SETTING_VER
        s.settingId = sid
        s.settingType = 0  # NVDRS_DWORD_TYPE
        s.current.u32 = value & 0xFFFFFFFF
        self._chk(self.f["DRS_SetSetting"](self.session, self.profile, ctypes.byref(s)), "SetSetting")
        self._chk(self.f["DRS_SaveSettings"](self.session), "SaveSettings")

    def reset(self, sid):
        """Torna al valore predefinito del driver."""
        r = self.f["DRS_DeleteProfileSetting"](self.session, self.profile, sid)
        if r not in (NVAPI_OK, NVAPI_SETTING_NOT_FOUND):
            self._chk(r, "DeleteProfileSetting")
        self._chk(self.f["DRS_SaveSettings"](self.session), "SaveSettings")

    def close(self):
        try:
            self.f["DRS_DestroySession"](self.session)
        except Exception:
            pass


def nvidia_read():
    drs = NvDrs()
    if not drs.ok:
        return {"ok": False, "error": drs.error}
    raw, errors = {}, {}
    for k, sid in NV.items():
        try:
            raw[k] = drs.get(sid)
        except Exception as e:
            raw[k] = (None, None)
            errors[k] = str(e)
    try:
        stored = drs.enum()
    except Exception as e:
        stored = "errore: %s" % e
    drs.close()
    r = {"ok": True, "raw": {k: list(v) for k, v in raw.items()}, "read_errors": errors,
         "stored_count": len(stored) if isinstance(stored, list) else None,
         "stored": [["0x%08X" % i, v, loc] for i, v, loc in stored] if isinstance(stored, list) else stored}
    if errors and len(errors) == len(NV):  # nessuna impostazione letta: non mostrare valori inventati
        r.update(ok=False, error="Il driver NVIDIA non risponde alla lettura delle impostazioni: " +
                 next(iter(errors.values())))
    return r


def _v(raw, k, default):
    v = raw.get(k, (None, None))[0]
    return default if v is None else v


def nvidia_analyze(raw, refresh_hz=None):
    """Trasforma i valori grezzi in righe leggibili + problemi trovati."""
    rows, probs = [], []

    def row(name, value, level="ok", note=""):
        rows.append({"name": name, "value": value, "level": level, "note": note})

    def prob(g, t, s, sol, fix=None):
        probs.append(dict(gravita=g, titolo=t, spiegazione=s, soluzione=sol, auto_fix=None, fix_id=fix))

    cpl = raw.get("LOW_LATENCY_CPL", (None, None))[0]
    prl = _v(raw, "PRERENDERLIMIT", 0)
    if cpl is not None:
        ll = {0: "Disattivata", 1: "Attivata", 2: "Ultra"}.get(cpl, "valore %d" % cpl)
    else:
        ll = "Disattivata" if prl == 0 else ("Attivata" if prl == 1 else "%d frame pre-renderizzati" % prl)
    row("Modalita' bassa latenza", ll,
        "info" if ll == "Ultra" else "ok",
        "Ultra puo' abbassare gli FPS quando il limite e' la CPU e non funziona in DX12; nei giochi con NVIDIA Reflex "
        "viene ignorata." if ll == "Ultra" else "Nei giochi con Reflex conta solo Reflex.")
    if prl > 3 and cpl is None:
        prob(2, "Troppi frame pre-renderizzati (%d)" % prl,
             "Il driver prepara fino a %d frame in anticipo: aumenta molto l'input lag." % prl,
             "Imposta 'Modalita' bassa latenza' su Attivata (si puo' fare da Ottimizzazioni).", fix="nvfix_prerender")

    vs = _v(raw, "VSYNCMODE", 0x60925292)
    vrr = _v(raw, "VRR_MODE", 1)
    row("Sincronizzazione verticale (V-Sync)", VSYNC.get(vs, hex(vs)), "bad" if vs in VSYNC_HALF else "ok")
    if vs in VSYNC_HALF:
        prob(3, "V-Sync a frazione della frequenza", "Il Pannello NVIDIA forza il V-Sync a %s: i giochi sono limitati "
             "a una frazione della frequenza del monitor (es. 82 FPS su 165 Hz)." % VSYNC[vs],
             "Correggi dalle Ottimizzazioni (torna a 'Usa l'impostazione dell'applicazione') o dal Pannello NVIDIA.", fix="nvfix_vsync_half")
    if vs == 0x18888888 and vrr:
        prob(1, "Fast Sync attivo insieme a G-SYNC", "Fast Sync con G-SYNC puo' causare stutter quando gli FPS "
             "superano la frequenza del monitor.", "Con G-SYNC usa V-Sync 'Attivato' + limite FPS 3 sotto la frequenza "
             "(Blur Busters).")

    fps = _v(raw, "FRL_FPS", 0)
    row("Frequenza fotogrammi massima", "Disattivata" if not fps else "%d FPS" % fps,
        "bad" if fps and refresh_hz and fps < refresh_hz * 0.8 else "ok")
    if fps and refresh_hz and fps < refresh_hz * 0.8:
        prob(2, "Limite FPS globale basso (%d FPS su monitor da %d Hz)" % (fps, refresh_hz),
             "Il Pannello NVIDIA limita TUTTI i giochi a %d FPS." % fps,
             "Se non e' voluto, alzalo a %d (3 sotto la frequenza) o disattivalo dalle Ottimizzazioni."
             % (refresh_hz - 3), fix="nvfix_fpscap_low")

    ps = _v(raw, "PREFERRED_PSTATE", 5)
    row("Modalita' di gestione dell'alimentazione", PSTATE.get(ps, str(ps)),
        "bad" if ps == 4 else ("info" if ps == 1 else "ok"),
        "Globale = la GPU non scende mai di frequenza: piu' consumi e calore anche sul desktop." if ps == 1 else "")
    if ps == 4:
        prob(2, "Gestione energia NVIDIA su 'consumo minimo'", "La GPU viene tenuta a frequenze basse per risparmiare.",
             "Riporta la modalita' a Normale dalle Ottimizzazioni.", fix="nvfix_minpower")

    sc = _v(raw, "SHADERCACHE", 1)
    size = raw.get("SHADERCACHE_SIZE", (None, None))
    if not sc:
        sc_txt, lvl = "DISATTIVATA", "bad"
    elif size[0] is None or size[1] == 3:
        sc_txt, lvl = "Attiva, dimensione predefinita del driver", "ok"
    elif size[0] == 0xFFFFFFFF:
        sc_txt, lvl = "Attiva, illimitata", "ok"
    else:
        sc_txt, lvl = "Attiva, %d MB" % size[0], "info" if size[0] < 4096 else "ok"
    row("Cache shader", sc_txt, lvl)
    if not sc:
        prob(3, "Cache shader NVIDIA disattivata", "Senza cache il gioco ricompila gli shader a ogni avvio: e' una "
             "delle cause principali di stutter.", "Riattivala dalle Ottimizzazioni.", fix="nvfix_shadercache")
    elif lvl == "info":
        prob(1, "Cache shader NVIDIA piccola (%d MB)" % size[0], "Con molti giochi la cache si riempie e gli shader "
             "vengono ricompilati (stutter).", "Impostala su Illimitata o 10 GB dalle Ottimizzazioni.", fix="nv_shadercache_unlimited")

    row("G-SYNC", VRR_MODE.get(vrr, str(vrr)), "ok")
    ov = _v(raw, "VRR_APP_OVERRIDE", 0)
    row("Tecnologia monitor / G-SYNC per le app", VRR_OVR.get(ov, str(ov)), "bad" if ov in (1, 2, 4) else "ok")
    if ov in (1, 2, 4) and vrr:
        prob(2, "G-SYNC bloccato nel profilo globale", "G-SYNC e' attivo ma il profilo globale lo disattiva "
             "('%s'): niente frequenza variabile nei giochi." % VRR_OVR[ov], "Riportalo su 'Consentito' dalle Ottimizzazioni.", fix="nvfix_vrr_blocked")

    rr = _v(raw, "REFRESH_RATE_OVERRIDE", 0)
    row("Frequenza di aggiornamento preferita", "La piu' alta disponibile" if rr == 1 else "Controllata dall'applicazione",
        "info" if rr != 1 else "ok", "" if rr == 1 else "Alcuni giochi in schermo intero partono a 60 Hz.")

    q = _v(raw, "QUALITY_ENHANCEMENTS", 0)
    row("Filtro texture - Qualita'", QUALITY.get(q, hex(q)), "ok")

    th = _v(raw, "OGL_THREAD_CONTROL", 0)
    row("Ottimizzazione thread", {0: "Auto", 1: "Attivata", 2: "Disattivata"}.get(th, str(th)), "bad" if th == 2 else "ok")
    if th == 2:
        prob(1, "Ottimizzazione thread disattivata", "Nei giochi OpenGL (es. Minecraft Java) il driver usa un solo "
             "thread: meno FPS.", "Riportala su Auto dalle Ottimizzazioni.", fix="nvfix_thread")

    fx = _v(raw, "FXAA_ENABLE", 0)
    row("FXAA forzato", "Attivato" if fx else "Disattivato", "bad" if fx else "ok")
    if fx:
        prob(1, "FXAA forzato su tutti i giochi", "L'FXAA forzato dal driver sfoca immagine e testi e si somma "
             "all'antialiasing del gioco.", "Disattivalo dalle Ottimizzazioni e usa l'antialiasing del gioco.", fix="nvfix_fxaa")

    idle = raw.get("IDLE_FRL", (None, None))[0]
    if idle:
        row("Limite FPS per app inattive", "%d FPS" % idle, "info", "Le finestre in secondo piano vengono limitate: "
            "normale, ma se giochi in finestra con un altro monitor in uso puo' limitare il gioco.")
    return rows, probs


# ============================================================================ AMD (ADLX)

ADLX_VT = {
    "IADLXSystem": ["GetHybridGraphicsType", "GetGPUs", "QueryInterface", "GetDisplaysServices", "GetDesktopsServices",
                    "GetGPUsChangedHandling", "EnableLog", "Get3DSettingsServices"],
    "IADLXGPUList": ["Acquire", "Release", "QueryInterface", "Size", "Empty", "Begin", "End", "At", "Clear",
                     "Remove_Back", "Add_Back", "At_GPUList"],
    "IADLXGPU": ["Acquire", "Release", "QueryInterface", "VendorId", "ASICFamilyType", "Type", "IsExternal", "Name"],
    "IADLX3DSettingsServices": ["Acquire", "Release", "QueryInterface", "GetAntiLag", "GetChill", "GetBoost",
                                "GetImageSharpening", "GetEnhancedSync", "GetWaitForVerticalRefresh",
                                "GetFrameRateTargetControl", "GetAntiAliasing", "GetMorphologicalAntiAliasing",
                                "GetAnisotropicFiltering", "GetTessellation", "GetRadeonSuperResolution",
                                "GetResetShaderCache", "Get3DSettingsChangedHandling", "GetAMDFluidMotionFrames"],
    "IADLX3DAntiLag1": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled", "SetEnabled", "GetLevel",
                        "SetLevel"],
    "IADLX3DChill": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled", "GetFPSRange", "GetMinFPS",
                     "GetMaxFPS", "SetEnabled", "SetMinFPS", "SetMaxFPS"],
    "IADLX3DBoost": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled", "GetResolutionRange",
                     "GetResolution", "SetEnabled", "SetResolution"],
    "IADLX3DImageSharpening": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled", "GetSharpnessRange",
                               "GetSharpness", "SetEnabled", "SetSharpness"],
    "IADLX3DEnhancedSync": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled", "SetEnabled"],
    "IADLX3DWaitForVerticalRefresh": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled", "GetMode",
                                      "SetMode"],
    "IADLX3DFrameRateTargetControl": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled",
                                      "GetFPSRange", "GetFPS", "SetEnabled", "SetFPS"],
    "IADLX3DAntiAliasing": ["Acquire", "Release", "QueryInterface", "IsSupported", "GetMode", "GetLevel", "GetMethod",
                            "SetMode", "SetLevel", "SetMethod"],
    "IADLX3DMorphologicalAntiAliasing": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled",
                                         "SetEnabled"],
    "IADLX3DRadeonSuperResolution": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled", "SetEnabled"],
    "IADLX3DAMDFluidMotionFrames": ["Acquire", "Release", "QueryInterface", "IsSupported", "IsEnabled", "SetEnabled"],
}
ADLX_OK_CODES = (0, 1, 2)
WFVR = {0: "Sempre disattivata", 1: "Disattivata, se non specificato dall'app", 2: "Attivata, se non specificato "
        "dall'app", 3: "Sempre attivata"}


class _Obj:
    """Oggetto ADLX: chiama i metodi della vtable per nome."""

    def __init__(self, ptr, iface):
        self.ptr, self.iface = ptr, iface

    def call(self, method, *args, restype=ctypes.c_int):
        idx = ADLX_VT[self.iface].index(method)
        vtbl = ctypes.cast(ctypes.cast(self.ptr, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        # valori semplici con il loro tipo, tutto il resto (puntatori, byref, handle) come void*
        simple = (ctypes.c_int, ctypes.c_uint, ctypes.c_uint8, ctypes.c_long)
        argtypes = [ctypes.c_void_p] + [type(a) if isinstance(a, simple) else ctypes.c_void_p for a in args]
        fn = ctypes.CFUNCTYPE(restype, *argtypes)(vtbl[idx])  # su x64 stdcall e cdecl coincidono
        return fn(self.ptr, *args)

    def release(self):
        if self.iface != "IADLXSystem":
            try:
                self.call("Release", restype=ctypes.c_long)
            except Exception:
                pass


class _Range(ctypes.Structure):
    _fields_ = [("minValue", ctypes.c_int), ("maxValue", ctypes.c_int), ("step", ctypes.c_int)]


class Adlx:
    """Sessione ADLX sulla scheda AMD dedicata."""

    def __init__(self):
        self.ok, self.error, self.gpu, self.svc, self.objs = False, None, None, None, []
        try:
            self.dll = ctypes.CDLL("amdadlx64.dll")
            ver = ctypes.c_uint64(0)
            self.dll.ADLXQueryFullVersion(ctypes.byref(ver))
            sysp = ctypes.c_void_p()
            init = self.dll.ADLXInitialize
            init.argtypes = [ctypes.c_uint64, ctypes.POINTER(ctypes.c_void_p)]
            r = init(ver.value, ctypes.byref(sysp))
            if r not in ADLX_OK_CODES or not sysp:
                raise RuntimeError("ADLX non inizializzato (codice %d): aggiorna AMD Software Adrenalin" % r)
            self.system = _Obj(sysp, "IADLXSystem")
            lst = ctypes.c_void_p()
            self._ok(self.system.call("GetGPUs", ctypes.byref(lst)), "GetGPUs")
            gl = _Obj(lst, "IADLXGPUList")
            n = gl.call("Size", restype=ctypes.c_uint)
            best = None
            for i in range(n):
                g = ctypes.c_void_p()
                if gl.call("At_GPUList", ctypes.c_uint(i), ctypes.byref(g)) not in ADLX_OK_CODES:
                    continue
                gpu = _Obj(g, "IADLXGPU")
                t = ctypes.c_int(0)
                gpu.call("Type", ctypes.byref(t))
                name = ctypes.c_char_p()
                gpu.call("Name", ctypes.byref(name))
                cand = (t.value == 2, (name.value or b"").decode(errors="ignore"), gpu)
                if best is None or (cand[0] and not best[0]):
                    best = cand
            gl.release()
            if not best:
                raise RuntimeError("nessuna scheda AMD trovata da ADLX")
            self.gpu, self.gpu_name = best[2], best[1]
            sv = ctypes.c_void_p()
            self._ok(self.system.call("Get3DSettingsServices", ctypes.byref(sv)), "Get3DSettingsServices")
            self.svc = _Obj(sv, "IADLX3DSettingsServices")
            self.ok = True
        except Exception as e:
            self.error = str(e)

    @staticmethod
    def _ok(r, what):
        if r not in ADLX_OK_CODES:
            raise RuntimeError("ADLX %s: codice %d" % (what, r))

    def feature(self, getter, iface):
        p = ctypes.c_void_p()
        if self.svc.call(getter, self.gpu.ptr, ctypes.byref(p)) not in ADLX_OK_CODES or not p:
            return None
        o = _Obj(p, iface)
        sup = ctypes.c_uint8(0)
        if o.call("IsSupported", ctypes.byref(sup)) not in ADLX_OK_CODES or not sup.value:
            o.release()
            return None
        self.objs.append(o)
        return o

    def get_bool(self, o, method="IsEnabled"):
        b = ctypes.c_uint8(0)
        return bool(b.value) if o.call(method, ctypes.byref(b)) in ADLX_OK_CODES else None

    def get_int(self, o, method):
        v = ctypes.c_int(0)
        return v.value if o.call(method, ctypes.byref(v)) in ADLX_OK_CODES else None

    def close(self):
        for o in self.objs:
            o.release()
        self.objs = []
        try:
            self.dll.ADLXTerminate()
        except Exception:
            pass


AMD_FEATURES = {  # chiave: (metodo del servizio, interfaccia)
    "antilag": ("GetAntiLag", "IADLX3DAntiLag1"), "chill": ("GetChill", "IADLX3DChill"),
    "boost": ("GetBoost", "IADLX3DBoost"), "sharpening": ("GetImageSharpening", "IADLX3DImageSharpening"),
    "esync": ("GetEnhancedSync", "IADLX3DEnhancedSync"), "vsync": ("GetWaitForVerticalRefresh", "IADLX3DWaitForVerticalRefresh"),
    "frtc": ("GetFrameRateTargetControl", "IADLX3DFrameRateTargetControl"),
    "aa": ("GetAntiAliasing", "IADLX3DAntiAliasing"), "mlaa": ("GetMorphologicalAntiAliasing", "IADLX3DMorphologicalAntiAliasing"),
    "rsr": ("GetRadeonSuperResolution", "IADLX3DRadeonSuperResolution"),
    "afmf": ("GetAMDFluidMotionFrames", "IADLX3DAMDFluidMotionFrames"),
}


def amd_read():
    a = Adlx()
    if not a.ok:
        return {"ok": False, "error": a.error}
    out = {"gpu": a.gpu_name}
    try:
        for key, (getter, iface) in AMD_FEATURES.items():
            try:
                o = a.feature(getter, iface)
            except Exception:
                o = None
            if o is None:
                out[key] = None
                continue
            d = {}
            if key == "aa":
                d["mode"] = a.get_int(o, "GetMode")
            else:
                d["enabled"] = a.get_bool(o)
            if key == "antilag":
                d["level"] = a.get_int(o, "GetLevel")
            if key == "chill":
                d["min"], d["max"] = a.get_int(o, "GetMinFPS"), a.get_int(o, "GetMaxFPS")
            if key == "boost":
                d["resolution"] = a.get_int(o, "GetResolution")
            if key == "sharpening":
                d["sharpness"] = a.get_int(o, "GetSharpness")
            if key == "vsync":
                d["mode"] = a.get_int(o, "GetMode")
            if key == "frtc":
                d["fps"] = a.get_int(o, "GetFPS")
            out[key] = d
    finally:
        a.close()
    return {"ok": True, "raw": out}


def amd_set(key, action, value=None):
    """action: 'enabled' (value bool) | 'vsync_mode' (value int) | 'frtc_fps' (value int)."""
    a = Adlx()
    if not a.ok:
        raise RuntimeError(a.error)
    try:
        getter, iface = AMD_FEATURES[key]
        o = a.feature(getter, iface)
        if o is None:
            raise RuntimeError("impostazione non supportata da questa scheda")
        if action == "enabled":
            r = o.call("SetEnabled", ctypes.c_uint8(1 if value else 0))
        elif action == "vsync_mode":
            r = o.call("SetMode", ctypes.c_int(value))
        elif action == "frtc_fps":
            r = o.call("SetFPS", ctypes.c_int(value))
        else:
            raise RuntimeError("azione sconosciuta")
        if r not in ADLX_OK_CODES:
            raise RuntimeError("Adrenalin ha rifiutato la modifica (codice %d)" % r)
    finally:
        a.close()


def amd_analyze(raw, refresh_hz=None):
    rows, probs = [], []

    def row(name, value, level="ok", note=""):
        rows.append({"name": name, "value": value, "level": level, "note": note})

    def prob(g, t, s, sol, fix=None):
        probs.append(dict(gravita=g, titolo=t, spiegazione=s, soluzione=sol, auto_fix=None, fix_id=fix))

    def en(k):
        d = raw.get(k)
        return None if not d else d.get("enabled")

    al = raw.get("antilag")
    if al:
        lvl = " (Anti-Lag 2 / Next)" if al.get("level") == 1 else ""
        row("Radeon Anti-Lag", ("Attivo" + lvl) if al.get("enabled") else "Disattivato", "ok",
            "Riduce l'input lag quando la GPU e' al limite. Il vecchio Anti-Lag+ causava ban VAC in CS2: la versione "
            "attuale del driver e Anti-Lag 2 (integrato nei giochi) sono considerati sicuri.")
    ch = raw.get("chill")
    if ch:
        row("Radeon Chill", ("Attivo (%s-%s FPS)" % (ch.get("min"), ch.get("max"))) if ch.get("enabled") else "Disattivato",
            "bad" if ch.get("enabled") else "ok")
        if ch.get("enabled"):
            prob(2, "Radeon Chill attivo", "Chill abbassa gli FPS quando muovi poco il mouse: e' pensato per risparmiare "
                 "energia, non come limitatore, e i cambi di FPS causano micro-stutter (AMD community).",
                 "Disattivalo dalle Ottimizzazioni e usa 'Controllo obiettivo frequenza fotogrammi' come limite.", fix="amdfix_chill")
    bo = raw.get("boost")
    if bo:
        row("Radeon Boost", ("Attivo (risoluzione minima %s%%)" % bo.get("resolution")) if bo.get("enabled") else "Disattivato",
            "info" if bo.get("enabled") else "ok")
        if bo.get("enabled"):
            prob(1, "Radeon Boost attivo", "Boost abbassa la risoluzione nei movimenti veloci: immagine meno nitida e "
                 "scie (ghosting) nei giochi con TAA.", "Se non ti serve, disattivalo dalle Ottimizzazioni.", fix="amd_boost_off")
    sh = raw.get("sharpening")
    if sh:
        row("Radeon Image Sharpening", ("Attivo (%s%%)" % sh.get("sharpness")) if sh.get("enabled") else "Disattivato", "ok",
            "Costo minimo, solo estetica.")
    es = en("esync")
    if es is not None:
        row("Enhanced Sync", "Attivo" if es else "Disattivato", "bad" if es else "ok")
        if es:
            prob(2, "Enhanced Sync attivo", "Con un monitor FreeSync, Enhanced Sync e' segnalato da molti utenti come "
                 "causa di stutter ogni pochi frame e sfarfallii.", "Disattivalo dalle Ottimizzazioni (con FreeSync "
                 "non serve).", fix="amdfix_esync")
    vs = raw.get("vsync")
    if vs and vs.get("mode") is not None:
        m = vs["mode"]
        row("Attesa aggiornamento verticale (V-Sync)", WFVR.get(m, str(m)), "info" if m == 3 else "ok")
        if m == 3:
            prob(1, "V-Sync forzato sempre attivo", "Il V-Sync forzato dal driver aggiunge input lag in tutti i giochi.",
                 "Riportalo a 'Disattivata, se non specificato dall'app' dalle Ottimizzazioni (o usa FreeSync).", fix="amdfix_vsync_always")
    fr = raw.get("frtc")
    if fr:
        on, fps = fr.get("enabled"), fr.get("fps")
        low = on and fps and refresh_hz and fps < refresh_hz * 0.8
        row("Controllo obiettivo frequenza fotogrammi", ("Attivo (%s FPS)" % fps) if on else "Disattivato",
            "bad" if low else "ok")
        if low:
            prob(2, "Limite FPS globale basso (%d FPS su %d Hz)" % (fps, refresh_hz),
                 "Adrenalin limita tutti i giochi a %d FPS." % fps, "Alzalo a %d (3 sotto la frequenza) o "
                 "disattivalo dalle Ottimizzazioni." % (refresh_hz - 3), fix="amdfix_frtc_low")
    aa = raw.get("aa")
    if aa and aa.get("mode") is not None:
        row("Antialiasing", {0: "Usa le impostazioni dell'app", 1: "Migliora le impostazioni dell'app",
                             2: "Sostituisci le impostazioni dell'app"}.get(aa["mode"], str(aa["mode"])),
            "info" if aa["mode"] == 2 else "ok")
        if aa["mode"] == 2:
            prob(1, "Antialiasing forzato dal driver", "Sostituire l'antialiasing dei giochi costa prestazioni e spesso "
                 "non funziona nei giochi DX12/Vulkan.", "Riportalo su 'Usa le impostazioni dell'app' in Adrenalin.")
    ml = en("mlaa")
    if ml is not None:
        row("Antialiasing morfologico (MLAA)", "Attivo" if ml else "Disattivato", "bad" if ml else "ok")
        if ml:
            prob(1, "Antialiasing morfologico attivo", "Sfoca immagine e testi e costa qualche FPS in tutti i giochi.",
                 "Disattivalo dalle Ottimizzazioni.", fix="amdfix_mlaa")
    rs = en("rsr")
    if rs is not None:
        row("Radeon Super Resolution", "Attivo" if rs else "Disattivato", "info" if rs else "ok",
            "Se un gioco gira a risoluzione piu' bassa dello schermo, RSR la ingrandisce: piu' FPS, meno nitidezza."
            if rs else "")
    af = en("afmf")
    if af is not None:
        row("AMD Fluid Motion Frames (AFMF)", "Attivo" if af else "Disattivato", "info" if af else "ok",
            "Genera frame intermedi: piu' fluidita' visiva ma piu' input lag. Sconsigliato negli sparatutto." if af else "")
        if af:
            prob(1, "AMD Fluid Motion Frames attivo", "AFMF aggiunge latenza e puo' causare artefatti; gli FPS mostrati "
                 "non corrispondono alla reattivita' reale.", "Tienilo solo per giochi single-player; disattivalo "
                 "dalle Ottimizzazioni per i competitivi.", fix="amd_afmf_off")
    return rows, probs


# ============================================================================ interfaccia comune

_CACHE = {"t": 0, "data": None}


_LOCK = __import__("threading").RLock()


def read(vendor, refresh_hz=None, max_age=3):
    """Legge e analizza le impostazioni del driver della scheda dedicata (una lettura alla volta)."""
    with _LOCK:
        return _read(vendor, refresh_hz, max_age)


def _read(vendor, refresh_hz=None, max_age=3):
    if _CACHE["data"] and time.time() - _CACHE["t"] < max_age and _CACHE["data"].get("vendor") == vendor:
        return _CACHE["data"]
    if vendor == "nvidia":
        r = nvidia_read()
        name = "Pannello di controllo NVIDIA"
        analyze = nvidia_analyze
    elif vendor == "amd":
        r = amd_read()
        name = "AMD Software Adrenalin"
        analyze = amd_analyze
    else:
        return {"vendor": vendor, "ok": False, "error": "Lettura delle impostazioni disponibile solo per NVIDIA e AMD."}
    if r.get("ok"):
        rows, probs = analyze(r["raw"], refresh_hz)
        from .tweak_docs import DRIVER_DOCS
        for row in rows:
            row["doc"] = DRIVER_DOCS.get(row["name"])
        r.update(rows=rows, problems=probs)
    r.update(vendor=vendor, panel=name)
    _CACHE.update(t=time.time(), data=r)
    return r


def invalidate():
    _CACHE["data"] = None
