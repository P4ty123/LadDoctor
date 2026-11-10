"""Analisi dei dati: frame time (da PresentMon) + campioni di sistema.

Questo modulo non dipende da Windows, quindi si puo' testare ovunque.
"""
import csv
import statistics

# Istruzioni diverse a seconda della marca della scheda video
VENDOR_TEXT = {
    "nvidia": {
        "cap": "Pannello di controllo NVIDIA > Gestisci impostazioni 3D > Frequenza fotogrammi massima",
        "latency": "Se il gioco ha NVIDIA Reflex, attivalo (On + Boost).",
        "sync": "G-SYNC",
        "shader": "Pannello di controllo NVIDIA > Gestisci impostazioni 3D > 'Dimensione cache Shader' = "
                  "10 GB o Illimitata",
        "shader_short": "cache shader NVIDIA grande",
    },
    "amd": {
        "cap": "AMD Software Adrenalin > Gaming > Grafica > 'Controllo obiettivo frequenza fotogrammi' "
               "(Frame Rate Target Control)",
        "latency": "Attiva 'Radeon Anti-Lag' in Adrenalin (o AMD Anti-Lag 2 nel gioco se presente). Non usare "
                   "insieme Radeon Chill e il limite FPS.",
        "sync": "FreeSync",
        "shader": "AMD Software Adrenalin > Gaming > Grafica > Avanzate > 'Cache shader' = Ottimizzata AMD "
                  "(non usare 'Ripristina cache shader' se non serve: la svuota)",
        "shader_short": "cache shader di Adrenalin attiva",
    },
    "intel": {
        "cap": "il limite FPS del gioco (o RivaTuner Statistics Server); Intel Graphics Software non ha un limite "
               "globale affidabile su tutte le schede",
        "latency": "Se il gioco ha Intel XeLL (bassa latenza, insieme a XeSS 2), attivalo.",
        "sync": "Adaptive Sync (VRR)",
        "shader": "Lascia attiva la cache shader del driver Intel e aggiorna il driver da intel.com: sulle Intel "
                  "molti stutter da shader sono stati corretti dai driver recenti",
        "shader_short": "driver Intel aggiornato",
    },
    "altro": {
        "cap": "il limite FPS del gioco (o RivaTuner Statistics Server)",
        "latency": "",
        "sync": "G-SYNC/FreeSync (VRR)",
        "shader": "Lascia attiva la cache shader nel pannello del driver video",
        "shader_short": "cache shader del driver attiva",
    },
}


# Colonne possibili del frame time, nelle varie versioni di PresentMon
FRAMETIME_COLUMNS = ["frametime", "msbetweenappstart", "msbetweenpresents"]


def load_frametimes(csv_path, process_name=None):
    """Legge il CSV di PresentMon e restituisce una lista di frame time in ms."""
    frametimes = []
    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        header = None
        for row in reader:
            if not row:
                continue
            if header is None:
                header = [h.strip().lower() for h in row]
                col = next((header.index(c) for c in FRAMETIME_COLUMNS if c in header), None)
                if col is None:
                    raise ValueError("Formato CSV di PresentMon non riconosciuto: " + ",".join(row[:10]))
                app_col = header.index("application") if "application" in header else None
                continue
            if len(row) <= col:
                continue
            if process_name and app_col is not None and row[app_col].lower() != process_name.lower():
                continue
            try:
                v = float(row[col])
            except ValueError:
                continue
            if 0 < v < 5000:
                frametimes.append(v)
    return frametimes


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def detect_stutters(frametimes, window=30):
    """Trova gli stutter: frame molto piu' lunghi di quelli appena precedenti.

    Uno stutter e' un frame che dura almeno 2x la mediana dei frame recenti
    e almeno 8 ms in piu' (cosi' a 300 FPS non contiamo variazioni invisibili).
    Restituisce lista di (indice_frame, tempo_s, durata_ms, mediana_ms).
    """
    stutters = []
    t = 0.0
    recent = []
    for i, ft in enumerate(frametimes):
        t += ft / 1000.0
        if len(recent) >= 10:
            med = statistics.median(recent)
            if ft >= 2.0 * med and ft - med >= 8.0:
                stutters.append((i, t, ft, med))
        recent.append(ft)
        if len(recent) > window:
            recent.pop(0)
    return stutters


def frame_stats(frametimes):
    s = sorted(frametimes)
    total_s = sum(frametimes) / 1000.0
    n = len(frametimes)
    avg_ft = total_s * 1000.0 / n
    # 1% / 0.1% low = FPS medio del peggior 1% / 0.1% dei frame
    def low(pct):
        k = max(1, int(n * pct / 100.0))
        worst = s[-k:]
        return 1000.0 / (sum(worst) / len(worst))
    return {
        "frames": n,
        "durata_s": total_s,
        "fps_medi": 1000.0 / avg_ft,
        "fps_1low": low(1),
        "fps_01low": low(0.1),
        "ft_mediana": percentile(s, 50),
        "ft_p95": percentile(s, 95),
        "ft_p99": percentile(s, 99),
        "ft_max": s[-1],
        # 1% / 0,1% low "a percentile" (metodo di PresentMon e altri tool): il frame time al 99 / 99,9 percentile
        "fps_p1": 1000.0 / percentile(s, 99),
        "fps_p01": 1000.0 / percentile(s, 99.9),
        "long_100": sum(1 for x in frametimes if x >= 100),
        "long_250": sum(1 for x in frametimes if x >= 250),
    }


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def correlate(samples, stutters, t_offset=0.0, margin=1.0):
    """Divide i campioni di sistema in 'durante stutter' e 'normali'.

    samples: lista di dict con chiave 't' (secondi dall'inizio cattura).
    """
    times = [s[1] + t_offset for s in stutters]
    during, normal = [], []
    j = 0
    for smp in samples:
        hit = False
        for st in times:
            if abs(st - smp["t"]) <= margin:
                hit = True
                break
        (during if hit else normal).append(smp)
    return during, normal


def diagnose(stats, stutters, samples, sysinfo, game_exe, refresh_hz=None, deep=False):
    """Applica le regole e restituisce (lista_problemi, lista_info).

    Ogni problema: dict(gravita, titolo, spiegazione, soluzione, auto_fix).
    gravita: 3 = alta, 2 = media, 1 = bassa
    """
    problems = []
    info = []
    vendor = ((sysinfo or {}).get("gpu") or {}).get("vendor")
    vt = VENDOR_TEXT.get(vendor, VENDOR_TEXT["altro"])
    dur_min = max(stats["durata_s"] / 60.0, 0.01)
    n_st = len(stutters)
    big = [s for s in stutters if s[2] >= 50]
    per_min = n_st / dur_min

    if per_min < 2 and not big:
        info.append("Frame pacing buono: %.1f stutter al minuto." % per_min)
    else:
        info.append("%d stutter in %.1f minuti (%.1f/min), di cui %d gravi (>50 ms)."
                    % (n_st, dur_min, per_min, len(big)))

    during, normal = correlate(samples, stutters)
    has_corr = len(during) >= 2 and len(normal) >= 2
    found_cause = False

    def avg(group, key):
        return _mean([s.get(key) for s in group])

    # --- VRAM piena ---
    vram_pct = [s["vram_used"] / s["vram_total"] * 100 for s in samples
                if s.get("vram_used") is not None and s.get("vram_total")]
    if vram_pct and max(vram_pct) >= 93:
        found_cause = True
        problems.append(dict(
            gravita=3, cause="vram", titolo="Memoria della scheda video (VRAM) quasi piena",
            spiegazione="La VRAM ha raggiunto il %.0f%%. Quando si riempie, la GPU deve spostare texture "
                        "nella RAM di sistema, cosa che provoca scatti evidenti." % max(vram_pct),
            soluzione="Nel gioco abbassa la qualita' delle TEXTURE di un livello (e' l'impostazione che "
                      "usa piu' VRAM). Se usi Frame Generation o Path/Ray Tracing, anche quelli consumano "
                      "VRAM. Chiudi browser e app che usano la GPU (Chrome, Discord con accelerazione hw).",
            auto_fix=None))

    # --- RAM piena ---
    ram = [s["ram_pct"] for s in samples if s.get("ram_pct") is not None]
    if ram and max(ram) >= 88:
        found_cause = True
        problems.append(dict(
            gravita=3, cause="ram", titolo="RAM di sistema quasi piena",
            spiegazione="La RAM e' arrivata al %.0f%%: Windows inizia a usare il disco come memoria." % max(ram),
            soluzione="Chiudi i programmi in background (browser con tante schede, launcher, ecc.).",
            auto_fix=None))

    if has_corr and not deep:  # con la diagnosi precisa queste correlazioni sono fatte stutter per stutter
        # --- Disco (streaming asset) ---
        d_st, d_no = avg(during, "disk_read_mb"), avg(normal, "disk_read_mb")
        if d_st is not None and d_no is not None and d_st > 30 and d_st > 2.5 * (d_no + 1):
            found_cause = True
            problems.append(dict(
                gravita=2, cause="disk", titolo="Gli stutter coincidono con letture dal disco",
                spiegazione="Durante gli scatti il disco legge in media %.0f MB/s contro %.0f MB/s normalmente: "
                            "il gioco sta caricando dati mentre giochi (streaming)." % (d_st, d_no),
                soluzione="Assicurati che il gioco sia installato su un SSD NVMe (non HDD, non SSD quasi pieno). "
                          "Lascia almeno il 15% di spazio libero sul disco. Se e' gia' su NVMe, e' un limite "
                          "del motore del gioco: un limite FPS aiuta a mascherarlo.",
                auto_fix=None))

        # --- Processi in background che si attivano durante gli stutter ---
        def bg_counts(group):
            c = {}
            for s in group:
                for name, cpu in s.get("bg_top", []):
                    if cpu >= 3.0:
                        c[name] = c.get(name, 0) + 1
            return c
        c_st, c_no = bg_counts(during), bg_counts(normal)
        culprits = []
        for name, cnt in c_st.items():
            frac_st = cnt / len(during)
            frac_no = c_no.get(name, 0) / len(normal)
            if frac_st >= 0.3 and frac_st >= 2 * frac_no + 0.1:
                culprits.append(name)
        if culprits:
            found_cause = True
            problems.append(dict(
                gravita=2, cause="background", titolo="Programmi in background attivi durante gli stutter",
                spiegazione="Questi processi usano CPU proprio quando il gioco scatta: " + ", ".join(culprits),
                soluzione="Chiudili prima di giocare o disattiva il loro avvio automatico "
                          "(Gestione attivita' > App di avvio).",
                auto_fix=("close_processes", culprits)))

        # --- Picchi CPU sul gioco (shader / caricamenti) ---
        g_st, g_no = avg(during, "game_cpu"), avg(normal, "game_cpu")
        if g_st is not None and g_no is not None and g_st > g_no * 1.4 and g_st - g_no > 5:
            info.append("Durante gli stutter il gioco usa molta piu' CPU (%.0f%% vs %.0f%%): tipico della "
                        "compilazione shader o del caricamento di nuove zone." % (g_st, g_no))

    # --- Throttling GPU ---
    temps = [s["gpu_temp"] for s in samples if s.get("gpu_temp") is not None]
    hots = [s["gpu_hotspot"] for s in samples if s.get("gpu_hotspot") is not None]
    with_thr = [s for s in samples if "thr_thermal" in s]
    thermal = [s for s in with_thr if s["thr_thermal"]]
    power = [s for s in with_thr if s.get("thr_power")]

    if temps:
        msg = "Temperatura GPU: media %.0f C, massima %.0f C" % (sum(temps) / len(temps), max(temps))
        if hots:
            msg += "; hotspot (punto piu' caldo) massimo %.0f C" % max(hots)
        info.append(msg + ".")
    else:
        info.append("Temperatura GPU non disponibile per questa scheda video.")

    thermal_frac = len(thermal) / len(with_thr) if with_thr else 0
    if thermal_frac > 0.05:
        found_cause = True
        extra = ""
        if has_corr:
            d_thr = sum(1 for s in during if s.get("thr_thermal")) / len(during)
            if d_thr > thermal_frac + 0.15:
                extra = " Durante gli stutter la GPU era in throttling nel %.0f%% dei casi: e' una delle " \
                        "cause degli scatti." % (d_thr * 100)
        problems.append(dict(
            gravita=3 if thermal_frac > 0.25 else 2,
            cause="throttle", titolo="La GPU si surriscalda e abbassa le frequenze (throttling termico)",
            spiegazione="Per il %.0f%% del tempo la scheda video ha rallentato per il calore%s.%s"
                        % (thermal_frac * 100, " (temperatura massima %.0f C%s)" % (
                            max(temps), ", hotspot %.0f C" % max(hots) if hots else "") if temps else "", extra),
            soluzione="1) Pulisci la polvere da ventole e dissipatore della scheda e dai filtri del case. "
                      "2) Controlla che le ventole del case siano messe bene (davanti/sotto che aspirano, dietro/"
                      "sopra che espellono). 3) Se hai fatto overclock, togli l'overclock. 4) Un leggero "
                      "undervolt riduce molto le temperature. 5) Se la scheda ha qualche anno e l'hotspot supera "
                      "i 100 C, la pasta termica potrebbe essere da cambiare (meglio farlo fare a un tecnico).",
            auto_fix=None))
    elif temps and max(temps) >= 85:
        problems.append(dict(
            gravita=1, cause="throttle", titolo="GPU molto calda",
            spiegazione="La temperatura e' arrivata a %.0f C. Non c'e' ancora throttling evidente, ma sei vicino "
                        "al limite." % max(temps),
            soluzione="Pulisci la polvere e controlla il flusso d'aria del case.",
            auto_fix=None))
    elif hots and max(hots) >= 100:
        problems.append(dict(
            gravita=1, cause="throttle", titolo="Hotspot della GPU molto alto",
            spiegazione="Il punto piu' caldo della GPU e' arrivato a %.0f C (limite circa 110 C)." % max(hots),
            soluzione="Pulisci la polvere. Se la differenza tra hotspot e temperatura normale supera i 25-30 C, "
                      "la pasta termica potrebbe essere da sostituire.",
            auto_fix=None))

    if with_thr and len(power) / len(with_thr) > 0.5:
        info.append("La GPU lavora al limite di potenza per il %.0f%% del tempo: e' normale quando e' al 100%% "
                    "e non causa scatti da solo." % (len(power) / len(with_thr) * 100))

    # --- GPU al 99% senza limite FPS ---
    gpu_util = [s["gpu_util"] for s in samples if s.get("gpu_util") is not None]
    if gpu_util and per_min >= 2:
        avg_util = sum(gpu_util) / len(gpu_util)
        if avg_util >= 95:
            problems.append(dict(
                gravita=2, cause="gpu_bound", titolo="GPU sempre al 100%: frame pacing instabile",
                spiegazione="La GPU e' in media al %.0f%%. Quando e' completamente saturata, ogni piccola "
                            "variazione della scena diventa uno scatto e aumenta l'input lag." % avg_util,
                soluzione="Metti un limite FPS: %s. Imposta un valore che il gioco tiene quasi sempre "
                          "(es. %d FPS). %s"
                          % (vt["cap"], max(30, int(min(1000.0 / stats['ft_p95'] * 0.95, (refresh_hz or 1000) - 3))),
                             vt["latency"]),
                auto_fix=None))

    # --- FPS sopra il refresh del monitor ---
    if refresh_hz and stats["fps_medi"] > refresh_hz * 1.15:
        problems.append(dict(
            gravita=1, cause="fps_over_refresh", titolo="FPS molto sopra la frequenza del monitor",
            spiegazione="Fai in media %.0f FPS ma il monitor mostra al massimo %d Hz: i frame in piu' "
                        "non si vedono e rendono il ritmo irregolare." % (stats["fps_medi"], refresh_hz),
            soluzione="Limita gli FPS a %d (3 sotto il refresh) da %s, e attiva %s se il "
                      "monitor lo supporta." % (refresh_hz - 3, vt["cap"], vt["sync"]),
            auto_fix=None))

    # --- Andamento: shader compilation (stutter concentrati all'inizio) ---
    if n_st >= 6 and not deep:
        third = stats["durata_s"] / 3
        first = sum(1 for s in stutters if s[1] < third)
        last = sum(1 for s in stutters if s[1] >= 2 * third)
        if first >= 2.5 * max(last, 1):
            problems.append(dict(
                gravita=2, cause="shader", titolo="Stutter concentrati all'inizio (compilazione shader)",
                spiegazione="Nel primo terzo della sessione ci sono %d stutter, nell'ultimo %d. Il gioco "
                            "compila gli shader la prima volta che vede effetti/zone nuove." % (first, last),
                soluzione="1) " + vt["shader"] + ". 2) Se il gioco ha l'opzione 'precompila shader' "
                          "all'avvio, lasciala finire. 3) Dopo un aggiornamento driver la cache si svuota: "
                          "e' normale che le prime sessioni scattino di piu'.",
                auto_fix=None))

    # --- Stutter senza causa di sistema ---
    if per_min >= 2 and not found_cause and not deep:
        problems.append(dict(
            gravita=1, cause="pacing", titolo="Stutter non causati dal tuo PC (probabile motore del gioco)",
            spiegazione="Il sistema era tranquillo quando il gioco scattava (RAM, VRAM, disco e background "
                        "nella norma). Quindi e' molto probabile che siano 'traversal stutter' "
                        "o compilazione shader del gioco stesso, frequenti nei giochi Unreal Engine 4/5.",
            soluzione="Si puo' ridurre ma non eliminare: limite FPS stabile, " + vt["shader_short"] + ", "
                      "prova DX11 al posto di DX12 se il gioco lo permette, e tieni il gioco aggiornato.",
            auto_fix=None))

    problems.sort(key=lambda p: -p["gravita"])
    return problems, info


def analyze_session(csv_path, game_name, samples, sysinfo, refresh_hz=None, driver_lookup=None, drive=None):
    """Analisi completa di una registrazione: statistiche, stutter classificati uno per uno, problemi e info."""
    from . import stutter as ST
    all_frames = ST.load_frames(csv_path, game_name)
    dur = all_frames[-1]["t"] if all_frames else 0
    ex = ST.exclusions(samples, dur)
    frames = [f for f in all_frames if not ST.excluded(f["t"], ex)]
    excluded_s = sum(f["ft"] for f in all_frames if ST.excluded(f["t"], ex)) / 1000.0
    focus_lost = len(ex) - 1
    frametimes = [f["ft"] for f in frames]
    if len(frametimes) < 200:
        return {"frames": frames, "frametimes": frametimes, "too_few": True, "total_frames": len(all_frames),
                "excluded_s": excluded_s}
    stats = frame_stats(frametimes)
    detail, summary = ST.classify(frames, samples, refresh_hz)
    health = ST.system_health(samples)
    legacy = [(x["i"], x["t"], x["ft"], x["med"]) for x in detail]
    vendor = ((sysinfo or {}).get("gpu") or {}).get("vendor")
    vt = VENDOR_TEXT.get(vendor, VENDOR_TEXT["altro"])
    drivers = None
    if driver_lookup and (any(x["kind"] == "dpc" for x in detail) or (health.get("lat_p99") or 0) >= 2.0):
        try:
            drivers = driver_lookup()
        except Exception:
            drivers = None
    deep_probs = ST.problems(detail, summary, health, stats, vt, refresh_hz, drivers, drive)
    base_probs, info = diagnose(stats, legacy, samples, sysinfo, game_name, refresh_hz, deep=True)
    # niente doppioni: la versione precisa vince su quella generica della stessa causa
    deep_causes = {p["cause"] for p in deep_probs}
    if summary.get("cap_fps"):  # un limite FPS c'e' gia': niente consigli di metterlo
        deep_causes |= {"gpu_bound", "fps_over_refresh"}
    probs = deep_probs + [p for p in base_probs if p.get("cause") not in deep_causes]
    probs.sort(key=lambda p: -p["gravita"])
    info = info + ST.info_lines(summary, health)
    # blocchi lunghi (>= 100 ms) con il minuto, per capire cosa succedeva (salvataggio, mappa, caricamento...)
    longs = [{"t": round(f["t"], 1), "ft": round(f["ft"], 1)} for f in frames if f["ft"] >= 100]
    summary["long_frames"] = sorted(longs, key=lambda x: -x["ft"])[:20]
    summary["long_share_low"] = None
    if stats["long_100"]:
        k = max(1, int(len(frametimes) * 0.001))
        worst = sorted(frametimes)[-k:]
        summary["long_share_low"] = sum(1 for x in worst if x >= 100) / len(worst) * 100
    util = [x.get("gpu_util") for x in samples if x.get("gpu_util") is not None and not ST.excluded(x["t"], ex)]
    if util:
        summary["gpu_util_avg"] = sum(util) / len(util)
        summary["gpu_util_p90"] = sorted(util)[int(len(util) * 0.9)]
        info.append("Utilizzo medio della GPU durante il gioco: %.0f%% (90%% del tempo sotto il %.0f%%)."
                    % (summary["gpu_util_avg"], summary["gpu_util_p90"]))
    info.append("1%% low: %.0f FPS come media dei frame peggiori, %.0f FPS a percentile; 0,1%% low: %.0f / %.0f FPS. "
                "Se i due valori sono molto diversi, i bassi dipendono da pochi blocchi lunghi, non da un gioco "
                "irregolare." % (stats["fps_1low"], stats["fps_p1"], stats["fps_01low"], stats["fps_p01"]))
    info.insert(0, "Analizzati %.0f secondi di gioco. Esclusi %.0f secondi: i primi 5 secondi%s (in quei momenti Windows "
                "e il gioco rallentano apposta, non sono stutter)." % (stats["durata_s"], excluded_s,
                (" e %d volte in cui il gioco non era la finestra attiva (Alt+Tab), piu' 3 secondi dopo il ritorno"
                 % focus_lost) if focus_lost else ""))
    return {"frames": frames, "frametimes": frametimes, "stats": stats, "stutters": legacy, "detail": detail,
            "summary": summary, "health": health, "problems": probs, "info": info, "too_few": False}
