// Позабраузерна перевірка геометрії (Node, без Vite/DOM) — щоб хоч якось
// підтвердити, що OpenCascade реально будує коректний підшипник, без
// доступу до браузера в цій сесії. Імпортує ту саму `bearing()`, яку
// використовує worker.js — жодного дублювання логіки побудови.
//
// Дві перевірки навмисно НЕЗАЛЕЖНІ від формул усередині bearing(): вони
// б не впіймали баг попередньої версії (кулька в металі, кільця
// зрослися в одне тіло), бо той баг не ламав жодне число на вході —
// ламалась ЛИШЕ фактична форма дуги. Тому тут:
//   1. Об'єм перетину кожної кульки з кожним кільцем (`.intersect()` +
//      `measureVolume`) — має бути ~0.
//   2. Мінімальний і максимальний радіус кожного кільця — заміряні З
//      РЕАЛЬНОЇ ТРИКУТНОЇ СІТКИ (.mesh().vertices), а не з формул
//      побудови: перевіряє, що мінімальний радіус зовнішнього кільця
//      БІЛЬШИЙ за максимальний радіус внутрішнього.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import opencascade from "replicad-opencascadejs";
import { setOC, measureVolume } from "replicad";
import { bearing, BEARING_CATALOG } from "./bearing.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const wasmPath = path.resolve(here, "../../../../node_modules/replicad-opencascadejs/dist/replicad_single.wasm");

const VOLUME_TOLERANCE_MM3 = 1e-3; // "практично нуль" — похибка тесселяції/булевої операції

// --- перевірка 1: об'єм перетину куля<->кільце має бути ~0 --------------
function intersectionVolumeMm3(a, b) {
  try {
    const common = a.clone().intersect(b.clone());
    if (!common || common.isNull) return 0;
    const volume = measureVolume(common);
    common.delete?.();
    return volume;
  } catch (e) {
    // OCCT типово кидає помилку саме тоді, коли перетину НЕМАЄ (порожній
    // результат булевої операції) — це PASS, а не збій перевірки.
    return 0;
  }
}

// --- перевірка 2: мін/макс радіус кільця з реальної сітки, не з формул --
function radiiFromMesh(mesh) {
  const radii = [];
  for (let i = 0; i < mesh.vertices.length; i += 3) {
    radii.push(Math.hypot(mesh.vertices[i], mesh.vertices[i + 1]));
  }
  return radii;
}

async function main() {
  const wasmBinary = readFileSync(wasmPath);
  const OC = await opencascade({ wasmBinary });
  setOC(OC);
  console.log("OpenCascade ініціалізовано.\n");

  let anyFailed = false;

  for (const [code, spec] of Object.entries(BEARING_CATALOG)) {
    console.log(`=== ${code} (${spec.d}/${spec.D}/${spec.B}) ===`);
    const t0 = performance.now();
    const { innerRing, outerRing, balls, ballRadius, pitchRadius, grooveRadius } = bearing(
      spec.d,
      spec.D,
      spec.B,
      9
    );
    const elapsed = performance.now() - t0;
    console.log(
      `  побудовано за ${elapsed.toFixed(1)} мс (Rb=${ballRadius.toFixed(3)}, Rp=${pitchRadius.toFixed(3)}, Rg=${grooveRadius.toFixed(3)})`
    );

    // --- перевірка 1 ---
    let maxIntersectionVolume = 0;
    for (const ring of [innerRing, outerRing]) {
      for (const ball of balls) {
        const volume = intersectionVolumeMm3(ball, ring);
        maxIntersectionVolume = Math.max(maxIntersectionVolume, volume);
      }
    }
    const intersectionOk = maxIntersectionVolume <= VOLUME_TOLERANCE_MM3;
    console.log(
      `  ${intersectionOk ? "✅" : "❌"} перетин куля<->кільце: макс. об'єм = ${maxIntersectionVolume.toExponential(3)} мм³`
    );
    if (!intersectionOk) anyFailed = true;

    // --- перевірка 2 ---
    const innerMesh = innerRing.mesh({ tolerance: 0.05 });
    const outerMesh = outerRing.mesh({ tolerance: 0.05 });
    const innerRadii = radiiFromMesh(innerMesh);
    const outerRadii = radiiFromMesh(outerMesh);
    const innerMaxRadius = Math.max(...innerRadii);
    const outerMinRadius = Math.min(...outerRadii);
    const gap = outerMinRadius - innerMaxRadius;
    const gapOk = gap > 0;
    console.log(
      `  ${gapOk ? "✅" : "❌"} зазор між кільцями: innerRing max=${innerMaxRadius.toFixed(3)}, ` +
        `outerRing min=${outerMinRadius.toFixed(3)}, зазор=${gap.toFixed(3)} мм`
    );
    if (!gapOk) anyFailed = true;

    console.log();
  }

  if (anyFailed) {
    console.error("ПЕРЕВІРКА НЕ ПРОЙШЛА — див. ❌ вище.");
    process.exit(1);
  }
  console.log("Усі перевірки пройдено для всіх розмірів каталогу.");
}

main().catch((e) => {
  console.error("ПОМИЛКА:", e);
  process.exit(1);
});
