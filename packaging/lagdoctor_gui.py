"""LagDoctor.exe (senza finestra nera).

  LagDoctor.exe                 apre il programma
  LagDoctor.exe --gamemode      game mode invisibile (parte con Windows)
  LagDoctor.exe --timer 5000    tiene il timer di sistema a 0,5 ms (parte con Windows)
  LagDoctor.exe --avvio-windows [--ridotto]   avvio automatico con Windows (eventualmente ridotto a icona)
"""
import os
import sys

if not getattr(sys, "frozen", False):  # avviato da sorgente: la cartella del programma e' quella sopra
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
    if args[:1] == ["--gamemode"]:
        from lagdoctor import gamemode
        gamemode.main()
    elif args[:1] == ["--timer"]:
        from lagdoctor import extra_tweaks
        units = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5000
        exec(compile(extra_tweaks.TIMER_SCRIPT % units, "timer_resolution", "exec"), {"__name__": "__main__"})
    else:
        from lagdoctor import server
        server.main(minimized="--ridotto" in args, from_logon="--avvio-windows" in args)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        from lagdoctor import paths
        os.makedirs(paths.DATA_DIR, exist_ok=True)
        with open(paths.data("errore.txt"), "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise
