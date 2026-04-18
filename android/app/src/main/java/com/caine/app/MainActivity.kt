package com.caine.app

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.WindowManager
import android.webkit.*
import android.widget.FrameLayout
import androidx.appcompat.app.AppCompatActivity
import androidx.browser.customtabs.CustomTabsIntent

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val CAINE_URL = "https://caine-ye8z.onrender.com"

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS)
        window.statusBarColor     = Color.parseColor("#0b0b0b")
        window.navigationBarColor = Color.parseColor("#0b0b0b")
        supportActionBar?.hide()

        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
          or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
        )

        webView = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#0b0b0b"))
            layoutParams = FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        }

        webView.settings.apply {
            javaScriptEnabled    = true
            domStorageEnabled    = true
            databaseEnabled      = true
            allowFileAccess      = true
            cacheMode            = WebSettings.LOAD_DEFAULT
            setSupportZoom(false)
            displayZoomControls  = false
            useWideViewPort      = true
            loadWithOverviewMode = true
            // strip "; wv" so Google Identity Services renders the sign-in button
            userAgentString      = userAgentString.replace("; wv", "")
        }

        android.webkit.CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(webView, true)
        }

        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, req: WebResourceRequest): Boolean {
                val url = req.url.toString()
                return when {
                    // our app — stay in WebView
                    url.startsWith(CAINE_URL) -> false
                    // Google accounts — open in Chrome Custom Tab so auth works reliably,
                    // then the tab closes and brings user back here
                    url.contains("accounts.google.com") -> {
                        openCustomTab(url)
                        true
                    }
                    // everything else — open in external browser
                    else -> {
                        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                        true
                    }
                }
            }

            override fun onPageFinished(view: WebView, url: String) {
                // after any page load, sync cookies so session persists
                android.webkit.CookieManager.getInstance().flush()
            }

            override fun onReceivedError(
                view: WebView, req: WebResourceRequest, err: WebResourceError
            ) {
                if (req.isForMainFrame) {
                    view.loadUrl("file:///android_asset/offline.html")
                }
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(msg: ConsoleMessage?) = true
        }

        setContentView(webView)

        if (isOnline()) webView.loadUrl(CAINE_URL)
        else webView.loadUrl("file:///android_asset/offline.html")
    }

    override fun onResume() {
        super.onResume()
        webView.onResume()
        // coming back from Custom Tab auth — reload so session cookie takes effect
        if (isOnline()) webView.reload()
    }

    override fun onPause() {
        super.onPause()
        webView.onPause()
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    private fun openCustomTab(url: String) {
        CustomTabsIntent.Builder()
            .setShowTitle(false)
            .build()
            .launchUrl(this, Uri.parse(url))
    }

    private fun isOnline(): Boolean {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val net = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(net) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}
