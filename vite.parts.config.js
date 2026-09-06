import { fileURLToPath } from "node:url";
import path from "node:path";
import { defineConfig } from "vite";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

// Збирає лише вкладку "Деталі" (web/static/js/parts/) — окремий бандл +
// WASM (OpenCascade через replicad), які потім роздає локальний
// Python-сервер (web/server.py) з web/static/dist/parts/. Жодного CDN
// тут: важить офлайн-режим в Android-застосунку (модуль 14). three.js
// сюди НЕ входить — та сама CDN-збірка, що вже підключена для решти
// застосунку (index.html), береться як глобальний `window.THREE`.
//
// ОКРЕМИЙ від vite.geometry.config.js файл конфігурації (не один спільний
// білд з кількома input) — інакше однойменні worker.js-чанки обох
// вкладок ("Деталі" й просторова лінія Будівництва) зіткнулися б в
// одному output-каталозі. package.json запускає обидва послідовно.
export default defineConfig({
  // Відносні шляхи в бандлі — без цього Vite прописує асети (WASM,
  // воркер) від КОРЕНЯ сайту ("/replicad_single.wasm"), а роздаються
  // вони не з кореня, а з web/static/dist/parts/.
  base: "./",
  build: {
    outDir: path.resolve(rootDir, "web/static/dist/parts"),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(rootDir, "web/static/js/parts/parts-viewer.js"),
      // index.html імпортує `createPartsController` напряму з готового
      // бандла ("import ... from ./dist/parts/parts-viewer.js"). Без
      // preserveEntrySignatures Rollup вважає export нічийним (жоден
      // .html ЦЬОГО Ж білда на нього не посилається) і викидає ВСЕ тіло
      // parts-viewer.js як мертвий код (build.lib цього не робить, але
      // тоді WASM-асет воркера чомусь вбудовується в JS як base64
      // замість окремого файлу — тож лишаємось на звичайному білді).
      preserveEntrySignatures: "strict",
      output: {
        // Без хешів у назвах: index.html посилається на ці файли за
        // фіксованим ім'ям напряму (не через build-маніфест).
        entryFileNames: "[name].js",
        chunkFileNames: "[name].js",
        assetFileNames: "[name][extname]",
      },
    },
  },
  // worker.js підхоплюється автоматично через патерн
  // `new Worker(new URL("./worker.js", import.meta.url), {type:"module"})`
  // у parts-viewer.js — Vite бандлить його (разом з replicad і
  // replicad-opencascadejs) як окремий ES-модуль-чанк.
  worker: {
    format: "es",
    rollupOptions: {
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "[name].js",
        assetFileNames: "[name][extname]",
      },
    },
  },
  optimizeDeps: {
    // replicad-opencascadejs сам вантажить .wasm через fetch/locateFile —
    // попереднє бандлення Vite (esbuild) цьому лише заважає.
    exclude: ["replicad-opencascadejs"],
  },
});
