"""Helpers that every module imports. Safe to run from FreeCAD console or freecadcmd."""

import FreeCAD as App
import Part


PROTECTED_PREFIXES = ("SITE_", "SURVEY_", "REF_")


def doc():
    d = App.ActiveDocument
    if d is None:
        raise RuntimeError("No active FreeCAD document")
    return d


def get_or_create(name, type_id="Part::Feature"):
    d = doc()
    obj = d.getObject(name)
    if obj is None:
        obj = d.addObject(type_id, name)
        obj.Label = name
    return obj


def replace_shape(name, shape):
    obj = get_or_create(name)
    obj.Shape = shape
    return obj


def purge_owned(prefix):
    """Delete only objects this module owns. Never touch protected prefixes."""
    if prefix.startswith(PROTECTED_PREFIXES) and prefix != "REF_":
        raise RuntimeError(f"refusing to purge protected prefix {prefix}")
    d = doc()
    for obj in list(d.Objects):
        if obj.Name.startswith(prefix):
            d.removeObject(obj.Name)


def recompute():
    doc().recompute()


def named(name):
    obj = doc().getObject(name)
    if obj is None:
        raise KeyError(f"missing object {name}")
    return obj


def group(name):
    d = doc()
    obj = d.getObject(name)
    if obj is None:
        obj = d.addObject("App::DocumentObjectGroup", name)
        obj.Label = name
    return obj


def add_to_group(grp, obj):
    try:
        if obj not in grp.Group:
            grp.addObject(obj)
    except Exception:
        pass
    return obj


def set_color(obj, color, transparency=0):
    """Best-effort view settings; ignored under headless freecadcmd."""
    try:
        vo = obj.ViewObject
        if vo is None:
            return
        if color is not None:
            vo.ShapeColor = tuple(float(c) for c in color[:3])
        if transparency:
            vo.Transparency = int(transparency)
    except Exception:
        pass


def add_shape(name, shape, grp=None, color=None, transparency=0):
    obj = replace_shape(name, shape)
    if color is not None or transparency:
        set_color(obj, color, transparency)
    if grp is not None:
        add_to_group(grp, obj)
    return obj
