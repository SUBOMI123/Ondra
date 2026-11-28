"""
Production car models for the showroom, loaded from .blend files in place of the stand-in CarConcept.

Each model is appended from its own .blend, stripped of cameras, lights, ground planes, badges and
plates, normalised (nose towards -Y, real-world length, centred), and its paint is replaced so one
model can be black, silver or bronze. Grounding on the tyres is done by the caller, which knows
where the car stands.

Licences are not all commercial (see docs/DECISIONS.md, 2026-11-24). Credit: Mustang (CC0, #82339),
BMW M4 (#81957), Audi A8 by 50Groszy (#13745), Lamborghini Urus (#92440), all from Blend Swap.
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

# front: direction the nose points in the source file, as (x, y).
# drop: exact object names to remove (badges, plates, lettering, helper planes, floor discs).
# paint: material names (or name prefixes) that carry the body colour.
# tyres: object name prefixes used to find the ground contact.
SPECS = {
    "mustang": dict(
        file="1968 Mustang GT Fastback/Ford_1968_Mustang_GT_Fastback.blend",
        front=(0, -1),
        length=4.76,
        drop={"Plane", "Plane.001", "LicensePlate", "LicensePlate.001"},
        paint=("CarPaint",),
        tyres=("Tire",),
    ),
    "bmw": dict(
        file="BMW M4 F82/BMW_M4_(20)_blendswap.blend",
        front=(0, -1),
        length=4.67,
        drop={"Ground", "BMWBlack", "Windscreen_for_lattice", "Main_Body.004", "Rim_cap", "Duplication_Plane_Tyre", "Duplication_Plane_Tyre_2", "Duplication_Plane_Tyre_3"},
        paint=("car_paint",),
        tyres=("Tyre",),
        # The file ships one wheel and instances it onto the other three corners with dupli-faces,
        # which Blender no longer carries over. Rebuild them: (axle y offset from the modelled wheel, mirrored to the left side).
        bounds_skip=("Rim",),  # the rim mesh carries stray geometry that would inflate the car's size
        clone_wheel=(("Tyre", "Rim"), [(0.0, True), (2.81, False), (2.81, True)]),
    ),
    "audi": dict(
        file="Audi A8 2010/Audi.blend",
        front=(-1, 0),
        length=5.14,
        drop={"Audi_logo", "Audi_logo.001", "Logo_Rim", "Logo_Rim.001", "Logo_Rim.002", "Logo_Rim.003", "Font", "Font.001", "Plane", "Plane.024", "Plane.025", "Plane.026"},
        paint=("Lakier",),
        tyres=("Tire",),
        # The author posed the front wheels turned 45 degrees for the showcase shot; straighten them.
        unsteer=(("Tire", 0.7854), ("Tire.002", 0.7854)),
        glass=("Szyby",),  # the 2011 material renders opaque white in Cycles
    ),
    "urus": dict(
        file="lamborghini urus 2019 free 3d model  non rigged/urus BS.blend",
        front=(0, 1),
        length=5.11,
        drop={"Plane.009", "Plane.011", "Plane.012", "Plane.013", "Plane.014", "Plane.015", "Plane.020", "Text"},
        paint=("car paint",),
        tyres=("opona",),
    ),
}

PAINTS = {"black": (0.008, 0.008, 0.009), "silver": (0.55, 0.56, 0.58), "bronze": (0.16, 0.085, 0.045)}


def _src(o):
    """Name the object had in its own .blend (Blender renames on collision when several cars share a scene)."""
    return o.get("src", o.name)


def _delete(o):
    bpy.data.objects.remove(o, do_unlink=True)


def _evaluated_points(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for v in me.vertices:
            yield mw @ v.co
        ev.to_mesh_clear()


def _bounds(objs):
    pts = list(_evaluated_points(objs))
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def tyre_zmin(objs, prefixes):
    tyres = [o for o in objs if o.type == "MESH" and _src(o).startswith(prefixes)]
    return min(p.z for p in _evaluated_points(tyres))


def load(model, name, assets_dir, paint):
    """Append `model`, clean and normalise it. Returns (root, objects); root origin is the car's centre on the floor plane."""
    spec = SPECS[model]
    path = os.path.join(assets_dir, spec["file"])
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        names = list(src.objects)
        dst.objects = list(names)
    objs = []
    for n, o in zip(names, dst.objects):
        if o is not None:
            o["src"] = n
            objs.append(o)
    for o in objs:
        bpy.context.scene.collection.objects.link(o)

    # Cameras, lights, anything the author hid from renders, and the named badges and plates.
    for o in list(objs):
        if o.type in {"CAMERA", "LIGHT"} or _src(o) in spec["drop"] or o.hide_render:
            objs.remove(o)
            _delete(o)
    bpy.context.view_layer.update()

    if spec.get("clone_wheel"):
        parts, corners = spec["clone_wheel"]
        src = [o for o in objs if _src(o) in parts]
        y0 = src[0].location.y
        for dy, mirror in corners:
            for o in src:
                n = o.copy()
                bpy.context.scene.collection.objects.link(n)
                if mirror:
                    n.rotation_euler.z += math.pi
                    n.location = (-o.location.x, 2 * (y0 + dy) - (o.location.y + dy), o.location.z)
                else:
                    n.location = (o.location.x, o.location.y + dy, o.location.z)
                objs.append(n)

    for tyre_name, delta in spec.get("unsteer", ()):
        pivot = next(o for o in objs if _src(o) == tyre_name).location.copy()
        rot = Matrix.Translation(pivot) @ Matrix.Rotation(delta, 4, "Z") @ Matrix.Translation(-pivot)
        for o in objs:
            if o.parent is None and abs(o.location.x - pivot.x) < 0.45 and abs(o.location.y - pivot.y) < 0.45 and abs(o.location.z - pivot.z) < 0.5:
                o.matrix_basis = rot @ o.matrix_basis
    bpy.context.view_layer.update()

    # Paint: one fresh coat shared by every body panel.
    mat = bpy.data.materials.new(f"{name} paint")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*PAINTS[paint], 1)
    b.inputs["Metallic"].default_value = 0.85 if paint != "black" else 0.6
    b.inputs["Roughness"].default_value = 0.32
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.03
    for o in objs:
        if o.type == "MESH":
            for slot in o.material_slots:
                if slot.material and slot.material.name.startswith(spec["paint"]):
                    slot.material = mat

    if spec.get("glass"):
        gm = bpy.data.materials.new(f"{name} glass")
        gm.use_nodes = True
        gb = gm.node_tree.nodes["Principled BSDF"]
        gb.inputs["Base Color"].default_value = (0.82, 0.88, 0.9, 1)
        gb.inputs["Roughness"].default_value = 0.03
        gb.inputs["Transmission Weight"].default_value = 1.0
        gb.inputs["IOR"].default_value = 1.45
        for o in objs:
            if o.type == "MESH":
                for slot in o.material_slots:
                    if slot.material and slot.material.name.startswith(spec["glass"]):
                        slot.material = gm

    # Normalise: parent everything to `inner`, turn the nose to -Y, scale to real length, centre.
    inner = bpy.data.objects.new(f"{name} inner", None)
    bpy.context.scene.collection.objects.link(inner)
    for o in objs:
        if o.parent is None or o.parent not in objs:
            o.parent = inner
    inner.rotation_euler = (0, 0, -math.pi / 2 - math.atan2(spec["front"][1], spec["front"][0]))
    bpy.context.view_layer.update()
    body = [o for o in objs if not _src(o).startswith(spec.get("bounds_skip", ()))]
    lo, hi = _bounds(body)
    inner.scale = (spec["length"] / (hi.y - lo.y),) * 3
    bpy.context.view_layer.update()
    lo, hi = _bounds(body)
    inner.location = (-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, 0)
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    inner.parent = root
    bpy.context.view_layer.update()
    return root, objs
