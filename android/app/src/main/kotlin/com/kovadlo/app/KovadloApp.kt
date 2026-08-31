package com.kovadlo.app

import android.app.Application
import android.util.Log
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

/**
 * Точка старту вбудованого Python (Chaquopy): піднімає той самий
 * `web.server` (модулі 3/5/9/11/14), що й на десктопі, — на
 * `127.0.0.1` (лише локальна петля, недоступно ззовні), фоновим
 * потоком, і тримає його живим на весь час роботи застосунку.
 *
 * Пакет `kovadlo`/`web` підключений як є (символічні посилання в
 * `android/pysrc`, `app/build.gradle.kts`), без жодних змін чи
 * копіювання джерела — обмеження модуля 14.
 */
class KovadloApp : Application() {

    companion object {
        private const val TAG = "KovadloApp"

        @Volatile
        var serverPort: Int = 0
            private set

        @Volatile
        var startupError: String? = null
            private set
    }

    /** Записує [startupError] з міткою кроку й КОНКРЕТНОГО catch, що
     * спрацював — щоб на екрані було видно, чи це взагалі той самий
     * catch, і на якому саме кроці впало (діагностика, тимчасово). */
    private fun fail(step: String, t: Throwable) {
        Log.e(TAG, "$step впав", t)
        startupError = "KT-CATCH $step:\n" + t.stackTraceToString()
    }

    override fun onCreate() {
        super.onCreate()

        try {
            if (!Python.isStarted()) {
                Python.start(AndroidPlatform(this))
            }
        } catch (t: Throwable) {
            fail("STEP1 (Python.start)", t)
            return
        }

        val python: Python
        try {
            python = Python.getInstance()
        } catch (t: Throwable) {
            fail("STEP2 (Python.getInstance)", t)
            return
        }

        // android_bootstrap.create_server_or_raise (android/pysrc/, НЕ
        // web/server.py — той не чіпаємо) замість прямого виклику
        // create_server: при збої кидає RuntimeError, чиє повідомлення —
        // повний Python traceback (traceback.format_exc()), а не лише
        // останній рядок винятку.
        val bootstrapModule: PyObject
        try {
            bootstrapModule = python.getModule("android_bootstrap")
        } catch (t: Throwable) {
            fail("STEP3 (getModule android_bootstrap)", t)
            return
        }

        // port=0 -> ОС сама обирає вільний локальний порт (як і в
        // тестах на десктопі, create_server(port=0, ...)).
        val server: PyObject
        try {
            server = bootstrapModule.callAttr("create_server_or_raise", 0)
        } catch (t: Throwable) {
            fail("STEP4 (callAttr create_server_or_raise)", t)
            return
        }

        try {
            val port = server.get("server_address")!!.asList()[1].toInt()
            serverPort = port

            Thread {
                try {
                    server.callAttr("serve_forever")
                } catch (t: Throwable) {
                    Log.e(TAG, "Python HTTP-сервер зупинився з помилкою", t)
                }
            }.apply {
                isDaemon = true
                name = "kovadlo-python-server"
                start()
            }

            Log.i(TAG, "Ковадло: локальний сервер запущено на 127.0.0.1:$port")
        } catch (t: Throwable) {
            fail("STEP5 (server_address/thread)", t)
        }
    }
}
