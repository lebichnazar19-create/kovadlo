// Web Worker: усе важке (ініціалізація OpenCascade WASM, побудова тіла,
// тесселяція) виконується тут, поза головним потоком — вкладка "Деталі"
// не має підвисати браузер під час розрахунку. Головний потік отримує
// назад лише ГОТОВІ дані сітки (вершини/трикутники/лінії), а не самі
// OpenCascade-об'єкти (їх неможливо передати через structured clone).
//
// Створюється (і тому й вантажить WASM) лише при першому відкритті
// вкладки "Деталі" — див. `ensurePartsWorker()` у parts-viewer.js.
import opencascade from "replicad-opencascadejs";
import opencascadeWasm from "replicad-opencascadejs/wasm?url";
import { setOC } from "replicad";
import { bearing } from "./bearing.js";

let ready = false;

async function init() {
  const OC = await opencascade({ locateFile: () => opencascadeWasm });
  setOC(OC);
  ready = true;
  postMessage({ type: "ready" });
}

function meshFaces(shape) {
  return shape.mesh({ tolerance: 0.05, angularTolerance: 0.3 });
}

function meshEdges(shape) {
  return shape.meshEdges({ tolerance: 0.05 });
}

// `spec` = {d, D, B, ballCount} приходить від головного потоку повністю
// готовим (каталог розмірів і кількість куль за замовчуванням — це UI-
// рівень, у parts-viewer.js; worker.js знає лише про саму геометрію).
function buildBearingPayload(spec) {
  const t0 = performance.now();
  const { innerRing, outerRing, balls } = bearing(spec.d, spec.D, spec.B, spec.ballCount);

  const parts = [
    { name: "innerRing", kind: "ring", faces: meshFaces(innerRing), edges: meshEdges(innerRing) },
    { name: "outerRing", kind: "ring", faces: meshFaces(outerRing), edges: meshEdges(outerRing) },
    ...balls.map((ball, i) => ({ name: `ball${i}`, kind: "ball", faces: meshFaces(ball) })),
  ];

  return { parts, elapsedMs: performance.now() - t0 };
}

self.addEventListener("message", async (event) => {
  const msg = event.data;
  if (msg.type === "build") {
    if (!ready) {
      postMessage({ type: "error", requestId: msg.requestId, message: "OpenCascade ще не готовий" });
      return;
    }
    try {
      const { parts, elapsedMs } = buildBearingPayload(msg.spec);
      postMessage({ type: "result", requestId: msg.requestId, parts, elapsedMs });
    } catch (e) {
      postMessage({ type: "error", requestId: msg.requestId, message: e.message });
    }
  }
});

init().catch((e) => postMessage({ type: "error", message: "Не вдалося ініціалізувати OpenCascade: " + e.message }));
