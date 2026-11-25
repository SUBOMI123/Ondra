"""
Ondra dealership floor: scene builder for Blender 5.2 (bpy).

Builds the showroom used for the scroll-scrubbed floor tour on apps/site:
polished concrete, walnut slat walls, a glass curtain wall onto the night city,
sodium-amber pendants, three cars, six agent desks staffed by frosted-glass figures,
and the owner's glass office at the end of the aisle.

Run (from the repo root, with assets fetched by fetch_assets.py):
    python design/3d/floor/build_scene.py --assets design/3d/assets --save design/3d/floor/floor.blend
Then render stills or the camera path with render.py.

Coordinates: X across the hall (left is negative), Y along it (the aisle runs towards -Y), Z up. Metres.
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent as agent_mod  # noqa: E402

# ---------------------------------------------------------------- args
argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--assets", required=True)
ap.add_argument("--save", required=True)
ap.add_argument("--screen", default=None, help="Image for the monitor screens (the Ondra inbox)")
ap.add_argument("--human", default=None, help="MakeHuman base.obj (defaults to <assets>/human/base.obj)")
args = ap.parse_args(argv)
A = os.path.abspath(args.assets)

# ---------------------------------------------------------------- reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col_root = scene.collection

# Brand colours (linear-ish approximations of the sRGB tokens)
AMBER = (1.0, 0.52, 0.16)
AI_BLUE = (0.30, 0.50, 1.0)
VIP_RED = (1.0, 0.06, 0.06)
WARM_WHITE = (1.0, 0.86, 0.72)


# ---------------------------------------------------------------- helpers
def link(obj, collection=None):
    (collection or col_root).objects.link(obj)
    return obj


def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links


def bsdf_of(m):
    return m.node_tree.nodes["Principled BSDF"]


def img(path, non_color=False):
    i = bpy.data.images.load(path, check_existing=True)
    if non_color:
        i.colorspace_settings.name = "Non-Color"
    return i


def pbr_material(name, tex_prefix, scale=1.0, tint=(1, 1, 1), rough_range=(0.0, 1.0), coat=0.0, coat_rough=0.05, normal_strength=1.0, flatten=0.0, flatten_to=(0.3, 0.3, 0.3)):
    """Principled material from Poly Haven diffuse / normal / roughness maps, mapped in object space."""
    m, n, l = new_mat(name)
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    ext = "jpg"
    d = n.new("ShaderNodeTexImage")
    d.image = img(f"{A}/tex/{tex_prefix}_diff.{ext}")
    d.projection = "BOX"
    d.projection_blend = 0.2
    l.new(mp.outputs["Vector"], d.inputs["Vector"])
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    # Mix has float, vector and colour sockets all named A/B/Result: pick the colour ones.
    col_a = next(i for i in mix.inputs if i.name == "A" and i.type == "RGBA")
    col_b = next(i for i in mix.inputs if i.name == "B" and i.type == "RGBA")
    col_out = next(o for o in mix.outputs if o.name == "Result" and o.type == "RGBA")
    col_b.default_value = (*tint, 1)
    l.new(d.outputs["Color"], col_a)
    if flatten:
        flat = n.new("ShaderNodeMix")
        flat.data_type = "RGBA"
        flat.inputs["Factor"].default_value = flatten
        fa = next(i for i in flat.inputs if i.name == "A" and i.type == "RGBA")
        fb = next(i for i in flat.inputs if i.name == "B" and i.type == "RGBA")
        fo = next(o for o in flat.outputs if o.name == "Result" and o.type == "RGBA")
        fb.default_value = (*flatten_to, 1)
        l.new(col_out, fa)
        col_out = fo
    l.new(col_out, b.inputs["Base Color"])
    r = n.new("ShaderNodeTexImage")
    r.image = img(f"{A}/tex/{tex_prefix}_rough.{ext}", True)
    r.projection = "BOX"
    r.projection_blend = 0.2
    l.new(mp.outputs["Vector"], r.inputs["Vector"])
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = rough_range[0]
    mr.inputs["To Max"].default_value = rough_range[1]
    l.new(r.outputs["Color"], mr.inputs["Value"])
    l.new(mr.outputs["Result"], b.inputs["Roughness"])
    nt = n.new("ShaderNodeTexImage")
    nt.image = img(f"{A}/tex/{tex_prefix}_nor.{ext}", True)
    nt.projection = "BOX"
    nt.projection_blend = 0.2
    l.new(mp.outputs["Vector"], nt.inputs["Vector"])
    nm = n.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = normal_strength
    l.new(nt.outputs["Color"], nm.inputs["Color"])
    l.new(nm.outputs["Normal"], b.inputs["Normal"])
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = coat_rough
    return m


def flat_material(name, color, rough=0.5, metal=0.0, emission=None, strength=0.0):
    m, n, l = new_mat(name)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emission:
        b.inputs["Emission Color"].default_value = (*emission, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def emissive(name, color, strength):
    m, n, l = new_mat(name)
    n.remove(n["Principled BSDF"])
    e = n.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    l.new(e.outputs["Emission"], n["Material Output"].inputs["Surface"])
    return m


def glass_material(name, rough=0.02, color=(1, 1, 1)):
    m, n, l = new_mat(name)
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["Roughness"].default_value = rough
    b.inputs["IOR"].default_value = 1.45
    return m


def box(name, size, loc, mat, bevel=0.0, rot=(0, 0, 0), collection=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        bm = o.modifiers.new("bevel", "BEVEL")
        bm.width = bevel
        bm.segments = 3
        bm.limit_method = "ANGLE"
    o.data.materials.append(mat)
    if collection:
        for c in o.users_collection:
            c.objects.unlink(o)
        collection.objects.link(o)
    return o


def cylinder(name, r, h, loc, mat, verts=48, rot=(0, 0, 0), open_ends=False):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=loc, rotation=rot, end_fill_type="NOTHING" if open_ends else "NGON")
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return o


def parent_to(children, parent):
    for c in children:
        c.parent = parent


def empty(name, loc=(0, 0, 0), rot=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.location = loc
    e.rotation_euler = rot
    link(e)
    return e


def import_gltf(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path, loglevel=50)
    return [o for o in bpy.data.objects if o not in before]


def group(objs, name, loc, rot_z=0.0, scale=1.0):
    root = empty(name)
    for o in objs:
        if o.parent is None:
            o.parent = root
    root.location = loc
    root.rotation_euler = (0, 0, rot_z)
    root.scale = (scale, scale, scale)
    return root


# ---------------------------------------------------------------- materials
M = {
    "floor": pbr_material("Floor concrete", "concrete_floor_02", scale=0.32, tint=(0.62, 0.62, 0.62), rough_range=(0.12, 0.28), coat=0.55, coat_rough=0.04, normal_strength=0.25, flatten=0.4, flatten_to=(0.12, 0.12, 0.125)),
    "walnut": pbr_material("Walnut", "black_walnut_veneer_01", scale=0.9, tint=(0.36, 0.25, 0.18), rough_range=(0.32, 0.55), normal_strength=0.4),
    "walnut_desk": pbr_material("Walnut desk", "black_walnut_veneer_01", scale=0.7, tint=(0.3, 0.2, 0.145), rough_range=(0.18, 0.35), coat=0.35, coat_rough=0.12, normal_strength=0.3),
    "leather": pbr_material("Leather black", "fabric_leather_02", scale=4.0, tint=(0.12, 0.11, 0.1), rough_range=(0.35, 0.6), normal_strength=0.6, flatten=0.85, flatten_to=(0.022, 0.02, 0.019)),
    "metal_black": flat_material("Metal black", (0.02, 0.02, 0.022), rough=0.32, metal=1.0),
    "metal_brushed": flat_material("Metal brushed", (0.6, 0.6, 0.62), rough=0.28, metal=1.0),
    "panel_dark": flat_material("Panel dark", (0.025, 0.022, 0.02), rough=0.8),
    "ceiling": flat_material("Ceiling", (0.05, 0.05, 0.052), rough=0.9),
    "plastic_black": flat_material("Plastic black", (0.015, 0.015, 0.016), rough=0.45),
    "glass": glass_material("Glass wall", rough=0.01),
    "strip": emissive("Light strip", (1.0, 0.8, 0.6), 5.5),
    "pendant_glow": emissive("Pendant glow", AMBER, 45.0),
    "uplight": emissive("Uplight", (1.0, 0.6, 0.28), 7.0),
    "led_red": emissive("VIP LED", VIP_RED, 40.0),
}

# Monitor screens show the real Ondra inbox.
screen_mat, sn, sl = new_mat("Screen")
sn.remove(sn["Principled BSDF"])
se = sn.new("ShaderNodeEmission")
se.inputs["Strength"].default_value = 0.38
if args.screen and os.path.exists(args.screen):
    st = sn.new("ShaderNodeTexImage")
    st.image = img(os.path.abspath(args.screen))
    sl.new(st.outputs["Color"], se.inputs["Color"])
else:
    se.inputs["Color"].default_value = (0.75, 0.82, 1.0, 1)
sl.new(se.outputs["Emission"], sn["Material Output"].inputs["Surface"])


# The agents: frosted glass with a soft AI-blue rim. Unmistakably not people.
def agent_material():
    m, n, l = new_mat("Agent frosted glass")
    out = n["Material Output"]
    b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.92, 0.95, 1.0, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.34
    b.inputs["IOR"].default_value = 1.35
    em = n.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*AI_BLUE, 1)
    em.inputs["Strength"].default_value = 2.2
    lw = n.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    ramp = n.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.55
    ramp.inputs["From Max"].default_value = 1.0
    l.new(lw.outputs["Facing"], ramp.inputs["Value"])
    mix = n.new("ShaderNodeMixShader")
    l.new(ramp.outputs["Result"], mix.inputs["Fac"])
    l.new(b.outputs["BSDF"], mix.inputs[1])
    l.new(em.outputs["Emission"], mix.inputs[2])
    l.new(mix.outputs["Shader"], out.inputs["Surface"])
    # faint cool volume so the figure reads as a solid of glass, not a hollow shell
    vol = n.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = (0.75, 0.85, 1.0, 1)
    vol.inputs["Density"].default_value = 0.6
    l.new(vol.outputs["Volume"], out.inputs["Volume"])
    return m


M["agent"] = agent_material()

# ---------------------------------------------------------------- world: the night city outside
world = bpy.data.worlds.new("Night")
scene.world = world
world.use_nodes = True
wn, wl = world.node_tree.nodes, world.node_tree.links
env = wn.new("ShaderNodeTexEnvironment")
env.image = img(f"{A}/hdri/modern_buildings_night_2k.hdr")
wmap = wn.new("ShaderNodeMapping")
wmap.inputs["Rotation"].default_value = (0, 0, math.radians(110))
wtc = wn.new("ShaderNodeTexCoord")
wl.new(wtc.outputs["Generated"], wmap.inputs["Vector"])
wl.new(wmap.outputs["Vector"], env.inputs["Vector"])
wl.new(env.outputs["Color"], wn["Background"].inputs["Color"])
wn["Background"].inputs["Strength"].default_value = 0.14

# ---------------------------------------------------------------- the hall
HALL_X = 8.0
Y0, Y1 = 3.0, -40.0
H = 5.0
L = Y0 - Y1

floor = box("Floor", (2 * HALL_X + 2, L + 4, 0.1), (0, (Y0 + Y1) / 2, -0.05), M["floor"])
box("Ceiling", (2 * HALL_X + 2, L + 4, 0.1), (0, (Y0 + Y1) / 2, H + 0.05), M["ceiling"])

# Linear light strips in two rows down the aisle
for y in range(0, int(Y1) - 2, -4):
    for x in (-2.6, 2.6):
        box(f"Strip {x} {y}", (0.07, 2.8, 0.03), (x, y - 1.2, H - 0.02), M["strip"])

# Right wall: walnut slats over a dark panel, warm grazing uplight at the base
box("Right panel", (0.1, L, H), (HALL_X + 0.05, (Y0 + Y1) / 2, H / 2), M["panel_dark"])
slat = box("Right slats", (0.05, 0.06, H - 0.2), (HALL_X - 0.04, Y0 - 0.2, H / 2), M["walnut"])
arr = slat.modifiers.new("array", "ARRAY")
arr.relative_offset_displace = (0, -2.2, 0)
arr.count = int(L / 0.132)
box("Right uplight", (0.04, L, 0.04), (HALL_X - 0.12, (Y0 + Y1) / 2, 0.03), M["uplight"])

# Back wall: walnut slats behind the owner's office
box("Back panel", (2 * HALL_X, 0.1, H), (0, Y1 - 0.05, H / 2), M["panel_dark"])
bslat = box("Back slats", (0.06, 0.05, H - 0.2), (-HALL_X + 0.1, Y1 + 0.04, H / 2), M["walnut"])
barr = bslat.modifiers.new("array", "ARRAY")
barr.relative_offset_displace = (2.2, 0, 0)
barr.count = int(2 * HALL_X / 0.132)
box("Back uplight", (2 * HALL_X, 0.04, 0.04), (0, Y1 + 0.12, 0.03), M["uplight"])

# Left wall: glass curtain wall onto the night for the showroom half, slats beyond
GLASS_END = -17.0
glass = box("Curtain wall", (0.03, Y0 - GLASS_END, H), (-HALL_X, (Y0 + GLASS_END) / 2, H / 2), M["glass"])
glass.visible_shadow = False
for y in range(int(Y0), int(GLASS_END) - 1, -3):
    box(f"Mullion {y}", (0.08, 0.08, H), (-HALL_X + 0.02, y, H / 2), M["metal_black"])
box("Left panel", (0.1, GLASS_END - Y1, H), (-HALL_X - 0.05, (GLASS_END + Y1) / 2, H / 2), M["panel_dark"])
lslat = box("Left slats", (0.05, 0.06, H - 0.2), (-HALL_X + 0.04, GLASS_END - 0.2, H / 2), M["walnut"])
larr = lslat.modifiers.new("array", "ARRAY")
larr.relative_offset_displace = (0, -2.2, 0)
larr.count = int((GLASS_END - Y1) / 0.132)
box("Left uplight", (0.04, GLASS_END - Y1, 0.04), (-HALL_X + 0.12, (GLASS_END + Y1) / 2, 0.03), M["uplight"])

# Ground plane outside the glass so the city doesn't float
box("Outside ground", (30, 60, 0.1), (-HALL_X - 15.5, -10, -0.06), flat_material("Asphalt", (0.02, 0.02, 0.022), rough=0.55))


# ---------------------------------------------------------------- pendants
def pendant(x, y, z=3.15, light=True):
    shade = cylinder(f"Pendant {x} {y}", 0.3, 0.36, (x, y, z), M["metal_black"], open_ends=True)
    cylinder(f"Pendant cap {x} {y}", 0.3, 0.01, (x, y, z + 0.175), M["metal_black"])
    sol = shade.modifiers.new("shell", "SOLIDIFY")
    sol.thickness = 0.01
    disk = cylinder(f"Pendant glow {x} {y}", 0.27, 0.01, (x, y, z - 0.17), M["pendant_glow"])
    disk.visible_shadow = False
    cylinder(f"Cable {x} {y}", 0.004, H - z - 0.18, (x, y, (H + z + 0.18) / 2), M["metal_black"], verts=8)
    if light:
        ld = bpy.data.lights.new(f"Pendant spot {x} {y}", "SPOT")
        ld.energy = 300
        ld.color = (1.0, 0.68, 0.38)
        ld.spot_size = math.radians(95)
        ld.spot_blend = 0.8
        ld.shadow_soft_size = 0.22
        lo = bpy.data.objects.new(ld.name, ld)
        lo.location = (x, y, z - 0.2)
        link(lo)


# ---------------------------------------------------------------- furniture
def office_chair(name, loc, rot_z, seat_z=0.47):
    root = empty(name, loc, (0, 0, rot_z))
    parts = []
    for i in range(5):
        a = i / 5 * math.tau
        leg = box(f"{name} leg {i}", (0.035, 0.3, 0.035), (math.sin(a) * 0.15, math.cos(a) * 0.15, 0.07), M["metal_black"], bevel=0.01, rot=(0, 0, -a))
        cas = bpy.ops.mesh.primitive_uv_sphere_add(radius=0.03, location=(math.sin(a) * 0.29, math.cos(a) * 0.29, 0.03))
        c = bpy.context.active_object
        c.data.materials.append(M["plastic_black"])
        parts += [leg, c]
    parts.append(cylinder(f"{name} column", 0.025, seat_z - 0.1, (0, 0, (seat_z - 0.1) / 2 + 0.06), M["metal_brushed"], verts=24))
    seat = box(f"{name} seat", (0.5, 0.48, 0.09), (0, 0, seat_z - 0.045), M["leather"], bevel=0.035)
    sub = seat.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 2
    back = box(f"{name} back", (0.46, 0.07, 0.56), (0, 0.24, 0.84), M["leather"], bevel=0.03, rot=(math.radians(-8), 0, 0))
    bsub = back.modifiers.new("sub", "SUBSURF")
    bsub.levels = bsub.render_levels = 2
    parts += [seat, back, box(f"{name} spine", (0.05, 0.03, 0.4), (0, 0.27, 0.62), M["metal_black"], bevel=0.01, rot=(math.radians(-8), 0, 0))]
    for s in (-1, 1):
        parts.append(box(f"{name} arm {s}", (0.05, 0.3, 0.035), (s * 0.27, 0.0, 0.66), M["plastic_black"], bevel=0.012))
        parts.append(box(f"{name} armpost {s}", (0.03, 0.03, 0.18), (s * 0.27, 0.05, 0.57), M["metal_black"]))
    for p in parts:
        bpy.ops.object.select_all(action="DESELECT")
        p.select_set(True)
        bpy.ops.object.shade_smooth()
    parent_to(parts, root)
    return root


def monitor(name, loc, rot_z, parent=None):
    root = empty(name, loc, (0, 0, rot_z))
    bezel = box(f"{name} bezel", (0.64, 0.025, 0.38), (0, 0, 0.36), M["plastic_black"], bevel=0.006)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -0.0135, 0.36), rotation=(math.radians(90), 0, 0))
    scr = bpy.context.active_object
    scr.name = f"{name} screen"
    scr.scale = (0.61, 0.344, 1)
    scr.data.materials.append(screen_mat)
    neck = box(f"{name} neck", (0.05, 0.04, 0.2), (0, 0.04, 0.12), M["metal_brushed"], bevel=0.008)
    foot = box(f"{name} foot", (0.24, 0.18, 0.012), (0, 0.04, 0.006), M["metal_brushed"], bevel=0.004)
    parent_to([bezel, scr, neck, foot], root)
    if parent:
        root.parent = parent
    return root


def desk(name, loc, rot_z, monitors=1):
    """Desk whose working side (where the agent sits) is local -Y; monitors face the agent."""
    root = empty(name, loc, (0, 0, rot_z))
    top = box(f"{name} top", (1.7, 0.8, 0.045), (0, 0, 0.74), M["walnut_desk"], bevel=0.004)
    legs = [box(f"{name} leg {s}", (0.04, 0.72, 0.72), (s * 0.81, 0, 0.36), M["metal_black"], bevel=0.004) for s in (-1, 1)]
    modesty = box(f"{name} modesty", (1.55, 0.02, 0.36), (0, 0.33, 0.52), M["walnut_desk"])
    kb = box(f"{name} keyboard", (0.42, 0.13, 0.015), (0, -0.2, 0.77), M["plastic_black"], bevel=0.004)
    parts = [top, *legs, modesty, kb]
    parent_to(parts, root)
    monitor(f"{name} monitor", (0, 0.14, 0.7625), 0.0, parent=root)
    if monitors == 2:
        monitor(f"{name} monitor 2", (0.66, 0.06, 0.7625), math.radians(-24), parent=root)
    return root


# ---------------------------------------------------------------- the agents
TEMPLATE, HEAD_C, HEAD_R = agent_mod.build_template(args.human or f"{A}/human/base.obj", M["agent"])
SEAT_Z = max(0.42, min(0.5, agent_mod.seat_height(TEMPLATE) - 0.005))


def headset(name, root):
    """Headset sized to the figure's head, parented to the placed agent."""
    c = HEAD_C
    r = HEAD_R
    bpy.ops.mesh.primitive_torus_add(major_radius=r * 1.02, minor_radius=0.008, location=(c.x, c.y + 0.005, c.z + 0.01), rotation=(0, math.radians(90), 0))
    band = bpy.context.active_object
    band.name = f"{name} headset band"
    band.data.materials.append(M["plastic_black"])
    bpy.ops.object.shade_smooth()
    parts = [band]
    for sx in (-1, 1):
        parts.append(cylinder(f"{name} cup {sx}", 0.034, 0.022, (c.x + sx * (r * 0.98), c.y + 0.005, c.z - 0.02), M["plastic_black"], rot=(0, math.radians(90), 0)))
    parts.append(cylinder(f"{name} mic", 0.004, 0.13, (c.x + r * 0.75, c.y - 0.06, c.z - 0.07), M["plastic_black"], verts=8, rot=(math.radians(70), 0, math.radians(-35))))
    parent_to(parts, root)


# Desk stations. The agent sits on the aisle side and faces the wall; the screens face the agent,
# so from the aisle you look over the agent's shoulder at the Ondra inbox.
STATIONS = [
    # (name, x, y, side, headset, monitors)
    ("Reception", -3.7, -15.0, -1, True, 1),
    ("WhatsApp", 3.7, -15.6, 1, False, 2),
    ("Bookings", -3.7, -20.0, -1, False, 1),
    ("Service", 3.7, -20.6, 1, True, 1),
    ("Handoffs", -3.7, -25.0, -1, False, 2),
    ("Follow-ups", 3.7, -25.6, 1, False, 1),
]
for name, x, y, side, has_headset, mons in STATIONS:
    face_wall = math.radians(-90) if side < 0 else math.radians(90)  # turns the figure's -Y towards the wall
    desk(f"{name} desk", (x, y, 0), face_wall + math.pi, monitors=mons)
    seat = Vector((x - side * 0.7, y, 0))
    office_chair(f"{name} chair", seat, face_wall, seat_z=SEAT_Z)
    fig = agent_mod.place(TEMPLATE, f"{name} agent", seat, face_wall)
    if has_headset:
        headset(name, fig)
    pendant(x - side * 0.6, y, light=True)

# Showroom pendants over the cars
for (x, y) in [(-4.3, -5.2), (4.4, -3.8), (4.1, -10.2)]:
    pendant(x, y, z=3.0)

# ---------------------------------------------------------------- the cars (stand-ins; see README)
PAINTS = {"black": (0.008, 0.008, 0.009), "silver": (0.55, 0.56, 0.58), "bronze": (0.16, 0.085, 0.045)}


def car(name, loc, rot_z, paint):
    objs = import_gltf(f"{A}/models/CarConcept.glb")
    for o in list(objs):
        if o.name.startswith("License Plate") or "Emblem" in o.name or (o.type == "MESH" and not any(sl.material for sl in o.material_slots)):
            bpy.data.objects.remove(o, do_unlink=True)
            objs.remove(o)
    for o in objs:
        if o.type == "MESH":
            for slot in o.material_slots:
                mt = slot.material
                if mt and mt.name.startswith("Paint"):
                    nm = mt.copy()
                    nm.name = f"{name} paint"
                    b = nm.node_tree.nodes.get("Principled BSDF")
                    if b:
                        for lk in list(b.inputs["Base Color"].links):
                            nm.node_tree.links.remove(lk)
                        b.inputs["Base Color"].default_value = (*PAINTS[paint], 1)
                        b.inputs["Metallic"].default_value = 0.85 if paint != "black" else 0.6
                        b.inputs["Roughness"].default_value = 0.32
                        b.inputs["Coat Weight"].default_value = 1.0
                        b.inputs["Coat Roughness"].default_value = 0.03
                    slot.material = nm
    root = group(objs, name, loc, rot_z, scale=1.1)
    bpy.context.view_layer.update()
    # Ground on the tyres only: the model also carries a shadow plane below the wheels.
    tyres = [o for o in objs if o.type == "MESH" and any(sl.material and sl.material.name.startswith("Tire") for sl in o.material_slots)]
    # Use real vertices: bounding-box corners of round, rotated tyres sit below the rubber.
    zmin = min((o.matrix_world @ v.co).z for o in tyres for v in o.data.vertices)
    root.location.z -= zmin
    return root


car("Car black", (-4.3, -5.2, 0), math.radians(-150), "black")
car("Car silver", (4.4, -3.8, 0), math.radians(148), "silver")
car("Car bronze", (4.1, -10.2, 0), math.radians(-158), "bronze")

# ---------------------------------------------------------------- plants
for i, (mid, x, y, sc) in enumerate(
    [("pachira_aquatica_01", -7.0, -18.6, 1.5), ("potted_plant_02", 7.1, -12.6, 1.6), ("calathea_orbifolia_01", -7.1, -22.6, 2.2), ("potted_plant_02", 7.1, -27.8, 1.6), ("pachira_aquatica_01", -6.8, 1.6, 1.5)]
):
    objs = import_gltf(f"{A}/models/{mid}/{mid}.gltf")
    group(objs, f"Plant {i}", (x, y, 0), rot_z=i * 1.3, scale=sc)

# ---------------------------------------------------------------- the owner's office (no agent: VIPs reach you)
OY = -34.5
ow = 5.2
od = 4.2
for (sx, sy, lx, ly) in [(ow, 0.03, 0, OY + od / 2), (0.03, od, -ow / 2, OY), (0.03, od, ow / 2, OY)]:
    g = box(f"Office glass {lx} {ly}", (sx, sy, 3.0), (lx, ly, 1.5), M["glass"])
    g.visible_shadow = False
box("Office header", (ow + 0.1, od + 0.1, 0.08), (0, OY, 3.04), M["metal_black"])
box("Office door frame", (0.06, 0.06, 3.0), (0.9, OY + od / 2, 1.5), M["metal_black"])
exec_desk = empty("Owner desk", (0, OY - 0.4, 0))
dparts = [
    box("Owner desk top", (2.1, 0.95, 0.06), (0, 0, 0.74), M["walnut_desk"], bevel=0.006),
    box("Owner desk body", (2.0, 0.85, 0.7), (0, -0.02, 0.36), M["walnut_desk"], bevel=0.006),
    box("Owner laptop", (0.34, 0.24, 0.012), (-0.15, 0.05, 0.776), M["metal_brushed"], bevel=0.004),
    box("Owner phone", (0.2, 0.16, 0.05), (0.62, 0.08, 0.795), M["plastic_black"], bevel=0.01),
]
led = box("Owner phone LED", (0.026, 0.026, 0.012), (0.58, 0.155, 0.822), M["led_red"])
dparts.append(led)
parent_to(dparts, exec_desk)
office_chair("Owner chair", (0, OY - 1.2, 0), 0.0, seat_z=0.5)
lamp = import_gltf(f"{A}/models/desk_lamp_arm_01/desk_lamp_arm_01.gltf")
group(lamp, "Owner lamp", (-0.8, OY - 0.4, 0.77), rot_z=math.radians(160), scale=1.0)
for o in lamp:
    if o.type == "MESH":
        for slot in o.material_slots:
            slot.material = M["metal_black"]
lamp_light = bpy.data.lights.new("Owner lamp light", "POINT")
lamp_light.energy = 35
lamp_light.color = (1.0, 0.7, 0.4)
lamp_light.shadow_soft_size = 0.05
llo = bpy.data.objects.new("Owner lamp light", lamp_light)
llo.location = (-0.62, OY - 0.35, 1.18)
link(llo)
pendant(0, OY + 0.6, z=3.0, light=False)
office_fill = bpy.data.lights.new("Office fill", "AREA")
office_fill.energy = 18
office_fill.color = (1.0, 0.86, 0.72)
office_fill.size = 2.5
ofo = bpy.data.objects.new("Office fill", office_fill)
ofo.location = (0, OY, 2.95)
link(ofo)
red_glow = bpy.data.lights.new("VIP LED glow", "POINT")
red_glow.energy = 1.5
red_glow.color = (1.0, 0.1, 0.1)
red_glow.shadow_soft_size = 0.01
rgo = bpy.data.objects.new("VIP LED glow", red_glow)
rgo.location = (0.58, OY - 0.4 + 0.155, 0.85)
link(rgo)

# ---------------------------------------------------------------- cameras
def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def camera(name, loc, target, lens, focus=None, fstop=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_end = 120
    if focus is not None:
        cd.dof.use_dof = True
        cd.dof.focus_distance = focus
        cd.dof.aperture_fstop = fstop or 2.8
    co = bpy.data.objects.new(name, cd)
    co.location = loc
    link(co)
    look_at(co, target)
    return co


camera("CAM establishing", (0.2, 3.0, 1.62), (0.0, -24.0, 1.2), 27)
camera("CAM desk", (-1.35, -13.55, 1.52), (-3.85, -15.05, 1.0), 36, focus=2.1, fstop=3.2)
camera("CAM office", (-0.35, -29.2, 1.5), (0.05, -34.9, 0.95), 35, focus=5.4, fstop=4.0)
scene.camera = bpy.data.objects["CAM establishing"]

for o in bpy.data.objects:
    if o.type == "LIGHT":
        o.visible_camera = False
        o.visible_glossy = False  # no hot dots reflected in the glass walls

# ---------------------------------------------------------------- render settings
scene.render.engine = "CYCLES"
cy = scene.cycles
cy.device = "CPU"
cy.samples = 128
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.02
cy.use_denoising = True
cy.denoiser = "OPENIMAGEDENOISE"
cy.max_bounces = 8
cy.transmission_bounces = 8
cy.volume_bounces = 1
cy.caustics_reflective = False
cy.caustics_refractive = False
cy.sample_clamp_indirect = 8.0
cy.blur_glossy = 0.6
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = 0.6
scene.render.image_settings.file_format = "PNG"

os.makedirs(os.path.dirname(os.path.abspath(args.save)), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save))
print("saved", args.save)
