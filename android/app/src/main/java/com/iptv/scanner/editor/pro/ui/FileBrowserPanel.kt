package com.iptv.scanner.editor.pro.ui

import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.Settings
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.LockOpen
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iptv.scanner.editor.pro.ui.theme.tvFocusBorder
import java.io.File

/**
 * 文件浏览器面板：当系统 SAF 不可用时（Android TV 无文件选择器），
 * 提供应用内文件浏览功能，让用户选择本地 M3U/M3U8 文件导入。
 *
 * 特性：
 * - 从外部存储根目录开始浏览
 * - 目录优先，文件按名称排序
 * - 高亮显示 M3U/M3U8 文件
 * - 支持 TV 遥控器 DPAD 焦点导航
 * - 点击 M3U 文件触发 importPlaylistFromFile
 */
@Composable
fun FileBrowserPanel(viewModel: AppViewModel) {
    val context = LocalContext.current
    var hasStoragePermission by remember { mutableStateOf(android.os.Environment.isExternalStorageManager()) }
    var currentPath by remember {
        val initDir = if (hasStoragePermission) {
            try {
                Environment.getExternalStorageDirectory().absolutePath
            } catch (e: Exception) {
                "/storage"
            }
        } else {
            context.getExternalFilesDir(null)?.absolutePath ?: context.filesDir.absolutePath
        }
        mutableStateOf(initDir)
    }

    // 应用从后台返回时（如从权限设置页面返回）重新检查权限
    val lifecycleOwner = androidx.compose.ui.platform.LocalLifecycleOwner.current
    androidx.compose.runtime.DisposableEffect(lifecycleOwner) {
        val observer = androidx.lifecycle.LifecycleEventObserver { _, event ->
            if (event == androidx.lifecycle.Lifecycle.Event.ON_RESUME) {
                val granted = android.os.Environment.isExternalStorageManager()
                if (granted && !hasStoragePermission) {
                    // 权限刚授予，切换到外部存储根目录
                    hasStoragePermission = true
                    try {
                        currentPath = Environment.getExternalStorageDirectory().absolutePath
                    } catch (e: Exception) {
                        currentPath = "/storage"
                    }
                }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    val items = remember(currentPath) {
        try {
            val dir = File(currentPath)
            val files = dir.listFiles()?.toMutableList() ?: mutableListOf()
            // 目录在前，文件在后；各自按名称排序
            files.sortWith(compareBy<File> { !it.isDirectory }.thenBy { it.name.lowercase() })
            files
        } catch (e: Exception) {
            emptyList()
        }
    }

    Surface(
        color = Color(0xF0161616),
        modifier = Modifier.fillMaxSize()
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            // 标题栏
            Surface(
                color = Color(0xFF1F1F1F),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "选择播放列表文件",
                            style = MaterialTheme.typography.titleMedium,
                            color = Color.White,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            text = currentPath,
                            color = Color(0xFF888888),
                            fontSize = 12.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    IconButton(
                        onClick = { viewModel.toggleFileBrowser() },
                        modifier = Modifier.tvFocusBorder()
                    ) {
                        Icon(Icons.Default.Close, contentDescription = "关闭", tint = Color.White)
                    }
                }
            }

            // 权限不足提示
            if (!hasStoragePermission) {
                Surface(
                    color = Color(0xFF2A2010),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "仅可浏览应用目录。授予权限后可浏览全部存储",
                            color = Color(0xFFFFB74D),
                            fontSize = 12.sp,
                            modifier = Modifier.weight(1f)
                        )
                        Button(
                            onClick = {
                                try {
                                    val intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
                                        data = Uri.parse("package:${context.packageName}")
                                    }
                                    context.startActivity(intent)
                                } catch (e: Exception) {
                                    // 某些设备不支持直接跳转，回退到通用设置
                                    try {
                                        context.startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
                                    } catch (e2: Exception) {
                                        viewModel.showOsd("无法打开权限设置", "请手动在系统设置中授予权限")
                                    }
                                }
                            },
                            modifier = Modifier.tvFocusBorder()
                        ) {
                            Icon(
                                Icons.Default.LockOpen,
                                contentDescription = null,
                                modifier = Modifier.padding(end = 4.dp)
                            )
                            Text("授予权限", fontSize = 12.sp)
                        }
                    }
                }
            }

            // 返回上一级
            val parentPath = remember(currentPath) {
                val f = File(currentPath)
                f.parentFile?.absolutePath
            }
            if (parentPath != null) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { currentPath = parentPath }
                        .padding(horizontal = 16.dp, vertical = 10.dp)
                        .tvFocusBorder(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = "返回上一级",
                        tint = Color(0xFFCCCCCC),
                        modifier = Modifier.padding(end = 8.dp)
                    )
                    Text("返回上一级", color = Color(0xFFCCCCCC), fontSize = 14.sp)
                }
            }

            // 文件列表
            if (items.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = "此目录为空或无法访问",
                        color = Color(0xFF888888),
                        fontSize = 14.sp
                    )
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 4.dp)
                ) {
                    items(
                        items = items,
                        key = { it.absolutePath }
                    ) { file ->
                        val isM3u = file.extension.lowercase() in setOf("m3u", "m3u8")
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    if (file.isDirectory) {
                                        currentPath = file.absolutePath
                                    } else if (isM3u) {
                                        viewModel.importPlaylistFromFile(file.absolutePath)
                                    }
                                }
                                .padding(horizontal = 16.dp, vertical = 10.dp)
                                .tvFocusBorder(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = if (file.isDirectory) Icons.Default.Folder else Icons.Default.Description,
                                contentDescription = null,
                                tint = if (file.isDirectory) Color(0xFF66BB6A) else if (isM3u) Color(0xFFFFB74D) else Color(0xFF666666),
                                modifier = Modifier.padding(end = 10.dp)
                            )
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = file.name,
                                    color = if (isM3u) Color(0xFFFFB74D) else Color.White,
                                    fontSize = 14.sp,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                                if (!file.isDirectory) {
                                    val sizeText = remember(file.length()) {
                                        val len = file.length()
                                        when {
                                            len < 1024 -> "${len}B"
                                            len < 1024 * 1024 -> "${len / 1024}KB"
                                            else -> "${len / (1024 * 1024)}MB"
                                        }
                                    }
                                    Text(
                                        text = sizeText,
                                        color = Color(0xFF666666),
                                        fontSize = 11.sp
                                    )
                                }
                            }
                            if (isM3u) {
                                Text(
                                    text = "M3U",
                                    color = Color(0xFFFFB74D),
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    modifier = Modifier
                                        .background(Color(0x33FFB74D), RoundedCornerShape(4.dp))
                                        .padding(horizontal = 6.dp, vertical = 2.dp)
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
