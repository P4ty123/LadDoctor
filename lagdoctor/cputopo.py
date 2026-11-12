"""Struttura del processore e decisione sull'affinita' dei core per i giochi.

Legge da Windows (GetLogicalProcessorInformationEx) quali core logici condividono la stessa cache L3 (= stesso
CCD sui Ryzen) e la classe di efficienza di ogni core (core P / core E sugli Intel ibridi).

Regole (dai test della community e dai produttori):
  - Ryzen con DUE CCD e 3D V-Cache su uno solo (7900X3D, 7950X3D, 9900X3D, 9950X3D): il gioco va sul CCD con la
    cache grande. E' cio' che fa il driver AMD "3D V-Cache Performance Optimizer", ma non sempre riconosce il gioco.
  - Ryzen con DUE CCD uguali (5900X, 5950X, 7900X, 7950X, 9900X, 9950X): il gioco su un solo CCD evita la latenza
    tra i chiplet (e' la "Game Mode" di Ryzen Master). Solo se quel CCD ha almeno 6 core.
  - Intel ibridi (12a-14a gen, Core Ultra 200S): il gioco solo sui core P evita i frame lenti quando un thread
    finisce su un core E. Solo con almeno 8 core P: con meno, il gioco ha bisogno anche dei core E.
  - Tutti gli altri (un solo CCD come 9800X3D/7800X3D, Intel non ibridi, portatili...): nessuna affinita'.
    Forzarla toglierebbe core al gioco senza nessun vantaggio.
"""
import ctypes

_CACHE = {}


def cpu_name():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
    except Exception:
        import platform
        return platform.processor() or ""


def _bits(mask, group):
    return [group * 64 + i for i in range(64) if mask >> i & 1]


def read():
    """dict: logical, cores=[{cpus, eff}], l3=[{cpus, size_mb}] oppure None se non leggibile."""
    if "topo" in _CACHE:
        return _CACHE["topo"]
    topo = None
    try:
        k32 = ctypes.windll.kernel32
        f = k32.GetLogicalProcessorInformationEx
        f.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        size = ctypes.c_uint32(0)
        f(0xFFFF, None, ctypes.byref(size))
        buf = ctypes.create_string_buffer(size.value)
        if not f(0xFFFF, buf, ctypes.byref(size)):
            raise OSError("GetLogicalProcessorInformationEx")
        raw = buf.raw
        topo = parse(raw)
    except Exception:
        topo = None
    _CACHE["topo"] = topo
    return topo


def parse(raw):
    u32 = lambda o: int.from_bytes(raw[o:o + 4], "little")
    u16 = lambda o: int.from_bytes(raw[o:o + 2], "little")
    u64 = lambda o: int.from_bytes(raw[o:o + 8], "little")
    cores, l3 = [], []
    off = 0
    while off + 8 <= len(raw):
        rel, size = u32(off), u32(off + 4)
        if size == 0:
            break
        if rel == 0:    # RelationProcessorCore
            eff = raw[off + 9]
            cpus = _bits(u64(off + 32), u16(off + 40))
            cores.append({"cpus": cpus, "eff": eff})
        elif rel == 2:  # RelationCache
            level, csize, ctype = raw[off + 8], u32(off + 12), u32(off + 16)
            if level == 3 and ctype in (0, 3):  # unificata
                l3.append({"cpus": _bits(u64(off + 40), u16(off + 48)), "size_mb": round(csize / 2**20)})
        off += size
    if not cores:
        return None
    return {"logical": sum(len(c["cpus"]) for c in cores), "cores": cores, "l3": l3}


def _has_battery():
    """True se il PC ha una batteria (portatile): la modalita' efficienza libera potenza per il gioco."""
    try:
        class SPS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                        ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                        ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
        s = SPS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            return False
        return s.BatteryFlag not in (128, 255)  # 128 = nessuna batteria, 255 = sconosciuto
    except Exception:
        return False


def eco_decide(topo=None, name=None, battery=None):
    """Modalita' efficienza (EcoQoS) per i programmi in background: {"apply": bool, "why": str}.

    Rende di piu' della sola priorita' bassa dove i core non sono tutti uguali o dove la potenza e' limitata:
      - Intel ibridi (core P + E): Windows sposta i programmi in background sui core E -> core P liberi per il gioco
      - Ryzen con core di due tipi (Zen 5 + Zen 5c dei portatili): idem sui core 'c'
      - portatili: i programmi in background girano a frequenza bassa -> piu' potenza e meno calore per il gioco
    Su un desktop con tutti i core uguali (es. Ryzen 9800X3D) non cambia niente rispetto alla priorita' bassa: la
    CPU non e' limitata dalla potenza mentre giochi, quindi resta spenta."""
    topo = topo if topo is not None else read()
    name = name if name is not None else cpu_name()
    battery = _has_battery() if battery is None else battery
    if not topo:
        return {"apply": False, "why": "Non riesco a leggere la struttura del processore: resta la priorita' bassa."}
    effs = {c["eff"] for c in topo["cores"]}
    kind = decide(topo, name).get("kind")
    if len(effs) >= 2 or kind in ("intel_ibrido", "intel_ibrido_pochi_p", "ryzen_ibrido"):
        return {"apply": True, "why": "Processore con core di due tipi: i programmi in background vengono spostati "
                                      "sui core piu' piccoli e i core piu' veloci restano liberi per il gioco."}
    if battery:
        return {"apply": True, "why": "Portatile: i programmi in background girano a frequenza bassa, cosi' resta "
                                      "piu' potenza (e meno calore) per il gioco."}
    return {"apply": False, "why": "Tutti i core sono uguali e un PC fisso non e' limitato dalla potenza mentre "
                                   "giochi: la modalita' efficienza non darebbe niente in piu' della priorita' bassa, "
                                   "quindi non viene usata."}


def decide(topo=None, name=None):
    """{"apply": bool, "cpus": [...], "kind": str, "why": str} per questo PC."""
    topo = topo if topo is not None else read()
    name = name if name is not None else cpu_name()
    n = (name or "").lower()
    out = {"apply": False, "cpus": None, "cpu": name, "kind": "uniforme"}
    if not topo:
        out.update(kind="sconosciuto", why="Non riesco a leggere la struttura del processore: nessuna affinita'.")
        return out
    ncores = len(topo["cores"])
    if max(cpu for c in topo["cores"] for cpu in c["cpus"]) >= 64:
        out.update(kind="molti core", why="Processore con piu' di 64 thread: Windows li gestisce gia' a gruppi.")
        return out
    effs = sorted({c["eff"] for c in topo["cores"]})
    l3 = [x for x in topo["l3"] if x["cpus"]]
    is_amd = "amd" in n or "ryzen" in n
    is_intel = "intel" in n

    if len(l3) >= 2 and is_amd:
        big = max(l3, key=lambda x: x["size_mb"])
        small = min(l3, key=lambda x: x["size_mb"])
        cores_in = lambda cache: sum(1 for c in topo["cores"] if set(c["cpus"]) <= set(cache["cpus"]))
        if big["size_mb"] >= 1.5 * small["size_mb"] and "x3d" not in n:
            out.update(kind="ryzen_ibrido",
                       why="Ryzen con core di due tipi (es. Zen 5 + Zen 5c dei portatili): Windows e il driver AMD "
                           "li gestiscono gia'; fissare il gioco su un gruppo gli toglierebbe troppi core.")
            return out
        if big["size_mb"] >= 1.5 * small["size_mb"] and cores_in(big) >= 6:
            out.update(apply=True, cpus=sorted(big["cpus"]), kind="ryzen_x3d_2ccd",
                       why="Ryzen con due CCD e 3D V-Cache solo su uno (L3 %d MB contro %d MB): il gioco viene "
                           "messo sui %d core con la cache grande, dove va piu' veloce. Fa la stessa cosa del driver "
                           "AMD, ma funziona anche con i giochi che il driver non riconosce."
                           % (big["size_mb"], small["size_mb"], cores_in(big)))
            return out
        first = next((x for x in l3 if 0 in x["cpus"]), l3[0])
        if cores_in(first) >= 6:
            out.update(apply=True, cpus=sorted(first["cpus"]), kind="ryzen_2ccd",
                       why="Ryzen con %d CCD uguali: il gioco viene tenuto sul primo CCD (%d core, i piu' veloci) "
                           "per evitare la latenza quando i thread si spostano tra i chiplet. E' quello che fa la "
                           "'Game Mode' di Ryzen Master, senza spegnere l'altro CCD per il resto del PC."
                           % (len(l3), cores_in(first)))
        else:
            out.update(kind="ryzen_2ccd_piccolo",
                       why="Ryzen con piu' CCD ma pochi core per CCD: il gioco ha bisogno di tutti i core.")
        return out

    if len(effs) >= 2 and (is_intel or not is_amd):
        top = max(effs)
        pcores = [c for c in topo["cores"] if c["eff"] == top]
        ecount = ncores - len(pcores)
        if len(pcores) >= 8:
            out.update(apply=True, cpus=sorted(cpu for c in pcores for cpu in c["cpus"]), kind="intel_ibrido",
                       why="Intel ibrido con %d core P e %d core E: il gioco viene tenuto sui core P, cosi' nessun "
                           "thread importante finisce su un core E lento (causa tipica di frame lenti). I core E "
                           "restano a Windows e ai programmi in background." % (len(pcores), ecount))
        else:
            out.update(kind="intel_ibrido_pochi_p",
                       why="Intel ibrido con solo %d core P: togliere i core E al gioco gli lascerebbe troppi pochi "
                           "core. Windows 11 (Thread Director) li gestisce meglio da solo." % len(pcores))
        return out

    if is_amd and "x3d" in n:
        why = ("Ryzen X3D con un solo CCD: tutti i core hanno la 3D V-Cache, quindi non c'e' un gruppo di core "
               "migliore. Forzare l'affinita' toglierebbe solo core al gioco.")
    else:
        why = "Tutti i core sono uguali e condividono la stessa cache: Windows li gestisce gia' nel modo migliore."
    out["why"] = why
    return out
