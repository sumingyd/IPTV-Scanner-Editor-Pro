package com.iptv.scanner.editor.pro.ui

/**
 * 更多功能面板集合（门面文件）。
 *
 * 原各面板 Composable 已按职责拆分到独立文件（同包）：
 * - [PanelHelpers]：通用组件（PanelScaffold/SectionLabel/DescText/LabeledSlider 等）
 * - PlayerSettingsPanels.kt：VideoSettingsPanel/AudioSettingsPanel/PlaybackPanel/ViewSettingsPanel/AvSyncPanel/ClipExportPanel
 * - SubtitlePanels.kt：SubtitleSettingsPanel/SubtitleSearchPanel
 * - ScreenshotPanels.kt：ScreenshotPanel
 * - NetworkPanels.kt：NetworkPanel
 * - SourceManagePanels.kt：MappingPanel/ScanPanel/RecentFilesPanel
 * - AboutPanels.kt：AboutPanel/UpdateDialog
 * - MiscPanels.kt：OpenUrlDialog/ExitConfirmDialog/ToolsPanel/ReminderPanel/ResumePanel/BookmarkPanel/AudioVisualizerPanel/LyricsPanel
 *
 * 所有面板都是全屏覆盖式 Surface，与 PlayerSettingsPanel 风格一致。
 * 对外调用方无感知（同包 top-level 函数，无需修改 import）。
 */
