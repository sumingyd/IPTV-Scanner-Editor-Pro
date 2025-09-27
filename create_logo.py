#!/usr/bin/env python3
"""
IPTV Scanner Editor Pro Logo Generator
生成专业的程序logo
"""

import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np

def create_logo():
    """创建程序logo"""
    # 设置logo尺寸
    size = (512, 512)
    
    # 创建透明背景
    logo = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(logo)
    
    # 定义颜色方案
    primary_color = (41, 128, 185)    # 蓝色 - 代表专业和技术
    secondary_color = (52, 152, 219)  # 浅蓝色
    accent_color = (231, 76, 60)      # 红色 - 代表扫描和活动
    text_color = (44, 62, 80)         # 深蓝色 - 文字颜色
    
    # 绘制背景圆形
    center = (size[0] // 2, size[1] // 2)
    radius = 200
    
    # 渐变背景
    for r in range(radius, 0, -1):
        alpha = int(255 * (r / radius))
        color = (primary_color[0], primary_color[1], primary_color[2], alpha)
        draw.ellipse([center[0]-r, center[1]-r, center[0]+r, center[1]+r], 
                    fill=color, outline=None)
    
    # 绘制扫描雷达效果
    # 外圈
    draw.ellipse([center[0]-180, center[1]-180, center[0]+180, center[1]+180], 
                outline=secondary_color, width=8)
    
    # 内圈
    draw.ellipse([center[0]-120, center[1]-120, center[0]+120, center[1]+120], 
                outline=secondary_color, width=6)
    
    # 扫描线
    for angle in range(0, 360, 30):
        rad = np.radians(angle)
        x1 = center[0] + 120 * np.cos(rad)
        y1 = center[1] + 120 * np.sin(rad)
        x2 = center[0] + 180 * np.cos(rad)
        y2 = center[1] + 180 * np.sin(rad)
        draw.line([x1, y1, x2, y2], fill=accent_color, width=3)
    
    # 中心点
    draw.ellipse([center[0]-20, center[1]-20, center[0]+20, center[1]+20], 
                fill=accent_color, outline=text_color, width=2)
    
    # 添加电视图标元素
    # 电视屏幕
    tv_width, tv_height = 120, 80
    tv_x, tv_y = center[0] - tv_width//2, center[1] - tv_height//2 - 10
    
    # 电视边框
    draw.rectangle([tv_x-5, tv_y-5, tv_x+tv_width+5, tv_y+tv_height+5], 
                  fill=text_color, outline=None)
    
    # 电视屏幕
    draw.rectangle([tv_x, tv_y, tv_x+tv_width, tv_y+tv_height], 
                  fill=secondary_color, outline=None)
    
    # 电视底座
    draw.rectangle([center[0]-30, tv_y+tv_height+5, center[0]+30, tv_y+tv_height+20], 
                  fill=text_color, outline=None)
    
    # 添加信号波
    for i, wave_height in enumerate([15, 25, 35, 25, 15]):
        wave_x = tv_x + tv_width + 10 + i * 15
        wave_y1 = center[1] - wave_height//2
        wave_y2 = center[1] + wave_height//2
        draw.line([wave_x, wave_y1, wave_x, wave_y2], fill=accent_color, width=4)
    
    # 添加文字
    try:
        # 尝试使用系统字体
        font_large = ImageFont.truetype("arial.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        # 如果系统字体不可用，使用默认字体
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # 程序名称
    text = "IPTV Pro"
    bbox = draw.textbbox((0, 0), text, font=font_large)
    text_width = bbox[2] - bbox[0]
    text_x = center[0] - text_width // 2
    text_y = center[1] + 120
    
    draw.text((text_x, text_y), text, fill=text_color, font=font_large)
    
    # 副标题
    subtitle = "Scanner & Editor"
    bbox = draw.textbbox((0, 0), subtitle, font=font_small)
    text_width = bbox[2] - bbox[0]
    text_x = center[0] - text_width // 2
    text_y = center[1] + 160
    
    draw.text((text_x, text_y), subtitle, fill=text_color, font=font_small)
    
    return logo

def save_logo_variants(logo):
    """保存不同格式的logo"""
    # 保存为PNG（透明背景）
    logo.save('logo.png', 'PNG')
    print("✓ Logo已保存为 logo.png")
    
    # 保存为ICO（Windows图标）
    # 创建不同尺寸的ICO
    ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_images = []
    
    for size in ico_sizes:
        resized_logo = logo.resize(size, Image.Resampling.LANCZOS)
        ico_images.append(resized_logo)
    
    ico_images[0].save('logo.ico', format='ICO', sizes=ico_sizes)
    print("✓ Logo已保存为 logo.ico")
    
    # 保存为正方形版本（用于应用商店等）
    square_logo = logo.resize((256, 256), Image.Resampling.LANCZOS)
    square_logo.save('logo_square.png', 'PNG')
    print("✓ Logo已保存为 logo_square.png")

def create_simple_logo():
    """创建简化版logo（用于小图标）"""
    size = (64, 64)
    logo = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(logo)
    
    # 简化颜色方案
    primary_color = (41, 128, 185)
    accent_color = (231, 76, 60)
    
    # 绘制简化图标
    center = (size[0] // 2, size[1] // 2)
    
    # 电视图标
    tv_width, tv_height = 30, 20
    tv_x, tv_y = center[0] - tv_width//2, center[1] - tv_height//2
    
    # 电视屏幕
    draw.rectangle([tv_x, tv_y, tv_x+tv_width, tv_y+tv_height], 
                  fill=primary_color, outline=None)
    
    # 信号波
    for i in range(3):
        wave_x = tv_x + tv_width + 2 + i * 4
        wave_height = 8 + i * 4
        wave_y1 = center[1] - wave_height//2
        wave_y2 = center[1] + wave_height//2
        draw.line([wave_x, wave_y1, wave_x, wave_y2], fill=accent_color, width=2)
    
    return logo

if __name__ == "__main__":
    print("正在生成IPTV Scanner Editor Pro Logo...")
    
    # 创建主logo
    main_logo = create_logo()
    save_logo_variants(main_logo)
    
    # 创建简化版logo
    simple_logo = create_simple_logo()
    simple_logo.save('logo_simple.png', 'PNG')
    print("✓ 简化版Logo已保存为 logo_simple.png")
    
    print("\n🎉 Logo生成完成！")
    print("生成的文件：")
    print("  - logo.png (512x512 PNG，透明背景)")
    print("  - logo.ico (多尺寸Windows图标)")
    print("  - logo_square.png (256x256 正方形版本)")
    print("  - logo_simple.png (64x64 简化版本)")
    
    print("\n💡 使用建议：")
    print("  - logo.ico 用于程序窗口图标")
    print("  - logo.png 用于关于对话框")
    print("  - logo_simple.png 用于工具栏小图标")
    print("  - logo_square.png 用于应用商店展示")
