// Просторова лінія через OCCT: коловий профіль, розгорнутий уздовж
// полілінії (`genericSweep`). Одна функція для повітропроводу, кабелю й
// арматури — різняться лише diameterMm і колір матеріалу (колір — це
// турбота виклику на клієнті, не геометрії; тут лише тіло).
//
// Замінює саморобний `THREE.TubeGeometry` (web/static/index.html,
// колишня buildDuctMesh) реальним B-rep тілом з OpenCascade.
import { makeLine, makeCircle, assembleWire, genericSweep, measureLength } from "replicad";

function subtract(a, b) {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function length(v) {
  return Math.hypot(v[0], v[1], v[2]);
}

function normalize(v) {
  const len = length(v);
  if (len < 1e-9) {
    throw new Error("Дві сусідні точки полілінії збігаються — не можу визначити напрямок профілю");
  }
  return [v[0] / len, v[1] / len, v[2] / len];
}

/**
 * Розгортає коловий профіль діаметром `diameterMm` уздовж просторової
 * полілінії `points` (масив `{x, y, z}` у мм, щонайменше 2 точки).
 *
 * @returns {{solid: import("replicad").Solid, pathLengthMm: number}}
 *   `solid` — викликач відповідає за `.delete()`; `pathLengthMm` —
 *   довжина шляху, заміряна з реального дроту (`measureLength`), а не
 *   сума вхідних відстаней — це те, що звіряє verify.mjs.
 */
export function sweepTube(points, diameterMm) {
  if (points.length < 2) {
    throw new Error("Потрібно щонайменше 2 точки для просторової лінії");
  }
  if (!(diameterMm > 0)) {
    throw new Error("diameterMm має бути додатним");
  }

  const pts = points.map((p) => [p.x, p.y, p.z]);

  const pathEdges = [];
  for (let i = 0; i < pts.length - 1; i++) {
    pathEdges.push(makeLine(pts[i], pts[i + 1]));
  }
  const pathWire = assembleWire(pathEdges);

  const startDirection = normalize(subtract(pts[1], pts[0]));
  const profileWire = assembleWire([makeCircle(diameterMm / 2, pts[0], startDirection)]);

  // "round" — заокруглені переходи в зламах полілінії, інакше на різких
  // кутах профіль сам себе перетинає (кабель/арматура гнуться, а не
  // ламаються під гострим кутом).
  const solid = genericSweep(profileWire, pathWire, { transitionMode: "round" });
  const pathLengthMm = measureLength(pathWire);

  return { solid, pathLengthMm };
}
