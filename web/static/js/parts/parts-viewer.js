// Головний потік вкладки "Деталі": керує Worker'ом (worker.js — важка
// частина, OpenCascade), будує THREE-геометрію з готових даних сітки,
// малює сцену. THREE.js тут — ГЛОБАЛЬНИЙ `window.THREE` (той самий
// CDN-скрипт, що вже підключений для "Будівництва"/"Механізмів" у
// index.html), а не окремий імпорт — не дублюємо three.js другий раз
// у цьому бандлі.
//
// Offline/APK: сам this bundle і worker.js (з replicad+OpenCascade
// WASM) роздаються локальним Python-сервером (web/server.py) з
// web/static/dist/parts/ — жодного звернення в мережу, CDN тут лише
// для three.js (той самий, що й для решти застосунку).
import { syncFaces, syncLines } from "replicad-threejs-helper";
import { BEARING_CATALOG, DEFAULT_BALL_COUNT } from "./bearing.js";

const RING_MATERIAL = new THREE.MeshStandardMaterial({ color: 0x888c92, metalness: 0.4, roughness: 0.55 });
const BALL_MATERIAL = new THREE.MeshStandardMaterial({ color: 0xe4e7eb, metalness: 0.6, roughness: 0.2 });
const EDGE_MATERIAL = new THREE.LineBasicMaterial({ color: 0x14161a });

let worker = null;
let workerReady = null; // Promise, що резолвиться, коли worker відповість {type:"ready"}
let nextRequestId = 1;
let pendingRequestId = null; // остання надіслана вимога — старіші відповіді ігноруються

// Worker (і, разом з ним, завантаження WASM OpenCascade) створюється
// лише один раз, при першому виклику — тобто лише коли користувач
// реально відкриє вкладку "Деталі", а не при завантаженні сторінки.
function ensurePartsWorker(onStatus) {
  if (worker) return workerReady;

  worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
  workerReady = new Promise((resolve, reject) => {
    worker.addEventListener("message", (event) => {
      const msg = event.data;
      if (msg.type === "ready") {
        resolve();
      } else if (msg.type === "error" && msg.requestId === undefined) {
        // помилка самої ініціалізації (ще до першого запиту)
        onStatus?.("Помилка ініціалізації OpenCascade: " + msg.message);
        reject(new Error(msg.message));
      }
    });
    worker.addEventListener("error", (e) => reject(e));
  });
  onStatus?.("Завантаження OpenCascade (перший раз може зайняти кілька секунд)…");
  return workerReady;
}

function requestBearing(spec) {
  const requestId = nextRequestId++;
  pendingRequestId = requestId;
  return new Promise((resolve, reject) => {
    function onMessage(event) {
      const msg = event.data;
      if (msg.requestId !== requestId) return; // застаріла чи чужа відповідь
      worker.removeEventListener("message", onMessage);
      if (requestId !== pendingRequestId) return; // користувач вже обрав щось інше — відкидаємо
      if (msg.type === "result") resolve(msg);
      else if (msg.type === "error") reject(new Error(msg.message));
    }
    worker.addEventListener("message", onMessage);
    worker.postMessage({ type: "build", requestId, spec });
  });
}

function meshToThreeMesh(part, material) {
  const geometry = new THREE.BufferGeometry();
  syncFaces(geometry, part.faces);
  return new THREE.Mesh(geometry, material);
}

function meshToThreeEdges(part) {
  const geometry = new THREE.BufferGeometry();
  syncLines(geometry, part.edges);
  return new THREE.LineSegments(geometry, EDGE_MATERIAL);
}

function partsToGroup(parts) {
  const group = new THREE.Group();
  for (const part of parts) {
    if (part.kind === "ring") {
      group.add(meshToThreeMesh(part, RING_MATERIAL));
      group.add(meshToThreeEdges(part));
    } else {
      group.add(meshToThreeMesh(part, BALL_MATERIAL));
    }
  }
  return group;
}

export function createPartsController({ scene3dLike, onStatus }) {
  let currentGroup = null;

  function disposeGroup(group) {
    if (!group) return;
    group.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
    });
  }

  async function load(code) {
    const spec = { ...BEARING_CATALOG[code], ballCount: DEFAULT_BALL_COUNT };
    onStatus(`Будую ${code} (${spec.d}/${spec.D}/${spec.B})…`);
    try {
      await ensurePartsWorker(onStatus);
      const { parts, elapsedMs } = await requestBearing(spec);
      if (currentGroup) {
        scene3dLike.scene.remove(currentGroup);
        disposeGroup(currentGroup);
      }
      currentGroup = partsToGroup(parts);
      scene3dLike.scene.add(currentGroup);
      onStatus(
        `${code}: d=${spec.d} D=${spec.D} B=${spec.B} мм, ${spec.ballCount} куль — ` +
          `згенеровано за ${elapsedMs.toFixed(1)} мс`
      );
    } catch (e) {
      console.error(e);
      onStatus("Помилка: " + e.message);
    }
  }

  return { load, catalog: BEARING_CATALOG };
}
