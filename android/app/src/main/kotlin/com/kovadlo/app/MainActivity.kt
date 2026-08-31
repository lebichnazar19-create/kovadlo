package com.kovadlo.app

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen

/**
 * Єдина активність застосунку: WebView на весь екран із локальною
 * сторінкою модулів 3/5/9/11 (`web/static/index.html`), яку віддає
 * вбудований Python-сервер ([KovadloApp]). Повністю офлайн — жодного
 * звернення в інтернет, лише `127.0.0.1`.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)

        webView = WebView(this)
        setContentView(webView)

        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        // Офлайн-застосунок: жодних мережевих запитів, окрім локального
        // сервера на 127.0.0.1 — кеш і безпечний перегляд файлів не потрібні.
        webView.settings.allowFileAccess = false
        webView.settings.allowContentAccess = false

        webView.webViewClient = WebViewClient()
        webView.addJavascriptInterface(ProjectFileBridge(this, webView), "KovadloNative")

        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    // Навігація між вкладками — це стан у самому SPA
                    // (JS, не історія браузера), тож "назад" у WebView
                    // немає сенсу: просто закриваємо застосунок.
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            },
        )

        loadApp()
    }

    private fun loadApp() {
        val port = KovadloApp.serverPort
        if (port <= 0) {
            val error = KovadloApp.startupError ?: "невідома помилка запуску Python"
            val escaped = error
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            webView.loadDataWithBaseURL(
                null,
                "<html><body style='background:#2B2E33;color:#E8A33D;font-family:sans-serif;padding:24px'>" +
                    "<h2>Ковадло не змогло запуститися</h2>" +
                    "<p>Помилка вбудованого Python-сервера (повний traceback):</p>" +
                    "<pre style='white-space:pre-wrap;word-break:break-word;color:#F2E9DD;" +
                    "font-size:12px'>$escaped</pre>" +
                    "</body></html>",
                "text/html",
                "utf-8",
                null,
            )
            return
        }
        webView.loadUrl("http://127.0.0.1:$port/")
    }
}
