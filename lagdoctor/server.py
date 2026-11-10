"""LagDoctor - interfaccia grafica.

Un piccolo server locale (solo 127.0.0.1, protetto da un codice casuale) serve l'interfaccia
in lagdoctor/ui e risponde alle sue richieste. La finestra si apre con Edge in modalita' app.
"""
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import psutil

from . import analysis, capture, checks, factors, fixes, gamemode, gpu_driver, paths, report, scan, sessions, tweak_docs, tweaks
from . import __version__, settings, tray, updater
from . import gpu as gpumod
from .main import BACKUP, GAME_HINTS, NOT_GAMES, REPORTS, ROOT, TOOLS

UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
TOKEN = secrets.token_urlsafe(24)
MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json",
        ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}


def log_error():
    try:
        with open(os.path.join(ROOT, "errore.txt"), "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
    except Exception:
        pass


# ======================================================================= lavori in background

class Job:
    def __init__(self, kind):
        self.id = secrets.token_hex(6)
        self.kind = kind
        self.status = "running"   # running / done / error
        self.messages = []
        self.live = None
        self.result = None
        self.error = None
        self.stop = threading.Event()
        self.started = time.time()

    def msg(self, text):
        self.messages.append(str(text).strip())

    def as_dict(self):
        return {"id": self.id, "kind": self.kind, "status": self.status, "messages": self.messages[-30:],
                "live": self.live, "result": self.result, "error": self.error}


JOBS = {}
STATE = {"sysinfo": None, "sys_problems": [], "statuses": {}, "restore_done": False, "sensor": None,
         "busy": None}
LOCK = threading.Lock()


def start_job(kind, fn, *args):
    job = Job(kind)
    JOBS[job.id] = job

    def run():
        try:
            job.result = fn(job, *args)
            job.status = "done"
        except Exception as e:
            log_error()
            job.error = str(e) or e.__class__.__name__
            job.status = "error"
        finally:
            if STATE["busy"] == job.id:
                STATE["busy"] = None
    threading.Thread(target=run, daemon=True).start()
    return job


# ======================================================================= dati per l'interfaccia

def _reboot_file():
    return os.path.join(ROOT, "riavvio_necessario.json")


def note_reboot(ids):
    """Ricorda le modifiche che richiedono il riavvio, finche' Windows non viene riavviato."""
    data = {"boot": psutil.boot_time(), "ids": []}
    try:
        with open(_reboot_file(), encoding="utf-8") as f:
            old = json.load(f)
        if abs(old.get("boot", 0) - data["boot"]) < 5:
            data["ids"] = old.get("ids", [])
    except (OSError, ValueError):
        pass
    data["ids"] = sorted(set(data["ids"]) | set(ids))
    with open(_reboot_file(), "w", encoding="utf-8") as f:
        json.dump(data, f)


def reboot_pending():
    try:
        with open(_reboot_file(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return []
    if abs(d.get("boot", 0) - psutil.boot_time()) >= 5:  # Windows e' stato riavviato
        try:
            os.remove(_reboot_file())
        except OSError:
            pass
        return []
    return [tweaks.BY_ID[i].name for i in d.get("ids", []) if i in tweaks.BY_ID]


def vendor():
    return (((STATE["sysinfo"] or {}).get("gpu")) or {}).get("vendor")


def driver_report(fresh=True):
    if fresh:
        gpu_driver.invalidate()
    try:
        return gpu_driver.read(vendor(), (STATE["sysinfo"] or {}).get("refresh_hz"))
    except Exception as e:
        log_error()
        return {"ok": False, "vendor": vendor(), "error": str(e)}


def tweak_json(t, st, applied, sysinfo):
    return {"id": t.id, "name": t.name, "cat": t.cat, "desc": t.desc, "efficacy": t.efficacy, "risk": t.risk,
            "risk_label": tweaks.RISK[t.risk], "reboot": t.reboot, "warning": t.warning, "kind": t.kind,
            "harm_if_off": t.harm_if_off, "group": t.group, "source": t.source,
            "recommended": t.recommended(sysinfo), "status": st.get(t.id), "applied": t.id in applied,
            "needs_path": isinstance(t, tweaks.DefenderExclusionTweak), "doc": tweak_docs.get(t.id),
            "note": getattr(t, "note", None)}


def catalog_json():
    st = STATE["statuses"]
    applied = tweaks.applied_by_us()
    return {"tweaks": [tweak_json(t, st, applied, STATE["sysinfo"]) for t in tweaks.for_vendor(vendor())],
            "myths": [{"name": n, "why": w} for n, w in tweaks.NOT_TOGGLEABLE],
            "manual": [{"name": n, "how": h, "source": src} for n, h, src in tweaks.MANUAL_TIPS],
            "checked": bool(st)}


STATUS_TIMEOUT = 25  # secondi massimi per una voce: se Windows non risponde la segno "non verificabile"


def _status_of(t):
    t0 = time.time()
    try:
        st = t.status()
    except Exception:
        st = None
    return st, time.time() - t0


def refresh_statuses(job, ids=None):
    """Controlla lo stato delle voci, 6 alla volta. Una voce bloccata non blocca le altre ne' l'interfaccia."""
    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    todo = [tweaks.BY_ID[i] for i in ids] if ids else tweaks.for_vendor(vendor())
    pool = ThreadPoolExecutor(max_workers=6)
    started = {}
    pending = set()
    for t in todo:
        f = pool.submit(_status_of, t)
        started[f] = (t, time.time())
        pending.add(f)
    done_n, slow = 0, []
    while pending:
        finished, pending = wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)
        for f in finished:
            t, _t0 = started[f]
            st, dt = f.result()
            STATE["statuses"][t.id] = st
            done_n += 1
            if dt > 3:
                slow.append("%s %.1fs" % (t.id, dt))
        now = time.time()
        for f in list(pending):  # una voce che non risponde: la lascio "non verificabile" e vado avanti
            t, t0 = started[f]
            if f.running() and getattr(f, "_ld_t", None) is None:
                f._ld_t = now  # quando ha iniziato davvero (le altre aspettano un posto libero)
            if getattr(f, "_ld_t", None) and now - f._ld_t > STATUS_TIMEOUT:
                STATE["statuses"][t.id] = None
                slow.append("%s BLOCCATA" % t.id)
                pending.discard(f)
                done_n += 1
        if job:
            job.msg("Controllo impostazioni: %d/%d" % (done_n, len(todo)))
    pool.shutdown(wait=False)
    if slow:
        try:
            with open(paths.data("avvio_lento.log"), "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + ", ".join(slow) + "\n")
        except OSError:
            pass


def job_update(job):
    job.msg("Controllo l'ultima versione su GitHub...")
    info = updater.check(force=True)
    if info.get("error"):
        raise RuntimeError(info["error"])
    if not info.get("available"):
        return {"msg": "Hai gia' l'ultima versione (%s)." % info["current"]}
    job.msg("Scarico LagDoctor %s..." % info["latest"])
    last = [-10]

    def prog(pct):
        if pct - last[0] >= 2:
            last[0] = pct
            job.msg("Scarico LagDoctor %s... %d%%" % (info["latest"], pct))
    path = updater.download(info, prog)
    job.msg("File controllato: integro. Chiudo LagDoctor e installo: si riapre da solo tra circa un minuto...")
    # PRIMA chiudo la finestra: l'installatore, appena parte, chiude subito il programma (prima non c'era tempo)
    time.sleep(2)  # la pagina fa in tempo a mostrare il messaggio
    _close_windows()
    updater.install(path)
    threading.Thread(target=lambda: (time.sleep(1), _shutdown()), daemon=True).start()
    return {"msg": "Installazione avviata", "restarting": True}


def _gm_quick():
    try:
        return gamemode.quick_status()
    except Exception:
        return None


def gamemode_json(scan=False):
    c = gamemode.load_config()
    added = None
    if scan or not c["games"]:
        added = gamemode.refresh_games(c)
        gamemode.save_config(c)
    try:
        cpu = gamemode.cputopo.decide()
    except Exception:
        cpu = None
    return {"config": c, "status": gamemode.status(), "added": added, "cpu": cpu,
            "options": [{"id": k, "default": d, "name": n, "what": w, "risk": r} for k, d, n, w, r in gamemode.OPTIONS],
            "priorities": [{"id": k, "name": v[0]} for k, v in gamemode.PRIORITY.items()]}


def gamemode_post(b):
    act = b.get("action")
    c = gamemode.load_config()
    if act == "enable":
        gamemode.enable()
    elif act == "disable":
        gamemode.disable()
    elif act == "game":
        for g in c["games"]:
            if g["id"] == b.get("id"):
                if "on" in b:
                    g["on"] = bool(b["on"])
                if b.get("priority") in gamemode.PRIORITY:
                    g["priority"] = b["priority"]
        gamemode.save_config(c)
    elif act == "opt":
        if b.get("id") in gamemode.DEFAULT_OPTS:
            c["opts"][b["id"]] = bool(b.get("value"))
            gamemode.save_config(c)
    elif act == "add":
        exe = b.get("exe") or ""
        if not exe:
            raise ValueError("percorso del gioco mancante")
        g = gamemode.G.manual(exe)
        g.update(on=True, priority="high")
        c["games"] = [x for x in c["games"] if x["id"] != g["id"]] + [g]
        c["removed"] = [i for i in c["removed"] if i != g["id"]]
        c["games"].sort(key=lambda x: x["name"].lower())
        gamemode.save_config(c)
    elif act == "remove":
        c["games"] = [x for x in c["games"] if x["id"] != b.get("id")]
        if b.get("id") not in c["removed"]:
            c["removed"].append(b.get("id"))
        gamemode.save_config(c)
    else:
        raise ValueError("azione sconosciuta")
    return gamemode_json()


def game_candidates():
    cands = []
    for p in psutil.process_iter(["pid", "name", "exe", "memory_info"]):
        name = (p.info["name"] or "").lower()
        if not name or name in NOT_GAMES or name in capture.IGNORE_PROCS:
            continue
        mem = p.info["memory_info"].rss / 2**20 if p.info["memory_info"] else 0
        exe = (p.info["exe"] or "").lower()
        likely = any(h in exe for h in GAME_HINTS)
        if mem > 300 or (likely and mem > 100):
            cands.append({"pid": p.info["pid"], "name": p.info["name"], "mem": round(mem), "likely": likely,
                          "exe": p.info["exe"]})
    cands.sort(key=lambda c: (not c["likely"], -c["mem"]))
    return cands[:15]


# ======================================================================= lavori

def job_boot(job, hw=None):
    job.msg("Leggo le impostazioni del sistema..." if hw else "Primo avvio: leggo l'hardware del PC...")
    info, probs = checks.run_all(hw)
    STATE["sysinfo"] = info
    STATE["hw_cached"] = True  # da qui l'interfaccia puo' aprirsi: il resto continua in background
    tweaks.CONTEXT.update(refresh_hz=info.get("refresh_hz"), vendor=(info.get("gpu") or {}).get("vendor"))
    job.msg("Leggo le impostazioni del driver video...")
    drv = driver_report()
    if drv.get("ok"):
        probs = probs + drv.get("problems", [])
    STATE["sys_problems"] = probs
    job.msg("Controllo lo stato delle impostazioni...")
    refresh_statuses(job)
    return {"sysinfo": info, "problems": probs}


def job_scan(job):
    data = scan.collect(STATE["sysinfo"], progress=job.msg)
    for t in data.get("tweaks", []):
        STATE["statuses"][t["id"]] = t["stato"]
    probs = scan.problems(data, STATE["sysinfo"])
    job.msg("Leggo le impostazioni del driver video...")
    drv = driver_report()
    if drv.get("ok"):
        probs += drv.get("problems", [])
    os.makedirs(REPORTS, exist_ok=True)
    name = "scansione-%s.html" % time.strftime("%Y%m%d-%H%M%S")
    scan.build_report(os.path.join(REPORTS, name), data, probs)
    g = data.get("gpu_main") or {}
    cpu = (scan._list(data.get("cpu")) or [{}])[0]
    os_ = data.get("os") or {}
    summary = {
        "cpu": cpu.get("Name"), "gpu": g.get("name"), "vram": g.get("vram_mb"),
        "ram": STATE["sysinfo"].get("ram") if STATE["sysinfo"] else None,
        "windows": "%s %s (build %s)" % (os_.get("caption", ""), os_.get("display", ""), os_.get("build", "")),
        "displays": data.get("displays", []), "disks": scan._list(data.get("disks")),
        "net": scan._list(data.get("net")), "errors": {k: data.get(k) for k in ("ev_whea", "ev_tdr", "ev_kp41", "ev_bsod")},
        "apps": len(scan._list(data.get("apps"))), "startup": len(scan._list(data.get("startup"))),
        "services": data.get("services_running"), "uptime_h": data.get("uptime_h"),
    }
    return {"problems": probs, "summary": summary, "report": name}


def job_apply(job, ids, path):
    if not STATE["restore_done"]:
        job.msg("Creo un punto di ripristino di Windows (puo' richiedere 1-2 minuti)...")
        ok, msg = tweaks.create_restore_point()
        job.msg("Punto di ripristino creato." if ok else "Punto di ripristino NON creato (%s). Ogni modifica ha "
                                                          "comunque il suo backup." % msg[-120:])
        STATE["restore_done"] = True
    results = []
    for tid in ids:
        t = tweaks.BY_ID[tid]
        if isinstance(t, tweaks.DefenderExclusionTweak):
            t.path = path
        try:
            r = tweaks.apply_one(tid)
            results.append({"id": tid, "name": t.name, "ok": True, "msg": r})
        except Exception as e:
            results.append({"id": tid, "name": t.name, "ok": False, "msg": str(e)})
        job.msg("%s: %s" % (t.name, results[-1]["msg"]))
    refresh_statuses(None, [t.id for t in tweaks.CATALOG if t.group in {tweaks.BY_ID[i].group for i in ids}
                            and t.group] + list(ids))
    rb = [r["id"] for r in results if r["ok"] and tweaks.BY_ID[r["id"]].reboot]
    if rb:
        note_reboot(rb)
    return {"results": results, "reboot": bool(rb)}


def job_revert(job, ids):
    results = []
    for tid in ids:
        try:
            results.append({"id": tid, "name": tweaks.BY_ID[tid].name, "ok": True, "msg": tweaks.revert_one(tid)})
            if tweaks.BY_ID[tid].reboot:
                note_reboot([tid])
        except Exception as e:
            results.append({"id": tid, "name": tweaks.BY_ID[tid].name, "ok": False, "msg": str(e)})
    refresh_statuses(None, ids)
    return {"results": results}


def job_restore_all(job):
    msgs = tweaks.revert_all()
    msgs.append(fixes.undo_all(BACKUP))
    sessions.end_experiment()
    for m in msgs:
        job.msg(m)
    refresh_statuses(job)
    return {"messages": msgs}


def job_record(job, pid, seconds, label):
    game = psutil.Process(pid)
    gname = game.name()
    exe = ""
    try:
        exe = game.exe()
    except psutil.Error:
        pass
    drive, drive_problems = checks.check_game_drive(exe or "C:\\")
    job.msg("Preparo PresentMon...")
    pm = capture.ensure_presentmon(TOOLS, progress=job.msg, stop=job.stop)
    os.makedirs(REPORTS, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = gname.replace(".exe", "")
    csv_path = os.path.join(REPORTS, "frame-%s-%s.csv" % (base, stamp))
    job.msg("Registrazione in corso: torna nel gioco!")

    def prog(d):
        job.live = d
    samples = capture.record(pm, game, csv_path, seconds, STATE["sysinfo"].get("gpu"), stop_event=job.stop,
                             on_progress=prog)
    try:  # dati di sistema salvati accanto ai frame: servono per rianalizzare o inviare la sessione
        with open(csv_path.replace(".csv", "-sistema.json"), "w", encoding="utf-8") as f:
            json.dump({"samples": samples, "sysinfo": STATE["sysinfo"], "drive": drive}, f, default=str)
    except OSError:
        pass
    job.msg("Analizzo ogni frame e classifico gli stutter uno per uno...")
    res = analysis.analyze_session(csv_path, gname, samples, STATE["sysinfo"], STATE["sysinfo"].get("refresh_hz"),
                                   driver_lookup=checks.suspect_drivers, drive=drive)
    frametimes = res["frametimes"]
    if res["too_few"]:
        if res.get("total_frames", 0) >= 200:
            raise RuntimeError("Registrazione troppo breve: dopo aver escluso i primi secondi e i momenti fuori dal "
                               "gioco (%.0f s) restano solo %d frame. Registra almeno 30 secondi giocando."
                               % (res.get("excluded_s", 0), len(frametimes)))
        raise RuntimeError("Troppi pochi frame registrati (%d). Il gioco era aperto e in partita? Alcuni giochi "
                           "con anti-cheat bloccano la misura." % len(frametimes))
    stats, stutters, info = res["stats"], res["stutters"], res["info"]
    all_p = sorted(res["problems"] + drive_problems, key=lambda p: -p["gravita"])
    job.msg("Controllo le impostazioni del PC collegate agli stutter...")
    drv_ids = [t.id for t in tweaks.for_vendor(vendor()) if t.vendor]
    gpu_driver.invalidate()
    refresh_statuses(None, drv_ids)
    spm = len(stutters) / max(stats["durata_s"] / 60, 0.01)
    fac = factors.analyze(all_p, spm, STATE["statuses"], tweaks.applied_by_us(), vendor(), STATE["sysinfo"],
                          capped=bool(res["summary"].get("cap_fps")))
    html_name = "report-%s-%s.html" % (base, stamp)
    report.build(os.path.join(REPORTS, html_name), gname, stats, stutters, frametimes, all_p, info,
                 STATE["sysinfo"], drive, factors=fac, detail=res["detail"], summary=res["summary"])
    summary = dict(gioco=gname, cartella=os.path.dirname(exe) if exe else None, data=time.strftime("%d/%m/%Y %H:%M"),
                   etichetta=label, report=os.path.join(REPORTS, html_name), stutter=len(stutters),
                   stutter_min=len(stutters) / max(stats["durata_s"] / 60, 0.01),
                   modifiche_attive=tweaks.applied_by_us(), **{k: round(v, 2) for k, v in stats.items()})
    summary["id"] = sessions.add(summary)
    return {"session": summary, "problems": all_p, "info": info, "report": html_name, "factors": fac,
            "breakdown": res["summary"], "health": res["health"],
            "detail": sorted(res["detail"], key=lambda x: -x["ft"])[:40]}


# ======================================================================= HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self, qs):
        return secrets.compare_digest(self.headers.get("X-Token", "") or (qs.get("t", [""])[0]), TOKEN)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        STATE["last_req"] = time.time()
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        try:
            if u.path in ("/", "/index.html"):
                if not self._authorized(qs):
                    return self._send(403, b"Accesso negato", "text/plain")
                return self._static("index.html")
            if u.path.startswith("/ui/"):
                return self._static(u.path[4:])
            if not self._authorized(qs):
                return self._send(403, {"error": "token"})
            if u.path == "/report":
                name = os.path.basename(qs.get("f", [""])[0])
                path = os.path.join(REPORTS, name)
                if not name.endswith(".html") or not os.path.isfile(path):
                    return self._send(404, b"Report non trovato", "text/plain")
                with open(path, "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            return self._send(200, self.api_get(u.path, qs))
        except Exception as e:
            log_error()
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/bye":  # la finestra e' stata chiusa (inviato dal browser senza intestazioni)
            if secrets.compare_digest(parse_qs(u.query).get("t", [""])[0], TOKEN):
                STATE["bye"] = time.time()
                if TRAY is not None and TRAY.ok and not STATE.get("tray_hint"):
                    threading.Thread(target=_tray_hint, daemon=True).start()
            return self._send(204, b"", "text/plain")
        STATE["last_req"] = time.time()
        if not secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN):
            return self._send(403, {"error": "token"})
        try:
            code, body = self.api_post(u.path, self._body())
            return self._send(code, body)
        except Exception as e:
            log_error()
            return self._send(500, {"error": str(e)})

    def _static(self, rel):
        path = os.path.normpath(os.path.join(UI_DIR, rel))
        if not path.startswith(UI_DIR) or not os.path.isfile(path):
            return self._send(404, b"", "text/plain")
        with open(path, "rb") as f:
            data = f.read()
        if rel == "index.html":
            data = data.replace(b"__TOKEN__", TOKEN.encode())
        return self._send(200, data, MIME.get(os.path.splitext(path)[1], "application/octet-stream"))

    # ------------------------------------------------------------------ GET
    def api_get(self, path, qs):
        if path == "/api/state":
            boot = JOBS.get(STATE.get("boot_job") or "")
            exp = sessions.experiment()
            applied = set(tweaks.applied_by_us())
            probs = [p for p in STATE["sys_problems"]  # togli i problemi gia' corretti
                     if not (p.get("fix_id") and (p["fix_id"] in applied or STATE["statuses"].get(p["fix_id"]) is True))]
            return {"sysinfo": STATE["sysinfo"], "problems": probs, "experiment": exp,
                    "applied": len(tweaks.applied_by_us()), "busy": STATE["busy"],
                    "admin": _is_admin(), "reboot": reboot_pending(),
                    "booting": boot.status == "running" if boot else False,
                    "boot_msg": boot.messages[-1] if boot and boot.messages else None,
                    "hw_cached": STATE.get("hw_cached", False),
                    "version": __version__, "installed": paths.FROZEN, "data_dir": paths.DATA_DIR,
                    "gm": _gm_quick()}
        if path == "/api/job":
            job = JOBS.get(qs.get("id", [""])[0])
            return job.as_dict() if job else {"status": "missing"}
        if path == "/api/catalog":
            return catalog_json()
        if path == "/api/startup":
            return {"items": tweaks.startup_items(),
                    "bad": sorted(k.lower() for k, v in checks.KNOWN_BAD.items() if v)}
        if path == "/api/driver":
            return driver_report(fresh=True)
        if path == "/api/processes":
            return {"items": game_candidates()}
        if path == "/api/ping":
            return {"ok": True}
        if path == "/api/settings":
            return settings.status()
        if path == "/api/update":
            return updater.check(force=qs.get("force", ["0"])[0] == "1")
        if path == "/api/gamemode":
            return gamemode_json(scan=qs.get("scan", ["0"])[0] == "1")
        if path == "/api/sessions":
            return {"items": list(reversed(sessions.all_sessions()))}
        if path == "/api/compare":
            a = sessions.get(int(qs["a"][0]))
            b = sessions.get(int(qs["b"][0]))
            rows, verdict, why = sessions.compare(a, b)
            da, db = set(a.get("modifiche_attive", [])), set(b.get("modifiche_attive", []))
            nm = lambda i: tweaks.BY_ID[i].name if i in tweaks.BY_ID else i
            return {"a": a, "b": b, "verdict": verdict, "why": why,
                    "rows": [{"label": r[0], "a": r[1], "b": r[2], "pct": r[3], "better": r[4]} for r in rows],
                    "added": [nm(i) for i in db - da], "removed": [nm(i) for i in da - db],
                    "same_game": a["gioco"].lower() == b["gioco"].lower()}
        if path == "/api/sensors":
            m = STATE["sensor"]
            if m is None:
                m = gpumod.make_monitor((STATE["sysinfo"] or {}).get("gpu"))
                if m.available:
                    m.start()
                STATE["sensor"] = m
            m.last_read = time.time()
            return {"available": m.available, "data": m.latest}
        return {"error": "sconosciuto"}

    # ------------------------------------------------------------------ POST
    def api_post(self, path, b):
        if path == "/api/boot":
            old = JOBS.get(STATE.get("boot_job") or "")
            if old and old.status == "running":  # gia' in corso (es. finestra ricaricata)
                return 200, old.as_dict()
            hw = checks.cached_hardware()
            STATE["hw_cached"] = bool(hw)
            if hw and not STATE["sysinfo"]:
                # avvii successivi: l'interfaccia si apre subito con l'hardware salvato, le impostazioni si
                # rileggono in background
                STATE["sysinfo"] = {k: hw.get(k) for k in ("cpu", "gpu", "refresh_hz", "ram_gb", "ram")}
                tweaks.CONTEXT.update(refresh_hz=hw.get("refresh_hz"), vendor=(hw.get("gpu") or {}).get("vendor"))
            job = start_job("boot", job_boot, hw)
            STATE["boot_job"] = job.id
            return 200, job.as_dict()
        if path in ("/api/scan", "/api/apply", "/api/revert", "/api/restore_all", "/api/record", "/api/check"):
            if STATE["busy"] and JOBS.get(STATE["busy"]) and JOBS[STATE["busy"]].status == "running":
                return 409, {"error": "C'e' gia' un'operazione in corso: aspetta che finisca."}
        if path == "/api/scan":
            job = start_job("scan", job_scan)
        elif path == "/api/check":
            job = start_job("check", lambda j: refresh_statuses(j) or catalog_json())
        elif path == "/api/apply":
            ids = [i for i in b.get("ids", []) if i in tweaks.BY_ID]
            seen, uniq = set(), []
            for i in ids:  # una sola voce per gruppo
                g = tweaks.BY_ID[i].group
                if g and g in seen:
                    continue
                seen.add(g)
                uniq.append(i)
            if any(tweaks.BY_ID[i].risk >= 2 for i in uniq) and b.get("confirm") != "CONFERMO":
                return 400, {"error": "Per le modifiche rischiose serve la conferma."}
            path_ = b.get("defender_path") or ""
            if any(isinstance(tweaks.BY_ID[i], tweaks.DefenderExclusionTweak) for i in uniq) and not os.path.isdir(path_):
                return 400, {"error": "La cartella per l'esclusione di Defender non esiste: %s" % path_}
            job = start_job("apply", job_apply, uniq, path_)
        elif path == "/api/revert":
            job = start_job("revert", job_revert, [i for i in b.get("ids", []) if i in tweaks.BY_ID])
        elif path == "/api/restore_all":
            job = start_job("restore_all", job_restore_all)
        elif path == "/api/record":
            seconds = max(30, min(3600, int(b.get("seconds", 300))))
            job = start_job("record", job_record, int(b["pid"]), seconds, b.get("label", ""))
        elif path == "/api/stop":
            job = JOBS.get(b.get("id", ""))
            if job:
                job.stop.set()
            return 200, {"ok": True}
        elif path == "/api/startup":
            item = next((i for i in tweaks.startup_items() if i["hive"] == b.get("hive") and i["name"] == b.get("name")), None)
            if not item:
                return 404, {"error": "voce non trovata"}
            tweaks.set_startup(item, bool(b.get("enabled")))
            return 200, {"ok": True}
        elif path == "/api/gamemode":
            return 200, gamemode_post(b)
        elif path == "/api/settings":
            d = settings.load()
            for k in settings.DEFAULTS:
                if k in b:
                    d[k] = bool(b[k])
            settings.apply(d)
            return 200, settings.status()
        elif path == "/api/update/install":
            return 200, start_job("update", job_update).as_dict()
        elif path == "/api/fix":
            fix = b.get("fix")
            if not fix or fix[0] not in fixes.DESCRIPTIONS:
                return 400, {"error": "correzione sconosciuta"}
            return 200, {"msg": fixes.apply((fix[0], fix[1]), BACKUP)}
        elif path == "/api/experiment/start":
            sessions.start_experiment(b["game"], int(b["before"]), b["ids"])
            return 200, {"ok": True}
        elif path == "/api/experiment/end":
            sessions.end_experiment()
            return 200, {"ok": True}
        elif path == "/api/force_off":
            tid = b.get("id")
            if tid not in tweaks.BY_ID:
                return 400, {"error": "voce sconosciuta"}
            msg = tweaks.force_off(tid)
            if tweaks.BY_ID[tid].reboot:
                note_reboot([tid])
            refresh_statuses(None, [tid])
            return 200, {"msg": msg}
        elif path == "/api/reboot":
            subprocess.Popen(["shutdown", "/r", "/t", "15", "/c", "LagDoctor: riavvio per applicare le modifiche"])
            return 200, {"ok": True}
        elif path == "/api/open_folder":
            os.makedirs(REPORTS, exist_ok=True)
            os.startfile(REPORTS)
            return 200, {"ok": True}
        elif path == "/api/show":  # un secondo avvio di LagDoctor chiede di riaprire la finestra
            threading.Thread(target=show_window, daemon=True).start()
            return 200, {"ok": True}
        elif path == "/api/quit":
            threading.Thread(target=lambda: (time.sleep(0.8), _close_windows(2.0), _shutdown()), daemon=True).start()
            return 200, {"ok": True}
        else:
            return 404, {"error": "sconosciuto"}
        if job.kind in ("scan", "apply", "revert", "restore_all", "record", "check"):
            STATE["busy"] = job.id
        return 200, job.as_dict()


def _is_admin():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


SERVER = None


def _shutdown():
    time.sleep(0.5)
    if TRAY is not None:
        TRAY.stop()
    if STATE["sensor"]:
        STATE["sensor"].stop()
    try:
        if INSTANCE:
            os.remove(INSTANCE)
    except OSError:
        pass
    SERVER.shutdown()


def _sensor_reaper():
    """Spegne il monitor dei sensori se la pagina non lo legge piu'."""
    while True:
        time.sleep(5)
        m = STATE["sensor"]
        if m is not None and time.time() - getattr(m, "last_read", 0) > 15:
            m.stop()
            STATE["sensor"] = None


INSTANCE = None  # file con indirizzo e processo del LagDoctor gia' aperto


def _existing_instance():
    """Se LagDoctor e' gia' aperto, restituisce il suo indirizzo (per riaprire la finestra invece di avviarne un altro)."""
    try:
        with open(INSTANCE, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("pid") and d["pid"] != os.getpid() and psutil.pid_exists(d["pid"]):
            import urllib.request
            req = urllib.request.Request(d["url"].split("/?")[0] + "/api/ping", headers={"X-Token": d["token"]})
            with urllib.request.urlopen(req, timeout=3) as r:
                if r.status == 200:
                    return d["url"]
    except Exception:
        pass
    return None


def _auto_exit():
    """Versione installata (senza finestra nera): quando chiudi la finestra di LagDoctor, il programma si chiude.

    Non si guarda il processo di Edge: quando LagDoctor e' amministratore, Edge si riavvia da solo senza permessi e
    il processo avviato termina subito (prima di questa correzione LagDoctor si chiudeva dopo pochi secondi).
    - la pagina, quando viene chiusa, manda un saluto (/api/bye): se entro 8 secondi non arriva altro, mi chiudo
      (8 secondi: se la pagina era solo ricaricata, nel frattempo richiede di nuovo i dati)
    - riserva: nessun contatto dalla pagina per 10 minuti (la pagina manda un battito ogni 20 secondi)
    - se il PC e' stato in sospensione, il conteggio riparte."""
    STATE["last_req"] = time.time()
    last_loop = time.time()
    while True:
        time.sleep(2)
        now = time.time()
        if now - last_loop > 30:  # il PC si e' appena risvegliato dalla sospensione
            STATE["last_req"] = now
            STATE["bye"] = None
        last_loop = now
        if STATE["busy"] and JOBS.get(STATE["busy"]) and JOBS[STATE["busy"]].status == "running":
            STATE["last_req"] = now  # mai chiudere durante un'operazione
            continue
        bye = STATE.get("bye")
        if bye and now - bye > 8 and STATE["last_req"] <= bye + 0.5:
            break
        if now - STATE["last_req"] > 600:
            break
    _shutdown()


def _startup_repairs():
    """Dopo l'installazione o un aggiornamento: rimette a posto gli avvii automatici e riavvia la game mode."""
    for fn in (gamemode.recover, gamemode.ensure_running, _repair_timer, settings.repair):
        try:
            fn()
        except Exception:
            log_error()


def _repair_timer():
    from . import extra_tweaks
    extra_tweaks.repair_timer()


def _lagdoctor_windows():
    """Finestre di Edge con il titolo 'LagDoctor' (la finestra del programma)."""
    try:
        from ctypes import wintypes
        import ctypes
        u32 = ctypes.windll.user32
        proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    except Exception:
        return []
    found = []

    def cb(h, _l):
        n = u32.GetWindowTextLengthW(h)
        if u32.IsWindowVisible(h) and n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(h, buf, n + 1)
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            try:
                is_edge = psutil.Process(pid.value).name().lower() == "msedge.exe"
            except psutil.Error:
                is_edge = False
            if is_edge and buf.value.strip().startswith("LagDoctor"):
                found.append(h)
        return True
    u32.EnumWindows(proto(cb), 0)
    return found


def _window_processes():
    """Processi di Edge che usano il profilo dedicato di LagDoctor (solo la finestra di LagDoctor, mai le altre)."""
    profile = os.path.normcase(os.path.join(paths.DATA_TOOLS, "finestra"))
    out = []
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if (p.info["name"] or "").lower() != "msedge.exe":
                continue
            cmd = os.path.normcase(" ".join(p.info["cmdline"] or []))
            if profile in cmd:
                out.append(p)
        except psutil.Error:
            continue
    return out


def _close_windows(wait=4.0):
    """Chiude la finestra di LagDoctor: prima con gentilezza (WM_CLOSE), poi chiudendo i processi di Edge del suo
    profilo dedicato se e' ancora aperta."""
    try:
        import ctypes
        for h in _lagdoctor_windows():
            ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
    except Exception:
        pass
    end = time.time() + wait
    while time.time() < end and _window_processes():
        time.sleep(0.25)
    procs = _window_processes()
    for p in procs:
        try:
            p.terminate()
        except psutil.Error:
            pass
    if procs:
        psutil.wait_procs(procs, timeout=3)


def _minimize_later(proc, seconds=25):
    """Riduce a icona la finestra di LagDoctor appena compare (avvio con Windows 'ridotto a icona')."""
    try:
        import ctypes
        u32 = ctypes.windll.user32
    except Exception:
        return
    end = time.time() + seconds
    while time.time() < end:
        found = _lagdoctor_windows()
        if found:
            for h in found:
                u32.ShowWindow(h, 7)  # SW_SHOWMINNOACTIVE: ridotta a icona, senza rubare lo stato attivo
            return
        time.sleep(0.25)


TRAY = None
URL = None


def _tray_hint():
    """Dopo la chiusura della finestra (non un semplice ricaricamento), una volta: LagDoctor e' ancora qui."""
    bye = STATE.get("bye")
    time.sleep(6)
    if STATE.get("bye") == bye and STATE.get("last_req", 0) <= (bye or 0) + 0.5 and not STATE.get("tray_hint"):
        STATE["tray_hint"] = True
        TRAY.notify("LagDoctor e' ancora aperto", "Lo trovi qui, tra le icone vicino all'orologio. Clic per riaprirlo, "
                                                  "tasto destro > Esci per chiuderlo.")


def show_window():
    """Riapre la finestra di LagDoctor, o la porta in primo piano se e' gia' aperta."""
    wins = _lagdoctor_windows()
    if wins:
        try:
            import ctypes
            u32 = ctypes.windll.user32
            for h in wins[:1]:
                u32.ShowWindow(h, 9)  # SW_RESTORE
                u32.SetForegroundWindow(h)
            return
        except Exception:
            pass
    open_window(URL)


def quit_all():
    """Esci dal menu dell'icona: chiude la finestra e il programma."""
    _close_windows(2.0)
    _shutdown()


def open_window(url, minimized=False):
    edge_paths = [os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                  os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")]
    exe = next((p for p in edge_paths if os.path.isfile(p)), None) or shutil.which("msedge")
    if exe:
        profile = os.path.join(paths.DATA_TOOLS, "finestra")
        os.makedirs(profile, exist_ok=True)
        STATE["window"] = subprocess.Popen([exe, "--app=" + url, "--window-size=1280,860",
                                            "--user-data-dir=" + profile, "--no-first-run",
                                            "--no-default-browser-check"])
        STATE["window_t"] = time.time()
        if minimized:
            threading.Thread(target=_minimize_later, args=(STATE["window"],), daemon=True).start()
    else:
        webbrowser.open(url)


def run(open_ui=True, port=0, minimized=False, from_logon=False):
    global SERVER
    tweaks.init(ROOT)
    sessions.init(REPORTS, ROOT)
    checks.HW_FILE = os.path.join(ROOT, "hardware.json")
    global INSTANCE
    INSTANCE = paths.data("in_esecuzione.json")
    if open_ui:
        url = _existing_instance()
        if url:  # gia' aperto: chiedo a quello di mostrare la finestra (all'avvio di Windows non serve)
            if not from_logon:
                try:
                    import urllib.request
                    with open(INSTANCE, encoding="utf-8") as f:
                        tok = json.load(f)["token"]
                    req = urllib.request.Request(url.split("/?")[0] + "/api/show", data=b"{}", method="POST",
                                                 headers={"X-Token": tok, "Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=3).read()
                except Exception:
                    open_window(url)
            return url
    SERVER = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/?t=%s" % (SERVER.server_address[1], TOKEN)
    try:
        with open(INSTANCE, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "url": url, "token": TOKEN}, f)
    except OSError:
        pass
    threading.Thread(target=_sensor_reaper, daemon=True).start()
    global TRAY, URL
    URL = url
    tray_ok = False
    if open_ui:
        threading.Thread(target=_startup_repairs, daemon=True).start()
        # icona vicino all'orologio: chiudere la finestra con la X non chiude il programma
        TRAY = tray.Tray(os.path.join(UI_DIR, "lagdoctor.ico"), on_open=show_window, on_quit=quit_all,
                         tooltip="LagDoctor " + __version__)
        try:
            tray_ok = TRAY.start()
        except Exception:
            tray_ok = False
    if (paths.FROZEN or from_logon) and open_ui and not tray_ok:
        threading.Thread(target=_auto_exit, daemon=True).start()  # senza icona: si chiude con la finestra
    print("\n  LagDoctor e' aperto in una finestra a parte.")
    print("  NON chiudere questa finestra nera finche' usi LagDoctor (chiudila per uscire).")
    print("  Se la finestra non si e' aperta, copia questo indirizzo nel browser:\n  " + url + "\n")
    if open_ui and not (minimized and from_logon and tray_ok):  # ridotto a icona all'avvio: solo l'icona
        open_window(url, minimized)
    try:
        SERVER.serve_forever()
    except KeyboardInterrupt:
        pass
    return url


def main(minimized=False, from_logon=False):
    from .main import is_admin, relaunch_as_admin
    if os.name == "nt" and not is_admin() and not paths.FROZEN:
        relaunch_as_admin("lagdoctor.server")
    if not paths.FROZEN and not from_logon:
        os.system("title LagDoctor")
    run(minimized=minimized, from_logon=from_logon)


if __name__ == "__main__":
    main()
