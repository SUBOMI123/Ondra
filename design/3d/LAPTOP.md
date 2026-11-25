# Final renders on your laptop

The cloud session that built this scene renders on a CPU (about 3 minutes per full-quality frame). Your laptop's GPU does the same frame in seconds, and it can see the car models on your Desktop. Do the final renders there.

## 1. Set up (once)

1. Install **Blender 5.2 LTS** from blender.org.
2. In Blender: Edit > Preferences > System > Cycles Render Devices. Pick **Metal** (Apple Silicon Mac) or **OptiX** (NVIDIA). Tick your GPU.
3. Pull the branch in your local clone of the repo:
   ```bash
   git fetch origin claude/magical-galileo-kn5bw6 && git checkout claude/magical-galileo-kn5bw6
   ```
4. Open the **Claude desktop app**, start a **Claude Code** session in that repo folder, and paste the prompt below.

## 2. Prompt to paste

> Continue the 3D floor for the Ondra landing page. Read `design/3d/README.md`, `design/3d/LAPTOP.md` and `docs/DECISIONS.md` first, and use the `ondra-ui` skill.
>
> 1. Look in `~/Desktop/car models`. For each model, tell me the file format, where it came from and its licence (look for a licence or readme file next to it). Flag anything that isn't cleared for commercial use on a website, and any visible brand badges, grilles or logos. Don't use a model until I've confirmed it.
> 2. For the models I confirm: add an option to `design/3d/floor/build_scene.py` that loads them in place of the stand-in CarConcept, removes badges and plates, grounds them on the tyres, and recolours the paint (black, silver, bronze).
> 3. Fetch assets with `python design/3d/fetch_assets.py`, build the scene with Blender's own Python (`blender -b -P design/3d/floor/build_scene.py -- --assets design/3d/assets --save design/3d/floor/floor.blend --screen design/3d/screens/inbox.png`), and set Cycles to use the GPU.
> 4. Render the three look-dev stills first (`render.py`, cameras "CAM establishing", "CAM desk", "CAM office") so I can check the cars.
> 5. Once I approve, render the walk with `render_walk.py` at 1600 wide, 128 samples, all 180 frames, plus the portrait version for phones (`--portrait --width 1280`). Keep `anchors.json` from both.

## 3. What to expect

| Machine | Per frame (1600px, 128 samples) | Whole walk (180 frames) |
|---|---|---|
| NVIDIA RTX 3070 and up | 5 to 15 s | 15 to 45 min |
| Apple M2/M3 Pro or Max | 20 to 45 s | 1 to 2.5 h |
| Apple M1 / base chips | 45 to 90 s | 2.5 to 4.5 h |
| This cloud session (CPU) | about 3 min | about 9 h |

These are estimates; the first few frames tell you the real number.
