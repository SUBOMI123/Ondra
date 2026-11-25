"""
Render stills from the floor scene.

    python design/3d/floor/render.py --blend design/3d/floor/floor.blend --camera "CAM desk" --out out/desk.png --samples 128 --width 1600
"""
import argparse
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cycles_device  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--blend", required=True)
ap.add_argument("--camera", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--width", type=int, default=1600)
ap.add_argument("--exposure", type=float, default=None)
ap.add_argument("--device", choices=["gpu", "cpu"], default="gpu", help="Cycles device; gpu falls back to CPU when none is found")
a = ap.parse_args(argv)

bpy.ops.wm.open_mainfile(filepath=a.blend)
s = bpy.context.scene
s.camera = bpy.data.objects[a.camera]
s.cycles.samples = a.samples
if a.device == "gpu":
    cycles_device.use_gpu(s)
else:
    s.cycles.device = "CPU"
s.render.resolution_x = a.width
s.render.resolution_y = round(a.width * 9 / 16)
s.render.resolution_percentage = 100
if a.exposure is not None:
    s.view_settings.exposure = a.exposure
s.render.filepath = a.out
s.render.threads_mode = "AUTO"
t = time.time()
bpy.ops.render.render(write_still=True)
print(f"rendered {a.camera} in {time.time() - t:.0f}s -> {a.out}")
