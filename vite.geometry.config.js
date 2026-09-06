import { fileURLToPath } from "node:url";
import path from "node:path";
import { defineConfig } from "vite";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

// Збирає всю OCCT-геометрію "Будівництва" (web/static/js/geometry/) —
// труба (повітропровід/кабель/арматура, tube.js), підлога й стіни
// (room.js) — один спільний Worker/WASM на все, не три окремі бандли.
// Роздає web/server.py з web/static/dist/geometry/ — без CDN, для
// офлайн-режиму в Android-застосунку (модуль 14).
//
// ОКРЕМИЙ від vite.parts.config.js файл — той самий бандл-конфлікт з
// vite.parts.config.js (однойменні worker.js-чанки), що і пояснено там.
export default defineConfig({
  base: "./",
  build: {
    outDir: path.resolve(rootDir, "web/static/dist/geometry"),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(rootDir, "web/static/js/geometry/geometry-controller.js"),
      // Без цього Rollup викидає export createGeometryController як
      // мертвий код — жоден .html ЦЬОГО Ж білда на нього не посилається
      // (index.html підключає готовий бандл окремим import() у рантаймі).
      preserveEntrySignatures: "strict",
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "[name].js",
        assetFileNames: "[name][extname]",
      },
    },
  },
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
    exclude: ["replicad-opencascadejs"],
  },
});
