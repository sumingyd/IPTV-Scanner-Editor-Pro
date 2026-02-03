#!/usr/bin/env python3
"""
测试验证服务优化效果
"""

import time
from services.validator_service import StreamValidator

def test_validation_speed():
    """测试验证速度"""
    validator = StreamValidator()
    
    # 测试URL列表（示例）
    test_urls = [
        # 有效URL示例（需要替换为实际可用的URL）
        "http://example.com/stream.m3u8",
        "rtp://239.1.1.1:1234",
        # 无效URL示例
        "http://invalid.example.com/notfound.m3u8",
        "rtp://192.168.99.99:9999"
    ]
    
    print("=== 验证服务优化测试 ===")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    for i, url in enumerate(test_urls, 1):
        print(f"测试 {i}/{len(test_urls)}: {url}")
        
        # 测试不同超时时间
        for timeout in [3, 5, 10, 15]:
            start_time = time.time()
            try:
                result = validator.validate_stream(url, timeout=timeout)
                elapsed = time.time() - start_time
                
                print(f"  超时{timeout}秒: {'有效' if result['valid'] else '无效'} "
                      f"(耗时: {elapsed:.2f}秒, 延迟: {result.get('latency', 0)}ms)")
                
                if result.get('error'):
                    print(f"    错误: {result['error'][:100]}")
                if result.get('warning'):
                    print(f"    警告: {result['warning'][:100]}")
                    
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  超时{timeout}秒: 异常 - {str(e)[:100]} (耗时: {elapsed:.2f}秒)")
        
        print()

def test_tcp_check():
    """测试TCP快速检查"""
    validator = StreamValidator()
    
    test_urls = [
        "http://www.baidu.com:80",
        "https://www.google.com:443",
        "rtp://239.1.1.1:1234",  # UDP协议，应该跳过TCP检查
        "http://invalid-host-9999.example.com:80"  # 应该失败
    ]
    
    print("=== TCP快速检查测试 ===")
    
    for url in test_urls:
        start_time = time.time()
        try:
            result = validator._quick_tcp_check(url, timeout=2)
            elapsed = time.time() - start_time
            
            print(f"{url}: {'成功' if result else '失败'} (耗时: {elapsed:.3f}秒)")
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"{url}: 异常 - {str(e)[:50]} (耗时: {elapsed:.3f}秒)")

def performance_comparison():
    """性能对比：优化前 vs 优化后"""
    validator = StreamValidator()
    
    # 模拟URL（使用本地回环地址避免网络影响）
    test_url = "http://127.0.0.1:8080/test.m3u8"
    
    print("=== 性能对比测试 ===")
    
    # 测试优化后的方法
    print("优化后验证方法:")
    for timeout in [3, 5, 10]:
        start_time = time.time()
        try:
            result = validator.validate_stream(test_url, timeout=timeout)
            elapsed = time.time() - start_time
            
            print(f"  超时{timeout}秒: 耗时{elapsed:.2f}秒, "
                  f"结果: {'有效' if result['valid'] else '无效'}")
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  超时{timeout}秒: 异常 ({elapsed:.2f}秒) - {str(e)[:50]}")
    
    print("\n关键优化点:")
    print("1. 添加TCP快速检查层 - 快速过滤无效URL")
    print("2. 减少探测大小 - 从10MB减少到500KB")
    print("3. 优化ffprobe参数 - 只获取必要信息")
    print("4. 移除'可接受错误'逻辑 - 减少错判")
    print("5. 使用动态超时 - 从配置文件读取")

if __name__ == "__main__":
    print("开始验证服务优化测试...")
    print("=" * 50)
    
    # 运行测试
    test_tcp_check()
    print()
    
    performance_comparison()
    print()
    
    # 注释掉实际网络测试，避免长时间等待
    # test_validation_speed()
    
    print("=" * 50)
    print("测试完成！")
    print("\n优化总结:")
    print("✅ 添加了TCP快速检查层，快速过滤无效URL")
    print("✅ 减少了ffprobe探测大小，提高验证速度")
    print("✅ 优化了ffprobe命令参数，减少不必要的数据获取")
    print("✅ 移除了'可接受错误'逻辑，减少错判")
    print("✅ 保持超时时间动态配置，从UI控件读取")
    print("\n预期效果:")
    print("1. 扫描速度提升：无效URL在TCP检查阶段快速失败")
    print("2. 准确性提高：严格判断ffprobe返回码，减少错判")
    print("3. 资源使用减少：更小的探测大小，更少的系统资源占用")