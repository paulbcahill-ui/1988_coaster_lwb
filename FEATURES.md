# 1988 Coaster LWB: features

What this FreeCAD build changes from a stock 1988 Toyota Coaster LWB (2nd gen, B20/B30). The figures come from
`params/coaster_params.json`, `macros/10_coaster_shell.py` and the build at commit fa86737
(`exports/usable_floor.json`, 17 Nov 2026 19:44 AEST, `failed_ops` empty). Labels below are the object and
group Labels in the FreeCAD tree. Axes: front at x = 0, aft is +X, kerb/left is -Y, offside/right is +Y.

## Body and exterior

- **RHD (Australia):** Driver Door, Driver Seat and Steering Wheel are on the offside (+Y). The folding/sliding
  Entry Door and the Entry Step are on the kerb side (-Y).
- **High roof:** 6860 L x 1995 W x 2550 H, wheelbase 3800. The build's `dims_check` reports 6860 / 1995 / 2550.
- **Roof:** the shell is split by one plane at z 2380 into **Body** (walls, Exterior group) and **Roof Panel**,
  which sits in the **Roof** group with the **Roof Brow** (a small overhang above the windscreen). The Roof group
  has no switch property; hide or show it in the tree.
- **Windscreen:** a single fixed pane with no centre pillar.
- **Front:** Windscreen Cowl, Front Panel, Grille, Grille Bars, Grille Badge, Left/Right Headlamp, Left/Right
  Indicator and a chrome Front Bumper.
- **Rear:** there is no emergency door. It has a full-width **Rear Window** (1635 x 860, 120 corner radius) and a
  top-hinged **Boot Lid** (z 594–1466, 1292 wide) between the Left/Right Tail Lamps. Rear Bumper.
- **Skirt:** a separate proud band (z 450, 250 high; Body stays one solid). The underfloor Storage Flaps sit
  in it.

## Dynamics (operable parts)

To use one: select the object or group, change the property in the Property editor, then recompute. Each moving
part's Placement is an expression, saved in the file, so no add-on is needed. Build-time values come from
`door_controls` in the params.

| Object or group (Label) | Property | Range (default) | Behaviour |
| --- | --- | --- | --- |
| Entry Door (-Y) | `OpenFraction` | 0–1 (0) | Swings out over 0–`SwingPhase`, then slides aft. Its window glass follows. |
| Entry Door | `SwingPhase` | 0.05–0.95 (0.3) | Share of the travel used for the swing |
| Entry Door | `SwingOut` (mm) | 0–300 (80) | Outward offset; keep at 45 or more to clear the rub strip |
| Entry Door | `SlideTravel` (mm) | 0–2000 (850) | Aft slide when fully open |
| Driver Door (+Y) | `OpenAngle` (deg) | 0–70 (0) | Hinged on its front edge, opens outward. Its glass follows. |
| Boot Lid | `OpenAngle` (deg) | 0–85 (0) | Top-hinged, opens up and out |
| Bedroom Doors (group, in Bedroom) | `OpenFraction` | 0–1 (0) | Bi-parting pair across the 850 x 1650 opening. Bedroom Door Left/Right read it through `href()`. |
| Bedroom Doors | `SlideTravel` (mm) | 0–1000 (425) | Slide of each leaf toward its own side |
| Left/Right Wardrobe Door 1, 2 | `OpenAngle` (deg) | 0–100 (0) | Faces the centreline. Door 1 hinges forward, door 2 aft. The handle follows. Not limited for clashes. |
| Left Storage Flap 1–2, Right Storage Flap 1–3 | `OpenAngle` (deg) | 0–90 (0) | Top-hinged, opens up and out. Its Lock Marker follows. |

**"Lockable" is not modelled.** Each flap has a **Lock Marker**, a small solid on its free edge that moves with
the flap. There is no lock state or property.

## Windows

- **17 switchable windows:**
  - Left/Right Side Window 1–6
  - Right Side Window Front
  - Passenger Side Window
  - Rear Window
  - Entry Door Window
  - Driver Door Window
- **How to switch one:** each window is a group in **Glazing** holding "<window> Glass" and "<window> Filler".
  The group carries the boolean **`Glazed`** (true = glass, false = body-coloured panel). The children's
  Visibility reads it through `href()`. Toggle `Glazed` and recompute; don't use Space. Build-time states come
  from `windows` in the params (all true).
- **Window Count** (in Glazing) has `WindowTotal` (17), `GlazedCount` and `SolidCount`.
- **The Windscreen is always glass.** It has no group, switch or filler.

## Interior

- **Seats:** all passenger seats are removed. The Driver Seat, Dash, Instrument Cluster, Steering Wheel and
  Engine Hump are kept (Cab group).
- **Living floor:** 4.63 m², x 1500–4250, 1800 wide, excluding the arches and the step well.
- **Entry Step** (Cabin group): 800 wide, 440 tread depth, top at z 450, in the kerb-side step well (x 1520–2320).
- **Underfloor storage** (Storage group): bins in the 200 mm slab between the skirt and the floor (z 450–650),
  600 inboard.
  - Right Storage Bin 1: x 1630–2370
  - Through Storage Bin 1: x 2370–4370, with flaps on both sides
  - Through Storage Bin 2: x 5430–6700, with flaps on both sides
  - The chassis, tank, spare and exhaust are not modelled. Treat the bins as placeholders.
- **Bedroom** (Bedroom group):
  - **Bedroom Wall:** 50 thick, aft face at x 4300, flush with the Rear Left/Right Arch Housings. The doorway is
    850 x 1650.
  - **Walkway** to the bed: 432.5 (target 600, flagged). Clear floor is 0.32 m².
- **Boot:** internal, 1000 deep into the cabin from the rear wall, with the bed platform on top. The boot opening
  runs z 700–1100.
- **Bed** (Bed sub-group): Bed Platform over the boot, top at z 1118, x 4732.5–6762.5.
  - **Mattress:** 1800 x 2030 x 250, full width, with rounded edges and a 15 mm crown. Headroom is 1112.
  - **Left/Right Pillow:** 730 x 480 x 130, at the head (rear).
- **Reading Lamps** sub-group: Left/Right Reading Lamp (wall plate and arm) and Shade, on the solid strip aft of
  the last side window. They sit at x 6654, arm z 2318, with the shade 780 above the mattress at |y| 600.
- **Wardrobes** sub-group (fa86737), one per side over the rear arch housing against the side wall:
  - **Size:** x 4300–4722.5 (ends `bed_wardrobe_gap` 10 forward of the bed). Inside: 386.5 long, 520 deep,
    1334 high. Outside: 422.5 long, 538 deep, 1770 high (z 700–2470).
  - **Parts:**
    - Left/Right Wardrobe: carcass, with the bus wall as the back
    - … Base: floor to z 1118, enclosing the arch housing
    - … Top Panel: fixed
    - … Door 1 and … Door 2: 159.75 wide, z 1121–2320, facing the centreline
    - … Handle 1 and … Handle 2
    - … Rail 1: across the bus at x 4511, z 2372, 500 long. It holds about 20 garments and has a 1254 drop.

## Key params (`params/coaster_params.json`, `dimensions_mm`)

| Param | Value | Confidence |
| --- | ---: | --- |
| overall_length / overall_width / overall_height | 6860 / 1995 / 2550 | confirmed |
| wheelbase | 3800 | confirmed |
| front_overhang / rear_overhang | 1100 / 1960 | nominal / derived_nominal |
| interior_width | 1800 | estimated |
| wall_thickness / roof_thickness | 97.5 / 70 | derived_nominal / nominal |
| floor_height / cab_zone_length | 700 / 1500 | nominal |
| window_sill_z / window_head_z / windscreen_sill_z | 1500 / 2360 / 1450 | nominal |
| body_skirt_z / skirt_height | 450 / 250 | nominal |
| entry_door_width | 800 | nominal |
| boot_depth_into_cabin / boot_internal_height | 1000 / 400 | nominal |
| rear_arch_length / rear_arch_width / rear_arch_height | 1200 / 400 / 400 | nominal / estimated / nominal |
| bedroom_wall_thickness / bedroom_door_opening_width / bedroom_door_height | 50 / 850 / 1650 | nominal |
| bed_mattress_width / bed_mattress_length / bed_mattress_thickness | 1830 / 2030 / 250 | standard / standard / nominal |
| wardrobe_hanger_depth / bed_wardrobe_gap | 520 / 10 | nominal |
| tyre_od | 780 | estimated |

Only the overall dimensions and the wheelbase (6 params) are confirmed from Toyota sources. The rest are tagged
nominal (125), derived (20), modelling (9), derived_nominal (5), estimated (4), standard (2) or
confirmed_adjacent (1). Everything not confirmed needs checking by tape
measure on the bus. The model clamps the king mattress (1830) to the 1800 interior and reports the 30 mm
overrun.

## Known clashes

From `wardrobes.clashes` in `exports/usable_floor.json` (fa86737 build), kept in Paul's layout:

1. Wardrobe Door 1 (each side) meets the bedroom wall at 100°.
2. Wardrobe Doors 1 and 2 open at 90° stand in the walkway: x 4320–4368 and 4654–4702, out to |y| 202.
3. Hangers (450) don't fit the 386.5 internal wardrobe length along X.
4. The passage between the closed wardrobe fronts is 724, narrower than the 850 doorway. It is 564 with one side
   open and 404 with both open.
5. The wardrobes cover Side Window 3 (132 of 644) and Side Window 4 (230 of 644) on both sides.

Also known, but not in that list:

- The Bed Platform base overlaps the Rear Left/Right Arch Housings for x 4732.5–5500, |y| 500–900. This has
  been the case since before the wardrobes.
- The Bedroom Wall crosses Side Window 3.
- The bedroom walkway (432.5) is short of the 600 target.
