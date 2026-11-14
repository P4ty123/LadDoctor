"""Verifica completa (strumento di prova): per OGNI ottimizzazione, per la game mode e per le altre funzioni di
LagDoctor controlla sul PC se quello che dovrebbe essere attivo lo e' davvero, e perche'.

Ogni riga ha un esito:
  ok      = attiva e verificata sullo stato reale di Windows
  ko      = PROBLEMA: LagDoctor l'ha applicata (o dovrebbe esserci) ma su questo PC non risulta attiva
  reboot  = applicata, ma l'effetto arriva solo dopo il riavvio (applicata dopo l'ultimo avvio di Windows)
  off     = non attiva (non e' stata applicata: niente da verificare)
  unk     = Windows non permette di leggerla
  manual  = si cambia solo a mano (niente da verificare per LagDoctor)
Solo lettura: la verifica non cambia niente.
"""
import datetime
import json
import os
import time

import psutil

from . import paths, tweaks

T = tweaks


# ------------------------------------------------------------------ dettagli per tipo di ottimizzazione
def _fmt(v):
    if v is None:
        return "assente"
    if isinstance(v, bytes):
        return v.hex()[:24]
    return str(v)


def _reg_detail(t):
    vals = t.values() if hasattr(t, "values") else []
    out = []
    for h, p, n, _typ, want in vals or []:
        cur = T.reg_read(h, p, n)[0]
        mark = "=" if cur == want or (cur is None and getattr(t, "absent_ok", False)) else "≠"
        out.append("%s\\...\\%s %s %s%s" % (h, p.split("\\")[-1], n, _fmt(cur),
                                           "" if mark == "=" else " (atteso %s)" % _fmt(want)))
    if getattr(t, "active", None) is not None:
        out.append("stato letto per effetto (anche se impostato con valori diversi)")
    return out


def _svc_detail(t):
    v = T.reg_read("HKLM", T.ServiceTweak.KEY + "\\" + t.service, "Start")[0]
    names = {0: "avvio", 1: "sistema", 2: "automatico", 3: "manuale", 4: "disattivato"}
    try:
        st = psutil.win_service_get(t.service).status()
    except Exception:
        st = "non leggibile"
    return ["servizio %s: avvio %s (atteso %s), stato %s" % (t.service, names.get(v, "non leggibile" if v is None else v), names.get(t.start, t.start), st)]


def detail(t):
    """Righe di dettaglio: cosa e' stato letto su Windows per decidere."""
    out = []
    try:
        if isinstance(t, T.RegTweak):
            out += _reg_detail(t)
        elif isinstance(t, T.ServiceTweak):
            out += _svc_detail(t)
        elif isinstance(t, T.PowerSettingTweak):
            cur = t._present()
            if not cur:
                out.append("impostazione energetica non leggibile")
            for s, q in cur.items():
                out.append("piano attivo%s: corrente %s / batteria %s (atteso %s)"
                           % ("" if s == t.setting else " (P-core)", q[0], q[1], t.value))
        elif isinstance(t, T.PowerPlanTweak):
            out.append("piano energetico attivo: %s" % (T._active_scheme() or "non leggibile"))
        elif isinstance(t, T.BcdTweak):
            code, o = T.run(["bcdedit", "/enum", "{current}"])
            line = next((l.strip() for l in o.splitlines() if l.split() and l.split()[0].lower() == t.option), None)
            out.append("bcdedit: %s" % (line or "%s non impostato" % t.option))
        elif t.id == "timer_res":
            from . import extra_tweaks as XT
            cur = XT.timer_now_ms()
            task = T.run(["schtasks", "/Query", "/TN", XT.TIMER_TASK])[0] == 0
            proc = any("--timer" in " ".join(p.info.get("cmdline") or []) or "timer_resolution" in " ".join(p.info.get("cmdline") or [])
                       for p in psutil.process_iter(["cmdline"]))
            out.append("timer attuale %s · attivita' all'avvio %s · processo %s" % (
                "%.3f ms" % cur if cur is not None else "non leggibile", "presente" if task else "assente",
                "in esecuzione" if proc else "non in esecuzione"))
        elif t.kind == "overlay":
            run = t.running() if hasattr(t, "running") else []
            out.append("processi dell'overlay aperti: %s" % (", ".join(run) if run else "nessuno"))
        elif hasattr(t, "packages"):
            from . import extra_tweaks as XT
            names = XT.installed_appx() or set()
            present = [p for p in t.packages if p.lower() in names]
            out.append("app ancora installate: %s" % (", ".join(present) if present else "nessuna"))
    except Exception as e:
        out.append("dettaglio non leggibile: %s" % e)
    note = getattr(t, "note", None)
    if note:
        out.append(str(note))
    return out


# ------------------------------------------------------------------ esito
def _applied_after_boot(info):
    try:
        when = datetime.datetime.fromisoformat(info.get("data")).timestamp()
    except Exception:
        return False
    return when > psutil.boot_time()


def verdict(t, status, applied_info):
    applied = applied_info is not None
    if getattr(t, "manual", False):
        if status is True:
            return "ok", "spento (impostazione del programma)"
        return "manual", "si cambia solo dal suo programma"
    if status is True and applied and t.reboot and _applied_after_boot(applied_info):
        return "reboot", "impostata: l'effetto arriva dopo il riavvio di Windows"
    if status is True:
        return "ok", "attiva" + (" (applicata da LagDoctor)" if applied else " (gia' impostata su Windows)")
    if status is None:
        why = getattr(t, "note", None) or "Windows non permette di leggerla"
        return "unk", why + (" (applicata da LagDoctor)" if applied else "")
    if applied:
        if t.reboot and _applied_after_boot(applied_info):
            return "reboot", "applicata: funziona dopo il riavvio di Windows"
        return "ko", "PROBLEMA: applicata da LagDoctor ma su questo PC non risulta attiva"
    return "off", "non attiva"


def check_tweaks(statuses, vendor):
    state = T.load_state()
    rows = []
    for t in T.for_vendor(vendor):
        st = statuses.get(t.id) if t.id in statuses else None
        code, msg = verdict(t, st, state.get(t.id))
        rows.append({"group": t.cat, "name": t.name, "id": t.id, "res": code, "msg": msg,
                     "detail": detail(t) if code in ("ok", "ko", "reboot", "unk") else []})
    return rows


# ------------------------------------------------------------------ game mode
def check_gamemode():
    from . import gamemode as G
    rows = []
    c = G.load_config()
    st = G.status()
    on = bool(c.get("enabled"))
    rows.append({"group": "Game mode", "name": "Game mode accesa", "res": "ok" if on else "off",
                 "msg": "accesa" if on else "spenta: accendila dalla pagina Game mode", "detail": []})
    if on:
        rows.append({"group": "Game mode", "name": "Programma invisibile della game mode", "res": "ok" if st.get("running") else "ko",
                     "msg": "in esecuzione" if st.get("running") else "PROBLEMA: non e' in esecuzione", "detail": []})
        rows.append({"group": "Game mode", "name": "Avvio con Windows della game mode", "res": "ok" if st.get("autostart") else "ko",
                     "msg": "attivita' presente" if st.get("autostart") else "PROBLEMA: attivita' all'avvio assente", "detail": []})
        games = [g["name"] for g in c.get("games", []) if g.get("on")]
        rows.append({"group": "Game mode", "name": "Giochi seguiti", "res": "ok" if games else "ko",
                     "msg": ", ".join(games) if games else "nessun gioco acceso nell'elenco", "detail": []})
    v = G.verify() if on else {"active": False, "items": []}
    if on and not v.get("active"):
        rows.append({"group": "Game mode", "name": "Ottimizzazioni durante il gioco", "res": "unk",
                     "msg": "nessun gioco aperto: apri un gioco dell'elenco, aspetta 15 secondi e premi Ricontrolla",
                     "detail": []})
    for it in v.get("items", []):
        res = "ok" if it["ok"] is True else "ko" if it["ok"] is False else "unk"
        rows.append({"group": "Game mode durante il gioco: " + it["group"], "name": it["name"], "res": res,
                     "msg": it.get("detail") or "", "detail": []})
    return rows


# ------------------------------------------------------------------ altre funzioni di LagDoctor
def _task_exists(name):
    return T.run(["schtasks", "/Query", "/TN", name])[0] == 0


def check_other():
    rows = []
    g = "Altre funzioni di LagDoctor"
    # avvio di LagDoctor con Windows
    try:
        from . import settings
        s = settings.status()
        if s.get("autostart"):
            rows.append({"group": g, "name": "Avvio di LagDoctor con Windows", "res": "ok" if s.get("task") else "ko",
                         "msg": "attivita' presente" if s.get("task") else "PROBLEMA: attivita' all'avvio assente", "detail": []})
        else:
            rows.append({"group": g, "name": "Avvio di LagDoctor con Windows", "res": "off", "msg": "non attivo", "detail": []})
    except Exception as e:
        rows.append({"group": g, "name": "Avvio di LagDoctor con Windows", "res": "unk", "msg": str(e), "detail": []})
    # guardiano degli overlay
    try:
        from . import overlays as O
        st = O._state()
        if st:
            task = _task_exists(O.GUARD_TASK)
            run = bool(O._guard_pids())
            rows.append({"group": g, "name": "Guardiano degli overlay (li tiene spenti)", "res": "ok" if task and run else "ko",
                         "msg": ("attivita' %s, processo %s" % ("presente" if task else "ASSENTE", "in esecuzione" if run else "NON in esecuzione")),
                         "detail": ["overlay spenti da LagDoctor: " + ", ".join(sorted(st))]})
        else:
            rows.append({"group": g, "name": "Guardiano degli overlay", "res": "off", "msg": "nessun overlay spento da LagDoctor", "detail": []})
    except Exception as e:
        rows.append({"group": g, "name": "Guardiano degli overlay", "res": "unk", "msg": str(e), "detail": []})
    # programmi all'avvio disattivati da LagDoctor
    try:
        dis = T.load_state().get("_startup", {})
        items = {("%s::%s" % (i["hive"], i["name"])): i for i in T.startup_items()}
        for key, it in dis.items():
            cur = items.get("%s::%s" % (it["hive"], it["name"]))
            ok = cur is not None and not cur["enabled"]
            rows.append({"group": "Avvio automatico: programmi disattivati", "name": it["name"], "res": "ok" if ok else "ko",
                         "msg": "non parte con Windows" if ok else ("PROBLEMA: risulta di nuovo attivo" if cur else "voce non piu' presente"),
                         "detail": []})
    except Exception as e:
        rows.append({"group": "Avvio automatico: programmi disattivati", "name": "Lettura", "res": "unk", "msg": str(e), "detail": []})
    # servizi e attivita' pianificate disattivati da LagDoctor
    try:
        from . import autostart as A
        mine = A._load()
        if mine:
            listed = {("%s:%s" % (i["kind"], i["id"])): i for i in A.list_items(include_windows=True)["items"]}
            for key in mine:
                cur = listed.get(key)
                kind, _, ident = key.partition(":")
                if cur is None:
                    res, msg = "unk", "non trovato (disinstallato?)"
                elif cur["on"]:
                    res, msg = "ko", "PROBLEMA: parte di nuovo con Windows"
                elif cur["running"]:
                    res, msg = "ko", "PROBLEMA: avvio disattivato ma il processo e' aperto"
                else:
                    res, msg = "ok", "avvio disattivato e fermo"
                rows.append({"group": "Avvio automatico: processi in background disattivati",
                             "name": (cur or {}).get("name", ident), "res": res, "msg": msg,
                             "detail": [(cur or {}).get("origin", "")] if cur else []})
    except Exception as e:
        rows.append({"group": "Avvio automatico: processi in background disattivati", "name": "Lettura", "res": "unk",
                     "msg": str(e), "detail": []})
    return rows


def summary(rows):
    out = {}
    for r in rows:
        out[r["res"]] = out.get(r["res"], 0) + 1
    return out


def as_text(rows, version):
    sym = {"ok": "[OK]", "ko": "[PROBLEMA]", "reboot": "[RIAVVIO]", "off": "[non attiva]", "unk": "[?]",
           "manual": "[a mano]"}
    out = ["LagDoctor %s - Verifica completa - %s" % (version, time.strftime("%d/%m/%Y %H:%M")), ""]
    s = summary(rows)
    out.append("OK %d · PROBLEMI %d · da riavviare %d · non attive %d · non leggibili %d" % (
        s.get("ok", 0), s.get("ko", 0), s.get("reboot", 0), s.get("off", 0), s.get("unk", 0)))
    group = None
    for r in rows:
        if r["group"] != group:
            group = r["group"]
            out += ["", "== " + group]
        out.append("%-12s %s: %s" % (sym.get(r["res"], r["res"]), r["name"], r["msg"]))
        for d in r.get("detail") or []:
            out.append("             - " + d)
    return "\n".join(out)
