"""Fixture geometry for the differential-pair meander study.

Each variant is two centrelines, P and N, buffered into copper polygons. In
every bent variant P is the inner trace of a 180-degree U-bend and N the
outer, so P is short by pi*s before any tuning. A tuning section is cut into
P on the leg leading into the bend, with its amplitude solved so that P's
centreline comes out exactly as long as N's after the corners are chamfered.

Ports (scikit-rf's se2gmm order): 1 = P near end, 2 = N near end,
3 = P far end, 4 = N far end. In a bent variant both ends sit on the launch
plane x = 0; the near end is the lower leg (y < 0), the far end the upper.

Run: python scripts/geometry.py   (writes build/geometry/<variant>.json)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import yaml
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "geometry"
ARC_STEP_DEG = 1.0
CHAMFER_SAVING = 8 - 4 * math.sqrt(2)  # length lost per excursion, in units of the chamfer


def params() -> dict:
    return yaml.safe_load((ROOT / "parameters.yaml").read_text())


def arc(cx, cy, r, a0, a1):
    n = max(2, math.ceil(abs(a1 - a0) / math.radians(ARC_STEP_DEG)))
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n))
            for k in range(n + 1)]


def length(points) -> float:
    return sum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def dedupe(points, tol=1e-9):
    out = [points[0]]
    for p in points[1:]:
        if math.dist(p, out[-1]) > tol:
            out.append(p)
    return out


def meander(x_start, y0, n, a, top, bottom, c, sign=1.0):
    """n chamfered rectangular excursions of amplitude a (centreline), entering
    at (x_start, y0) and leaving on the same baseline; sign +1 bends toward +y."""
    pts = []
    for k in range(n):
        xl = x_start + c + k * (top + bottom)
        xr = xl + top
        pts += [(xl - c, y0), (xl, y0 + sign * c), (xl, y0 + sign * (a - c)), (xl + c, y0 + sign * a),
                (xr - c, y0 + sign * a), (xr, y0 + sign * (a - c)), (xr, y0 + sign * c), (xr + c, y0)]
    return pts


def meander_span(n, top, bottom, c) -> float:
    return n * top + (n - 1) * bottom + 2 * c


def u_bend(p, lower_p=None, lower_n=None):
    """P and N centrelines of the U-bend fixture. `lower_p`/`lower_n` replace
    the straight lower leg (x from 0 to the bend) with a given polyline."""
    L, R, s = p["fixture"]["leg_length"], p["fixture"]["bend_radius"], p["pair"]["pitch"]
    lp = lower_p or [(0.0, -R), (L, -R)]
    ln = lower_n or [(0.0, -(R + s)), (L, -(R + s))]
    P = lp + arc(L, 0.0, R, -math.pi / 2, math.pi / 2)[1:] + [(0.0, R)]
    N = ln + arc(L, 0.0, R + s, -math.pi / 2, math.pi / 2)[1:] + [(0.0, R + s)]
    return dedupe(P), dedupe(N)


def ports_u(p):
    R, s = p["fixture"]["bend_radius"], p["pair"]["pitch"]
    return [
        {"number": 1, "net": "P", "end": "near", "x": 0.0, "y": -R, "inward": 1},
        {"number": 2, "net": "N", "end": "near", "x": 0.0, "y": -(R + s), "inward": 1},
        {"number": 3, "net": "P", "end": "far", "x": 0.0, "y": R, "inward": 1},
        {"number": 4, "net": "N", "end": "far", "x": 0.0, "y": R + s, "inward": 1},
    ]


def tuned(p, family: str, placement: str, added: float | None = None):
    """The U-bend with a single-conductor tuning section cut into P's lower leg.
    `added` overrides the added length (default: exactly N's excess over P)."""
    L, R = p["fixture"]["leg_length"], p["fixture"]["bend_radius"]
    t = p["tuning"]
    f = t["families"][family]
    n, top, bottom, c = f["excursions"], f["top"], f["bottom"], t["chamfer"]
    p_b, n_b = u_bend(p)
    deficit = added if added is not None else length(n_b) - length(p_b)
    a_nominal = deficit / (2 * n)
    a = (deficit / n + CHAMFER_SAVING * c) / 2
    span = meander_span(n, top, bottom, c)
    x_start = L - t["gap_to_bend"] - span if placement == "near" else t["far_start"]
    lower = [(0.0, -R)] + meander(x_start, -R, n, a, top, bottom, c, sign=+1.0) + [(L, -R)]
    P, N = u_bend(p, lower_p=dedupe(lower))
    return P, N, {"excursions": n, "amplitude": a, "amplitude_nominal": a_nominal, "top": top,
                  "bottom": bottom, "chamfer": c, "section_start": x_start, "section_end": x_start + span,
                  "fold_edge_spacing": min(x for x in (top, bottom) if x > 0) - p["pair"]["width"]}


def excursion(p):
    """Both traces displaced together along a raised cosine, at constant pitch."""
    L, R, s = p["fixture"]["leg_length"], p["fixture"]["bend_radius"], p["pair"]["pitch"]
    e = p["excursion"]["E"]
    amp, span = e["amplitude"], e["length"]
    x1 = L - e["gap_to_bend"] - span
    yc0 = -(R + s / 2)
    samples = 600
    P, N = [(0.0, -R)], [(0.0, -(R + s))]
    for k in range(samples + 1):
        x = x1 + span * k / samples
        phase = 2 * math.pi * (x - x1) / span
        y = yc0 - amp * (1 - math.cos(phase)) / 2           # outward, away from the bend centre
        dy = -amp * math.pi / span * math.sin(phase)
        norm = math.hypot(1.0, dy)
        nx, ny = -dy / norm, 1.0 / norm                     # left of travel (+x)
        P.append((x + s / 2 * nx, y + s / 2 * ny))
        N.append((x - s / 2 * nx, y - s / 2 * ny))
    P.append((L, -R))
    N.append((L, -(R + s)))
    P, N = u_bend(p, lower_p=dedupe(P), lower_n=dedupe(N))
    return P, N, {"amplitude": amp, "length": span, "section_start": x1, "section_end": x1 + span}


def straight(p):
    L, R, s = p["fixture"]["leg_length"], p["fixture"]["bend_radius"], p["pair"]["pitch"]
    total = 2 * L + math.pi * (R + s / 2)   # the U-bend's mean centreline length
    P = [(0.0, -R), (total, -R)]
    N = [(0.0, -(R + s)), (total, -(R + s))]
    ports = [
        {"number": 1, "net": "P", "end": "near", "x": 0.0, "y": -R, "inward": 1},
        {"number": 2, "net": "N", "end": "near", "x": 0.0, "y": -(R + s), "inward": 1},
        {"number": 3, "net": "P", "end": "far", "x": total, "y": -R, "inward": -1},
        {"number": 4, "net": "N", "end": "far", "x": total, "y": -(R + s), "inward": -1},
    ]
    return P, N, {"length": total}, ports


def serpentine(p, kind: str):
    """The straight pair with a large serpentine on P, for the fold
    self-coupling (eta) experiment; `ref` is the same pair untuned."""
    P, N, info, ports = straight(p)
    if kind == "ref":
        return P, N, info, ports
    sp = p["serpentine"]
    n, c, R = sp["excursions"], p["tuning"]["chamfer"], p["fixture"]["bend_radius"]
    top, bottom = sp[kind]["top"], sp[kind]["bottom"]
    a = (sp["added_length"] / n + CHAMFER_SAVING * c) / 2
    span = meander_span(n, top, bottom, c)
    x_start = (info["length"] - span) / 2
    P = dedupe([(0.0, -R)] + meander(x_start, -R, n, a, top, bottom, c, sign=+1.0) + [(info["length"], -R)])
    info = dict(info, excursions=n, amplitude=a, top=top, bottom=bottom, chamfer=c, section_start=x_start,
                section_end=x_start + span, added_length=sp["added_length"],
                fold_edge_spacing=min(top, bottom) - p["pair"]["width"])
    return P, N, info, ports


def with_radius(p, radius):
    q = json.loads(json.dumps(p))
    q["fixture"]["bend_radius"] = radius
    return q


VARIANTS = {
    "A": "straight reference, the U-bend's mean length",
    "B": "untuned 180-degree U-bend",
    "C": "U-bend, sparse tuning (2 excursions) next to the bend",
    "C_far": "U-bend, sparse tuning (2 excursions) next to the launch",
    "D": "U-bend, dense accordion (4 excursions) next to the bend",
    "E": "U-bend, pair-level raised-cosine excursion (control)",
    "F": "U-bend, one broad trombone next to the bend",
    "C_cal": "U-bend, sparse tuning lengthened by its EM residual",
    "D_cal": "U-bend, dense accordion lengthened by its EM residual",
    "F_cal": "U-bend, broad trombone lengthened by its EM residual",
    "S_ref": "straight pair, reference for the serpentine experiment",
    "S_loose": "straight pair, 6 mm serpentine on P, folds 1.0 mm apart",
    "S_tight": "straight pair, 6 mm serpentine on P, folds 0.15 mm apart",
    "B_sl": "stripline: untuned U-bend",
    "C_sl": "stripline: sparse tuning next to the bend",
    "D_sl": "stripline: dense accordion next to the bend",
    "F_sl": "stripline: broad trombone next to the bend",
    "S_ref_sl": "stripline: straight pair, serpentine reference",
    "S_loose_sl": "stripline: 6 mm serpentine, folds 1.0 mm apart",
    "S_tight_sl": "stripline: 6 mm serpentine, folds 0.15 mm apart",
    "B_R075": "untuned U-bend, inner radius 0.75 mm",
    "B_R3": "untuned U-bend, inner radius 3.0 mm",
}

# Variants that share one mesh at each level.
FAMILIES = {
    "U": ["B", "C", "C_far", "D", "E", "F", "C_cal", "D_cal", "F_cal"],
    "A": ["A"],
    "S": ["S_ref", "S_loose", "S_tight"],
    "U075": ["B_R075"],
    "U3": ["B_R3"],
    "Usl": ["B_sl", "C_sl", "D_sl", "F_sl"],
    "Ssl": ["S_ref_sl", "S_loose_sl", "S_tight_sl"],
}
STRIPLINE_FAMILIES = ("Usl", "Ssl")


def family_of(name: str) -> str:
    return next(f for f, members in FAMILIES.items() if name in members)


def build(name: str, p=None) -> dict:
    p = p or params()
    if name.endswith("_sl"):
        g = build(name[:-3], p)
        g["name"] = name
        g["description"] = VARIANTS[name]
        return g
    w = p["pair"]["width"]
    extra, ports = {}, ports_u(p)
    if name == "A":
        P, N, extra, ports = straight(p)
    elif name == "B":
        P, N = u_bend(p)
    elif name in ("C", "D", "F"):
        P, N, extra = tuned(p, name, "near")
    elif name == "C_far":
        P, N, extra = tuned(p, "C", "far")
    elif name in ("C_cal", "D_cal", "F_cal"):
        fam = name[0]
        P, N, extra = tuned(p, fam, "near", added=p["calibrated_added_length"][fam])
    elif name == "E":
        P, N, extra = excursion(p)
    elif name.startswith("S_"):
        P, N, extra, ports = serpentine(p, name[2:])
    elif name.startswith("B_R"):
        q = with_radius(p, {"B_R075": 0.75, "B_R3": 3.0}[name])
        P, N = u_bend(q)
        ports = ports_u(q)
        extra = {"bend_radius": q["fixture"]["bend_radius"]}
    else:
        raise KeyError(name)
    poly = {}
    for net, line in (("P", P), ("N", N)):
        shape = LineString(line).buffer(w / 2, cap_style="flat", join_style="mitre", mitre_limit=5.0)
        poly[net] = shape
    clearance = poly["P"].distance(poly["N"])
    p_len, n_len = length(P), length(N)
    return {
        "name": name,
        "description": VARIANTS[name],
        "centreline": {"P": [list(map(lambda v: round(v, 7), pt)) for pt in P],
                       "N": [list(map(lambda v: round(v, 7), pt)) for pt in N]},
        "copper": {net: [[round(x, 7), round(y, 7)] for x, y in poly[net].exterior.coords[:-1]]
                   for net in ("P", "N")},
        "ports": ports,
        "length": {"P": p_len, "N": n_len, "N_minus_P": n_len - p_len},
        "clearance_PN": clearance,
        "clearance_ok": clearance >= p["pair"]["min_clearance"] - 1e-9,
        "area_bbox": _bbox_area(poly),
        "tuning": extra,
    }


def _bbox_area(poly) -> float:
    x0, y0, x1, y1 = poly["P"].union(poly["N"]).bounds
    return (x1 - x0) * (y1 - y0)


def main():
    p = params()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in VARIANTS:
        g = build(name, p)
        (OUT / f"{name}.json").write_text(json.dumps(g, indent=1))
        t = g["tuning"]
        a = f" A={t['amplitude']:.4f} (2NA rule {t['amplitude_nominal']:.4f})" if "amplitude_nominal" in t else ""
        print(f"{name:6s} P={g['length']['P']:.4f} N={g['length']['N']:.4f} N-P={g['length']['N_minus_P']:+.5f}"
              f" clearance={g['clearance_PN']:.4f} ok={g['clearance_ok']}{a}")


if __name__ == "__main__":
    main()
