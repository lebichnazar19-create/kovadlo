package com.kovadlo.app

import android.net.Uri
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.nio.charset.StandardCharsets

/**
 * Місток JS <-> Kotlin для збереження/відкриття файлу проєкту (модуль 14).
 *
 * Свідомо через Storage Access Framework (`ACTION_CREATE_DOCUMENT` /
 * `ACTION_OPEN_DOCUMENT`), а НЕ через пряме читання/запис файлу за
 * шляхом: на Android 10+ (API 29+) scoped storage все одно не дав би
 * вільного доступу до файлової системи навіть з дозволом
 * `WRITE_EXTERNAL_STORAGE` (він працює лише як legacy-сумісність до
 * API 28, див. `AndroidManifest.xml`) — SAF єдиний надійний спосіб,
 * що працює однаково на всіх підтримуваних версіях і не вимагає
 * жодного дозволу.
 *
 * Методи, позначені `@JavascriptInterface`, викликаються з `index.html`
 * як `window.KovadloNative.saveProject(...)` / `.openProject()`.
 * Результат повертається назад у JS асинхронно, через
 * `webView.evaluateJavascript(...)`, бо показ системного діалогу вибору
 * файлу — процес, який не може повернути значення синхронно.
 */
class ProjectFileBridge(private val activity: AppCompatActivity, private val webView: WebView) {

    private var pendingSaveJson: String? = null

    private val createDocumentLauncher =
        activity.registerForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri: Uri? ->
            val json = pendingSaveJson
            pendingSaveJson = null
            if (uri == null || json == null) {
                notifyJs("onKovadloSaveResult", "false", "null")
                return@registerForActivityResult
            }
            try {
                activity.contentResolver.openOutputStream(uri)?.use { out ->
                    OutputStreamWriter(out, StandardCharsets.UTF_8).use { it.write(json) }
                } ?: throw IllegalStateException("Не вдалося відкрити файл для запису")
                notifyJs("onKovadloSaveResult", "true", "null")
            } catch (t: Throwable) {
                notifyJs("onKovadloSaveResult", "false", jsStringLiteral(t.message ?: t.toString()))
            }
        }

    private val openDocumentLauncher =
        activity.registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
            if (uri == null) {
                notifyJs("onKovadloOpenResult", "false", "null", "null")
                return@registerForActivityResult
            }
            try {
                val text = activity.contentResolver.openInputStream(uri)?.use { input ->
                    InputStreamReader(input, StandardCharsets.UTF_8).readText()
                } ?: throw IllegalStateException("Не вдалося відкрити файл для читання")
                notifyJs("onKovadloOpenResult", "true", jsStringLiteral(text), "null")
            } catch (t: Throwable) {
                notifyJs("onKovadloOpenResult", "false", "null", jsStringLiteral(t.message ?: t.toString()))
            }
        }

    @JavascriptInterface
    fun saveProject(json: String, suggestedName: String) {
        pendingSaveJson = json
        val name = suggestedName.ifBlank { "kovadlo-project.json" }
        activity.runOnUiThread { createDocumentLauncher.launch(name) }
    }

    @JavascriptInterface
    fun openProject() {
        activity.runOnUiThread { openDocumentLauncher.launch(arrayOf("application/json")) }
    }

    private fun notifyJs(callbackName: String, vararg jsArgs: String) {
        val call = "javascript:window.$callbackName && window.$callbackName(${jsArgs.joinToString(",")});"
        activity.runOnUiThread { webView.evaluateJavascript(call, null) }
    }

    /** Коректно екранований рядковий літерал для вставки прямо в JS-код. */
    private fun jsStringLiteral(value: String): String = JSONObject.quote(value)
}
