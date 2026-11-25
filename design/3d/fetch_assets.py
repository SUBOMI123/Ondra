"""
Download the assets the floor scene needs into design/3d/assets (gitignored).

    python design/3d/fetch_assets.py

Sources and licences:
- Poly Haven textures, HDRI and models: CC0 (polyhaven.com/license)
- MakeHuman base mesh: CC0 (makehumancommunity/makehuman, LICENSE.ASSETS.md)
- Car Concept (stand-in car): CC-BY 4.0, Khronos glTF-Sample-Assets. Attribution required; logos excluded.
"""
import json
import os
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
op = urllib.request.build_opener()
op.addheaders = [("User-Agent", "ondra-asset-fetch/1.0")]
urllib.request.install_opener(op)


def get(u):
    return json.load(urllib.request.urlopen(u))


def save(url, rel):
    path = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
        print("fetched", rel)


TEXTURES = ["concrete_floor_02", "black_walnut_veneer_01", "fabric_leather_02"]
MODELS = ["potted_plant_02", "pachira_aquatica_01", "desk_lamp_arm_01", "calathea_orbifolia_01"]

for tid in TEXTURES:
    f = get(f"https://api.polyhaven.com/files/{tid}")
    for short, key in [("diff", "Diffuse"), ("nor", "nor_gl"), ("rough", "Rough")]:
        k = next(x for x in f if x.lower() == key.lower())
        e = f[k]["2k"]["jpg"]
        save(e["url"], f"tex/{tid}_{short}.jpg")

h = get("https://api.polyhaven.com/files/modern_buildings_night")["hdri"]["2k"]["hdr"]
save(h["url"], "hdri/modern_buildings_night_2k.hdr")

for mid in MODELS:
    g = get(f"https://api.polyhaven.com/files/{mid}")["gltf"]["1k"]["gltf"]
    save(g["url"], f"models/{mid}/{mid}.gltf")
    for rel, inc in g.get("include", {}).items():
        save(inc["url"], f"models/{mid}/{rel}")

save("https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/CarConcept/glTF-Binary/CarConcept.glb", "models/CarConcept.glb")
save("https://raw.githubusercontent.com/makehumancommunity/makehuman/master/makehuman/data/3dobjs/base.obj", "human/base.obj")
print("done:", OUT)
