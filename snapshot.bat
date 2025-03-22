# 在项目文件夹内右键新建文本文档，粘贴以下内容后保存为`snapshot.bat`
@echo off
echo 正在创建版本指纹...
git init > nul 2>&1
git add . > nul 2>&1
git commit -m "当前状态" > nul 2>&1
git bundle create project.bundle HEAD > nul 2>&1
echo 请将生成的 project.bundle 文件发给我
echo 文件大小: %~z0
pause