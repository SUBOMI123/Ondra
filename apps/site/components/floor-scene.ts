/**
 * The dealership floor for the walk-through, built in code as a high-end architectural model:
 * faceless porcelain mannequins (the agents are not people, so they don't pretend to be),
 * clearcoat cars, walnut and glass, lit by an environment map plus warm sodium pendants.
 *
 * Loaded on demand by Walkthrough.tsx, so three.js never touches first paint.
 */
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";

export type FloorEls = {
  section: HTMLElement;
  canvas: HTMLCanvasElement;
  labels: HTMLDivElement;
  intro: HTMLDivElement;
  outro: HTMLDivElement;
};

type Agent = {
  x: number;
  z: number;
  ry: number;
  role: string;
  name: string;
  doing: string;
  headset?: boolean;
  two?: boolean;
  amber?: boolean;
};

const AGENTS: Agent[] = [
  { x: -3.2, z: -12, ry: Math.PI / 2, role: "Voice agent", name: "Reception", doing: "Answering a call about a black G63", headset: true },
  { x: 3.2, z: -12.5, ry: -Math.PI / 2, role: "Messaging agent", name: "WhatsApp and email", doing: "Replying to a buyer in Lagos with photos", two: true },
  { x: -3.2, z: -17, ry: Math.PI / 2, role: "Booking agent", name: "Test drives and visits", doing: "Booking a video walkaround for Thursday", amber: true },
  { x: 3.2, z: -17.5, ry: -Math.PI / 2, role: "Service agent", name: "Service desk", doing: "Fitting an oil change into Bay 2", headset: true },
  { x: -3.2, z: -22, ry: Math.PI / 2, role: "Routing agent", name: "Handoffs", doing: "Sending a qualified buyer to Daniel in Sales", two: true },
  { x: 3.2, z: -22.5, ry: -Math.PI / 2, role: "Follow-up agent", name: "Follow-ups", doing: "Drafting nudges for buyers who went quiet", amber: true },
];

type V3 = [number, number, number];

export function mountScene(els: FloorEls) {
  const { section, canvas, labels, intro, outro } = els;
  const small = window.innerWidth < 700;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, small ? 1.5 : 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const bg = new THREE.Color(0xd9d3c9);
  scene.background = bg;
  scene.fog = new THREE.Fog(bg, 20, 42);

  // Soft studio reflections on paint, glass and the polished floor.
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = envTex;
  scene.environmentIntensity = 0.55;

  const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 100);

  scene.add(new THREE.HemisphereLight(0xfffaf0, 0xb3a796, 0.9));
  const sun = new THREE.DirectionalLight(0xfff1dc, 2.0);
  sun.position.set(6, 12, 4);
  sun.castShadow = true;
  sun.shadow.mapSize.set(small ? 1024 : 2048, small ? 1024 : 2048);
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.02;
  Object.assign(sun.shadow.camera, { left: -10, right: 10, top: 20, bottom: -20, far: 60 });
  sun.target.position.set(0, 0, -14);
  scene.add(sun, sun.target);

  /* ------------------------------------------------------------ materials */
  const std = (color: number, roughness = 0.8, metalness = 0) =>
    new THREE.MeshStandardMaterial({ color, roughness, metalness });
  const paint = (color: number) =>
    new THREE.MeshPhysicalMaterial({ color, metalness: 0.55, roughness: 0.32, clearcoat: 1, clearcoatRoughness: 0.06 });

  const M = {
    floor: new THREE.MeshPhysicalMaterial({ color: 0xcdc6bb, roughness: 0.32, clearcoat: 0.35, clearcoatRoughness: 0.25 }),
    wall: std(0xefebe4, 0.92),
    walnut: std(0x6e4b34, 0.5),
    deskTop: std(0x7d5a42, 0.42),
    metal: std(0x232428, 0.35, 0.6),
    chair: std(0x26282d, 0.62),
    mannequin: new THREE.MeshPhysicalMaterial({ color: 0xe4ddd1, roughness: 0.42, clearcoat: 0.25, clearcoatRoughness: 0.4 }),
    joint: new THREE.MeshPhysicalMaterial({ color: 0xcfc4b3, roughness: 0.5 }),
    headset: std(0x1b1c20, 0.4, 0.3),
    glass: new THREE.MeshPhysicalMaterial({ color: 0xcfe0ea, transparent: true, opacity: 0.16, roughness: 0.04, metalness: 0.1 }),
    carGlass: new THREE.MeshPhysicalMaterial({ color: 0x0c0f14, roughness: 0.06, metalness: 0.2, clearcoat: 1 }),
    tyre: std(0x101012, 0.85),
    rim: std(0xb8bbc0, 0.25, 1),
    headlight: new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff6e8, emissiveIntensity: 1.6 }),
    taillight: new THREE.MeshStandardMaterial({ color: 0x7a0f12, emissive: 0xd93a3f, emissiveIntensity: 1.2 }),
    strip: new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff4e0, emissiveIntensity: 1.1 }),
    shade: std(0x1d1e22, 0.5, 0.2),
    bulb: new THREE.MeshStandardMaterial({ color: 0xffd9a0, emissive: 0xf2a33a, emissiveIntensity: 2.2 }),
    red: new THREE.MeshStandardMaterial({ color: 0xd93a3f, emissive: 0xd93a3f, emissiveIntensity: 1.1 }),
    plant: std(0x3f5a3a, 0.8),
    pot: std(0x2a2b2f, 0.6),
  };
  const screens = { blue: screenMaterial("blue"), amber: screenMaterial("amber") };

  /* ------------------------------------------------------------ helpers */
  type Par = THREE.Object3D;
  const add = <T extends THREE.Mesh>(o: T, par: Par, cast = true): T => {
    o.castShadow = cast;
    o.receiveShadow = true;
    par.add(o);
    return o;
  };
  const rbox = (w: number, h: number, d: number, r: number, m: THREE.Material, x: number, y: number, z: number, par: Par = scene) => {
    const o = add(new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 3, Math.min(r, w / 2, h / 2, d / 2)), m), par);
    o.position.set(x, y, z);
    return o;
  };
  const box = (w: number, h: number, d: number, m: THREE.Material, x: number, y: number, z: number, par: Par = scene) => {
    const o = add(new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m), par);
    o.position.set(x, y, z);
    return o;
  };
  const cyl = (rt: number, rb: number, h: number, m: THREE.Material, x: number, y: number, z: number, par: Par = scene, seg = 28) => {
    const o = add(new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), m), par);
    o.position.set(x, y, z);
    return o;
  };
  const sphere = (r: number, m: THREE.Material, p: V3, par: Par, scale: V3 = [1, 1, 1]) => {
    const o = add(new THREE.Mesh(new THREE.SphereGeometry(r, 24, 18), m), par);
    o.position.set(...p);
    o.scale.set(...scale);
    return o;
  };
  const up = new THREE.Vector3(0, 1, 0);
  /** A rounded limb from a to b, with a ball joint at a. */
  const limb = (a: V3, b: V3, r: number, par: Par, joint = true) => {
    const va = new THREE.Vector3(...a);
    const vb = new THREE.Vector3(...b);
    const dir = vb.clone().sub(va);
    const len = dir.length();
    const o = add(new THREE.Mesh(new THREE.CapsuleGeometry(r, Math.max(0.001, len - r * 0.6), 6, 16), M.mannequin), par);
    o.position.copy(va).add(vb).multiplyScalar(0.5);
    o.quaternion.setFromUnitVectors(up, dir.normalize());
    if (joint) sphere(r * 1.08, M.joint, a, par);
    return o;
  };

  /* ------------------------------------------------------------ room */
  const floor = add(new THREE.Mesh(new THREE.PlaneGeometry(16, 46), M.floor), scene, false);
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(0, 0, -16);
  box(0.2, 4.2, 46, M.wall, -7, 2.1, -16);
  box(0.2, 4.2, 46, M.wall, 7, 2.1, -16);
  box(14, 4.2, 0.2, M.wall, 0, 2.1, -36);
  // Walnut slat wall behind the owner's office, echoing the showroom in the hero photo.
  for (let x = -6.6; x <= 6.6; x += 0.22) box(0.11, 4.0, 0.08, M.walnut, x, 2.0, -35.85);
  for (let z = -2; z > -34; z -= 4) {
    box(0.12, 0.04, 2.6, M.strip, -2.2, 3.95, z).castShadow = false;
    box(0.12, 0.04, 2.6, M.strip, 2.2, 3.95, z).castShadow = false;
  }
  // Back-wall sign on a light panel. Redrawn once Archivo has loaded.
  {
    const c = document.createElement("canvas");
    c.width = 1024;
    c.height = 200;
    const g = c.getContext("2d")!;
    const draw = () => {
      g.fillStyle = "#F1EFEA";
      g.fillRect(0, 0, c.width, c.height);
      g.fillStyle = "#16171B";
      g.font = "700 84px Archivo, Arial, sans-serif";
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText("Your Dealership", 512, 104);
    };
    draw();
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    const p = new THREE.Mesh(new THREE.PlaneGeometry(4.1, 0.8), new THREE.MeshBasicMaterial({ map: t }));
    p.position.set(0, 3.72, -35.75);
    scene.add(p);
    document.fonts?.ready.then(() => {
      draw();
      t.needsUpdate = true;
      render();
    });
  }
  // Plants and pendant lights for warmth.
  const plant = (x: number, z: number) => {
    cyl(0.28, 0.22, 0.55, M.pot, x, 0.275, z);
    for (let i = 0; i < 7; i++) {
      const a = (i / 7) * Math.PI * 2;
      sphere(0.26, M.plant, [x + Math.cos(a) * 0.16, 0.85 + (i % 3) * 0.16, z + Math.sin(a) * 0.16], scene, [1, 1.3, 1]);
    }
  };
  plant(-6.2, -14.5);
  plant(6.2, -20);
  plant(-6.2, -26);
  const pendant = (x: number, z: number, light: boolean) => {
    cyl(0.006, 0.006, 1.1, M.metal, x, 3.65, z, scene, 6).castShadow = false;
    cyl(0.16, 0.3, 0.32, M.shade, x, 2.95, z).castShadow = false;
    const b = cyl(0.27, 0.27, 0.02, M.bulb, x, 2.78, z);
    b.castShadow = false;
    if (light) {
      const l = new THREE.PointLight(0xffb45e, 5, 6, 1.6);
      l.position.set(x, 2.6, z);
      scene.add(l);
    }
  };
  [-12.2, -17.2, -22.2].forEach((z, i) => {
    pendant(-3.2, z, i !== 1 || !small);
    pendant(3.2, z - 0.3, !small);
  });

  /* ------------------------------------------------------------ cars */
  const car = (x: number, z: number, ry: number, color: number) => {
    const g = new THREE.Group();
    g.position.set(x, 0, z);
    g.rotation.y = ry;
    scene.add(g);
    const body = new THREE.Group();
    body.rotation.y = Math.PI / 2; // profile is drawn along x; the car's length runs along z
    g.add(body);

    const W = 1.86;
    const bevel = 0.08;
    // Lower body: full width, up to the beltline.
    const profile = new THREE.Shape();
    profile.moveTo(-2.2, 0.3);
    profile.lineTo(-2.27, 0.6);
    profile.quadraticCurveTo(-2.24, 0.82, -1.92, 0.86);
    profile.lineTo(-1.0, 0.95);
    profile.lineTo(1.92, 0.99);
    profile.quadraticCurveTo(2.3, 0.94, 2.28, 0.62);
    profile.lineTo(2.22, 0.3);
    profile.closePath();
    const bodyGeo = new THREE.ExtrudeGeometry(profile, {
      depth: W - bevel * 2,
      bevelEnabled: true,
      bevelSize: bevel,
      bevelThickness: bevel,
      bevelSegments: 6,
      curveSegments: 18,
    });
    bodyGeo.translate(0, 0, -(W - bevel * 2) / 2);
    const bodyPaint = paint(color);
    add(new THREE.Mesh(bodyGeo, bodyPaint), body);

    // Glass cabin, narrower than the body (tumblehome), with a painted roof panel.
    const cabin = new THREE.Shape();
    cabin.moveTo(-1.08, 0.94);
    cabin.quadraticCurveTo(-0.64, 1.3, -0.38, 1.37);
    cabin.lineTo(0.8, 1.39);
    cabin.quadraticCurveTo(1.42, 1.31, 1.88, 0.98);
    cabin.closePath();
    const cw = W - 0.34;
    const cabinGeo = new THREE.ExtrudeGeometry(cabin, { depth: cw - 0.12, bevelEnabled: true, bevelSize: 0.06, bevelThickness: 0.06, bevelSegments: 4, curveSegments: 16 });
    cabinGeo.translate(0, 0, -(cw - 0.12) / 2);
    add(new THREE.Mesh(cabinGeo, M.carGlass), body);
    rbox(1.2, 0.05, cw - 0.08, 0.025, bodyPaint, 0.22, 1.43, 0, body);

    // Light strips
    box(0.04, 0.05, W * 0.8, M.headlight, -2.28, 0.72, 0, body).castShadow = false;
    box(0.04, 0.05, W * 0.84, M.taillight, 2.29, 0.84, 0, body).castShadow = false;

    // Wheels: tyre, rim, spokes
    for (const [wx, side] of [[-1.38, 1], [1.38, 1], [-1.38, -1], [1.38, -1]] as const) {
      const wheel = new THREE.Group();
      wheel.position.set(wx, 0.37, side * (W / 2 - 0.04));
      body.add(wheel);
      const tyre = add(new THREE.Mesh(new THREE.TorusGeometry(0.28, 0.1, 14, 36), M.tyre), wheel);
      tyre.scale.z = 1.25;
      const rim = add(new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.2, 32), M.rim), wheel);
      rim.rotation.x = Math.PI / 2;
      for (let s = 0; s < 5; s++) {
        const sp = box(0.04, 0.42, 0.03, M.tyre, 0, 0, side * 0.105, wheel);
        sp.rotation.z = (s / 5) * Math.PI;
      }
    }
  };
  car(-3.8, -3.2, 0.35, 0x0b0c0e);
  car(3.8, -4.2, -0.4, 0xb4b7bb);
  car(-4.0, -8.6, 0.25, 0x3a2a1c);

  /* ------------------------------------------------------------ mannequin */
  /** A seated, faceless mannequin. Local frame: seat at origin, facing -z (towards the desk). */
  const mannequin = (par: Par, headset: boolean) => {
    const p = new THREE.Group();
    par.add(p);
    // Pelvis and torso
    sphere(0.15, M.mannequin, [0, 0.6, 0.02], p, [1.25, 0.75, 1]);
    const torsoProfile = [
      [0.0, 0.0],
      [0.13, 0.0],
      [0.125, 0.12],
      [0.16, 0.3],
      [0.185, 0.4],
      [0.15, 0.47],
      [0.06, 0.5],
      [0.0, 0.5],
    ].map(([r, y]) => new THREE.Vector2(r, y));
    const torso = add(new THREE.Mesh(new THREE.LatheGeometry(torsoProfile, 28), M.mannequin), p);
    torso.scale.set(1, 1, 0.72);
    torso.position.set(0, 0.62, 0.02);
    torso.rotation.x = -0.07;
    // Neck and head (egg-shaped, no face)
    limb([0, 1.1, 0], [0, 1.2, -0.02], 0.045, p, false);
    sphere(0.105, M.mannequin, [0, 1.31, -0.04], p, [0.92, 1.18, 1]);
    // Arms reaching to the keyboard
    for (const s of [-1, 1]) {
      const shoulder: V3 = [s * 0.2, 1.03, 0.0];
      const elbow: V3 = [s * 0.25, 0.84, -0.2];
      const wrist: V3 = [s * 0.13, 0.83, -0.47];
      limb(shoulder, elbow, 0.05, p);
      limb(elbow, wrist, 0.042, p);
      sphere(0.05, M.mannequin, [wrist[0], wrist[1] - 0.01, wrist[2] - 0.06], p, [0.8, 0.5, 1.4]);
      // Legs
      const hip: V3 = [s * 0.1, 0.56, -0.02];
      const knee: V3 = [s * 0.11, 0.57, -0.44];
      const ankle: V3 = [s * 0.11, 0.1, -0.5];
      limb(hip, knee, 0.075, p);
      limb(knee, ankle, 0.058, p);
      rbox(0.09, 0.07, 0.22, 0.03, M.mannequin, ankle[0], 0.04, ankle[2] - 0.06, p);
    }
    if (headset) {
      const band = add(new THREE.Mesh(new THREE.TorusGeometry(0.125, 0.014, 8, 32, Math.PI), M.headset), p);
      band.position.set(0, 1.33, -0.04);
      band.rotation.y = Math.PI / 2;
      sphere(0.04, M.headset, [0.12, 1.3, -0.04], p, [0.6, 1, 1]);
      sphere(0.04, M.headset, [-0.12, 1.3, -0.04], p, [0.6, 1, 1]);
      (limb([0.12, 1.27, -0.06], [0.05, 1.2, -0.17], 0.008, p, false) as THREE.Mesh).material = M.headset;
    }
    return p;
  };

  /* ------------------------------------------------------------ desk stations */
  const station = (x: number, z: number, ry: number, o: { empty?: boolean; two?: boolean; amber?: boolean; headset?: boolean }) => {
    const g = new THREE.Group();
    g.position.set(x, 0, z);
    g.rotation.y = ry;
    scene.add(g);
    const scr = o.amber ? screens.amber : screens.blue;
    rbox(1.7, 0.05, 0.8, 0.02, M.deskTop, 0, 0.75, 0, g);
    box(0.04, 0.73, 0.04, M.metal, -0.8, 0.365, -0.35, g);
    box(0.04, 0.73, 0.04, M.metal, 0.8, 0.365, -0.35, g);
    box(0.04, 0.73, 0.04, M.metal, -0.8, 0.365, 0.35, g);
    box(0.04, 0.73, 0.04, M.metal, 0.8, 0.365, 0.35, g);
    const monitor = (mx: number, mz: number, rot = 0) => {
      const m = new THREE.Group();
      m.position.set(mx, 0, mz);
      m.rotation.y = rot;
      g.add(m);
      rbox(0.7, 0.42, 0.03, 0.012, M.metal, 0, 1.06, 0, m);
      const face = new THREE.Mesh(new THREE.PlaneGeometry(0.66, 0.38), scr);
      face.position.set(0, 1.06, 0.017);
      m.add(face);
      box(0.04, 0.24, 0.04, M.metal, 0, 0.87, -0.03, m);
      rbox(0.22, 0.015, 0.16, 0.007, M.metal, 0, 0.78, -0.02, m);
    };
    monitor(0, -0.25);
    if (o.two) monitor(0.72, -0.15, -0.35);
    rbox(0.42, 0.018, 0.14, 0.006, M.metal, 0, 0.785, 0.05, g);
    // Office chair
    const c = new THREE.Group();
    c.position.set(0, 0, 0.75);
    g.add(c);
    for (let i = 0; i < 5; i++) {
      const leg = box(0.03, 0.03, 0.3, M.metal, 0, 0.05, 0, c);
      leg.rotation.y = (i / 5) * Math.PI * 2;
      leg.translateZ(0.15);
    }
    cyl(0.025, 0.025, 0.38, M.metal, 0, 0.25, 0, c);
    rbox(0.5, 0.08, 0.48, 0.04, M.chair, 0, 0.48, 0.02, c);
    const back = rbox(0.46, 0.56, 0.06, 0.03, M.chair, 0, 0.86, 0.27, c);
    back.rotation.x = 0.1;
    if (!o.empty) mannequin(c, !!o.headset);
    const anchor = new THREE.Object3D();
    anchor.position.set(0, 2.15, 0.7);
    g.add(anchor);
    return anchor;
  };

  /* ------------------------------------------------------------ labels */
  const tags: { anchor: THREE.Object3D; el: HTMLDivElement }[] = [];
  const mk = (html: string, cls = "") => {
    const d = document.createElement("div");
    d.className = "floor-label " + cls;
    d.innerHTML = html;
    labels.appendChild(d);
    return d;
  };
  for (const a of AGENTS) {
    const anchor = station(a.x, a.z, a.ry, a);
    tags.push({ anchor, el: mk(`<span class="role"><i></i>${a.role}</span><b>${a.name}</b><span class="doing">${a.doing}</span>`) });
  }

  // Owner's glass office: empty chair, red VIP line.
  {
    const z = -29.5;
    box(0.05, 3, 4, M.glass, -2.4, 1.5, z).castShadow = false;
    box(0.05, 3, 4, M.glass, 2.4, 1.5, z).castShadow = false;
    box(4.8, 3, 0.05, M.glass, 0, 1.5, z + 2).castShadow = false;
    box(4.84, 0.06, 4.04, M.metal, 0, 3.0, z);
    const anchor = station(0, z - 0.2, Math.PI, { empty: true, amber: true });
    rbox(0.2, 0.05, 0.11, 0.02, M.red, 0.5, 0.8, z - 0.2);
    tags.push({
      anchor,
      el: mk(
        `<span class="role"><i></i>Not an agent</span><b>Your office</b><span class="doing">VIP calls skip the agents and ring straight through to you</span>`,
        "vip",
      ),
    });
  }

  /* ------------------------------------------------------------ camera and scroll */
  const path: V3[] = [
    [0, 1.65, 4],
    [0, 1.65, -4],
    [0, 1.7, -10],
    [0, 1.7, -15],
    [0, 1.7, -20],
    [0, 1.7, -24.5],
  ];
  const camAt = (t: number): V3 => {
    const n = path.length - 1;
    const f = t * n;
    const i = Math.min(n - 1, Math.floor(f));
    const k = f - i;
    const a = path[i];
    const b = path[i + 1];
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
  };
  const clamp = (x: number) => Math.max(0, Math.min(1, x));
  const v = new THREE.Vector3();

  const size = () => {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.fov = w < 700 ? 66 : 52;
    camera.updateProjectionMatrix();
  };

  function render() {
    const vh = window.innerHeight;
    const r = section.getBoundingClientRect();
    if (r.bottom < -vh || r.top > vh * 2) return; // off-screen: skip work
    const p = clamp(-r.top / (section.offsetHeight - vh));
    const pi = clamp(p / 0.86);
    const c = camAt(pi);
    camera.position.set(c[0] + Math.sin(pi * 9) * 0.25, c[1], c[2]);
    camera.lookAt(Math.sin(pi * 9) * 0.6, 1.3, c[2] - 6);
    renderer.render(scene, camera);

    const W = window.innerWidth;
    for (const t of tags) {
      t.anchor.getWorldPosition(v);
      const d = camera.position.z - v.z;
      v.project(camera);
      let vis = v.z < 1 && d > 1.2 && d < 11 ? Math.min(1, (d - 1.2) / 1.5) * Math.min(1, (11 - d) / 3) : 0;
      if (p < 0.04 || p > 0.88) vis = 0;
      const x = (v.x * 0.5 + 0.5) * W;
      const y = (-v.y * 0.5 + 0.5) * vh;
      t.el.style.opacity = String(vis);
      // Keep labels on screen; on phones the desks sit near the edges.
      const lw = t.el.offsetWidth;
      const lx = Math.max(8, Math.min(W - lw - 8, x - lw / 2));
      t.el.style.transform = `translate(${lx}px,${y - t.el.offsetHeight - 26}px)`;
    }
    intro.style.opacity = String(1 - clamp(p / 0.08));
    outro.style.opacity = String(clamp((p - 0.88) / 0.07));
  }

  let ticking = false;
  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      render();
    });
  };
  const onResize = () => {
    size();
    render();
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onResize);
  size();
  render();

  return () => {
    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("resize", onResize);
    labels.innerHTML = "";
    envTex.dispose();
    pmrem.dispose();
    renderer.dispose();
  };
}

/** A glowing monitor face with a tiny chat UI on it, so the desks read as "working". */
function screenMaterial(kind: "blue" | "amber") {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 296;
  const g = c.getContext("2d")!;
  const bg = kind === "blue" ? "#0F1B33" : "#1F160A";
  const accent = kind === "blue" ? "#5B8DEF" : "#F2A33A";
  g.fillStyle = bg;
  g.fillRect(0, 0, c.width, c.height);
  g.fillStyle = "rgba(255,255,255,.06)";
  g.fillRect(0, 0, 130, c.height);
  for (let i = 0; i < 6; i++) {
    g.fillStyle = i === 1 ? accent : "rgba(255,255,255,.14)";
    g.fillRect(16, 24 + i * 42, 98, 22);
  }
  const bubble = (x: number, y: number, w: number, fill: string) => {
    g.fillStyle = fill;
    g.beginPath();
    g.roundRect(x, y, w, 34, 10);
    g.fill();
  };
  bubble(150, 26, 220, "rgba(255,255,255,.18)");
  bubble(250, 76, 240, accent);
  bubble(150, 126, 170, "rgba(255,255,255,.18)");
  bubble(290, 176, 200, accent);
  g.fillStyle = "rgba(255,255,255,.1)";
  g.fillRect(150, 244, 340, 30);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return new THREE.MeshStandardMaterial({ map: t, emissive: 0xffffff, emissiveMap: t, emissiveIntensity: 0.9, roughness: 0.3 });
}
