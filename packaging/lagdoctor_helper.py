"""LagDoctorHelper.exe (con console).

  LagDoctorHelper.exe --probe          sonda di latenza usata durante le registrazioni
  LagDoctorHelper.exe --autodiagnosi   controllo di sola lettura di tutte le funzioni
  LagDoctorHelper.exe --disinstalla    usata dal programma di disinstallazione: spegne la game mode
                                       (ripristinando tutto) e toglie gli avvii automatici
  LagDoctorHelper.exe --ripristina     annulla tutte le modifiche fatte da LagDoctor
"""
import os
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fix_child_dll_path():
    """PyInstaller fa cercare le DLL nella sua cartella _internal e i programmi avviati da LagDoctor (PowerShell,
    powercfg...) ereditano questa impostazione: possono caricare librerie sbagliate e bloccarsi (es. i comandi di
    rete di PowerShell). La riporto al normale: i moduli di LagDoctor sono gia' caricati."""
    if getattr(sys, "frozen", False) and os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        except Exception:
            pass


def main():
    _fix_child_dll_path()
    args = sys.argv[1:]
    if args[:1] == ["--probe"]:
        from lagdoctor import capture
        exec(compile(capture.LATENCY_PROBE, "probe", "exec"), {"__name__": "__main__"})
    elif args[:1] == ["--autodiagnosi"]:
        import autodiagnosi
        autodiagnosi.main()
        input("\nPremi Invio per chiudere...")
    elif args[:1] == ["--disinstalla"]:
        from lagdoctor import gamemode, tweaks
        try:
            gamemode.disable()
        except Exception as e:
            print("game mode:", e)
        if "--ripristina" in args:
            from lagdoctor import fixes, paths
            tweaks.init(paths.DATA_DIR)
            for m in tweaks.revert_all():
                print(m)
            print(fixes.undo_all(paths.data("backup_impostazioni.json")))
        # il Timer Resolution parte da LagDoctor.exe: senza programma non funzionerebbe piu', quindi lo annullo
        from lagdoctor import extra_tweaks, paths
        tweaks.init(paths.DATA_DIR)
        if "timer_res" in tweaks.applied_by_us():
            print("Timer Resolution:", tweaks.revert_one("timer_res"))
        tweaks.run(["schtasks", "/Delete", "/TN", extra_tweaks.TIMER_TASK, "/F"])
        from lagdoctor import settings
        tweaks.run(["schtasks", "/Delete", "/TN", settings.TASK, "/F"])  # avvio con Windows
    elif args[:1] == ["--verifica"]:
        # usata da GitHub dopo la costruzione: il programma si carica e ha tutti i suoi file?
        import importlib
        from lagdoctor import paths
        for m in ("server", "gamemode", "capture", "stutter", "analysis", "tweaks", "extra_tweaks", "driver_tweaks",
                  "gpu_driver", "scan", "checks", "updater", "cputopo", "games", "virt_tweak", "tray", "cputemp", "settings"):
            importlib.import_module("lagdoctor." + m)
        from lagdoctor import server, capture, __version__
        need = [os.path.join(server.UI_DIR, f) for f in ("index.html", "app.js", "style.css")]
        need.append(capture.find_presentmon(paths.TOOLS) or "PresentMon mancante")
        missing = [f for f in need if not os.path.isfile(f)]
        print("LagDoctor", __version__, "| file mancanti:", missing or "nessuno")
        sys.exit(1 if missing else 0)
    elif args[:1] == ["--ripristina"]:
        from lagdoctor import fixes, paths, tweaks
        tweaks.init(paths.DATA_DIR)
        for m in tweaks.revert_all():
            print(m)
        print(fixes.undo_all(paths.data("backup_impostazioni.json")))
        input("\nFatto. Premi Invio per chiudere...")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
