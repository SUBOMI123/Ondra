"""Point Cycles at the best GPU backend available (Metal on Apple Silicon, OptiX/CUDA on NVIDIA), else leave it on CPU."""
import bpy


def use_gpu(scene):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
        except TypeError:
            continue
        gpus = [d for d in prefs.devices if d.type != "CPU"]
        if gpus:
            for d in prefs.devices:
                d.use = d.type != "CPU" or kind == "METAL"  # Metal also runs the CPU alongside; harmless
            scene.cycles.device = "GPU"
            print("Cycles device:", kind, [d.name for d in gpus])
            return kind
    scene.cycles.device = "CPU"
    print("Cycles device: CPU (no GPU found)")
    return None
