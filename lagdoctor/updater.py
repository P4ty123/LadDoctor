"""Aggiornamenti automatici da GitHub.

Ogni nuova versione viene pubblicata come "Release" sul repository GitHub (vedi GITHUB_REPO), con allegati:
  - LagDoctor-Setup-<versione>.exe   l'installatore
  - SHA256SUMS.txt                   l'impronta dell'installatore (per controllare che il file sia integro)

Il programma chiede a GitHub qual e' l'ultima versione, la confronta con la propria, scarica l'installatore,
controlla l'impronta e lo avvia in modalita' silenziosa. L'installatore sostituisce solo i file del programma: i dati
(backup delle modifiche, report, game mode) sono in C:\\ProgramData\\LagDoctor e non vengono toccati.
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request

from . import GITHUB_REPO, __version__, paths

API = "https://api.github.com/repos/%s/releases/latest" % GITHUB_REPO
PAGE = "https://github.com/%s/releases/latest" % GITHUB_REPO
UA = "LagDoctor-updater"
_CACHE = {"t": 0, "data": None}


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check(force=False):
    """Restituisce dict: current, latest, available, notes, url, setup (url), sums (url), error."""
    if not force and _CACHE["data"] and time.time() - _CACHE["t"] < 1800:
        return _CACHE["data"]
    out = {"current": __version__, "latest": None, "available": False, "notes": "", "page": PAGE,
           "installed": paths.FROZEN, "error": None}
    try:
        rel = json.loads(_get(API))
        latest = (rel.get("tag_name") or "").lstrip("vV")
        assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        setup_name = next((n for n in assets if re.match(r"LagDoctor-Setup.*\.exe$", n, re.I)), None)
        setup = assets.get(setup_name)
        out.update(latest=latest, notes=(rel.get("body") or "")[:4000], setup=setup, setup_name=setup_name,
                   sums=assets.get("SHA256SUMS.txt"),
                   available=bool(latest) and vtuple(latest) > vtuple(__version__) and bool(setup))
    except urllib.error.HTTPError as e:
        out["error"] = "nessuna versione pubblicata" if e.code == 404 else "GitHub ha risposto %d" % e.code
    except Exception as e:
        out["error"] = "non riesco a contattare GitHub (%s)" % (e.__class__.__name__,)
    _CACHE.update(t=time.time(), data=out)
    return out


def download(info, progress=None):
    """Scarica l'installatore e ne controlla l'impronta SHA-256. Restituisce il percorso del file."""
    if not info.get("setup") or not info.get("sums"):
        raise RuntimeError("la versione pubblicata non ha l'installatore o il file delle impronte")
    sums = _get(info["sums"]).decode("utf-8", "replace")
    name = info.get("setup_name") or info["setup"].rsplit("/", 1)[-1]
    want = None
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == name:
            want = parts[0].lower()
    if not want:
        raise RuntimeError("impronta dell'installatore non trovata")
    folder = os.path.join(tempfile.gettempdir(), "LagDoctor-aggiornamento")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    req = urllib.request.Request(info["setup"], headers={"User-Agent": UA})
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress and total:
                progress(done * 100 // total)
    if h.hexdigest().lower() != want:
        os.remove(path)
        raise RuntimeError("il file scaricato e' danneggiato o non e' quello pubblicato: aggiornamento annullato")
    return path


def install(setup_path):
    """Avvia l'installatore in silenzio: chiude LagDoctor, sostituisce i file e lo riapre."""
    if not paths.FROZEN:
        raise RuntimeError("l'aggiornamento automatico funziona solo nella versione installata")
    from . import gamemode
    gamemode.stop_for_update()  # la game mode usa LagDoctor.exe: va fermata (ripristinando tutto) prima
    subprocess.Popen([setup_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
                      "/AGGIORNAMENTO"], creationflags=0x00000008, close_fds=True)
