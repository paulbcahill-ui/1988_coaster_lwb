"""Build a 1988 Toyota Coaster LWB (2nd gen B20/B30) hollow body and empty-cabin layout.

Owns BODY_*, FLR_*, DR_*, GLZ_*, WHL_*, CAB_*, ARCH_*, REF_*, GRP_*, LIT_*, TRM_*,
STEP_*, STO_*, BED_*.
Idempotent: opens a fresh document, rebuilds from params/coaster_params.json.

Units are millimetres. Do not hard-code measured vehicle dimensions here;
read them from params. Modelling-style radii and offsets also live in params.

Axes: x=0 is the front bumper face and the bus runs aft along +X, so the driver
faces -X. With +Z up the driver's RIGHT is +Y. Every side-dependent part reads
sides.y_sign_left / y_sign_right from params (left/kerb/entry = -Y,
right/offside/driver = +Y). Never hard-code +hw / -hw for a side.

Body (rebuilt 2026-11-17):
  * BODY_SHELL is ONE solid: a boxy prism (flat raked front, flat roof,
    vertical rear) with every upper edge filleted at body_edge_radius, then
    the cabin cavity (same shape, inset by the wall/roof thickness) removed
    with a single boolean cut. After all openings it is split by one plane
    (roof_split_z) into Body (walls, BODY_SHELL) and Roof (BODY_ROOF), so
    the two meet exactly.
  * Openings: two-piece windscreen in the flat front, driver door (right),
    folding entry door (left), side window band, full-width rear window, and
    the boot opening in the lower rear panel. There is NO rear emergency door.
  * Boot is INTERNAL: opening in the lower boot_height_fraction of the rear
    panel (floor line to rear window sill), top-hinged Boot Lid, and a Boot
    enclosure (front face + top) reaching boot_depth_into_cabin into the cabin
    from the inner rear wall.
  * Entry Step (2026-11-17, Cabin group): tread in the kerb-side step well at
    the bottom of the entry door opening; the well is cut out of the floor slab.
  * Storage group: underfloor bins between the skirt and the underside of the
    cabin floor, runs derived from bumpers/arch cuts/step well (overridable),
    through-bins where the kerb and offside runs overlap; flaps (OpenAngle,
    top-hinged by default) and Lock Markers that follow their flaps.
  * Bedroom group: dividing wall whose rear face (bedroom_wall_x) is flush
    with the rear arch housings' forward face, centred bi-parting doors
    Bedroom Door Left/Right (OpenFraction and SlideTravel on the left leaf),
    Bed Platform (over the boot by default) and the Bedroom Floor. The Living
    Floor (FLR_EMPTY_USABLE, still reported as usable_floor_*) runs from the
    cab zone to the wall.
  * Glass panes are separate thin solids recessed inside their openings, so
    nothing pokes through the roof or the cutaway plane.
  * The cutaway view uses true planar booleans at cutaway_z (stored in the
    render cache), not triangle culling, so the cut edge is clean.
  * Operable doors (2026-11-17): Entry Door (OpenFraction, SwingPhase,
    SwingOut, SlideTravel), Driver Door (OpenAngle), Boot Lid (OpenAngle).
    Placement expressions on each door read its own properties, so the
    property editor + recompute moves them, also after reopening, no add-on.
  * Labels are plain proper nouns ("Doors", "Body", "Entry Door", ...);
    internal Names keep their safe prefixes (GRP_, DR_, GLZ_, ...) and the
    renderer keys on Names.
  * Render/STL triangles are vertex-merged and conformingly refined to
    export.render_max_edge_mm so the painter's-algorithm renders do not
    show through and each object's mesh stays watertight.

Run headless:
  freecadcmd.exe macros\\10_coaster_shell.py
"""

from __future__ import annotations

import json
import math
import pickle
import sys
import traceback
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fcutil import (  # noqa: E402
    add_shape,
    group,
    recompute,
)

DOC_NAME = "1988_coaster_lwb_shell"


def load_params():
    path = ROOT / "params" / "coaster_params.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    values = {k: v["value"] for k, v in data["dimensions_mm"].items()}
    sides = data.get("sides", {})
    values["_y_left"] = float(sides.get("y_sign_left", 1))
    values["_y_right"] = float(sides.get("y_sign_right", -1))
    # Operable-door controls (fractions, degrees, mm). Not dimensions, so kept in their own section.
    # Layout switches (strings / booleans) live in layout_options.
    for section in ("door_controls", "layout_options"):
        for k, v in data.get(section, {}).items():
            if isinstance(v, dict) and "value" in v:
                values[k] = v["value"]
    # Build-time Glazed state per window, keyed by plain Label (True = glass, False = solid skin).
    values["_windows"] = {k: bool(v["value"]) for k, v in data.get("windows", {}).items()
                          if isinstance(v, dict) and "value" in v}
    return data, values


def Vv(values, key):
    return float(values[key])


def opt(values, key, default):
    """Number param that may be null (= use the derived default)."""
    v = values.get(key)
    if v is None or v == "":
        return float(default)
    return float(v)


def flag(values, key, default):
    v = values.get(key)
    return default if v is None else v


def vec(x, y, z):
    return App.Vector(float(x), float(y), float(z))


FAILED_OPS = []
WINDOWS = []        # (glass object, filler object) per window, filled by add_glass_and_doors
INACTIVE = set()    # Names hidden at build time (glass of a solid window, filler of a glazed one)


def try_fuse(a, b, label="fuse"):
    try:
        out = a.fuse(b)
        if out is not None and not out.isNull():
            return out.removeSplitter()
    except Exception as exc:
        print(f"  fuse failed ({label}): {exc}")
    FAILED_OPS.append(label)
    return a


def try_cut(shape, cutter, label=""):
    try:
        out = shape.cut(cutter)
        if out is None or out.isNull():
            print(f"  cut produced null ({label})")
            FAILED_OPS.append(label)
            return shape
        if out.Volume <= 1.0:
            print(f"  cut emptied shape ({label}), skipped")
            FAILED_OPS.append(label)
            return shape
        return out
    except Exception as exc:
        print(f"  cut failed ({label}): {exc}")
        FAILED_OPS.append(label)
        return shape


def try_common(shape, other, label=""):
    try:
        out = shape.common(other)
        if out is None or out.isNull() or out.Volume <= 1.0:
            print(f"  common empty ({label})")
            return None
        return out
    except Exception as exc:
        print(f"  common failed ({label}): {exc}")
        return None


def box(dx, dy, dz, x, y, z):
    if dx <= 0 or dy <= 0 or dz <= 0:
        raise ValueError(f"invalid box {dx} {dy} {dz}")
    return Part.makeBox(float(dx), float(dy), float(dz), vec(x, y, z))


def cylinder(r, h, x, y, z, direction):
    return Part.makeCylinder(float(r), float(h), vec(x, y, z), direction)


def u_arch_cutter(axle_x, y0, y1, radius, cz):
    """Wheel-arch slot along Y: a cylinder on the wheel centre plus a box down to the ground."""
    if y1 < y0:
        y0, y1 = y1, y0
    span = y1 - y0
    cyl = cylinder(radius, span, axle_x, y0, cz, vec(0, 1, 0))
    base = box(2 * radius, span, cz + 10.0, axle_x - radius, y0, -10.0)
    return try_fuse(cyl, base, "arch_slot")


def make_tyre(cx, cy, cz, od, rim_d, width):
    outer_r = od / 2.0
    inner_r = max(20.0, rim_d / 2.0 - 2.0)
    core = cylinder(outer_r, width, cx, cy - width / 2.0, cz, vec(0, 1, 0))
    hole = cylinder(inner_r, width + 8.0, cx, cy - width / 2.0 - 4.0, cz, vec(0, 1, 0))
    tyre = try_cut(core, hole, "tyre hole")
    # Rounded tread shoulders.
    shoulder_r = min(width, od - rim_d) * 0.22
    try:
        tor = Part.makeTorus(
            max(10.0, outer_r - shoulder_r),
            shoulder_r,
            vec(cx, cy, cz),
            vec(0, 1, 0),
        )
        tyre = try_fuse(tyre, tor)
    except Exception as exc:
        print(f"  tyre torus skipped: {exc}")
    return tyre


def make_rim(cx, cy, cz, rim_d, width):
    rw = width * 0.55
    barrel = cylinder(max(20.0, rim_d / 2.0 - 6.0), rw, cx, cy - rw / 2.0, cz, vec(0, 1, 0))
    hub = cylinder(rim_d * 0.18, rw + 10.0, cx, cy - (rw + 10.0) / 2.0, cz, vec(0, 1, 0))
    # Five simple spokes as boxes rotated around Y? Skip — a dish is enough.
    dish = cylinder(rim_d * 0.42, 8.0, cx, cy - 4.0, cz, vec(0, 1, 0))
    return try_fuse(try_fuse(barrel, hub), dish)


def side_window_ranges(P, V):
    """Return list of (x0, x1) for the main passenger window band."""
    L = Vv(V, "overall_length")
    entry_end = Vv(V, "entry_door_x") + Vv(V, "entry_door_width")
    start = entry_end + 80.0
    end = L - 520.0
    n = 5
    pillar = 80.0
    available = end - start
    win = (available - (n - 1) * pillar) / n
    ranges = []
    x = start
    for _ in range(n):
        ranges.append((x, x + win))
        x += win + pillar
    return ranges


def sides(V):
    """(sign_left, sign_right) from params: left/kerb/entry = -Y, right/offside/driver = +Y."""
    return Vv(V, "_y_left"), Vv(V, "_y_right")


def span(s, a, b):
    """Y interval between |a| and |b| on the side with sign s, as (ymin, ymax)."""
    ya, yb = s * a, s * b
    return (min(ya, yb), max(ya, yb))


def boot_layout(V):
    """Internal boot: opening in the lower part of the rear panel and the enclosure behind it."""
    floor = Vv(V, "floor_height")
    sill = Vv(V, "window_sill_z")
    z1 = floor + Vv(V, "boot_height_fraction") * (sill - floor)
    x_inner = Vv(V, "overall_length") - Vv(V, "wall_thickness")
    return {
        "z0": floor,
        "z1": z1,
        "half_w": Vv(V, "boot_opening_width") / 2.0,
        "x_inner": x_inner,
        "x_front": x_inner - Vv(V, "boot_depth_into_cabin"),
        "t": Vv(V, "boot_panel_thickness"),
    }


def boot_front_x(V):
    return boot_layout(V)["x_front"]


def entry_step_layout(V):
    """Entry Step tread in the kerb-side step well, as wide as the door (centred on it)."""
    hw = Vv(V, "overall_width") / 2.0
    iw = Vv(V, "interior_width")
    ex = Vv(V, "entry_door_x")
    ew = Vv(V, "entry_door_width")
    sw = min(opt(V, "entry_step_width", ew), ew)
    x0 = ex + (ew - sw) / 2.0
    return {
        "x0": x0, "x1": x0 + sw, "width": sw,
        "well_in": iw / 2.0 - Vv(V, "entry_step_well_inboard"),   # |y| of the well's inner edge
        "tread_depth": Vv(V, "entry_step_tread_depth"),
        "z_top": opt(V, "entry_step_z", Vv(V, "body_skirt_z")),
        "t": Vv(V, "entry_step_thickness"),
        "hw": hw,
    }


def living_floor_x1(V):
    """Living floor ends at the bedroom wall (forward face) if there is one, else at the boot."""
    if flag(V, "bedroom_enabled", True):
        return bedroom_layout(V)["wall_x0"]
    return boot_front_x(V)


def usable_floor_parts(V, x0=None, x1=None):
    """Return (polygon outline as list of (x,y), area_mm2, length, width, subtracted)
    for the floor strip x0..x1 (default: cab zone end to the living-floor end)."""
    iw = Vv(V, "interior_width")
    y0 = -iw / 2.0
    y1 = iw / 2.0
    if x0 is None:
        x0 = Vv(V, "cab_zone_length")
    if x1 is None:
        x1 = living_floor_x1(V)
    length = x1 - x0
    width = iw
    s_left, s_right = sides(V)

    # Start with the full rectangle area, subtract keep-outs that overlap it.
    area = length * width
    subtracted = []

    def band(s, w):
        """Inward band of width w against the side wall with sign s."""
        return (y1 - w, y1) if s > 0 else (y0, y0 + w)

    def overlap_area(ax0, ax1, ay0, ay1, name):
        ox0, ox1 = max(x0, ax0), min(x1, ax1)
        oy0, oy1 = max(y0, ay0), min(y1, ay1)
        if ox1 > ox0 and oy1 > oy0:
            a = (ox1 - ox0) * (oy1 - oy0)
            subtracted.append({"name": name, "area_mm2": a, "x0": ox0, "x1": ox1, "y0": oy0, "y1": oy1})
            return a
        return 0.0

    rear_axle = Vv(V, "front_overhang") + Vv(V, "wheelbase")
    front_axle = Vv(V, "front_overhang")
    for tag, s in (("L", s_left), ("R", s_right)):
        ra_l = Vv(V, "rear_arch_length")
        area -= overlap_area(rear_axle - ra_l / 2.0, rear_axle + ra_l / 2.0,
                             *band(s, Vv(V, "rear_arch_width")), f"ARCH_REAR_{tag}")
        fa_l = Vv(V, "front_arch_length")
        area -= overlap_area(front_axle - fa_l / 2.0, front_axle + fa_l / 2.0,
                             *band(s, Vv(V, "front_arch_width")), f"ARCH_FRONT_{tag}")

    # Entry step well on the LEFT / kerb side, at the entry door (lowered floor, as wide as the step).
    st = entry_step_layout(V)
    area -= overlap_area(st["x0"], st["x1"], *band(s_left, Vv(V, "entry_step_well_inboard")), "ENTRY_STEP")

    # Outline is the outer rectangle; keep-outs are stored separately for the face boolean.
    outline = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return outline, area, length, width, subtracted


def arch_housing_x0(axle, length):
    """Forward (low-X) face of an interior arch housing; add_arch_housings and the bedroom wall
    both use this, so the wall's rear face is exactly flush with the rear housings."""
    return axle - length / 2.0


def arch_cut_radius(V):
    """Radius of the wheel-arch cut in the body (tyre radius + 90 mm), as in arch_cutters."""
    return Vv(V, "tyre_od") / 2.0 + 90.0


def subtract_intervals(lo, hi, blocks, min_len):
    """[lo, hi] minus the (a, b) blocks, keeping pieces at least min_len long."""
    pieces = [(lo, hi)]
    for a, b in blocks:
        nxt = []
        for p0, p1 in pieces:
            if b <= p0 or a >= p1:
                nxt.append((p0, p1))
                continue
            if a > p0:
                nxt.append((p0, a))
            if b < p1:
                nxt.append((b, p1))
        pieces = nxt
    return [(round(a, 1), round(b, 1)) for a, b in pieces if b - a >= min_len]


def storage_layout(V):
    """Underfloor side bins: z from the skirt (bottom of the skin) up to the underside of the
    cabin floor. Runs per side between the bumpers, the wheel-arch cuts and (kerb) the step well.
    Where kerb and offside runs overlap and nothing modelled is in the way, one bin passes right
    across (flap each side). Pure Python so it can be checked without FreeCAD."""
    L = Vv(V, "overall_length")
    s_left, s_right = sides(V)
    front_axle = Vv(V, "front_overhang")
    rear_axle = front_axle + Vv(V, "wheelbase")
    R = arch_cut_radius(V)
    ca, cb, cs = Vv(V, "storage_clear_arch"), Vv(V, "storage_clear_bumper"), Vv(V, "storage_clear_step")
    # Front bumper ends at body_front_x + 50 (it is sunk 50 into the face); rear bumper starts at L - 110.
    lo = max(opt(V, "storage_min_x", Vv(V, "cab_zone_length")), Vv(V, "body_front_x") + 50.0 + cb)
    hi = L - 110.0 - cb
    arches = [(front_axle - R - ca, front_axle + R + ca), (rear_axle - R - ca, rear_axle + R + ca)]
    st = entry_step_layout(V)
    step_block = (st["x0"] - cs, st["x1"] + cs)
    min_run = Vv(V, "storage_min_run")
    runs = {}
    for tag, key, blocks in (("L", "storage_left_runs", arches + [step_block]),
                             ("R", "storage_right_runs", arches)):
        override = V.get(key)
        if override:
            runs[tag] = [(float(a), float(b)) for a, b in override]
        else:
            runs[tag] = subtract_intervals(lo, hi, blocks, min_run)

    # Split into segments: overlaps -> through bins (if allowed), the rest -> side-only bins.
    through = []
    if flag(V, "storage_pass_through", True):
        for a0, a1 in runs["L"]:
            for b0, b1 in runs["R"]:
                o0, o1 = max(a0, b0), min(a1, b1)
                if o1 - o0 >= min_run:
                    through.append((o0, o1))
    segments = []
    for x0, x1 in through:
        segments.append({"kind": "through", "x0": x0, "x1": x1, "sides": ["L", "R"]})
    for tag in ("L", "R"):
        for r0, r1 in runs[tag]:
            for p0, p1 in subtract_intervals(r0, r1, through, 1.0):
                segments.append({"kind": "side", "x0": p0, "x1": p1, "sides": [tag]})
    segments.sort(key=lambda g: (g["x0"], g["kind"]))
    n_side = {"L": 0, "R": 0}
    n_flap = {"L": 0, "R": 0}
    n_thru = 0
    for g in segments:
        if g["kind"] == "through":
            n_thru += 1
            g["bin"] = f"STO_BIN_T{n_thru}"
        else:
            tag = g["sides"][0]
            n_side[tag] += 1
            g["bin"] = f"STO_BIN_{tag}{n_side[tag]}"
        g["flaps"] = []
        for tag in g["sides"]:
            n_flap[tag] += 1
            g["flaps"].append(f"STO_FLAP_{tag}{n_flap[tag]}")
        g["length"] = round(g["x1"] - g["x0"], 1)
    hinge = str(flag(V, "storage_flap_hinge", "top")).lower()
    return {
        "z0": Vv(V, "body_skirt_z"),
        "z1": Vv(V, "floor_height") - Vv(V, "floor_thickness"),
        "depth": Vv(V, "storage_bin_depth_inboard"),
        "t": Vv(V, "storage_panel_thickness"),
        "flap_t": Vv(V, "storage_flap_thickness"),
        "hinge": "bottom" if hinge == "bottom" else "top",
        "runs": runs,
        "run_lengths": {k: [round(b - a, 1) for a, b in v] for k, v in runs.items()},
        "segments": segments,
        "limits": {"lo": lo, "hi": hi, "arch_blocks": arches, "step_block": step_block},
        "sides": {"L": s_left, "R": s_right},
    }


def bedroom_layout(V):
    """Bedroom at the rear: dividing wall, sliding door, bed platform. Pure Python."""
    iw = Vv(V, "interior_width")
    floor = Vv(V, "floor_height")
    ceiling = Vv(V, "overall_height") - Vv(V, "roof_thickness")
    s_left, s_right = sides(V)
    B = boot_layout(V)
    boot_top = B["z1"] + B["t"]
    mw, ml = Vv(V, "bed_mattress_width"), Vv(V, "bed_mattress_length")
    orient = str(flag(V, "bed_orientation", "lengthwise")).lower()
    along, across = (ml, mw) if orient != "crosswise" else (mw, ml)
    plat_len = opt(V, "bed_platform_length", along)
    plat_w = opt(V, "bed_platform_width", min(across, iw))
    over_boot = bool(flag(V, "bed_over_boot", True))
    bed_x1 = B["x_inner"] if over_boot else B["x_front"]
    bed_x0 = bed_x1 - plat_len
    walkway_target = Vv(V, "bedroom_walkway")
    rear_axle = Vv(V, "front_overhang") + Vv(V, "wheelbase")
    ra0 = arch_housing_x0(rear_axle, Vv(V, "rear_arch_length"))
    ra1 = ra0 + Vv(V, "rear_arch_length")
    # Wall's rear (bedroom) face flush with the forward face of the rear arch housings.
    wall_x = opt(V, "bedroom_wall_x", ra0)
    wall_t = Vv(V, "bedroom_wall_thickness")
    walkway = bed_x0 - wall_x
    arch_top = floor + Vv(V, "rear_arch_height")
    arch_under_bed = ra1 > bed_x0 and ra0 < bed_x1
    if over_boot:
        default_top = max(boot_top, arch_top if arch_under_bed else 0.0)
    else:
        default_top = max(floor + 450.0, arch_top if arch_under_bed else 0.0)
    p_top = floor + opt(V, "bed_platform_height", default_top - floor)
    # Centred bi-parting pair: each leaf covers half the opening plus the jamb overlap, meets the
    # other at y=0 (centre gap), and slides half the opening toward its own side wall.
    door_w = Vv(V, "bedroom_door_opening_width")
    door_h = min(Vv(V, "bedroom_door_height"), ceiling - floor - 100.0)
    overlap = Vv(V, "bedroom_door_leaf_overlap")
    gap = Vv(V, "bedroom_door_centre_gap")
    side_clr = Vv(V, "bedroom_door_side_clearance")
    leaf_w = door_w / 2.0 + overlap - gap / 2.0
    travel = door_w / 2.0
    inner_open = gap / 2.0 + travel                 # |y| of the leaf's inner edge when open
    outer_open = gap / 2.0 + leaf_w + travel        # |y| of the leaf's outer edge when open
    return {
        "orientation": "crosswise" if orient == "crosswise" else "lengthwise",
        "mattress_along_x": along, "mattress_across_y": across,
        "mattress_overrun_mm": round(across - iw, 1),
        "platform_length": plat_len, "platform_width": plat_w,
        "platform_overrun_mm": round(plat_w - iw, 1),
        "over_boot": over_boot,
        "bed_x0": bed_x0, "bed_x1": bed_x1,
        "platform_top_z": p_top, "platform_height_above_floor": p_top - floor,
        "boot_top_z": boot_top, "rear_arch_top_z": arch_top, "rear_arch_under_bed": arch_under_bed,
        "ceiling_z": ceiling,
        "headroom_over_platform": ceiling - p_top,
        "headroom_over_mattress": ceiling - p_top - Vv(V, "bed_mattress_thickness"),
        "walkway": walkway, "walkway_target": walkway_target,
        "walkway_short_mm": round(max(0.0, walkway_target - walkway), 1),
        "bed_fits": walkway >= 0.0,
        "rear_arch_x0": ra0, "rear_arch_x1": ra1,
        "wall_x": wall_x, "wall_x0": wall_x - wall_t, "wall_t": wall_t,
        "bedroom_length": B["x_inner"] - wall_x,
        "door_w": door_w, "door_h": door_h, "door_t": Vv(V, "bedroom_door_thickness"),
        "door_y_center": 0.0, "door_leaf_w": leaf_w, "door_travel": travel,
        "door_overlap": overlap, "door_centre_gap": gap,
        "door_inner_open": inner_open, "door_outer_open": outer_open,
        "door_clears_opening": inner_open >= door_w / 2.0 - 1e-6,
        "door_clears_side_walls": outer_open <= iw / 2.0 - side_clr + 1e-6,
        "door_max_opening": iw / 2.0 - side_clr - overlap,
        "door_sides": {"L": s_left, "R": s_right},
        "x_inner": B["x_inner"], "boot_front": B["x_front"],
    }


def face_with_cutouts(outline, cutouts, z):
    outer = Part.makePolygon([vec(x, y, z) for x, y in outline + [outline[0]]])
    face = Part.Face(outer)
    for c in cutouts:
        rect = [
            vec(c["x0"], c["y0"], z),
            vec(c["x1"], c["y0"], z),
            vec(c["x1"], c["y1"], z),
            vec(c["x0"], c["y1"], z),
            vec(c["x0"], c["y0"], z),
        ]
        try:
            hole = Part.Face(Part.makePolygon(rect))
            face = face.cut(hole)
        except Exception as exc:
            print(f"  floor cutout {c['name']} failed: {exc}")
    return face


def add_prop(obj, typ, name, group_name, value, doc=""):
    try:
        if not hasattr(obj, name):
            obj.addProperty(typ, name, group_name, doc)
        setattr(obj, name, value)
    except Exception as exc:
        print(f"  property {name} failed: {exc}")


def merge_vertices(verts, faces, tol=0.01):
    """Weld coincident vertices (per-face tessellation duplicates seam nodes) and drop degenerate triangles."""
    key_to_idx = {}
    new = []
    remap = []
    for v in verts:
        k = (round(v[0] / tol), round(v[1] / tol), round(v[2] / tol))
        i = key_to_idx.get(k)
        if i is None:
            i = len(new)
            key_to_idx[k] = i
            new.append((float(v[0]), float(v[1]), float(v[2])))
        remap.append(i)
    out = []
    for f in faces:
        a, b, c = remap[f[0]], remap[f[1]], remap[f[2]]
        if a != b and b != c and a != c:
            out.append((a, b, c))
    return new, out


def refine_mesh(verts, faces, max_edge):
    """Conforming longest-edge bisection until no edge exceeds max_edge.

    Every triangle sharing a split edge is split at the same midpoint, so a
    watertight input stays watertight (no T-junctions). Winding is preserved.
    """
    import heapq

    verts = [tuple(v) for v in verts]
    tris = {}
    edge_tris = {}
    heap = []
    counter = [0]
    max2 = float(max_edge) ** 2

    def ekey(a, b):
        return (a, b) if a < b else (b, a)

    def len2(e):
        p, q = verts[e[0]], verts[e[1]]
        return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2

    def add_tri(t):
        tid = counter[0]
        counter[0] += 1
        tris[tid] = t
        for i in range(3):
            e = ekey(t[i], t[(i + 1) % 3])
            edge_tris.setdefault(e, set()).add(tid)
            l2 = len2(e)
            if l2 > max2:
                heapq.heappush(heap, (-l2, e))

    def remove_tri(tid):
        t = tris.pop(tid)
        for i in range(3):
            e = ekey(t[i], t[(i + 1) % 3])
            s = edge_tris.get(e)
            if s is not None:
                s.discard(tid)
                if not s:
                    del edge_tris[e]
        return t

    for f in faces:
        add_tri(tuple(f))

    while heap:
        _, e = heapq.heappop(heap)
        owners = edge_tris.get(e)
        if not owners:
            continue
        p, q = verts[e[0]], verts[e[1]]
        m = len(verts)
        verts.append(((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0, (p[2] + q[2]) / 2.0))
        for tid in list(owners):
            t = remove_tri(tid)
            for i in range(3):
                u, w, c = t[i], t[(i + 1) % 3], t[(i + 2) % 3]
                if ekey(u, w) == e:
                    add_tri((u, m, c))
                    add_tri((m, w, c))
                    break
    return verts, list(tris.values())


def mesh_edge_report(faces):
    """Count open (boundary) and non-manifold edges of a welded triangle list."""
    counts = {}
    for a, b, c in faces:
        for e in ((a, b), (b, c), (c, a)):
            k = (e[0], e[1]) if e[0] < e[1] else (e[1], e[0])
            counts[k] = counts.get(k, 0) + 1
    open_e = sum(1 for n in counts.values() if n == 1)
    nonman = sum(1 for n in counts.values() if n > 2)
    return {"triangles": len(faces), "open_edges": open_e, "nonmanifold_edges": nonman}


def tessellate_shape(shape, deviation, max_edge=0.0):
    if shape is None or shape.isNull():
        return None, None
    verts, faces = shape.tessellate(float(deviation))
    if not verts or not faces:
        return None, None
    verts = [(v.x, v.y, v.z) for v in verts]
    faces = [tuple(f) for f in faces]
    verts, faces = merge_vertices(verts, faces)
    if max_edge and max_edge > 0:
        verts, faces = refine_mesh(verts, faces, max_edge)
    return verts, faces


def tessellate_obj(obj, deviation, max_edge=0.0):
    verts, faces = tessellate_shape(obj.Shape, deviation, max_edge)
    if not verts or not faces:
        return None
    return {
        "name": obj.Name,
        "label": obj.Label,
        "vertices": verts,
        "faces": faces,
    }


def reset_document():
    existing = App.listDocuments()
    for name, d in list(existing.items()):
        if name == DOC_NAME or d.Label == DOC_NAME:
            App.closeDocument(name)
    doc = App.newDocument(DOC_NAME)
    doc.Label = DOC_NAME
    return doc


# --------------------------------------------------------------------------
# Body geometry
# --------------------------------------------------------------------------

def body_dims(V):
    L = Vv(V, "overall_length")
    W = Vv(V, "overall_width")
    D = {
        "L": L,
        "W": W,
        "H": Vv(V, "overall_height"),
        "hw": W / 2.0,
        "skirt": Vv(V, "body_skirt_z"),
        "x_front": Vv(V, "body_front_x"),
        "x_rear": L - Vv(V, "rear_face_setback"),
        "tan": math.tan(math.radians(Vv(V, "front_rake_deg"))),
        "r": Vv(V, "body_edge_radius"),
        "wall": Vv(V, "wall_thickness"),
        "roof_t": Vv(V, "roof_thickness"),
    }
    D["cos"] = 1.0 / math.sqrt(1.0 + D["tan"] ** 2)
    return D


def front_x_at(D, z, inset=0.0):
    """X of the flat raked front face at height z, moved aft by a perpendicular inset."""
    return D["x_front"] + (z - D["skirt"]) * D["tan"] + inset / D["cos"]


def front_normal(D):
    """Outward unit normal of the flat front face (forward and slightly up)."""
    n = vec(-1.0, 0.0, D["tan"])
    n.normalize()
    return n


def front_prism(D, y0, y1, z0, z1, d_out, depth):
    """Prism on the raked front plane: a rectangle (y0..y1, z0..z1) offset d_out
    outward along the face normal, extruded `depth` inward."""
    n = front_normal(D)
    pts = []
    for y, z in ((y0, z0), (y1, z0), (y1, z1), (y0, z1)):
        p = vec(front_x_at(D, z), y, z)
        pts.append(p + vec(n.x * d_out, n.y * d_out, n.z * d_out))
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    return face.extrude(vec(-n.x * depth, -n.y * depth, -n.z * depth))


def side_cutter(D, s, x0, x1, z0, z1):
    """Box that punches through the side wall with sign s (and 20 mm past its inner face)."""
    t = D["wall"] + 80.0
    y0 = (D["hw"] - D["wall"] - 20.0) if s > 0 else -(D["hw"] + 60.0)
    return box(x1 - x0, t, z1 - z0, x0, y0, z0)


def side_slab_y(D, s, depth, thick):
    """Y-min of a slab whose outer face is `depth` inside the side skin with sign s."""
    outer = D["hw"] - depth
    return (outer - thick) if s > 0 else -outer


def round_vertical_edges(shp, r):
    try:
        edges = [e for e in shp.Edges
                 if len(e.Vertexes) == 2 and abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1.0]
        out = shp.makeFillet(r, edges)
        if out.isValid():
            return out
    except Exception as exc:
        print(f"  edge rounding skipped: {exc}")
    return shp


def upper_edges(solid, z_floor):
    """All edges except those lying in the bottom plane z_floor."""
    return [e for e in solid.Edges if max(v.Point.z for v in e.Vertexes) > z_floor + 1.0]


def prism_xz(profile, y0, width):
    """Extrude a closed XZ polygon (list of (x, z)) from y0 across +Y by width."""
    pts = [vec(x, y0, z) for x, z in profile]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(vec(0, width, 0))


def build_exterior(V):
    """Boxy 2nd-gen Coaster body: flat raked front, flat roof, vertical rear and sides,
    all upper edges radiused. The boot is internal, so the rear is a plain face."""
    D = body_dims(V)
    hw, z0, z1 = D["hw"], D["skirt"], D["H"]
    profile = [
        (front_x_at(D, z0), z0),
        (D["x_rear"], z0),
        (D["x_rear"], z1),
        (front_x_at(D, z1), z1),
    ]
    solid = prism_xz(profile, -hw, D["W"])
    edges = upper_edges(solid, z0)
    try:
        body = solid.makeFillet(D["r"], edges)
        if body.isNull() or not body.isValid():
            raise RuntimeError("fillet result invalid")
        print(f"  exterior: {len(edges)} edges filleted at r={D['r']:.0f}")
    except Exception as exc:
        print(f"  WARNING exterior fillet failed ({exc}); using sharp-edged body")
        FAILED_OPS.append("exterior_fillet")
        body = solid

    return as_single_solid(body, "exterior")


def build_cavity(V):
    """Cabin void: same boxy form inset by the wall (sides/front/rear) and roof thickness."""
    D = body_dims(V)
    hw = Vv(V, "interior_width") / 2.0
    z0 = Vv(V, "floor_height")
    z1 = D["H"] - D["roof_t"]
    x_rear = D["L"] - D["wall"]
    profile = [
        (front_x_at(D, z0, D["wall"]), z0),
        (x_rear, z0),
        (x_rear, z1),
        (front_x_at(D, z1, D["wall"]), z1),
    ]
    solid = prism_xz(profile, -hw, 2.0 * hw)
    r_in = max(20.0, D["r"] - D["wall"])
    try:
        cav = solid.makeFillet(r_in, upper_edges(solid, z0))
        if cav.isNull() or not cav.isValid():
            raise RuntimeError("fillet result invalid")
        return cav
    except Exception as exc:
        print(f"  cavity fillet failed ({exc}); using sharp cavity")
        return solid


def as_single_solid(shp, label):
    try:
        shp = shp.removeSplitter()
    except Exception:
        pass
    if shp.ShapeType != "Solid" and len(shp.Solids) == 1:
        shp = shp.Solids[0]
    if not shp.isValid():
        try:
            shp.fix(0.01, 0.01, 0.1)
        except Exception as exc:
            print(f"  fix failed ({label}): {exc}")
    if len(shp.Solids) != 1:
        print(f"  WARNING {label}: {len(shp.Solids)} solids (expected 1)")
    return shp


def arch_cutters(V):
    W = Vv(V, "overall_width")
    hw = W / 2.0
    wall = Vv(V, "wall_thickness")
    od = Vv(V, "tyre_od")
    radius = od / 2.0 + 90.0
    cz = od / 2.0
    front_axle = Vv(V, "front_overhang")
    rear_axle = front_axle + Vv(V, "wheelbase")
    s_left, s_right = sides(V)
    y_out = hw + 80.0
    cutters = []
    for axle, arch_w, name in (
        (front_axle, Vv(V, "front_arch_width"), "front"),
        (rear_axle, Vv(V, "rear_arch_width"), "rear"),
    ):
        # Stop 20 mm inside the interior arch housing so the housing closes the hole.
        y_in = hw - wall - arch_w + 20.0
        for tag, s in (("L", s_left), ("R", s_right)):
            y0, y1 = span(s, y_in, y_out)
            cutters.append((f"{name}_{tag}", u_arch_cutter(axle, y0, y1, radius, cz)))
    return cutters


def windscreen_layout(V, D):
    z0 = Vv(V, "windscreen_sill_z")
    z1 = min(Vv(V, "windscreen_head_z"), D["H"] - D["r"] - 40.0)
    y_out = D["hw"] - D["r"] - Vv(V, "a_pillar_width")
    y_in = Vv(V, "windscreen_mullion") / 2.0
    return z0, z1, y_in, y_out


def door_top(V, height_key, z_floor):
    """Door head, kept at or below the window head so it never notches the roof radius."""
    return min(z_floor + Vv(V, height_key), Vv(V, "window_head_z"))


DRIVER_WIN_FRAC = 0.45   # share of the driver door height taken by its window (door_panel)
WINDOW_PILLAR = 80.0     # pillar between side windows (side_window_ranges)


def driver_glass_profile(V):
    """Window opening in the Driver Door leaf, same formula as door_panel(): (x0, x1, z0, z1)."""
    floor = Vv(V, "floor_height")
    x = Vv(V, "driver_door_x")
    w = Vv(V, "driver_door_width")
    z1 = door_top(V, "driver_door_height", floor)
    win_h = (z1 - floor) * DRIVER_WIN_FRAC
    z0 = z1 - 80.0 - win_h
    return x + 80.0, x + w - 80.0, z0, z0 + win_h


def passenger_window_layout(V):
    """Fixed kerb-side cab window opposite the driver door: the Driver Door Glass profile
    mirrored to y_sign_left (params override), trimmed to keep a pillar to the A-pillar/front
    corner and to the entry door opening."""
    D = body_dims(V)
    gx0, gx1, gz0, gz1 = driver_glass_profile(V)
    x0 = opt(V, "passenger_window_x0", gx0)
    x1 = opt(V, "passenger_window_x1", gx1)
    z0 = opt(V, "passenger_window_sill_z", gz0)
    z1 = opt(V, "passenger_window_head_z", gz1)
    pillar = opt(V, "passenger_window_min_pillar", WINDOW_PILLAR)
    # Front limit: raked face at the window head, plus the edge radius and a pillar.
    x_min = front_x_at(D, z1) + D["r"] + pillar
    x_max = Vv(V, "entry_door_x") - pillar
    out = {"profile": [gx0, gx1, gz0, gz1], "x_min": x_min, "x_max": x_max, "pillar": pillar,
           "trimmed_front": x0 < x_min, "trimmed_rear": x1 > x_max}
    out.update(x0=max(x0, x_min), x1=min(x1, x_max), z0=z0, z1=z1)
    return out


def rear_window_half_width(D):
    return D["hw"] - D["r"] - 60.0


def punch_openings(shell, V):
    D = body_dims(V)
    s_left, s_right = sides(V)
    wall = D["wall"]
    floor = Vv(V, "floor_height")

    # Two-piece windscreen in the flat front, between slim A-pillars and a centre mullion.
    ws_z0, ws_z1, ws_yi, ws_yo = windscreen_layout(V, D)
    for tag, s in (("L", s_left), ("R", s_right)):
        y0, y1 = span(s, ws_yi, ws_yo)
        cutter = front_prism(D, y0, y1, ws_z0, ws_z1, 40.0, 40.0 + wall + 60.0)
        shell = try_cut(shell, cutter, f"windscreen_{tag}")

    # Folding entry door, LEFT / kerb side; opening runs down to the skirt (step well).
    ex = Vv(V, "entry_door_x")
    ew = Vv(V, "entry_door_width")
    st = entry_step_layout(V)
    shell = try_cut(shell, side_cutter(D, s_left, ex, ex + ew, min(D["skirt"], st["z_top"]) - 10.0,
                                       door_top(V, "entry_door_height", floor)), "entry_door")

    # Step well: the floor slab inside the entry door, from the skin to the well's inner edge,
    # removed down to the Entry Step tread (open at the bottom when the tread is at the skirt).
    wz0 = (D["skirt"] - 10.0) if st["z_top"] <= D["skirt"] + 1.0 else st["z_top"]
    wy0, wy1 = span(s_left, st["well_in"], D["hw"] + 60.0)
    shell = try_cut(shell, box(st["x1"] - st["x0"], wy1 - wy0, floor + 10.0 - wz0, st["x0"], wy0, wz0),
                    "entry_step_well")

    # Underfloor storage: one void per bin through the skin and slab, from below the skirt up to
    # the underside of the cabin floor (side-only bins storage_bin_depth_inboard deep; through bins
    # right across). The bin walls and flaps are separate objects in the Storage group.
    S = storage_layout(V)
    for g in S["segments"]:
        if g["kind"] == "through":
            vy0, vy1 = -(D["hw"] + 60.0), D["hw"] + 60.0
        else:
            vy0, vy1 = span(S["sides"][g["sides"][0]], D["hw"] - S["depth"], D["hw"] + 60.0)
        shell = try_cut(shell, box(g["x1"] - g["x0"], vy1 - vy0, S["z1"] - (S["z0"] - 10.0),
                                   g["x0"], vy0, S["z0"] - 10.0), "storage_" + g["bin"])

    # Driver door, RIGHT / offside.
    dx = Vv(V, "driver_door_x")
    dw = Vv(V, "driver_door_width")
    shell = try_cut(shell, side_cutter(D, s_right, dx, dx + dw, floor,
                                       door_top(V, "driver_door_height", floor)), "driver_door")

    # Fixed passenger-side cab window, LEFT / kerb, opposite the driver door.
    pw = passenger_window_layout(V)
    if pw["x1"] - pw["x0"] > 50.0:
        shell = try_cut(shell, side_cutter(D, s_left, pw["x0"], pw["x1"], pw["z0"], pw["z1"]),
                        "passenger_window")

    # Side window band, both sides.
    sill = Vv(V, "window_sill_z")
    head = Vv(V, "window_head_z")
    for x0, x1 in side_window_ranges(None, V):
        for tag, s in (("L", s_left), ("R", s_right)):
            shell = try_cut(shell, side_cutter(D, s, x0, x1, sill, head), f"win_{tag}_{int(x0)}")

    # Full-width rear window (no rear door on the 1988 LWB).
    rw = rear_window_half_width(D)
    shell = try_cut(shell, box(wall + 100.0, 2.0 * rw, head - sill, D["L"] - wall - 40.0, -rw, sill),
                    "rear_window")

    # Boot opening through the lower rear panel (floor line up to boot_height_fraction of the
    # floor-to-sill height); the fixed rear panel above it runs up to the rear window.
    B = boot_layout(V)
    shell = try_cut(shell, box(wall + 100.0, 2.0 * B["half_w"], B["z1"] - B["z0"],
                               D["L"] - wall - 40.0, -B["half_w"], B["z0"]), "boot_opening")
    return shell


def add_glass_and_doors(doc, V, colors, groups):
    D = body_dims(V)
    s_left, s_right = sides(V)
    floor = Vv(V, "floor_height")
    glass_t = 6.0
    recess = 15.0      # glass outer face sits this far inside the skin
    clr = 2.0          # clearance to the opening edge
    door_t = 40.0
    gcol = colors["glass_color"]
    galpha = int(round(100 * (1.0 - float(colors.get("glass_alpha", 0.45)))))
    dcol = colors["body_color"]

    wall = D["wall"]

    def glass(name, shp, filler_shp=None, filler_col=None):
        """Glass pane plus (optionally) its solid filler: skin-thick, body colour, flush in the
        opening. Which one shows is set by the pane's Glazed property (see window_controls)."""
        gobj = add_shape(name, shp, groups["GRP_GLAZING"], gcol, galpha)
        if filler_shp is not None:
            fobj = add_shape(name.replace("GLZ_", "FIL_", 1), filler_shp, groups["GRP_GLAZING"],
                             filler_col or dcol)
            WINDOWS.append((gobj, fobj))
        return gobj

    # Two windscreen panes, recessed in the raked front.
    ws_z0, ws_z1, ws_yi, ws_yo = windscreen_layout(V, D)
    for tag, s in (("L", s_left), ("R", s_right)):
        y0, y1 = span(s, ws_yi + clr, ws_yo - clr)
        fy0, fy1 = span(s, ws_yi, ws_yo)
        glass(f"GLZ_WINDSCREEN_{tag}", front_prism(D, y0, y1, ws_z0 + clr, ws_z1 - clr, -recess, glass_t),
              front_prism(D, fy0, fy1, ws_z0, ws_z1, 0.0, wall))

    # Side windows.
    sill = Vv(V, "window_sill_z")
    head = Vv(V, "window_head_z")
    for i, (x0, x1) in enumerate(side_window_ranges(None, V), start=1):
        for tag, s in (("L", s_left), ("R", s_right)):
            glass(f"GLZ_SIDE_{tag}_{i}",
                  box(x1 - x0 - 2 * clr, glass_t, head - sill - 2 * clr,
                      x0 + clr, side_slab_y(D, s, recess, glass_t), sill + clr),
                  box(x1 - x0, wall, head - sill, x0, side_slab_y(D, s, 0.0, wall), sill))

    # Passenger Side Window: fixed glass, recessed like the side windows.
    pw = passenger_window_layout(V)
    if pw["x1"] - pw["x0"] > 50.0:
        glass("GLZ_PASSENGER", box(pw["x1"] - pw["x0"] - 2 * clr, glass_t, pw["z1"] - pw["z0"] - 2 * clr,
                                   pw["x0"] + clr, side_slab_y(D, s_left, recess, glass_t), pw["z0"] + clr),
              box(pw["x1"] - pw["x0"], wall, pw["z1"] - pw["z0"], pw["x0"],
                  side_slab_y(D, s_left, 0.0, wall), pw["z0"]))

    # Full-width rear window (filler spans the rear wall, inner face to the rear skin).
    rw0 = rear_window_half_width(D)
    rw = rw0 - clr
    glass("GLZ_REAR", box(glass_t, 2.0 * rw, head - sill - 2 * clr,
                          D["x_rear"] - recess - glass_t, -rw, sill + clr),
          box(D["x_rear"] - (D["L"] - wall), 2.0 * rw0, head - sill, D["L"] - wall, -rw0, sill))

    def door_panel(name, s, x, width, z0, z1, win_frac):
        y = side_slab_y(D, s, 4.0, door_t)
        h = z1 - z0
        panel = box(width - 8.0, door_t, h - 6.0, x + 4.0, y, z0 + 3.0)
        win_h = h * win_frac          # driver: matches driver_glass_profile()
        win_z = z1 - 80.0 - win_h
        cutter = box(width - 160.0, door_t + 20.0, win_h, x + 80.0, y - 10.0, win_z)
        panel = try_cut(panel, cutter, name + "_win")
        # Door glass is its own object (not in a compound) so it can follow the door's Placement.
        # Its filler fills the leaf's window cut at leaf thickness and moves with the door too.
        gobj = glass(name.replace("DR_", "GLZ_"),
                     box(width - 164.0, glass_t, win_h - 4.0, x + 82.0,
                         y + door_t / 2.0 - glass_t / 2.0, win_z + 2.0),
                     box(width - 160.0, door_t, win_h, x + 80.0, y, win_z))
        return add_shape(name, panel, groups["GRP_DOORS"], dcol), gobj

    ex = Vv(V, "entry_door_x")
    entry, entry_glass = door_panel("DR_ENTRY", s_left, ex, Vv(V, "entry_door_width"),
                                    D["skirt"], door_top(V, "entry_door_height", floor), 0.55)
    dx = Vv(V, "driver_door_x")
    driver, driver_glass = door_panel("DR_DRIVER", s_right, dx, Vv(V, "driver_door_width"),
                                      floor, door_top(V, "driver_door_height", floor), DRIVER_WIN_FRAC)
    make_entry_door_operable(V, entry, entry_glass, s_left)
    # Hinge: front (low-X) vertical edge of the door leaf, on its outer face.
    make_driver_door_operable(V, driver, driver_glass, s_right,
                              dx + 4.0, s_right * (D["hw"] - 4.0))
    for door in (entry, driver):
        follow_placement(doc.getObject(door.Name.replace("DR_", "FIL_")), door)

    # Boot lid: flush in the lower rear-panel opening, top-hinged. Not a cabin door.
    B = boot_layout(V)
    lid_w = 2.0 * B["half_w"] - 8.0
    lid_h = B["z1"] - B["z0"] - 8.0
    if lid_h > 50.0 and lid_w > 50.0:
        lid = box(28.0, lid_w, lid_h, D["x_rear"] - 30.0, -lid_w / 2.0, B["z0"] + 4.0)
        obj = add_shape("DR_BOOT_LID", lid, groups["GRP_DOORS"], dcol)
        add_prop(obj, "App::PropertyString", "Hinge", "Door", "top edge, opens upward and outward",
                 "Boot lid hinge line (internal boot behind the lower rear panel; not a cabin door)")
        # Hinge: top outer edge of the lid.
        make_boot_lid_operable(V, obj, D["x_rear"] - 2.0, B["z1"] - 4.0)


def add_boot_enclosure(V, colors, groups):
    """Internal boot box: front face + top across the inside width, standing on the cabin floor
    at the rear. Its top's underside is level with the boot opening head."""
    B = boot_layout(V)
    iw = Vv(V, "interior_width")
    t = B["t"]
    depth = B["x_inner"] - B["x_front"]
    front = box(t, iw, B["z1"] + t - B["z0"], B["x_front"], -iw / 2.0, B["z0"])
    top = box(depth, iw, t, B["x_front"], -iw / 2.0, B["z1"])
    shp = as_single_solid(try_fuse(front, top, "boot_enclosure"), "boot_enclosure")
    obj = add_shape("BOOT_ENCLOSURE", shp, groups["GRP_CABIN"], colors.get("arch_color"))
    add_prop(obj, "App::PropertyFloat", "DepthIntoCabin_mm", "Coaster", float(depth),
             "Protrusion into the cabin from the inner rear wall, mm (nominal, verify)")
    return obj


def add_entry_step(V, colors, groups):
    """Entry Step: tread in the kerb-side step well, at the bottom of the entry door opening,
    below cabin floor level and outboard of the floor edge. In the Cabin group (fixed fitting)."""
    st = entry_step_layout(V)
    s_left, _ = sides(V)
    y0, y1 = span(s_left, st["hw"] - 5.0 - st["tread_depth"], st["hw"] - 5.0)
    shp = box(st["x1"] - st["x0"], y1 - y0, st["t"], st["x0"], y0, st["z_top"] - st["t"])
    obj = add_shape("STEP_ENTRY", shp, groups["GRP_CABIN"], colors.get("bumper_color", (0.2, 0.2, 0.2)))
    add_prop(obj, "App::PropertyString", "Note", "Coaster",
             "Tread top at entry_step_z (default = bottom of the entry door opening). Nominal - VERIFY. "
             "Only the step in the well is modelled; the ground-to-step rise is not.", "Layout note")
    return obj


def add_storage(V, colors, groups):
    """Underfloor bins (walls as an open tray), hinged flaps with OpenAngle, and lock markers."""
    D = body_dims(V)
    S = storage_layout(V)
    hw, t, ft = D["hw"], S["t"], S["flap_t"]
    z0, z1 = S["z0"], S["z1"]
    grp = groups["GRP_STORAGE"]
    bin_col = colors.get("arch_color", (0.4, 0.4, 0.4))
    flap_col = colors.get("body_lower_color", colors["body_color"])
    lock_col = colors.get("light_rear_color", (0.8, 0.1, 0.1))
    top = S["hinge"] == "top"
    for g in S["segments"]:
        x0, x1 = g["x0"], g["x1"]
        if g["kind"] == "through":
            oy0, oy1 = -(hw - 30.0), hw - 30.0
            iy0, iy1 = -(hw + 10.0), hw + 10.0
        else:
            s = S["sides"][g["sides"][0]]
            oy0, oy1 = span(s, hw - S["depth"], hw - 30.0)
            iy0, iy1 = span(s, hw - S["depth"] + t, hw + 10.0)
        outer = box(x1 - x0, oy1 - oy0, z1 - z0, x0, oy0, z0)
        inner = box(x1 - x0 - 2 * t, iy1 - iy0, z1 - z0 - 2 * t, x0 + t, iy0, z0 + t)
        tray = as_single_solid(try_cut(outer, inner, g["bin"]), g["bin"])
        bobj = add_shape(g["bin"], tray, grp, bin_col)
        add_prop(bobj, "App::PropertyFloat", "RunLength_mm", "Coaster", float(x1 - x0),
                 "Bin length along X, mm (derived; override with storage_left_runs/storage_right_runs)")
        add_prop(bobj, "App::PropertyString", "Note", "Coaster",
                 "Real underfloor (chassis rails, fuel tank, spare wheel, exhaust, driveshaft) is NOT "
                 "modelled - measure before building.", "Layout note")
        for tag, fname in zip(g["sides"], g["flaps"]):
            s = S["sides"][tag]
            fy0, fy1 = span(s, hw - 5.0 - ft, hw - 5.0)
            flap = add_shape(fname, box(x1 - x0 - 8.0, fy1 - fy0, z1 - z0 - 8.0, x0 + 4.0, fy0, z0 + 4.0),
                             grp, flap_col)
            # Lock marker on the free edge (bottom if top-hinged), proud of the flap face.
            ly0, ly1 = span(s, hw - 5.0, hw + 3.0)
            lz = (z0 + 10.0) if top else (z1 - 35.0)
            lock = add_shape(fname.replace("STO_FLAP_", "STO_LOCK_"),
                             box(50.0, ly1 - ly0, 25.0, (x0 + x1) / 2.0 - 25.0, ly0, lz), grp, lock_col)
            make_flap_operable(V, flap, lock, s, s * (hw - 5.0), (z1 - 4.0) if top else (z0 + 4.0), top)
    return S


def add_bedroom(V, colors, groups, cavity):
    """Dividing wall (fitted to the cabin section), bi-parting doors, bed platform, bedroom floor."""
    Bd = bedroom_layout(V)
    iw = Vv(V, "interior_width")
    floor = Vv(V, "floor_height")
    grp = groups["GRP_BEDROOM"]
    ceil_z = Bd["ceiling_z"]
    # Wall: a slab clipped to the cabin void, so it follows the radiused ceiling corners.
    slab = box(Bd["wall_t"], iw + 400.0, ceil_z - floor + 200.0, Bd["wall_x0"], -iw / 2.0 - 200.0, floor)
    wall = try_common(slab, cavity, "bedroom_wall") or box(Bd["wall_t"], iw, ceil_z - floor - 60.0,
                                                           Bd["wall_x0"], -iw / 2.0, floor)
    yc, dw, dh = Bd["door_y_center"], Bd["door_w"], Bd["door_h"]
    wall = try_cut(wall, box(Bd["wall_t"] + 20.0, dw, dh + 10.0, Bd["wall_x0"] - 10.0, yc - dw / 2.0, floor - 10.0),
                   "bedroom_door_opening")
    add_shape("BED_WALL", as_single_solid(wall, "bedroom_wall"), grp, (0.86, 0.83, 0.76))
    # Bi-parting leaves on the living side of the wall, meeting on the centreline.
    lw, lt = Bd["door_leaf_w"], Bd["door_t"]
    lh = min(dh + 25.0, ceil_z - floor - 20.0)
    leaves = {}
    for tag in ("L", "R"):
        s = Bd["door_sides"][tag]
        y0, y1 = span(s, Bd["door_centre_gap"] / 2.0, Bd["door_centre_gap"] / 2.0 + lw)
        leaf = box(lt, y1 - y0, lh, Bd["wall_x0"] - 5.0 - lt, y0, floor + 5.0)
        leaves[tag] = add_shape(f"BED_DOOR_{tag}", leaf, grp, colors.get("dash_color", (0.3, 0.3, 0.3)))
    make_bedroom_doors_operable(V, leaves["L"], leaves["R"], Bd["door_sides"], Bd["door_travel"])
    # Bed platform: solid base forward of the boot; over the boot only a deck up to platform height.
    pw, ptop = Bd["platform_width"], Bd["platform_top_z"]
    bx0, bx1 = Bd["bed_x0"], Bd["bed_x1"]
    if Bd["over_boot"]:
        front_x1 = min(bx1, Bd["boot_front"])
        base = box(front_x1 - bx0, pw, ptop - floor, bx0, -pw / 2.0, floor) if front_x1 > bx0 + 1.0 else None
        deck_z0 = Bd["boot_top_z"]
        if ptop - deck_z0 > 1.0 and bx1 > Bd["boot_front"]:
            deck = box(bx1 - max(bx0, Bd["boot_front"]), pw, ptop - deck_z0, max(bx0, Bd["boot_front"]),
                       -pw / 2.0, deck_z0)
            base = deck if base is None else as_single_solid(try_fuse(base, deck, "bed_platform"), "bed_platform")
    else:
        base = box(bx1 - bx0, pw, ptop - floor, bx0, -pw / 2.0, floor)
    if base is not None:
        plat = add_shape("BED_PLATFORM", base, grp, colors.get("seat_color", (0.3, 0.3, 0.4)))
        add_prop(plat, "App::PropertyString", "Mattress", "Coaster",
                 f"{Bd['mattress_across_y']:.0f} across x {Bd['mattress_along_x']:.0f} along ({Bd['orientation']}); "
                 f"overrun vs interior width {Bd['mattress_overrun_mm']:+.0f} mm", "Mattress fit")
        add_prop(plat, "App::PropertyFloat", "PlatformTopZ_mm", "Coaster", float(ptop),
                 "Platform top above ground, mm (nominal, verify)")
    # Bedroom floor: the walkway between the wall and the bed, minus arch keep-outs.
    outline, area, blen, bw, cut = usable_floor_parts(V, Bd["wall_x"], bx0)
    if blen > 1.0:
        try:
            shp = face_with_cutouts(outline, cut, floor + 1.0).extrude(vec(0, 0, 6.0))
        except Exception:
            shp = box(blen, bw, 6.0, Bd["wall_x"], -bw / 2.0, floor + 1.0)
        fobj = add_shape("FLR_BEDROOM", shp, grp, colors["usable_floor_color"])
        add_prop(fobj, "App::PropertyFloat", "FloorArea_m2", "Coaster", float(area / 1e6),
                 "Clear bedroom floor (walkway) area, square metres")
    return Bd, area, blen, cut


# --------------------------------------------------------------------------
# Operable doors
#
# Same idea as the house bi-folds (control properties in the property editor,
# saved in the file, applied on change), but self-contained: the house uses a
# document observer from the HouseAutoReset add-on, which this file must not
# need. Here each moving part's Placement is an EXPRESSION of its own control
# properties, so editing a property + recompute moves it, also after reopening
# the FCStd, with no add-on, proxy or macro running. The controls sit on the
# door objects themselves, not on the Doors group: a child's expression that
# reads its own group would be a dependency cycle (the group links its children).
# Door glass Placement = door Placement, so the glass moves with the leaf.
# --------------------------------------------------------------------------

def add_control(obj, name, value, lo, hi, step, doc):
    """Float control clamped in the property editor (the expressions clamp again)."""
    try:
        if not hasattr(obj, name):
            obj.addProperty("App::PropertyFloatConstraint", name, "Door", doc)
        setattr(obj, name, (float(min(max(value, lo), hi)), float(lo), float(hi), float(step)))
    except Exception as exc:
        print(f"  control {obj.Name}.{name} failed: {exc}")
        FAILED_OPS.append(f"control_{obj.Name}.{name}")


def set_expr(obj, prop, expr):
    try:
        obj.setExpression(prop, expr)
    except Exception as exc:
        print(f"  expression {obj.Name}.{prop} failed: {exc}\n    {expr}")
        FAILED_OPS.append(f"expr_{obj.Name}.{prop}")


def follow_placement(child, leader):
    if child is not None:
        set_expr(child, "Placement", f"{leader.Name}.Placement")


def dc(V, key, default):
    try:
        return float(V[key])
    except (KeyError, TypeError, ValueError):
        return float(default)


def make_entry_door_operable(V, door, glass_obj, s):
    """Swing-out sliding plug door: out by SwingOut over 0..SwingPhase, then slides aft (+X)
    by SlideTravel over SwingPhase..1 along the outside of the body."""
    n = door.Name
    add_control(door, "OpenFraction", dc(V, "entry_door_open_fraction", 0.0), 0.0, 1.0, 0.05,
                "Entry door: 0 = closed, 1 = fully open (swing out, then slide toward the rear).")
    add_control(door, "SwingPhase", dc(V, "entry_door_swing_phase", 0.3), 0.05, 0.95, 0.05,
                "Share of OpenFraction used for the outward swing; the rest is the slide. Default 0.3.")
    add_control(door, "SwingOut", dc(V, "entry_door_swing_out", 80.0), 0.0, 300.0, 5.0,
                "Outward offset clear of the body, mm. Nominal 80 - VERIFY on the bus.")
    add_control(door, "SlideTravel", dc(V, "entry_door_slide_travel", 850.0), 0.0, 2000.0, 10.0,
                "Slide toward the rear (+X) when fully open, mm. Nominal 850 - VERIFY on the bus.")
    f = f"max(0; min(1; {n}.OpenFraction))"
    ph = f"max(0.05; min(0.95; {n}.SwingPhase))"
    out = f"min(1; {f} / {ph})"
    slide = f"max(0; ({f} - {ph}) / (1 - {ph}))"
    expr = (f"placement(vector({slide} * {n}.SlideTravel; {s:.0f} * {out} * {n}.SwingOut; 0); "
            f"vector(0; 0; 1); 0)")
    set_expr(door, "Placement", expr)
    follow_placement(glass_obj, door)


def make_driver_door_operable(V, door, glass_obj, s, hinge_x, hinge_y):
    """Hinged on its front (low-X) vertical edge, swinging outward (toward sign s)."""
    n = door.Name
    hi = dc(V, "driver_door_max_angle", 70.0)
    add_control(door, "OpenAngle", dc(V, "driver_door_open_angle", 0.0), 0.0, hi, 5.0,
                f"Driver door open angle, degrees (0 = closed, max {hi:.0f}). Hinged on the front edge, opens outward.")
    a = f"max(0; min({hi:g}; {n}.OpenAngle))"
    expr = (f"placement(vector(0; 0; 0); rotation(vector(0; 0; 1); {s:.0f} * {a}); "
            f"vector({hinge_x:.3f}; {hinge_y:.3f}; 0))")
    set_expr(door, "Placement", expr)
    follow_placement(glass_obj, door)


def make_boot_lid_operable(V, lid, hinge_x, hinge_z):
    """Top-hinged: the lower edge swings out (+X) and up about a transverse (Y) axis."""
    n = lid.Name
    hi = dc(V, "boot_lid_max_angle", 85.0)
    add_control(lid, "OpenAngle", dc(V, "boot_lid_open_angle", 0.0), 0.0, hi, 5.0,
                f"Boot lid open angle, degrees (0 = closed, max {hi:.0f}). Top-hinged, opens up and out.")
    a = f"max(0; min({hi:g}; {n}.OpenAngle))"
    # Rotation about -Y by +a moves the hanging lower edge toward +X (outward at the rear).
    expr = (f"placement(vector(0; 0; 0); rotation(vector(0; -1; 0); {a}); "
            f"vector({hinge_x:.3f}; 0; {hinge_z:.3f}))")
    set_expr(lid, "Placement", expr)


def make_flap_operable(V, flap, lock, s, hinge_y, hinge_z, top):
    """Storage flap on a longitudinal hinge at its outer top (or bottom) edge, opening outward."""
    n = flap.Name
    hi = dc(V, "storage_flap_max_angle", 90.0)
    where = "top-hinged, opens up and out" if top else "bottom-hinged, drops down and out"
    add_control(flap, "OpenAngle", dc(V, "storage_flap_open_angle", 0.0), 0.0, hi, 5.0,
                f"Storage flap open angle, degrees (0 = closed, max {hi:.0f}); {where}.")
    a = f"max(0; min({hi:g}; {n}.OpenAngle))"
    # About +X by +a a point below the hinge moves toward +Y; above the hinge, toward -Y.
    ax = s if top else -s
    expr = (f"placement(vector(0; 0; 0); rotation(vector({ax:.0f}; 0; 0); {a}); "
            f"vector(0; {hinge_y:.3f}; {hinge_z:.3f}))")
    set_expr(flap, "Placement", expr)
    follow_placement(lock, flap)


def make_bedroom_doors_operable(V, left, right, signs, travel):
    """Bi-parting pair. The controls live on the LEFT leaf (Bedroom Door Left); both leaves'
    Placements read them, mirrored, each sliding toward its own side wall. The right leaf only
    reads the left leaf, so there is no cycle."""
    n = left.Name
    add_control(left, "OpenFraction", dc(V, "bedroom_door_open_fraction", 0.0), 0.0, 1.0, 0.05,
                "Bedroom doors (both leaves): 0 = closed, 1 = fully open (each slides to its own side).")
    add_control(left, "SlideTravel", travel, 0.0, 1000.0, 10.0,
                "Slide distance of each leaf when fully open, mm (default half the opening width).")
    f = f"max(0; min(1; {n}.OpenFraction))"
    for leaf, tag in ((left, "L"), (right, "R")):
        set_expr(leaf, "Placement",
                 f"placement(vector(0; {signs[tag]:.0f} * {f} * {n}.SlideTravel; 0); vector(0; 0; 1); 0)")


# --------------------------------------------------------------------------
# Glazed / solid windows
#
# Each window is a glass pane (GLZ_*) plus a filler (FIL_*): skin thickness, body colour,
# flush in the opening. The pane carries a boolean 'Glazed'. Both objects' Visibility is an
# EXPRESSION of that flag. Visibility is an App property flagged Output/Hidden/NoModify; the
# expression engine still binds it, and Document::recompute evaluates Output-property
# expressions after the feature executes (PropertyExpressionEngine::ExecuteOutput, FreeCAD
# 1.0/1.1 App/Document.cpp), so the swap survives save/reopen and needs no add-on. Shapes and
# Placements never change, so nothing moves out of the bounding box and door glass/fillers keep
# following their doors. Exports/renders use the build-time state from params "windows".
# --------------------------------------------------------------------------

def window_controls(doc, V, groups, computed):
    states = V.get("_windows", {})
    rows = []
    for gobj, fobj in WINDOWS:
        label = display_label(gobj.Name)
        glazed = bool(states.get(label, True))
        add_prop(gobj, "App::PropertyBool", "Glazed", "Window", glazed,
                 "True = glass, False = solid skin (filler shown). Recompute after changing.")
        n = gobj.Name
        for obj, expr, on in ((gobj, f"{n}.Glazed ? 1 : 0", glazed), (fobj, f"{n}.Glazed ? 0 : 1", not glazed)):
            try:
                obj.Visibility = on
            except Exception:
                pass
            set_expr(obj, "Visibility", expr)
            if not on:
                INACTIVE.add(obj.Name)
        rows.append({"label": label, "glass": n, "filler": fobj.Name, "glazed": glazed})
    names = [g.Name for g, _ in WINDOWS]
    glazed_n = sum(1 for r in rows if r["glazed"])
    computed["windows"] = {"per_window": rows, "glazed_count": glazed_n,
                           "solid_count": len(rows) - glazed_n, "total": len(rows)}
    unknown = sorted(set(states) - {r["label"] for r in rows})
    if unknown:
        computed["windows"]["unknown_param_labels"] = unknown
        print(f"  WARNING params windows labels with no window: {unknown}")
    # Separate counter object (not the Glazing group, which links the panes).
    try:
        cnt = doc.addObject("App::FeaturePython", "WIN_COUNT")
    except Exception:
        cnt = doc.addObject("App::DocumentObjectGroup", "WIN_COUNT")
    add_prop(cnt, "App::PropertyInteger", "WindowTotal", "Windows", len(rows), "Number of windows")
    add_prop(cnt, "App::PropertyInteger", "GlazedCount", "Windows", glazed_n, "Windows with Glazed = True")
    add_prop(cnt, "App::PropertyInteger", "SolidCount", "Windows", len(rows) - glazed_n,
             "Windows with Glazed = False (solid skin)")
    if names:
        set_expr(cnt, "GlazedCount", " + ".join(f"({n}.Glazed ? 1 : 0)" for n in names))
        set_expr(cnt, "SolidCount", "WIN_COUNT.WindowTotal - WIN_COUNT.GlazedCount")
    try:
        groups["GRP_GLAZING"].addObject(cnt)
    except Exception as exc:
        print(f"  Window Count not grouped: {exc}")
    print(f"  windows: {glazed_n} glazed, {len(rows) - glazed_n} solid, {len(rows)} total")


def add_wheels(V, colors, groups):
    od = Vv(V, "tyre_od")
    rim_d = Vv(V, "rim_diameter")
    tw = Vv(V, "tyre_width")
    cz = od / 2.0
    front_axle = Vv(V, "front_overhang")
    rear_axle = front_axle + Vv(V, "wheelbase")
    ft = Vv(V, "front_track")
    rt = Vv(V, "rear_track")
    gap = Vv(V, "dual_tyre_gap")
    s_left, s_right = sides(V)

    def one_wheel(tag, cx, cy):
        tyre = make_tyre(cx, cy, cz, od, rim_d, tw)
        rim = make_rim(cx, cy, cz, rim_d, tw)
        add_shape(f"WHL_TYRE_{tag}", tyre, groups["GRP_WHEELS"], colors["tyre_color"])
        add_shape(f"WHL_RIM_{tag}", rim, groups["GRP_WHEELS"], colors["rim_color"])

    pair_off = (tw + gap) / 2.0
    for tag, s in (("L", s_left), ("R", s_right)):
        one_wheel(f"F{tag}", front_axle, s * ft / 2.0)
        one_wheel(f"R{tag}_OUT", rear_axle, s * (rt / 2.0 + pair_off))
        one_wheel(f"R{tag}_IN", rear_axle, s * (rt / 2.0 - pair_off))


def add_bumpers_and_trim(V, colors, groups):
    D = body_dims(V)
    s_left, s_right = sides(V)
    L, W, hw = D["L"], D["W"], D["hw"]
    bz = Vv(V, "bumper_z")
    bh = Vv(V, "bumper_height")
    grp = groups["GRP_EXTERIOR"]

    # Full-width front bumper from x=0, sunk 50 mm into the front face.
    bw = W - 10.0
    front = round_vertical_edges(box(D["x_front"] + 50.0, bw, bh, 0.0, -bw / 2.0, bz), 40.0)
    add_shape("TRM_BUMPER_FRONT", front, grp, colors["bumper_color"])

    # Rear bumper on the bumper line, ending at overall length (sunk 95 mm into the rear face).
    rear = round_vertical_edges(box(110.0, bw, bh, L - 110.0, -bw / 2.0, bz), 40.0)
    add_shape("TRM_BUMPER_REAR", rear, grp, colors["bumper_color"])

    # Separate flat grille panel on the front face, low down above the bumper.
    ws_z0 = Vv(V, "windscreen_sill_z")
    gz0 = bz + bh + 30.0
    gz1 = min(gz0 + 300.0, ws_z0 - 80.0)
    gw = hw * 0.5
    add_shape("TRM_GRILLE", front_prism(D, -gw, gw, gz0, gz1, 12.0, 32.0), grp, colors["grille_color"])
    bars = []
    n_bars = 4
    for i in range(n_bars):
        zc = gz0 + (gz1 - gz0) * (i + 1) / (n_bars + 1)
        bars.append(front_prism(D, -gw + 25.0, gw - 25.0, zc - 9.0, zc + 9.0, 18.0, 8.0))
    add_shape("TRM_GRILLE_BARS", Part.makeCompound(bars), grp, colors["rim_color"])

    # Headlamps either side of the grille, low on the face.
    hz0 = gz0 + 20.0
    hz1 = hz0 + 170.0
    for tag, s in (("L", s_left), ("R", s_right)):
        y0, y1 = span(s, gw + 60.0, hw - D["r"] - 15.0)
        add_shape(f"LIT_HEAD_{tag}", front_prism(D, y0, y1, hz0, hz1, 14.0, 34.0), grp,
                  colors["light_front_color"])

    # Vertical tail-lamp clusters at the rear corners, proud of the rear face.
    for tag, s in (("L", s_left), ("R", s_right)):
        y0, y1 = span(s, hw - D["r"] - 155.0, hw - D["r"] - 15.0)
        add_shape(f"LIT_TAIL_{tag}", box(32.0, y1 - y0, 450.0, D["x_rear"] - 20.0, y0, 900.0), grp,
                  colors["light_rear_color"])

    # Side rubbing strips, broken at the door openings on each side.
    strip_z, strip_h, strip_t = 1080.0, 50.0, 12.0
    x_start = Vv(V, "front_overhang") + Vv(V, "tyre_od") / 2.0 + 190.0
    x_end = D["x_rear"] - D["r"] - 20.0
    gaps = {
        "L": [(Vv(V, "entry_door_x"), Vv(V, "entry_door_x") + Vv(V, "entry_door_width"))],
        "R": [(Vv(V, "driver_door_x"), Vv(V, "driver_door_x") + Vv(V, "driver_door_width"))],
    }
    for tag, s in (("L", s_left), ("R", s_right)):
        segs = [(x_start, x_end)]
        for a, b in gaps[tag]:
            nxt = []
            for s0, s1 in segs:
                if b <= s0 or a >= s1:
                    nxt.append((s0, s1))
                    continue
                if a - 20.0 - s0 > 50.0:
                    nxt.append((s0, a - 20.0))
                if s1 - (b + 20.0) > 50.0:
                    nxt.append((b + 20.0, s1))
            segs = nxt
        y0 = (hw - 4.0) if s > 0 else (-hw + 4.0 - strip_t)
        parts = [box(x1 - x0, strip_t, strip_h, x0, y0, strip_z) for x0, x1 in segs if x1 > x0]
        if parts:
            add_shape(f"TRM_STRIP_{tag}", Part.makeCompound(parts), grp, colors["rub_strip_color"])


def add_arch_housings(V, colors, groups):
    iw = Vv(V, "interior_width")
    floor = Vv(V, "floor_height")
    front_axle = Vv(V, "front_overhang")
    rear_axle = front_axle + Vv(V, "wheelbase")
    s_left, s_right = sides(V)

    def housing(name, axle, length, width, height, s):
        x = arch_housing_x0(axle, length)
        y = (iw / 2.0 - width) if s > 0 else -iw / 2.0
        return add_shape(name, box(length, width, height, x, y, floor), groups["GRP_ARCHES"], colors["arch_color"])

    for tag, s in (("L", s_left), ("R", s_right)):
        housing(f"ARCH_REAR_{tag}", rear_axle, Vv(V, "rear_arch_length"), Vv(V, "rear_arch_width"),
                Vv(V, "rear_arch_height"), s)
        housing(f"ARCH_FRONT_{tag}", front_axle, Vv(V, "front_arch_length"), Vv(V, "front_arch_width"),
                Vv(V, "front_arch_height"), s)


def add_cab(V, colors, groups):
    iw = Vv(V, "interior_width")
    floor = Vv(V, "floor_height")
    cab_end = Vv(V, "cab_zone_length")
    # Driver on the RIGHT / offside (y_sign_right, +Y with the front at x=0) for Australian RHD.
    # Left / kerb (y_sign_left, -Y) stays clear for the entry door, opposite the driver.
    y_right = Vv(V, "_y_right")
    seat_w, seat_d, seat_h = 500.0, 500.0, 130.0
    back_t, back_h = 90.0, 620.0
    seat_x = cab_end - seat_d - 80.0
    if y_right < 0:
        seat_y = -iw / 2.0 + 40.0
    else:
        seat_y = iw / 2.0 - 40.0 - seat_w
    cushion = box(seat_d, seat_w, seat_h, seat_x, seat_y, floor)
    back = box(back_t, seat_w, back_h, seat_x + seat_d - back_t, seat_y, floor + seat_h)
    add_shape("CAB_DRIVER_SEAT", try_fuse(cushion, back), groups["GRP_CAB"], colors["seat_color"])

    dash_x0 = Vv(V, "cavity_start_x") + 20.0
    dash_x1 = min(seat_x - 40.0, dash_x0 + 520.0)
    dash_z0 = floor + 280.0
    dash_h = 420.0
    dash = box(dash_x1 - dash_x0, iw - 40.0, dash_h, dash_x0, -iw / 2.0 + 20.0, dash_z0)
    add_shape("CAB_DASH", dash, groups["GRP_CAB"], colors["dash_color"])
    # Instrument cluster on the right, in front of the driver, so the offside reads clearly.
    cluster = box(80.0, 300.0, 140.0, dash_x1 - 90.0, seat_y + 100.0, dash_z0 + dash_h - 50.0)
    add_shape("CAB_INSTRUMENTS", cluster, groups["GRP_CAB"], (0.12, 0.12, 0.14))

    # Steering wheel in front of the driver (right / offside).
    sw_cx = dash_x1 + 30.0
    sw_cy = seat_y + seat_w / 2.0
    sw_cz = floor + 720.0
    try:
        wheel = Part.makeTorus(165.0, 16.0, vec(sw_cx, sw_cy, sw_cz), vec(0.85, 0.0, 0.15))
        add_shape("CAB_STEERING", wheel, groups["GRP_CAB"], colors["rubber_color"])
    except Exception as exc:
        print(f"  steering wheel failed: {exc}")

    # A modest engine-hump / doghouse on the centreline in the cab, typical of a 2nd-gen Coaster.
    hump = box(cab_end - dash_x0 - 40.0, 420.0, 380.0, dash_x0 + 20.0, -210.0, floor)
    add_shape("CAB_ENGINE_HUMP", hump, groups["GRP_CAB"], colors["dash_color"])


def add_floor_and_refs(V, colors, groups, computed):
    L = Vv(V, "overall_length")
    iw = Vv(V, "interior_width")
    floor_z = Vv(V, "floor_height")
    thick = Vv(V, "floor_thickness")
    x0 = Vv(V, "cavity_start_x")
    x1 = L - Vv(V, "wall_thickness")

    outline, area, use_len, use_w, cutouts = usable_floor_parts(V)
    B = boot_layout(V)
    computed["boot_enclosure"] = {
        "x0": B["x_front"], "x1": B["x_inner"], "y0": -iw / 2.0, "y1": iw / 2.0,
        "z0": B["z0"], "z_top": B["z1"] + B["t"], "opening_z1": B["z1"],
        "opening_width": 2.0 * B["half_w"], "depth_into_cabin": B["x_inner"] - B["x_front"],
    }
    computed["usable_floor_x0_mm"] = outline[0][0]
    computed["usable_floor_x1_mm"] = outline[1][0]
    computed["usable_floor_area_mm2"] = area
    computed["usable_floor_area_m2"] = area / 1e6
    computed["usable_floor_length_mm"] = use_len
    computed["usable_floor_width_mm"] = use_w
    computed["usable_floor_outline"] = outline
    computed["usable_floor_cutouts"] = cutouts

    # Structural floor plate (full cabin, including cab), arches sit on top.
    plate = box(x1 - x0, iw, thick, x0, -iw / 2.0, floor_z - thick)
    st = entry_step_layout(V)
    wy0, wy1 = span(Vv(V, "_y_left"), st["well_in"], iw / 2.0 + 10.0)
    plate = try_cut(plate, box(st["x1"] - st["x0"], wy1 - wy0, thick + 20.0, st["x0"], wy0, floor_z - thick - 10.0),
                    "floor_step_well")
    flr = add_shape("FLR_CABIN", plate, groups["GRP_FLOOR"], colors["floor_color"])

    # Green usable empty passenger floor (thin plate with keep-outs cut).
    usable_face = face_with_cutouts(outline, cutouts, floor_z + 1.0)
    try:
        usable = usable_face.extrude(vec(0, 0, 6.0))
    except Exception:
        usable = box(use_len, use_w, 6.0, outline[0][0], -use_w / 2.0, floor_z + 1.0)
    empty = add_shape("FLR_EMPTY_USABLE", usable, groups["GRP_CABIN"], colors["usable_floor_color"])

    add_prop(empty, "App::PropertyFloat", "UsableArea_m2", "Coaster",
             float(area / 1e6), "Living floor area (cab zone to the bedroom wall), square metres")
    add_prop(empty, "App::PropertyFloat", "UsableLength_mm", "Coaster",
             float(use_len), "Living floor length from the cab zone to the bedroom wall, millimetres")
    add_prop(empty, "App::PropertyFloat", "UsableWidth_mm", "Coaster",
             float(use_w), "Interior width used for the usable floor, millimetres")
    add_prop(empty, "App::PropertyString", "CabinCondition", "Coaster",
             "Passenger seats removed. Driver seat and dash retained. Living floor runs from the cab zone to the bedroom wall (or the Boot if there is no bedroom). Area excludes arch keep-outs and the entry step well.",
             "Layout note")
    add_prop(flr, "App::PropertyFloat", "UsableArea_m2", "Coaster", float(area / 1e6),
             "Living floor area, square metres")

    # Floor outline (wire) and centreline.
    outline_wire = Part.makePolygon([vec(x, y, floor_z + 8.0) for x, y in outline + [outline[0]]])
    add_shape("REF_FLOOR_OUTLINE", outline_wire, groups["GRP_REF"], (0.1, 0.4, 0.15))

    cl = Part.makePolygon([vec(0.0, 0.0, floor_z + 8.0), vec(L, 0.0, floor_z + 8.0)])
    add_shape("REF_CENTRELINE", cl, groups["GRP_REF"], (0.8, 0.15, 0.15))

    # Cab zone marker (a thin tinted plate, not part of usable area).
    cab = box(Vv(V, "cab_zone_length") - x0, iw, 4.0, x0, -iw / 2.0, floor_z + 1.0)
    cab_obj = add_shape("REF_CAB_ZONE", cab, groups["GRP_REF"], (0.75, 0.62, 0.35))
    _ = cab_obj

    # Open volume edges at headroom height — a wireframe box, not a solid, so STEP stays hollow.
    z1 = Vv(V, "floor_height") + Vv(V, "interior_headroom")
    ux0, uy0 = outline[0]
    ux1, uy1 = outline[2][0], outline[2][1]
    corners = [
        vec(ux0, uy0, floor_z), vec(ux1, uy0, floor_z), vec(ux1, uy1, floor_z), vec(ux0, uy1, floor_z),
        vec(ux0, uy0, z1), vec(ux1, uy0, z1), vec(ux1, uy1, z1), vec(ux0, uy1, z1),
    ]
    edges = []
    for a, b in ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)):
        edges.append(Part.makeLine(corners[a], corners[b]))
    vol = Part.Compound(edges)
    vol_obj = add_shape("REF_EMPTY_CABIN_VOLUME", vol, groups["GRP_CABIN"], (0.2, 0.55, 0.3))
    _ = vol_obj

    return empty, area, use_len, use_w


GROUP_LABELS = {
    "GRP_EXTERIOR": "Exterior",
    "GRP_FLOOR": "Floor",
    "GRP_GLAZING": "Glazing",
    "GRP_DOORS": "Doors",
    "GRP_WHEELS": "Wheels",
    "GRP_ARCHES": "Wheel Arches",
    "GRP_CAB": "Cab",
    "GRP_CABIN": "Cabin",
    "GRP_REF": "Reference",
    "GRP_ROOF": "Roof",
    "GRP_STORAGE": "Storage",
    "GRP_BEDROOM": "Bedroom",
}

FIXED_LABELS = {
    "BODY_SHELL": "Body",
    "BODY_ROOF": "Roof Panel",          # qualified: the group is labelled "Roof"
    "BOOT_ENCLOSURE": "Boot",
    "REF_EXTERIOR_ENVELOPE": "Exterior Envelope",
    "GLZ_WINDSCREEN_L": "Windscreen Left",
    "GLZ_WINDSCREEN_R": "Windscreen Right",
    "GLZ_REAR": "Rear Window",
    "GLZ_PASSENGER": "Passenger Side Window",
    "WIN_COUNT": "Window Count",
    "DR_ENTRY": "Entry Door",
    "GLZ_ENTRY": "Entry Door Glass",
    "DR_DRIVER": "Driver Door",
    "GLZ_DRIVER": "Driver Door Glass",
    "DR_BOOT_LID": "Boot Lid",
    "TRM_BUMPER_FRONT": "Front Bumper",
    "TRM_BUMPER_REAR": "Rear Bumper",
    "TRM_GRILLE": "Grille",
    "TRM_GRILLE_BARS": "Grille Bars",
    "LIT_HEAD_L": "Left Headlamp",
    "LIT_HEAD_R": "Right Headlamp",
    "LIT_TAIL_L": "Left Tail Lamp",
    "LIT_TAIL_R": "Right Tail Lamp",
    "TRM_STRIP_L": "Left Rub Strip",
    "TRM_STRIP_R": "Right Rub Strip",
    "CAB_DRIVER_SEAT": "Driver Seat",
    "CAB_DASH": "Dash",
    "CAB_INSTRUMENTS": "Instrument Cluster",
    "CAB_STEERING": "Steering Wheel",
    "CAB_ENGINE_HUMP": "Engine Hump",
    "FLR_CABIN": "Cabin Floor",
    "FLR_EMPTY_USABLE": "Living Floor",
    "FLR_BEDROOM": "Bedroom Floor",
    "STEP_ENTRY": "Entry Step",
    "BED_WALL": "Bedroom Wall",
    "BED_DOOR_L": "Bedroom Door Left",
    "BED_DOOR_R": "Bedroom Door Right",
    "BED_PLATFORM": "Bed Platform",
    "REF_FLOOR_OUTLINE": "Floor Outline",
    "REF_CENTRELINE": "Centreline",
    "REF_CAB_ZONE": "Cab Zone",
    "REF_EMPTY_CABIN_VOLUME": "Empty Cabin Volume",
}

_SIDE = {"L": "Left", "R": "Right"}
_WHEEL_POS = {"FL": "Front Left", "FR": "Front Right",
              "RL_OUT": "Rear Left Outer", "RL_IN": "Rear Left Inner",
              "RR_OUT": "Rear Right Outer", "RR_IN": "Rear Right Inner"}


def display_label(name):
    """Plain proper-noun Label for an internal Name (Names stay safe identifiers)."""
    if name in GROUP_LABELS:
        return GROUP_LABELS[name]
    if name in FIXED_LABELS:
        return FIXED_LABELS[name]
    if name.startswith("GLZ_SIDE_"):          # GLZ_SIDE_L_3 -> Left Side Window 3
        _, _, side, idx = name.split("_", 3)
        return f"{_SIDE.get(side, side)} Side Window {idx}"
    if name.startswith("WHL_TYRE_"):
        return f"{_WHEEL_POS.get(name[9:], name[9:])} Tyre"
    if name.startswith("WHL_RIM_"):
        return f"{_WHEEL_POS.get(name[8:], name[8:])} Wheel"
    if name.startswith("FIL_"):               # FIL_SIDE_L_1 -> Left Side Window 1 Filler
        return display_label("GLZ_" + name[4:]) + " Filler"
    if name.startswith("STO_BIN_T"):          # STO_BIN_T1 -> Through Storage Bin 1
        return f"Through Storage Bin {name[9:]}"
    for pre, word in (("STO_BIN_", "Storage Bin"), ("STO_FLAP_", "Storage Flap"), ("STO_LOCK_", "Lock Marker")):
        if name.startswith(pre):              # STO_FLAP_L1 -> Left Storage Flap 1
            rest = name[len(pre):]
            return f"{_SIDE.get(rest[:1], rest[:1])} {word} {rest[1:]}"
    if name.startswith("ARCH_"):              # ARCH_REAR_L -> Rear Left Arch Housing
        _, axle, side = name.split("_", 2)
        return f"{axle.title()} {_SIDE.get(side, side)} Arch Housing"
    return name


def apply_labels(doc):
    seen = {}
    for obj in doc.Objects:
        label = display_label(obj.Name)
        if label in seen:                     # qualify only on a real clash
            label = f"{label} ({obj.Name})"
        seen[label] = obj.Name
        try:
            obj.Label = label
        except Exception as exc:
            print(f"  label {obj.Name} failed: {exc}")


def roof_split_z(V):
    """Planar roof line: between the window/door/windscreen heads and the roof-edge fillet start."""
    H = Vv(V, "overall_height")
    r = Vv(V, "body_edge_radius")
    return 0.5 * (Vv(V, "window_head_z") + (H - r))


def split_roof(shell, V):
    """One half-space box; common = Roof, cut = Body walls, so they meet exactly on the plane."""
    L = Vv(V, "overall_length")
    W = Vv(V, "overall_width")
    z = roof_split_z(V)
    upper = box(L + 2000.0, W + 2000.0, 2000.0, -1000.0, -W / 2.0 - 1000.0, z)
    try:
        roof = shell.common(upper)
        walls = shell.cut(upper)
        if roof.isNull() or walls.isNull() or roof.Volume <= 1.0 or walls.Volume <= 1.0:
            raise RuntimeError("empty half")
    except Exception as exc:
        print(f"  WARNING roof split failed ({exc}); keeping one Body solid")
        FAILED_OPS.append("roof_split")
        return shell, None
    return as_single_solid(walls, "Body"), as_single_solid(roof, "Roof")


def check_solid(label, shp):
    """Validity report for the body shell (printed and stored in usable_floor.json)."""
    info = {
        "shape_type": shp.ShapeType,
        "valid": bool(shp.isValid()),
        "solids": len(shp.Solids),
        "shells": len(shp.Shells),
        "closed": bool(shp.Shells) and all(s.isClosed() for s in shp.Shells),
        "volume_m3": round(shp.Volume / 1e9, 4),
    }
    try:
        shp.check(True)
        info["check"] = "ok"
    except Exception as exc:
        info["check"] = str(exc)[:300]
    bb = shp.BoundBox
    info["bbox_mm"] = [round(bb.XMin, 1), round(bb.XMax, 1), round(bb.YMin, 1),
                       round(bb.YMax, 1), round(bb.ZMin, 1), round(bb.ZMax, 1)]
    print(f"  {label}: {info}")
    return info


def cutaway_z(V):
    H = Vv(V, "overall_height")
    return min(H - Vv(V, "roof_thickness") - 8.0, Vv(V, "window_head_z") - 250.0)


def add_cutaway_mesh(item, obj, V, deviation, max_edge):
    """Store a true planar cut (below cutaway_z) of obj for the roof-off render."""
    z = cutaway_z(V)
    shp = obj.Shape
    bb = shp.BoundBox
    if bb.ZMin >= z - 0.5:
        item["cutaway_hide"] = True
        return
    if bb.ZMax <= z + 0.5:
        return
    L = Vv(V, "overall_length")
    W = Vv(V, "overall_width")
    clip = box(L + 2000.0, W + 2000.0, z + 1000.0, -1000.0, -W / 2.0 - 1000.0, -1000.0)
    try:
        part = shp.common(clip)
        verts, faces = tessellate_shape(part, deviation, max_edge)
    except Exception as exc:
        print(f"  cutaway {obj.Name} failed: {exc}")
        return
    if not verts or not faces:
        item["cutaway_hide"] = True
        return
    item["cutaway_vertices"] = verts
    item["cutaway_faces"] = faces


def export_all(doc, P, meshes, computed):
    exports = ROOT / "exports"
    exports.mkdir(exist_ok=True)
    meshes_dir = exports / "meshes"
    meshes_dir.mkdir(exist_ok=True)

    fcstd = exports / P["export"]["fcstd_name"]
    doc.saveAs(str(fcstd))
    print(f"saved {fcstd}")

    step_objs = []
    skip_prefixes = ("REF_", "GRP_")
    for obj in doc.Objects:
        if not hasattr(obj, "Shape"):
            continue
        if obj.Name.startswith(skip_prefixes) or obj.Name in INACTIVE:
            continue
        if obj.Shape is None or obj.Shape.isNull():
            continue
        # Do not put the empty-volume wire or the annotation floor? The usable floor plate is useful in STEP.
        if obj.Name == "REF_EMPTY_CABIN_VOLUME":
            continue
        step_objs.append(obj)
    step_path = exports / P["export"]["step_name"]
    try:
        Part.export(step_objs, str(step_path))
        print(f"saved {step_path} ({len(step_objs)} objects)")
    except Exception as exc:
        print(f"STEP export failed: {exc}")
        # Fallback: compound
        try:
            shapes = [o.Shape for o in step_objs if not o.Shape.isNull()]
            Part.Compound(shapes).exportStep(str(step_path))
            print(f"saved compound STEP {step_path}")
        except Exception as exc2:
            print(f"STEP fallback failed: {exc2}")

    # Default exportStl meshing is far too fine (100MB+ per lofted solid).
    # A coarse combined STL is written later from the already-tessellated render cache.
    for old in meshes_dir.glob("*.stl"):
        try:
            old.unlink()
        except Exception:
            pass

    cache = {
        "meshes": meshes,
        "computed": computed,
        "meta": P.get("meta", {}),
        "style": P.get("style", {}),
        "values": {k: v["value"] for k, v in P["dimensions_mm"].items()},
    }
    cache_path = exports / "render_cache.pkl"
    with cache_path.open("wb") as f:
        pickle.dump(cache, f, protocol=4)
    print(f"saved {cache_path}")

    summary_path = exports / "usable_floor.json"
    summary_path.write_text(json.dumps(computed, indent=2), encoding="utf-8")
    print(f"saved {summary_path}")
    return fcstd, step_path


def run():
    del FAILED_OPS[:]
    del WINDOWS[:]
    INACTIVE.clear()
    P, V = load_params()
    colors = P["style"]
    deviation = float(P["export"]["tessellate_deviation_mm"])
    max_edge = float(P["export"].get("render_max_edge_mm", 250))
    s_left, s_right = sides(V)
    print("Building 1988 Coaster LWB shell from params/coaster_params.json")
    print(f"  L={V['overall_length']} W={V['overall_width']} H={V['overall_height']} WB={V['wheelbase']}")
    print(f"  sides: left/kerb/entry y_sign={s_left:+.0f}, right/offside/driver y_sign={s_right:+.0f} "
          "(x=0 front, driver faces -X, so right = +Y)")
    if s_right <= 0 or s_left >= 0:
        print("  WARNING: params sides look swapped for a front-at-x=0 model (expect left=-1, right=+1)")

    doc = reset_document()
    groups = {
        "GRP_EXTERIOR": group("GRP_EXTERIOR"),
        "GRP_FLOOR": group("GRP_FLOOR"),
        "GRP_GLAZING": group("GRP_GLAZING"),
        "GRP_DOORS": group("GRP_DOORS"),
        "GRP_WHEELS": group("GRP_WHEELS"),
        "GRP_ARCHES": group("GRP_ARCHES"),
        "GRP_CAB": group("GRP_CAB"),
        "GRP_CABIN": group("GRP_CABIN"),
        "GRP_REF": group("GRP_REF"),
        "GRP_ROOF": group("GRP_ROOF"),
        "GRP_STORAGE": group("GRP_STORAGE"),
        "GRP_BEDROOM": group("GRP_BEDROOM"),
    }

    computed = {
        "coordinate_system": P["coordinate_system"],
        "design_case": "High-roof LWB, passenger seats removed, RHD Australia, internal rear boot (no rear door)",
        "sides": {"y_sign_left": s_left, "y_sign_right": s_right},
    }

    print("Building exterior body (filleted prism)...")
    exterior = build_exterior(V)
    print("Building interior cavity...")
    cavity = build_cavity(V)
    print("Hollowing shell...")
    shell = try_cut(exterior, cavity, "cavity")
    if shell.Volume >= exterior.Volume * 0.98:
        raise RuntimeError("cavity cut did not hollow the body")
    print(f"  shell volume {shell.Volume/1e9:.3f} m^3 (exterior was {exterior.Volume/1e9:.3f})")

    print("Cutting wheel-arch openings...")
    for name, cutter in arch_cutters(V):
        shell = try_cut(shell, cutter, f"arch_{name}")

    print("Cutting windscreen, doors, window band, rear window and boot...")
    shell = punch_openings(shell, V)
    shell = as_single_solid(shell, "BODY_SHELL")
    unsplit = check_solid("unsplit shell", shell)

    z_split = roof_split_z(V)
    print(f"Splitting Roof from Body at z={z_split:.1f}...")
    walls, roof = split_roof(shell, V)
    computed["roof_split_z_mm"] = z_split
    computed["shell_check"] = {"Body": check_solid("Body", walls), "unsplit": unsplit}
    add_shape("BODY_SHELL", walls, groups["GRP_EXTERIOR"], colors["body_color"])
    if roof is not None:
        computed["shell_check"]["Roof"] = check_solid("Roof", roof)
        add_shape("BODY_ROOF", roof, groups["GRP_ROOF"], colors["body_color"])
        vol_sum = walls.Volume + roof.Volume
        computed["shell_check"]["split_volume_error_mm3"] = round(vol_sum - shell.Volume, 1)
        print(f"  Body+Roof volume - unsplit volume = {vol_sum - shell.Volume:.1f} mm^3 (expect ~0)")
    env = Part.makePolygon([
        vec(0, -Vv(V, "overall_width") / 2, 0),
        vec(Vv(V, "overall_length"), -Vv(V, "overall_width") / 2, 0),
        vec(Vv(V, "overall_length"), Vv(V, "overall_width") / 2, 0),
        vec(0, Vv(V, "overall_width") / 2, 0),
        vec(0, -Vv(V, "overall_width") / 2, 0),
    ])
    add_shape("REF_EXTERIOR_ENVELOPE", env, groups["GRP_EXTERIOR"], (0.3, 0.3, 0.3))

    print("Adding glass, doors, boot lid, wheels, trim, cab and floor...")
    add_glass_and_doors(doc, V, colors, groups)
    add_wheels(V, colors, groups)
    add_bumpers_and_trim(V, colors, groups)
    add_arch_housings(V, colors, groups)
    add_boot_enclosure(V, colors, groups)
    add_cab(V, colors, groups)
    window_controls(doc, V, groups, computed)
    add_entry_step(V, colors, groups)
    S = add_storage(V, colors, groups)
    empty, area, use_len, use_w = add_floor_and_refs(V, colors, groups, computed)
    _ = empty
    st = entry_step_layout(V)
    computed["passenger_window"] = passenger_window_layout(V)
    computed["entry_step"] = {"group": "Cabin", "x0": st["x0"], "x1": st["x1"], "width": st["width"],
                              "tread_depth": st["tread_depth"], "z_top": st["z_top"], "thickness": st["t"],
                              "well_inner_abs_y": st["well_in"], "side": "left/kerb (y_sign_left)"}
    computed["storage"] = {
        "hinge": S["hinge"], "z0": S["z0"], "z1": S["z1"], "bin_height": S["z1"] - S["z0"],
        "depth_inboard": S["depth"], "runs": S["runs"], "run_lengths": S["run_lengths"],
        "segments": S["segments"], "limits": S["limits"],
        "not_modelled": "Chassis rails, fuel tank, spare wheel, exhaust, driveshaft and other underfloor "
                        "parts are NOT modelled. Measure the real underfloor before building bins.",
    }
    computed["living_floor_area_m2"] = area / 1e6
    computed["living_floor_x0_mm"] = Vv(V, "cab_zone_length")
    computed["living_floor_x1_mm"] = Vv(V, "cab_zone_length") + use_len
    if flag(V, "bedroom_enabled", True):
        Bd, b_area, b_len, b_cut = add_bedroom(V, colors, groups, cavity)
        computed["bedroom"] = dict(Bd)
        computed["bedroom_floor_area_m2"] = b_area / 1e6
        computed["bedroom_floor_length_mm"] = b_len
        computed["bedroom_floor_cutouts"] = b_cut
        computed["bedroom_footprint_m2"] = Bd["bedroom_length"] * Vv(V, "interior_width") / 1e6

    recompute()

    # Overall-dimension check (body, bumpers, lamps, fixed glass; doors may be open; rub strips stand 8 mm proud).
    bb = None
    for obj in doc.Objects:
        if not obj.Name.startswith(("BODY_", "TRM_BUMPER", "LIT_", "GLZ_", "TRM_GRILLE")):
            continue
        if obj.Name in ("GLZ_ENTRY", "GLZ_DRIVER") or obj.Name in INACTIVE:   # moving / hidden
            continue
        b = obj.Shape.BoundBox
        if bb is None:
            bb = App.BoundBox(b)
        else:
            bb.add(b)
    if bb is not None:
        dims = {"length": round(bb.XLength, 1), "width": round(bb.YLength, 1), "height": round(bb.ZMax, 1),
                "x_min": round(bb.XMin, 1)}
        exp = (Vv(V, "overall_length"), Vv(V, "overall_width"), Vv(V, "overall_height"))
        dims["expected"] = list(exp)
        dims["ok"] = (abs(dims["length"] - exp[0]) < 1.0 and abs(dims["width"] - exp[1]) < 1.0
                      and abs(dims["height"] - exp[2]) < 1.0 and abs(bb.XMin) < 1.0)
        computed["dims_check"] = dims
        print(f"  overall dims {dims}")

    # Colour map used by the renderer (headless FCStd may not store ViewObject colours).
    color_by_prefix = {
        "BODY_": colors["body_color"],
        "TRM_BUMPER": colors["bumper_color"],
        "TRM_GRILLE_BARS": colors["rim_color"],
        "TRM_GRILLE": colors["grille_color"],
        "TRM_STRIP": colors["rub_strip_color"],
        "LIT_HEAD": colors["light_front_color"],
        "LIT_TAIL": colors["light_rear_color"],
        "GLZ_": list(colors["glass_color"]) + [colors.get("glass_alpha", 0.45)],
        "FIL_": colors["body_color"],
        "DR_BOOT": colors.get("body_lower_color", colors["body_color"]),
        "DR_": colors["body_color"],
        "WHL_TYRE": colors["tyre_color"],
        "WHL_RIM": colors["rim_color"],
        "ARCH_": colors["arch_color"],
        "BOOT_": colors["arch_color"],
        "CAB_DRIVER": colors["seat_color"],
        "CAB_DASH": colors["dash_color"],
        "CAB_STEERING": colors["rubber_color"],
        "CAB_ENGINE": colors["dash_color"],
        "FLR_CABIN": colors["floor_color"],
        "FLR_EMPTY": colors["usable_floor_color"],
        "REF_CAB_ZONE": (0.75, 0.62, 0.35),
        "STEP_": colors["bumper_color"],
        "STO_BIN": colors["arch_color"],
        "STO_FLAP": colors.get("body_lower_color", colors["body_color"]),
        "STO_LOCK": colors["light_rear_color"],
        "BED_WALL": (0.86, 0.83, 0.76),
        "BED_DOOR": colors["dash_color"],
        "BED_PLATFORM": colors["seat_color"],
        "FLR_BEDROOM": colors["usable_floor_color"],
    }

    def color_for(name):
        for prefix, col in color_by_prefix.items():
            if name.startswith(prefix):
                return col
        return colors["body_color"]

    apply_labels(doc)
    recompute()
    door_state = {}
    for nm, props in (("DR_ENTRY", ("OpenFraction", "SwingPhase", "SwingOut", "SlideTravel")),
                      ("DR_DRIVER", ("OpenAngle",)), ("DR_BOOT_LID", ("OpenAngle",)),
                      ("BED_DOOR_L", ("OpenFraction", "SlideTravel"))) + tuple(
                          (o.Name, ("OpenAngle",)) for o in doc.Objects if o.Name.startswith("STO_FLAP_")):
        o = doc.getObject(nm)
        if o is not None:
            door_state[nm] = {p: float(getattr(o, p)) for p in props if hasattr(o, p)}
            door_state[nm]["placement"] = str(o.Placement)
    computed["door_state"] = door_state
    print(f"  door state (render/STEP use this): {door_state}")

    print("Tessellating for renders (welded, refined, plus planar cutaway meshes)...")
    computed["cutaway_z_mm"] = cutaway_z(V)
    mesh_checks = {}
    meshes = []
    for obj in doc.Objects:
        if not hasattr(obj, "Shape") or obj.Name.startswith("GRP_") or obj.Name in INACTIVE:
            continue
        if obj.Name in ("REF_CENTRELINE", "REF_FLOOR_OUTLINE", "REF_EXTERIOR_ENVELOPE", "REF_EMPTY_CABIN_VOLUME"):
            # Keep wires out of the shaded render; the 2D drawings show them.
            continue
        try:
            item = tessellate_obj(obj, deviation, max_edge)
        except Exception as exc:
            print(f"  tessellate {obj.Name} failed: {exc}")
            continue
        if not item:
            continue
        rep = mesh_edge_report(item["faces"])
        mesh_checks[obj.Name] = rep
        if not obj.Name.startswith("REF_"):
            add_cutaway_mesh(item, obj, V, deviation, max_edge)
        col = color_for(obj.Name)
        if isinstance(col, (list, tuple)) and len(col) == 4:
            item["color"] = list(col[:3])
            item["alpha"] = float(col[3])
        else:
            item["color"] = list(col)
            item["alpha"] = 1.0
        meshes.append(item)
    computed["mesh_checks"] = mesh_checks
    leaky = {k: v for k, v in mesh_checks.items()
             if (v["open_edges"] or v["nonmanifold_edges"]) and not k.startswith(("REF_", "FLR_EMPTY"))}
    if leaky:
        print(f"  WARNING meshes with open/non-manifold edges: {leaky}")
    else:
        print("  all solid meshes watertight (0 open, 0 non-manifold edges)")
    computed["failed_ops"] = list(FAILED_OPS)
    if FAILED_OPS:
        print(f"  WARNING boolean/fillet operations that fell back: {FAILED_OPS}")

    computed["mesh_parts"] = [m["name"] for m in meshes]
    export_all(doc, P, meshes, computed)
    recompute()
    # Save again so properties stick.
    doc.saveAs(str(ROOT / "exports" / P["export"]["fcstd_name"]))

    print("---- body shell ----")
    for key in ("Body", "Roof"):
        sc = computed["shell_check"].get(key)
        if sc:
            print(f"  {key}: valid={sc['valid']} closed={sc['closed']} solids={sc['solids']} "
                  f"check={sc['check']} volume={sc['volume_m3']} m^3")
    print("---- living floor (cab zone to bedroom wall) ----")
    print(f"  length {use_len:.0f} mm  width {use_w:.0f} mm  area {area/1e6:.2f} m^2")
    if "bedroom" in computed:
        b = computed["bedroom"]
        print(f"  bedroom: wall_x {b['wall_x']:.1f}, length {b['bedroom_length']:.0f}, clear floor "
              f"{computed['bedroom_floor_area_m2']:.2f} m^2, mattress overrun {b['mattress_overrun_mm']:+.0f} mm")
    print(f"  storage runs {computed['storage']['runs']} hinge={computed['storage']['hinge']}")
    print("build ok")
    return doc


if __name__ == "__main__" or __name__ == "__builtin__" or App.Application:
    # freecadcmd executes the file and also may set a module name other than __main__.
    try:
        run()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
