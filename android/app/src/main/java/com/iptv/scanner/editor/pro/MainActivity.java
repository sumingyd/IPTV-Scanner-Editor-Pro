package com.iptv.scanner.editor.pro;

import android.annotation.SuppressLint;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import androidx.appcompat.app.AppCompatActivity;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import com.iptv.scanner.editor.pro.mpv.MPVView;
import com.iptv.scanner.editor.pro.mpv.MpvJsBridge;

/**
 * 主 Activity：三层混合架构
 *  1. 底层 MPVView（SurfaceView + JNI mpv）负责视频渲染
 *  2. 中层 WebView 透明叠加，加载 Python aiohttp 服务的移动 UI
 *  3. Python 服务运行在子线程，提供 RESTful API 和静态资源
 *
 * 遥控器/键盘适配：
 *  - DPAD/确认/菜单/媒体键通过 evaluateJavascript 转发给 HTML UI 的 onRemoteKey(code)
 *  - BACK 键由 Java 层处理（关闭面板或退出）
 *  - VOLUME_UP/DOWN/MUTE 由系统处理，不拦截
 */
public class MainActivity extends AppCompatActivity {

    private static final String TAG = "IPTVMainActivity";
    private MPVView mpvView;
    private WebView webView;
    private MpvJsBridge mpvBridge;
    private Thread serverThread;
    private volatile boolean serverReady = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        FrameLayout layout = new FrameLayout(this);

        mpvView = new MPVView(this);
        layout.addView(mpvView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.TRANSPARENT);
        webView.setFocusable(true);
        webView.setFocusableInTouchMode(true);
        layout.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));

        setContentView(layout);

        setupMPV();
        setupWebView();
        // 立即显示加载提示页面，避免服务器启动期间黑屏
        showLoadingPage();
        startServer();
        waitForServerAndLoad();
    }

    /**
     * 服务器启动期间显示加载提示页面（避免黑屏）
     */
    private void showLoadingPage() {
        String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
                + "<meta name='viewport' content='width=device-width,initial-scale=1.0'>"
                + "<style>"
                + "body{margin:0;padding:0;background:#1a1a2e;color:#e0e0e0;"
                + "font-family:sans-serif;display:flex;flex-direction:column;"
                + "align-items:center;justify-content:center;height:100vh;}"
                + ".spinner{width:60px;height:60px;border:4px solid rgba(255,255,255,0.1);"
                + "border-top-color:#4a9eff;border-radius:50%;"
                + "animation:spin 1s linear infinite;margin-bottom:24px;}"
                + "@keyframes spin{to{transform:rotate(360deg);}}"
                + "h2{margin:0 0 8px 0;font-size:20px;font-weight:500;}"
                + "p{margin:0;color:#888;font-size:14px;}"
                + "</style></head><body>"
                + "<div class='spinner'></div>"
                + "<h2>IPTV 扫描编辑器专业版</h2>"
                + "<p>正在启动服务...</p>"
                + "</body></html>";
        webView.loadDataWithBaseURL("about:blank", html, "text/html", "UTF-8", null);
    }

    private void setupMPV() {
        String configDir = getDir("mpv_config", MODE_PRIVATE).getAbsolutePath();
        String cacheDir = getCacheDir().getAbsolutePath();
        mpvView.initialize(configDir, cacheDir);

        mpvBridge = new MpvJsBridge(mpvView, webView);
        mpvBridge.register();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        webView.clearCache(true);
        webView.clearHistory();
        WebView.setWebContentsDebuggingEnabled(true);
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

    private void waitForServerAndLoad() {
        new Thread(() -> {
            Log.i(TAG, "Waiting for server...");
            final int maxWaitSeconds = 300;  // 最长等待 300 秒（Chaquopy 首次启动可能较慢）
            for (int i = 0; i < maxWaitSeconds; i++) {
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
                        Log.i(TAG, "Server ready after " + (i + 1) + "s");
                        break;
                    }
                } catch (Exception ignored) {
                }
                // 每 5 秒更新加载提示，显示等待进度
                if (i > 0 && i % 5 == 0) {
                    final int elapsed = i + 1;
                    runOnUiThread(() -> updateLoadingProgress(elapsed));
                }
            }
            if (serverReady) {
                Log.i(TAG, "Loading mobile URL in WebView");
                runOnUiThread(() -> {
                    try {
                        webView.loadUrl("http://127.0.0.1:8080/mobile/?v=" + System.currentTimeMillis());
                        Log.i(TAG, "loadUrl called successfully");
                    } catch (Exception e) {
                        Log.e(TAG, "loadUrl failed", e);
                    }
                });
            } else {
                Log.e(TAG, "Server not ready after " + maxWaitSeconds + "s");
                runOnUiThread(() -> webView.loadData(
                        "<html><body style='background:#1a1a2e;color:#e0e0e0;display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;font-family:sans-serif'>"
                        + "<h2 style='color:#ff6b6b'>服务器启动失败</h2>"
                        + "<p style='color:#888'>请尝试重启应用，或查看 logcat 日志</p>"
                        + "</body></html>",
                        "text/html", "UTF-8"));
            }
        }).start();
    }

    /**
     * 更新加载提示页面的等待进度
     */
    private void updateLoadingProgress(int seconds) {
        String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
                + "<meta name='viewport' content='width=device-width,initial-scale=1.0'>"
                + "<style>"
                + "body{margin:0;padding:0;background:#1a1a2e;color:#e0e0e0;"
                + "font-family:sans-serif;display:flex;flex-direction:column;"
                + "align-items:center;justify-content:center;height:100vh;}"
                + ".spinner{width:60px;height:60px;border:4px solid rgba(255,255,255,0.1);"
                + "border-top-color:#4a9eff;border-radius:50%;"
                + "animation:spin 1s linear infinite;margin-bottom:24px;}"
                + "@keyframes spin{to{transform:rotate(360deg);}}"
                + "h2{margin:0 0 8px 0;font-size:20px;font-weight:500;}"
                + "p{margin:0;color:#888;font-size:14px;}"
                + ".progress{margin-top:16px;color:#666;font-size:12px;}"
                + "</style></head><body>"
                + "<div class='spinner'></div>"
                + "<h2>IPTV 扫描编辑器专业版</h2>"
                + "<p>正在启动服务...</p>"
                + "<div class='progress'>已等待 " + seconds + " 秒</div>"
                + "</body></html>";
        webView.loadDataWithBaseURL("about:blank", html, "text/html", "UTF-8", null);
    }

    /**
     * 遥控器/键盘事件分发：
     *  - BACK 由 Java 层处理（关闭面板或退出）
     *  - DPAD/确认/菜单/媒体键转发给 HTML UI 的 onRemoteKey(code)
     */
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            // 先让 JS 处理（关闭打开的面板），JS 不处理则退出
            webView.evaluateJavascript(
                "if(window.onRemoteKey){if(onRemoteKey(" + keyCode + ")){}}",
                value -> {
                    // evaluateJavascript 完成后无返回值时 value 为 null 或 "null"
                    // 这里简单处理：直接由 JS 决定，BACK 总是允许返回
                }
            );
            // BACK 键同时由 Java 层兜底：如果 WebView 可后退则后退，否则退出
            if (webView.canGoBack()) {
                webView.goBack();
                return true;
            }
            // 不主动 finish，让 JS 处理；如果 JS 不处理，用户再按一次 BACK 由系统处理
        }

        // 转发给 HTML UI 的遥控器按键
        if (dispatchKeyToJS(keyCode)) {
            return true;
        }

        return super.onKeyDown(keyCode, event);
    }

    /**
     * 把遥控器/媒体按键转发给 HTML UI。
     * @return true 表示已转发（消费），false 表示不处理
     */
    private boolean dispatchKeyToJS(int keyCode) {
        switch (keyCode) {
            // 方向键
            case KeyEvent.KEYCODE_DPAD_UP:
            case KeyEvent.KEYCODE_DPAD_DOWN:
            case KeyEvent.KEYCODE_DPAD_LEFT:
            case KeyEvent.KEYCODE_DPAD_RIGHT:
            case KeyEvent.KEYCODE_DPAD_CENTER:
            // 菜单键
            case KeyEvent.KEYCODE_MENU:
            // 媒体键
            case KeyEvent.KEYCODE_MEDIA_PLAY:
            case KeyEvent.KEYCODE_MEDIA_PAUSE:
            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
            case KeyEvent.KEYCODE_MEDIA_NEXT:
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
            case KeyEvent.KEYCODE_MEDIA_STOP:
            case KeyEvent.KEYCODE_MEDIA_STEP_FORWARD:
            case KeyEvent.KEYCODE_MEDIA_STEP_BACKWARD:
            case KeyEvent.KEYCODE_MEDIA_FAST_FORWARD:
            case KeyEvent.KEYCODE_MEDIA_REWIND:
            // 数字键（频道号输入）
            case KeyEvent.KEYCODE_0:
            case KeyEvent.KEYCODE_1:
            case KeyEvent.KEYCODE_2:
            case KeyEvent.KEYCODE_3:
            case KeyEvent.KEYCODE_4:
            case KeyEvent.KEYCODE_5:
            case KeyEvent.KEYCODE_6:
            case KeyEvent.KEYCODE_7:
            case KeyEvent.KEYCODE_8:
            case KeyEvent.KEYCODE_9:
            // 字母键（快捷键）
            case KeyEvent.KEYCODE_F:
            case KeyEvent.KEYCODE_M:
            case KeyEvent.KEYCODE_S:
            case KeyEvent.KEYCODE_E:
            case KeyEvent.KEYCODE_L:
            case KeyEvent.KEYCODE_P:
            case KeyEvent.KEYCODE_O:
            case KeyEvent.KEYCODE_C:
            case KeyEvent.KEYCODE_T:
            case KeyEvent.KEYCODE_B:
                webView.evaluateJavascript(
                    "if(window.onRemoteKey)onRemoteKey(" + keyCode + ");",
                    null
                );
                return true;
        }
        return false;
    }

    @Override
    protected void onDestroy() {
        if (mpvBridge != null) {
            mpvBridge.unregister();
        }
        if (mpvView != null) {
            mpvView.destroy();
        }
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
