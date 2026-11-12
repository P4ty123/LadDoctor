"""Icona di LagDoctor nell'area di notifica (in basso a destra, vicino all'orologio).

- clic sinistro (o doppio clic): apre la finestra di LagDoctor
- clic destro: menu con "Apri LagDoctor" ed "Esci"
Chiudere la finestra con la X non chiude il programma: resta qui finche' non scegli "Esci".
Tutto con le API di Windows (ctypes), nessuna libreria esterna. Se l'icona non si puo' creare, start() restituisce
False e il programma si comporta come prima (si chiude insieme alla finestra).
"""
import ctypes
import os
import threading
from ctypes import wintypes

WM_DESTROY, WM_CLOSE, WM_COMMAND, WM_NULL = 0x0002, 0x0010, 0x0111, 0x0000
WM_APP_TRAY = 0x8001
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_CONTEXTMENU = 0x0202, 0x0203, 0x0205, 0x007B
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
NIIF_INFO, NIIF_USER = 0x1, 0x4
MF_STRING, MF_GRAYED, MF_SEPARATOR, MF_DEFAULT = 0x0, 0x1, 0x800, 0x1000
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x2, 0x80, 0x100
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
HWND_MESSAGE = wintypes.HWND(-3)
ID_OPEN, ID_QUIT = 1001, 1002

LRESULT = ctypes.c_ssize_t
_FUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)  # su Linux (solo per i test) non esiste
WNDPROC = _FUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]


class GUID(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID), ("hBalloonIcon", wintypes.HICON)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT), ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM), ("time", wintypes.DWORD), ("pt", wintypes.POINT)]


class Tray:
    def __init__(self, icon_path, on_open, on_quit, tooltip="LagDoctor"):
        self.icon_path, self.on_open, self.on_quit, self.tooltip = icon_path, on_open, on_quit, tooltip
        self.hwnd = None
        self.ok = False
        self._ready = threading.Event()
        self._proc = WNDPROC(self._wndproc)  # riferimento tenuto vivo
        self._taskbar_created = None
        self._nid = None

    # ------------------------------------------------------------------ avvio
    def start(self, timeout=5):
        if os.name != "nt":
            return False
        threading.Thread(target=self._run, daemon=True, name="tray").start()
        self._ready.wait(timeout)
        return self.ok

    def _api(self):
        u32, s32, k32 = ctypes.windll.user32, ctypes.windll.shell32, ctypes.windll.kernel32
        u32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        u32.DefWindowProcW.restype = LRESULT
        u32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                        wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        u32.CreateWindowExW.restype = wintypes.HWND
        u32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                   wintypes.UINT]
        u32.LoadImageW.restype = wintypes.HANDLE
        u32.CreatePopupMenu.restype = wintypes.HMENU
        u32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
        u32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.LPVOID]
        u32.TrackPopupMenu.restype = wintypes.BOOL
        u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        u32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        s32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
        k32.GetModuleHandleW.restype = wintypes.HMODULE
        return u32, s32, k32

    def _run(self):
        try:
            u32, s32, k32 = self._api()
            self.u32, self.s32 = u32, s32
            hinst = k32.GetModuleHandleW(None)
            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.lpfnWndProc = self._proc
            wc.hInstance = hinst
            wc.lpszClassName = "LagDoctorTray"
            u32.RegisterClassExW(ctypes.byref(wc))
            self.hwnd = u32.CreateWindowExW(0, "LagDoctorTray", "LagDoctor", 0, 0, 0, 0, 0, HWND_MESSAGE, None,
                                            hinst, None)
            if not self.hwnd:
                raise OSError("CreateWindowExW")
            self._taskbar_created = u32.RegisterWindowMessageW("TaskbarCreated")
            self.hicon = None
            if self.icon_path and os.path.isfile(self.icon_path):
                self.hicon = u32.LoadImageW(None, self.icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if not self.hicon:
                self.hicon = u32.LoadIconW(None, wintypes.LPCWSTR(32512))  # IDI_APPLICATION
            # l'area di notifica puo' non rispondere subito (PC lento o appena acceso): riprovo per ~30 secondi
            import time as _t
            for i in range(15):
                if self._add():
                    self.ok = True
                    break
                if i == 2:
                    self._ready.set()  # non blocco l'avvio: se l'icona arriva dopo, LagDoctor se ne accorge
                _t.sleep(2)
        except Exception:
            self.ok = False
        self._ready.set()
        if not self.ok:
            return
        msg = MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))

    def _nid_base(self):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        return nid

    def _add(self):
        nid = self._nid_base()
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_APP_TRAY
        nid.hIcon = self.hicon
        nid.szTip = self.tooltip[:127]
        return bool(self.s32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))

    # ------------------------------------------------------------------ eventi
    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_APP_TRAY:
                ev = lparam & 0xFFFF
                if ev in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self._safe(self.on_open)
                elif ev in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self._menu()
                return 0
            if self._taskbar_created and msg == self._taskbar_created:
                self._add()  # Esplora risorse e' ripartito (es. dopo la game mode): rimetto l'icona
                return 0
            if msg == WM_DESTROY:
                self.s32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid_base()))
                self.u32.PostQuitMessage(0)
                return 0
        except Exception:
            pass
        return self.u32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _menu(self):
        u32 = self.u32
        m = u32.CreatePopupMenu()
        u32.AppendMenuW(m, MF_STRING | MF_DEFAULT, ID_OPEN, "Apri LagDoctor")
        u32.AppendMenuW(m, MF_SEPARATOR, 0, None)
        u32.AppendMenuW(m, MF_STRING, ID_QUIT, "Esci")
        pt = wintypes.POINT()
        u32.GetCursorPos(ctypes.byref(pt))
        u32.SetForegroundWindow(self.hwnd)  # altrimenti il menu non si chiude cliccando altrove
        cmd = u32.TrackPopupMenu(m, TPM_RIGHTBUTTON | TPM_NONOTIFY | TPM_RETURNCMD, pt.x, pt.y, 0, self.hwnd, None)
        u32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        u32.DestroyMenu(m)
        if cmd == ID_OPEN:
            self._safe(self.on_open)
        elif cmd == ID_QUIT:
            self._safe(self.on_quit)

    @staticmethod
    def _safe(fn):
        threading.Thread(target=fn, daemon=True).start()  # mai bloccare i messaggi di Windows

    # ------------------------------------------------------------------ dall'esterno
    def notify(self, title, text):
        """Notifica di Windows (fumetto) dall'icona."""
        if not self.ok:
            return
        try:
            nid = self._nid_base()
            nid.uFlags = NIF_INFO
            nid.szInfoTitle = title[:63]
            nid.szInfo = text[:255]
            nid.dwInfoFlags = NIIF_INFO
            self.s32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
        except Exception:
            pass

    def stop(self):
        if self.ok and self.hwnd:
            try:
                self.u32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass
            self.ok = False
