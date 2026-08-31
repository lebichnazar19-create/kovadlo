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

    override fun onCreate() {
        super.onCreate()

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        try {
            val python = Python.getInstance()
            val serverModule = python.getModule("web.server")
            // port=0 -> ОС сама обирає вільний локальний порт (як і в
            // тестах на десктопі, create_server(port=0, ...)).
            val server: PyObject = serverModule.callAttr("create_server", 0)
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
            // Не рвемо застосунок одразу — MainActivity показує зрозуміле
            // повідомлення, якщо serverPort так і лишився 0.
            // Повний traceback (не лише t.message), щоб на екрані помилки
            // було видно точний рядок збою, включно з Python-кадрами, які
            // Chaquopy додає в стек винятку.
            Log.e(TAG, "Не вдалося запустити вбудований Python-сервер", t)
            startupError = t.stackTraceToString()
        }
    }
}
