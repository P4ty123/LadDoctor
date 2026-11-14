"""Un'unica voce per tutta la virtualizzazione di Windows.

Spegne (e con Annulla riaccende) insieme:
  - Integrita' della memoria (Isolamento core)       -> registro HVCI
  - VBS e Credential Guard                            -> registro DeviceGuard / Lsa
  - Funzionalita' di Windows: Hyper-V, Piattaforma macchina virtuale, Piattaforma Windows Hypervisor, Sandbox
  - avvio dell'hypervisor                             -> bcdedit hypervisorlaunchtype
Annulla rimette ogni cosa esattamente com'era prima (riaccende solo quello che era acceso).
"""
import re

from . import tweaks as T

FEATURES = [("Microsoft-Hyper-V-All", "Hyper-V"), ("VirtualMachinePlatform", "Piattaforma macchina virtuale"),
            ("HypervisorPlatform", "Piattaforma Windows Hypervisor"),
            ("Containers-DisposableClientVM", "Sandbox di Windows")]
DG = r"SYSTEM\CurrentControlSet\Control\DeviceGuard"
REG = [("HKLM", DG, "EnableVirtualizationBasedSecurity", 0),
       ("HKLM", DG + r"\Scenarios\HypervisorEnforcedCodeIntegrity", "Enabled", 0),
       ("HKLM", r"SYSTEM\CurrentControlSet\Control\Lsa", "LsaCfgFlags", 0)]
_FEAT_LIST = ",".join("'%s'" % f for f, _ in FEATURES)


def enabled_features():
    """Nomi delle funzionalita' di virtualizzazione attive (None se non leggibile)."""
    code, out = T.ps("foreach ($n in @(%s)) { $f = Get-WindowsOptionalFeature -Online -FeatureName $n "
                     "-ErrorAction SilentlyContinue; if ($f -and $f.State.ToString() -eq 'Enabled') { 'ON:' + $n } }; "
                     "'FINE'" % _FEAT_LIST, timeout=120)
    if "FINE" not in out:
        return None
    return re.findall(r"ON:(\S+)", out)


def hypervisor_launch():
    """Valore di hypervisorlaunchtype in bcdedit (None = non impostato, cioe' Auto)."""
    code, out = T.run(["bcdedit", "/enum", "{current}"])
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].lower() == "hypervisorlaunchtype":
            return parts[-1]
    return None


class VirtualizationTweak(T.Tweak):
    def status(self):
        code, out = T.ps("$d = Get-CimInstance -Namespace root\\Microsoft\\Windows\\DeviceGuard Win32_DeviceGuard "
                         "-ErrorAction SilentlyContinue; if (-not $d) { 'unknown' } else { "
                         "$d.VirtualizationBasedSecurityStatus -ne 2 }")
        last = out.strip().splitlines()[-1].strip().lower() if out.strip() else ""
        if last not in ("true", "false"):
            return None
        feats = enabled_features()
        if feats is None:
            return None
        return last == "true" and not feats

    def apply(self):
        backup = {"reg": [], "features": [], "hv": hypervisor_launch(), "hv_set": False}
        try:
            for h, p, n, v in REG:
                prev, ptype = T.reg_read(h, p, n)
                backup["reg"].append([h, p, n, ptype, prev])
                T.reg_write(h, p, n, T.DWORD, v)
            feats = enabled_features()
            if feats is None:
                raise RuntimeError("non riesco a leggere le Funzionalita' di Windows")
            for f in feats:
                code, out = T.ps("Disable-WindowsOptionalFeature -Online -FeatureName '%s' -NoRestart "
                                 "-ErrorAction Stop | Out-Null; 'OK'" % f, timeout=600)
                if not out.strip().endswith("OK"):
                    raise RuntimeError("non riesco a disattivare %s: %s" % (f, out[-200:]))
                backup["features"].append(f)
            code, out = T.run(["bcdedit", "/set", "{current}", "hypervisorlaunchtype", "off"])
            if code != 0:
                raise RuntimeError("bcdedit non ha accettato la modifica: " + out[-200:])
            backup["hv_set"] = True
        except Exception:
            self.revert(backup)  # niente modifiche a meta'
            raise
        return backup

    def revert(self, backup):
        errors = []
        for h, p, n, ptype, prev in backup.get("reg", []):
            try:
                if prev is None:
                    T.reg_delete(h, p, n)
                else:
                    T.reg_write(h, p, n, ptype, prev)
            except Exception as e:
                errors.append(str(e))
        for f in backup.get("features", []):
            code, out = T.ps("Enable-WindowsOptionalFeature -Online -FeatureName '%s' -All -NoRestart "
                             "-ErrorAction Stop | Out-Null; 'OK'" % f, timeout=600)
            if not out.strip().endswith("OK"):
                errors.append("%s: %s" % (f, out[-150:]))
        if backup.get("hv_set"):
            if backup.get("hv") is None:
                T.run(["bcdedit", "/deletevalue", "{current}", "hypervisorlaunchtype"])
            else:
                T.run(["bcdedit", "/set", "{current}", "hypervisorlaunchtype", backup["hv"]])
        if errors:
            raise RuntimeError("; ".join(errors))


VIRT = VirtualizationTweak(
    "virt_off", "Sicurezza (PERICOLOSE)",
    "Disattiva tutta la virtualizzazione (VBS, Isolamento core, Hyper-V)",
    "Spegne insieme: Integrita' della memoria (Isolamento core), VBS e Credential Guard, e nelle Funzionalita' "
    "di Windows Hyper-V, Piattaforma macchina virtuale, Piattaforma Windows Hypervisor e Sandbox. "
    "Annulla rimette tutto esattamente com'era.", "media", risk=3, reboot=True, group="virt",
    warning="Riduce la protezione contro driver e malware a livello kernel. Smettono di funzionare WSL2, Docker, "
            "macchine virtuali, Sandbox ed emulatori Android. Alcuni anti-cheat recenti possono richiedere "
            "l'Integrita' della memoria. Con BitLocker tieni a portata la chiave di ripristino.",
    recommend=lambda s: None,
    source="Microsoft: 'Options to optimize gaming performance in Windows 11'; Tom's Hardware")

OLD_IDS = ("hvci_off", "vbs_off", "vmp_off", "hypervisor_off")


def register():
    old = [t for t in T.CATALOG if t.id in OLD_IDS]
    for t in old:
        t.group = "virt"  # se una vecchia voce era applicata, viene annullata prima di applicare quella nuova
    T.CATALOG[:] = [t for t in T.CATALOG if t.id not in OLD_IDS]
    T.CATALOG.append(VIRT)
    T.CATALOG.sort(key=lambda t: T.CAT_ORDER.index(t.cat))
    # niente clear(): BY_ID contiene anche voci tolte dal catalogo che devono restare annullabili
    T.BY_ID.update({t.id: t for t in T.CATALOG})
    T.BY_ID.update({t.id: t for t in old})  # restano annullabili se applicate con una versione precedente
