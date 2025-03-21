from PIL import Image
 
def remove_iccp_profile(image_path):
    with Image.open(image_path) as img:
        if img.info.get('icc_profile'):
            img.save(image_path, icc_profile=None)
            print(f"Warning fixed for {image_path}")
        else:
            print(f"No ICC profile found in {image_path}")
 
# 使用方法，例如处理当前目录下所有PNG图片
import os
for filename in os.listdir('.'):
    if filename.endswith(".png"):
        remove_iccp_profile(filename)