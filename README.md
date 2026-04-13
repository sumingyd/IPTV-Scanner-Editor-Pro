# IPTV Scanner Editor Pro / IPTV 专业扫描编辑工具

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

一款功能全面的 IPTV 频道扫描、验证、播放和管理工具。集成 MPV 播放引擎，支持 EPG 电子节目单、频道台标自动加载、多主题界面、中英双语，从扫描到观看一站式完成。

## ✨ 核心功能

### 🎬 集成播放器
- **MPV 引擎驱动**：基于 libmpv 的高性能流媒体播放
- **完整播放控制**：播放（▶）、暂停（▮▮）、停止（■）、音量调节、静音切换
- **倍速播放**：循环切换多种播放速度
- **画面比例**：支持原始/16:9/4:3/填充等多种比例模式
- **全屏播放**：F11 或按钮一键全屏，Escape 退出
- **时移/回看**：支持直播时移和历史节目回看功能
- **悬浮控制面板**：底部浮动面板显示频道信息、节目进度、媒体参数
- **软件图标占位**：未播放时视频区域显示程序图标

### 📺 EPG 电子节目单
- **XMLTV 格式解析**：支持标准 XMLTV / JSON 格式 EPG 数据源
- **智能匹配**：优先 tvg-id → 其次 tvg-name → 最后频道名，全部模糊匹配
- **日期导航**：查看历史/当天/未来日期的节目安排
- **实时进度条**：显示当前节目的播放进度和时间轴
- **自动订阅**：配置 EPG 地址后自动下载更新，支持过期检测和 URL 变更感知
- **Gzip 兼容**：自动识别并解压 .gz 压缩的 EPG 数据

### 🖼️ 频道台标系统
- **在线加载**：自动从播放列表 tvg-logo URL 下载台标图片
- **异步下载**：后台线程加载，不阻塞 UI
- **本地缓存**：缓存机制，减少重复下载
- **智能预加载**：滚动列表时自动预加载可见区域台标
- **高清渲染**：High-DPI 屏幕支持，原图缓存 + 显示时按需缩放

### 🔍 智能频道扫描
- **范围扫描**：支持 IP 范围格式（如 `239.1.1.[1-255]:5002`）
- **多协议**：单播、组播、HTTP/HTTPS 流链接
- **自定义参数**：超时时间、线程数、用户代理等可调
- **追加扫描**：在现有列表基础上增量添加新频道
- **重试机制**：自动重试失败的频道，支持循环扫描模式

### ✅ 批量验证
- **有效性检测**：批量检测所有频道是否可用
- **性能指标**：检测延迟、分辨率等流媒体参数
- **实时统计**：进度条、有效/无效数量实时更新
- **智能重试**：自动重试验证失败的项

### 🎯 频道管理
- **M3U 播放列表**：支持标准 M3U/M3U8 格式导入导出
- **拖拽排序**：自由调整频道顺序
- **分组筛选**：下拉框按分组快速过滤频道
- **右键操作**：删除、复制频道名及 URL 等快捷操作
- **智能映射**：自动匹配频道名称、LOGO、分组信息
- **拼音排序**：中文频道名按拼音首字母排序
- **多格式导出**：M3U、TXT、Excel（需 openpyxl）

### 🎨 界面与体验
- **5 种主题**：
  - Dark（深色）
  - Light（浅色）
  - Dark Blue（暗蓝）
  - Neumorphic Light（新拟态亮色）
  - GitHub Dark（GitHub 暗色）
- **双语界面**：中文 / English 一键切换
- **三栏布局**：左侧 EPG 节目单 | 中间视频区域 | 右侧频道列表面板
- **悬浮面板**：EPG 列表、频道列表、播放控制面板均可独立开关
- **键盘快捷键**：空格播放/暂停、F11 全屏、E/L/M 切换面板、Ctrl+O 打开文件

### ⚙️ 订阅与自动化
- **播放列表订阅**：配置远程 M3U 地址，定时自动更新
- **EPG 订阅**：配置 EPG 数据源地址，自动下载解析
- **URL 变更检测**：订阅地址变更时强制重新下载
- **过期策略**：可配置的过期时间，到期自动刷新
- **配置持久化**：所有设置自动保存到 config.ini

## 🚀 快速开始

### 方式一：直接运行（推荐）
```bash
python pyqt_player.py
```

### 方式二：从源码安装依赖
```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python pyqt_player.py
```

### 系统要求
- **操作系统**：Windows 10/11
- **Python**：3.8+
- **内存**：2GB RAM 以上
- **网络**：需要网络连接用于频道扫描、EPG 下载和流媒体播放

## 📖 使用指南

### 基本流程

1. **打开播放列表**
   - 文件菜单 → 打开播放列表（Ctrl+O）
   - 支持 `.m3u` / `.m3u8` / `.txt` 格式

2. **配置订阅（可选）**
   - 工具菜单 → 订阅设置
   - 设置播放列表 URL 和 EPG 数据源地址
   - 配置过期时间和自动刷新策略

3. **播放频道**
   - 双击右侧频道列表中的任意频道开始播放
   - 底部控制面板：▶ 播放 / ▮▮ 暂停 / ■ 停止
   - 调节音量滑块、切换倍速、调整画面比例
   - 点击 ⛶ 全屏或按 F11

4. **查看节目单**
   - 左侧 EPG 面板显示当前选中频道的节目安排
   - 点击 ◀ / ▶ 切换日期查看不同天的节目
   - 进度条显示当前播放位置

5. **扫描新频道**
   - 工具菜单 → 扫描频道
   - 输入 IP 范围（如 `239.3.1.[1-100]:8000`）
   - 设置超时和线程数后开始扫描

6. **保存结果**
   - 文件菜单 → 另存为（Ctrl+S）
   - 选择 M3U / TXT / Excel 格式导出

### 高级功能

#### 频道映射
- 工具菜单 → 频道映射管理器
- 可视化编辑频道名称、LOGO、分组的映射规则
- 支持提交自定义映射到仓库

#### 主题与语言
- 语言菜单：切换 中文 / English
- 主题菜单：5 种主题即时切换，全局生效

#### 面板控制
- 视图菜单或快捷键：
  - **E** — 显示/隐藏 EPG 节目单面板
  - **L** — 显示/隐藏频道列表面板
  - **M** — 显示/隐藏播放控制面板

## 📁 项目结构

```
IPTV-Scanner-Editor-Pro/
├── pyqt_player.py              # 主窗口 & 播放器核心
├── main.py                     # 传统入口
├── requirements.txt            # Python 依赖
├── core/                       # 核心模块
│   ├── config_manager.py       # 配置管理（INI）
│   ├── epg_parser.py           # EPG 解析器（XMLTV/JSON）
│   ├── language_manager.py     # 多语言管理（内置 zh/en 翻译）
│   └── log_manager.py          # 日志管理
├── services/                   # 服务层
│   ├── mpv_player_service.py   # MPV 播放引擎（libmpv）
│   ├── scanner_service.py      # 频道扫描服务
│   ├── logo_cache_service.py   # 台标缓存服务（异步+DPI）
│   ├── validator_service.py    # 频道验证服务
│   ├── list_service.py         # 列表管理服务
│   └── epg_matcher.py          # EPG 模糊匹配引擎
├── ui/
│   ├── styles.py               # 5 套主题样式定义
│   ├── theme_manager.py        # 主题管理器
│   ├── floating_dialog.py      # 悬浮对话框基类
│   └── dialogs/
│       ├── about_dialog.py     # 关于对话框（含版本检查）
│       ├── scan_channel_dialog.py # 扫描频道对话框
│       └── mapping_manager_dialog.py # 映射管理器
├── utils/
│   └── thread_safety.py        # Qt 线程安全工具
├── resources/logo.ico          # 程序图标
├── cache/                      # 运行时缓存（自动生成）
│   ├── logo_cache/             # 台标图片缓存（从 tvg-logo URL 下载）
│   │   ├── meta.json           # 缓存元数据
│   │   └── *.png               # 各频道台标文件
│   ├── epg_cache.json          # EPG 数据缓存
│   └── playlist_cache.m3u      # 播放列表缓存
```

## 🛠️ 技术栈

| 组件 | 技术 |
|---|---|
| GUI 框架 | PyQt6 |
| 播放引擎 | libmpv (MPV) |
| HTTP 客户端 | requests |
| 图像处理 | Pillow |
| Excel 处理 | openpyxl |
| 拼音排序 | pypinyin |
| 异步 HTTP | aiohttp |

## 📸 程序截图

![](icons/1.png)
![](icons/2.png)
![](icons/3.png)
![](icons/4.png)
![](icons/5.png)
![](icons/6.png)

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/xxx`)
3. 提交更改 (`git commit -m 'Add xxx'`)
4. 推送分支 (`git push origin feature/xxx`)
5. 开启 Pull Request

### 提交内容
- **频道映射**：直接修改仓库中的映射文件并提交 PR
- **台标图片**：上传 PNG 格式的频道 Logo 到 `logo/` 或 `img/` 目录
- **语言翻译**：修改代码中的内置翻译（`BUILTIN_TRANSLATIONS`）

## 📞 联系方式

- **QQ群**：[757694351](https://qm.qq.com/q/lVkybTyrdK)
- **GitHub Issues**：[提交问题](https://github.com/sumingyd/IPTV-Scanner-Editor-Pro/issues)

## 💖 支持项目

如果你觉得这个项目对你有帮助，欢迎赞赏支持开发！

| 微信赞赏 | 支付宝赞赏 |
|---------|-----------|
| ![](icons/wx.png) | ![](icons/zfb.jpg) |

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。

---

*本工具仅供学习和研究使用，请遵守相关法律法规。*
