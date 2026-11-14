"""Finestra di LagDoctor senza la barra grigia di Edge (WebView2, tramite pywebview).

    LagDoctor.exe --finestra <indirizzo> [--ridotto]

E' un processo a parte, avviato dal programma come prima si avviava Edge: il resto di LagDoctor (server, icona
vicino all'orologio, avvio con Windows) non cambia. Se la finestra non parte o si chiude con un errore, LagDoctor
apre subito la finestra di Edge come prima (server.py) e per questa versione non riprova.

La barra del titolo la disegna l'interfaccia (ui/index.html, body.frameless). Solo funzioni ufficiali di
pywebview: trascinamento (classe pywebview-drag-region), move, resize, minimize, destroy. Niente chiamate dirette a
Windows sulla finestra (la 5.25.0 le usava e la finestra si chiudeva appena cliccata).
Errori e chiusure improvvise vengono scritti in errore-finestra.txt (cartella dei dati di LagDoctor).
"""
import os
import sys
import threading
import time

FAILED = 3
MIN_W, MIN_H = 900, 600


def _log_path():
    from . import paths
    os.makedirs(paths.DATA_DIR, exist_ok=True)
    return paths.data("errore-finestra.txt")


def _log(text):
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
    except Exception:
        pass


class Api:
    """Funzioni chiamate dalla barra del titolo dell'interfaccia (window.pywebview.api.*).

    IMPORTANTE: tutti gli attributi devono iniziare con "_". pywebview, al caricamento della pagina, esplora ogni
    attributo pubblico per trovare altre funzioni: con la finestra in un attributo pubblico (5.25.0 e 5.25.1)
    leggeva anche posizione e dimensioni della finestra, ognuna con un'attesa fino a 15 secondi, bloccando la
    finestra (caricamento infinito, "non risponde", chiusura)."""

    def __init__(self):
        self._window = None
        self._normal = None   # posizione e dimensioni prima di ingrandire
        self._maxed = False

    def _guard(fn):
        """Un errore in un comando della barra non deve mai chiudere la finestra: lo scrivo nel registro."""
        def wrap(self, *a):
            try:
                return fn(self, *a)
            except Exception:
                import traceback
                _log("errore in %s:\n%s" % (fn.__name__, traceback.format_exc()))
                return None
        wrap.__name__ = fn.__name__
        return wrap

    def _screen(self):
        """Area di lavoro (senza la barra delle applicazioni) dello schermo dove sta la finestra, in pixel logici."""
        import webview
        w = self._window
        cx, cy = w.x + w.width // 2, w.y + w.height // 2
        scr = None
        for s in webview.screens:
            if s.x <= cx < s.x + s.width and s.y <= cy < s.y + s.height:
                scr = s
                break
        scr = scr or webview.screens[0]
        fr = scr.frame  # WorkingArea di Windows
        try:
            return int(fr.X), int(fr.Y), int(fr.Width), int(fr.Height)
        except Exception:
            return scr.x, scr.y, scr.width, scr.height

    @_guard
    def minimize(self):
        self._window.minimize()

    @_guard
    def toggle_maximize(self):
        """Ingrandisci = occupa l'area di lavoro dello schermo (non copre la barra delle applicazioni)."""
        w = self._window
        if self._maxed and self._normal:
            x, y, wd, ht = self._normal
            w.resize(wd, ht)
            w.move(x, y)
            self._maxed = False
        else:
            self._normal = (w.x, w.y, w.width, w.height)
            x, y, wd, ht = self._screen()
            w.move(x, y)
            w.resize(wd, ht)
            self._maxed = True
        return self._maxed

    @_guard
    def is_maximized(self):
        return self._maxed

    @_guard
    def get_size(self):
        return [self._window.width, self._window.height]

    @_guard
    def resize_to(self, width, height, edge):
        """Ridimensiona dai bordi: i bordi sinistro e alto tengono fermo il lato opposto."""
        from webview.window import FixPoint
        fix = (FixPoint.SOUTH if "top" in edge else FixPoint.NORTH) | (FixPoint.EAST if "left" in edge else FixPoint.WEST)
        self._maxed = False
        self._window.resize(max(MIN_W, int(width)), max(MIN_H, int(height)), fix)

    @_guard
    def close(self):
        self._window.destroy()


class Watch:
    """Controlla il motore di WebView2: se un suo processo si chiude (la pagina diventa nera) lo scrive nel registro
    e rimedia: pagina ricaricata, oppure uscita con errore cosi' LagDoctor apre la finestra di Edge."""

    def __init__(self):
        self._window = None
        self._fails = 0
        self._attached = False

    def attach(self):
        if self._attached:  # "loaded" arriva a ogni caricamento della pagina: collego una volta sola
            return
        self._attached = True
        try:
            from System import Action
            form = self._window.native
            core = form.browser.webview.CoreWebView2

            def f():
                core.ProcessFailed += self._failed
            form.Invoke(Action(f)) if form.InvokeRequired else f()
            _log("fase: pagina caricata, finestra aperta (WebView2 %s)" % getattr(core.Environment, "BrowserVersionString", "?"))
        except Exception:
            import traceback
            _log("controllo di WebView2 non attivo:\n" + traceback.format_exc())

    def _failed(self, sender, args):
        kind = str(getattr(args, "ProcessFailedKind", "?"))
        reason = str(getattr(args, "Reason", "?"))
        code = getattr(args, "ExitCode", "?")
        self._fails += 1
        _log("processo di WebView2 chiuso: %s (motivo %s, codice %s) - volta n. %d" % (kind, reason, code, self._fails))
        try:
            if "BrowserProcessExited" in kind or self._fails > 2:
                _log("passo alla finestra di Edge")
                os._exit(FAILED)
            if "RenderProcess" in kind or "FrameRenderProcess" in kind:
                sender.Reload()  # pagina nera: la ricarico
        except Exception:
            os._exit(FAILED)


def _dotnet_handlers():
    """Errori di .NET (WinForms, WebView2): scritti nel registro. Quelli del thread della finestra non la chiudono."""
    try:
        import clr
        clr.AddReference("System.Windows.Forms")
        from System import AppDomain
        from System.Windows.Forms import Application, UnhandledExceptionMode
        AppDomain.CurrentDomain.UnhandledException += lambda s, e: _log("errore .NET (chiude la finestra):\n%s" % e.ExceptionObject)
        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException)
        Application.ThreadException += lambda s, e: _log("errore .NET nella finestra (ignorato):\n%s" % e.Exception)
        _log("fase: gestione errori .NET attiva")
    except Exception:
        import traceback
        _log("gestione errori .NET non attiva:\n" + traceback.format_exc())


def main(args):
    url = next((a for a in args if a.startswith("http")), None)
    if not url:
        return FAILED
    soft = "--senza-gpu" in args
    if soft:  # secondo tentativo: grafica in software (molti crash di WebView2 vengono dal driver video)
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-gpu --disable-gpu-compositing"
    _log("fase: avvio della finestra nuova (%s), processo %d" % ("grafica software" if soft else "normale", os.getpid()))
    log = None
    try:
        import faulthandler
        log = open(_log_path(), "a", encoding="utf-8")
        faulthandler.enable(log)  # chiusure improvvise (anche dentro WebView2/.NET) finiscono nel registro
    except Exception:
        pass

    def thread_error(a):
        import traceback
        _log("errore in un thread:\n" + "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
    threading.excepthook = thread_error
    try:
        import logging
        import webview
        from . import paths
        h = logging.FileHandler(_log_path(), encoding="utf-8")
        h.setLevel(logging.WARNING)
        logging.getLogger("pywebview").addHandler(h)
        _log("fase: pywebview %s caricato" % getattr(webview, "__version__", "?"))
    except Exception:
        import traceback
        _log("pywebview non disponibile:\n" + traceback.format_exc())
        return FAILED
    _dotnet_handlers()
    api = Api()
    try:
        win = webview.create_window("LagDoctor", url + ("&" if "?" in url else "?") + "frameless=1",
                                    width=1280, height=860, min_size=(MIN_W, MIN_H), frameless=True, easy_drag=False,
                                    shadow=False, background_color="#07080D", js_api=api,
                                    minimized="--ridotto" in args)
        api._window = win
        watch = Watch()
        watch._window = win
        win.events.loaded += watch.attach
        win.events.shown += lambda: _log("fase: finestra mostrata")
        win.events.closed += lambda: _log("fase: finestra chiusa")
        _log("fase: avvio di WebView2")
        icon = os.path.join(paths.RES_DIR, "lagdoctor", "ui", "lagdoctor.ico")
        storage = os.path.join(paths.DATA_TOOLS, "finestra-webview2")
        os.makedirs(storage, exist_ok=True)
        webview.start(gui="edgechromium", private_mode=False, storage_path=storage,
                      icon=icon if os.path.isfile(icon) else None)
    except Exception:
        import traceback
        _log("la finestra non si e' aperta:\n" + traceback.format_exc())
        return FAILED
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
