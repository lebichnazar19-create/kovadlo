// Головний потік вкладки "Будівництво": ліниво піднімає один спільний
// Worker (перший виклик build* — не при завантаженні сторінки) і
// повертає готовий THREE.Mesh/Group з "сирих" даних сітки, за тим самим
// патерном, що й web/static/js/parts/parts-viewer.js. Використовує
// ГЛОБАЛЬНИЙ window.THREE (той самий CDN-скрипт, що вже підключений у
// index.html) — не бандлить/не імпортує three.
//
// Усі три build* повертають геометрію в АБСОЛЮТНИХ світових мм (той
// самий Y-вгору, без дзеркалення осей, що й /api/scene3d) — тому єдине,
// що тут потрібно, це масштаб ×0.001 у метри (сцена завжди в метрах,
// див. CLAUDE.md); ні позиції, ні повороту застосовувати НЕ треба.
import { syncFaces, syncLines } from "replicad-threejs-helper";

const EDGE_MATERIAL = new THREE.LineBasicMaterial({ color: 0x14161a });
const MM_TO_M = 0.001;

let worker = null;
let workerReady = null;
let nextRequestId = 1;

function ensureGeometryWorker(onStatus) {
  if (worker) return workerReady;
  worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
  workerReady = new Promise((resolve, reject) => {
    worker.addEventListener("message", (event) => {
      const msg = event.data;
      if (msg.type === "ready") resolve();
      else if (msg.type === "error" && msg.requestId === undefined) {
        onStatus?.("Помилка ініціалізації OpenCascade: " + msg.message);
        reject(new Error(msg.message));
      }
    });
    worker.addEventListener("error", (e) => reject(e));
  });
  onStatus?.("Завантаження OpenCascade для геометрії Будівництва…");
  return workerReady;
}

function requestBuild(kind, spec) {
  const requestId = nextRequestId++;
  return new Promise((resolve, reject) => {
    function onMessage(event) {
      const msg = event.data;
      if (msg.requestId !== requestId) return;
      worker.removeEventListener("message", onMessage);
      if (msg.type === "result") resolve(msg);
      else if (msg.type === "error") reject(new Error(msg.message));
    }
    worker.addEventListener("message", onMessage);
    worker.postMessage({ type: "build", kind, requestId, spec });
  });
}

// Плоска UV-проєкція: `project(x,y,z) -> [u,v]` рахується на СИРИХ
// світових мм-координатах вершини (до масштабування групи в метри).
function attachUV(geometry, project) {
  const position = geometry.getAttribute("position");
  const uv = new Float32Array((position.count) * 2);
  for (let i = 0; i < position.count; i++) {
    const [u, v] = project(position.getX(i), position.getY(i), position.getZ(i));
    uv[i * 2] = u;
    uv[i * 2 + 1] = v;
  }
  geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
}

function meshAndEdgesGroup(faces, edges, material, uvProject) {
  const faceGeometry = new THREE.BufferGeometry();
  syncFaces(faceGeometry, faces);
  if (uvProject) attachUV(faceGeometry, uvProject);
  const mesh = new THREE.Mesh(faceGeometry, material);

  const edgeGeometry = new THREE.BufferGeometry();
  syncLines(edgeGeometry, edges);
  const lines = new THREE.LineSegments(edgeGeometry, EDGE_MATERIAL);

  const group = new THREE.Group();
  group.add(mesh);
  group.add(lines);
  group.scale.setScalar(MM_TO_M); // єдине місце переведення мм → м для всієї геометрії Будівництва
  return { group, mesh };
}

/**
 * `{ onStatus }` — колбек про стан завантаження/помилки воркера (той
 * самий стиль, що й createPartsController). Повертає `{ buildTube,
 * buildFloor, buildWall }` — усі три діляться ОДНИМ Worker/WASM.
 */
export function createGeometryController({ onStatus } = {}) {
  async function build(kind, spec) {
    await ensureGeometryWorker(onStatus);
    return requestBuild(kind, spec);
  }

  /**
   * `{ points, diameterMm, color }` → `{ group, mesh, pathLengthMm }`.
   * Одна функція для труби/кабелю/арматури — різняться лише diameterMm і
   * color, геометрія (web/static/js/geometry/tube.js::sweepTube) та сама.
   * `points` — масив `{x,y,z}` у мм, щонайменше 2 точки.
   */
  async function buildTube({ points, diameterMm, color = 0x888888 }) {
    const { faces, edges, pathLengthMm } = await build("tube", { points, diameterMm });
    const material = new THREE.MeshLambertMaterial({ color });
    const { group, mesh } = meshAndEdgesGroup(faces, edges, material, null);
    group.userData.pathLengthMm = pathLengthMm;
    return { group, mesh };
  }

  /**
   * `{ contour, thicknessMm, color }` → `{ group, mesh, areaMm2 }`.
   * `contour` — масив `[x, z]` у мм (контур кімнати, room.contour).
   * UV нормалізовано на bounding box контуру — та сама розкладка, що
   * колишній THREE-варіант рахував через boundsOfPoints.
   */
  async function buildFloor({ contour, thicknessMm, color = 0xd9d2c7 }) {
    const { faces, edges, areaMm2 } = await build("floor", { contour, thicknessMm });
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
    for (const [x, z] of contour) {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minZ = Math.min(minZ, z); maxZ = Math.max(maxZ, z);
    }
    const widthMm = Math.max(1, maxX - minX);
    const depthMm = Math.max(1, maxZ - minZ);
    const material = new THREE.MeshLambertMaterial({ color });
    const uvProject = (x, _y, z) => [(x - minX) / widthMm, (z - minZ) / depthMm];
    const { group, mesh } = meshAndEdgesGroup(faces, edges, material, uvProject);
    group.userData.areaMm2 = areaMm2;
    return { group, mesh };
  }

  /**
   * `{ wallData, color }` → `{ group, mesh, netAreaMm2 }`.
   * `wallData` — та сама форма, що передавалась у колишній buildWallMesh
   * (`start`/`end` — `[x,z]` у мм, `height_mm`, `openings`, ...). UV
   * нормалізовано на (довжина стіни × висота) — та сама розкладка, що
   * колишній THREE-варіант отримував від Shape задарма.
   */
  async function buildWall({ wallData, color = 0xcccccc }) {
    const { faces, edges, netAreaMm2 } = await build("wall", { wallData });
    const [x0, z0] = wallData.start;
    const [x1, z1] = wallData.end;
    const lengthMm = wallData.length_mm;
    const heightMm = wallData.height_mm;
    const dirX = (x1 - x0) / lengthMm;
    const dirZ = (z1 - z0) / lengthMm;
    const material = new THREE.MeshLambertMaterial({ color });
    const uvProject = (x, y, z) => [((x - x0) * dirX + (z - z0) * dirZ) / lengthMm, y / heightMm];
    const { group, mesh } = meshAndEdgesGroup(faces, edges, material, uvProject);
    group.userData.netAreaMm2 = netAreaMm2;
    return { group, mesh };
  }

  return { buildTube, buildFloor, buildWall };
}
