// Build a recipe (recipe.js) into a three.js model (docs/local-renderer.md).
//
//   const model = buildModel(THREE, recipe, seed);
//   scene.add(model.group); model.update(timeSeconds); model.setOpacity(0.5); model.dispose();
//   model.size  -> {w, h, d} of the unanimated model in recipe units
//
// Every shape is a unit geometry (1 x 1 x 1, standing on y = 0, centred on x and z), scaled to the part's
// size, so parts stack by their `pos[1]` exactly as Gemini is told. Rotations and part animations turn a
// part about its own centre (a pivot half its height above `pos`). Flat-shaded standard materials give
// the low-poly painted-miniature look; `glow` parts are emissive and skip tone mapping so flames and
// lit windows stay bright under the colour grade. `THREE` is passed in so this file never fetches it.

import { expandParts } from "./recipe.js";

const unitCache = new WeakMap(); // THREE -> Map(shape -> geometry)

function unitGeometry(THREE, shape) {
  let cache = unitCache.get(THREE);
  if (!cache) unitCache.set(THREE, (cache = new Map()));
  if (cache.has(shape)) return cache.get(shape);
  let g;
  switch (shape) {
    case "box": g = new THREE.BoxGeometry(1, 1, 1); break;
    case "cylinder": g = new THREE.CylinderGeometry(0.5, 0.5, 1, 14); break;
    case "cone": g = new THREE.ConeGeometry(0.5, 1, 14); break;
    case "sphere": g = new THREE.SphereGeometry(0.5, 14, 10); break;
    case "dome": g = new THREE.SphereGeometry(0.5, 14, 7, 0, Math.PI * 2, 0, Math.PI / 2); break;
    case "pyramid": g = new THREE.ConeGeometry(0.5, 1, 4); g.rotateY(Math.PI / 4); break;
    case "torus": g = new THREE.TorusGeometry(0.38, 0.12, 8, 18); g.rotateX(Math.PI / 2); break;
    case "wedge": g = new THREE.CylinderGeometry(0.5, 0.5, 1, 3); g.rotateZ(Math.PI / 2); g.rotateX(-Math.PI / 2); break; // roof prism: ridge along x, apex up
    case "capsule": g = new THREE.CapsuleGeometry(0.3, 0.4, 4, 10); break;
    default: g = new THREE.BoxGeometry(1, 1, 1);
  }
  // Normalise to exactly 1 x 1 x 1 with the base on y = 0.
  g.computeBoundingBox();
  const b = g.boundingBox;
  g.translate(-(b.min.x + b.max.x) / 2, -b.min.y, -(b.min.z + b.max.z) / 2);
  g.scale(1 / Math.max(b.max.x - b.min.x, 1e-6), 1 / Math.max(b.max.y - b.min.y, 1e-6), 1 / Math.max(b.max.z - b.min.z, 1e-6));
  g.computeBoundingBox();
  cache.set(shape, g);
  return g;
}

const MATERIAL = {
  stone: { roughness: 0.92, metalness: 0 },
  wood: { roughness: 0.85, metalness: 0 },
  metal: { roughness: 0.42, metalness: 0.65 },
  gold: { roughness: 0.32, metalness: 0.85 },
  cloth: { roughness: 0.95, metalness: 0, side: "double" },
  leaf: { roughness: 0.88, metalness: 0 },
  scale: { roughness: 0.6, metalness: 0.1 },
  crystal: { roughness: 0.12, metalness: 0.1, opacity: 0.82, emissive: 0.25 },
  water: { roughness: 0.15, metalness: 0.1, opacity: 0.85 },
  glow: { roughness: 1, metalness: 0, emissive: 1.6, glow: true },
};

function makeMaterial(THREE, colour, kind) {
  const spec = MATERIAL[kind] ?? MATERIAL.stone;
  const c = new THREE.Color(colour);
  const mat = new THREE.MeshStandardMaterial({
    color: c, roughness: spec.roughness, metalness: spec.metalness, flatShading: true,
    side: spec.side === "double" ? THREE.DoubleSide : THREE.FrontSide,
  });
  if (spec.emissive) { mat.emissive = c.clone(); mat.emissiveIntensity = spec.emissive; }
  if (spec.glow) mat.toneMapped = false;
  mat.userData.baseOpacity = spec.opacity ?? 1;
  if (spec.opacity) { mat.transparent = true; mat.opacity = spec.opacity; }
  return mat;
}

const DEG = Math.PI / 180;

/** Pure: stable phase for part `i` of a model seeded `seed`. */
export function phaseFor(seed, i) {
  return ((Math.sin((seed + 1) * 12.9898 + i * 78.233) * 43758.5453) % 1 + 1) % 1 * Math.PI * 2;
}

export function buildModel(THREE, recipe, seed = 0) {
  const group = new THREE.Group();
  const inner = new THREE.Group(); // whole-model animation happens here, so placement stays on `group`
  group.add(inner);
  const materials = new Map();
  const animated = [];

  expandParts(recipe).forEach((p, i) => {
    const key = `${p.colour}|${p.material}`;
    if (!materials.has(key)) materials.set(key, makeMaterial(THREE, p.colour, p.material));
    const mat = p.anim === "flicker" ? makeMaterial(THREE, p.colour, p.material) : materials.get(key);
    if (p.anim === "flicker") materials.set(`${key}|${i}`, mat);
    const geometry = new THREE.Mesh(unitGeometry(THREE, p.shape), mat);
    geometry.scale.set(p.size[0], p.size[1], p.size[2]);
    geometry.position.y = -p.size[1] / 2;
    const mesh = new THREE.Group(); // the pivot, at the part's centre
    mesh.add(geometry);
    mesh.position.set(p.pos[0], p.pos[1] + p.size[1] / 2, p.pos[2]);
    const [rx, ry, rz] = p.rot ?? [0, 0, 0];
    mesh.rotation.set(rx * DEG, ry * DEG + (p.rotY ?? 0), rz * DEG);
    mesh.userData.material = mat;
    inner.add(mesh);
    if (p.anim) {
      animated.push({
        mesh, anim: p.anim, phase: phaseFor(seed, i),
        pos: mesh.position.clone(), rot: mesh.rotation.clone(), scale: mesh.scale.clone(),
        side: Math.sign(p.pos[2] || p.pos[0] || 1),
      });
    }
  });

  const box = new THREE.Box3().setFromObject(inner);
  const size = {
    w: Math.max(box.max.x - box.min.x, 0.05),
    h: Math.max(box.max.y, 0.05),
    d: Math.max(box.max.z - box.min.z, 0.05),
  };
  const centreX = (box.min.x + box.max.x) / 2, centreZ = (box.min.z + box.max.z) / 2;
  inner.position.set(-centreX, 0, -centreZ); // the model's footprint is centred on the group origin
  const base = inner.position.clone();
  const modelPhase = phaseFor(seed, 999);
  let opacity = 1;

  return {
    group,
    size,
    recipe,
    update(t) {
      const ph = modelPhase;
      inner.position.copy(base);
      inner.rotation.set(0, 0, 0);
      inner.scale.set(1, 1, 1);
      switch (recipe.animation) {
        case "bob": inner.position.y = base.y + Math.sin(t * 2.2 + ph) * 0.02; break;
        case "spin": inner.rotation.y = t * 0.4; break;
        case "sway": inner.rotation.z = Math.sin(t * 1.3 + ph) * 0.03; break;
        case "breathe": inner.scale.set(1 + Math.sin(t * 1.8 + ph) * 0.015, 1 + Math.sin(t * 1.8 + ph) * 0.03, 1); break;
        default: break;
      }
      for (const a of animated) {
        const { mesh } = a;
        const s = t + a.phase;
        if (a.anim === "spin") mesh.rotation.y = a.rot.y + t * 2.5;
        else if (a.anim === "bob") mesh.position.y = a.pos.y + Math.sin(s * 3) * 0.025;
        else if (a.anim === "sway") mesh.rotation.z = a.rot.z + Math.sin(s * 2.4) * 0.18;
        else if (a.anim === "flap") mesh.rotation.x = a.rot.x + Math.sin(s * 5) * 0.5 * a.side;
        else if (a.anim === "pulse") mesh.scale.copy(a.scale).multiplyScalar(1 + Math.sin(s * 3.2) * 0.08);
        else if (a.anim === "flicker") {
          const n = 0.5 + 0.3 * Math.sin(s * 17) + 0.2 * Math.sin(s * 29.7);
          mesh.scale.set(a.scale.x * (0.92 + 0.12 * n), a.scale.y * (0.8 + 0.35 * n), a.scale.z * (0.92 + 0.12 * n));
          const m = mesh.userData.material;
          if (m?.emissive) m.emissiveIntensity = 1.2 + 0.9 * n;
        }
      }
    },
    setOpacity(o) {
      if (Math.abs(o - opacity) < 0.005) return;
      opacity = o;
      for (const m of materials.values()) {
        const base = m.userData.baseOpacity ?? 1;
        m.transparent = o < 1 || base < 1;
        m.opacity = base * o;
        m.depthWrite = o >= 1;
      }
    },
    dispose() {
      for (const m of materials.values()) m.dispose();
      group.removeFromParent();
    },
  };
}
