# 3D: the dealership floor

Source for the floor tour on the marketing site: a showroom built in Blender from scripts, rendered offline and played back on the page as a scroll-scrubbed image sequence.

## Rebuild

Needs Blender 5.2 as a Python module (`pip install bpy==5.2.5`, Python 3.13) or the Blender app (`blender -b -P <script> -- <args>`).

```bash
python design/3d/fetch_assets.py
python design/3d/floor/build_scene.py --assets design/3d/assets --save design/3d/floor/floor.blend --screen design/3d/screens/inbox.png
python design/3d/floor/render.py --blend design/3d/floor/floor.blend --camera "CAM desk" --out design/3d/renders/desk.png --samples 128
```

`--screen` is a 16:9 screenshot of the Ondra inbox, shown on every monitor.

## What's in the scene

- **The agents** are frosted-glass human forms with a faint AI-blue rim (`floor/agent.py`). The body is the MakeHuman base mesh, rigged on its own joint helpers and posed seated at the keyboard. Gender-neutral and faceless on purpose: they are not people, and not robots.
- **Room:** polished concrete, walnut slat walls with warm uplights, a glass curtain wall onto the night city, sodium-amber pendants, linear ceiling lights.
- **Owner's office** at the end of the aisle: empty, with a red light on the desk phone. VIPs ring you, not the AI.
- **Cars:** stand-ins until we license production models (see below).

## Licences

| Asset | Source | Licence |
|---|---|---|
| Textures, HDRI, plants, desk lamp | Poly Haven | CC0 |
| Human base mesh | MakeHuman (`makehuman/data/3dobjs/base.obj`) | CC0 |
| Car Concept (stand-in) | Khronos glTF-Sample-Assets | CC-BY 4.0: credit "Car Concept by Eric Chadwick, Khronos Group, CC-BY 4.0" if it ships; logos excluded |

## Before launch

- **Cars:** replace the stand-in with two or three licensed production-quality models of generic luxury cars (no badges). Budget roughly $50-300 each (CGTrader, TurboSquid) or BlenderKit.
- **Final renders** are much faster on a GPU. CPU here takes about 3 minutes per 1280px frame at 96 samples.
