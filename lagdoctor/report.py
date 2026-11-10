"""Crea il report HTML (si apre nel browser)."""
import datetime
import html

SEV = {3: ("ALTA", "#e5484d"), 2: ("MEDIA", "#f5a524"), 1: ("BASSA", "#3e9bff")}


def _frametime_svg(frametimes, stutters, width=1000, height=260):
    if not frametimes:
        return ""
    n = len(frametimes)
    buckets = min(width, n)
    per = n / buckets
    pts_max, pts_med = [], []
    for b in range(buckets):
        chunk = frametimes[int(b * per):max(int((b + 1) * per), int(b * per) + 1)]
        pts_max.append(max(chunk))
        pts_med.append(sorted(chunk)[len(chunk) // 2])
    srt = sorted(frametimes)
    top = max(srt[int(n * 0.999) - 1] * 1.3 if n > 10 else srt[-1], 20)
    top = min(max(top, max(s[2] for s in stutters) if stutters else 0), 250)

    def y(v):
        return height - min(v, top) / top * (height - 10)

    def line(vals):
        step = width / max(len(vals) - 1, 1)
        return " ".join("%.1f,%.1f" % (i * step, y(v)) for i, v in enumerate(vals))

    grid = ""
    for ms in (8.3, 16.7, 33.3, 50, 100, 200):
        if ms < top:
            grid += ('<line x1="0" x2="%d" y1="%.1f" y2="%.1f" class="grid"/>'
                     '<text x="4" y="%.1f" class="lbl">%g ms (%d FPS)</text>'
                     % (width, y(ms), y(ms), y(ms) - 3, ms, round(1000 / ms)))
    total = sum(frametimes) / 1000.0
    marks = "".join('<line x1="%.1f" x2="%.1f" y1="0" y2="%d" class="st"/>'
                    % (s[1] / total * width, s[1] / total * width, height) for s in stutters if s[2] >= 50)
    return ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" class="chart">%s%s'
            '<polyline points="%s" class="ftmax"/><polyline points="%s" class="ftmed"/></svg>'
            % (width, height, grid, marks, line(pts_max), line(pts_med)))


def _factors_html(factors):
    if not factors:
        return ""
    out = "<h2>Impostazioni del tuo PC collegate a questi stutter</h2>"
    for f in factors:
        out += '<div class="card" style="margin-bottom:10px"><b>%s</b>' % html.escape(f["titolo"])
        if f["peggiora"]:
            out += '<p style="color:#e5484d;margin:8px 0 4px">Attive ora e PEGGIORANO il problema:</p><ul>'
            out += "".join("<li><b>%s</b> - %s</li>" % (html.escape(x.get("label") or x["name"]),
                                                          html.escape(x["why"] or "")) for x in f["peggiora"])
            out += "</ul>"
        if f["aiuta"]:
            out += '<p style="color:#46c37b;margin:8px 0 4px">Non attive, potrebbero AIUTARE:</p><ul>'
            out += "".join("<li><b>%s</b> - %s</li>" % (html.escape(x["name"]), html.escape(x["why"] or ""))
                           for x in f["aiuta"])
            out += "</ul>"
        out += "</div>"
    return out + '<p class="mut">Puoi applicarle da LagDoctor > Ottimizzazioni e verificarle con il test Prima / Dopo.</p>'


KIND_COLORS = {"dpc": "#e5484d", "disk": "#f5a524", "paging": "#ff7a45", "vram": "#c084fc", "background": "#facc15",
               "cpu_throttle": "#fb923c", "gpu_throttle": "#f97316", "shader": "#3e9bff", "main_thread": "#22d3ee",
               "gpu_spike": "#a3e635", "vsync": "#94a3b8", "present": "#e879f9", "system": "#64748b"}


def _breakdown_html(summary):
    if not summary or not summary.get("kinds"):
        return ""
    bar = "".join('<div title="%s" style="width:%.2f%%;background:%s"></div>' % (html.escape(k[3]), k[2],
                                                                              KIND_COLORS.get(k[0], "#888"))
                  for k in summary["kinds"])
    legend = "".join('<div><span style="background:%s"></span>%s: <b>%d</b> (%.0f%%)</div>'
                     % (KIND_COLORS.get(k[0], "#888"), html.escape(k[3]), k[1], k[2]) for k in summary["kinds"])
    b = summary.get("bound")
    bound = ("<p class='mut'>Collo di bottiglia frame per frame (non e' l'utilizzo): il limite era la GPU nel %.0f%% "
             "dei frame, la CPU nel %.0f%%, il V-Sync o un limite FPS nel %.0f%%.%s</p>"
             % (b["gpu"], b["cpu"], b["limitato"], (" Utilizzo medio della GPU: %.0f%%." % summary["gpu_util_avg"])
                if summary.get("gpu_util_avg") is not None else "")) if b else ""
    return ('<h2>Di cosa sono fatti gli stutter</h2><div class="card"><div class="kbar">%s</div>'
            '<div class="klegend">%s</div>%s<p class="mut" style="font-size:13px">Ogni stutter e\' stato classificato '
            'guardando quale parte del frame si e\' allungata (lavoro CPU, lavoro GPU o attesa) e cosa succedeva nel '
            'sistema in quel quarto di secondo.</p></div>') % (bar, legend, bound)


def build(path, game_name, stats, stutters, frametimes, problems, info, sysinfo, drive, factors=None,
          detail=None, summary=None):
    rows = ""
    for p in problems:
        label, color = SEV[p["gravita"]]
        auto = '<span class="auto">Correzione automatica disponibile</span>' if p.get("auto_fix") else ""
        rows += ('<div class="prob" style="border-left-color:%s"><div class="ph"><span class="sev" '
                 'style="background:%s">%s</span><b>%s</b>%s</div><p>%s</p><p class="fix"><b>Come risolvere:</b> '
                 '%s</p></div>' % (color, color, label, html.escape(p["titolo"]), auto,
                                   html.escape(p["spiegazione"]), html.escape(p["soluzione"])))
    if not problems:
        rows = '<div class="prob ok"><b>Nessun problema trovato.</b> Il tuo sistema e il gioco vanno bene.</div>'

    gpu = sysinfo.get("gpu") or {}
    sys_rows = [
        ("CPU", sysinfo.get("cpu")),
        ("GPU", "%s (driver %s, %s MB VRAM)" % (gpu.get("name"), gpu.get("driver"), gpu.get("vram_mb"))
         if gpu else "non rilevata"),
        ("RAM", sysinfo.get("ram")),
        ("Monitor", "%s Hz" % sysinfo.get("refresh_hz") if sysinfo.get("refresh_hz") else "?"),
        ("Piano energetico", sysinfo.get("power_plan") or "?"),
        ("Pianificazione GPU hardware (HAGS)", {True: "attiva", False: "disattivata"}.get(sysinfo.get("hags"), "?")),
        ("Disco del gioco", "%s: %s %s, %.0f GB liberi" % (drive.get("lettera"), drive.get("tipo", "?"),
                                                           drive.get("bus", ""), drive.get("libero_gb", 0))),
    ]
    sys_html = "".join("<tr><td>%s</td><td>%s</td></tr>" % (html.escape(k), html.escape(str(v)))
                       for k, v in sys_rows)
    info_html = "".join("<li>%s</li>" % html.escape(i) for i in info)

    if detail:
        worst = sorted(detail, key=lambda x: -x["ft"])[:15]
        worst_html = "".join(
            "<tr><td>%d:%02d</td><td>%.1f ms</td><td>%.1f ms</td><td><b>%s</b><br><span class='mut'>%s%s</span></td>"
            "<td>%s</td></tr>" % (x["t"] // 60, x["t"] % 60, x["ft"], x["med"], html.escape(x["label"]),
                                  html.escape(x["evidence"] or ""), (" &middot; " + html.escape(x["detail"]))
                                  if x.get("detail") else "", x["conf"]) for x in worst)
    else:
        worst = sorted(stutters, key=lambda s: -s[2])[:10]
        worst_html = "".join("<tr><td>%d:%02d</td><td>%.1f ms</td><td>%.1f ms</td><td></td><td></td></tr>"
                             % (s[1] // 60, s[1] % 60, s[2], s[3]) for s in worst)

    page = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>LagDoctor - %(game)s</title>
<style>
:root{--bg:#0f1115;--card:#181b22;--fg:#e8eaf0;--mut:#9aa3b2;--line:#2a2f3a}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 "Segoe UI",system-ui,sans-serif}
main{max-width:1060px;margin:0 auto;padding:24px 16px}
h1{margin:0 0 4px;font-size:26px}h2{font-size:18px;margin:28px 0 10px}.mut{color:var(--mut)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:var(--card);border-radius:10px;padding:12px 14px}.kpi b{display:block;font-size:24px}
.kpi span{color:var(--mut);font-size:13px}
.card{background:var(--card);border-radius:10px;padding:14px}
.chart{width:100%%;height:260px;display:block}
.ftmax{fill:none;stroke:#e5484d;stroke-width:1}.ftmed{fill:none;stroke:#46c37b;stroke-width:1.5}
.grid{stroke:var(--line);stroke-dasharray:4 4}.lbl{fill:var(--mut);font-size:11px}
.st{stroke:#e5484d;stroke-opacity:.25;stroke-width:3}
.prob{background:var(--card);border-left:5px solid;border-radius:8px;padding:12px 14px;margin-bottom:10px}
.prob.ok{border-left-color:#46c37b}.prob p{margin:6px 0}.fix{color:#cfe3ff}
.ph{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.sev{color:#000;font-size:11px;font-weight:700;padding:2px 7px;border-radius:5px}
.auto{font-size:12px;color:#46c37b;border:1px solid #46c37b;border-radius:5px;padding:1px 6px}
table{border-collapse:collapse;width:100%%}td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
td:first-child{color:var(--mut)}
.kbar{display:flex;height:22px;border-radius:6px;overflow:hidden;margin-bottom:10px}
.klegend{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:4px 16px;font-size:13px}
.klegend span{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}
</style></head><body><main>
<h1>Report stutter: %(game)s</h1><div class="mut">%(date)s, registrazione di %(dur)s</div>
<h2>Risultati</h2><div class="kpis">
<div class="kpi"><b>%(fps).0f</b><span>FPS medi</span></div>
<div class="kpi"><b>%(low1).0f</b><span>1%% low (FPS nei momenti peggiori)</span></div>
<div class="kpi"><b>%(low01).0f</b><span>0.1%% low</span></div>
<div class="kpi"><b>%(nst)d</b><span>stutter (%(stm).1f al minuto)</span></div>
<div class="kpi"><b>%(maxft).0f ms</b><span>frame piu' lungo</span></div></div>
<h2>Frame time</h2><div class="card">%(svg)s
<div class="mut" style="font-size:13px;margin-top:6px">Verde = andamento normale, rosso = frame peggiori.
I picchi rossi sono gli scatti che senti. Piu' la linea e' piatta, piu' il gioco e' fluido.</div></div>
%(breakdown)s
<h2>Problemi trovati e soluzioni</h2>%(rows)s
%(factors)s
<h2>Altre informazioni</h2><div class="card"><ul>%(info)s</ul></div>
<h2>Gli stutter peggiori, uno per uno</h2><div class="card"><table><tr><th>Momento</th><th>Durata frame</th>
<th>Normale</th><th>Causa e prove misurate</th><th>Certezza</th></tr>%(worst)s</table></div>
<h2>Il tuo sistema</h2><div class="card"><table>%(sys)s</table></div>
</main></body></html>""" % dict(
        game=html.escape(game_name), date=datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        dur="%d min %02d s" % (stats["durata_s"] // 60, stats["durata_s"] % 60),
        fps=stats["fps_medi"], low1=stats["fps_1low"], low01=stats["fps_01low"], nst=len(stutters),
        stm=len(stutters) / max(stats["durata_s"] / 60, 0.01), maxft=stats["ft_max"],
        svg=_frametime_svg(frametimes, stutters), rows=rows, info=info_html,
        factors=_factors_html(factors), breakdown=_breakdown_html(summary),
        worst=worst_html or '<tr><td colspan="5">Nessuno</td></tr>', sys=sys_html)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
