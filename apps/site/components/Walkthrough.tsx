"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Scroll-driven walk down a stylised dealership floor (ported from design/mockups/landing.html).
 *
 * Differences from the mockup, on purpose:
 * - It is a section further down the page, not a 900vh gate in front of the value proposition.
 * - three.js is loaded only when the section comes near the viewport, so it costs nothing for
 *   visitors who never scroll this far and doesn't hurt first paint.
 * - Visitors with reduced motion or no WebGL skip it; the agent grid below carries the same content.
 * - The back-wall sign says "Your dealership", not the pilot dealer's name (needs their permission).
 */

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
  cloth?: "a" | "b" | "c";
  skin?: "a" | "b" | "c";
};

const AGENTS: Agent[] = [
  { x: -3.2, z: -12, ry: Math.PI / 2, role: "Voice agent", name: "Reception", doing: "Answering a call about a black G63", headset: true, skin: "a" },
  { x: 3.2, z: -12.5, ry: -Math.PI / 2, role: "Messaging agent", name: "WhatsApp and email", doing: "Replying to a buyer in Lagos with photos", two: true, cloth: "b", skin: "c" },
  { x: -3.2, z: -17, ry: Math.PI / 2, role: "Booking agent", name: "Test drives and visits", doing: "Booking a video walkaround for Thursday", amber: true, cloth: "c", skin: "b" },
  { x: 3.2, z: -17.5, ry: -Math.PI / 2, role: "Service agent", name: "Service desk", doing: "Fitting an oil change into Bay 2", headset: true, skin: "b" },
  { x: -3.2, z: -22, ry: Math.PI / 2, role: "Routing agent", name: "Handoffs", doing: "Sending a qualified buyer to Daniel in Sales", two: true, cloth: "b", skin: "a" },
  { x: 3.2, z: -22.5, ry: -Math.PI / 2, role: "Follow-up agent", name: "Follow-ups", doing: "Drafting nudges for buyers who went quiet", amber: true, cloth: "a", skin: "c" },
];

function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

export default function Walkthrough() {
  const sectionRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const introRef = useRef<HTMLDivElement>(null);
  const outroRef = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setEnabled(!reduce && webglAvailable());
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const section = sectionRef.current!;
    let cleanup: (() => void) | undefined;
    let cancelled = false;

    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        import("three").then((THREE) => {
          if (cancelled) return;
          cleanup = mountScene(THREE, {
            section,
            canvas: canvasRef.current!,
            labels: labelsRef.current!,
            intro: introRef.current!,
            outro: outroRef.current!,
          });
        });
      },
      { rootMargin: "800px 0px" },
    );
    io.observe(section);

    return () => {
      cancelled = true;
      io.disconnect();
      cleanup?.();
    };
  }, [enabled]);

  if (!enabled) return null;

  return (
    <section ref={sectionRef} id="walkthrough" aria-label="Walk the dealership floor" className="relative h-[480vh] bg-paper">
      <div className="sticky top-0 h-svh overflow-hidden bg-[#DCD7CE]">
        <canvas
          ref={canvasRef}
          className="block h-full w-full"
          aria-label="Inside the dealership: desks staffed by AI agents answering and routing calls and messages"
        />
        <div ref={labelsRef} aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden" />
        <div ref={introRef} className="pointer-events-none absolute inset-x-0 top-[14vh] mx-auto max-w-[1200px] px-6 text-ink">
          <p className="eyebrow text-muted">The floor</p>
          <h2 className="x mt-3 max-w-[14ch] text-[clamp(32px,5vw,64px)] font-bold leading-[1] tracking-[-0.015em]">
            Walk in. Every desk is staffed.
          </h2>
          <p className="mt-4 text-[13px] text-muted">Keep scrolling</p>
        </div>
        <div
          ref={outroRef}
          className="absolute inset-0 flex flex-col items-center justify-center bg-paper/85 px-6 text-center text-ink opacity-0"
        >
          <h2 className="x max-w-[16ch] text-[clamp(32px,5.2vw,68px)] font-bold leading-[1] tracking-[-0.015em]">
            None of them are people. All of them are on your side.
          </h2>
          <p className="mt-4 max-w-[46ch] text-[18px] text-ink-2">
            Ondra&apos;s agents answer, book and route. Your team takes the handoffs that need a person.
          </p>
        </div>
      </div>
    </section>
  );
}

type Els = {
  section: HTMLElement;
  canvas: HTMLCanvasElement;
  labels: HTMLDivElement;
  intro: HTMLDivElement;
  outro: HTMLDivElement;
};

function mountScene(THREE: typeof import("three"), els: Els) {
  const { section, canvas, labels, intro, outro } = els;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.92;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xdcd7ce);
  scene.fog = new THREE.Fog(0xdcd7ce, 22, 44);
  const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 100);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xb9b1a4, 1.6));
  const sun = new THREE.DirectionalLight(0xfff3e2, 2.2);
  sun.position.set(6, 12, 4);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -10, right: 10, top: 20, bottom: -20, far: 60 });
  sun.target.position.set(0, 0, -14);
  scene.add(sun, sun.target);

  const mat = (c: number, r = 0.8, m = 0) => new THREE.MeshStandardMaterial({ color: c, roughness: r, metalness: m });
  const M = {
    floor: mat(0xd7d3cc, 0.9),
    wall: mat(0xf1efeb, 0.95),
    desk: mat(0x8a6a50, 0.55),
    leg: mat(0x2b2c30, 0.5, 0.4),
    chair: mat(0x2f3136, 0.7),
    skin: { a: mat(0x8d5a3b, 0.7), b: mat(0xc68e62, 0.7), c: mat(0xe0b899, 0.7) },
    cloth: { a: mat(0x1f2a3d, 0.85), b: mat(0xf2f0ec, 0.85), c: mat(0x6b2e2e, 0.85) },
    screen: new THREE.MeshStandardMaterial({ color: 0x1d2533, emissive: 0x5b8def, emissiveIntensity: 0.55, roughness: 0.4 }),
    screenA: new THREE.MeshStandardMaterial({ color: 0x2a2215, emissive: 0xf2a33a, emissiveIntensity: 0.6, roughness: 0.4 }),
    car: mat(0x131417, 0.25, 0.7),
    carB: mat(0xe8e6e1, 0.25, 0.5),
    tyre: mat(0x111111, 0.9),
    glassC: mat(0x1e2530, 0.15, 0.6),
    glass: new THREE.MeshStandardMaterial({ color: 0xbfd6e6, transparent: true, opacity: 0.18, roughness: 0.05, metalness: 0.1 }),
    strip: new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xfff4e0, emissiveIntensity: 1 }),
    red: new THREE.MeshStandardMaterial({ color: 0xd93a3f, emissive: 0xd93a3f, emissiveIntensity: 0.8 }),
  };

  type Parent = import("three").Object3D;
  const box = (w: number, h: number, d: number, m: import("three").Material, x: number, y: number, z: number, par: Parent = scene) => {
    const o = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    o.position.set(x, y, z);
    o.castShadow = o.receiveShadow = true;
    par.add(o);
    return o;
  };
  const cyl = (rt: number, rb: number, h: number, m: import("three").Material, x: number, y: number, z: number, par: Parent = scene, seg = 20) => {
    const o = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), m);
    o.position.set(x, y, z);
    o.castShadow = true;
    par.add(o);
    return o;
  };

  // Room
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(16, 46), M.floor);
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(0, 0, -16);
  floor.receiveShadow = true;
  scene.add(floor);
  box(0.2, 4.2, 46, M.wall, -7, 2.1, -16);
  box(0.2, 4.2, 46, M.wall, 7, 2.1, -16);
  box(14, 4.2, 0.2, M.wall, 0, 2.1, -36);
  for (let z = -2; z > -34; z -= 4) {
    box(0.12, 0.05, 2.6, M.strip, -2.2, 3.9, z).castShadow = false;
    box(0.12, 0.05, 2.6, M.strip, 2.2, 3.9, z).castShadow = false;
  }

  // Back-wall sign
  {
    const c = document.createElement("canvas");
    c.width = 1024;
    c.height = 200;
    const g = c.getContext("2d")!;
    const draw = () => {
      g.clearRect(0, 0, c.width, c.height);
      g.fillStyle = "#16171B";
      g.font = "700 88px Archivo, Arial, sans-serif";
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText("Your Dealership", 512, 100);
    };
    draw();
    const t = new THREE.CanvasTexture(c);
    // Redraw once Archivo has loaded so the sign doesn't stay in the fallback font.
    document.fonts?.ready.then(() => {
      draw();
      t.needsUpdate = true;
      render();
    });
    t.colorSpace = THREE.SRGBColorSpace;
    const p = new THREE.Mesh(new THREE.PlaneGeometry(5, 1), new THREE.MeshBasicMaterial({ map: t, transparent: true }));
    p.position.set(0, 3.2, -35.85);
    scene.add(p);
  }

  // Showroom cars
  const car = (x: number, z: number, ry: number, m: import("three").Material) => {
    const g = new THREE.Group();
    g.position.set(x, 0, z);
    g.rotation.y = ry;
    scene.add(g);
    box(1.9, 0.62, 4.4, m, 0, 0.6, 0, g);
    box(1.62, 0.55, 2.3, m, 0, 1.18, -0.2, g);
    box(1.64, 0.45, 0.06, M.glassC, 0, 1.18, 0.97, g);
    box(1.64, 0.45, 0.06, M.glassC, 0, 1.18, -1.37, g);
    for (const [wx, wz] of [[-0.95, 1.4], [0.95, 1.4], [-0.95, -1.4], [0.95, -1.4]]) {
      cyl(0.36, 0.36, 0.28, M.tyre, wx, 0.36, wz, g, 24).rotation.z = Math.PI / 2;
    }
  };
  car(-3.8, -3.2, 0.35, M.car);
  car(3.8, -4.2, -0.4, M.carB);
  car(-4.0, -8.4, 0.25, M.carB);

  const person = (g: Parent, cloth: import("three").Material, headset: boolean, skin: import("three").Material) => {
    const p = new THREE.Group();
    g.add(p);
    const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.2, 0.42, 6, 12), cloth);
    torso.position.set(0, 1.05, 0);
    torso.rotation.x = -0.08;
    torso.castShadow = true;
    p.add(torso);
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.13, 20, 16), skin);
    head.position.set(0, 1.55, -0.03);
    head.castShadow = true;
    p.add(head);
    box(0.36, 0.13, 0.46, cloth, 0, 0.6, -0.18, p);
    box(0.14, 0.5, 0.14, cloth, -0.1, 0.32, -0.42, p);
    box(0.14, 0.5, 0.14, cloth, 0.1, 0.32, -0.42, p);
    const a1 = new THREE.Mesh(new THREE.CapsuleGeometry(0.055, 0.34, 4, 8), cloth);
    a1.position.set(-0.25, 1.02, -0.2);
    a1.rotation.x = 1.1;
    p.add(a1);
    const a2 = a1.clone();
    a2.position.x = 0.25;
    p.add(a2);
    if (headset) {
      const h = new THREE.Mesh(new THREE.TorusGeometry(0.14, 0.018, 8, 24, Math.PI), M.leg);
      h.position.set(0, 1.57, -0.03);
      h.rotation.y = Math.PI / 2;
      p.add(h);
      box(0.02, 0.02, 0.12, M.leg, 0.12, 1.48, -0.12, p);
    }
    return p;
  };

  const station = (
    x: number,
    z: number,
    ry: number,
    o: { empty?: boolean; two?: boolean; amber?: boolean; headset?: boolean; cloth?: import("three").Material; skin?: import("three").Material },
  ) => {
    const g = new THREE.Group();
    g.position.set(x, 0, z);
    g.rotation.y = ry;
    scene.add(g);
    const screen = o.amber ? M.screenA : M.screen;
    box(1.7, 0.05, 0.8, M.desk, 0, 0.75, 0, g);
    box(0.05, 0.73, 0.7, M.leg, -0.8, 0.37, 0, g);
    box(0.05, 0.73, 0.7, M.leg, 0.8, 0.37, 0, g);
    box(0.66, 0.4, 0.04, screen, 0, 1.05, -0.25, g);
    box(0.05, 0.22, 0.05, M.leg, 0, 0.86, -0.27, g);
    if (o.two) box(0.66, 0.4, 0.04, screen, 0.7, 1.05, -0.15, g).rotation.y = -0.35;
    box(0.42, 0.02, 0.14, M.leg, 0, 0.785, 0.05, g);
    const c = new THREE.Group();
    c.position.set(0, 0, 0.75);
    g.add(c);
    cyl(0.03, 0.03, 0.42, M.leg, 0, 0.21, 0, c);
    box(0.5, 0.08, 0.5, M.chair, 0, 0.46, 0, c);
    box(0.5, 0.62, 0.08, M.chair, 0, 0.85, 0.25, c);
    if (!o.empty) person(c, o.cloth ?? M.cloth.a, !!o.headset, o.skin ?? M.skin.a).position.z = -0.02;
    const anchor = new THREE.Object3D();
    anchor.position.set(0, 2.15, 0.7);
    g.add(anchor);
    return anchor;
  };

  const tags: { anchor: import("three").Object3D; el: HTMLDivElement }[] = [];
  const mk = (html: string, cls = "") => {
    const d = document.createElement("div");
    d.className = "floor-label " + cls;
    d.innerHTML = html;
    labels.appendChild(d);
    return d;
  };
  for (const a of AGENTS) {
    const anchor = station(a.x, a.z, a.ry, {
      two: a.two,
      amber: a.amber,
      headset: a.headset,
      cloth: M.cloth[a.cloth ?? "a"],
      skin: M.skin[a.skin ?? "a"],
    });
    tags.push({
      anchor,
      el: mk(`<span class="role"><i></i>${a.role}</span><b>${a.name}</b><span class="doing">${a.doing}</span>`),
    });
  }

  // Owner's glass office: empty chair, red VIP line
  {
    const z = -29.5;
    box(0.06, 3, 4, M.glass, -2.4, 1.5, z);
    box(0.06, 3, 4, M.glass, 2.4, 1.5, z);
    box(4.8, 3, 0.06, M.glass, 0, 1.5, z + 2);
    const anchor = station(0, z - 0.2, Math.PI, { empty: true, amber: true });
    box(0.18, 0.05, 0.1, M.red, 0.5, 0.79, z - 0.2);
    tags.push({
      anchor,
      el: mk(
        `<span class="role"><i></i>Not an agent</span><b>Your office</b><span class="doing">VIP calls skip the agents and ring straight through to you</span>`,
        "vip",
      ),
    });
  }

  const path: [number, number, number][] = [
    [0, 1.65, 4],
    [0, 1.65, -4],
    [0, 1.7, -10],
    [0, 1.7, -15],
    [0, 1.7, -20],
    [0, 1.7, -24.5],
  ];
  const camAt = (t: number) => {
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

  const render = () => {
    const vh = window.innerHeight;
    const r = section.getBoundingClientRect();
    if (r.bottom < -vh || r.top > vh * 2) return; // off-screen: skip work
    const p = clamp(-r.top / (section.offsetHeight - vh));
    const pi = clamp(p / 0.86);
    const c = camAt(pi);
    camera.position.set(c[0] + Math.sin(pi * 9) * 0.25, c[1], c[2]);
    camera.lookAt(Math.sin(pi * 9) * 0.6, 1.35, c[2] - 6);
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
  };

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
    renderer.dispose();
  };
}
