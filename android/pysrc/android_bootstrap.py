"""Android-лише bootstrap для запуску вбудованого веб-сервера (модуль 14).

НЕ symlink — окремий реальний файл поруч із `kovadlo/` і `web/` (які
підключені як є, без змін — обмеження модуля 14, див. коментар у
`app/build.gradle.kts`). Єдина мета цього файлу: обгорнути
`web.server.create_server` у try/except, що при збої повертає ПОВНИЙ
Python traceback (`traceback.format_exc()`) прямо як текст повідомлення
винятку.

Навіщо: `com.chaquo.python.PyException` за документацією Chaquopy має
об'єднувати Python- і Java-кадри в `getStackTrace()`, але покладатися на
це для екрана діагностики застосунку зайве — простіше й надійніше дати
Python самому відформатувати свій traceback, поки він ще має контекст
винятку (`sys.exc_info()`), і передати це одним рядком-повідомленням,
яке гарантовано доїде до Kotlin (`t.message`) незалежно від деталей
злиття стеків на боці JNI.
"""
from __future__ import annotations

import traceback


def create_server_or_raise(port: int = 0):
    """Як `web.server.create_server`, але при будь-якій помилці кидає
    `RuntimeError`, чиє повідомлення — повний traceback оригінального
    збою (файл, рядок, увесь ланцюжок), а не лише останній рядок
    (`str(exc)`).

    Імпорт `web.server` навмисно ЛОКАЛЬНИЙ і всередині цього самого
    `try` (а не на рівні модуля) — щоб traceback показував реальне
    місце падіння, навіть якщо воно стається в ланцюжку імпорту
    (`import web.server` тягне за собою `kovadlo/__init__.py`,
    `web/project_io.py`, `web/reports.py`, `web/scene3d.py`,
    `web/tiling_render.py`), а не тільки всередині виклику
    `create_server()`."""
    try:
        from web.server import create_server

        return create_server(port)
    except Exception as exc:  # noqa: BLE001 — навмисно широко: потрібен ПОВНИЙ traceback будь-якого збою
        raise RuntimeError(traceback.format_exc()) from exc
