package com.iptv.scanner.editor.pro;

import android.annotation.SuppressLint;
import android.app.PictureInPictureParams;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import androidx.activity.OnBackPressedCallback;
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
    private static final int FILE_CHOOSER_REQUEST = 10011;

    private MPVView mpvView;
    private WebView webView;
    private MpvJsBridge mpvBridge;
    private Thread serverThread;
    private volatile boolean serverReady = false;

    /** 文件选择回调（HTML <input type="file"> 触发） */
    private ValueCallback<Uri[]> filePathCallback = null;

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
        /* 注入 Android JS 桥接（PiP、全屏等系统功能）
         * 注意：与 MpvJsBridge 注入的 "AndroidMpv" 区分，这里注入 "Android" */
        webView.addJavascriptInterface(new AndroidJsBridge(), "Android");
        // 立即显示加载提示页面，避免服务器启动期间黑屏
        showLoadingPage();
        startServer();
        waitForServerAndLoad();
    }

    /**
     * Android JS 桥接：提供系统功能给 HTML 调用
     * - enterPictureInPicture()：进入画中画模式
     * - toggleFullscreen()：切换沉浸式全屏
     * - isPiPSupported()：检查是否支持画中画
     */
    public class AndroidJsBridge {
        @JavascriptInterface
        public void enterPictureInPicture() {
            runOnUiThread(() -> {
                try {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                            && getPackageManager().hasSystemFeature(
                                    "android.software.picture_in_picture")) {
                        PictureInPictureParams.Builder builder =
                                new PictureInPictureParams.Builder();
                        enterPictureInPictureMode(builder.build());
                        Log.i(TAG, "Entered Picture-in-Picture mode");
                    } else {
                        Log.w(TAG, "PiP not supported on this device");
                        webView.evaluateJavascript(
                                "showOSD('画中画','当前设备不支持');", null);
                    }
                } catch (Exception e) {
                    Log.e(TAG, "enterPictureInPicture failed", e);
                    webView.evaluateJavascript(
                            "showOSD('画中画','进入失败: " + e.getMessage() + "');", null);
                }
            });
        }

        @JavascriptInterface
        public boolean isPiPSupported() {
            return Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                    && getPackageManager().hasSystemFeature(
                            "android.software.picture_in_picture");
        }

        @JavascriptInterface
        public boolean isInPiPMode() {
            return Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && isInPictureInPictureMode();
        }

        @JavascriptInterface
        public void toggleFullscreen() {
            runOnUiThread(() -> {
                try {
                    int ui = getWindow().getDecorView().getSystemUiVisibility();
                    int immersive = View.SYSTEM_UI_FLAG_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY;
                    if ((ui & View.SYSTEM_UI_FLAG_FULLSCREEN) == 0) {
                        /* 当前非全屏，进入全屏 */
                        getWindow().getDecorView().setSystemUiVisibility(
                                ui | immersive);
                    } else {
                        /* 当前全屏，退出 */
                        getWindow().getDecorView().setSystemUiVisibility(
                                ui & ~immersive);
                    }
                } catch (Exception e) {
                    Log.e(TAG, "toggleFullscreen failed", e);
                }
            });
        }
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
        /* 清除 WebView 的所有缓存和 Service Worker 缓存
         * 旧版 sw.js 使用 stale-while-revalidate 策略缓存了旧 HTML
         * 必须在每次启动时清除，确保加载最新版本 */
        webView.clearCache(true);
        webView.clearHistory();
        try {
            android.webkit.WebStorage.getInstance().deleteAllData();
        } catch (Exception e) {
            Log.w(TAG, "Clear WebStorage failed", e);
        }
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

            /**
             * 支持 HTML <input type="file">：打开系统文件选择器
             * 用于"打开本地播放列表"和"打开本地视频"功能
             */
            @Override
            public boolean onShowFileChooser(WebView webView,
                                              ValueCallback<Uri[]> filePathCallback,
                                              FileChooserParams fileChooserParams) {
                /* 如果已有未完成的回调，先取消 */
                if (MainActivity.this.filePathCallback != null) {
                    MainActivity.this.filePathCallback.onReceiveValue(null);
                }
                MainActivity.this.filePathCallback = filePathCallback;
                try {
                    Intent intent = fileChooserParams.createIntent();
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST);
                    return true;
                } catch (Exception e) {
                    Log.e(TAG, "onShowFileChooser failed", e);
                    MainActivity.this.filePathCallback = null;
                    return false;
                }
            }
        });

        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        /* 禁用 WebView 默认的焦点高亮
         * 遥控器方向键由 onKeyDown → dispatchKeyToJS → onRemoteKey 完全控制
         * 如果不禁用，WebView 内部的方向键焦点移动会显示一个选择框，干扰用户体验 */
        webView.setDefaultFocusHighlightEnabled(false);
        /* 通过 dispatchKeyEvent 拦截方向键，阻止 WebView 内部焦点导航
         * 注意：不能 setFocusable(false)，否则 Activity.onKeyDown 收不到按键事件 */
        webView.setOnKeyListener((v, keyCode, event) -> {
            // 方向键由 Activity.onKeyDown 统一处理，这里全部拦截
            // 避免 WebView 内部移动焦点显示选择框
            if (event.getAction() == KeyEvent.ACTION_DOWN) {
                switch (keyCode) {
                    case KeyEvent.KEYCODE_DPAD_UP:
                    case KeyEvent.KEYCODE_DPAD_DOWN:
                    case KeyEvent.KEYCODE_DPAD_LEFT:
                    case KeyEvent.KEYCODE_DPAD_RIGHT:
                    case KeyEvent.KEYCODE_DPAD_CENTER:
                        return true; // 消费事件，不让 WebView 处理
                }
            }
            return false;
        });
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
     *  - BACK 由 Java 层处理（关闭面板或退出应用）
     *  - DPAD/确认/菜单/媒体键转发给 HTML UI 的 onRemoteKey(code)
     *
     * BACK 键处理逻辑（与 PC 端行为一致）：
     * 1. 先异步询问 JS（onRemoteKey）是否处理了 BACK（关闭打开的面板）
     * 2. JS 返回 true 表示已处理（有面板关闭），不做任何事
     * 3. JS 返回 false 表示没有面板要关闭，调用 finish() 退出应用
     * 注意：不再调用 webView.goBack()，避免回到 about:blank 加载页面
     */
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            webView.evaluateJavascript(
                "if(window.onRemoteKey){onRemoteKey(" + keyCode + ");}else{false;}",
                value -> {
                    boolean handled = "true".equals(value);
                    if (!handled) {
                        // JS 没处理（没有面板要关闭），退出应用
                        finish();
                    }
                }
            );
            return true;  // 总是消费 BACK 事件，由异步回调决定是否退出
        }

        // 转发给 HTML UI 的遥控器按键
        if (dispatchKeyToJS(keyCode)) {
            // 阻止 WebView 默认的焦点导航（方向键选择框）
            // 让 JS 层的 onRemoteKey 完全控制按键行为
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

    /**
     * 处理文件选择结果（onShowFileChooser 启动的 Intent）
     * 将选择的文件 URL 传回给 WebView 的 filePathCallback
     */
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != FILE_CHOOSER_REQUEST) return;
        if (filePathCallback == null) return;
        Uri[] results = null;
        if (resultCode == RESULT_OK && data != null) {
            if (data.getData() != null) {
                results = new Uri[]{data.getData()};
            } else if (data.getClipData() != null) {
                int count = data.getClipData().getItemCount();
                results = new Uri[count];
                for (int i = 0; i < count; i++) {
                    results[i] = data.getClipData().getItemAt(i).getUri();
                }
            }
        }
        filePathCallback.onReceiveValue(results);
        filePathCallback = null;
    }

    /**
     * 用户按 HOME 键离开应用时自动进入 PiP（如果正在播放且支持 PiP）
     */
    @Override
    protected void onUserLeaveHint() {
        super.onUserLeaveHint();
        /* 仅在播放中才自动进入 PiP，避免空闲时也进入 */
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                && getPackageManager().hasSystemFeature(
                        "android.software.picture_in_picture")
                && mpvView != null) {
            try {
                PictureInPictureParams.Builder builder = new PictureInPictureParams.Builder();
                enterPictureInPictureMode(builder.build());
                Log.i(TAG, "Auto-entered PiP on user leave");
            } catch (Exception e) {
                Log.w(TAG, "Auto PiP failed: " + e.getMessage());
            }
        }
    }

    /**
     * PiP 模式变化回调：通知 JS 切换 UI 布局
     */
    @Override
    public void onPictureInPictureModeChanged(boolean isInPictureInPictureMode) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode);
        final String js = "if(window.onPiPChange)onPiPChange("
                + (isInPictureInPictureMode ? "true" : "false") + ");";
        webView.post(() -> webView.evaluateJavascript(js, null));
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
