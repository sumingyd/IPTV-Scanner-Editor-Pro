package com.iptv.scanner.editor.pro;

import android.annotation.SuppressLint;
import android.os.Bundle;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;


import androidx.appcompat.app.AppCompatActivity;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;


public class MainActivity extends AppCompatActivity {

    private static final String TAG = "IPTVMainActivity";
    private WebView webView;
    private Thread serverThread;
    private volatile boolean serverReady = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);


        startServer();

        webView = new WebView(this);
        setContentView(webView);
        setupWebView();

        waitForServerAndLoad();
    }

    private void startServer() {
        serverThread = new Thread(() -> {
            try {
                Log.i(TAG, "Starting Python server...");
                Python py = Python.getInstance();
                py.getModule("android_bridge").callAttr("start_server");
            } catch (Exception e) {
                Log.e(TAG, "Server start failed", e);
            }
        }, "IPTVServer");
        serverThread.setDaemon(true);
        serverThread.start();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                if (url.startsWith("http://127.0.0.1") || url.startsWith("http://localhost")) {
                    return false;
                }
                return super.shouldOverrideUrlLoading(view, url);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onShowCustomView(View view, CustomViewCallback callback) {
                super.onShowCustomView(view, callback);
            }
        });

        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
    }

    private void waitForServerAndLoad() {
        new Thread(() -> {
            Log.i(TAG, "Waiting for server...");
            for (int i = 0; i < 120; i++) {
                try {
                    Thread.sleep(1000);
                    java.net.HttpURLConnection conn = (java.net.HttpURLConnection)
                            new java.net.URL("http://127.0.0.1:8080/api/status").openConnection();
                    conn.setRequestMethod("GET");
                    conn.setConnectTimeout(2000);
                    int code = conn.getResponseCode();
                    conn.disconnect();
                    if (code == 200) {
                        serverReady = true;
                        Log.i(TAG, "Server ready after " + (i+1) + "s");
                        break;
                    }
                } catch (Exception ignored) {
                }
            }
            if (serverReady) {
                Log.i(TAG, "Loading mobile URL in WebView");
                runOnUiThread(() -> {
                    try {
                        webView.loadUrl("http://127.0.0.1:8080/mobile/");
                        Log.i(TAG, "loadUrl called successfully");
                    } catch (Exception e) {
                        Log.e(TAG, "loadUrl failed", e);
                    }
                });
            } else {
                Log.e(TAG, "Server not ready after 120s");
                runOnUiThread(() -> webView.loadData(
                        "<html><body style='background:#1a1a2e;color:#e0e0e0;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif'><h2>Server startup failed</h2></body></html>",
                        "text/html", "UTF-8"));
            }
        }).start();
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}