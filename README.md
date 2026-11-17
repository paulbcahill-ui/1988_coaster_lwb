# 1988 Toyota Coaster LWB — FreeCAD empty-cabin layout

FreeCAD design layout of a **1988 Toyota Coaster long-body** (2nd generation, B20/B30 series) with **all passenger seats removed**. The driver seat, dash and steering wheel are retained. Right-hand drive (Australia): driver on the right, passenger entry door on the kerb (left) side. Two side doors only: there is **no rear emergency door**; the rear has a full-width window above a lower-rear luggage boot with its own lid.

**Agents (Grok Bot): read [AGENTS.md](AGENTS.md) first** for how to work with FreeCAD on this project.

Created 16 Nov 2026 (Australia/Brisbane). Folder layout follows `house-whitsundays`: `exports`, `lib`, `macros`, `params`, `scans`, `refs`, `docs`, `pngs`.

The 3D model is a recognisable hollow Coaster body (boxy body, flat slightly raked front, two-piece windscreen, flat grille, low headlamps, full-width bumper, side window band, doors, rear boot, roof, wheels and tyres, interior wall thickness) — not a solid block. The passenger cabin is an empty, labelled volume.

## Important: which dimensions were used

The figures **6990 / 2030 / 2635 / 3935 mm** belong to the **3rd-generation and later** Coaster (1993–), not a 1988 B20/B30. This build uses official 2nd-generation long-body figures.

| Dimension | Value (mm) | Status | Source |
| --- | ---: | --- | --- |
| Overall length | 6860 | Confirmed | [Toyota 75-year lineage, long body K-BB30-MRY](https://www.toyota-global.com/company/history_of_toyota/75years/vehicle_lineage/car/id60006636/index.html); [20 May 1982 Toyota press release](https://global.toyota/en/detail/7714342) |
| Overall width | 1995 | Confirmed | Same Toyota official table; [CarsGuide 1988 SWB](https://www.carsguide.com.au/toyota/coaster/car-dimensions/1988) / [1992 LWB](https://www.carsguide.com.au/toyota/coaster/1992) |
| Overall height (high roof, design case) | 2550 | Confirmed | Official standard-body high roof 2550; official text: high roof is +170 mm on both bodies, so LWB high roof = 2380 + 170. Australian 1988 SWB listings are 2550. [CarsGuide 1992 LWB](https://www.carsguide.com.au/toyota/coaster/1992) lists 2560 — a late-gen 10 mm difference. |
| Overall height (standard roof) | 2380 | Confirmed, not used | Official long-body example grade. Confirm which roof the actual bus has. |
| Wheelbase | 3800 | Confirmed | Toyota official long body; 1982 press release; [CarsGuide 1988 Deluxe LWB](https://www.carsguide.com.au/toyota/coaster/price/1988/deluxe-lwb) |
| Front overhang | 1100 | **Nominal — measure** | Not published for 2nd gen. |
| Rear overhang | 1960 | **Derived / measure** | 6860 − 3800 − 1100. Only as good as the front overhang. |
| Interior width | 1800 | **Estimated — measure** | Later Coaster wall build-up (2080 − 1885 = 195) applied to the 1995 mm 2nd-gen body. 1880 mm would leave only ~57 mm per wall on this body and is likely optimistic. |
| Interior headroom | 1780 | **Derived / measure** | 2550 − 700 floor − 70 roof. |
| Floor height above ground | 700 | **Nominal — measure** | Brief planning value. |
| Driver cab zone (from front) | 1500 | **Nominal — measure** | Brief planning value. Empty passenger floor starts aft of this station. |
| Wall thickness | 97.5 | **Derived / measure** | (1995 − 1800) / 2. |
| Ground clearance | 185 | Adjacent confirmed | [1988 SWB](https://www.carsguide.com.au/toyota/coaster/car-dimensions/1988) 185 mm; 1992 LWB listed 195 mm. 1988 LWB not published. |
| Tyre | 7.00R16, OD ~780, width 178 | Fitment confirmed, OD estimated | CarsGuide 1988 Deluxe LWB lists 7.00R16 (in the track fields). Dual rears assumed for Deluxe LWB. |

Every value, source URL and confidence tag also lives in `params/coaster_params.json`. **Do not hard-code millimetres in macros** — change the params file and regenerate.

## Living floor and bedroom

Computed from the params (exact numbers are also stored on **Living Floor** (`FLR_EMPTY_USABLE`) and **Bedroom Floor** in the FreeCAD document and in `exports/usable_floor.json`; the `usable_floor_*` keys are the living floor):

- Living floor: from the cab zone (1500) to the forward face of the bedroom wall (4250) = **2750 × 1800 = 4.95 m²**, minus the front-arch overlap 2 × 100 × 220 = 0.044 and the entry step well 800 × 350 = 0.280 → **4.626 m² ≈ 4.63 m²**.
- Bedroom: the wall's rear face (`bedroom_wall_x` = 4300) is flush with the forward face of the rear arch housings (rear axle 4900 − 1200/2), so the housings are wholly inside the bedroom. Bedroom length 6762.5 − 4300 = **2462.5 mm** (4.43 m² footprint). Bed platform 2030 long over the boot (4732.5–6762.5). The bed fits, but the walkway is only **432.5 mm** (4300–4732.5), **167.5 short of the 600 target**; this is flagged, not fixed by moving the wall. Clear walkway floor 432.5 × 1800 = 0.7785 m² minus the full housing depth in it, 2 × 432.5 × 400 = 0.346 → **0.4325 m² ≈ 0.43 m²** (1000 mm clear between the housings; the rest of each housing, 4732.5–5500, is under the platform).
- Before the bedroom and the wider step well (boot only): 4262.5 × 1800 − 1.249 = 6.42 m².

The green floor in the plan and in the cutaway view is the living floor plus the bedroom walkway. Hatched boxes are keep-outs. Amber is the retained driver/dash zone. There are **no passenger seats**.

## What’s in the build

| Path | Role |
| --- | --- |
| `params/coaster_params.json` | Source of truth for every dimension, source and confidence |
| `lib/fcutil.py` | Shared FreeCAD helpers (same idea as the house project) |
| `macros/10_coaster_shell.py` | Builds the hollow 3D body, cabin, refs; writes FCStd, STEP, meshes, render cache |
| `macros/20_render_views.py` | Plan, side elevation, and three 3D isometric PNGs |
| `exports/1988_coaster_lwb_shell.FCStd` | FreeCAD document |
| `exports/1988_coaster_lwb_shell.step` | STEP of the real solids (not reference wires) |
| `exports/meshes/1988_coaster_lwb_shell.stl` | Coarse combined STL (~2.3 MB) from the render mesh; fine per-part STLs are not kept |
| `exports/usable_floor.json` | Computed usable floor figures |
| `pngs/1988_coaster_lwb_plan.png` | Dimensioned plan of the empty floor |
| `pngs/1988_coaster_lwb_elevation.png` | Dimensioned kerb-side elevation |
| `pngs/1988_coaster_lwb_iso_front.png` | Exterior 3/4 front |
| `pngs/1988_coaster_lwb_iso_rear.png` | Exterior 3/4 rear |
| `pngs/1988_coaster_lwb_iso_cutaway.png` | Roof hidden, empty interior |

FreeCAD groups (Labels): **Exterior**, **Floor**, **Glazing**, **Doors**, **Wheels**, **Wheel Arches**, **Cab**, **Cabin**, **Reference**, **Storage**, **Bedroom**. Plus **Roof**, which holds the roof solid (Label **Roof Panel**, qualified because the group is already called Roof). The roof solid is split from Body along one plane, `roof_split_z_mm` = (window head 2360 + fillet start 2400) / 2 = 2380, so the two meet exactly. Body (the walls) stays in Exterior. The internal boot enclosure is **Boot**, in Cabin.

Labels are plain proper nouns, for example Body, Windscreen Left / Right, Left Side Window 1–5, Rear Window, Passenger Side Window, Entry Door, Entry Door Glass, Driver Door, Driver Door Glass, Boot Lid, Front Bumper, Grille, Left Headlamp, Front Left Wheel / Front Left Tyre, Rear Left Outer Tyre, Rear Left Arch Housing, Driver Seat, Steering Wheel, Entry Step, Left Storage Bin 1 / Through Storage Bin 1, Left Storage Flap 1, Left Lock Marker 1, Bedroom Wall, Bedroom Door Left / Right, Bed Platform, Living Floor, Bedroom Floor and Centreline. A qualifier is added only where two labels would clash. Internal **Names** keep their safe prefixes (`GRP_`, `BODY_`, `DR_`, `GLZ_`, `WHL_`, …), and the renderer and expressions key on Names, so relabelling in the GUI breaks nothing.

Coordinate system: origin at the ground plane, vehicle centreline and front bumper face; **+X toward the rear**, **+Y toward the right / offside (driver)**, **−Y toward the left / kerb**, **+Z up**. Units mm.

## How to regenerate

FreeCAD 1.1.1 is at `C:\Program Files\FreeCAD_1.1.1-Windows-x86_64-py311`. From this folder, in PowerShell:

```powershell
$fc = "C:\Program Files\FreeCAD_1.1.1-Windows-x86_64-py311"
& "$fc\bin\freecadcmd.exe" ".\macros\10_coaster_shell.py"
& "$fc\bin\python.exe" ".\macros\20_render_views.py"
```

Edit `params/coaster_params.json` first if a tape measurement replaces a nominal value. Then rerun both commands. The macro is idempotent: it creates a fresh document and overwrites the exports.

## Measure on the actual bus

These are the values that should be taped and then written back into `params/coaster_params.json`:

- Roof height (standard 2380 vs high roof 2550 / possibly 2560)
- Front and rear overhangs (bumper face to axle centre)
- Interior width between finished side walls, mid-body, above the arches
- Interior headroom at the aisle centreline
- Finished floor height above ground (and any steps or changes of level)
- Depth of the driver/dash zone
- Wall, floor and roof thickness
- Entry and driver door opening sizes and positions; internal boot depth into the cabin, boot lid width and height
- Interior wheel-arch keep-out length, width and height (left and right)
- Entry step-well size, step tread height and depth, and the ground-to-step rise
- Underfloor: chassis rails, fuel tank, spare wheel, exhaust and driveshaft positions (none are modelled), and the real space for side bins
- Mattress actually wanted (king 1830 is 30 mm wider than the 1800 interior), and where a window pillar falls near the bedroom wall
- Window sill and head heights
- Track widths, tyre size / overall diameter, and whether the rears are duals

## Layout (Australian RHD)

Left and right are defined in `params/coaster_params.json` under `sides`, from the driver's seat facing forward (toward the front, −X):

- **−Y = left / kerb**: passenger entry door (just behind the left front wheel) and the entry step well.
- **+Y = right / offside**: driver seat, steering wheel, instrument cluster, and the driver door.
- Why: the front is at x = 0 and the bus runs aft along +X, so the driver faces −X; with +Z up the driver's right is (−X) × (+Z) = +Y. Every side-dependent part reads `y_sign_left` / `y_sign_right` (−1 / +1); nothing hard-codes a side.
- Rear: full-width rear window, a fixed rear panel, and in the lower `boot_height_fraction` (0.40) of the floor-to-sill height a top-hinged Boot Lid opening into an internal Boot enclosure, which protrudes `boot_depth_into_cabin` (1000, verify) into the cabin. It is not a walk-through door.

The body is a **single continuous** `BODY_SHELL` (walls and roof together). The roof is not split off as a separate cap, so the front header/brow stays part of the same solid.

## Visual notes

The 3D model is a **design layout envelope**, not a factory-accurate Class-A body. Front-end detail (grille, lamps, bumper) is simplified and should not be used as a fabrication pattern. Confirm every nominal dimension on the actual bus before fitting out.

The 3/4-front PNG is taken from the kerb (left, −Y) so the entry door is on the near flank; the driver is on the far/right side (+Y). Camera sides follow the params signs.

## Conventions (aligned with the house project)

- Scripts are the source of truth; the `.FCStd` is a derived artefact.
- No millimetre literals for measured vehicle data outside `params/`.
- Prefixes are owned by the numbered macro; reference objects use the `REF_` prefix.

## Body rebuild, 17 Nov 2026

Changes made to `macros/10_coaster_shell.py`, `params/coaster_params.json` and `macros/20_render_views.py`:

- **Sides fixed.** Left/kerb = −Y and right/offside/driver = +Y (see Layout). This covers the entry door, step well, driver door, seat, steering wheel, dash, wheels, arches, lamps and strips.
- **Body is one closed solid.** A boxy prism (flat front raked `front_rake_deg` = 8°, flat roof, vertical sides and rear), with every upper edge filleted at `body_edge_radius` = 150. The cabin is then removed with one boolean cut using the same form inset by the wall/roof thickness. This replaces the old lofted, bulbous nose (the source of the roof gap and the stray triangles).
- **Front.** There is a two-piece windscreen (centre `windscreen_mullion`, slim `a_pillar_width` strips), a separate flat grille panel with bars, rectangular headlamps low either side, and a full-width bumper.
- **Glass.** Panes are separate 6 mm solids recessed 15 mm inside their openings, so none stands proud or pokes above a cut. The windscreen panes render at alpha 0.18.
- **No rear door.** The `rear_door_*` params are removed. There is a full-width rear window. The boot was later made internal (see *Internal boot and roof split*).
- **Doors.** Door heads are capped at `window_head_z` so they don't notch the roof radius. The entry-door opening runs down to the skirt (step well).
- **Wheel arches** are now centred on the wheel and open up into the interior arch housings.
- **Cutaway.** The roof-off view uses true planar booleans at `cutaway_z_mm` made by macro 10, giving a clean cut edge with glass included.
- **Checks.** After the build, `exports/usable_floor.json` holds `shell_check` (valid, closed, solids, `check()`, volume, bbox), `dims_check` (overall L/W/H against params), `mesh_checks` (open or non-manifold edges per part) and `failed_ops`. Render and STL meshes are vertex-welded and refined to `export.render_max_edge_mm` (250) without T-junctions.
- **Not modelled.** There is no roof crown (the roof is flat with radiused edges) and no mirrors, wipers or badges. The rub strips stand 8 mm proud of the 1995 mm width.

Rebuild exactly as in *How to regenerate*. Run macro 10 first, then 20.

## Operable doors

Select the door in the tree, open its **Door** properties in the property editor, change a value, and recompute (Ctrl+R if auto-recompute is off). The door glass moves with the door. This works in any FreeCAD 1.1 without the house add-on: each door's Placement is an expression of its own properties, saved in the FCStd.

| Object (Label) | Property | Type | Range | Default |
| --- | --- | --- | --- | --- |
| Entry Door (left, −Y) | `OpenFraction` | float | 0–1 | 0 (closed) |
| Entry Door | `SwingPhase` | float | 0.05–0.95 | 0.3 (0–0.3 swings out, 0.3–1 slides toward the rear) |
| Entry Door | `SwingOut` | float, mm | 0–300 | 80 (**verify**) |
| Entry Door | `SlideTravel` | float, mm | 0–2000 | 850 (**verify**) |
| Driver Door (right, +Y) | `OpenAngle` | float, degrees | 0–70 | 0; hinged on the front edge, opens outward |
| Boot Lid | `OpenAngle` | float, degrees | 0–85 | 0; top-hinged, opens up and out |
| Left/Right Storage Flap n | `OpenAngle` | float, degrees | 0–90 | 0; top-hinged (gas-strut style), opens up and out; its Lock Marker follows |
| Bedroom Door Left | `OpenFraction` | float | 0–1 | 0; drives **both** bi-parting leaves, each slides toward its own side wall |
| Bedroom Door Left | `SlideTravel` | float, mm | 0–1000 | half the opening = 425 (each leaf) |

Bedroom Door Right has no controls; its Placement expression reads Bedroom Door Left's, mirrored (no cycle).

The initial values come from `door_controls` in `params/coaster_params.json`. The PNGs, STEP and STL show the doors in the state they were in at build time. To render an open door, set its value in `door_controls`, then rerun macros 10 and 20.

## Internal boot and roof split (17 Nov 2026)

- **Boot.** The external boot box and its pocket are gone, and the rear is a plain face again. The rear panel is split: the boot opening and lid take the lower 40 % of the height from the floor line (700) to the rear window sill (1620), so z 700–1068. A fixed panel runs above it up to the window. The opening is `boot_opening_width` = 1200 wide (verify) and sits inside the tail lamps. The **Boot** enclosure (front face plus top, 18 mm panels, across the 1800 inside width) stands on the rear of the cabin floor and reaches 1000 mm in from the inner rear wall, with its top's underside at 1068. **Boot Lid** keeps `OpenAngle` (0–85°, top-hinged). The rear bumper is back on the normal bumper line.
- **Usable floor.** It now ends at the boot's front face: 4262.5 × 1800, 6.42 m². `usable_floor.json` adds `usable_floor_x0_mm`, `usable_floor_x1_mm` and `boot_enclosure`. The plan and elevation show the boot as a hatched tan keep-out.
- **Roof.** The **Roof Panel** solid (group **Roof**) is split from **Body** with one half-space box at z 2380 (common gives the roof, cut gives the walls), so there is no gap or overlap. `shell_check` reports Body, Roof, the unsplit shell and the Body+Roof volume error (expect about 0). The dims check uses the combined bounding box, STEP and STL include the roof, and the roof-off cutaway hides it automatically because it lies wholly above the 2110 cut.
- **Params (boot).** Removed `boot_depth`, `boot_width`, `boot_bottom_z`, `boot_top_z`, `boot_wall` and `rear_bumper_*`. Added `boot_depth_into_cabin` = 1000, `boot_height_fraction` = 0.40, `boot_opening_width` = 1200 (all nominal, verify) and `boot_panel_thickness` = 18.

## Entry step, underfloor storage and bedroom (17 Nov 2026)

- **Entry Step** (group **Cabin**, a fixed fitting). Tread top at `entry_step_z` (null = bottom of the entry door opening = skirt 450), 30 thick, 800 wide (`entry_step_width` null = door width, x 1520–2320), 440 deep from the skin (`entry_step_tread_depth`), so it fills the bottom of the step well. The well (skin to |y| 550, x 1520–2320) is cut out of the floor slab and the Cabin Floor plate. The old `entry_step_width` (350, inward depth of the well) is now `entry_step_well_inboard`; `entry_step_length` (700) is gone, so the step-well keep-out is now 800 × 350. Only the step in the well is modelled, not the ground-to-step rise.
- **Storage** group. Bins run from the bottom of the skin (450) to the underside of the cabin floor (650), so they are only 200 mm tall in this model. Runs are derived between the bumpers, the arch cuts (tyre radius + 90) and, on the kerb side, the step well, with 50 mm clearances, and nothing forward of the cab zone (1500: engine and radiator). Kerb (−Y): 2370–4370 (2000) and 5430–6700 (1270). Offside (+Y): 1630–4370 (2740) and 5430–6700 (1270). Where both sides overlap, one **Through Storage Bin** spans the width with a flap each side (2370–4370 and 5430–6700). **Right Storage Bin 1** (1630–2370, 600 deep) is opposite the step well. Each bin is an open tray (12 mm panels), each flap is top-hinged (`storage_flap_hinge`), and each has a **Lock Marker** at its free edge. Override runs with `storage_left_runs`/`storage_right_runs`, or set `storage_pass_through` false. **The real underfloor (chassis rails, fuel tank, spare wheel, exhaust, driveshaft) is not modelled and must be measured.** The through-bins would cross the chassis rails and the driveshaft on a real Coaster.
- **Bedroom** group. A king mattress (1830 × 2030) does not fit crosswise (2030 and 1830 both exceed 1800). Lengthwise it is **30 mm wider than the 1800 interior**. The platform is built at 1800 wide (`bed_platform_width` null = min(mattress, interior)) and the overrun is reported, not hidden. Options: a queen (1530 × 2030, 270 spare) or king single (1070 × 2030), a custom 1800 × 2030 mattress, or squeezing a soft king 15 mm per side. The bed sits **over the boot** (`bed_over_boot` true): platform top 1100 (boot top 1086, raised to clear the rear-arch housings at 1100). Headroom is 2480 − 1100 = 1380 over the platform, 1130 over a 250 mattress (sitting, not standing). The boot is then reached only from outside through the Boot Lid (or a hatch in the platform). Bed forward of the boot instead puts the wall 1000 mm further forward (wall_x 3132.5) and cuts the living floor to 1582.5 × 1800 − 0.324 = 2.52 m². Its default 450 platform (z 1150) gives *less* headroom (1330 over the platform, 1080 over the mattress); its only gain is inside access to the boot from the bedroom. *Superseded on 17 Nov by the bedroom update below.*
- `usable_floor.json` adds `entry_step`, `storage` (runs, segments, hinge), `bedroom` (fit, heights, wall_x, door) and `living_floor_*` / `bedroom_floor_*` / `bedroom_footprint_m2`. Plan: step, dashed bins, wall, door, bed and mattress outline. Elevation: step, kerb-side flaps, wall and platform.

## Bedroom update (17 Nov 2026)

- **Wall.** `bedroom_wall_x` (null = derived) = the forward face of the rear arch housings, computed by the same `arch_housing_x0()` the housings use: 4900 − 1200/2 = **4300**. The 50 mm wall occupies 4250–4300. The rear-arch housings are now wholly in the bedroom. Bedroom 2462.5 long; the walkway in front of the bed is 432.5 (target `bedroom_walkway` 600, reported as `bedroom.walkway_short_mm` = 167.5). The wall still lands in side window 3 (4008–4732): 242 mm aft of its front edge and 432 mm forward of its rear edge. The nearest pillars are 3928–4008 and 4732–4812.
- **Doors.** The single slider is replaced by a centred bi-parting pair, **Bedroom Door Left** and **Bedroom Door Right**, on the living side of the wall. Opening `bedroom_door_opening_width` = **850** × `bedroom_door_height` 1650, centred on y = 0. Each leaf is 850/2 + 30 overlap − 1 (half the 2 mm centre gap) = 454 wide and 35 thick, and slides 425 toward its own side wall. Open, the inner edge is at |y| 426, clear of the 425 jamb, and the outer edge at |y| 880, 20 mm from the 900 side wall (clearance needs ≥ 10). With the 30 mm jamb overlap the largest opening that fits is 900 − 10 − 30 = **860**, so the suggested 900 would put each open leaf 30 mm into the side wall (outer edge at |y| 930). `bedroom_door_slide`, `bedroom_door_width` and `bedroom_door_y_center` are removed. New: `bedroom_door_opening_width`, `bedroom_door_leaf_overlap` (30), `bedroom_door_centre_gap` (2), `bedroom_door_side_clearance` (10).
- **Floors.** Living 4.63 m² (2750 × 1800 − 0.044 − 0.280). Bedroom walkway 0.43 m².

## Passenger Side Window (17 Nov 2026)

- Fixed glass on the kerb side (−Y, `y_sign_left`) in the cab zone, opposite the driver door: **Passenger Side Window** (`GLZ_PASSENGER`, group Glazing), with a matching opening cut in Body. It is not a door.
- Profile = the Driver Door Glass opening (same formula, `driver_glass_profile()`): x 900–1490, z 1445–2120 (door head 2200 − 80, sill 2120 − 0.45 × 1500 = 1445). Params `passenger_window_x0/x1/sill_z/head_z` default to those (null) and can be overridden.
- Clearance check with an 80 mm pillar (`passenger_window_min_pillar`, null = side-window pillar): front limit = raked face at the head (294.7) + edge radius 150 + 80 = 524.7, so 900 clears the A-pillar corner. Rear limit = entry door 1520 − 80 = 1440, so the mirrored 1490 would leave only 30 mm and is **trimmed to 1440**. Built opening: **x 900–1440 (540 wide), z 1445–2120 (675 tall)**; glass 2 mm inside that, recessed 15 mm. `usable_floor.json` → `passenger_window` records the profile, limits and trim.
