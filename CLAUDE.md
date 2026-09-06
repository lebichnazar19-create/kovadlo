# CLAUDE.md — шпаргалка для сесій у цьому репо

## Структура

- `kovadlo/` — ЯДРО, чистий Python, лише розрахунки/геометрія, без графіки.
  - `geometry.py`/`geometry3d.py` — Point/Point3, snap, площі, полігони, Face.
  - `elements.py`/`wall.py`/`room.py`/`profile.py` — Element (2 точки+профіль+матеріал+кут), Wall, Room.
  - `tile.py`/`grout.py`/`layout.py`/`surface.py`/`tiling.py` — плитка (модуль 2).
  - `electrical_*`/`cable_route.py`/`wiring_plan.py` — проводка (модуль 4).
  - `pcb_*.py` — плати (модуль 6).
  - `material_*.py` — база матеріалів (модуль 7), "посилання за іменем" — інші модулі зберігають `material_name: str`, не об'єкт.
  - `lighting*/ventilation*/climate*/insulation.py/fire_safety*` — інж. системи (модуль 8). `WallLayer`, `HeatState.wall_layers` — шари СТІНИ, порядок **від приміщення назовні** (0=внутр., останній=зовн.) — див. докстрінг `layer_interface_temperatures_c`.
  - `wall3d.py`/`opening.py`/`roof3d.py`/`building3d.py`/`volume_calc.py`/`mesh_export.py` — 3D-геометрія (модуль 10).
  - `steel_profiles.py`/`beam.py`/`shaft.py`/`transmission.py`/`motor.py`/`kinematics.py` — механіка (модуль 12).
  - `sensors.py`/`actuators.py`/`controller.py`/`automation_*.py` — автоматика (модуль 13).
  - `motion.py` — рух у часі: `Transform`, `Linear`/`Rotation`/`Geared`/`Composite`, `MotionPlan`, `exploded_view_motion_plan`.
- `web/` — сервер + одна HTML-сторінка (модулі 3/5/9/11), ЧИТАЄ ядро.
  - `server.py` — `AppState` (весь стан у пам'яті процесу) + HTTP-роутинг.
  - `scene3d.py` — серіалізація сцени для вкладки 3D (`/api/scene3d`).
  - `motion_state.py` — демо-стенд руху + розліт шарів стіни (`/api/motion/*`).
  - `ifc_export.py` — експорт кімнати в IFC4 через IfcOpenShell (LGPL, окремий `pip install -e ".[ifc]"`, лінивий import у сервері — НЕ в `kovadlo/`, бо не stdlib).
  - `static/index.html` — весь фронтенд, canvas 2D + three.js.
  - `static/js/parts/`, `static/js/geometry/` — OCCT (replicad/WASM) для вкладки «Деталі» й геометрії «Будівництва» (труба/підлога/стіни); `npm run build` кладе бандли в `static/dist/`, сервер їх роздає з `/dist/`.
- `tests/` — pytest, дзеркалить структуру `kovadlo/`+`web/` по файлу на модуль.
- `examples/` — по одному демо-скрипту на розрахунковий модуль.

## Головне правило архітектури

- **`kovadlo/` — лише stdlib.** Жодного `pip install` в ядрі, ніколи.
- **`web/` тільки ЧИТАЄ публічний API ядра** (`from kovadlo import ...` / `from kovadlo.xxx import ...`), ніколи не лізе в приватні (`_...`) методи/атрибути і не змінює файли `kovadlo/`. Кожен новий модуль у README явно пише "ядро не змінено" — тримай цю традицію.
- Нові речі в `kovadlo/xxx.py`, що стосуються ІНШОГО модуля (мотор→точка споживання, матеріал→стіна), підключаються "посиланням за іменем" (рядок), а не новим полем у старому класі.

## Запуск

```bash
pip install -e ".[dev]"     # для прикладів як модулів
pytest                       # 665+ тестів, ~50с
python -m web.server         # порт 8765 за замовчуванням; аргументом — інший порт
```
Сервер тримає стан у пам'яті процесу — після будь-якої зміни `web/*.py` його треба **перезапустити** (`pkill -f "python3 -m web.server"`, потім заново `run_in_background`). `pkill` іноді валить фоновий таск-нотіфікейшн з exit 144 — це очікувано, не баг.

## Конвенції

- **Одиниці**: `kovadlo/` — мм для геометрії (Point/Point3/Wall/Transform), м² для площ (`MM2_PER_M2`), метричні СІ для інж. розрахунків. `HeatState.wall_layers` (веб) зберігає товщину шару в **метрах** — конвертуй ×1000/÷1000 явно на межі з `motion.py`/сценою (мм).
- **three.js (index.html)**: усе в метрах (`x/1000, y/1000, z/1000`), **БЕЗ дзеркалення жодної осі**. Виняток — `buildFloorMesh`: там `-z` це локальна компенсація ЙОГО Ж `rotateX(-90°)`, а не конвенція сцени.
- **MotionPlan**: ключі — рядки. Якщо ім'я може повторитись (однаковий матеріал двічі в стіні) — префіксуй індексом: `f"{i}:{name}"`.
- **HTTP API**: GET без query-параметрів (тільки стан), будь-яке обчислення за вхідними даними — POST з JSON body (`/api/snap`, `/api/tiling`, `/api/motion/state`). Анімацію тягнути ПАЧКОЮ кадрів (`{"ts":[...]}` → `{"frames":[...]}`), не по одному запиту на кадр.

## Пастки, на яких я вже спотикався в цьому репо

1. **Z не мірити ніде** — один раз дзеркалив Z у `_to_three_matrix`/`threePosition`, бо помилково узагальнив локальний хак старого `buildFloorMesh` (тепер `buildFloorPreviewMesh`). Демо-стенд стояв не там, де мав. Звіряй з `buildWallPreviewMesh`/`buildDuctPreviewMesh` (жодного мінуса) — а ще краще з OCCT-геометрією (`geometry-controller.js`), яка взагалі рахує у світових мм без локальних поворотів.
2. **`Geared` коаксіальний** — успадковує `axis`/`origin` від `parent`. Друга шестерня має бути на ТІЙ САМІЙ (x,z), інша лише `y` — інакше вона рахуватиметься навколо чужої осі й полетить по колу навколо `parent`, а не крутитиметься на місці.
3. Порядок шарів стіни легко переплутати напрямком: 0 = зсередини кімнати, не ззовні. Нормаль для розльоту рахується "назовні" — протилежний знак до `place_detectors_along_contour` (там — усередину).
4. Нове поле в `AppState`, залежне від іншого стану (напр. `exploded_wall_index` від `heat.wall_layers`), треба явно чистити при видаленні/reset пов'язаних даних — інакше лишається посилання в нікуди.
5. Тести HTTP — `urllib.request` проти `create_server(port=0)` + `ThreadingHTTPServer` у фоновому треді (див. `test_server.py`), не `requests`.
6. `route` в `do_GET`/`do_POST` — точний збіг `self.path` (без query-рядка), КРІМ `/dist/` (префіксний, для бандлів OCCT) — якщо колись знадобиться `?param=`, доведеться самому парсити `urlparse`.
7. **Це середовище (Termux + proot-distro Ubuntu) має ДВА python** — голий `python`/`pip` резолвиться в Termux/Android (тег платформи `android_arm64_v8a`, БЕЗ шансів на нативні колеса типу ifcopenshell), а справжній проєкт (`/root/kovadlo`) живе в proot Ubuntu (`/usr/bin/python3`, glibc, `manylinux_*_aarch64` — тут ifcopenshell СТАВИТЬСЯ). Для будь-якої pip-залежності поза `kovadlo/` — venv саме там: `apt install python3-pip python3-venv` (одноразово), потім `python3 -m venv .venv && .venv/bin/pip install -e ".[ifc]"`. Основний `pytest`/`python -m web.server` (Termux, без сторонніх пакетів) і далі працюють — модуль з залежністю (`ifc_export.py`) імпортується ЛИНИВО, з graceful 501, а не падінням сервера.
