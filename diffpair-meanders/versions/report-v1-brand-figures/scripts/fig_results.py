"""Result figures: every curve and number comes from the extracted four-ports
(build/sparams) or from build/results/results.json. Nothing is typed in.

Colour by job: copper is the series a panel is about, teal the one it is
compared with, grey the untuned context; past that, small multiples.

Run: python scripts/fig_results.py [report|blog]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import skrf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analysis as an  # noqa: E402
import geometry  # noqa: E402
import style as S  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "build" / "results" / "results.json").read_text())
V = R["variants"]

NAMES = {"A": "A straight", "B": "B untuned", "C": "C sparse", "C_far": "C far", "D": "D dense",
         "E": "E pair excursion", "F": "F trombone", "C_cal": "C, EM-sized", "D_cal": "D, EM-sized",
         "F_cal": "F, EM-sized", "S_loose": "serpentine, 1.0 mm folds", "S_tight": "serpentine, 0.15 mm folds",
         "B_R075": "R = 0.75 mm", "B_R3": "R = 3 mm"}


def net(v, level="medium"):
    return an.load(level, v)


def mixed(v, level="medium"):
    return an.mixed(net(v, level))


def db(x):
    return 20 * np.log10(np.maximum(np.abs(x), 1e-12))


def label_end(ax, x, y, text, colour, size, dx=0.0, dy=0.0, ha="left"):
    ax.text(x + dx, y + dy, text, color=S.INK, fontsize=size, ha=ha, va="center",
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))


# ------------------------------------------------------------------ skew

def fig_skew(target):
    t = S.use(target)
    b = t["base"]
    order = [v for v in ("B", "E", "C_far", "D", "C", "F", "D_cal", "C_cal", "F_cal") if v in V]
    unc = R["uncertainty_ps"]
    fig, ax = plt.subplots(figsize=(t["double"] if target == "blog" else t["single"],
                                    (0.36 if target == "blog" else 0.62) * len(order) + 0.6))
    y = np.arange(len(order))[::-1]
    for yi, v in zip(y, order):
        s = V[v]["timing"]["50"]["skew"]
        e = V[v]["uncertainty_ps"] or 0.0
        colour = S.CONTEXT if v in ("B", "E") else (S.COPPER_FILL if v.endswith("_cal") else S.COPPER)
        ax.barh(yi, s, height=0.56, color=colour, edgecolor=S.COPPER if v.endswith("_cal") else "none",
                lw=1.0, zorder=3)
        ax.errorbar(s, yi, xerr=e, fmt="none", ecolor=S.INK, elinewidth=0.8, capsize=2, zorder=4)
        if "mtl_skew_50" in V[v]:
            ax.plot(V[v]["mtl_skew_50"], yi, marker="D", ms=4.5 if target == "report" else 6.5, color=S.TEAL,
                    mec="white", mew=0.8, zorder=5)
        eta = V[v]["timing"]["50"].get("eta")
        txt = f"{s:.1f} ps" + (f"   η {eta:.2f}" if eta is not None and not math.isnan(eta) else "")
        ax.text(max(s, 0) + e + 0.3, yi, txt, va="center", fontsize=b - 1, color=S.INK)
    ax.axvline(R["analytic"]["single_line"]["skew_ps"], color=S.PURPLE, ls=(0, (4, 3)), lw=1.0, zorder=2)
    ax.text(R["analytic"]["single_line"]["skew_ps"], len(order) - 0.35, r"$\pi s\sqrt{\varepsilon_{\rm eff}}/c$", color=S.INK,
            fontsize=b - 1.5, ha="center", va="bottom")
    ax.axvline(0, color=S.AXES, lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels([NAMES[v] for v in order])
    ax.tick_params(axis="y", length=0, labelcolor=S.INK)
    ax.set_xlabel("Intra-pair skew at the receiver (ps), P early is positive")
    ax.set_xlim(-5.4, 13.2)
    ax.set_ylim(-0.6, len(order) - 0.1)
    ax.grid(axis="y", visible=False)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    handles = [Patch(color=S.COPPER, label="full wave, tuned to equal length"),
               Patch(facecolor=S.COPPER_FILL, edgecolor=S.COPPER, label="full wave, sized from its residual"),
               Patch(color=S.CONTEXT, label="full wave, no intra-pair tuning"),
               Line2D([], [], marker="D", ls="none", color=S.TEAL, mec="white", label="MTL from lengths"),
               Line2D([], [], color=S.PURPLE, ls=(0, (4, 3)), label="geometric bend skew")]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=b - 1.5,
              handlelength=1.4, columnspacing=1.2)
    S.save(fig, "fig_skew", target)


# ------------------------------------------------------------------ waveforms

def fig_waveforms(target):
    t = S.use(target)
    b = t["base"]
    show = [v for v in ("B", "C", "D", "F") if v in V]
    fig, axes = plt.subplots(2, len(show), figsize=(t["double"], t["double"] * 0.42), sharex=True,
                             gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.12, "wspace": 0.12})
    for k, v in enumerate(show):
        w = an.waveforms(net(v), 50e-12)
        tt = w["t"] * 1e12
        tm = V[v]["timing"]["50"]
        lo, hi = tm["t50_d"] - 45, tm["t50_d"] + 45
        sel = (tt > lo) & (tt < hi)
        ax = axes[0, k]
        ax.plot(tt[sel], w["p_far"][sel], color=S.COPPER, label="P")
        ax.plot(tt[sel], -w["n_far"][sel], color=S.TEAL, label="−N")
        for tx, col in ((tm["t50_P"], S.COPPER), (tm["t50_N"], S.TEAL)):
            ax.axvline(tx, color=col, lw=0.6, ls=":")
        ax.set_title(f"{NAMES[v]}: {tm['skew']:.1f} ps", fontsize=b, pad=3)
        ax.set_ylim(-0.03, 0.55)
        if k == 0:
            ax.set_ylabel("Far-end voltage (V)")
            ax.legend(loc="upper left", fontsize=b - 1.5, handlelength=1.2)
        else:
            ax.tick_params(labelleft=False)
        ax2 = axes[1, k]
        ax2.plot(tt[sel], w["vc_far"][sel] * 1000, color=S.COPPER)
        ax2.set_ylim(-5, 55)
        ax2.axhline(0, color=S.AXES, lw=0.6)
        if k == 0:
            ax2.set_ylabel("Vc (mV)")
        else:
            ax2.tick_params(labelleft=False)
        ax2.set_xlabel("Time (ps)")
        ax2.text(0.03, 0.92, f"peak {np.max(w['vc_far'][sel]) * 1000:.0f} mV", transform=ax2.transAxes,
                 ha="left", va="top", fontsize=b - 1.5, color=S.INK)
    S.save(fig, "fig_waveforms", target)


# ------------------------------------------------------------------ mode conversion

def fig_scd21(target):
    t = S.use(target)
    b = t["base"]
    show = [v for v in ("C", "C_far", "D", "F", "E", "C_cal") if v in V]
    cols = 3
    rows = math.ceil(len(show) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(t["double"], t["double"] * 0.27 * rows), sharex=True, sharey=True,
                             gridspec_kw={"hspace": 0.3, "wspace": 0.08})
    mb = mixed("B")
    f = mb.f / 1e9
    for ax, v in zip(axes.ravel(), show):
        m = mixed(v)
        ax.plot(f[1:], db(mb.s[1:, 3, 0]), color=S.CONTEXT, lw=1.0, label="B untuned")
        ax.plot(f[1:], db(m.s[1:, 3, 0]), color=S.COPPER, label=NAMES[v])
        ax.set_title(NAMES[v], fontsize=b, pad=2)
        ax.set_xlim(0, 30)
        ax.set_ylim(-60, 0)
        if v == "E":
            ax.text(0.97, 0.06, "on top of B", transform=ax.transAxes, ha="right", fontsize=b - 1.5, color=S.SOFT)
    for ax in axes.ravel()[len(show):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("Frequency (GHz)")
    for ax in axes[:, 0]:
        ax.set_ylabel("|Scd21| (dB)")
    axes[0, 0].legend(["B untuned", "variant"], loc="lower right", fontsize=b - 1.5, handlelength=1.2)
    S.save(fig, "fig_scd21", target)


def fig_sdd(target):
    t = S.use(target)
    b = t["base"]
    if target == "report":
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(t["single"], t["single"] * 1.15), gridspec_kw={"hspace": 0.35})
    else:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(t["double"], t["double"] * 0.3), gridspec_kw={"wspace": 0.22})
    series = [("A", S.CONTEXT, 1.0), ("F", S.COPPER, None), ("D", S.TEAL, None)]
    for v, col, lw in series:
        if v not in V:
            continue
        m = mixed(v)
        f = m.f / 1e9
        ax1.plot(f[1:], db(m.s[1:, 0, 0]), color=col, lw=lw, label=NAMES[v])
        ax2.plot(f[1:], db(m.s[1:, 1, 0]), color=col, lw=lw, label=NAMES[v])
    ax1.set_ylabel("|Sdd11| (dB)")
    ax2.set_ylabel("|Sdd21| (dB)")
    for ax in (ax1, ax2):
        ax.set_xlabel("Frequency (GHz)")
        ax.set_xlim(0, 30)
    ax1.set_ylim(-50, -10)
    ax2.set_ylim(-4, 0.2)
    ax1.legend(loc="lower right", fontsize=b - 1.5, handlelength=1.2)
    S.save(fig, "fig_sdd", target)


def fig_tdr(target):
    t = S.use(target)
    b = t["base"]
    fig, ax = plt.subplots(figsize=(t["single"] if target == "report" else t["double"] * 0.7,
                                    t["single"] * 0.62 if target == "report" else t["double"] * 0.32))
    for v, col, lw in (("B", S.CONTEXT, 1.0), ("F", S.COPPER, None), ("D", S.TEAL, None)):
        tt, rho, z = an.tdr(mixed(v), 35e-12)
        sel = (tt > -10e-12) & (tt < 400e-12)
        ax.plot(tt[sel] * 1e12, z[sel], color=col, lw=lw, label=NAMES[v])
    ax.set_xlabel("Round-trip time from the launch (ps), 35 ps edge")
    ax.set_ylabel("Zdiff (Ω)")
    ax.set_ylim(85, 120)
    ax.legend(loc="upper left", fontsize=b - 1.5, handlelength=1.2, ncol=3)
    S.save(fig, "fig_tdr", target)


# ------------------------------------------------------------------ efficiency

def fig_eta(target):
    t = S.use(target)
    b = t["base"]
    rows = [(v, V[v]["timing"]["50"]["eta"]) for v in ("F", "C", "C_far", "D", "S_loose", "S_tight")
            if v in V and "eta" in V[v]["timing"]["50"]]
    notes = {"F": "F\nN = 1", "C": "C\nN = 2", "C_far": "C far\nN = 2", "D": "D\nN = 4",
             "S_loose": "serp.\nfolds 1.0", "S_tight": "serp.\nfolds 0.15"}
    fig, ax = plt.subplots(figsize=(t["single"] if target == "report" else t["double"] * 0.75,
                                    t["single"] * 0.7 if target == "report" else t["double"] * 0.36))
    x = np.arange(len(rows))
    for xi, (v, e) in zip(x, rows):
        col = S.TEAL if v.startswith("S_") else S.COPPER
        ax.bar(xi, e, width=0.62, color=col, zorder=3)
        ax.text(xi, e + 0.02, f"{e:.2f}", ha="center", va="bottom", fontsize=b - 1, color=S.INK)
    ax.axhline(1.0, color=S.PURPLE, ls=(0, (4, 3)), lw=1.0)
    ax.text(len(rows) - 0.5, 1.02, "η = 1: delay as length predicts", ha="right", va="bottom", fontsize=b - 1.5,
            color=S.INK)
    ax.set_xticks(x)
    ax.set_xticklabels([notes[v] for v, _ in rows], fontsize=b - 1.5)
    ax.tick_params(axis="x", length=0, labelcolor=S.INK)
    ax.set_ylabel("Delay efficiency η")
    ax.set_ylim(0, 1.15)
    ax.grid(axis="x", visible=False)
    S.save(fig, "fig_eta", target)


# ------------------------------------------------------------------ convergence

def fig_convergence(target):
    t = S.use(target)
    b = t["base"]
    conv = R["convergence"]
    cells = geometry.params()["simulation"]["levels"]
    fig, ax = plt.subplots(figsize=(t["single"] if target == "report" else t["double"] * 0.6,
                                    t["single"] * 0.66 if target == "report" else t["double"] * 0.36))
    colours = {"B": S.CONTEXT, "C": S.COPPER, "D": S.TEAL}
    for v in ("B", "C", "D"):
        if v not in conv:
            continue
        levels = sorted(conv[v]["skew_50"], key=lambda l: -cells[l])
        xs = [cells[l] * 1000 for l in levels]
        ys = [conv[v]["skew_50"][l] for l in levels]
        ax.plot(xs, ys, marker="o", ms=4, color=colours[v], label=NAMES[v])
        ax.errorbar([xs[-1]], [ys[-1]], yerr=[conv[v]["gci"]], fmt="none", ecolor=colours[v], capsize=3, lw=1.0)
        ax.annotate(f"±{conv[v]['gci']:.2f} ps", (xs[-1], ys[-1]), xytext=(8, 6), textcoords="offset points",
                    ha="left", va="bottom", fontsize=b - 1.5, color=S.INK)
    ax.set_xlabel("Finest cell in the copper regions (µm)")
    ax.set_ylabel("Skew, 50 ps edge (ps)")
    ax.set_xlim(70, 5)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=b - 1.5, handlelength=1.2)
    S.save(fig, "fig_convergence", target)


# ------------------------------------------------------------------ Pareto

# label offsets in points where two candidates sit close together
PARETO_OFFSETS = {("area", "C_far"): (6, 2), ("area", "C"): (6, -12), ("sdd11", "E"): (-14, 6),
                  ("sdd11", "B"): (6, -12), ("sdd11", "C_far"): (6, -12), ("sdd11", "D"): (6, 4)}

def fig_pareto(target):
    t = S.use(target)
    b = t["base"]
    P = R["pareto"]["objectives"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(t["double"], t["double"] * 0.33), gridspec_kw={"wspace": 0.25})
    for ax, (kx, key, xl), front in ((ax1, ("area", "area", "Board area of the tuning (mm²)"),
                                      R["pareto"]["front_skew_area"]),
                                     (ax2, ("sdd11_max_db", "sdd11", "Worst |Sdd11|, 0.1 to 20 GHz (dB)"),
                                      R["pareto"]["front_skew_sdd11"])):
        for v, o in P.items():
            on = v in front
            ax.plot(o[kx], o["skew"], marker="o", ms=6 if on else 4.5, color=S.COPPER if on else S.CONTEXT,
                    zorder=4 if on else 3, ls="none")
            short = {"B": "B", "C": "C", "C_far": "C far", "D": "D", "E": "E", "F": "F",
                     "C_cal": "C cal", "D_cal": "D cal", "F_cal": "F cal"}[v]
            off = PARETO_OFFSETS.get((key, v), (6, 4))
            ax.annotate(short, (o[kx], o["skew"]), xytext=off, textcoords="offset points", fontsize=b - 1.5,
                        ha="left", va="bottom", color=S.INK)
        pts = sorted((P[v][kx], P[v]["skew"]) for v in front)
        ax.step([p[0] for p in pts], [p[1] for p in pts], where="post", color=S.COPPER, lw=0.8, ls="--", zorder=2)
        ax.set_xlabel(xl)
        ax.set_ylabel("|Skew|, 50 ps edge (ps)")
        ax.set_ylim(-0.5, 11.5)
    S.save(fig, "fig_pareto", target)


# ------------------------------------------------------------------ edges and frequency

def fig_rise(target):
    t = S.use(target)
    b = t["base"]
    if target == "report":
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(t["single"], t["single"] * 1.15), gridspec_kw={"hspace": 0.45})
    else:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(t["double"], t["double"] * 0.3), gridspec_kw={"wspace": 0.25})
    rises = [float(k) for k in V["B"]["timing"]]
    for v, col in (("B", S.CONTEXT), ("C", S.COPPER), ("F", S.TEAL)):
        sk = [V[v]["timing"][f"{r:g}"]["skew"] for r in rises]
        vc = [V[v]["timing"][f"{r:g}"]["vc_pp_rel"] * 100 for r in rises]
        ax1.plot(rises, sk, marker="o", ms=3.5, color=col, label=NAMES[v])
        ax2.plot(rises, vc, marker="o", ms=3.5, color=col, label=NAMES[v])
    ax1.set_ylabel("Skew (ps)")
    ax2.set_ylabel("Common-mode peak, % of the step")
    for ax in (ax1, ax2):
        ax.set_xlabel("Edge, 10 to 90 % (ps)")
        ax.set_xscale("log")
        ax.set_xticks(rises)
        ax.set_xticklabels([f"{r:g}" for r in rises])
        ax.minorticks_off()
    ax1.set_ylim(0, 11)
    ax2.set_ylim(0, None)
    ax2.legend(loc="upper right", fontsize=b - 1.5, handlelength=1.2)
    S.save(fig, "fig_rise", target)


def fig_fd_skew(target):
    t = S.use(target)
    b = t["base"]
    fig, ax = plt.subplots(figsize=(t["single"] if target == "report" else t["double"] * 0.7,
                                    t["single"] * 0.62 if target == "report" else t["double"] * 0.34))
    for v, col, lw in (("B", S.CONTEXT, 1.0), ("C", S.TEAL, None), ("C_far", S.COPPER, None)):
        m = mixed(v)
        f = m.f
        r = np.abs(m.s[:, 3, 0]) / np.abs(m.s[:, 1, 0])
        tau = 2 * np.arctan(r) / (2 * np.pi * np.maximum(f, 1)) * 1e12
        sel = f >= 1e9
        ax.plot(f[sel] / 1e9, tau[sel], color=col, lw=lw, label=NAMES[v])
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("2 atan|Scd21/Sdd21| / ω (ps)")
    ax.set_xlim(1, 30)
    ax.set_ylim(0, 12)
    ax.legend(loc="upper left", fontsize=b - 1.5, ncol=3, handlelength=1.2)
    S.save(fig, "fig_fd_skew", target)


def fig_radius(target):
    t = S.use(target)
    b = t["base"]
    pts = [(0.75, "B_R075"), (1.5, "B"), (3.0, "B_R3")]
    pts = [(r, v) for r, v in pts if v in V]
    fig, ax = plt.subplots(figsize=(t["single"] if target == "report" else t["double"] * 0.5,
                                    t["single"] * 0.6 if target == "report" else t["double"] * 0.3))
    ax.plot([r for r, _ in pts], [V[v]["timing"]["50"]["skew"] for _, v in pts], marker="o", color=S.COPPER,
            label="full wave, 50 ps edge")
    ax.axhline(R["analytic"]["single_line"]["skew_ps"], color=S.PURPLE, ls=(0, (4, 3)), lw=1.0,
               label=r"$\pi s\sqrt{\varepsilon_{\rm eff}}/c$")
    ax.set_xlabel("Bend radius of P, R (mm)")
    ax.set_ylabel("Skew (ps)")
    ax.set_ylim(8, 10.5)
    ax.set_xlim(0.5, 3.25)
    ax.legend(loc="lower left", fontsize=b - 1.5, handlelength=1.4)
    S.save(fig, "fig_radius", target)


def fig_eye(target):
    t = S.use(target)
    b = t["base"]
    show = [v for v in ("A", "B", "F") if v in V]
    fig, axes = plt.subplots(2, len(show), figsize=(t["double"], t["double"] * 0.42), sharey="row",
                             gridspec_kw={"height_ratios": [1.6, 1], "hspace": 0.85 if target == "report" else 0.55,
                                          "wspace": 0.08})
    for k, v in enumerate(show):
        e = an.eye(net(v), 16e9, 35e-12)
        tt, d, c, ui = e["t"], e["vd"], e["vc"], e["ui"]
        dt = tt[1] - tt[0]
        td = V[v]["timing"]["35"]["t50_d"] * 1e-12
        n0 = int(round((16 * ui + td - ui / 2 - tt[0]) / dt))
        per = int(round(ui / dt))
        ax = axes[0, k]
        for j in range(16, 230):
            s0 = n0 + (j - 16) * per
            seg = d[s0: s0 + 2 * per]
            if seg.size == 2 * per:
                ax.plot(np.arange(seg.size) * dt * 1e12, seg, color=S.COPPER, lw=0.35, alpha=0.35)
        ax.set_title(f"{NAMES[v]}: height {e['eye_height_rel'] * 100:.1f} %", fontsize=b, pad=3)
        ax.set_xlabel("Time (ps), 2 UI")
        ax.set_xlim(0, 2 * ui * 1e12)
        ax2 = axes[1, k]
        sel = slice(n0, n0 + 40 * per)
        ax2.plot((tt[sel] - tt[sel][0]) * 1e12, c[sel] * 1000, color=S.TEAL, lw=0.8)
        ax2.set_xlabel("Time (ps)")
        ax2.set_title(f"Vc {e['vc_pp_rel'] * 100:.1f} % of the swing, p-p", fontsize=b - 1, pad=3,
                      fontweight="regular", color=S.INK)
        if k == 0:
            ax.set_ylabel("Vd at receiver (V)")
            ax2.set_ylabel("Vc (mV)")
    S.save(fig, "fig_eye", target)


def fig_stripline(target):
    """Delay efficiency in microstrip and in stripline, same copper."""
    t = S.use(target)
    b = t["base"]
    pairs = [(v, v + "_sl") for v in ("F", "C", "D", "S_loose", "S_tight") if v in V and v + "_sl" in V]
    if not pairs:
        return
    notes = {"F": "F\nN = 1", "C": "C\nN = 2", "D": "D\nN = 4", "S_loose": "serp.\nfolds 1.0",
             "S_tight": "serp.\nfolds 0.15"}
    fig, ax = plt.subplots(figsize=(t["single"] if target == "report" else t["double"] * 0.75,
                                    t["single"] * 0.7 if target == "report" else t["double"] * 0.36))
    x = np.arange(len(pairs))
    wd = 0.36
    for xi, (ms, sl) in zip(x, pairs):
        for dx, v, col in ((-wd / 2, ms, S.COPPER), (wd / 2, sl, S.TEAL)):
            e = V[v]["timing"]["50"]["eta"]
            ax.bar(xi + dx, e, width=wd * 0.92, color=col, zorder=3)
            ax.text(xi + dx, e + 0.02, f"{e:.2f}", ha="center", va="bottom", fontsize=b - 2, color=S.INK)
    ax.axhline(1.0, color=S.PURPLE, ls=(0, (4, 3)), lw=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels([notes[m_] for m_, _ in pairs], fontsize=b - 1.5)
    ax.tick_params(axis="x", length=0, labelcolor=S.INK)
    ax.set_ylabel("Delay efficiency η")
    ax.set_ylim(0, 1.18)
    ax.grid(axis="x", visible=False)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=S.COPPER, label="microstrip"), Patch(color=S.TEAL, label="stripline")],
              loc="upper left", fontsize=b - 1.5, ncol=2, handlelength=1.2)
    S.save(fig, "fig_stripline", target)


ALL_FIGS = [fig_skew, fig_waveforms, fig_scd21, fig_sdd, fig_tdr, fig_eta, fig_convergence, fig_pareto,
            fig_rise, fig_fd_skew, fig_radius, fig_eye, fig_stripline]

if __name__ == "__main__":
    targets = [a for a in sys.argv[1:] if a in ("report", "blog")] or ["report", "blog"]
    only = [a for a in sys.argv[1:] if a.startswith("fig_")]
    for tg in targets:
        for fn in ALL_FIGS:
            if not only or fn.__name__ in only:
                fn(tg)
    print("ok")
