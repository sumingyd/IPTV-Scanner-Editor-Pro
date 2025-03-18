# IPTV-Scanner Editor Pro / IPTV专业管理器
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

专业的IPTV管理工具，集播放列表编辑、EPG集成和智能扫描于一体

---

## 🌟 功能特性
### 🎯 核心功能
- **智能播放器集成**  
  支持直接播放m3u/m3u8格式播放列表，实时显示分辨率/帧率
- **高级播放列表编辑器**  
  📝 支持频道增删改、排序分组、属性批量修改
- **EPG智能匹配系统**  
  📺 修改频道名称时自动匹配EPG节目单建议列表
- **直播源扫描引擎**  
  🔍 自定义IP段/端口范围扫描，自动验证有效性并识别分辨率
- **历史版本管理**  
  ⏳ 支持播放列表修改历史记录与版本回滚

### 🚀 进阶功能
- 多播放列表同时管理（Tab式界面）
- 正则表达式批量重命名
- 扫描任务队列管理
- 硬件加速播放支持
- 代理服务器配置

## 📥 安装指南

- 克隆仓库
```ssh
git clone https://github.com/yourusername/IPTV-Scanner-Editor-Pro.git
```
- 安装依赖
```ssh
pip install -r requirements.txt
```
- 启动程序
```ssh
python main.py
```
## 🖥 使用说明

### 播放列表管理
- 示例：加载播放列表

manager = PlaylistManager()
playlist = manager.load("example.m3u")

- 示例：EPG智能匹配

channel.rename_with_epg_suggestions(epg_provider="huoshan")

- 直播源扫描

scanner = SourceScanner(
    ip_range="192.168.1.1-192.168.1.255",
    ports=[8000, 8001, 1935],
    timeout=2.0
)
valid_sources = scanner.start_scan()

## 📷 界面预览

功能完善的播放列表编辑器


智能扫描结果展示（有效源标记为绿色）

## 🤝 参与贡献

欢迎通过Issue提交建议或PR：

Fork项目仓库

创建功能分支 (git checkout -b feature/AmazingFeature)

提交更改 (git commit -m 'Add some AmazingFeature')

推送分支 (git push origin feature/AmazingFeature)

新建Pull Request

##📜 开源协议

本项目基于 MIT License 开源
