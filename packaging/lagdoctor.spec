# -*- mode: python ; coding: utf-8 -*-
# Ricetta PyInstaller: crea dist\LagDoctor con due eseguibili che condividono le stesse librerie.
#   LagDoctor.exe        programma (senza finestra nera), game mode, timer
#   LagDoctorHelper.exe  sonda di latenza, autodiagnosi, pulizia alla disinstallazione (con console)
# Uso:  python -m PyInstaller --noconfirm --clean packaging\lagdoctor.spec
import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(SPECPATH, "lagdoctor.ico")
datas = [
    (os.path.join(ROOT, "lagdoctor", "ui"), os.path.join("lagdoctor", "ui")),
    (os.path.join(ROOT, "strumenti", "PresentMon-2.4.1-x64.exe"), "strumenti"),
    (os.path.join(ROOT, "strumenti", "PresentMon-LICENSE.txt"), "strumenti"),
]
hidden = collect_submodules("lagdoctor") + ["autodiagnosi"]
# finestra WebView2 (lagdoctor/window.py): pywebview + pythonnet. Le DLL di WebView2 e gli script di pywebview li
# aggiunge il suo hook per PyInstaller; i moduli li indico qui perche' sono importati solo dentro window.main().
webview_hidden = ["webview", "webview.platforms.winforms", "webview.platforms.edgechromium", "webview.platforms.win32",
                  "clr", "clr_loader", "pythonnet", "proxy_tools", "bottle"]

gui = Analysis([os.path.join(SPECPATH, "lagdoctor_gui.py")], pathex=[ROOT], datas=datas, hiddenimports=hidden + webview_hidden)
helper = Analysis([os.path.join(SPECPATH, "lagdoctor_helper.py")], pathex=[ROOT], hiddenimports=hidden)

gui_exe = EXE(PYZ(gui.pure), gui.scripts, [], exclude_binaries=True, name="LagDoctor", icon=ICON,
              console=False, uac_admin=True, upx=False)
helper_exe = EXE(PYZ(helper.pure), helper.scripts, [], exclude_binaries=True, name="LagDoctorHelper", icon=ICON,
                 console=True, uac_admin=True, upx=False)

COLLECT(gui_exe, gui.binaries, gui.datas, helper_exe, helper.binaries, helper.datas, name="LagDoctor", upx=False)
