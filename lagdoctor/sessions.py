"""Archivio delle sessioni registrate e confronto prima/dopo."""
import json
import os

FILE = None
EXPERIMENT = None


def init(reports_dir, root):
    global FILE, EXPERIMENT
    os.makedirs(reports_dir, exist_ok=True)
    FILE = os.path.join(reports_dir, "sessioni.json")
    EXPERIMENT = os.path.join(root, "esperimento_in_corso.json")


def _load(path, default):
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except ValueError:
            pass
    return default


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add(summary):
    data = _load(FILE, [])
    summary["id"] = (max((s["id"] for s in data), default=0) + 1)
    data.append(summary)
    _save(FILE, data)
    return summary["id"]


def all_sessions(game=None):
    data = _load(FILE, [])
    if game:
        data = [s for s in data if s["gioco"].lower() == game.lower()]
    return data


def get(sid):
    return next((s for s in _load(FILE, []) if s["id"] == sid), None)


# ------------------------------------------------------------ esperimento prima/dopo

def experiment():
    return _load(EXPERIMENT, None)


def start_experiment(game, before_id, tweak_ids):
    _save(EXPERIMENT, {"gioco": game, "prima": before_id, "modifiche": tweak_ids})


def end_experiment():
    if EXPERIMENT and os.path.exists(EXPERIMENT):
        os.remove(EXPERIMENT)


# ------------------------------------------------------------ confronto

METRICS = [  # chiave, etichetta, "piu' alto e' meglio"
    ("fps_medi", "FPS medi", True),
    ("fps_1low", "1% low", True),
    ("fps_01low", "0.1% low", True),
    ("stutter_min", "Stutter al minuto", False),
    ("ft_p99", "Frame time 99% (ms)", False),
]


def compare(a, b):
    """Confronta sessione a (prima) e b (dopo). Restituisce (righe_tabella, verdetto, spiegazione)."""
    rows = []
    ch = {}
    for key, label, higher in METRICS:
        va, vb = a.get(key), b.get(key)
        if va is None or vb is None:
            continue
        pct = (vb - va) / va * 100 if va else (0 if vb == va else 100)
        better = (vb > va) if higher else (vb < va)
        ch[key] = pct
        rows.append((label, va, vb, pct, better))

    fps, low1 = ch.get("fps_medi", 0), ch.get("fps_1low", 0)
    st = ch.get("stutter_min", 0)
    st_abs = b.get("stutter_min", 0) - a.get("stutter_min", 0)
    much_stutter = a.get("stutter_min", 0) >= 1 or b.get("stutter_min", 0) >= 1

    worse = fps <= -5 or low1 <= -6 or (much_stutter and st >= 30 and st_abs >= 1)
    better = (low1 >= 6 or (much_stutter and st <= -30 and st_abs <= -1)) and fps > -5
    if worse and not better:
        verdict = "PEGGIORATO"
        why = "Dopo le modifiche il gioco va peggio. Ti consiglio di annullarle."
    elif better and not worse:
        verdict = "MIGLIORATO"
        why = "Le modifiche hanno migliorato fluidita' e/o stutter in modo misurabile. Tienile."
    elif better and worse:
        verdict = "MISTO"
        why = "Alcuni valori migliorano e altri peggiorano: ripeti il test per esserne sicuro."
    else:
        verdict = "NESSUNA DIFFERENZA"
        why = ("Le differenze sono entro il margine di errore normale tra due partite (circa 5%). "
               "Le modifiche non portano benefici misurabili in questo gioco: puoi annullarle.")
    return rows, verdict, why


def print_comparison(a, b):
    rows, verdict, why = compare(a, b)
    print("\n  %-22s %12s %12s %10s" % ("", "PRIMA", "DOPO", "Differenza"))
    print("  " + "-" * 60)
    for label, va, vb, pct, better in rows:
        mark = "  meglio" if better and abs(pct) >= 3 else ("  peggio" if not better and abs(pct) >= 3 else "")
        print("  %-22s %12.1f %12.1f %+9.1f%%%s" % (label, va, vb, pct, mark))
    print("\n  RISULTATO: %s\n  %s" % (verdict, why))
    if a.get("durata_s", 0) < 150 or b.get("durata_s", 0) < 150:
        print("  Nota: registrazioni sotto i 3 minuti sono poco affidabili per i confronti.")
    return verdict
