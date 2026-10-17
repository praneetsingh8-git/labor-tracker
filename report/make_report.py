#!/usr/bin/env python3
"""Build Aveer's 3-day report (PDF + email HTML + subject) from tracker rows.

Usage: python3 report/make_report.py --data rows.json [--now 2026-10-15T07:52] [--out out/]
rows.json: a JSON array of lt_events rows (id, type, start_ts, end_ts, data, deleted).
Writes out/report.pdf, out/email.html, out/meta.json.
"""
import argparse, json, pathlib, datetime as dt
from zoneinfo import ZoneInfo
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart

TZ = ZoneInfo("America/Toronto")
ROOT = pathlib.Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "content.js").read_text().split("=", 1)[1].rstrip().rstrip(";"))
BIRTH = dt.datetime.fromisoformat(C["birth"]).replace(tzinfo=TZ)
BABY, MOM, SURNAME = C["baby"], C["mom"], C["surname"]
DAILY = {"synthroid": "Synthroid", "pregpink": "Pregvit pink", "pregblue": "Pregvit blue", "iron": "Iron (Heme Boost)"}
PRN = {"acet": ("Acetaminophen 500 mg", 8), "ibu": ("Ibuprofen 400 mg", 6)}

INK, MUTED, ACCENT, GOOD, WARN, BAD = (colors.HexColor(x) for x in ("#1f1b24", "#6f6774", "#e8684a", "#2fa57a", "#c98a00", "#d64554"))
SERIES = [colors.HexColor("#e8684a"), colors.HexColor("#4f8fd6"), colors.HexColor("#8a6d3b")]


def day_start(n):  # calendar day n of life, midnight to midnight
    d = BIRTH.date() + dt.timedelta(days=n - 1)
    return dt.datetime(d.year, d.month, d.day, 0, 0, tzinfo=TZ)  # calendar days, midnight to midnight


def day_of(t):
    n = max(1, int((t - BIRTH).total_seconds() // 86400) + 1)
    while n > 1 and t < day_start(n): n -= 1
    while t >= day_start(n + 1): n += 1
    return n


def wet_min(n): return C["wetMin"].get(str(n), 6)


def tip_for(n):
    tip = C["tips"][0]
    for x in C["tips"]:
        if x["from"] <= n: tip = x
    return tip


def ms(t): return dt.datetime.fromtimestamp(t / 1000, TZ)
def hm(t): return t.strftime("%-I:%M %p")
def md(t): return t.strftime("%b %-d")
def fmt_kg(kg):
    lb = kg * 2.20462; l = int(lb); oz = round((lb - l) * 16)
    if oz == 16: l, oz = l + 1, 0
    return f"{kg:.2f} kg ({l} lb {oz} oz)"


class Data:
    def __init__(self, rows):
        self.ev = []
        for r in rows:
            if r.get("deleted"): continue
            d = r.get("data") or {}
            if isinstance(d, str): d = json.loads(d)
            self.ev.append({"id": r["id"], "type": r["type"], "start": ms(int(r["start_ts"])),
                            "end": ms(int(r["end_ts"])) if r.get("end_ts") not in (None, "") else None, "data": d})
        self.ev.sort(key=lambda e: e["start"])
        st = [e for e in self.ev if e["type"] == "settings" and e["data"].get("mergeMin") is not None]
        self.merge_s = float(st[-1]["data"]["mergeMin"]) * 60 if st else 45 * 60

    def of(self, *types): return [e for e in self.ev if e["type"] in types]

    def day(self, n):
        a, b = day_start(n), day_start(n + 1)
        inside = [e for e in self.ev if a <= e["start"] < b]
        feeds = [e for e in inside if e["type"] == "feed"]
        sessions, last = 0, None
        for f in feeds:  # same rule as the app: explicit flag, else resumed within merge window
            c = f["data"].get("cont")
            if last is None or c is False or (c is not True and (f["start"] - last).total_seconds() > self.merge_s): sessions += 1
            last = max(last, f["end"] or f["start"]) if last and c is not False else (f["end"] or f["start"])
        dia = [e for e in inside if e["type"] == "diaper"]
        breast_min = sum(((f["end"] - f["start"]).total_seconds() / 60) for f in feeds if f["data"].get("kind") == "breast" and f["end"])
        sleep_h = 0.0
        for s in self.of("sleep"):
            e = s["end"] or min(b, dt.datetime.now(TZ))
            sleep_h += max(0, (min(e, b) - max(s["start"], a)).total_seconds()) / 3600
        meds = [e for e in inside if e["type"] == "med"]
        return {"n": n, "a": a, "b": b, "feeds": sessions, "breast_min": round(breast_min),
                "bottle_ml": round(sum(f["data"].get("ml") or 0 for f in feeds)),
                "wet": sum(1 for d in dia if d["data"].get("kind") in ("wet", "both")),
                "dirty": sum(1 for d in dia if d["data"].get("kind") in ("dirty", "both")),
                "sleep_h": round(sleep_h, 1), "meds": meds,
                "logged": bool(feeds or dia),
                "sparse": sessions < 4 and len(dia) < 2}


def trend(vals, unit=""):
    s = " > ".join(f"{v:g}{unit}" for v in vals)
    if len(vals) < 2: return s
    d = vals[-1] - vals[0]
    word = "steady" if abs(d) < 1e-9 else (f"up {d:g}{unit}" if d > 0 else f"down {abs(d):g}{unit}")
    return f"{s} ({word})"


def build(rows, now, out):
    D = Data(rows)
    last_complete = day_of(now) - 1
    if last_complete < 1:
        raise SystemExit("No complete day of life yet")
    days = [D.day(n) for n in range(max(1, last_complete - 2), last_complete + 1)]
    p_from, p_to = days[0]["a"], days[-1]["b"]
    period = f"{md(days[0]['a'])} to {md(days[-1]['a'])}"

    # ---- labor & birth (only when the report starts at day 1)
    labor = []
    if days[0]["n"] == 1:
        cs = [e for e in D.of("contraction") if e["start"] < BIRTH and e["end"]]
        if cs:
            durs = [x for x in ((e["end"] - e["start"]).total_seconds() for e in cs) if x <= 240] or [0]
            last_hr = [e for e in cs if e["start"] >= cs[-1]["start"] - dt.timedelta(hours=1)]
            gaps = [(b["start"] - a["start"]).total_seconds() / 60 for a, b in zip(last_hr, last_hr[1:])]
            labor.append(f"{len(cs)} contractions timed from {cs[0]['start'].strftime('%a %b %-d, %-I:%M %p')} to {cs[-1]['start'].strftime('%-I:%M %p')}; average length {sum(durs) / len(durs):.0f} s.")
            if gaps: labor.append(f"Last tracked hour: {len(last_hr)} contractions, about {sum(gaps) / len(gaps):.1f} min apart.")
        for n in [e for e in D.of("note") if e["start"] <= BIRTH + dt.timedelta(minutes=1)]:
            labor.append(f"{n['start'].strftime('%a %-I:%M %p')}: {n['data'].get('text', '')}")
        if not any("deliver" in (n["data"].get("text") or "").lower() or "born" in (n["data"].get("text") or "").lower() for n in D.of("note")):
            labor.append(f"{BABY} was born {BIRTH.strftime('%A %b %-d at %-I:%M %p')}.")
        first = min([e["start"] for e in D.of("contraction", "note") if e["start"] < BIRTH] or [BIRTH])
        period = f"{md(first)} to {md(days[-1]['a'])}"

    # ---- status
    logged = [d for d in days if d["logged"] and not d["sparse"]]
    latest = days[-1]
    below = lambda d: d["logged"] and not d["sparse"] and (d["wet"] < wet_min(d["n"]) or d["feeds"] < C["feedsMin"])
    flags = []
    for d in days:
        if not d["logged"] or d["sparse"]:
            flags.append(f"Day {d['n']} looks incompletely logged ({d['feeds']} feed{'s' if d['feeds'] != 1 else ''}, {d['wet'] + d['dirty']} diaper{'s' if d['wet'] + d['dirty'] != 1 else ''} recorded), so its numbers aren't reliable.")
    if below(latest):
        flags.append(f"Day {latest['n']} was below the typical range ({latest['feeds']} feeds, {latest['wet']} wet diapers vs {C['feedsMin']}+ feeds and {wet_min(latest['n'])}+ wet). "
                     "If this wasn't just missed logging, call your doctor or Health811 (dial 811).")
    for d in days:
        for k, (name, mx) in PRN.items():
            tabs = sum(m["data"].get("tablets") or 0 for m in d["meds"] if m["data"].get("med") == k)
            if tabs > mx: flags.append(f"{MOM}: {name} {tabs} tablets on day {d['n']} (form max {mx}).")
    if below(latest): smiley = "\U0001F610"          # neutral face
    elif flags or len(logged) < len(days) or any(below(d) for d in days): smiley = "\U0001F642"  # slight smile
    else: smiley = "\U0001F60A"                       # smiling
    status_text = {"\U0001F60A": "All good: feeds and wet diapers were in the typical range every day.",
                   "\U0001F642": "Mostly good, with a few things to look at below.",
                   "\U0001F610": "Needs attention: see the notes below."}[smiley]

    # ---- changes
    ns = [d["n"] for d in days]
    changes = [
        f"Feeds per day: {trend([d['feeds'] for d in days])}. Typical is {C['feedsMin']}+.",
        f"Wet diapers: {trend([d['wet'] for d in days])}. Typical for day {ns[-1]} is {wet_min(ns[-1])}+, and 6+ from day 5.",
        f"Dirty diapers: {trend([d['dirty'] for d in days])}.",
        f"Sleep logged: {trend([d['sleep_h'] for d in days], ' h')}.",
    ]
    if any(d["breast_min"] for d in days): changes.append(f"Breastfeeding minutes: {trend([d['breast_min'] for d in days], ' min')}.")
    if any(d["bottle_ml"] for d in days): changes.append(f"Bottle volume: {trend([d['bottle_ml'] for d in days], ' ml')}.")
    weights = sorted([(e["start"], e["data"].get("kg") or e["data"].get("weightKg")) for e in D.of("growth", "visit")
                      if (e["data"].get("kg") or e["data"].get("weightKg"))], key=lambda x: x[0])
    if any(d["sparse"] or not d["logged"] for d in days):
        changes.insert(0, "Some days were incompletely logged, so drops below may reflect missed entries rather than real changes.")
    if weights:
        w_txt = f"Latest weight {fmt_kg(weights[-1][1])} on {md(weights[-1][0])}"
        if len(weights) > 1: w_txt += f" ({(weights[-1][1] - weights[0][1]) * 1000:+.0f} g since {md(weights[0][0])})"
        changes.append(w_txt + ".")

    # ---- mom
    mom_rows = [["", *[f"Day {d['n']}" for d in days]]]
    for k, name in DAILY.items():
        mom_rows.append([name, *[", ".join(hm(m["start"]) for m in d["meds"] if m["data"].get("med") == k) or "not logged" for d in days]])
    for k, (name, mx) in PRN.items():
        mom_rows.append([name, *[f"{sum(m['data'].get('tablets') or 0 for m in d['meds'] if m['data'].get('med') == k)} tabs" for d in days]])
    pains = [m["data"]["pain"] for d in days for m in d["meds"] if m["data"].get("pain") is not None]
    stock = next((e for e in reversed(D.of("stock")) if e["data"].get("med") == "synthroid"), None)
    synth_left = None
    if stock:
        used = sum(m["data"].get("tablets") or 1 for m in D.of("med") if m["data"].get("med") == "synthroid" and m["start"] > stock["start"])
        synth_left = stock["data"]["count"] - used
    mom_notes = []
    if synth_left is not None:
        mom_notes.append(f"Synthroid: {max(0, synth_left)} pills left (about {max(0, synth_left)} days)." + (" Request a refill now." if synth_left <= 7 else ""))
    if pains: mom_notes.append(f"Pain scores logged: average {sum(pains) / len(pains):.1f}/10, latest {pains[-1]}/10.")

    # ---- health
    visits = [e for e in D.of("visit") if p_from <= e["start"] < p_to]
    open_fu = sorted([(f.get("due") or "9999", f["text"], v) for v in D.of("visit") for f in (v["data"].get("followups") or []) if not f.get("done")], key=lambda x: x[0])
    need_summary = [v["id"] for v in D.of("visit") if v["data"].get("transcript") and not v["data"].get("ai_summary")]

    # ---- documents
    reg_state = {e["data"].get("key"): e["data"] for e in D.of("task")}
    docs_due = []
    for r in C["regs"]:
        st = reg_state.get(r["key"], {})
        if st.get("done") or r["due_days"] is None: continue
        due = day_start(1) + dt.timedelta(days=r["due_days"])
        left = (due - now).days
        if left <= 14: docs_due.append((left, f"{r['title']}: due {md(due)}" + (f" ({abs(left)} day{'s' if abs(left) != 1 else ''} overdue)" if left < 0 else f" ({left} day{'s' if left != 1 else ''} left)")))
    docs_due.sort()
    req = [r for r in C["regs"] if r["group"] == "Required"]
    req_done = sum(1 for r in req if reg_state.get(r["key"], {}).get("done"))

    # ---- milestones in period
    ms_hits = [e for e in D.of("milestone") if p_from <= e["start"] < p_to]

    # ---- next 3 days
    nxt = []
    for n in range(last_complete + 1, last_complete + 4):
        a = day_start(n)
        nxt.append((f"Day {n} ({a.strftime('%a %b %-d')})", f"Aim for {C['feedsMin']}+ feeds and {wet_min(n)}+ wet diapers. {tip_for(n)['today']}"))
    prep = tip_for(last_complete + 3)["next"]
    horizon = day_start(last_complete + 4)
    upcoming = [f"Follow-up: {t}" + (f" (due {d})" if d != "9999" else "") for d, t, v in open_fu
                if d == "9999" or dt.date.fromisoformat(d) <= horizon.date()]

    subject = f"{BABY} {SURNAME} - Report Period {period} - {smiley}"
    meta = {"subject": subject, "period": period, "smiley": smiley, "days": [d["n"] for d in days],
            "pdf": "report.pdf", "need_summary_visit_ids": need_summary, "flags": flags}

    out.mkdir(parents=True, exist_ok=True)
    make_pdf(out / "report.pdf", period, labor, days, status_text, smiley, flags, changes, mom_rows, mom_notes,
             visits, open_fu, docs_due, req_done, len(req), ms_hits, nxt, prep, upcoming)
    (out / "email.html").write_text(make_html(period, labor, days, status_text, flags, changes, mom_rows, mom_notes,
                                              open_fu, docs_due, ms_hits, nxt, prep, upcoming))
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


# ---------------- PDF ----------------
def styles():
    base = dict(fontName="Helvetica", textColor=INK, leading=14, fontSize=10)
    return {"h1": ParagraphStyle("h1", **{**base, "fontName": "Helvetica-Bold", "fontSize": 20, "leading": 24}),
            "h2": ParagraphStyle("h2", **{**base, "fontName": "Helvetica-Bold", "fontSize": 13, "leading": 17, "textColor": ACCENT, "spaceBefore": 10, "spaceAfter": 4}),
            "p": ParagraphStyle("p", **base),
            "small": ParagraphStyle("s", **{**base, "fontSize": 8.5, "textColor": MUTED, "leading": 11}),
            "li": ParagraphStyle("li", **{**base, "leftIndent": 10, "bulletIndent": 0, "spaceAfter": 2})}


def bar_chart(title, labels, series, names, unit=""):
    d = Drawing(250, 150)
    d.add(String(0, 138, title, fontName="Helvetica-Bold", fontSize=10, fillColor=INK))
    c = VerticalBarChart()
    c.x, c.y, c.width, c.height = 28, 30, 215, 95
    c.data = series
    c.categoryAxis.categoryNames = labels
    c.categoryAxis.labels.fontName = c.valueAxis.labels.fontName = "Helvetica"
    c.categoryAxis.labels.fontSize = c.valueAxis.labels.fontSize = 8
    c.valueAxis.valueMin = 0
    top = max([max(s) for s in series] + [1])
    c.valueAxis.valueMax = top * 1.25
    c.valueAxis.valueStep = max(1, round(top / 4)) if top >= 4 else 1
    c.valueAxis.strokeColor = c.categoryAxis.strokeColor = colors.HexColor("#cccccc")
    c.barSpacing, c.groupSpacing = 2, 10
    c.barLabelFormat, c.barLabels.fontSize, c.barLabels.nudge = "%g", 7.5, 6
    for i in range(len(series)):
        c.bars[i].fillColor = SERIES[i]; c.bars[i].strokeColor = None
    d.add(c)
    x = 28
    for i, n in enumerate(names):
        d.add(String(x + 10, 6, n, fontName="Helvetica", fontSize=8, fillColor=MUTED))
        from reportlab.graphics.shapes import Rect
        d.add(Rect(x, 6, 7, 7, fillColor=SERIES[i], strokeColor=None))
        x += 10 + len(n) * 4.6 + 14
    return d


def make_pdf(path, period, labor, days, status_text, smiley, flags, changes, mom_rows, mom_notes,
             visits, open_fu, docs_due, req_done, req_total, ms_hits, nxt, prep, upcoming):
    S = styles()
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.7 * inch, rightMargin=0.7 * inch, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            title=f"{BABY} {SURNAME} report {period}", author="Aveer tracker", compress=1)
    f = []
    f.append(Paragraph(f"{BABY} {SURNAME} &middot; 3-day report", S["h1"]))
    f.append(Paragraph(f"{period} &middot; days {days[0]['n']}-{days[-1]['n']} of life (midnight to midnight) &middot; generated {dt.datetime.now(TZ).strftime('%b %-d, %-I:%M %p')}", S["small"]))
    f.append(Spacer(1, 8))
    col = {"\U0001F60A": GOOD, "\U0001F642": WARN, "\U0001F610": BAD}[smiley]
    box = Table([[Paragraph(f"<b>{status_text}</b>", ParagraphStyle("st", parent=S["p"], textColor=colors.white, fontSize=11, leading=15))]],
                colWidths=[7.1 * inch], style=[("BACKGROUND", (0, 0), (-1, -1), col), ("BOX", (0, 0), (-1, -1), 0, col),
                                               ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)])
    f.append(box)
    for fl in flags: f.append(Paragraph(fl, S["li"], bulletText="!"))

    # KPI table
    hdr = ["", *[f"Day {d['n']}\n{d['a'].strftime('%b %-d')}" for d in days]]
    rows = [hdr,
            ["Feeds", *[str(d["feeds"]) for d in days]],
            ["Wet diapers", *[f"{d['wet']} (typ {wet_min(d['n'])}+)" for d in days]],
            ["Dirty diapers", *[str(d["dirty"]) for d in days]],
            ["Breastfeeding", *[f"{d['breast_min']} min" for d in days]],
            ["Bottle", *[f"{d['bottle_ml']} ml" for d in days]],
            ["Sleep logged", *[f"{d['sleep_h']:g} h" for d in days]]]
    if labor:
        f.append(Paragraph("Labor & birth", S["h2"]))
        for x in labor: f.append(Paragraph(esc(x), S["li"], bulletText="\u2022"))
    f.append(Paragraph(f"{BABY} at a glance", S["h2"]))
    f.append(Table(rows, colWidths=[1.6 * inch] + [5.5 * inch / len(days)] * len(days), style=table_style()))
    labels = [f"Day {d['n']}" for d in days]
    charts = Table([[bar_chart("Feeds & diapers", labels, [[d["feeds"] for d in days], [d["wet"] for d in days], [d["dirty"] for d in days]], ["Feeds", "Wet", "Dirty"]),
                     bar_chart("Sleep logged (hours)", labels, [[d["sleep_h"] for d in days]], ["Sleep"])]], colWidths=[3.55 * inch, 3.55 * inch])
    f.append(Spacer(1, 6)); f.append(charts)
    f.append(Paragraph("What changed", S["h2"]))
    for c in changes: f.append(Paragraph(c, S["li"], bulletText="•"))

    f.append(Paragraph(f"{MOM}'s medicines", S["h2"]))
    f.append(Table(mom_rows, colWidths=[1.6 * inch] + [5.5 * inch / len(days)] * len(days), style=table_style()))
    for n in mom_notes: f.append(Paragraph(n, S["li"], bulletText="•"))

    f.append(Paragraph("Health", S["h2"]))
    if visits:
        for v in visits:
            d = v["data"]
            txt = f"<b>{md(v['start'])} &middot; {esc(d.get('kind', 'Visit'))}</b>{' &middot; ' + esc(d['provider']) if d.get('provider') else ''}"
            if d.get("weightKg"): txt += f" &middot; {fmt_kg(d['weightKg'])}"
            f.append(Paragraph(txt, S["p"]))
            if d.get("notes"): f.append(Paragraph(esc(d["notes"]), S["li"]))
            if d.get("ai_summary"): f.append(Paragraph("<i>Summary (AI):</i> " + esc(d["ai_summary"]), S["li"]))
    else:
        f.append(Paragraph("No visits logged in this period.", S["p"]))
    if open_fu:
        f.append(Paragraph("<b>Open follow-ups</b>", S["p"]))
        for due, t, v in open_fu: f.append(Paragraph(esc(t) + (f" &middot; due {due}" if due != "9999" else ""), S["li"], bulletText="•"))

    f.append(Paragraph("Documents & registrations", S["h2"]))
    f.append(Paragraph(f"{req_done} of {req_total} required items done.", S["p"]))
    for _, t in docs_due: f.append(Paragraph(esc(t), S["li"], bulletText="•"))
    if ms_hits:
        f.append(Paragraph("Milestones & moments", S["h2"]))
        for m in ms_hits: f.append(Paragraph(f"{md(m['start'])}: {esc(m['data'].get('title', ''))}" + (f" - {esc(m['data']['note'])}" if m["data"].get("note") else ""), S["li"], bulletText="*"))

    nx = [Paragraph("What to expect in the next 3 days", S["h2"])]
    for h, t in nxt: nx.append(Paragraph(f"<b>{h}</b> &middot; {esc(t)}", S["li"], bulletText="•"))
    nx.append(Paragraph(f"<b>Be ready:</b> {esc(prep)}", S["p"]))
    for u in upcoming: nx.append(Paragraph(esc(u), S["li"], bulletText="•"))
    f.append(KeepTogether(nx))
    f.append(Spacer(1, 10))
    f.append(Paragraph("Built from what was logged in the tracker; days with missed logging will look low. General guidance only, not medical advice. "
                       "For a baby under 3 months, a rectal temperature of 38.0 C or higher needs medical care right away. Health811: dial 811.", S["small"]))
    doc.build(f)


def table_style():
    return TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 9), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9), ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                       ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f6eee9")),
                       ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf8f7")]),
                       ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e6e0dc")), ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                       ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)])


def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------- Email HTML (inline styles for Gmail) ----------------
def make_html(period, labor, days, status_text, flags, changes, mom_rows, mom_notes, open_fu, docs_due, ms_hits, nxt, prep, upcoming):
    td = 'style="padding:6px 8px;border-bottom:1px solid #eee;text-align:center"'
    tl = 'style="padding:6px 8px;border-bottom:1px solid #eee;font-weight:bold"'
    h2 = 'style="color:#e8684a;font-size:16px;margin:18px 0 6px"'
    head = "".join(f'<th {td}>Day {d["n"]}<br><span style="color:#888;font-weight:normal">{d["a"].strftime("%b %-d")}</span></th>' for d in days)
    def row(name, vals): return f"<tr><td {tl}>{name}</td>" + "".join(f"<td {td}>{v}</td>" for v in vals) + "</tr>"
    li = lambda xs: "<ul style='padding-left:18px;margin:4px 0'>" + "".join(f"<li style='margin:3px 0'>{esc(x)}</li>" for x in xs) + "</ul>" if xs else ""
    html = f"""<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1f1b24;max-width:640px;margin:auto">
<h1 style="font-size:22px;margin:0">{BABY} {SURNAME} &middot; 3-day report</h1>
<div style="color:#6f6774;font-size:13px">{period} &middot; days {days[0]['n']}-{days[-1]['n']} of life</div>
<div style="background:#f6eee9;border-radius:10px;padding:12px 14px;margin:14px 0;font-weight:bold">{esc(status_text)}</div>
{li(flags)}
{f'<h2 {h2}>Labor &amp; birth</h2>' + li(labor) if labor else ''}
<table style="border-collapse:collapse;width:100%;font-size:14px"><tr><th {tl}></th>{head}</tr>
{row("Feeds", [d["feeds"] for d in days])}{row("Wet diapers", [f"{d['wet']} <span style='color:#888'>(typ {wet_min(d['n'])}+)</span>" for d in days])}
{row("Dirty diapers", [d["dirty"] for d in days])}{row("Breastfeeding", [f"{d['breast_min']} min" for d in days])}
{row("Bottle", [f"{d['bottle_ml']} ml" for d in days])}{row("Sleep logged", [f"{d['sleep_h']:g} h" for d in days])}</table>
<h2 {h2}>What changed</h2>{li(changes)}
<h2 {h2}>{MOM}'s medicines</h2><table style="border-collapse:collapse;width:100%;font-size:13px">
{"".join(row(r[0], r[1:]) for r in mom_rows[1:])}</table>{li(mom_notes)}
<h2 {h2}>Follow-ups &amp; documents</h2>{li([t + (f' (due {d})' if d != '9999' else '') for d, t, v in open_fu] + [t for _, t in docs_due]) or '<p>Nothing due.</p>'}
{f'<h2 {h2}>Milestones</h2>' + li([md(m['start']) + ': ' + m['data'].get('title', '') for m in ms_hits]) if ms_hits else ''}
<h2 {h2}>Next 3 days</h2>{li([h + ': ' + t for h, t in nxt])}
<p><b>Be ready:</b> {esc(prep)}</p>{li(upcoming)}
<p style="color:#888;font-size:12px;margin-top:20px">Full report attached as PDF. Built from what was logged in the tracker; general guidance only, not medical advice. Health811: dial 811.</p>
</div>"""
    return html


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--now")
    ap.add_argument("--out", default="report/out")
    a = ap.parse_args()
    now = dt.datetime.fromisoformat(a.now).replace(tzinfo=TZ) if a.now else dt.datetime.now(TZ)
    rows = json.loads(pathlib.Path(a.data).read_text())
    if isinstance(rows, dict) and "rows" in rows: rows = rows["rows"]
    print(json.dumps(build(rows, now, pathlib.Path(a.out)), ensure_ascii=False, indent=1))
