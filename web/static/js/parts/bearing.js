// Параметрична геометрія кулькового підшипника (replicad/OpenCascade).
//
// Навмисно НЕ ініціалізує OpenCascade сам (`setOC(...)`) — це виклична
// сторона (worker.js у браузері, verify.mjs у Node), бо ініціалізація
// асинхронна й одноразова, а цей модуль має бути простою синхронною
// функцією, яку можна викликати багато разів поспіль.
//
// Той самий файл імпортує і браузерний worker (через Vite-бандл), і
// verify.mjs напряму через Node (без бандлера, `import` з bare specifier
// "replicad" резолвиться в node_modules так само, як і в браузері після
// збірки) — тому тут лише голий ESM, без нічого специфічного для Vite.
import { draw, makeSphere } from "replicad";

// --- каталог стандартних розмірів (серія 7000, кулькові радіально-упорні):
// d — отвір, D — зовнішній діаметр, B — ширина, усе в мм.
export const BEARING_CATALOG = {
  "7204": { d: 20, D: 47, B: 14 },
  "7205": { d: 25, D: 52, B: 15 },
  "7206": { d: 30, D: 62, B: 16 },
};
export const DEFAULT_BALL_COUNT = 9; // орієнтовно, типово для цієї серії — каталог його не задає

// ---- профіль кільця (переріз у площині XZ: X — радіус від осі обертання,
// Z — уздовж осі): пряма стінка на радіусі `rFlat`, плече на `rShoulder`,
// і канавка під кульку — дуга через 3 точки до `rGrooveMid` на осьовому
// центрі. Той самий код для внутрішнього й зовнішнього кілець: для
// внутрішнього канавка прогинається ДО осі (rGrooveMid < rShoulder), для
// зовнішнього — ВІД осі (rGrooveMid > rShoulder); форма контуру та сама.
//
// Три точки дуги мають лежати РІВНО на колі радіуса Rg (дивись коментар
// над `bearing()`) — інакше дуга через довільні 3 точки матиме зовсім
// інший фактичний радіус кривизни, і геометрія розійдеться з розрахунком.
function ringProfile(rFlat, rShoulder, rGrooveMid, grooveHalfSpan, halfWidth) {
  return draw([rFlat, -halfWidth])
    .vLineTo(halfWidth)
    .hLineTo(rShoulder)
    .vLineTo(grooveHalfSpan)
    .threePointsArcTo([rShoulder, -grooveHalfSpan], [rGrooveMid, 0])
    .vLineTo(-halfWidth)
    .close();
}

// ---- геометрія канавки: дотичні кола, не довільні множники -----------
//
// Канавка — дуга кола радіуса Rg, ДОТИЧНА до кульки (радіус Rb) в
// осьовому центрі (v=0). Для двох кіл, дотичних зсередини (кулька —
// всередині більшого кола канавки, Rg > Rb), відстань між центрами =
// Rg - Rb. Розв'язавши це для точки дотику в потрібному місці (Rp-Rb
// для внутрішнього кільця, Rp+Rb для зовнішнього), центр дуги:
//   внутрішнє: Cin  = Rp - Rb + Rg
//   зовнішнє:  Cout = Rp + Rb - Rg
// і сама дуга (радіальна координата як функція осьової v, |v|<=grooveHalfSpan):
//   внутрішнє: r(v) = Cin  - sqrt(Rg² - v²)   (мінімум у центрі = Rp-Rb, дотик)
//   зовнішнє:  r(v) = Cout + sqrt(Rg² - v²)   (максимум у центрі = Rp+Rb, дотик)
// Це математично гарантує відсутність перетину з кулькою на всій довжині
// канавки, а не лише в центрі — перевірено окремо (verify.mjs: об'єм
// перетину куля<->кільце й мінімальний/максимальний радіус кожного
// кільця з реальної сітки).
//
// grooveHalfSpan = Rb: канавка займає рівно ширину самої кульки, за нею
// — пряме плече (rShoulder) на все, що лишилось до краю кільця.
export function bearing(d, D, B, ballCount) {
  const rBore = d / 2;
  const rOuter = D / 2;
  const halfWidth = B / 2;
  const pitchRadius = (d + D) / 4; // dm/2, dm = (d+D)/2 — середній діаметр
  const ballDiameter = 0.32 * (D - d); // Dw ≈ 0.32*(D-d)
  const ballRadius = ballDiameter / 2;
  const grooveRadius = 0.52 * ballDiameter; // Rg ≈ 0.52*Dw — трохи більший за кульку
  const grooveHalfSpan = ballRadius;

  if (grooveRadius <= ballRadius) {
    throw new Error("Радіус канавки має бути більшим за радіус кульки (конформність)");
  }
  const sag = Math.sqrt(grooveRadius * grooveRadius - grooveHalfSpan * grooveHalfSpan);

  const innerCenter = pitchRadius - ballRadius + grooveRadius;
  const innerGrooveBottom = pitchRadius - ballRadius; // точка дотику, v=0
  const innerShoulder = innerCenter - sag; // v=±grooveHalfSpan (край канавки/початок плеча)

  const outerCenter = pitchRadius + ballRadius - grooveRadius;
  const outerGrooveTop = pitchRadius + ballRadius; // точка дотику, v=0
  const outerShoulder = outerCenter + sag;

  // Захист від невалідного профілю для довільних (не з каталогу) d/D/B.
  if (rBore >= innerGrooveBottom || innerShoulder >= pitchRadius) {
    throw new Error(`Невалідний профіль внутрішнього кільця для d=${d}, D=${D}`);
  }
  if (rOuter <= outerGrooveTop || outerShoulder <= pitchRadius) {
    throw new Error(`Невалідний профіль зовнішнього кільця для d=${d}, D=${D}`);
  }
  if (outerShoulder <= innerShoulder) {
    throw new Error(`Кільця перекриються по радіусу для d=${d}, D=${D} (немає зазору)`);
  }

  const innerRing = ringProfile(rBore, innerShoulder, innerGrooveBottom, grooveHalfSpan, halfWidth)
    .sketchOnPlane("XZ")
    .revolve([0, 0, 1]);

  const outerRing = ringProfile(rOuter, outerShoulder, outerGrooveTop, grooveHalfSpan, halfWidth)
    .sketchOnPlane("XZ")
    .revolve([0, 0, 1]);

  const balls = [];
  const angleStep = 360 / ballCount;
  for (let i = 0; i < ballCount; i++) {
    balls.push(makeSphere(ballRadius).translate([pitchRadius, 0, 0]).rotate(i * angleStep, [0, 0, 0], [0, 0, 1]));
  }

  return { innerRing, outerRing, balls, ballRadius, pitchRadius, grooveRadius };
}
