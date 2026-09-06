// Спільний Web Worker для всієї OCCT-геометрії "Будівництва" — труба
// (повітропровід/кабель/арматура), підлога, стіна. Один Worker/один
// WASM на всі три, не три окремі бандли — рахунок не в основному потоці.
import opencascade from "replicad-opencascadejs";
import opencascadeWasm from "replicad-opencascadejs/wasm?url";
import { setOC } from "replicad";
import { sweepTube } from "./tube.js";
import { extrudeFloor, extrudeWall } from "./room.js";

let ready = false;

async function init() {
  const OC = await opencascade({ locateFile: () => opencascadeWasm });
  setOC(OC);
  ready = true;
  postMessage({ type: "ready" });
}

function meshFaces(shape) {
  // Товщина об'єктів тут — десятки-сотні мм на конструкціях у кілька
  // метрів, тому допуск грубіший, ніж у web/static/js/parts/worker.js
  // (де деталь ~40 мм) — інакше сітка розростається без користі для ока.
  return shape.mesh({ tolerance: 1, angularTolerance: 0.4 });
}

function meshEdges(shape) {
  return shape.meshEdges({ tolerance: 1 });
}

function buildTube(spec) {
  const { solid, pathLengthMm } = sweepTube(spec.points, spec.diameterMm);
  const payload = { faces: meshFaces(solid), edges: meshEdges(solid), pathLengthMm };
  solid.delete();
  return payload;
}

function buildFloor(spec) {
  const { solid, areaMm2 } = extrudeFloor(spec.contour, spec.thicknessMm);
  const payload = { faces: meshFaces(solid), edges: meshEdges(solid), areaMm2 };
  solid.delete();
  return payload;
}

function buildWall(spec) {
  const { solid, netAreaMm2 } = extrudeWall(spec.wallData);
  const payload = { faces: meshFaces(solid), edges: meshEdges(solid), netAreaMm2 };
  solid.delete();
  return payload;
}

const BUILDERS = { tube: buildTube, floor: buildFloor, wall: buildWall };

self.addEventListener("message", async (event) => {
  const msg = event.data;
  if (msg.type !== "build") return;
  if (!ready) {
    postMessage({ type: "error", requestId: msg.requestId, message: "OpenCascade ще не готовий" });
    return;
  }
  const builder = BUILDERS[msg.kind];
  if (!builder) {
    postMessage({ type: "error", requestId: msg.requestId, message: `Невідомий тип побудови: ${msg.kind}` });
    return;
  }
  try {
    const t0 = performance.now();
    const result = builder(msg.spec);
    postMessage({ type: "result", requestId: msg.requestId, ...result, elapsedMs: performance.now() - t0 });
  } catch (e) {
    postMessage({ type: "error", requestId: msg.requestId, message: e.message });
  }
});

init().catch((e) => postMessage({ type: "error", message: "Не вдалося ініціалізувати OpenCascade: " + e.message }));
