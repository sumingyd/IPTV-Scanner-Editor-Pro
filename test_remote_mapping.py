import requests
import json
import os
from channel_mappings import load_remote_mappings, ChannelMappingManager

def test_remote_mapping():
    print("测试远程映射加载...")
    
    # 测试直接请求
    url = "https://raw.githubusercontent.com/sumingyd/IPTV-Scanner-Editor-Pro/main/local_channel_mappings.csv"
    print(f"测试URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"HTTP状态码: {response.status_code}")
        print(f"内容长度: {len(response.text)}")
        print(f"内容前100字符: {response.text[:100]}")
        
        # 保存到临时文件测试解析
        temp_file = "test_remote.csv"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        print(f"临时文件已创建: {temp_file}")
        
        # 测试解析
        from channel_mappings import load_mappings_from_file
        mappings = load_mappings_from_file(temp_file)
        print(f"解析出的映射数量: {len(mappings)}")
        
        # 显示前几个映射
        for i, (key, value) in enumerate(list(mappings.items())[:5]):
            print(f"映射 {i+1}: {key} -> {value}")
        
        # 清理临时文件
        os.remove(temp_file)
        
    except Exception as e:
        print(f"请求失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试load_remote_mappings函数...")
    try:
        mappings = load_remote_mappings()
        print(f"load_remote_mappings返回的映射数量: {len(mappings)}")
    except Exception as e:
        print(f"load_remote_mappings失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试ChannelMappingManager...")
    try:
        manager = ChannelMappingManager()
        print(f"管理器加载的远程映射数量: {len(manager.remote_mappings)}")
        print(f"管理器组合映射数量: {len(manager.combined_mappings)}")
    except Exception as e:
        print(f"ChannelMappingManager失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_remote_mapping()
