"""
The Ondra agent: a seated human form in frosted glass.

Built from the MakeHuman base mesh (CC0, makehumancommunity/makehuman, data/3dobjs/base.obj),
rigged on the mesh's own joint helpers, posed seated with hands on a keyboard, then baked.
Gender-neutral on purpose: the agents are not people, they are presences at the desks.
"""
import math

import bpy
from mathutils import Matrix, Vector

S = 0.1  # MakeHuman units are decimetres


def _to_blender(p):
    # MakeHuman: x right, y up, z forward  ->  Blender: x, -z (faces -Y), y up
    return Vector((p[0] * S, -p[2] * S, p[1] * S))


def _read_obj(path):
    verts, body_faces, joints, g = [], [], {}, None
    for line in open(path):
        if line.startswith("v "):
            verts.append(tuple(map(float, line.split()[1:4])))
        elif line.startswith("g "):
            g = line.split()[1]
        elif line.startswith("f "):
            idx = [int(t.split("/")[0]) - 1 for t in line.split()[1:]]
            if g == "body":
                body_faces.append(idx)
            elif g.startswith("joint"):
                joints.setdefault(g, set()).update(idx)
    jc = {}
    for k, ids in joints.items():
        pts = [verts[i] for i in ids]
        jc[k[len("joint-") :]] = tuple(sum(p[j] for p in pts) / len(pts) for j in range(3))
    return verts, body_faces, jc


# bone name -> (head joint, tail joint, parent)
BONES = {
    "hips": ("pelvis", "spine-3", None),
    "spine": ("spine-3", "spine-1", "hips"),
    "chest": ("spine-1", "neck", "spine"),
    "neck": ("neck", "head", "chest"),
    "head": ("head", "head-2", "neck"),
}
for s in "lr":
    BONES.update(
        {
            f"clavicle.{s}": (f"{s}-clavicle", f"{s}-shoulder", "chest"),
            f"upperarm.{s}": (f"{s}-shoulder", f"{s}-elbow", f"clavicle.{s}"),
            f"forearm.{s}": (f"{s}-elbow", f"{s}-hand", f"upperarm.{s}"),
            f"hand.{s}": (f"{s}-hand", f"{s}-hand-2", f"forearm.{s}"),
            f"thigh.{s}": (f"{s}-upper-leg", f"{s}-knee", "hips"),
            f"shin.{s}": (f"{s}-knee", f"{s}-ankle", f"thigh.{s}"),
            f"foot.{s}": (f"{s}-ankle", f"{s}-foot-2", f"shin.{s}"),
        }
    )

# Seated, typing. Directions in Blender space for a figure facing -Y. Left side is +X in MakeHuman's "l".
POSE = {
    "hips": (0, 0.08, 1),
    "spine": (0, 0.04, 1),
    "chest": (0, -0.06, 1),
    "neck": (0, -0.22, 1),
    "head": (0, -0.12, 1),
    "thigh.l": (0.06, -1, -0.06),
    "thigh.r": (-0.06, -1, -0.06),
    "shin.l": (0.02, 0.12, -1),
    "shin.r": (-0.02, 0.12, -1),
    "foot.l": (0.05, -1, -0.25),
    "foot.r": (-0.05, -1, -0.25),
    "upperarm.l": (0.1, -0.3, -0.95),
    "upperarm.r": (-0.1, -0.3, -0.95),
    "forearm.l": (-0.2, -1, 0.22),
    "forearm.r": (0.2, -1, 0.22),
    "hand.l": (-0.08, -1, -0.1),
    "hand.r": (0.08, -1, -0.1),
}


# Twist about the bone's own axis (degrees) so palms face the keyboard, not each other.
ROLL = {"forearm.l": 40, "forearm.r": -40, "hand.l": 80, "hand.r": -80}


def build_template(obj_path, material, name="Agent template"):
    """Returns (mesh_object, head_world_center, head_radius) with the seated pose applied, feet on Z=0."""
    verts, faces, jc = _read_obj(obj_path)
    used = sorted({i for f in faces for i in f})
    remap = {o: n for n, o in enumerate(used)}
    me = bpy.data.meshes.new(name)
    me.from_pydata([_to_blender(verts[i]) for i in used], [], [[remap[i] for i in f] for f in faces])
    me.validate()
    body = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(body)

    arm_data = bpy.data.armatures.new(f"{name} rig")
    arm = bpy.data.objects.new(f"{name} rig", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = {}
    for bn, (h, t, par) in BONES.items():
        b = arm_data.edit_bones.new(bn)
        b.head = _to_blender(jc[h])
        b.tail = _to_blender(jc[t])
        eb[bn] = b
    for bn, (_, _, par) in BONES.items():
        if par:
            eb[bn].parent = eb[par]
            eb[bn].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # Skin with automatic (heat) weights
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")

    # Pose: aim each bone along its target direction, parents first
    bpy.ops.object.mode_set(mode="POSE")
    order = list(BONES)  # dict order is already parent-before-child
    for bn in order:
        if bn not in POSE:
            continue
        pb = arm.pose.bones[bn]
        bpy.context.view_layer.update()
        rest = pb.bone.matrix_local
        rest_dir = (pb.bone.tail_local - pb.bone.head_local).normalized()
        want = Vector(POSE[bn]).normalized()
        q = rest_dir.rotation_difference(want)
        head_now = pb.head.copy()  # posed head in armature space, from the parent's pose
        rot = q.to_matrix().to_4x4() @ Matrix(rest.to_3x3()).to_4x4()
        if bn in ROLL:
            rot = Matrix.Rotation(math.radians(ROLL[bn]), 4, want) @ rot
        pb.matrix = Matrix.Translation(head_now) @ rot
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()

    # Bake the pose into the mesh
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    for m in body.modifiers:
        if m.type == "ARMATURE":
            bpy.ops.object.modifier_apply(modifier=m.name)
    head_pb = arm.pose.bones["head"]
    head_center = (arm.matrix_world @ head_pb.head + arm.matrix_world @ head_pb.tail) / 2
    head_r = (_to_blender(jc["head-2"]) - _to_blender(jc["head"])).length * 0.62
    body.parent = None
    bpy.data.objects.remove(arm, do_unlink=True)

    # Feet on the floor, pelvis over the origin
    zs = [v.co.z for v in body.data.vertices]
    pelvis = _to_blender(jc["pelvis"])
    shift = Vector((-pelvis.x, -pelvis.y - 0.02, -min(zs)))
    body.data.transform(Matrix.Translation(shift))
    head_center += shift

    for p in body.data.polygons:
        p.use_smooth = True
    sub = body.modifiers.new("sub", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    body.data.materials.clear()
    body.data.materials.append(material)
    body.hide_render = True
    body.hide_viewport = True
    return body, head_center, head_r


def seat_height(template):
    """Height of the underside of the thighs, to size the chair to the figure."""
    vs = [v.co for v in template.data.vertices if -0.32 < v.co.y < -0.12 and abs(v.co.x) < 0.2]
    return min(v.z for v in vs) if vs else 0.47


def place(template, name, loc, rot_z):
    o = bpy.data.objects.new(name, template.data)
    for m in template.modifiers:
        nm = o.modifiers.new(m.name, m.type)
        if m.type == "SUBSURF":
            nm.levels, nm.render_levels = m.levels, m.render_levels
    o.location = loc
    o.rotation_euler = (0, 0, rot_z)
    bpy.context.scene.collection.objects.link(o)
    return o
