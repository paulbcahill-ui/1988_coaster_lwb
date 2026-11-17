"""Render dimensioned 2D plan/elevation and 3D isometric PNG views.

Reads params/coaster_params.json and exports/render_cache.pkl (written by
macros/10_coaster_shell.py). Run with FreeCAD's bundled Python so matplotlib
and numpy are available:

  "C:\\Program Files\\FreeCAD_1.1.1-Windows-x86_64-py311\\bin\\python.exe" macros\\20_render_views.py
"""

from __future__ import annotations

import json
import math
import pickle
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import PolyCollection, LineCollection  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle, Circle, FancyArrowPatch  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PNGS = ROOT / "pngs"
EXPORTS = ROOT / "exports"
DPI = 160


def load_all():
    params = json.loads((ROOT / "params" / "coaster_params.json").read_text(encoding="utf-8"))
    values = {k: v["value"] for k, v in params["dimensions_mm"].items()}
    cache_path = EXPORTS / "render_cache.pkl"
    cache = None
    if cache_path.exists():
        with cache_path.open("rb") as f:
            cache = pickle.load(f)
    computed_path = EXPORTS / "usable_floor.json"
    computed = {}
    if computed_path.exists():
        computed = json.loads(computed_path.read_text(encoding="utf-8"))
    if cache and cache.get("computed"):
        computed = {**computed, **cache["computed"]}
    return params, values, cache, computed


def mm(values, key):
    return float(values[key])


def dim_line(ax, p0, p1, text, offset, side="auto", color="#222", fontsize=8):
    """Simple dimension line between two 2D points. offset is a 2-vector in data units."""
    p0 = np.array(p0, dtype=float)
    p1 = np.array(p1, dtype=float)
    d = p1 - p0
    length = np.linalg.norm(d)
    if length < 1:
        return
    n = np.array(offset, dtype=float)
    a = p0 + n
    b = p1 + n
    ax.plot([p0[0], a[0]], [p0[1], a[1]], color=color, lw=0.6)
    ax.plot([p1[0], b[0]], [p1[1], b[1]], color=color, lw=0.6)
    ax.annotate(
        "",
        xy=b,
        xytext=a,
        arrowprops=dict(arrowstyle="<|-|>", color=color, lw=0.8, mutation_scale=10),
    )
    mid = (a + b) / 2.0
    # Offset the text a little further along the same direction.
    nlen = np.linalg.norm(n)
    extra = n / nlen * 90 if nlen else np.array([0.0, 90.0])
    ax.text(
        mid[0] + extra[0] * 0.15,
        mid[1] + extra[1] * 0.15,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=color,
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85),
    )


def draw_plan(params, V, computed, path):
    L = mm(V, "overall_length")
    W = mm(V, "overall_width")
    iw = mm(V, "interior_width")
    wall = mm(V, "wall_thickness")
    cab = mm(V, "cab_zone_length")
    front_axle = mm(V, "front_overhang")
    rear_axle = front_axle + mm(V, "wheelbase")
    od = mm(V, "tyre_od")
    tw = mm(V, "tyre_width")
    ft = mm(V, "front_track")
    rt = mm(V, "rear_track")
    gap = mm(V, "dual_tyre_gap")

    sides = params.get("sides", {})
    SL = float(sides.get("y_sign_left", -1))   # left / kerb / entry
    SR = float(sides.get("y_sign_right", 1))   # right / offside / driver

    fig, ax = plt.subplots(figsize=(16.5, 8.2))
    ax.set_aspect("equal")
    ax.set_title(
        "1988 Toyota Coaster LWB  —  empty cabin plan  —  high-roof design case\n"
        "Passenger seats removed.  Units mm.  Right-hand drive (Australia): driver on the right, entry on the kerb (left).",
        fontsize=11,
        pad=12,
    )

    # Exterior body
    ext = Rectangle((0, -W / 2), L, W, fill=False, ec="#333", lw=1.6, zorder=3)
    ax.add_patch(ext)
    # Interior walls
    ax.add_patch(Rectangle(
        (mm(V, "cavity_start_x"), -iw / 2),
        L - mm(V, "cavity_start_x") - wall,
        iw,
        fill=False, ec="#666", lw=0.8, ls="--", zorder=3,
    ))

    # Cab zone
    ax.add_patch(Rectangle(
        (mm(V, "cavity_start_x"), -iw / 2),
        cab - mm(V, "cavity_start_x"),
        iw,
        fc="#e6c888", ec="#9a7a30", lw=0.6, alpha=0.55, zorder=2, label="Driver / dash zone (retained)",
    ))

    # Usable floor
    use_len = computed.get("usable_floor_length_mm", L - cab - wall)
    use_w = computed.get("usable_floor_width_mm", iw)
    cutouts = computed.get("usable_floor_cutouts", [])
    ax.add_patch(Rectangle(
        (cab, -use_w / 2), use_len, use_w,
        fc="#8fbe8f", ec="#2f6b2f", lw=0.8, alpha=0.55, zorder=1, label="Living floor (and bedroom walkway)",
    ))
    for c in cutouts:
        ax.add_patch(Rectangle(
            (c["x0"], c["y0"]), c["x1"] - c["x0"], c["y1"] - c["y0"],
            fc="#c9c4bb", ec="#5c584f", lw=0.7, alpha=0.95, zorder=2,
            hatch="///",
        ))

    # Doors
    def door_mark(x, y_sign, width, label, color):
        y = y_sign * W / 2
        ax.add_patch(Rectangle(
            (x, y - (18 if y_sign > 0 else -18) - (0 if y_sign > 0 else 36)),
            width, 36,
            fc=color, ec="#222", lw=0.6, zorder=4, alpha=0.9,
        ))
        ax.text(x + width / 2, y + y_sign * 160, label, ha="center", va="center", fontsize=7, color="#222")

    door_mark(mm(V, "entry_door_x"), SL, mm(V, "entry_door_width"), "ENTRY DOOR\n(kerb / left)", "#6ea6d9")
    door_mark(mm(V, "driver_door_x"), SR, mm(V, "driver_door_width"), "DRIVER DOOR\n(right)", "#6ea6d9")
    # Internal rear boot enclosure (floor keep-out) and the boot lid in the lower rear panel.
    # No rear door on the 1988 LWB.
    bx1 = L - wall
    bx0 = bx1 - mm(V, "boot_depth_into_cabin")
    ax.add_patch(Rectangle((bx0, -iw / 2), bx1 - bx0, iw, fc="#d8c08a", ec="#7a5a20", lw=0.8,
                           alpha=0.85, hatch="\\\\", zorder=3, label="Internal boot (floor keep-out)"))
    ax.text((bx0 + bx1) / 2, 0, f"BOOT\n{bx1 - bx0:.0f} deep\n(internal)", ha="center", va="center",
            fontsize=7, color="#5a3a10", zorder=7)
    bo_w = mm(V, "boot_opening_width")
    ax.add_patch(Rectangle((L - 36, -bo_w / 2), 36, bo_w, fc="#d8c08a", ec="#222", lw=0.6, zorder=4))
    ax.text(L + 80, W / 2 + 280, "BOOT LID (lower rear panel,\ntop-hinged; no rear door)",
            ha="left", va="center", fontsize=7, color="#7a5a20")

    # Entry Step tread in the kerb-side step well (outboard of the floor edge).
    st = computed.get("entry_step")
    if st:
        sy0 = SL * (W / 2 - 5)
        sy1 = SL * (W / 2 - 5 - st["tread_depth"])
        ax.add_patch(Rectangle((st["x0"], min(sy0, sy1)), st["x1"] - st["x0"], abs(sy1 - sy0),
                               fc="#5a5a60", ec="#111", lw=0.6, alpha=0.85, zorder=4, label="Entry Step"))
        ax.text((st["x0"] + st["x1"]) / 2, SL * (W / 2 - 60), f"STEP z{st['z_top']:.0f}", ha="center",
                va="center", fontsize=6, color="white", zorder=8)

    # Underfloor storage bins: dashed outlines (they are below the floor).
    sto = computed.get("storage", {})
    hw = W / 2
    for i, g in enumerate(sto.get("segments", [])):
        if g["kind"] == "through":
            y0, y1 = -hw + 30, hw - 30
        else:
            sg = SL if g["sides"][0] == "L" else SR
            y0, y1 = sorted((sg * (hw - 30), sg * (hw - sto.get("depth_inboard", 600))))
        ax.add_patch(Rectangle((g["x0"], y0), g["x1"] - g["x0"], y1 - y0, fill=False, ec="#8a3a8a",
                               lw=1.0, ls="--", zorder=6, label="Underfloor storage (dashed)" if i == 0 else None))
        ax.text((g["x0"] + g["x1"]) / 2, (y0 + y1) / 2 + (0 if g["kind"] == "side" else -330),
                f"{'through ' if g['kind'] == 'through' else ''}bin {g['length']:.0f}", ha="center",
                va="center", fontsize=6, color="#8a3a8a", zorder=8)

    # Bedroom: wall, sliding door, bed platform (mattress outline dashed, shows any overrun).
    bd = computed.get("bedroom")
    if bd:
        ax.add_patch(Rectangle((bd["wall_x0"], -iw / 2), bd["wall_t"], iw, fc="#8a7f6a", ec="#333",
                               lw=0.6, zorder=6, label="Bedroom wall"))
        yc, dw = bd["door_y_center"], bd["door_w"]
        ax.add_patch(Rectangle((bd["wall_x0"] - 2, yc - dw / 2), bd["wall_t"] + 4, dw, fc="white",
                               ec="none", zorder=6))
        # Centred bi-parting leaves (closed), with arrows to each side wall.
        lw_, g2 = bd["door_leaf_w"], bd.get("door_centre_gap", 2) / 2
        for sg in (-1, 1):
            y0 = min(sg * g2, sg * (g2 + lw_))
            ax.add_patch(Rectangle((bd["wall_x0"] - 5 - bd["door_t"], y0), bd["door_t"], lw_,
                                   fc="#4a4f5a", ec="#111", lw=0.5, zorder=7))
            ax.annotate("", xy=(bd["wall_x0"] - 80, sg * (g2 + bd["door_travel"])), xytext=(bd["wall_x0"] - 80, sg * 40),
                        arrowprops=dict(arrowstyle="->", color="#4a4f5a", lw=0.8), zorder=7)
        ax.text(bd["wall_x0"] - 120, 0, f"BI-PARTING\nDOORS {dw:.0f}", ha="right", va="center", fontsize=6,
                color="#4a4f5a", zorder=8)
        pw = bd["platform_width"]
        ax.add_patch(Rectangle((bd["bed_x0"], -pw / 2), bd["bed_x1"] - bd["bed_x0"], pw, fc="#b9a6c9",
                               ec="#4a3a5a", lw=0.8, alpha=0.6, zorder=4, label="Bed platform"))
        ma, mc = bd["mattress_along_x"], bd["mattress_across_y"]
        ax.add_patch(Rectangle((bd["bed_x1"] - ma, -mc / 2), ma, mc, fill=False, ec="#4a3a5a", lw=0.8,
                               ls=":", zorder=6))
        ax.text((bd["bed_x0"] + bd["bed_x1"]) / 2, -iw / 2 + 230,
                f"BED {mc:.0f} x {ma:.0f} ({bd['orientation']})\noverrun {bd['mattress_overrun_mm']:+.0f} mm vs {iw:.0f}"
                f"\nplatform z{bd['platform_top_z']:.0f}{' over boot' if bd['over_boot'] else ''}",
                ha="center", va="center", fontsize=6.5, color="#3a2a4a", zorder=8)
        dim_line(ax, (bd["wall_x"], W / 2), (L - wall, W / 2), f"bedroom {bd['bedroom_length']:.0f}", (0, 140), fontsize=7)

    # Wheels
    def tyre(x, y, width=tw):
        ax.add_patch(Rectangle((x - od / 2, y - width / 2), od, width, fc="#222", ec="#000", lw=0.4, zorder=5, alpha=0.9))

    tyre(front_axle, SL * ft / 2)
    tyre(front_axle, SR * ft / 2)
    pair = (tw + gap) / 2
    for sign in (1, -1):
        tyre(rear_axle, sign * rt / 2 + sign * pair)
        tyre(rear_axle, sign * rt / 2 - sign * pair)

    # Driver seat
    seat_y0 = (iw / 2 - 80 - 500) if SR > 0 else (-iw / 2 + 80)
    ax.add_patch(Rectangle((cab - 580, seat_y0), 500, 500, fc="#2c3342", ec="#111", lw=0.5, zorder=4))
    ax.text(cab - 330, seat_y0 + 250, "DRIVER\nSEAT", ha="center", va="center", fontsize=6, color="white")
    ax.text(L * 0.55, SL * (iw / 2 - 120), "LEFT  ·  kerb  ·  entry", ha="center", va="center", fontsize=8, color="#1a4a7a", zorder=7)
    ax.text(L * 0.55, SR * (iw / 2 - 120), "RIGHT  ·  offside  ·  driver", ha="center", va="center", fontsize=8, color="#7a2010", zorder=7)

    # Centreline
    ax.plot([0, L], [0, 0], color="#c04040", ls="-.", lw=0.8, zorder=6, label="Centreline")

    # Axle marks
    ax.plot([front_axle, front_axle], [-W / 2 - 40, W / 2 + 40], color="#555", ls=":", lw=0.6)
    ax.plot([rear_axle, rear_axle], [-W / 2 - 40, W / 2 + 40], color="#555", ls=":", lw=0.6)
    ax.text(front_axle, W / 2 + 220, "FRONT AXLE", ha="center", fontsize=7, color="#444")
    ax.text(rear_axle, W / 2 + 220, "REAR AXLE", ha="center", fontsize=7, color="#444")

    # Dimensions
    dim_line(ax, (0, W / 2), (L, W / 2), f"overall length {L:.0f}", (0, 520), fontsize=8)
    dim_line(ax, (0, W / 2), (front_axle, W / 2), f"front OH {front_axle:.0f}  (nominal)", (0, 320), fontsize=7)
    dim_line(ax, (front_axle, W / 2), (rear_axle, W / 2), f"wheelbase {mm(V,'wheelbase'):.0f}  (confirmed)", (0, 320), fontsize=7)
    dim_line(ax, (rear_axle, W / 2), (L, W / 2), f"rear OH {mm(V,'rear_overhang'):.0f}  (derived / nominal)", (0, 320), fontsize=7)
    dim_line(ax, (cab, -W / 2), (cab + use_len, -W / 2), f"living floor length {use_len:.0f}", (0, -280), fontsize=8)
    bdf = computed.get("bedroom")
    if bdf and computed.get("bedroom_floor_length_mm", 0) > 1:
        ax.add_patch(Rectangle((bdf["wall_x"], -iw / 2), bdf["bed_x0"] - bdf["wall_x"], iw, fc="#8fbe8f",
                               ec="#2f6b2f", lw=0.8, alpha=0.55, zorder=1))
        for c in computed.get("bedroom_floor_cutouts", []):
            ax.add_patch(Rectangle((c["x0"], c["y0"]), c["x1"] - c["x0"], c["y1"] - c["y0"],
                                   fc="#c9c4bb", ec="#5c584f", lw=0.7, alpha=0.95, zorder=2, hatch="///"))
    dim_line(ax, (0, -W / 2), (cab, -W / 2), f"cab zone {cab:.0f}  (nominal)", (0, -280), fontsize=7)
    dim_line(ax, (L, -W / 2), (L, W / 2), f"overall width {W:.0f}", (420, 0), fontsize=8)
    ax.text((cab + cab + use_len) / 2, 0, f"interior width {iw:.0f} mm  (estimated)", ha="center", va="center", fontsize=8, color="#1a4a1a", bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#8fbe8f", alpha=0.9), zorder=7)

    area = computed.get("usable_floor_area_m2", use_len * use_w / 1e6)
    bed_line = ""
    if bdf:
        short = (f" (SHORT of {bdf['walkway_target']:.0f} target)" if bdf.get("walkway_short_mm", 0) > 0 else "")
        bed_line = (f"Bedroom: wall rear face at x {bdf['wall_x']:.0f} (flush with rear arch housings), "
                    f"{bdf['bedroom_length']:.0f} long; walkway {bdf.get('walkway', 0):.0f}{short}; clear walkway floor "
                    f"{computed.get('bedroom_floor_area_m2', 0):.2f} m².  Dashed purple = underfloor storage bins.\n")
    note = (
        f"Living floor  {use_len:.0f} x {use_w:.0f} mm   =   {area:.2f} m²   (cab zone to the bedroom wall)\n"
        "Area excludes wheel-arch keep-outs and the entry step well.\n" + bed_line +
        "Plan viewed from above, front at left: driver/right side (+Y) is at the top, kerb/entry side (-Y) at the bottom.\n"
        "Green = empty usable floor.  Hatched grey = arch / step keep-outs.  Hatched tan = internal boot.  Amber = retained cab zone.\n"
        "Confirmed overall: 6860 L x 1995 W, wheelbase 3800, high roof 2550.  "
        "Overhangs, interior width, floor height, doors and arches: verify by tape measure."
    )
    ax.text(
        0, -W / 2 - 980, note,
        ha="left", va="top", fontsize=8,
        bbox=dict(boxstyle="round,pad=0.4", fc="#f7f7f2", ec="#aaa"),
    )

    ax.legend(loc="upper left", fontsize=7, framealpha=0.92, bbox_to_anchor=(0.0, 1.02))
    ax.set_xlabel("X  mm   (0 = front bumper face, +X toward rear)")
    ax.set_ylabel("Y  mm   (0 = centreline, +Y = right / offside / driver, -Y = left / kerb)" if SR > 0
                  else "Y  mm   (0 = centreline, +Y = left / kerb)")
    ax.set_xlim(-200, L + 950)
    ax.set_ylim(-W / 2 - 1250, W / 2 + 900)
    ax.grid(True, ls=":", lw=0.4, color="#ccc")
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {path}")


def draw_elevation(params, V, computed, path):
    L = mm(V, "overall_length")
    H = mm(V, "overall_height")
    floor = mm(V, "floor_height")
    head = mm(V, "interior_headroom")
    skirt = mm(V, "body_skirt_z")
    front_axle = mm(V, "front_overhang")
    rear_axle = front_axle + mm(V, "wheelbase")
    od = mm(V, "tyre_od")
    wall = mm(V, "wall_thickness")

    fig, ax = plt.subplots(figsize=(16.5, 7.6))
    ax.set_aspect("equal")
    ax.set_title(
        "1988 Toyota Coaster LWB  —  kerb-side (left) elevation  —  high-roof design case\n"
        "Passenger seats removed.  Units mm.  Body shape is a design envelope; confirm overhangs and heights on the bus.",
        fontsize=11,
        pad=12,
    )

    # Ground
    ax.plot([-200, L + 400], [0, 0], color="#666", lw=1.0, zorder=1)
    ax.axhspan(-80, 0, fc="#e8e4d8", ec="none", zorder=0)

    # Simplified side profile (matches the loft stations qualitatively).
    profile_top = [
        (0, H * 0.41),
        (0.026 * L, H * 0.50),
        (0.066 * L, H * 0.69),
        (0.124 * L, H * 0.90),
        (0.190 * L, H),
        (L, H),
    ]
    # Insert U-shaped wheel-arch cutouts into the skirt, kerb-side elevation.
    arch_r = od / 2.0 + 90.0
    def skirt_with_arches(axles):
        pts = [(L, skirt)]
        stations = [L, 0.190 * L]
        # Walk from rear to front along the skirt, dropping a semicircle at each axle.
        x = L
        skirt_pts = [(L, skirt)]
        cut_xs = sorted(axles, reverse=True)
        # Build the lower outline from the rear forward, with arch dips.
        cursor_x = L
        chain = [(L, skirt)]
        for axle in cut_xs:
            # line down to the aft tangency, then the arch (upper semicircle from aft to fwd).
            x_aft = axle + arch_r
            x_fwd = axle - arch_r
            chain.append((x_aft, skirt))
            ts = np.linspace(0.0, math.pi, 24)
            for th in ts:
                # th=0 at aft (+X), th=pi at forward; z from skirt down to ground-ish then up.
                # The arch opening goes down from the skirt toward z=0.
                chain.append((axle + arch_r * math.cos(th), max(0.0, arch_r * math.sin(th))))
            chain.append((x_fwd, skirt))
        chain.append((0.190 * L, skirt))
        chain.append((0.066 * L, skirt - 20))
        chain.append((0.026 * L, mm(V, "bumper_z") + 70))
        chain.append((0, mm(V, "bumper_z")))
        return chain
    profile_bot = skirt_with_arches([front_axle, rear_axle])
    body = profile_top + profile_bot
    ax.add_patch(Polygon(body, closed=True, fc="#e9e6de", ec="#333", lw=1.4, zorder=2))

    # Roof thickness hint
    ax.plot([0.190 * L, L], [H, H], color="#333", lw=1.4)
    ax.plot([0.190 * L, L], [H - mm(V, "roof_thickness"), H - mm(V, "roof_thickness")], color="#888", lw=0.6, ls="--")

    # Floor and headroom
    ax.plot([mm(V, "cavity_start_x"), L - wall], [floor, floor], color="#6b4f32", lw=1.2, zorder=3)
    use_x1 = computed.get("usable_floor_x1_mm", L - wall - mm(V, "boot_depth_into_cabin"))
    ax.plot(
        [mm(V, "cab_zone_length"), use_x1],
        [floor + head, floor + head],
        color="#2f6b2f", lw=0.8, ls="--", zorder=3,
    )

    # Window band
    sill = mm(V, "window_sill_z")
    whead = mm(V, "window_head_z")
    # Entry door
    ex, ew, eh = mm(V, "entry_door_x"), mm(V, "entry_door_width"), mm(V, "entry_door_height")
    e_top = min(floor + eh, whead)
    ax.add_patch(Rectangle((ex, skirt), ew, e_top - skirt, fc="#e9e6de", ec="#222", lw=0.8, zorder=4))
    ax.add_patch(Rectangle((ex + 50, floor + 750), ew - 100, eh - 900, fc="#6aa3c7", ec="#222", lw=0.6, zorder=5, alpha=0.8))
    ax.text(ex + ew / 2, -160, "ENTRY DOOR", ha="center", va="top", fontsize=8, color="#1a4a7a")

    # Side windows — same layout as the macro
    start = ex + ew + 80.0
    end = L - 520.0
    n = 5
    pillar = 80.0
    win = (end - start - (n - 1) * pillar) / n
    x = start
    for _ in range(n):
        ax.add_patch(Rectangle((x, sill), win, whead - sill, fc="#6aa3c7", ec="#222", lw=0.6, zorder=4, alpha=0.7))
        x += win + pillar

    # Passenger Side Window (fixed, kerb side, opposite the driver door)
    pwin = computed.get("passenger_window")
    if pwin:
        ax.add_patch(Rectangle((pwin["x0"], pwin["z0"]), pwin["x1"] - pwin["x0"], pwin["z1"] - pwin["z0"],
                               fc="#6aa3c7", ec="#222", lw=0.6, zorder=4, alpha=0.7))

    # Windscreen
    ax.add_patch(Polygon(
        [(220, mm(V, "windscreen_sill_z")), (1280, mm(V, "windscreen_sill_z")),
         (1280, mm(V, "windscreen_head_z")), (900, mm(V, "windscreen_head_z")),
         (250, mm(V, "windscreen_sill_z") + 200)],
        closed=True, fc="#6aa3c7", ec="#222", lw=0.7, zorder=4, alpha=0.7,
    ))

    # Internal boot enclosure on the rear of the cabin floor (no rear door on the 1988 LWB).
    bx1 = L - wall
    bx0 = bx1 - mm(V, "boot_depth_into_cabin")
    b_top = floor + mm(V, "boot_height_fraction") * (sill - floor) + mm(V, "boot_panel_thickness")
    ax.add_patch(Rectangle((bx0, floor), bx1 - bx0, b_top - floor, fc="#d8c08a", ec="#7a5a20", lw=0.8,
                           alpha=0.8, hatch="\\\\", zorder=4))
    ax.text((bx0 + bx1) / 2, b_top + 40, "INTERNAL BOOT", ha="center", va="bottom", fontsize=7, color="#5a3a10", zorder=7)

    # Entry Step tread (in the door opening), storage flaps (kerb side), bedroom wall and bed.
    st = computed.get("entry_step")
    if st:
        ax.add_patch(Rectangle((st["x0"], st["z_top"] - st["thickness"]), st["x1"] - st["x0"], st["thickness"],
                               fc="#5a5a60", ec="#111", lw=0.6, zorder=6))
        ax.text((st["x0"] + st["x1"]) / 2, st["z_top"] + 30, "STEP", ha="center", va="bottom", fontsize=6, zorder=7)
    sto = computed.get("storage", {})
    for g in sto.get("segments", []):
        if "L" in g["sides"]:
            ax.add_patch(Rectangle((g["x0"], sto["z0"]), g["x1"] - g["x0"], sto["z1"] - sto["z0"], fill=False,
                                   ec="#8a3a8a", lw=0.9, ls="--", zorder=6))
            ax.text((g["x0"] + g["x1"]) / 2, (sto["z0"] + sto["z1"]) / 2, f"bin flap ({sto.get('hinge', 'top')}-hinged)",
                    ha="center", va="center", fontsize=6, color="#8a3a8a", zorder=7)
    bd = computed.get("bedroom")
    if bd:
        ax.add_patch(Rectangle((bd["wall_x0"], floor), bd["wall_t"], bd["ceiling_z"] - floor, fill=False,
                               ec="#8a7f6a", lw=1.0, ls="--", zorder=5))
        ax.text(bd["wall_x"], bd["ceiling_z"] - 60, "BEDROOM WALL", ha="left", va="top", fontsize=6, color="#5a4f3a", zorder=7)
        ax.add_patch(Rectangle((bd["bed_x0"], floor), bd["bed_x1"] - bd["bed_x0"], bd["platform_top_z"] - floor,
                               fill=False, ec="#4a3a5a", lw=1.0, ls="--", zorder=5))
        ax.text(bd["bed_x0"] + 40, bd["platform_top_z"] - 40,
                f"BED PLATFORM z{bd['platform_top_z']:.0f}\nheadroom over mattress {bd['headroom_over_mattress']:.0f}",
                ha="left", va="top", fontsize=6, color="#3a2a4a", zorder=7)

    # Bumpers
    bz, bh = mm(V, "bumper_z"), mm(V, "bumper_height")
    ax.add_patch(Rectangle((-15, bz), 90, bh, fc="#2e2e32", ec="#111", lw=0.5, zorder=5))
    ax.add_patch(Rectangle((L - 110, bz), 110, bh, fc="#2e2e32", ec="#111", lw=0.5, zorder=5))

    # Wheel arch scallops + wheels (near / kerb side)
    def wheel(axle, dual=False):
        ax.add_patch(Circle((axle, od / 2), od / 2, fc="#1a1a1a", ec="#000", lw=0.6, zorder=6))
        ax.add_patch(Circle((axle, od / 2), mm(V, "rim_diameter") / 2, fc="#b7b7b9", ec="#444", lw=0.5, zorder=7))
        ax.add_patch(Circle((axle, od / 2), 50, fc="#444", ec="#222", lw=0.4, zorder=8))
        # Arch cut outline
        r = od / 2 + 90
        ts = np.linspace(0, math.pi, 40)
        xs = axle + r * np.cos(ts)
        zs = r * np.sin(ts)
        ax.plot(xs, zs, color="#333", lw=0.8, zorder=5)

    wheel(front_axle, False)
    wheel(rear_axle, True)
    ax.text(rear_axle, -130, "DUAL REAR", ha="center", fontsize=7, color="#333")

    # Cab zone vertical
    ax.plot([mm(V, "cab_zone_length"), mm(V, "cab_zone_length")], [floor, floor + head],
            color="#9a7a30", ls="-.", lw=0.8, zorder=5)
    ax.text(mm(V, "cab_zone_length") - 40, floor + head + 60, "CAB ZONE END", ha="right", fontsize=7, color="#9a7a30")

    # Dimensions
    dim_line(ax, (0, H), (L, H), f"overall length {L:.0f}  (confirmed)", (0, 280), fontsize=8)
    dim_line(ax, (0, H), (front_axle, H), f"front OH {front_axle:.0f}", (0, 140), fontsize=7)
    dim_line(ax, (front_axle, H), (rear_axle, H), f"wheelbase {mm(V,'wheelbase'):.0f}", (0, 140), fontsize=7)
    dim_line(ax, (rear_axle, H), (L, H), f"rear OH {mm(V,'rear_overhang'):.0f}", (0, 140), fontsize=7)
    dim_line(ax, (0, 0), (0, H), f"high roof {H:.0f}  (confirmed)", (-420, 0), fontsize=8)
    dim_line(ax, (0, 0), (0, floor), f"floor {floor:.0f}  (nominal)", (-240, 0), fontsize=7)
    dim_line(ax, (L, floor), (L, floor + head), f"headroom {head:.0f}  (derived / nominal)", (260, 0), fontsize=7)
    dim_line(ax, (mm(V, "cab_zone_length"), 0), (use_x1, 0),
             f"living floor length {computed.get('usable_floor_length_mm', 0):.0f}", (0, -320), fontsize=8)

    area = computed.get("usable_floor_area_m2", 0)
    note = (
        f"Living floor (cab zone to bedroom wall)  {computed.get('usable_floor_length_mm', 0):.0f} x "
        f"{computed.get('usable_floor_width_mm', 0):.0f} mm  =  {area:.2f} m²\n"
        "Standard-roof official height is 2380 mm; this model uses the high-roof case (2550 mm = 2380 + 170).\n"
        "Floor height, overhangs, window band, door openings and arch sizes are nominal — verify by tape measure."
    )
    ax.text(0, -620, note, ha="left", va="top", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.4", fc="#f7f7f2", ec="#aaa"))

    ax.set_xlabel("X  mm   (0 = front bumper face, +X toward rear)")
    ax.set_ylabel("Z  mm   (0 = ground)")
    ax.set_xlim(-700, L + 700)
    ax.set_ylim(-850, H + 550)
    ax.grid(True, ls=":", lw=0.4, color="#ccc")
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {path}")


def look_at(eye, target, up):
    eye = np.asarray(eye, dtype=float)
    target = np.asarray(target, dtype=float)
    up = np.asarray(up, dtype=float)
    f = target - eye
    f = f / np.linalg.norm(f)
    u = up / np.linalg.norm(up)
    s = np.cross(f, u)
    s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    rot = np.stack([s, u, -f], axis=0)
    return eye, rot


def project_points(pts, eye, rot, fov_deg=32.0, aspect=1.6):
    cam = (pts - eye) @ rot.T
    # Avoid behind-camera blow-ups
    z = np.clip(-cam[:, 2], 50.0, None)
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    x = f * cam[:, 0] / z
    y = f * cam[:, 1] / z * aspect
    return np.column_stack([x, y]), z, cam


def shade_faces(verts, faces, light_dir, color, alpha=1.0, eye=None, hide_inner=False, V=None):
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-9
    n = n.copy()
    n[ok] = n[ok] / ln[ok, None]
    centres = (v0 + v1 + v2) / 3.0
    # Back-face cull so the inner skin of the hollow shell cannot paint the exterior.
    if eye is not None:
        to_eye = np.asarray(eye, dtype=float) - centres
        facing = np.einsum("ij,ij->i", n, to_eye) > 0
        # If winding is inverted on most faces, flip rather than drawing almost nothing.
        if np.count_nonzero(facing & ok) < 0.2 * max(1, np.count_nonzero(ok)):
            n = -n
            facing = np.einsum("ij,ij->i", n, to_eye) > 0
        ok = ok & facing
    # Exterior views: drop the inner skin of the hollow shell so it cannot
    # show through the lower flanks (painter's-algorithm / z-fight).
    if hide_inner and V is not None:
        iw = float(V["interior_width"])
        x0 = float(V["cavity_start_x"]) + 30.0
        x1 = float(V["overall_length"]) - float(V["wall_thickness"]) - 30.0
        z0 = float(V["floor_height"]) + 5.0
        z1 = float(V["overall_height"]) - float(V["roof_thickness"]) - 5.0
        cc = np.array([0.5 * (x0 + x1), 0.0, 0.5 * (z0 + z1)])
        inward = np.einsum("ij,ij->i", n, cc - centres) > 0
        inside = (
            (centres[:, 0] > x0) & (centres[:, 0] < x1)
            & (np.abs(centres[:, 1]) < iw / 2.0 - 5.0)
            & (centres[:, 2] > z0) & (centres[:, 2] < z1)
        )
        ok = ok & ~(inward & inside)
    light = np.asarray(light_dir, dtype=float)
    light = light / np.linalg.norm(light)
    ndotl = np.clip(n @ light, 0.0, 1.0)
    ambient, diffuse = (0.70, 0.30) if alpha < 0.99 else (0.38, 0.62)
    intens = ambient + diffuse * ndotl
    rgb = np.array(color, dtype=float)[:3]
    if alpha < 0.5:
        rgb = np.clip(rgb * 1.25, 0, 1)
    cols = np.zeros((len(faces), 4))
    cols[:, :3] = np.clip(rgb * intens[:, None], 0, 1)
    cols[:, 3] = alpha
    return np.stack([v0, v1, v2], axis=1), cols, centres, ok


def draw_3d_view(cache, V, computed, path, title, eye, target, hide_roof=False, hide_names=None, hide_inner=True):
    if not cache or not cache.get("meshes"):
        print(f"skip {path}: no render cache")
        return

    hide_names = set(hide_names or [])
    H = mm(V, "overall_height")
    roof_cut_z = H - mm(V, "roof_thickness") - 8.0
    light = np.array([0.45, 0.65, 0.85])
    eye, rot = look_at(eye, target, np.array([0.0, 0.0, 1.0]))

    opaque_parts = []
    glass_parts = []
    for item in cache["meshes"]:
        name = item["name"]
        if name in hide_names:
            continue
        if hide_roof and name.startswith("BODY_ROOF") and name != "BODY_SHELL":
            continue
        planar_cut = hide_roof and "cutaway_z_mm" in computed
        if planar_cut and item.get("cutaway_hide"):
            continue
        if planar_cut and item.get("cutaway_vertices") is not None:
            # True planar boolean cut made in FreeCAD by macro 10: clean edge, glass included.
            verts = np.asarray(item["cutaway_vertices"], dtype=float)
            faces = np.asarray(item["cutaway_faces"], dtype=int)
        else:
            verts = np.asarray(item["vertices"], dtype=float)
            faces = np.asarray(item["faces"], dtype=int)
        if verts.size == 0 or faces.size == 0:
            continue
        if hide_roof and not planar_cut and name.startswith("BODY_"):
            # Legacy cache without planar cutaway meshes: crude triangle cull.
            # Open the whole roof including over the cab, so the driver seat is visible.
            c = verts[faces].mean(axis=1)
            cut_z = min(roof_cut_z, float(V.get("window_head_z", 2360)) - 250.0)
            keep = c[:, 2] < cut_z
            faces = faces[keep]
            if len(faces) == 0:
                continue
        color = item.get("color", [0.9, 0.9, 0.88])
        if name == "CAB_STEERING":
            color = [0.75, 0.75, 0.72]
        elif name == "CAB_DRIVER_SEAT":
            color = [0.20, 0.38, 0.62]
        elif name == "CAB_INSTRUMENTS":
            color = [0.15, 0.6, 0.35]
        alpha = float(item.get("alpha", 1.0))
        is_glass = name.startswith("GLZ_")
        if is_glass:
            # Windscreen must stay readable: a dark plate hides the RHD wheel.
            alpha = 0.18 if name.startswith("GLZ_WINDSCREEN") else min(alpha, 0.32)
        try:
            tris, cols, centres, ok = shade_faces(verts, faces, light, color, alpha, eye=eye, hide_inner=hide_inner, V=V)
        except Exception:
            continue
        tris, cols, centres = tris[ok], cols[ok], centres[ok]
        if len(tris) == 0:
            continue
        (glass_parts if is_glass else opaque_parts).append((tris, cols, centres))

    parts = opaque_parts + glass_parts
    if not parts:
        print(f"skip {path}: nothing to draw")
        return

    def concat_and_sort(group):
        if not group:
            return None, None, None, None
        tris = np.concatenate([p[0] for p in group], axis=0)
        cols = np.concatenate([p[1] for p in group], axis=0)
        centres = np.concatenate([p[2] for p in group], axis=0)
        cam = (centres - eye) @ rot.T
        order = np.argsort(cam[:, 2])  # far (more negative cam_z) first
        proj, _, _ = project_points(tris.reshape(-1, 3), eye, rot, fov_deg=28.0, aspect=1.0)
        proj = proj.reshape(-1, 3, 2)
        return proj[order], cols[order], centres[order], tris[order]

    op_proj, op_cols, op_centres, _ = concat_and_sort(opaque_parts)
    gl_proj, gl_cols, _, _ = concat_and_sort(glass_parts)

    # Ground grid / shadow
    L = mm(V, "overall_length")
    W = mm(V, "overall_width")
    grid_pts = []
    for x in np.linspace(-400, L + 400, 9):
        grid_pts.append([[x, -W / 2 - 400, 0], [x, W / 2 + 400, 0]])
    for y in np.linspace(-W / 2 - 400, W / 2 + 400, 7):
        grid_pts.append([[-400, y, 0], [L + 400, y, 0]])

    fig, ax = plt.subplots(figsize=(12.5, 8.5))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=11, pad=10)

    for a, b in grid_pts:
        p, _, _ = project_points(np.array([a, b], dtype=float), eye, rot, 28.0, 1.0)
        ax.plot(p[:, 0], p[:, 1], color="#d9d5cc", lw=0.5, zorder=0)

    if op_proj is not None:
        ax.add_collection(PolyCollection(
            op_proj, facecolors=op_cols, edgecolors="none", linewidths=0, zorder=2,
        ))
    if gl_proj is not None:
        ax.add_collection(PolyCollection(
            gl_proj, facecolors=gl_cols, edgecolors="none", linewidths=0, zorder=3,
        ))

    used = op_proj if op_proj is not None else gl_proj
    xs, ys = used.reshape(-1, 2).T
    pad = 0.06 * max(xs.max() - xs.min(), ys.max() - ys.min())
    ax.set_xlim(xs.min() - pad, xs.max() + pad)
    ax.set_ylim(ys.min() - pad, ys.max() + pad)

    area = computed.get("usable_floor_area_m2")
    footer = "1988 Toyota Coaster LWB  ·  6860 x 1995 x 2550 mm  ·  WB 3800  ·  RHD  ·  seats removed"
    if area:
        footer += f"  ·  living floor {computed.get('usable_floor_length_mm', 0):.0f} x {computed.get('usable_floor_width_mm', 0):.0f} mm = {area:.2f} m²"
    ax.text(0.5, 0.02, footer, transform=ax.transAxes, ha="center", va="bottom", fontsize=7.5, color="#333")

    fig.tight_layout()
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    ntri = (0 if op_proj is None else len(op_proj)) + (0 if gl_proj is None else len(gl_proj))
    print(f"wrote {path}  ({ntri} triangles)")


def main():
    params, V, cache, computed = load_all()
    PNGS.mkdir(exist_ok=True)

    draw_plan(params, V, computed, PNGS / "1988_coaster_lwb_plan.png")
    draw_elevation(params, V, computed, PNGS / "1988_coaster_lwb_elevation.png")

    L = mm(V, "overall_length")
    W = mm(V, "overall_width")
    H = mm(V, "overall_height")
    target = np.array([L * 0.52, 0.0, H * 0.42])
    sides = params.get("sides", {})
    SL = float(sides.get("y_sign_left", -1))   # left / kerb / entry
    SR = float(sides.get("y_sign_right", 1))   # right / offside / driver

    # More frontal 3/4 from the kerb (left, +Y): entry door on the near flank,
    # windscreen more face-on so the driver/wheel read clearly on the far/right side.
    eye_front = np.array([-5200.0, SL * 3000.0, 2400.0])
    draw_3d_view(
        cache, V, computed,
        PNGS / "1988_coaster_lwb_iso_front.png",
        "1988 Toyota Coaster LWB  —  3/4 front from kerb (left): entry door near, driver on the far right",
        eye_front, target, hide_inner=True,
    )

    # 3/4 rear from the right-rear so the rear door and duals read clearly.
    eye_rear = np.array([L + 3800.0, SR * 5000.0, 2700.0])
    draw_3d_view(
        cache, V, computed,
        PNGS / "1988_coaster_lwb_iso_rear.png",
        "1988 Toyota Coaster LWB  —  3/4 rear from the offside (right)",
        eye_rear, target, hide_inner=True,
    )

    # Cutaway: hide the roof, look down into the empty cabin from front-left-high.
    eye_cut = np.array([-1800.0, SL * 4800.0, 5200.0])
    target_cut = np.array([L * 0.55, 0.0, mm(V, "floor_height") + 200.0])
    draw_3d_view(
        cache, V, computed,
        PNGS / "1988_coaster_lwb_iso_cutaway.png",
        "1988 Toyota Coaster LWB  —  cutaway (roof hidden)  —  empty passenger cabin, driver seat retained",
        eye_cut, target_cut, hide_roof=True, hide_inner=False,
    )
    write_coarse_stl(cache, EXPORTS / "meshes" / "1988_coaster_lwb_shell.stl")
    print("render ok")


def write_coarse_stl(cache, path):
    """Write a binary STL from the already-tessellated render cache (coarse, useful size)."""
    if not cache or not cache.get("meshes"):
        print("no cache; skipped coarse STL")
        return
    path = Path(path)
    path.parent.mkdir(exist_ok=True)
    n_tri = 0
    chunks = []
    for item in cache["meshes"]:
        if item["name"].startswith("REF_"):
            continue
        verts = np.asarray(item["vertices"], dtype=np.float32)
        faces = np.asarray(item["faces"], dtype=np.int32)
        if verts.size == 0 or faces.size == 0:
            continue
        v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
        n = np.cross(v1 - v0, v2 - v0)
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        ln[ln < 1e-9] = 1.0
        n = n / ln
        n_tri += len(faces)
        # Will write below in one pass — collect
        chunks.append((n.astype(np.float32), v0, v1, v2))
    header = b"1988 Coaster LWB coarse STL".ljust(80, b"\x00")
    buf = bytearray()
    buf += header
    buf += int(n_tri).to_bytes(4, "little")
    for n, v0, v1, v2 in chunks:
        rec = np.zeros((len(n), 50), dtype=np.uint8)
        packed = np.column_stack([n, v0, v1, v2]).astype(np.float32)
        rec[:, :48] = packed.view(np.uint8).reshape(len(n), 48)
        buf += rec.tobytes()
    path.write_bytes(buf)
    print(f"wrote coarse STL {path} ({n_tri} triangles, {path.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
