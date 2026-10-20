"""openEMS models for the meander study, written as openEMS's own XML.

openEMS's Python bindings are not installed on this host, so the model is
written in the XML vocabulary those bindings write (checked against
openEMS v0.37.0-rc3): a conducting sheet for the signal copper, a lossy
dielectric box, and for each port a lumped resistor, two probes and, on the
excited port only, an excitation. The return plane is the domain's PEC floor.

Every U-bend variant at one mesh level shares one mesh: the fine regions are
the union of all variants' copper, so discretisation error in the copper the
variants share is common to them and drops out of their differences.

Run: python scripts/model.py <variant> <level> <port>  (prints the XML)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry  # noqa: E402

EPS0 = 8.8541878128e-12
C0 = 299792458.0
GRADING = 1.3


def fmt(v: float) -> str:
    return f"{v:.7g}" if v != 0 else "0"


# ---------------------------------------------------------------- the mesh

def _local_cell(x, regions, fine, coarse):
    """The largest cell allowed at x: `fine` inside a region, growing by
    GRADING per cell away from it, never above `coarse`."""
    d = min((max(lo - x, 0.0, x - hi) for lo, hi in regions), default=math.inf)
    if d == 0:
        return fine
    # cells growing geometrically from `fine` cover distance d after k cells
    # with fine*(g^k - 1)/(g - 1) = d, by which point the cell is fine*g^k.
    return min(coarse, fine + (GRADING - 1) * d)


def lines(lo, hi, fixed, regions, fine, coarse):
    """Mesh lines over [lo, hi] through every fixed line, no cell larger than
    the local limit."""
    keep = sorted({round(v, 6) for v in fixed if lo <= v <= hi} | {lo, hi})
    merged = [keep[0]]
    for v in keep[1:]:
        if v - merged[-1] < fine / 3:   # two fixed lines too close: keep the first
            continue
        merged.append(v)
    out = [merged[0]]
    for a, b in zip(merged, merged[1:]):
        # integrate 1/h over [a, b] to count cells, then place them at equal
        # steps of that integral
        samples = 200
        xs = [a + (b - a) * k / samples for k in range(samples + 1)]
        inv = [1 / _local_cell(x, regions, fine, coarse) for x in xs]
        cum = [0.0]
        for k in range(samples):
            cum.append(cum[-1] + (inv[k] + inv[k + 1]) / 2 * (xs[k + 1] - xs[k]))
        n = max(1, math.ceil(cum[-1] - 1e-9))
        for j in range(1, n):
            target = cum[-1] * j / n
            k = next(i for i in range(samples) if cum[i + 1] >= target)
            frac = (target - cum[k]) / (cum[k + 1] - cum[k])
            out.append(xs[k] + frac * (xs[k + 1] - xs[k]))
        out.append(b)
    return [round(v, 6) for v in out]


def mesh(family: str, level: str, p=None):
    """The mesh for 'U' (every bent variant) or 'A' (the straight one)."""
    p = p or geometry.params()
    sim = p["simulation"]
    fine, coarse, air = sim["levels"][level], sim["coarse_cell"], sim["air_cell"]
    w, s = p["pair"]["width"], p["pair"]["pitch"]
    L, R = p["fixture"]["leg_length"], p["fixture"]["bend_radius"]
    h = p["stackup"]["dielectric_height"]
    m = sim["margin_xy"]
    pad = 0.3
    traces_y_u = [-R, -(R + s), R, R + s]
    if family == "U":
        variants = [geometry.build(v, p) for v in geometry.FAMILIES["U"]]
        xs = [pt[0] for g in variants for net in ("P", "N") for pt in g["copper"][net]]
        ys = [pt[1] for g in variants for net in ("P", "N") for pt in g["copper"][net]]
        x_lo, x_hi, y_lo, y_hi = min(xs), max(xs), min(ys), max(ys)
        starts = [g["tuning"]["section_start"] for g in variants if "section_start" in g["tuning"]]
        ends = [g["tuning"]["section_end"] for g in variants if "section_end" in g["tuning"]]
        far = [g["tuning"] for g in variants if g["name"] == "C_far"][0]
        x_regions = [(-pad, pad), (far["section_start"] - pad, far["section_end"] + pad),
                     (min(st for st in starts if st > L / 2) - pad, x_hi + pad)]
        x_fixed = [0.0]
        y_fixed = [y + d for y in traces_y_u for d in (-w / 2, 0.0, w / 2)]
        traces_y = traces_y_u
    elif family in ("S", "U075", "U3", "Usl", "Ssl"):
        variants = [geometry.build(v, p) for v in geometry.FAMILIES[family]]
        xs = [pt[0] for g in variants for net in ("P", "N") for pt in g["copper"][net]]
        ys = [pt[1] for g in variants for net in ("P", "N") for pt in g["copper"][net]]
        x_lo, x_hi, y_lo, y_hi = min(xs), max(xs), min(ys), max(ys)
        port_x = sorted({q["x"] for g in variants for q in g["ports"]})
        x_regions = [(x - pad, x + pad) for x in port_x]
        x_regions += [(g["tuning"]["section_start"] - pad, g["tuning"]["section_end"] + pad)
                      for g in variants if "section_start" in g["tuning"]]
        if family not in ("S", "Ssl"):
            x_regions.append((L - pad, x_hi + pad))
        x_fixed = port_x
        traces_y = sorted({q["y"] for g in variants for q in g["ports"]})
        y_fixed = [y + d for y in traces_y for d in (-w / 2, 0.0, w / 2)]
    else:
        g = geometry.build("A", p)
        total = g["tuning"]["length"]
        x_lo, x_hi = 0.0, total
        y_lo, y_hi = -(R + s) - w / 2, -R + w / 2
        x_regions = [(-pad, pad), (total - pad, total + pad)]
        x_fixed = [0.0, total]
        y_fixed = [y + d for y in (-R, -(R + s)) for d in (-w / 2, 0.0, w / 2)]
        traces_y = [-R, -(R + s)]
    y_regions = [(y_lo - pad, y_hi + pad)]
    X = lines(x_lo - m, x_hi + m, x_fixed, x_regions, fine, coarse)
    Y = lines(y_lo - m, y_hi + m, y_fixed, y_regions, fine, coarse)
    if family in geometry.STRIPLINE_FAMILIES:
        b = p["stripline"]["plane_spacing"]
        Z = lines(0.0, b, [0.0, b / 2, b], [(0.0, b)], fine, air)
    else:
        top = h + sim["air_above"]
        Z = lines(0.0, top, [0.0, h], [(0.0, h)], fine, air)
    return {"x": X, "y": Y, "z": Z, "traces_y": traces_y}


# ---------------------------------------------------------------- the model

def _box(lo, hi, prio, ind="          "):
    return (f'{ind}<Box Priority="{prio}">\n'
            f'{ind}  <P1 X="{fmt(lo[0])}" Y="{fmt(lo[1])}" Z="{fmt(lo[2])}"/>\n'
            f'{ind}  <P2 X="{fmt(hi[0])}" Y="{fmt(hi[1])}" Z="{fmt(hi[2])}"/>\n'
            f'{ind}</Box>\n')


def _polygon(points, z, prio, ind="          "):
    out = f'{ind}<Polygon Priority="{prio}" Elevation="{fmt(z)}" NormDir="2" QtyVertices="{len(points)}">\n'
    for x, y in points:
        out += f'{ind}  <Vertex X1="{fmt(x)}" X2="{fmt(y)}"/>\n'
    return out + f"{ind}</Polygon>\n"


def model_xml(variant: str, level: str, excited: int, p=None, *, copper: str = "sheet",
              lossless: bool = False, f0: float | None = None, fc: float | None = None,
              max_timesteps: int | None = None, end_criteria: float | None = None) -> str:
    p = p or geometry.params()
    g = geometry.build(variant, p)
    family = geometry.family_of(variant)
    grid = mesh(family, level, p)
    st, sim = p["stackup"], p["simulation"]
    h, w = st["dielectric_height"], p["pair"]["width"]
    strip = family in geometry.STRIPLINE_FAMILIES
    slab = p["stripline"]["plane_spacing"] if strip else h      # dielectric thickness
    if strip:
        h = slab / 2                                             # copper height above the lower plane
    f0 = f0 or sim["f_max"] / 2
    fc = fc or sim["f_max"] / 2
    kappa = 0.0 if lossless else 2 * math.pi * st["loss_tangent_at"] * EPS0 * st["epsilon_r"] * st["loss_tangent"]
    X, Y, Z = grid["x"], grid["y"], grid["z"]
    big = 1.0
    props, ident = "", 0
    props += (f'      <Material ID="{ident}" Name="substrate" Isotropy="1">\n        <Primitives>\n'
              + _box((X[0] - big, Y[0] - big, 0.0), (X[-1] + big, Y[-1] + big, slab), 1)
              + "        </Primitives>\n"
              f'        <Property Epsilon="{fmt(st["epsilon_r"])},1,1" Mue="1,1,1" Kappa="{fmt(kappa)},0,0" Sigma="0,0,0" Density="0"/>\n'
              '        <Weight Epsilon="1,1,1" Mue="1,1,1" Kappa="1,1,1" Sigma="1,1,1" Density="1"/>\n'
              "      </Material>\n")
    ident += 1
    sheets = "".join(_polygon(g["copper"][net], h, 10) for net in ("P", "N"))
    if copper == "pec":
        props += (f'      <Metal ID="{ident}" Name="copper">\n        <Primitives>\n{sheets}'
                  "        </Primitives>\n      </Metal>\n")
    else:
        props += (f'      <ConductingSheet ID="{ident}" Name="copper" Conductivity="{fmt(st["copper_conductivity"])}" '
                  f'Thickness="{fmt(st["copper_thickness"] / 1000)}">\n        <Primitives>\n{sheets}'
                  "        </Primitives>\n      </ConductingSheet>\n")
    ident += 1
    R0 = p["fixture"]["port_impedance"]
    for port in g["ports"]:
        n, x, y = port["number"], port["x"], port["y"]
        lo, hi = (x, y - w / 2, 0.0), (x, y + w / 2, h)
        props += (f'      <LumpedElement ID="{ident}" Name="port_resist_{n}" Direction="2" Caps="1" '
                  f'R="{fmt(R0)}" LEtype="0">\n        <Primitives>\n{_box(lo, hi, 5)}'
                  "        </Primitives>\n      </LumpedElement>\n")
        ident += 1
        if n == excited:
            props += (f'      <Excitation ID="{ident}" Name="port_excite_{n}" Number="0" Enabled="1" Frequency="0" '
                      f'Delay="0" Type="0" Excite="0,0,-1" PropDir="0,0,0">\n        <Primitives>\n{_box(lo, hi, 5)}'
                      '        </Primitives>\n        <Weight X="1" Y="1" Z="1"/>\n      </Excitation>\n')
            ident += 1
        props += (f'      <ProbeBox ID="{ident}" Name="port_ut_{n}" Visible="0" Number="0" Type="0" Weight="-1" '
                  'NormDir="-1" StartTime="0" StopTime="0">\n        <Primitives>\n'
                  + _box((x, y, 0.0), (x, y, h), 0) + "        </Primitives>\n      </ProbeBox>\n")
        ident += 1
        props += (f'      <ProbeBox ID="{ident}" Name="port_it_{n}" Visible="0" Number="0" Type="1" Weight="1" '
                  'NormDir="2" StartTime="0" StopTime="0">\n        <Primitives>\n'
                  + _box((x, y - w / 2, h / 2), (x, y + w / 2, h / 2), 0)
                  + "        </Primitives>\n      </ProbeBox>\n")
        ident += 1
    grid_xml = "".join(f'      <{t} Qty="{len(v)}">{",".join(fmt(c) for c in v)}</{t}>\n'
                       for t, v in (("XLines", X), ("YLines", Y), ("ZLines", Z)))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<openEMS>\n'
            f'  <FDTD NumberOfTimesteps="{max_timesteps or sim["max_timesteps"]}" endCriteria="{(end_criteria or sim["end_criteria"]):g}" '
            'OverSampling="4" TimeStepMethod="3">\n'
            f'    <Excitation Type="0" f0="{f0:g}" fc="{fc:g}"/>\n'
            f'    <BoundaryCond xmin="MUR" xmax="MUR" ymin="MUR" ymax="MUR" zmin="PEC" zmax="{"PEC" if strip else "MUR"}"/>\n'
            "  </FDTD>\n"
            '  <ContinuousStructure CoordSystem="0">\n'
            '    <RectilinearGrid DeltaUnit="0.001" CoordSystem="0">\n'
            f"{grid_xml}    </RectilinearGrid>\n"
            '    <BackgroundMaterial Epsilon="1" Mue="1" Kappa="0" Sigma="0"/>\n'
            "    <ParameterSet/>\n    <Properties>\n"
            f"{props}    </Properties>\n  </ContinuousStructure>\n</openEMS>\n")


def stats(family: str, level: str):
    g = mesh(family, level)
    nx, ny, nz = len(g["x"]), len(g["y"]), len(g["z"])
    dmin = min(min(b - a for a, b in zip(v, v[1:])) for v in (g["x"], g["y"], g["z"]))
    return nx, ny, nz, nx * ny * nz, dmin


if __name__ == "__main__":
    if len(sys.argv) == 4:
        sys.stdout.write(model_xml(sys.argv[1], sys.argv[2], int(sys.argv[3])))
    else:
        for fam in ("U", "A"):
            for lvl in ("coarse", "medium", "fine"):
                print(fam, lvl, stats(fam, lvl))
