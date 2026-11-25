"""
Render the walk as an image sequence and export, per frame, where each label anchor lands on screen.

    python design/3d/floor/render_walk.py --blend floor.blend --out renders/walk --width 1600 --samples 128 [--start 1 --end 180 --step 1]

Writes <out>/frame_0001.png ... and <out>/anchors.json:
    {"width": 1600, "height": 900, "frames": [{"frame": 1, "anchors": {"Reception": [x, y, visible], ...}}, ...]}
x and y are fractions of the frame (0..1, origin top-left); visible is false when the point is behind the camera
or outside the frame. The web player uses these to pin labels to the desks.
"""
import argparse
import json
import os
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--blend", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--width", type=int, default=1600)
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--start", type=int, default=None)
ap.add_argument("--end", type=int, default=None)
ap.add_argument("--step", type=int, default=1)
ap.add_argument("--portrait", action="store_true", help="9:16 framing for phones")
ap.add_argument("--anchors-only", action="store_true")
a = ap.parse_args(argv)

bpy.ops.wm.open_mainfile(filepath=a.blend)
s = bpy.context.scene
cam = bpy.data.objects["CAM walk"]
s.camera = cam
s.cycles.samples = a.samples
if a.portrait:
    s.render.resolution_x = round(a.width * 9 / 16)
    s.render.resolution_y = a.width
    cam.data.sensor_fit = "VERTICAL"
    cam.data.sensor_height = 24
    cam.data.lens = 18
else:
    s.render.resolution_x = a.width
    s.render.resolution_y = round(a.width * 9 / 16)
s.render.resolution_percentage = 100
os.makedirs(a.out, exist_ok=True)
anchors = {k: Vector(v) for k, v in s["ondra_anchors"].items()}
start = a.start or s.frame_start
end = a.end or s.frame_end
frames = []
t0 = time.time()
for f in range(start, end + 1, a.step):
    s.frame_set(f)
    pts = {}
    for name, p in anchors.items():
        v = world_to_camera_view(s, cam, p)
        vis = v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1
        pts[name] = [round(v.x, 4), round(1 - v.y, 4), bool(vis)]
    frames.append({"frame": f, "anchors": pts})
    if not a.anchors_only:
        s.render.filepath = os.path.join(a.out, f"frame_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"frame {f} done, {time.time() - t0:.0f}s elapsed", flush=True)
with open(os.path.join(a.out, "anchors.json"), "w") as fh:
    json.dump({"width": s.render.resolution_x, "height": s.render.resolution_y, "frames": frames}, fh)
print("wrote", len(frames), "frames of anchors")
