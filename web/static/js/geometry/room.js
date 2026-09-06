// Підлога й стіни через OCCT, напряму у світових мм-координатах кімнати
// (те саме, що надсилає /api/scene3d) — без проміжної локальної
// 2D-форми + rotateY/rotateX, як робив THREE.ExtrudeGeometry. Це заразом
// прибирає джерело задокументованої пастки з дзеркаленням Z (CLAUDE.md,
// п.1): координати ніде не переводяться туди-сюди, лише один раз
// перемножуються на профіль/нормаль.
import { makeLine, makeFace, assembleWire, basicFaceExtrusion, Vector } from "replicad";

function wireFromPoints3(points) {
  const edges = points.map((p, i) => makeLine(p, points[(i + 1) % points.length]));
  return assembleWire(edges);
}

/**
 * Екструдує контур підлоги (плиту) вниз від y=0 ("верх плити на
 * y=0, під підлогою кімнати" — та сама умова, що й у колишньому
 * buildFloorMesh). `contour` — масив `[x, z]` у мм (кутовий полігон
 * кімнати, опуклий чи ні — довільна проста замкнена ламана).
 *
 * @returns {{solid, areaMm2}} `areaMm2` — площа контуру (шнурівкою), щоб
 *   verify.mjs міг звірити об'єм тіла = area × thickness незалежно від
 *   того, як саме побудована грань.
 */
export function extrudeFloor(contour, thicknessMm) {
  if (contour.length < 3) {
    throw new Error("Контур підлоги має щонайменше 3 точки");
  }
  if (!(thicknessMm > 0)) {
    throw new Error("thicknessMm має бути додатним");
  }

  const points3 = contour.map(([x, z]) => [x, 0, z]);
  const face = makeFace(wireFromPoints3(points3));
  const solid = basicFaceExtrusion(face, new Vector([0, -1, 0]).multiply(thicknessMm));

  // Площа шнурівкою (Shoelace formula) — незалежна від OCCT перевірка.
  let area2 = 0;
  for (let i = 0; i < contour.length; i++) {
    const [x0, z0] = contour[i];
    const [x1, z1] = contour[(i + 1) % contour.length];
    area2 += x0 * z1 - x1 * z0;
  }
  const areaMm2 = Math.abs(area2) / 2;

  return { solid, areaMm2 };
}

/**
 * Екструдує стіну з прямокутними прорізами (двері/вікна) як єдине тіло,
 * центроване на лінії start→end (половина товщини в кожен бік — та сама
 * умова, що й колишній `geometry.translate(0,0,-thicknessM/2)`).
 *
 * `wallData` — та сама форма, що й у buildWallMesh: `start`/`end` — `[x,
 * z]` у мм, `height_mm`, `thickness_mm`, `openings` —
 * `[{offset_mm, width_mm, sill_height_mm, height_mm}, ...]`.
 *
 * @returns {{solid, netAreaMm2}} `netAreaMm2` — площа профілю (стіна
 *   мінус прорізи), для тієї самої незалежної перевірки об'єму.
 */
export function extrudeWall(wallData) {
  const [x0, z0] = wallData.start;
  const [x1, z1] = wallData.end;
  const lengthMm = wallData.length_mm;
  const heightMm = wallData.height_mm;
  const thicknessMm = wallData.thickness_mm;
  if (!(lengthMm > 0) || !(heightMm > 0) || !(thicknessMm > 0)) {
    throw new Error("length_mm/height_mm/thickness_mm мають бути додатними");
  }

  const dirX = (x1 - x0) / lengthMm;
  const dirZ = (z1 - z0) / lengthMm;
  // Нормаль до напрямку стіни в площині підлоги (XZ) — напрям товщини.
  const normal = [dirZ, 0, -dirX];

  // (u, v) у площині стіни (u — уздовж довжини, v — по висоті) → світові
  // мм-координати на осьовій лінії стіни (t=0, товщина додається екструзією).
  function point3(u, v) {
    return [x0 + dirX * u, v, z0 + dirZ * u];
  }

  const outerWire = wireFromPoints3([point3(0, 0), point3(lengthMm, 0), point3(lengthMm, heightMm), point3(0, heightMm)]);

  let netAreaMm2 = lengthMm * heightMm;
  const holeWires = wallData.openings.map((o) => {
    const u0 = o.offset_mm, u1 = o.offset_mm + o.width_mm;
    const v0 = o.sill_height_mm, v1 = o.sill_height_mm + o.height_mm;
    netAreaMm2 -= o.width_mm * o.height_mm;
    return wireFromPoints3([point3(u0, v0), point3(u0, v1), point3(u1, v1), point3(u1, v0)]);
  });

  const face = makeFace(outerWire, holeWires);
  const solid = basicFaceExtrusion(face, new Vector(normal).multiply(thicknessMm))
    // Shape.translate() сам видаляє попереднє тіло й повертає нове — не
    // вільна функція translate(shape, v), яка чекає "сирий" wrapped-об'єкт.
    .translate(new Vector(normal).multiply(-thicknessMm / 2));

  return { solid, netAreaMm2 };
}
