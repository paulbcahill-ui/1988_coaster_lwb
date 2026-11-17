# Instructions for Grok Bot: FreeCAD on the 1988 Coaster LWB

Read this before changing anything. Update it in the same commit as any rule change.
Owner: Paul Cahill. Dates and times in AEST (Queensland).

## 1. Where things live

- Repo: `G:\My Drive\home\wkdir\artifacts\1988_coaster_lwb\` on Paul's PC (WORLDWATCH-ADMIN).
  Remote: https://github.com/paulbcahill-ui/1988_coaster_lwb, branch `main`.
- FreeCAD 1.1.1 (verified 2026-11-17):
  - `C:\Program Files\FreeCAD_1.1.1-Windows-x86_64-py311\bin\freecadcmd.exe` (headless)
  - `C:\Program Files\FreeCAD_1.1.1-Windows-x86_64-py311\bin\python.exe` (bundled Python with numpy and matplotlib)
- Live GUI: XML-RPC server at `127.0.0.1:9875`, method `execute_code`. Reach it from a machine Shell by
  piping a small Python script into `python -`, with a socket timeout of 60–90 s.
- Box/VM: there is **no FreeCAD on the box** (`which freecadcmd FreeCADCmd freecad` finds nothing,
  checked 2026-11-17). Installing it costs time and usage; do not, unless Paul asks.
- Machine Shell is **PowerShell 5**:
  - use `;`, never `&&`
  - use literal quoted paths (`Set-Location "G:\My Drive\..."`), not `$var` inside nested `-Command`
- CopyToBox and Read refuse `G:\` paths. Stage files in `C:\Users\paulb\terminals\<folder>\` first,
  then CopyToBox them into `/workspace/...`. Use CopyFromBox to bring them back the same way.

## 2. Headless or GUI?

- **Headless `freecadcmd`**: full rebuilds, booleans, exports. This is how macro 10 is designed to run.
- **GUI over RPC**: only small, read-only checks (object list, a property value, a placement).
  - Never open or close documents over RPC. Paul may have house documents open.
  - No heavy shape work over RPC. A long call blocks the GUI's dispatch: it looks "stuck" until the call
    returns.
- Paul often prefers to run the macros himself. **Edit files only unless he asks you to run them.**
  He pays for usage: plan carefully and get it right in as few runs as possible.

## 3. Build and render

From the repo folder, in PowerShell (same as the README):

```powershell
$fc = "C:\Program Files\FreeCAD_1.1.1-Windows-x86_64-py311"
& "$fc\bin\freecadcmd.exe" ".\macros\10_coaster_shell.py"
& "$fc\bin\python.exe" ".\macros\20_render_views.py"
```

- Macro 10 builds a fresh document, then writes `exports\1988_coaster_lwb_shell.FCStd` and `.step`,
  `exports\render_cache.pkl` and `exports\usable_floor.json`.
- Macro 20 renders 5 PNGs into `pngs\` from the cache and writes `exports\meshes\1988_coaster_lwb_shell.stl`.
- Syntax-check without writing `__pycache__` into the repo:
  `& "$fc\bin\python.exe" -c "import py_compile,sys; py_compile.compile(sys.argv[1], cfile=r'C:\Users\paulb\terminals\x.pyc', doraise=True)" ".\macros\10_coaster_shell.py"`

## 4. Params are the single source

- `params\coaster_params.json` holds every dimension (`dimensions_mm.<key>.value`), sides, style,
  export settings and `door_controls`.
- No millimetre literals for vehicle data in macros. Add a param with its source and confidence instead.
  Mark guesses `nominal` and "VERIFY".
- `door_controls` sets the **build-time** door states. PNG/STEP/STL show those states, not whatever was
  last clicked in the GUI.
- Fixed figures: 6860 L x 1995 W x 2550 H (high roof), wheelbase 3800, interior width 1800.
  Usable floor: 4262.5 x 1800, 6.42 m². It runs from the cab zone (1500) to the internal boot face (5762.5).

## 5. Axes and sides (Australian RHD)

- Origin: ground, centreline, front bumper face. **Front is x = 0, +X is aft, Z is up.**
- The driver faces -X, so the driver's right is (-X) x (+Z) = **+Y**.
  - **Left / kerb = -Y**: folding entry door, step well.
  - **Right / offside = +Y**: driver door, seat, steering wheel, instruments.
- Use `sides.y_sign_left` (-1) and `y_sign_right` (+1). In code, use `sides(V)` and `span(s, a, b)`.
  **Never hard-code +hw or -hw for a side.**

## 6. Naming

- Labels are plain proper nouns: Body, Roof Panel, Windscreen Left, Entry Door, Entry Door Glass,
  Driver Door, Boot Lid, Boot, Front Left Wheel, Front Left Tyre, Rear Left Arch Housing, and so on.
  Add a qualifier only on a real clash: the solid is "Roof Panel" because the group is "Roof".
- Internal Names stay stable (`BODY_SHELL`, `BODY_ROOF`, `DR_ENTRY`, `GLZ_*`, `WHL_*`, `GRP_*`, ...).
  The renderer, colours and expressions key on **Names**, so relabelling in the GUI is harmless.
  Do not rename Names without updating macro 20 and the expressions.
- Groups (Labels): Exterior, Roof, Floor, Glazing, Doors, Wheels, Wheel Arches, Cab, Cabin, Reference.
- `display_label()` / `FIXED_LABELS` in macro 10 own the mapping. Add new objects there.

## 7. Operable doors

Select the door, open its **Door** properties, change a value, then recompute. Each door's Placement is
an expression of its own properties, saved in the FCStd, so no add-on is needed. Door glass copies the
door's Placement.

| Object (Label) | Property | Range | Default |
| --- | --- | --- | --- |
| Entry Door (-Y) | `OpenFraction` | 0–1 | 0 (closed) |
| Entry Door | `SwingPhase` | 0.05–0.95 | 0.3 (swing out over 0–0.3, then slide aft) |
| Entry Door | `SwingOut` (mm) | 0–300 | 80, verify |
| Entry Door | `SlideTravel` (mm) | 0–2000 | 850, verify |
| Driver Door (+Y) | `OpenAngle` (deg) | 0–70 | 0, hinged on its front edge, opens outward |
| Boot Lid | `OpenAngle` (deg) | 0–85 | 0, top-hinged, opens up and out |

- The controls are on the door objects, not the Doors group. A child's expression that reads its own
  group would be a dependency cycle.
- Keep `SwingOut` at 45 mm or more, or the sliding door clips the rub strip.

## 8. Git

1. Commit before and after each change, one change per commit, with a clear message.
2. Files are UTF-8 without BOM, with LF endings. `core.autocrlf=false`.
3. `git status` and check the staged paths before every commit. Stage files explicitly; avoid `git add -A`.
4. Never force-push. Merge to `main` only with Paul's approval. No backup copies like `foo (1).py`:
   git is the rollback.
- Ignored as generated: `*.FCStd`, `*.FCBak`, `*.FCStd1`, `exports/*` (except `.gitkeep`), `meshes/`, `*.stl`,
  `*.step`/`*.stp`, `render_cache.pkl`, `usable_floor.json`, `__pycache__/`, `*.pyc`, Google Drive
  shortcuts and `desktop.ini`, plus `*.pdf`, `*.xlsx`, `*.mhtml` and `*.pt`. `pngs/` is tracked (small).
- The repo sits in a **Google Drive** synced folder. Don't run git while Drive is mid-sync or from two
  machines at once. If `desktop.ini` or `name (1)` files appear under `.git`, stop and tell Paul.
  GitHub is the real backup: push after commits Paul has approved.

## 9. Verify every build

1. Console: the `---- body shell ----` lines must show `valid=True closed=True solids=1 check=ok` for
   Body and Roof, and the final line must be `build ok`.
2. `exports\usable_floor.json`:
   - `failed_ops` must be empty. It lists any boolean, fillet, expression or roof split that fell back.
   - `shell_check`: Body, Roof, unsplit, and `split_volume_error_mm3` close to 0.
   - `dims_check.ok` must be true (6860 / 1995 / 2550, x_min 0).
   - `mesh_checks`: `open_edges` and `nonmanifold_edges` must be 0 per solid part.
   - `door_state`: the door values used for this build.
3. Render the PNGs and look at every one yourself. Copy them to `C:\Users\paulb\terminals\<folder>\`,
   CopyToBox them into `/workspace/uploads/`, and Read them. Check:
   - sides: entry door at -Y, steering wheel at +Y
   - the windscreen reads as glass
   - no holes or stray triangles
   - the cutaway edge is clean

## 10. Lessons learned (2026-11-17)

- **Side-sign bug**: +Y was treated as left, which put the entry door, step and driver on the wrong
  sides. With the front at x = 0 the driver's right is +Y. Check sides against this file, not instinct.
- **Lofted body**: a loft of rounded sections made a bulbous nose, a roof gap and stray triangles.
  Now the body is a boxy prism (flat raked front), its upper edges filleted, hollowed by one boolean cut
  with an inset copy. Keep it that way.
- **Cutaway**: dropping triangles by centroid gave a jagged edge and glass poking above it. Macro 10 now
  stores true planar boolean cuts (`cutaway_z_mm`) in the render cache.
- **Painter's renderer**: big triangles sort badly and show through. Meshes are welded and refined
  to `render_max_edge_mm` (250) without T-junctions, so they stay watertight.
- **No rear door** on the 1988 LWB. The rear has a full-width window, a fixed panel and a top-hinged
  Boot Lid (lower 40 % of floor-to-sill) into an internal **Boot** that intrudes about 1000 mm into the
  cabin.
- **Door expressions were written untested** (`placement()`, `rotation()`, `vector()`, `min`/`max`, `;`
  separators). After the first run, check `failed_ops` and try each door property once.
- **Usage**: Paul pays per use. Plan carefully, get it right in as few runs as possible, and don't iterate
  renders without need.
