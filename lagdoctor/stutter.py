"""Diagnosi precisa degli stutter.

1) Legge da PresentMon, per ogni frame, quanto hanno lavorato CPU e GPU e quanto si e' atteso
   (CPUBusy / CPUWait / GPUBusy / GPUWait: definizioni del README ufficiale di PresentMon).
2) Per ogni stutter capisce QUALE PARTE del frame e' esplosa (lavoro CPU, lavoro GPU, attesa).
3) Guarda cosa succedeva nel sistema in quel quarto di secondo (latenza driver, disco del gioco, paging, VRAM,
   frequenza CPU, processi in background, thread principale) e assegna una causa con il suo grado di certezza.
4) Riassume: limite CPU/GPU, modalita' di presentazione, V-Sync, distribuzione delle cause.

Ogni causa ha una chiave che factors.py collega alle ottimizzazioni del catalogo.
"""
import csv
import statistics

ALIASES = {
    "ft": ["frametime", "msbetweenappstart", "msbetweenpresents"],
    "cpu_busy": ["cpubusy", "mscpubusy"],
    "cpu_wait": ["cpuwait", "mscpuwait"],
    "gpu_busy": ["gpubusy", "msgpubusy"],
    "gpu_wait": ["gpuwait", "msgpuwait"],
    "gpu_time": ["gputime", "msgputime"],
    "gpu_latency": ["gpulatency", "msgpulatency"],
    "disp_latency": ["displaylatency", "msuntildisplayed"],
    "displayed": ["displayedtime", "msbetweendisplaychange"],
    "present_mode": ["presentmode"],
    "sync": ["syncinterval"],
    "tearing": ["allowstearing"],
    "app": ["application"],
    "frame_type": ["frametype"],
}

# Etichette, spiegazioni e chiave "causa" (usata da factors.py) di ogni tipo di stutter
KINDS = {
    "dpc": ("Driver che bloccano il sistema (latenza DPC/ISR)", "dpc"),
    "disk": ("Caricamento dati dal disco durante il gioco", "disk"),
    "paging": ("Memoria spostata sul disco (paging)", "paging"),
    "vram": ("Memoria video piena (VRAM che trabocca nella RAM)", "vram"),
    "background": ("Programma in background", "background"),
    "cpu_throttle": ("CPU che rallenta (energia o calore)", "cpu_throttle"),
    "gpu_throttle": ("GPU che rallenta (calore o energia)", "throttle"),
    "shader": ("Picco di lavoro CPU del gioco: compilazione shader / caricamento zona", "shader"),
    "main_thread": ("Thread principale del gioco al limite", "main_thread"),
    "gpu_spike": ("Picco di lavoro della GPU (effetto o scena pesante)", "gpu_bound"),
    "vsync": ("V-Sync: frame arrivato in ritardo di un refresh", "vsync"),
    "present": ("Presentazione del frame bloccata (driver video / compositore di Windows)", "present"),
    "system": ("Blocco di sistema non identificato", "pacing"),
}


def _f(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def load_frames(csv_path, process_name=None):
    """Tutte le colonne utili di PresentMon, frame per frame (gestisce i nomi delle varie versioni)."""
    frames = []
    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        idx = None
        t = 0.0
        for row in reader:
            if not row:
                continue
            if idx is None:
                head = [h.strip().lower() for h in row]
                idx = {k: next((head.index(a) for a in al if a in head), None) for k, al in ALIASES.items()}
                if idx["ft"] is None:
                    raise ValueError("Formato CSV di PresentMon non riconosciuto")
                continue

            def g(k):
                i = idx[k]
                return row[i] if i is not None and i < len(row) else None
            if process_name and idx["app"] is not None and (g("app") or "").lower() != process_name.lower():
                continue
            ft = _f(g("ft"))
            if ft is None or not 0 < ft < 5000:
                continue
            t += ft / 1000.0
            disp = g("displayed")
            frames.append({
                "t": t, "ft": ft, "cpu_busy": _f(g("cpu_busy")), "cpu_wait": _f(g("cpu_wait")),
                "gpu_busy": _f(g("gpu_busy")), "gpu_wait": _f(g("gpu_wait")), "gpu_time": _f(g("gpu_time")),
                "disp_latency": _f(g("disp_latency")),
                "dropped": None if disp is None else (disp.strip().upper() == "NA"),
                "present_mode": (g("present_mode") or "").strip(), "sync": _f(g("sync")),
                "tearing": _f(g("tearing")), "frame_type": (g("frame_type") or "").strip(),
            })
    return frames


def _median(vals, default=None):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else default


def _pct(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    return vals[min(len(vals) - 1, int(len(vals) * p / 100))]


class Context:
    """Stato del sistema intorno a un istante (campioni ogni 0,25 s) confrontato con la normalita' della sessione."""

    def __init__(self, samples):
        self.s = sorted(samples, key=lambda x: x["t"])
        self.base = {}
        for k in ("lat_max", "dpc_pct", "isr_pct", "hard_faults", "game_read_mb", "cpu_perf", "vram_shared_mb",
                  "game_cpu", "game_top_thread", "disk_read_mb"):
            self.base[k] = _median([x.get(k) for x in self.s])

    def bg_normal(self, name):
        """Uso normale di CPU di un processo: mediana su TUTTI i campioni lenti (assente = 0)."""
        slow = [x for x in self.s if "bg_top" in x]
        if not slow:
            return 0.0
        vals = [dict(x.get("bg_top") or []).get(name, 0.0) for x in slow]
        return _median(vals, 0.0)

    def near(self, t, margin=0.4):
        return [x for x in self.s if abs(x["t"] - t) <= margin]

    def evidence(self, t):
        """Segnali anomali intorno all'istante t: dict nome -> (valore, normale)."""
        w = self.near(t)
        if not w:
            return {}
        ev = {}
        b = self.base

        def mx(k):
            vals = [x.get(k) for x in w if x.get(k) is not None]
            return max(vals) if vals else None

        def mn(k):
            vals = [x.get(k) for x in w if x.get(k) is not None]
            return min(vals) if vals else None
        dpc = mx("dpc_pct")
        if dpc is not None and dpc >= 2.0 and dpc >= 2.5 * (b["dpc_pct"] or 0.2):
            ev["dpc_pct"] = (dpc, b["dpc_pct"])
        isr = mx("isr_pct")
        if isr is not None and isr >= 2.0 and isr >= 2.5 * (b["isr_pct"] or 0.2):
            ev["isr_pct"] = (isr, b["isr_pct"])
        lat = mx("lat_max")
        if lat is not None and lat >= 3.0 and lat >= 3 * (b["lat_max"] or 0.3):
            if not is_timer_tick(lat) or "dpc_pct" in ev or "isr_pct" in ev:
                ev["lat"] = (lat, b["lat_max"])
        hf = mx("hard_faults")
        rd = mx("game_read_mb")
        ram = mx("ram_pct")
        avail = mn("avail_mb")
        pressure = (ram is not None and ram >= 85) or (avail is not None and avail < 2048)
        if hf is not None and hf >= 100 and hf >= 5 * (b["hard_faults"] or 5):
            if pressure:
                ev["paging"] = (hf, b["hard_faults"])
            else:  # RAM libera: sono letture dei file del gioco (file mappati in memoria), non paging
                ev["streaming"] = (hf, b["hard_faults"])
        if rd is not None and rd >= 15 and rd >= 3 * ((b["game_read_mb"] or 0) + 2):
            ev["disk"] = (rd, b["game_read_mb"])
        perf = mn("cpu_perf")
        if perf is not None and b["cpu_perf"] and perf < 0.85 * b["cpu_perf"]:
            ev["cpu_perf"] = (perf, b["cpu_perf"])
        sh = mx("vram_shared_mb")
        if sh is not None and b["vram_shared_mb"] is not None and sh >= b["vram_shared_mb"] + 150:
            ev["vram_shared"] = (sh, b["vram_shared_mb"])
        vram = [x for x in w if x.get("vram_used") and x.get("vram_total")]
        if vram and max(x["vram_used"] / x["vram_total"] for x in vram) >= 0.95:
            ev["vram_full"] = (max(x["vram_used"] / x["vram_total"] for x in vram) * 100, None)
        if any(x.get("thr_thermal") for x in w):
            ev["gpu_throttle"] = (1, None)
        th = mx("game_top_thread")
        if th is not None and th >= 95:
            ev["main_thread"] = (th, b["game_top_thread"])
        # i processi in background si leggono una volta al secondo: finestra piu' larga
        bg = {}
        for x in self.near(t, 0.75):
            for name, c in x.get("bg_top", []) or []:
                bg[name] = max(bg.get(name, 0), c)
        spikes = [(n, c) for n, c in bg.items() if c >= 5 and c >= 3 * max(self.bg_normal(n), 0.5)]
        if spikes:
            ev["background"] = (max(spikes, key=lambda x: x[1]), None)
        return ev


TIMER_TICK = (13.0, 16.6)  # 15,6 ms - 1 ms di sonno richiesto, con margine


def is_timer_tick(lat):
    return TIMER_TICK[0] <= lat <= TIMER_TICK[1]


def exclusions(samples, duration_s, warmup=5.0, after_focus=3.0):
    """Intervalli da NON analizzare: primi secondi e momenti in cui il gioco non era la finestra attiva
    (Alt+Tab, menu di Windows) piu' qualche secondo dopo il ritorno, quando Windows ricarica il gioco in memoria."""
    ex = [(0.0, warmup)]
    s = sorted((x for x in samples if x.get("fg") is not None), key=lambda x: x["t"])
    if s and sum(1 for x in s if x["fg"] is False) > 0.8 * len(s):
        # il gioco non risulta MAI in primo piano: la finestra appartiene a un altro processo (launcher/anti-cheat)
        return ex
    start = None
    for x in s:
        if x["fg"] is False and start is None:
            start = x["t"] - 0.25
        elif x["fg"] is True and start is not None:
            ex.append((start, x["t"] + after_focus))
            start = None
    if start is not None:
        ex.append((start, duration_s + 1))
    return ex


def excluded(t, ex):
    return any(a <= t <= b for a, b in ex)


def is_stutter(ft, med, f=None, refresh_hz=None):
    """Stutter VISIBILE: almeno 2,5 volte il frame normale e almeno 12 ms in piu'.
    Eccezione: con il V-Sync un frame che resta per 2+ refresh si vede sempre."""
    if ft >= 2.5 * med and ft - med >= 12.0:
        return True
    return f is not None and ft - med >= 8.0 and _vsync_miss(f, refresh_hz)


def classify(frames, samples, refresh_hz=None):
    """Trova e classifica gli stutter. Restituisce (stutters, summary)."""
    ctx = Context(samples) if samples else None
    has_busy = sum(1 for f in frames if f["cpu_busy"] is not None and f["gpu_busy"] is not None) > len(frames) * 0.5
    stutters = []
    win = []
    for i, f in enumerate(frames):
        if len(win) >= 10:
            med = _median([w["ft"] for w in win])
            if is_stutter(f["ft"], med, f, refresh_hz):
                stutters.append(_classify_one(i, f, win, med, ctx, has_busy, refresh_hz))
        win.append(f)
        if len(win) > 30:
            win.pop(0)
    return stutters, _summary(frames, stutters, has_busy, refresh_hz)


def _classify_one(i, f, win, med, ctx, has_busy, refresh_hz):
    excess = f["ft"] - med
    part, detail = "sconosciuta", ""
    if has_busy and f["cpu_busy"] is not None and f["gpu_busy"] is not None:
        m_cpu = _median([w["cpu_busy"] for w in win], 0)
        m_gpu = _median([w["gpu_busy"] for w in win], 0)
        d_cpu, d_gpu = f["cpu_busy"] - m_cpu, f["gpu_busy"] - m_gpu
        if d_cpu >= 0.5 * excess and d_cpu >= d_gpu:
            part = "cpu"
        elif d_gpu >= 0.5 * excess:
            part = "gpu"
        else:
            part = "attesa"
        detail = "CPU %.1f ms (normale %.1f), GPU %.1f ms (normale %.1f)" % (f["cpu_busy"], m_cpu, f["gpu_busy"], m_gpu)
    ev = ctx.evidence(f["t"]) if ctx else {}
    kind, conf = _decide(part, ev, f, refresh_hz)
    return {"i": i, "t": round(f["t"], 3), "ft": round(f["ft"], 2), "med": round(med, 2), "part": part,
            "kind": kind, "label": KINDS[kind][0], "cause": KINDS[kind][1], "conf": conf,
            "evidence": _ev_text(ev), "detail": detail}


def _vsync_miss(f, refresh_hz):
    if not refresh_hz or not f.get("sync") or f.get("tearing"):
        return False
    period = 1000.0 / refresh_hz
    k = round(f["ft"] / period)
    return k >= 2 and abs(f["ft"] - k * period) < 0.25 * period


def _decide(part, ev, f, refresh_hz):
    """Regole: prima i segnali di sistema che spiegano DIRETTAMENTE quella parte del frame."""
    if "lat" in ev or "dpc_pct" in ev or "isr_pct" in ev:
        if part in ("attesa", "cpu", "sconosciuta"):
            return "dpc", "alta" if ("lat" in ev and ("dpc_pct" in ev or "isr_pct" in ev)) else "media"
    if part == "cpu":
        if "paging" in ev:
            return "paging", "alta"
        if "disk" in ev:
            return "disk", "alta"
        if "streaming" in ev:
            return "disk", "media"
        if "background" in ev:
            return "background", "media"
        if "cpu_perf" in ev:
            return "cpu_throttle", "media"
        if "main_thread" in ev:
            return "main_thread", "media"
        return "shader", "media"
    if part == "gpu":
        if "vram_shared" in ev or "vram_full" in ev:
            return "vram", "alta" if "vram_shared" in ev else "media"
        if "gpu_throttle" in ev:
            return "gpu_throttle", "alta"
        return "gpu_spike", "media"
    if part == "attesa":
        if _vsync_miss(f, refresh_hz):
            return "vsync", "alta"
        if "cpu_perf" in ev:
            return "cpu_throttle", "media"
        if "paging" in ev:
            return "paging", "media"
        if "composed" in (f.get("present_mode") or "").lower():
            return "present", "media"
        return "present", "bassa"
    # senza dati CPU/GPU per frame (PresentMon vecchio o API non supportata): solo segnali di sistema
    for key, kind in (("paging", "paging"), ("disk", "disk"), ("streaming", "disk"), ("vram_shared", "vram"), ("vram_full", "vram"),
                      ("background", "background"), ("cpu_perf", "cpu_throttle"), ("gpu_throttle", "gpu_throttle"),
                      ("main_thread", "main_thread")):
        if key in ev:
            return kind, "media"
    if _vsync_miss(f, refresh_hz):
        return "vsync", "media"
    return "system", "bassa"


def _ev_text(ev):
    parts = []
    if "lat" in ev:
        parts.append("risveglio del sistema in ritardo di %.1f ms (normale %.1f)" % (ev["lat"][0], ev["lat"][1] or 0))
    if "dpc_pct" in ev:
        parts.append("tempo CPU nei DPC %.1f%%" % ev["dpc_pct"][0])
    if "isr_pct" in ev:
        parts.append("tempo CPU negli interrupt %.1f%%" % ev["isr_pct"][0])
    if "paging" in ev:
        parts.append("%.0f pagine lette dal disco al secondo con la RAM quasi piena" % ev["paging"][0])
    if "streaming" in ev:
        parts.append("il gioco leggeva i suoi file dal disco (%.0f pagine/s, RAM libera)" % ev["streaming"][0])
    if "disk" in ev:
        parts.append("il gioco leggeva %.0f MB/s dal disco (normale %.0f)" % (ev["disk"][0], ev["disk"][1] or 0))
    if "cpu_perf" in ev:
        parts.append("prestazioni CPU al %.0f%% (normale %.0f%%)" % ev["cpu_perf"])
    if "vram_shared" in ev:
        parts.append("+%.0f MB di grafica spostati nella RAM" % (ev["vram_shared"][0] - (ev["vram_shared"][1] or 0)))
    if "vram_full" in ev:
        parts.append("VRAM al %.0f%%" % ev["vram_full"][0])
    if "gpu_throttle" in ev:
        parts.append("GPU in throttling termico")
    if "main_thread" in ev:
        parts.append("thread principale del gioco al %.0f%% di un core" % ev["main_thread"][0])
    if "background" in ev:
        parts.append("%s al %.0f%% di CPU" % ev["background"][0])
    return "; ".join(parts)


def detect_cap(frames):
    """Durata del frame imposta da un limite FPS, se c'e': almeno il 45% dei frame entro +-2% dello stesso valore."""
    fts = sorted(f["ft"] for f in frames if 2 < f["ft"] < 60)
    if len(fts) < 500:
        return None
    best, best_n = None, 0
    step = max(1, len(fts) // 400)
    j0 = 0
    for i in range(0, len(fts), step):  # finestra scorrevole su valori ordinati
        c = fts[i]
        while fts[j0] < c * 0.98:
            j0 += 1
        j1 = j0
        while j1 < len(fts) and fts[j1] <= c * 1.02:
            j1 += 1
        if j1 - j0 > best_n:
            best, best_n = c, j1 - j0
    return best if best_n >= 0.45 * len(fts) else None


def _summary(frames, stutters, has_busy, refresh_hz):
    n = len(frames)
    out = {"frames": n, "has_busy": has_busy, "stutters": len(stutters)}
    # limite FPS (del gioco, del driver o V-Sync): molti frame con la STESSA durata
    cap_ft = detect_cap(frames)
    if cap_ft:
        out["cap_fps"] = round(1000.0 / cap_ft)
    # limite CPU / GPU / attesa
    if has_busy:
        g = c = w = 0
        for f in frames:
            if f["cpu_busy"] is None or f["gpu_busy"] is None:
                continue
            gr, cr = f["gpu_busy"] / f["ft"], f["cpu_busy"] / f["ft"]
            capped = cap_ft is not None and abs(f["ft"] - cap_ft) <= 0.04 * cap_ft
            if gr >= 0.85:      # la GPU lavora per quasi tutto il frame: e' lei il limite
                g += 1
            elif capped:        # frame alla durata del limite FPS: l'attesa e' voluta (spesso contata come "CPU")
                w += 1
            elif cr >= 0.6:     # la GPU aspetta e la CPU lavora: limite CPU (o attese del motore del gioco)
                c += 1
            else:               # entrambe aspettano: limite FPS, V-Sync o frame limiter
                w += 1
        tot = max(g + c + w, 1)
        out["bound"] = {"gpu": g / tot * 100, "cpu": c / tot * 100, "limitato": w / tot * 100}
    modes = {}
    for f in frames:
        if f["present_mode"]:
            modes[f["present_mode"]] = modes.get(f["present_mode"], 0) + 1
    if modes:
        top = max(modes, key=modes.get)
        out["present_mode"] = top
        out["present_mode_pct"] = modes[top] / n * 100
    syncs = [f["sync"] for f in frames if f["sync"] is not None]
    if syncs:
        out["vsync_game"] = _median(syncs) >= 1
    tear = [f["tearing"] for f in frames if f["tearing"] is not None]
    if tear:
        out["tearing"] = _median(tear) >= 1
    dropped = [f["dropped"] for f in frames if f["dropped"] is not None]
    if dropped:
        out["dropped_pct"] = sum(dropped) / len(dropped) * 100
    lat = [f["disp_latency"] for f in frames if f["disp_latency"] is not None]
    if lat:
        out["display_latency_ms"] = _median(lat)
    kinds = {}
    for s in stutters:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    out["kinds"] = sorted(([k, v, v / max(len(stutters), 1) * 100, KINDS[k][0], KINDS[k][1]] for k, v in kinds.items()),
                          key=lambda x: -x[1])
    return out


def system_health(samples):
    """Valori della sessione intera (anche senza stutter): latenza driver, DPC, frequenza CPU."""
    samples = [dict(x) for x in samples]
    for x in samples:  # i "tick" del timer di Windows non sono latenza dei driver
        if x.get("lat_max") is not None and is_timer_tick(x["lat_max"]) and (x.get("dpc_pct") or 0) < 2 \
                and (x.get("isr_pct") or 0) < 2:
            x["lat_max"] = None

    def p(k, q):
        return _pct([x.get(k) for x in samples], q)
    return {"lat_p50": p("lat_max", 50), "lat_p99": p("lat_max", 99), "lat_max": p("lat_max", 100),
            "dpc_p95": p("dpc_pct", 95), "isr_p95": p("isr_pct", 95), "cpu_perf_p10": p("cpu_perf", 10),
            "cpu_perf_p50": p("cpu_perf", 50), "top_thread_p90": p("game_top_thread", 90),
            "hard_faults_p95": p("hard_faults", 95)}


def problems(stutters, summary, health, stats, vt, refresh_hz=None, drivers=None, drive=None):
    """Problemi da mostrare, ognuno con la sua chiave 'cause' per factors.py."""
    P = []
    total = max(len(stutters), 1)
    dur_min = max(stats["durata_s"] / 60.0, 0.01)

    def add(g, cause, t, s, sol):
        P.append(dict(gravita=g, titolo=t, spiegazione=s, soluzione=sol, auto_fix=None, cause=cause))

    def share(kind):
        return sum(1 for x in stutters if x["kind"] == kind), sum(1 for x in stutters if x["kind"] == kind) / total * 100

    def examples(kind, k=2):
        ex = [x for x in stutters if x["kind"] == kind and x["evidence"]][:k]
        return (" Esempio: al minuto %s %s." % ("%d:%02d" % (ex[0]["t"] // 60, ex[0]["t"] % 60), ex[0]["evidence"])) if ex else ""

    # le cause principali vengono sempre spiegate quando gli stutter sono frequenti
    per_min = len(stutters) / dur_min
    top = [k[0] for k in summary.get("kinds", [])[:3]]
    top += [x["kind"] for x in stutters if x["conf"] == "alta"]  # prove misurate certe: si spiegano sempre

    def relevant(kind, min_n=3, min_pct=12):
        n, pct = share(kind)
        main = n >= min_n and (pct >= min_pct or n / dur_min >= 1)
        return main or (kind in top and n >= 1 and per_min >= 2), n, pct

    ok, n, pct = relevant("dpc")
    lat_bad = health.get("lat_p99") is not None and health["lat_p99"] >= 2.0
    if ok or lat_bad:
        drv = ""
        if drivers:
            drv = " Driver da controllare per primi sul tuo PC: " + ", ".join(drivers[:6]) + "."
        add(3 if (ok and pct >= 25) else 2, "dpc", "Driver che bloccano il sistema (latenza DPC/ISR)",
            ("%d stutter (%.0f%%) coincidono con blocchi di sistema. " % (n, pct) if ok else "") +
            "Durante la partita Windows ha impiegato fino a %.1f ms in piu' a risvegliare un processo ad alta priorita' "
            "(normale sotto 1 ms; per i giochi sopra 2 ms e' un problema). Succede quando un driver (rete, audio, "
            "Wi-Fi, USB, scheda video, RGB) occupa la CPU troppo a lungo." % (health.get("lat_max") or 0) + drv,
            "1) Aggiorna driver di chipset, scheda di rete, audio e scheda video dal sito del produttore. 2) Chiudi o "
            "disinstalla software RGB/periferiche e audio 'potenziato' (Nahimic, Sonic Studio). 3) Se usi il Wi-Fi, prova "
            "il cavo. 4) Per sapere ESATTAMENTE quale driver e' il colpevole usa LatencyMon (Resplendence). Vedi anche "
            "le impostazioni collegate qui sotto.")
    ok, n, pct = relevant("disk")
    if ok:
        nvme = drive and (drive.get("bus") == "NVMe" or drive.get("tipo") == "SSD") and \
            (drive.get("libero_pct") or 100) >= 10
        if nvme:
            add(2, "disk", "Stutter mentre il gioco carica dati (%d, %.0f%%)" % (n, pct),
                "In quei momenti il gioco stava caricando texture o zone nuove." + examples("disk") + " Il gioco e' su "
                "un SSD %s con spazio libero: la velocita' del disco NON e' il problema (un NVMe legge migliaia di MB/s). "
                "Lo scatto viene da come il motore del gioco carica e decomprime i dati." % drive.get("bus", ""),
                "Abbassa le impostazioni di streaming/qualita' delle texture o la distanza di visualizzazione; escludi "
                "la cartella del gioco da Defender (il controllo antivirus dei file appena letti rallenta i "
                "caricamenti); tieni il gioco aggiornato.")
        else:
            add(2, "disk", "Stutter da caricamento dal disco (%d, %.0f%%)" % (n, pct),
                "In quei momenti il gioco stava leggendo molti dati dal disco (streaming di texture o zone)." +
                examples("disk"), "Sposta il gioco su un SSD NVMe con almeno il 15% di spazio libero; escludi la cartella "
                "dei giochi da Defender; TRIM attivo.")
    ok, n, pct = relevant("paging")
    if ok:
        add(3, "paging", "Stutter da paging: la RAM era quasi piena (%d, %.0f%%)" % (n, pct),
            "In quei momenti la RAM era quasi esaurita e Windows rileggeva dal disco memoria spostata nel file di "
            "paging." + examples("paging"),
            "Chiudi i programmi pesanti (browser, Discord in streaming), lascia il file di paging automatico; se "
            "succede spesso servono piu' GB di RAM.")
    ok, n, pct = relevant("vram")
    if ok:
        add(3, "vram", "Stutter da VRAM piena (%d, %.0f%%)" % (n, pct),
            "La memoria della scheda video era piena: parte della grafica e' finita nella RAM di sistema, molto piu' "
            "lenta." + examples("vram"), "Abbassa di un livello la qualita' delle TEXTURE (e ray tracing / frame "
            "generation se attivi); chiudi browser e app che usano la GPU.")
    ok, n, pct = relevant("background")
    if ok:
        add(2, "background", "Stutter causati da programmi in background (%d, %.0f%%)" % (n, pct),
            "Un altro programma ha usato molta CPU proprio durante gli scatti." + examples("background"),
            "Chiudi quel programma mentre giochi o toglilo dall'avvio automatico.")
    ok, n, pct = relevant("cpu_throttle")
    low_perf = health.get("cpu_perf_p10") is not None and health.get("cpu_perf_p50") and \
        health["cpu_perf_p10"] < 0.8 * health["cpu_perf_p50"]
    if ok or low_perf:
        add(2, "cpu_throttle", "La CPU rallenta durante il gioco",
            ("%d stutter (%.0f%%) coincidono con un calo delle prestazioni della CPU. " % (n, pct) if ok else "") +
            "La frequenza effettiva della CPU e' scesa fino al %.0f%% del normale: risparmio energetico o calore." %
            ((health.get("cpu_perf_p10") or 0) / (health.get("cpu_perf_p50") or 1) * 100),
            "Piano energetico Bilanciato o Prestazioni elevate (non Risparmio), modalita' 'Prestazioni migliori', "
            "controlla le temperature della CPU e il dissipatore.")
    ok, n, pct = relevant("gpu_throttle")
    if ok:
        add(2, "throttle", "Stutter da GPU che rallenta (%d, %.0f%%)" % (n, pct),
            "La scheda video ha abbassato le frequenze per il calore proprio durante gli scatti.",
            "Pulisci la polvere, migliora il flusso d'aria, togli eventuali overclock.")
    ok_sh, n_sh, pct_sh = relevant("shader")
    if ok_sh:
        times = [x["t"] for x in stutters if x["kind"] == "shader"]
        early = sum(1 for t in times if t < stats["durata_s"] / 3)
        late = sum(1 for t in times if t >= 2 * stats["durata_s"] / 3)
        if early >= 2 * max(late, 1):
            t, s = ("Stutter da compilazione shader (%d, %.0f%%)" % (n_sh, pct_sh),
                    "Picchi di lavoro della CPU del gioco concentrati all'inizio (%d nel primo terzo, %d nell'ultimo): "
                    "il gioco compila gli shader la prima volta che vede effetti o zone nuove." % (early, late))
        else:
            t, s = ("Stutter del motore del gioco (%d, %.0f%%)" % (n_sh, pct_sh),
                    "Picchi di lavoro della CPU del gioco distribuiti in tutta la partita, senza colpe del sistema "
                    "(disco, driver e background erano tranquilli): tipico 'traversal stutter' (caricamento di nuove zone) "
                    "o compilazione shader continua, frequente nei giochi open world.")
        add(2, "shader", t, s, vt["shader"] + ". Lascia finire la precompilazione degli shader se il gioco la offre; "
            "limita gli FPS a un valore stabile; il resto dipende dagli aggiornamenti del gioco.")
    ok, n, pct = relevant("main_thread")
    bound = summary.get("bound") or {}
    top_th = health.get("top_thread_p90")
    if summary.get("cap_fps"):
        P.append(dict(gravita=1, cause="fps_cap", auto_fix=None,
                      titolo="Il gioco e' limitato a %d FPS" % summary["cap_fps"],
                      spiegazione="La maggior parte dei frame dura esattamente lo stesso tempo: c'e' un limite FPS (nel "
                                  "gioco, nel driver) o il V-Sync. Non e' un problema: in quei frame CPU e GPU aspettano "
                                  "apposta, quindi NON contano come limite della CPU.",
                      soluzione="Se vuoi piu' FPS alza o togli il limite nelle impostazioni del gioco; con G-SYNC/FreeSync "
                                "il valore ideale e' 3 FPS sotto la frequenza del monitor."))
    if ok or (bound.get("cpu", 0) >= 50 and (top_th or 0) >= 90):
        add(2, "main_thread", "Limitato dal thread principale della CPU",
            "Il gioco usa un core al 100% (thread principale) mentre la GPU aspetta: gli FPS dipendono dalla velocita' "
            "di un singolo core." + (" %d stutter (%.0f%%) in questi momenti." % (n, pct) if ok else ""),
            "Riduci le impostazioni che pesano sulla CPU (distanza di visualizzazione, densita' di NPC/folla, "
            "simulazione); chiudi i programmi in background; il piano energetico non deve limitare la CPU.")
    elif bound.get("cpu", 0) >= 50 and top_th is not None and top_th < 75:
        # la GPU aspetta ma nessun core della CPU e' al limite: non e' la potenza della CPU
        add(1, "cpu_bound", "La GPU aspetta il gioco, ma la CPU non e' al limite (%.0f%% dei frame)" % bound["cpu"],
            "Nel %.0f%% dei frame la GPU finisce prima che il gioco prepari il frame successivo, pero' il thread piu' "
            "carico del gioco e' solo al %.0f%% di un core: la CPU ha margine. Sono attese interne del motore del gioco "
            "(simulazione, sincronizzazioni, limite FPS interno variabile), non mancanza di potenza della CPU."
            % (bound["cpu"], top_th),
            "Cambiare CPU non aiuterebbe. Puoi ridurre le impostazioni che pesano sulla simulazione (distanza di "
            "visualizzazione, densita' di oggetti/traffico) o semplicemente goderti gli FPS che hai.")
    elif bound.get("cpu", 0) >= 50:
        add(1, "cpu_bound", "Il gioco e' limitato dalla CPU (%.0f%% dei frame)" % bound["cpu"],
            "Per la maggior parte dei frame la GPU finisce prima della CPU: abbassare la grafica non aumenta gli FPS.",
            "Riduci le impostazioni che pesano sulla CPU (distanza di visualizzazione, densita' di oggetti/traffico); "
            "chiudi i programmi in background.")
    ok, n, pct = relevant("gpu_spike")
    if ok:
        add(1, "gpu_bound", "Picchi di lavoro della GPU (%d, %.0f%%)" % (n, pct),
            "Alcuni frame hanno richiesto molto piu' lavoro alla GPU (esplosioni, effetti, cambi di scena).",
            "Limita gli FPS a un valore che la GPU tiene anche nelle scene pesanti; abbassa gli effetti piu' costosi "
            "(ombre, volumetriche, ray tracing).")
    ok, n, pct = relevant("vsync")
    if ok:
        add(2, "vsync", "Stutter da V-Sync (%d, %.0f%%)" % (n, pct),
            "Con il V-Sync, quando un frame non e' pronto in tempo resta sullo schermo per un refresh in piu': lo vedi "
            "come uno scatto (es. da 16 a 33 ms).", "Usa G-SYNC/FreeSync con il limite FPS 3 sotto la frequenza del "
            "monitor, oppure limita gli FPS a un valore sempre raggiungibile.")
    ok, n, pct = relevant("present")
    pm = (summary.get("present_mode") or "").lower()
    if ok or ("composed" in pm and "independent" not in pm):
        add(2 if ok else 1, "present", "Presentazione dei frame tramite il compositore di Windows",
            ("%d stutter (%.0f%%) avvengono mentre il gioco aspetta che il frame venga mostrato. " % (n, pct) if ok else "")
            + ("Il gioco usa la modalita' '%s': i frame passano dal compositore di Windows (DWM), con piu' latenza e "
               "possibili scatti, invece di andare direttamente allo schermo." % summary.get("present_mode")
               if "composed" in pm else ""),
            "Usa lo schermo intero o attiva 'Ottimizzazioni per giochi in finestra'; con piu' monitor prova la voce "
            "MPO; evita overlay e registrazione in background.")
    ok, n, pct = relevant("system")
    if ok:
        no_busy = not summary.get("has_busy")
        add(2 if pct >= 40 else 1, "pacing", "Stutter senza una causa di sistema misurabile (%d, %.0f%%)" % (n, pct),
            "Durante questi scatti disco, memoria, driver, CPU e processi in background erano nella norma. " +
            ("PresentMon non ha fornito i tempi CPU/GPU di ogni frame per questo gioco, quindi non posso dire se il "
             "picco era della CPU o della GPU. " if no_busy else "") +
            "Di solito sono stutter del motore del gioco (caricamento di zone o compilazione shader) o del frame pacing.",
            vt["shader"] + ". Limita gli FPS a un valore stabile, tieni il gioco aggiornato e prova le ottimizzazioni "
            "di frame pacing qui sotto con il test Prima / Dopo.")
    if summary.get("dropped_pct", 0) >= 5:
        add(1, "present", "Frame scartati (%.0f%%)" % summary["dropped_pct"],
            "Una parte dei frame preparati non e' mai arrivata allo schermo (succede con FPS molto sopra la frequenza "
            "o con alcune modalita' di presentazione).", "Limita gli FPS 3 sotto la frequenza del monitor.")
    return P


def info_lines(summary, health):
    lines = []
    if summary.get("cap_fps"):
        lines.append("Limite FPS rilevato: %d FPS (gioco, driver o V-Sync)." % summary["cap_fps"])
    b = summary.get("bound")
    if b:
        lines.append("Collo di bottiglia (percentuale di FRAME, non utilizzo): il limite era la GPU nel %.0f%% dei frame, "
                     "la CPU nel %.0f%%, il V-Sync o un limite FPS nel %.0f%%." % (b["gpu"], b["cpu"], b["limitato"]))
    else:
        lines.append("PresentMon non ha fornito i tempi CPU/GPU per frame: la diagnosi usa solo i dati di sistema.")
    if summary.get("present_mode"):
        lines.append("Modalita' di presentazione: %s (%.0f%% dei frame)." % (summary["present_mode"],
                                                                              summary.get("present_mode_pct", 0)))
    if "vsync_game" in summary:
        lines.append("V-Sync nel gioco: %s%s." % ("attivo" if summary["vsync_game"] else "disattivato",
                                                 "" if "tearing" not in summary else
                                                 (", tearing consentito" if summary["tearing"] else "")))
    if summary.get("display_latency_ms"):
        lines.append("Latenza dal frame allo schermo: %.1f ms (mediana)." % summary["display_latency_ms"])
    if health.get("lat_p99") is not None:
        lines.append("Latenza di risveglio del sistema: tipica %.2f ms, 99%% %.2f ms, massima %.1f ms." %
                     (health["lat_p50"] or 0, health["lat_p99"], health["lat_max"] or 0))
    if health.get("dpc_p95") is not None:
        lines.append("Tempo CPU in DPC/interrupt (95%%): %.1f%% / %.1f%%." % (health["dpc_p95"], health["isr_p95"] or 0))
    if summary.get("kinds"):
        lines.append("Cause degli stutter: " + ", ".join("%s %.0f%%" % (k[3], k[2]) for k in summary["kinds"]) + ".")
    return lines
