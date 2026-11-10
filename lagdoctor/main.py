"""LagDoctor - trova la causa degli stutter nei giochi e li corregge.

Avvio: doppio clic su AVVIA.bat
"""
import ctypes
import os
import sys
import time

import psutil

from . import analysis, capture, checks, fixes, paths, report, scan, sessions, tweaks

try:
    paths.migrate()  # versioni precedenti: i dati stavano nella cartella del programma
except OSError:
    pass
ROOT = paths.DATA_DIR      # dati: C:\ProgramData\LagDoctor
TOOLS = paths.TOOLS        # PresentMon (incluso nel programma)
REPORTS = paths.REPORTS
BACKUP = paths.data("backup_impostazioni.json")
tweaks.init(ROOT)
sessions.init(REPORTS, ROOT)

GAME_HINTS = ("steamapps", "epic games", "riot games", "battle.net", "xboxgames", "ubisoft", "ea games",
              "electronic arts", "gog galaxy", "rockstar games", "\\games\\", "windowsapps")
NOT_GAMES = {"steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "battle.net.exe", "eadesktop.exe",
             "riotclientservices.exe", "upc.exe", "discord.exe", "chrome.exe", "msedge.exe", "firefox.exe",
             "explorer.exe", "searchhost.exe", "msmpeng.exe", "dwm.exe", "nvcontainer.exe", "nvidia app.exe",
             "memcompression", "registry", "svchost.exe", "csrss.exe", "lsass.exe", "spotify.exe",
             "wallpaper64.exe", "crashpad_handler.exe", "easyanticheat.exe", "vgc.exe", "msedgewebview2.exe"}


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(module="lagdoctor.main"):
    params = "-m " + module
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, paths.SRC_ROOT, 1)
    if r <= 32:
        print("Servono i permessi di amministratore per misurare i frame. Riprova e premi 'Si'.")
        input("Premi Invio per uscire...")
    sys.exit(0)


def title(t):
    print("\n" + "=" * 70 + "\n  " + t + "\n" + "=" * 70)


def ask(prompt, default=""):
    try:
        v = input(prompt).strip()
    except EOFError:
        v = ""
    return v or default


def yes(prompt):
    return ask(prompt + " [s/n]: ", "n").lower() in ("s", "si", "sì", "y", "yes")


def print_problems(problems):
    labels = {3: "[!!!]", 2: "[!! ]", 1: "[ ! ]"}
    for p in problems:
        print("\n  %s %s" % (labels[p["gravita"]], p["titolo"]))
        print("        " + p["spiegazione"])
        print("        -> " + p["soluzione"])


def offer_fixes(problems):
    fixable = [p for p in problems if p.get("auto_fix")]
    seen = set()
    for p in fixable:
        key = (p["auto_fix"][0], str(p["auto_fix"][1]))
        if key in seen:
            continue
        seen.add(key)
        if yes("\n  Vuoi che io proceda con: %s?" % fixes.describe(p["auto_fix"])):
            try:
                print("  " + fixes.apply(p["auto_fix"], BACKUP))
            except Exception as e:
                print("  Non sono riuscito: %s" % e)


def pick_game():
    while True:
        cands = []
        for p in psutil.process_iter(["pid", "name", "exe", "memory_info"]):
            name = (p.info["name"] or "").lower()
            if not name or name in NOT_GAMES or name in capture.IGNORE_PROCS:
                continue
            mem = p.info["memory_info"].rss / 2**20 if p.info["memory_info"] else 0
            exe = (p.info["exe"] or "").lower()
            likely = any(h in exe for h in GAME_HINTS)
            if mem > 300 or (likely and mem > 100):
                cands.append((likely, mem, p))
        cands.sort(key=lambda c: (not c[0], -c[1]))
        cands = cands[:12]
        print("\n  Processi aperti (* = probabilmente un gioco):\n")
        for i, (likely, mem, p) in enumerate(cands, 1):
            print("   %2d) %s %-40s %6.0f MB" % (i, "*" if likely else " ", p.info["name"], mem))
        print("\n    r) Aggiorna la lista")
        c = ask("\n  Scrivi il numero del gioco e premi Invio [1]: ", "1")
        if c.lower() == "r":
            continue
        try:
            return cands[int(c) - 1][2]
        except (ValueError, IndexError):
            print("  Scelta non valida.")


def run_session(sysinfo, sys_problems, label="", offer=True, game_name=None):
    """Registra una partita, analizza, salva. Restituisce il riepilogo della sessione (o None)."""
    title("PASSO 2 - Avvia il gioco" + (" (" + label + ")" if label else ""))
    if game_name:
        print("  Usa lo stesso gioco di prima (%s) e, se puoi, la stessa zona/mappa." % game_name)
    print("  1. Apri il gioco ed entra in partita (non restare nel menu).")
    print("  2. Torna qui con Alt+Tab.")
    ask("\n  Quando il gioco e' aperto, premi Invio...")
    game = pick_game()
    exe = ""
    try:
        exe = game.exe()
    except psutil.Error:
        pass
    drive, drive_problems = checks.check_game_drive(exe or "C:\\")

    title("PASSO 3 - Registrazione")
    mins = ask("  Quanti minuti vuoi registrare? (consigliato 5) [5]: ", "5")
    try:
        seconds = max(30, int(float(mins.replace(",", ".")) * 60))
    except ValueError:
        seconds = 300
    pm = capture.ensure_presentmon(TOOLS)
    print("\n  Torna nel gioco e GIOCA normalmente, soprattutto nelle zone dove senti gli scatti.")
    print("  La registrazione termina da sola dopo %d minuti (o premi Ctrl+C qui per fermarla prima)."
          % (seconds // 60))
    print("  Inizio tra 5 secondi...\n")
    time.sleep(5)
    os.makedirs(REPORTS, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    csv_path = os.path.join(REPORTS, "frame-%s-%s.csv" % (game.name().replace(".exe", ""), stamp))
    samples = capture.record(pm, game, csv_path, seconds, sysinfo.get("gpu"))

    title("PASSO 4 - Analisi")
    res = analysis.analyze_session(csv_path, game.name(), samples, sysinfo, sysinfo.get("refresh_hz"),
                                   driver_lookup=checks.suspect_drivers, drive=drive)
    frametimes = res["frametimes"]
    if res["too_few"]:
        print("  Troppi pochi frame registrati (%d). Il gioco era in primo piano e in partita?" % len(frametimes))
        print("  Alcuni giochi con anti-cheat bloccano la misura: in quel caso prova un altro gioco.")
        return None
    stats, stutters, problems, info = res["stats"], res["stutters"], res["problems"], res["info"]
    all_problems = sorted(problems + drive_problems + sys_problems, key=lambda p: -p["gravita"])

    print("  FPS medi: %.0f | 1%% low: %.0f | 0.1%% low: %.0f | stutter: %d"
          % (stats["fps_medi"], stats["fps_1low"], stats["fps_01low"], len(stutters)))
    for i in info:
        print("  - " + i)
    print_problems(all_problems)

    html_path = os.path.join(REPORTS, "report-%s-%s.html" % (game.name().replace(".exe", ""), stamp))
    report.build(html_path, game.name(), stats, stutters, frametimes, all_problems, info, sysinfo, drive,
                 detail=res["detail"], summary=res["summary"])
    print("\n  Report completo salvato in: " + html_path)
    try:
        os.startfile(html_path)
    except Exception:
        pass
    summary = dict(gioco=game.name(), cartella=os.path.dirname(exe) if exe else None,
                   data=time.strftime("%d/%m/%Y %H:%M"), etichetta=label, report=html_path,
                   stutter=len(stutters), stutter_min=len(stutters) / max(stats["durata_s"] / 60, 0.01),
                   modifiche_attive=tweaks.applied_by_us(),
                   **{k: round(v, 2) for k, v in stats.items()})
    summary["id"] = sessions.add(summary)
    print("  Sessione salvata con il numero #%d." % summary["id"])
    if offer:
        offer_fixes(all_problems)
    return summary


# ======================================================================= OTTIMIZZAZIONI

_restore_done = False


def ensure_restore_point():
    global _restore_done
    if _restore_done:
        return True
    print("\n  Creo un punto di ripristino di Windows (puo' richiedere fino a 1-2 minuti)...")
    ok, msg = tweaks.create_restore_point()
    if ok:
        print("  Punto di ripristino creato: se qualcosa va storto puoi tornare indietro da")
        print("  'Crea un punto di ripristino' > 'Ripristino configurazione di sistema'.")
        _restore_done = True
        return True
    print("  Non sono riuscito a creare il punto di ripristino: " + msg)
    print("  (Ogni modifica ha comunque il suo backup e si puo' annullare da LagDoctor.)")
    if yes("  Vuoi continuare lo stesso?"):
        _restore_done = True
        return True
    return False


def show_details(t):
    print("\n  %s" % t.name)
    print("  Rischio: %s | Efficacia: %s | Riavvio: %s" % (tweaks.RISK[t.risk], t.efficacy,
                                                          "si" if t.reboot else "no"))
    print("  " + t.desc)
    if t.warning:
        print("  ATTENZIONE: " + t.warning)


def confirm_risky(ts):
    risky = [t for t in ts if t.risk >= 2]
    if not risky:
        return True
    print("\n  !!! Stai per applicare modifiche RISCHIOSE o PERICOLOSE:")
    for t in risky:
        print("\n  - %s [%s]" % (t.name, tweaks.RISK[t.risk]))
        if t.warning:
            print("    " + t.warning)
    return ask("\n  Scrivi CONFERMO (in maiuscolo) per procedere: ") == "CONFERMO"


def apply_tweaks(ids, sysinfo):
    ts = [tweaks.BY_ID[i] for i in ids]
    ts = [t for t in ts if t.id not in tweaks.applied_by_us()]
    if not ts:
        print("  Niente da applicare.")
        return []
    if not confirm_risky(ts) or not ensure_restore_point():
        print("  Annullato.")
        return []
    done = []
    for t in ts:
        if isinstance(t, tweaks.DefenderExclusionTweak):
            last = next((s.get("cartella") for s in reversed(sessions.all_sessions()) if s.get("cartella")), "")
            default = os.path.dirname(last) if last else ""
            t.path = ask("  Cartella da escludere da Defender [%s]: " % default, default).strip('"')
        try:
            print("  %s: %s" % (t.name, tweaks.apply_one(t.id)))
            done.append(t.id)
        except Exception as e:
            print("  %s: NON RIUSCITA - %s" % (t.name, e))
    if any(tweaks.BY_ID[i].reboot for i in done):
        print("\n  Alcune modifiche funzionano solo dopo il RIAVVIO del PC.")
    return done


def get_statuses(ids=None):
    """Legge lo stato attuale di ogni ottimizzazione (una volta sola)."""
    print("  Controllo lo stato di %d impostazioni (circa 20-40 secondi)..." % len(tweaks.CATALOG))
    st = {}
    for t in tweaks.CATALOG:
        try:
            st[t.id] = t.status()
        except Exception:
            st[t.id] = None
    return st


EFF_ORDER = {"alta": 0, "media": 1, "bassa": 2, "comfort": 3, "dubbia": 4}


def entry_line(n, t, st, applied, sysinfo):
    if t.id in applied:
        lab = "[LD ON]"
    else:
        lab = {True: "[ ON  ]", False: "[  -  ]", None: "[  ?  ]"}[st.get(t.id)]
    rec = "*" if t.recommended(sysinfo) else " "
    return "  %3d) %s%s %-55s %-10s %-7s %s" % (n, lab, rec, t.name[:55], tweaks.RISK[t.risk], t.efficacy,
                                               "R" if t.reboot else "")


LEGEND = ("  [LD ON] applicata da LagDoctor  [ ON  ] gia' attiva  [  -  ] non attiva  [  ?  ] non verificabile\n"
          "  * consigliata per il tuo PC   R serve il riavvio   colonne: rischio, efficacia")


def build_lists(sysinfo, st):
    applied = tweaks.applied_by_us()
    cat = tweaks.for_vendor(tweaks.CONTEXT.get("vendor"))
    fixes_ = [t for t in cat if t.id not in applied and st.get(t.id) is False and
              ((t.kind == "fix" and t.recommended(sysinfo) is not False) or t.harm_if_off)]
    fix_groups = {t.group for t in fixes_ if t.group}
    avail = [t for t in cat if t not in fixes_ and t.id not in applied and t.kind != "fix"
             and st.get(t.id) is not True and not (t.group and t.group in fix_groups)]
    avail.sort(key=lambda t: (not t.recommended(sysinfo), EFF_ORDER.get(t.efficacy, 5), t.risk))
    active = [t for t in cat if t.kind != "fix" and (st.get(t.id) is True or t.id in applied)]
    return fixes_, avail, active


def select_and_apply(entries, sysinfo, st, allow_undo=False):
    """entries: lista numerata di ottimizzazioni. Gestisce i comandi e applica le scelte."""
    print("\n  COMANDI: numeri da applicare (es. 1,4,7-12) | c = correzioni + consigliate | s = tutte le SICURE")
    print("           d 5 = dettagli della 5 | m = miti da evitare%s | Invio = salta"
          % (" | u = annulla modifiche di LagDoctor" if allow_undo else ""))
    while True:
        c = ask("\n  Scelta: ").strip().lower()
        if not c:
            return
        if c == "m":
            print("\n  Ottimizzazioni famose che LagDoctor NON applica, e perche':")
            for name, why in tweaks.MYTHS:
                print("\n  - %s\n    %s" % (name, why))
            continue
        if c == "u" and allow_undo:
            undo_menu()
            continue
        if c.startswith("d"):
            try:
                show_details(entries[int(c[1:].strip()) - 1])
            except (ValueError, IndexError):
                print("  Numero non valido.")
            continue
        applied = tweaks.applied_by_us()
        if c == "c":
            chosen = [t for t in entries if (t.kind == "fix" or t.harm_if_off or t.recommended(sysinfo))
                      and st.get(t.id) is not True and t.id not in applied]
        elif c == "s":
            chosen = [t for t in entries if t.risk == 0 and st.get(t.id) is not True and t.id not in applied]
        else:
            try:
                nums = []
                for part in c.replace(" ", "").split(","):
                    if "-" in part:
                        a, b = part.split("-", 1)
                        nums += list(range(int(a), int(b) + 1))
                    elif part:
                        nums.append(int(part))
                chosen = [entries[n - 1] for n in nums if 1 <= n <= len(entries)]
            except ValueError:
                print("  Non ho capito.")
                continue
        seen_groups, uniq = set(), []
        for t in chosen:
            if t.group and t.group in seen_groups:
                print("  (salto '%s': e' un'alternativa di un'altra voce scelta)" % t.name)
                continue
            seen_groups.add(t.group)
            uniq.append(t)
        chosen = uniq
        if not chosen:
            print("  Niente da applicare con questa scelta.")
            continue
        print("\n  Hai scelto %d modifiche:" % len(chosen))
        for t in chosen:
            print("   - %s [%s]" % (t.name, tweaks.RISK[t.risk]))
        if yes("  Confermi?"):
            done = apply_tweaks([t.id for t in chosen], sysinfo)
            for tid in done:
                st[tid] = True
            return done


def undo_menu():
    applied = tweaks.applied_by_us()
    if not applied:
        print("  LagDoctor non ha applicato nessuna modifica.")
        return
    for i, tid in enumerate(applied, 1):
        print("  %2d) %s" % (i, tweaks.BY_ID[tid].name))
    sel = ask("\n  Numeri da annullare (es. 1,3) oppure 't' per tutte: ").lower()
    todo = applied if sel == "t" else [applied[int(x) - 1] for x in sel.replace(" ", "").split(",")
                                       if x.isdigit() and 0 < int(x) <= len(applied)]
    for tid in todo:
        print("  %s: %s" % (tweaks.BY_ID[tid].name, tweaks.revert_one(tid)))


def settings_review(sysinfo, st):
    """Dopo la scansione: cosa correggere e cosa si puo' ancora attivare."""
    fixes_, avail, active = build_lists(sysinfo, st)
    title("Impostazioni di Windows: risultato del controllo")
    print(LEGEND)
    entries = []
    if fixes_:
        print("\n  === DA CORREGGERE: impostazioni attuali che ti TOLGONO prestazioni (%d) ===" % len(fixes_))
        for t in fixes_:
            entries.append(t)
            print(entry_line(len(entries), t, st, [], sysinfo))
    else:
        print("\n  === DA CORREGGERE: nessuna impostazione dannosa trovata ===")
    print("\n  === OTTIMIZZAZIONI NON ANCORA ATTIVE (%d) - prima le consigliate ===" % len(avail))
    section = None
    for t in avail:
        sec = "CONSIGLIATE PER IL TUO PC" if t.recommended(sysinfo) else {
            "alta": "EFFICACIA ALTA", "media": "EFFICACIA MEDIA", "bassa": "EFFICACIA BASSA",
            "comfort": "COMODITA' (nessun effetto sugli FPS)",
            "dubbia": "EFFICACIA DUBBIA (tweak famosi senza prove: verificali col test prima/dopo)"}.get(t.efficacy, "")
        if sec != section:
            section = sec
            print("  --- %s ---" % sec)
        entries.append(t)
        print(entry_line(len(entries), t, st, [], sysinfo))
    print("\n  Gia' attive sul tuo PC: %d ottimizzazioni." % len(active))
    if entries:
        select_and_apply(entries, sysinfo, st)


def tweak_menu(sysinfo):
    title("Ottimizzazioni di Windows (%d voci)" % len(tweaks.CATALOG))
    st = get_statuses()
    print(LEGEND)
    applied = tweaks.applied_by_us()
    cat = None
    for n, t in enumerate(tweaks.CATALOG, 1):
        if t.cat != cat:
            cat = t.cat
            print("\n  --- %s ---" % cat.upper())
        print(entry_line(n, t, st, applied, sysinfo))
    select_and_apply(tweaks.CATALOG, sysinfo, st, allow_undo=True)


def startup_review():
    items = tweaks.startup_items()
    if not items:
        return
    title("Programmi che partono con Windows")
    on = [i for i in items if i["enabled"]]
    off = [i for i in items if not i["enabled"]]
    bad = {k.lower() for k, v in checks.KNOWN_BAD.items() if v}
    for n, it in enumerate(on, 1):
        import ntpath
        exe = ntpath.basename(it["cmd"].split('"')[1] if it["cmd"].startswith('"') else it["cmd"].split(" ")[0])
        flag = "  <- noto per causare scatti" if exe.lower() in bad else ""
        if "securityhealth" in it["name"].lower():
            flag = "  <- sicurezza di Windows, lascialo"
        print("  %2d) %-35s %s%s" % (n, it["name"][:35], exe[:40], flag))
    if off:
        print("\n  Gia' disattivati: " + ", ".join(i["name"] for i in off))
    sel = ask("\n  Numeri dei programmi da NON far partire con Windows (es. 2,5), Invio = salta: ")
    for x in sel.replace(" ", "").split(","):
        if x.isdigit() and 0 < int(x) <= len(on):
            tweaks.set_startup(on[int(x) - 1], False)
            print("  Disattivato all'avvio: %s" % on[int(x) - 1]["name"])
    if sel.strip():
        print("  (Si riattivano da Gestione attivita' > App di avvio, o con 'Ripristina TUTTO'.)")



# ======================================================================= PRIMA / DOPO

def experiment_flow(sysinfo, sys_problems):
    exp = sessions.experiment()
    if exp:
        before = sessions.get(exp["prima"])
        title("Test prima/dopo - registrazione DOPO")
        print("  Modifiche in prova: " + ", ".join(tweaks.BY_ID[i].name for i in exp["modifiche"]))
        if not yes("  Pronto a registrare la partita DOPO le modifiche?"):
            if yes("  Vuoi annullare il test (le modifiche restano applicate)?"):
                sessions.end_experiment()
            return
        after = run_session(sysinfo, [], label="DOPO", offer=False, game_name=exp["gioco"])
        if not after:
            return
        title("Risultato del test")
        verdict = sessions.print_comparison(before, after)
        if verdict in ("PEGGIORATO", "NESSUNA DIFFERENZA"):
            if yes("\n  Vuoi annullare le modifiche provate?"):
                for tid in exp["modifiche"]:
                    print("  %s: %s" % (tweaks.BY_ID[tid].name, tweaks.revert_one(tid)))
        elif verdict == "MISTO":
            print("  Ti consiglio di rifare il test DOPO un'altra volta prima di decidere.")
        sessions.end_experiment()
        return

    title("Test prima/dopo")
    print("  Come funziona:")
    print("   1. Registri una partita PRIMA delle modifiche (o ne scegli una gia' registrata).")
    print("   2. Scegli le ottimizzazioni da provare: LagDoctor le applica.")
    print("   3. Registri una partita DOPO, nella stessa zona e per lo stesso tempo.")
    print("   4. LagDoctor confronta e ti dice se sono servite; se no, le annulla.")
    print("  Consiglio: prova poche modifiche alla volta, cosi' sai quale ha aiutato.")

    old = sessions.all_sessions()[-8:]
    before = None
    if old:
        print("\n  Sessioni recenti:")
        for s in old:
            print("   #%d  %s  %s  FPS %.0f  1%%low %.0f  stutter/min %.1f" % (
                s["id"], s["data"], s["gioco"], s["fps_medi"], s["fps_1low"], s["stutter_min"]))
        c = ask("\n  Numero della sessione da usare come PRIMA, oppure Invio per registrarne una nuova: ")
        if c.strip("#").isdigit():
            before = sessions.get(int(c.strip("#")))
    if not before:
        before = run_session(sysinfo, [], label="PRIMA", offer=False)
        if not before:
            return

    title("Scegli le ottimizzazioni da provare")
    st = get_statuses()
    fixes_, avail, active = build_lists(sysinfo, st)
    entries = fixes_ + avail
    print(LEGEND)
    for n, t in enumerate(entries, 1):
        print(entry_line(n, t, st, [], sysinfo))
    done = select_and_apply(entries, sysinfo, st)
    if not done:
        return
    sessions.start_experiment(before["gioco"], before["id"], done)
    if any(tweaks.BY_ID[i].reboot for i in done):
        print("\n  RIAVVIA IL PC, poi riapri LagDoctor: ti chiedero' di registrare la partita DOPO.")
        return
    experiment_flow(sysinfo, sys_problems)


def compare_menu():
    data = sessions.all_sessions()
    if len(data) < 2:
        print("  Servono almeno 2 sessioni registrate.")
        return
    for s in data[-15:]:
        print("   #%d  %s  %-25s %-6s FPS %.0f  1%%low %.0f  stutter/min %.1f" % (
            s["id"], s["data"], s["gioco"][:25], s.get("etichetta", ""), s["fps_medi"], s["fps_1low"],
            s["stutter_min"]))
    try:
        a = sessions.get(int(ask("\n  Sessione PRIMA (numero): ").strip("#")))
        b = sessions.get(int(ask("  Sessione DOPO (numero): ").strip("#")))
    except ValueError:
        print("  Numero non valido.")
        return
    if not a or not b:
        print("  Sessione non trovata.")
        return
    if a["gioco"].lower() != b["gioco"].lower():
        print("  Attenzione: sono due giochi diversi, il confronto ha poco senso.")
    sessions.print_comparison(a, b)
    da, db = set(a.get("modifiche_attive", [])), set(b.get("modifiche_attive", []))
    if da != db:
        print("\n  Modifiche diverse tra le due sessioni:")
        for t in db - da:
            print("   + %s" % tweaks.BY_ID[t].name)
        for t in da - db:
            print("   - %s" % tweaks.BY_ID[t].name)


# ======================================================================= SCANSIONE COMPLETA

def full_scan(sysinfo):
    title("Scansione completa del sistema")
    data = scan.collect(sysinfo)
    probs = scan.problems(data, sysinfo)
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, "scansione-%s.html" % time.strftime("%Y%m%d-%H%M%S"))
    scan.build_report(path, data, probs)
    with open(path.replace(".html", ".json"), "w", encoding="utf-8") as f:
        import json
        json.dump(data, f, indent=1, ensure_ascii=False, default=str)
    active = sum(1 for t in data.get("tweaks", []) if t["stato"])
    print("\n  Letti: hardware, %d banchi RAM, %d dischi, %d schermi, %d programmi installati, %d all'avvio,"
          % (len(scan._list(data.get("ram"))), len(scan._list(data.get("disks"))), len(data.get("displays", [])),
             len(scan._list(data.get("apps"))), len(scan._list(data.get("startup")))))
    print("  %d servizi attivi, errori degli ultimi 30 giorni, %d/%d ottimizzazioni gia' attive."
          % (data.get("services_running") or 0, active, len(data.get("tweaks", []))))
    if probs:
        print("\n  Ho trovato %d problemi:" % len(probs))
        print_problems(sorted(probs, key=lambda p: -p["gravita"]))
    else:
        print("\n  Nessun problema trovato.")
    print("\n  Report completo: " + path)
    try:
        os.startfile(path)
    except Exception:
        pass
    offer_fixes(probs)
    st = {t["id"]: t["stato"] for t in data.get("tweaks", [])}
    settings_review(sysinfo, st)
    startup_review()
    print("\n  Scansione completata.")


def sensor_test(sysinfo):
    from . import gpu as gpumod
    title("Test sensori della scheda video (10 secondi)")
    m = gpumod.make_monitor(sysinfo.get("gpu"))
    if not m.available:
        print("  Non riesco a leggere la scheda video.")
        return
    m.start()
    names = [("gpu_util", "Utilizzo %"), ("vram_used", "VRAM MB"), ("gpu_temp", "Temp C"),
             ("gpu_hotspot", "Hotspot C"), ("gpu_clock", "Clock MHz"), ("gpu_power", "Watt"),
             ("thr_thermal", "Throttling termico"), ("thr_power", "Limite potenza")]
    for _ in range(10):
        time.sleep(1)
        d = m.latest
        def fmt(v):
            if isinstance(v, bool):
                return "SI" if v else "no"
            if isinstance(v, (int, float)):
                return "%.0f" % v
            return "-"
        print("  " + " | ".join("%s: %s" % (lbl, fmt(d.get(k))) for k, lbl in names))
    m.stop()
    print("\n  Se vedi '-' su Temp/Hotspot, quel dato non e' disponibile per la tua scheda.")


def main():
    if os.name == "nt" and not is_admin():
        relaunch_as_admin()
    os.system("title LagDoctor")
    title("LagDoctor - diagnosi stutter e lag")

    print("  PASSO 1 - Controllo il tuo PC (circa 10 secondi)...")
    sysinfo, sys_problems = checks.run_all()
    tweaks.CONTEXT.update(refresh_hz=sysinfo.get("refresh_hz"), vendor=(sysinfo.get("gpu") or {}).get("vendor"))
    gpu = sysinfo.get("gpu") or {}
    print("\n  CPU: %s\n  GPU: %s (driver %s)\n  RAM: %s\n  Monitor: %s Hz" % (
        sysinfo["cpu"], gpu.get("name", "?"), gpu.get("driver", "?"), sysinfo["ram"], sysinfo.get("refresh_hz")))
    if sys_problems:
        print("\n  Ho trovato %d cose da sistemare nella configurazione:" % len(sys_problems))
        print_problems(sys_problems)
    else:
        print("\n  Configurazione di Windows OK.")
    print("\n  Consiglio: la prima volta fai la Scansione completa (S) per controllare tutto il PC.")

    exp = sessions.experiment()
    if exp:
        print("\n  >>> Hai un test prima/dopo in corso su %s: scegli 3 per registrare il DOPO." % exp["gioco"])

    while True:
        title("Menu")
        print("  1) Analizza un gioco (registra e trova la causa degli stutter)")
        print("  S) Scansione completa del sistema (hardware, Windows, driver, errori, impostazioni)")
        print("  2) Ottimizzazioni di Windows (catalogo completo, %d voci)" % len(tweaks.CATALOG))
        print("  3) Test prima/dopo (verifica se un'ottimizzazione serve davvero)%s"
              % ("  <-- IN CORSO" if sessions.experiment() else ""))
        print("  4) Confronta due sessioni registrate")
        print("  5) Applica le correzioni trovate nel controllo iniziale")
        print("  6) Ripristina TUTTO com'era prima di LagDoctor")
        print("  7) Test sensori della scheda video")
        print("  0) Esci")
        c = ask("\n  Scelta: ", "1")
        try:
            if c == "1":
                run_session(sysinfo, sys_problems)
            elif c.lower() == "s":
                full_scan(sysinfo)
            elif c == "2":
                tweak_menu(sysinfo)
            elif c == "3":
                experiment_flow(sysinfo, sys_problems)
            elif c == "4":
                compare_menu()
            elif c == "5":
                if any(p.get("auto_fix") for p in sys_problems):
                    offer_fixes(sys_problems)
                else:
                    print("  Non ci sono correzioni automatiche da applicare.")
            elif c == "6":
                if yes("  Annullo tutte le modifiche fatte da LagDoctor?"):
                    for m in tweaks.revert_all():
                        print("  " + m)
                    print("  " + fixes.undo_all(BACKUP))
                    sessions.end_experiment()
                    print("  Se alcune modifiche richiedevano il riavvio, riavvia il PC.")
            elif c == "7":
                sensor_test(sysinfo)
            elif c == "0":
                break
        except KeyboardInterrupt:
            print("\n  Operazione annullata.")
        except Exception as e:
            import traceback
            log = os.path.join(ROOT, "errore.txt")
            with open(log, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
            print("\n  ERRORE: %s" % e)
            print("  Dettagli salvati in: " + log + "  (mandami quel file)")


if __name__ == "__main__":
    main()
