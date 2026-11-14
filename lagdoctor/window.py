"""Finestra di LagDoctor senza la barra grigia di Edge (WebView2, tramite pywebview).

    LagDoctor.exe --finestra <indirizzo> [--ridotto]

E' un processo a parte, avviato dal programma come prima si avviava Edge: il resto di LagDoctor (server, icona
vicino all'orologio, avvio con Windows) non cambia. Se la finestra non si puo' creare (WebView2 o .NET mancanti)
esce con il codice 3 e LagDoctor apre la finestra di Edge come prima.

La barra del titolo la disegna l'interfaccia (ui/index.html, body.frameless). Trascinare la barra e i bordi passa
il comando a Windows (WM_NCLBUTTONDOWN, come le altre app con WebView2 e barra propria): cosi' funzionano Snap
(trascina in alto o ai lati), il ridimensionamento normale e Win+frecce.
"""
import ctypes
import os
import sys

FAILED = 3

WM_NCLBUTTONDOWN = 0x00A1
HIT = {"caption": 2, "left": 10, "right": 11, "top": 12, "topleft": 13, "topright": 14,
       "bottom": 15, "bottomleft": 16, "bottomright": 17}
GWL_STYLE = -16
WS_MINIMIZEBOX, WS_MAXIMIZEBOX, WS_SYSMENU = 0x00020000, 0x00010000, 0x00080000
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND = 33, 2


def _user32():
    u = ctypes.windll.user32
    u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    u.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    return u


class Api:
    """Funzioni chiamate dalla barra del titolo dell'interfaccia (window.pywebview.api.*)."""

    def __init__(self):
        self.window = None

    # ------------------------------------------------------------ utilita'
    def _form(self):
        return self.window.native

    def _hwnd(self):
        return ctypes.c_void_p(self._form().Handle.ToInt64())

    def _ui(self, fn):
        """Esegue fn sul thread della finestra (le chiamate dall'interfaccia arrivano da un altro thread)."""
        from System import Action
        form = self._form()
        if form.InvokeRequired:
            form.Invoke(Action(fn))
        else:
            fn()

    def _fit_maximized(self):
        """Ingrandita senza bordo, WinForms coprirebbe la barra delle applicazioni: limito all'area di lavoro dello
        schermo in cui si trova la finestra (coordinate relative a quello schermo)."""
        from System.Drawing import Rectangle
        from System.Windows.Forms import Screen
        form = self._form()
        scr = Screen.FromHandle(form.Handle)
        wa, b = scr.WorkingArea, scr.Bounds
        form.MaximizedBounds = Rectangle(wa.X - b.X, wa.Y - b.Y, wa.Width, wa.Height)

    def setup(self):
        """Appena la finestra compare: angoli arrotondati (Windows 11), riduci/ingrandisci dalla barra delle
        applicazioni e dalla tastiera, area di lavoro quando e' ingrandita."""
        def f():
            u = _user32()
            h = self._hwnd()
            u.SetWindowLongW(h, GWL_STYLE, u.GetWindowLongW(h, GWL_STYLE) | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
            try:
                pref = ctypes.c_int(DWMWCP_ROUND)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(h, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(pref), 4)
            except Exception:
                pass  # Windows 10: angoli dritti
            self._fit_maximized()
            form = self._form()
            form.Move += lambda s, e: self._fit_maximized()  # spostata su un altro schermo
        try:
            self._ui(f)
        except Exception:
            pass

    def _nc(self, what):
        def f():
            u = _user32()
            u.ReleaseCapture()
            u.PostMessageW(self._hwnd(), WM_NCLBUTTONDOWN, HIT[what], 0)
        self._ui(f)

    # ------------------------------------------------------------ chiamate dall'interfaccia
    def minimize(self):
        self.window.minimize()

    def toggle_maximize(self):
        def f():
            from System.Windows.Forms import FormWindowState
            form = self._form()
            if form.WindowState == FormWindowState.Maximized:
                form.WindowState = FormWindowState.Normal
            else:
                self._fit_maximized()
                form.WindowState = FormWindowState.Maximized
        self._ui(f)

    def is_maximized(self):
        out = []

        def f():
            from System.Windows.Forms import FormWindowState
            out.append(self._form().WindowState == FormWindowState.Maximized)
        try:
            self._ui(f)
        except Exception:
            return False
        return bool(out and out[0])

    def close(self):
        self.window.destroy()

    def start_drag(self):
        self._nc("caption")

    def start_resize(self, edge):
        if edge in HIT and edge != "caption":
            self._nc(edge)


def main(args):
    url = next((a for a in args if a.startswith("http")), None)
    if not url:
        return FAILED
    try:
        import webview
        from . import paths
    except Exception:
        return FAILED
    api = Api()
    try:
        win = webview.create_window("LagDoctor", url + ("&" if "?" in url else "?") + "frameless=1",
                                    width=1280, height=860, min_size=(900, 600), frameless=True, easy_drag=False,
                                    shadow=True, background_color="#07080D", js_api=api,
                                    minimized="--ridotto" in args)
        api.window = win
        win.events.shown += api.setup
        icon = os.path.join(paths.RES_DIR, "lagdoctor", "ui", "lagdoctor.ico")
        storage = os.path.join(paths.DATA_TOOLS, "finestra-webview2")
        os.makedirs(storage, exist_ok=True)
        webview.start(gui="edgechromium", private_mode=False, storage_path=storage,
                      icon=icon if os.path.isfile(icon) else None)
    except Exception:
        try:
            import traceback
            from . import paths
            os.makedirs(paths.DATA_DIR, exist_ok=True)
            with open(paths.data("errore-finestra.txt"), "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        return FAILED
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
