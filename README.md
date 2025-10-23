# IPTV Scanner Editor Pro / IPTV 专业扫描编辑工具

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0+-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

一个功能强大的 IPTV 频道扫描、验证、编辑和管理工具，支持智能频道发现、批量验证、视频播放和高级频道管理功能。

## ✨ 主要特性

### 🔍 智能频道扫描
- **范围扫描**: 支持 IP 范围扫描（如 `239.1.1.[1-255]:5002`）
- **多协议支持**: 支持单播、组播、HTTP/HTTPS 流链接
- **自定义参数**: 可设置超时时间、线程数、用户代理等
- **智能解析**: 支持复杂地址格式和多个范围的地址

### ✅ 高级流验证
- **批量检测**: 打开播放列表后批量检测频道有效性
- **实时统计**: 显示验证进度、有效/无效频道数量
- **性能指标**: 检测延迟、分辨率等流媒体参数

### 🎯 智能频道管理
- **拖拽排序**: 支持拖拽调整频道顺序
- **右键操作**: 支持删除、复制频道名及URL
- **智能映射**: 自动匹配频道名、LOGO、分组信息
- **分组管理**: 支持频道分组和分类显示

### 🎬 集成视频播放
- **双击播放**: 双击频道列表直接播放当前频道
- **播放控制**: 支持播放、暂停、停止、音量调节
- **多格式支持**: 支持多种视频流格式

### ⚙️ 专业工具集成
- **URL解析器**: 支持复杂地址格式解析
- **频道映射管理器**: 可视化编辑映射规则
- **错误处理系统**: 智能恢复和错误报告
- **性能优化**: 支持大规模频道列表处理

## 🚀 快速开始

### 下载安装

#### 方式一：直接下载可执行文件（推荐）
1. 前往 [Releases 页面](https://github.com/sumingyd/IPTV-Scanner-Editor-Pro/releases)
2. 下载最新版本的 `IPTV-Scanner-Editor-Pro-*.exe` 文件
3. 双击运行即可使用

#### 方式二：从源码运行
```bash
# 克隆仓库
git clone https://github.com/sumingyd/IPTV-Scanner-Editor-Pro.git
cd IPTV-Scanner-Editor-Pro

# 安装依赖
pip install -r requirements.txt

# 运行程序
python main.py
```

### 系统要求
- **操作系统**: Windows 10/11
- **Python**: 3.8+（仅源码运行需要）
- **内存**: 至少 2GB RAM
- **网络**: 需要网络连接用于频道扫描和验证

## 📖 使用指南

### 基本使用流程

1. **启动程序**
   - 双击可执行文件或运行 `python main.py`
   - 等待启动动画完成

2. **频道扫描**
   - 在扫描设置中输入地址格式（如 `239.1.1.[1-255]:5002`）
   - 设置超时时间和线程数
   - 点击"完整扫描"开始扫描

3. **列表管理**
   - 打开现有播放列表进行批量验证
   - 使用右键菜单管理频道
   - 拖拽调整频道顺序

4. **视频播放**
   - 双击频道列表中的任意频道开始播放
   - 使用播放控制按钮进行播放控制

### 高级功能

#### 智能频道映射
- 程序会自动尝试获取频道名
- 通过映射文件匹配频道名、LOGO、分组
- 频道名的映射文件在仓库，可以直接去仓库提交修改
- 频道的logo可以直接在仓库提交上传到logo文件夹

#### 批量验证
- 打开播放列表后点击"检测有效性"按钮
- 程序会批量检测所有频道的有效性
- 显示详细的统计信息和进度

#### 配置管理
- 配置文件(config.ini)自动保存在程序目录
- 日志文件(app.log)自动轮转，最大5MB保留3个
- 所有设置自动保存，无需手动操作

## 🛠️ 开发说明

### 项目结构
```
IPTV-Scanner-Editor-Pro/
├── main.py                 # 主程序入口
├── ui_builder.py           # UI构建器
├── scanner_controller.py   # 扫描控制器
├── player_controller.py    # 播放控制器
├── channel_model.py        # 频道数据模型
├── config_manager.py       # 配置管理器
├── language_manager.py     # 语言管理器
├── about_dialog.py         # 关于对话框
├── requirements.txt        # Python依赖
├── pyproject.toml         # 项目配置
└── README.md              # 项目说明
```

### 依赖说明
- **PyQt6**: GUI框架
- **aiohttp**: 异步HTTP客户端
- **vlc**: 视频播放支持
- **ffmpeg**: 流媒体处理

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 如何贡献
1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 提交频道映射
- 频道名映射文件在仓库中
- 可以直接去仓库提交修改
- 频道的logo可以直接在仓库提交上传到logo文件夹

## 📞 联系与支持

### QQ群
- **群号**: 757694351
- **群链接**: [点击加入群聊](https://qm.qq.com/q/lVkybTyrdK)

### 问题反馈
- 使用 GitHub Issues 报告问题
- 在 QQ 群中交流使用经验

## 💖 支持项目

如果你觉得这个项目对你有帮助，欢迎赞赏支持开发！

| 微信赞赏 | 支付宝赞赏 |
|---------|-----------|
| ![](icons/wx.png) | ![](icons/zfb.jpg) |

## 📸 程序截图

![](icons/1.png)
![](icons/2.png)
![](icons/3.png)
![](icons/4.png)
![](icons/5.png)

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

感谢所有贡献者和用户的支持！

---

**注意**: 本工具仅供学习和研究使用，请遵守相关法律法规。
