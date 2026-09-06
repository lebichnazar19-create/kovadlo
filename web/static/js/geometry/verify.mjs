// Позабраузерна перевірка всієї OCCT-геометрії "Будівництва" (Node, без
// Vite/DOM) — ті самі функції, що worker.js викликає для труби
// (повітропровід/кабель/арматура), підлоги й стін.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import opencascade from "replicad-opencascadejs";
import { setOC, measureVolume } from "replicad";
import { sweepTube } from "./tube.js";
import { extrudeFloor, extrudeWall } from "./room.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const wasmPath = path.resolve(here, "../../../../node_modules/replicad-opencascadejs/dist/replicad_single.wasm");

const LENGTH_TOLERANCE_MM = 1e-2;
const VOLUME_TOLERANCE_MM3 = 1; // округлення тесселяції на об'ємах порядку 1e9 мм³

function distanceMm(a, b) {
  return Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
}

let anyFailed = false;

function check(label, ok, detail) {
  console.log(`  ${ok ? "✅" : "❌"} ${label}${detail ? ": " + detail : ""}`);
  if (!ok) anyFailed = true;
}

// ---- труба: повітропровід/кабель/арматура (web/static/js/geometry/tube.js) ----
//   1. Довжина шляху, заміряна з реального дроту (measureLength), має
//      збігатися із сумою відстаней між вхідними точками.
//   2. Тіло не порожнє (не null, об'єм > 0) — саме цей клас багів
//      (self-intersecting sweep на гострому куті) НЕ ловить перевірка
//      довжини, тому обидві перевірки незалежні.
function verifyTube() {
  const cases = [
    {
      name: "пряма ділянка",
      diameterMm: 20,
      points: [
        { x: 0, y: 0, z: 0 },
        { x: 1000, y: 0, z: 0 },
      ],
    },
    {
      name: "коліно 90°",
      diameterMm: 20,
      points: [
        { x: 0, y: 0, z: 0 },
        { x: 500, y: 0, z: 0 },
        { x: 500, y: 0, z: 500 },
      ],
    },
    {
      name: "просторова ламана (не в одній площині)",
      diameterMm: 15,
      points: [
        { x: 0, y: 0, z: 0 },
        { x: 300, y: 200, z: 0 },
        { x: 300, y: 200, z: 400 },
        { x: 0, y: 500, z: 400 },
      ],
    },
  ];

  for (const { name, points, diameterMm } of cases) {
    console.log(`=== труба: ${name} (Ø${diameterMm} мм, ${points.length} точок) ===`);
    const expectedLengthMm = points.slice(1).reduce((sum, p, i) => sum + distanceMm(points[i], p), 0);

    const t0 = performance.now();
    const { solid, pathLengthMm } = sweepTube(points, diameterMm);
    console.log(`  побудовано за ${(performance.now() - t0).toFixed(1)} мс`);

    check(
      "довжина шляху",
      Math.abs(pathLengthMm - expectedLengthMm) <= LENGTH_TOLERANCE_MM,
      `заміряно=${pathLengthMm.toFixed(3)} мм, задано=${expectedLengthMm.toFixed(3)} мм`
    );

    const isEmpty = !solid || solid.isNull;
    const volumeMm3 = isEmpty ? 0 : measureVolume(solid);
    check("тіло не порожнє", !isEmpty && volumeMm3 > 0, `об'єм = ${volumeMm3.toFixed(1)} мм³`);

    solid?.delete?.();
    console.log();
  }
}

// ---- підлога й стіни (web/static/js/geometry/room.js) ----
//   Об'єм тіла має дорівнювати area × thickness, де area — незалежна
//   перевірка (шнурівка для підлоги, довжина×висота мінус прорізи для
//   стіни) — той самий клас незалежності від внутрішніх формул, що й у
//   перевірці підшипника: не зловить баг у формі area, але зловить будь-
//   яке самоперетинання/провал грані, що псує саме тіло.
function verifyRoom() {
  const floorCases = [
    { name: "прямокутна кімната", contour: [[0, 0], [4000, 0], [4000, 3000], [0, 3000]], thicknessMm: 150 },
    {
      name: "Г-подібна (неопукла) кімната",
      contour: [[0, 0], [4000, 0], [4000, 2000], [2000, 2000], [2000, 3000], [0, 3000]],
      thicknessMm: 150,
    },
  ];
  for (const { name, contour, thicknessMm } of floorCases) {
    console.log(`=== підлога: ${name} ===`);
    const { solid, areaMm2 } = extrudeFloor(contour, thicknessMm);
    const volumeMm3 = measureVolume(solid);
    const expectedMm3 = areaMm2 * thicknessMm;
    check(
      "об'єм = area(шнурівка) × thickness",
      Math.abs(volumeMm3 - expectedMm3) <= VOLUME_TOLERANCE_MM3,
      `об'єм=${volumeMm3.toFixed(1)}, очікувано=${expectedMm3.toFixed(1)}`
    );
    solid.delete();
    console.log();
  }

  const wallCases = [
    {
      name: "без прорізів",
      wallData: { start: [0, 0], end: [3000, 0], length_mm: 3000, height_mm: 2700, thickness_mm: 200, openings: [] },
      checkCentering: false,
    },
    {
      name: "під кутом (3-4-5) з дверима й вікном",
      wallData: {
        start: [0, 0],
        end: [3000, 4000],
        length_mm: 5000,
        height_mm: 2700,
        thickness_mm: 200,
        openings: [
          { offset_mm: 200, width_mm: 900, sill_height_mm: 0, height_mm: 2100 },
          { offset_mm: 2500, width_mm: 1200, sill_height_mm: 900, height_mm: 1200 },
        ],
      },
      checkCentering: true,
    },
  ];
  for (const { name, wallData, checkCentering } of wallCases) {
    console.log(`=== стіна: ${name} ===`);
    const { solid, netAreaMm2 } = extrudeWall(wallData);
    const volumeMm3 = measureVolume(solid);
    const expectedMm3 = netAreaMm2 * wallData.thickness_mm;
    check(
      "об'єм = netArea(довжина×висота-прорізи) × thickness",
      Math.abs(volumeMm3 - expectedMm3) <= VOLUME_TOLERANCE_MM3,
      `об'єм=${volumeMm3.toFixed(1)}, очікувано=${expectedMm3.toFixed(1)}`
    );

    if (checkCentering) {
      // Стіна центрована на лінії start→end: діапазон по нормалі до
      // товщини має бути точно ±thickness/2 — інакше вона зсунута вбік
      // від осьової лінії, яку показує 2D-план.
      const [x0, z0] = wallData.start;
      const [x1, z1] = wallData.end;
      const dirX = (x1 - x0) / wallData.length_mm, dirZ = (z1 - z0) / wallData.length_mm;
      const nx = dirZ, nz = -dirX;
      const mesh = solid.mesh({ tolerance: 0.5 });
      let minPerp = Infinity, maxPerp = -Infinity;
      for (let i = 0; i < mesh.vertices.length; i += 3) {
        const perp = (mesh.vertices[i] - x0) * nx + (mesh.vertices[i + 2] - z0) * nz;
        minPerp = Math.min(minPerp, perp);
        maxPerp = Math.max(maxPerp, perp);
      }
      const half = wallData.thickness_mm / 2;
      check(
        "центрована на осьовій лінії (±thickness/2)",
        Math.abs(minPerp + half) < 0.5 && Math.abs(maxPerp - half) < 0.5,
        `діапазон=[${minPerp.toFixed(2)}, ${maxPerp.toFixed(2)}], очікувано=[${(-half).toFixed(2)}, ${half.toFixed(2)}]`
      );
    }

    solid.delete();
    console.log();
  }
}

async function main() {
  const wasmBinary = readFileSync(wasmPath);
  const OC = await opencascade({ wasmBinary });
  setOC(OC);
  console.log("OpenCascade ініціалізовано.\n");

  verifyTube();
  verifyRoom();

  if (anyFailed) {
    console.error("ПЕРЕВІРКА НЕ ПРОЙШЛА — див. ❌ вище.");
    process.exit(1);
  }
  console.log("Усі перевірки пройдено для всіх випадків.");
}

main().catch((e) => {
  console.error("ПОМИЛКА:", e);
  process.exit(1);
});
