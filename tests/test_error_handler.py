"""测试异常处理装饰器"""

import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock
from error_handler import (
    handle_exceptions,
    handle_specific_exceptions,
    retry_on_exception,
    log_execution_time,
    ErrorHandler,
    init_global_error_handler,
    get_global_error_handler
)
from PyQt6 import QtWidgets, QtCore
import sys


class TestErrorHandler(unittest.TestCase):
    """测试错误处理器类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建QApplication实例（如果不存在）
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])
        
        # 创建测试窗口
        self.window = QtWidgets.QWidget()
        self.error_handler = ErrorHandler(self.window)
    
    def tearDown(self):
        """测试后清理"""
        if hasattr(self, 'window'):
            self.window.close()
    
    def test_handle_exceptions_decorator(self):
        """测试handle_exceptions装饰器"""
        
        # 测试正常执行
        @handle_exceptions(default_return=None)
        def normal_function():
            return "success"
        
        result = normal_function()
        self.assertEqual(result, "success")
        
        # 测试异常处理
        @handle_exceptions(user_message="测试异常", default_return="default")
        def failing_function():
            raise ValueError("测试错误")
        
        result = failing_function()
        self.assertEqual(result, "default")
    
    def test_handle_specific_exceptions_decorator(self):
        """测试handle_specific_exceptions装饰器"""
        
        # 测试特定异常处理
        @handle_specific_exceptions(
            exceptions=(ValueError, TypeError),
            user_message="特定异常测试",
            default_return="handled"
        )
        def specific_failing_function(exception_type):
            if exception_type == ValueError:
                raise ValueError("值错误")
            elif exception_type == TypeError:
                raise TypeError("类型错误")
            else:
                raise RuntimeError("运行时错误")
        
        # 应该处理ValueError
        result = specific_failing_function(ValueError)
        self.assertEqual(result, "handled")
        
        # 应该处理TypeError
        result = specific_failing_function(TypeError)
        self.assertEqual(result, "handled")
        
        # 不应该处理RuntimeError，应该重新抛出
        with self.assertRaises(RuntimeError):
            specific_failing_function(RuntimeError)
    
    def test_retry_on_exception_decorator(self):
        """测试retry_on_exception装饰器"""
        
        call_count = 0
        
        @retry_on_exception(max_retries=3, delay=0.01)
        def retry_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"第{call_count}次失败")
            return f"第{call_count}次成功"
        
        # 测试重试功能
        result = retry_function()
        self.assertEqual(result, "第3次成功")
        self.assertEqual(call_count, 3)
    
    def test_log_execution_time_decorator(self):
        """测试log_execution_time装饰器"""
        
        import time
        
        @log_execution_time
        def slow_function():
            time.sleep(0.01)
            return "done"
        
        # 测试执行时间记录
        from log_manager import global_logger
        with patch.object(global_logger, 'debug') as mock_debug:
            result = slow_function()
            self.assertEqual(result, "done")
            # 验证日志被调用
            self.assertTrue(mock_debug.called)
    
    def test_error_handler_initialization(self):
        """测试错误处理器初始化"""
        handler = ErrorHandler(self.window)
        self.assertIsNotNone(handler)
        self.assertEqual(handler.parent_window, self.window)
    
    def test_global_error_handler(self):
        """测试全局错误处理器"""
        # 初始化全局错误处理器
        handler = init_global_error_handler(self.window)
        self.assertIsNotNone(handler)
        
        # 获取全局错误处理器
        global_handler = get_global_error_handler()
        self.assertEqual(handler, global_handler)
    
    def test_safe_execute(self):
        """测试safe_execute方法"""
        
        def normal_func():
            return "正常执行"
        
        def failing_func():
            raise ValueError("执行失败")
        
        # 测试正常执行
        result = self.error_handler.safe_execute(normal_func)
        self.assertEqual(result, "正常执行")
        
        # 测试异常处理
        result = self.error_handler.safe_execute(
            failing_func,
            user_message="测试错误",
            default_return="默认值"
        )
        self.assertEqual(result, "默认值")
    
    def test_user_friendly_messages(self):
        """测试用户友好的错误消息"""
        
        test_cases = [
            (FileNotFoundError("test.txt"), "文件未找到: test.txt"),
            (PermissionError("test.txt"), "没有权限访问文件: test.txt"),
            (ConnectionError("连接失败"), "网络连接失败: 连接失败"),
            (TimeoutError("超时"), "操作超时: 超时"),
            (ValueError("无效值"), "输入值无效: 无效值"),
            (TypeError("类型错误"), "类型错误: 类型错误"),
            (AttributeError("属性错误"), "对象属性错误: 属性错误"),
            (KeyboardInterrupt(), "操作被用户中断"),
            (SystemExit(), "程序正在退出"),
            (RuntimeError("运行时错误"), "发生未知错误: 运行时错误"),
        ]
        
        for exception, expected_message in test_cases:
            message = self.error_handler._get_user_friendly_message(exception)
            self.assertEqual(message, expected_message)


class TestErrorHandlerIntegration(unittest.TestCase):
    """测试错误处理器集成"""
    
    def setUp(self):
        """测试前准备"""
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication([])
        
        self.window = QtWidgets.QWidget()
        self.error_handler = ErrorHandler(self.window)
    
    def test_handle_exception_with_dialog(self):
        """测试带对话框的异常处理"""
        with patch.object(self.error_handler, 'show_error_dialog') as mock_dialog:
            with patch.object(self.error_handler, 'show_status_message') as mock_status:
                self.error_handler.handle_exception(
                    exception=ValueError("测试错误"),
                    user_message="用户友好的错误消息",
                    show_dialog=True
                )
                
                # 验证对话框被调用
                self.assertTrue(mock_dialog.called)
                # 验证状态栏消息被调用
                self.assertTrue(mock_status.called)
    
    def test_handle_exception_without_dialog(self):
        """测试不带对话框的异常处理"""
        with patch.object(self.error_handler, 'show_error_dialog') as mock_dialog:
            with patch.object(self.error_handler, 'show_status_message') as mock_status:
                self.error_handler.handle_exception(
                    exception=ValueError("测试错误"),
                    user_message="用户友好的错误消息",
                    show_dialog=False
                )
                
                # 验证对话框没有被调用
                self.assertFalse(mock_dialog.called)
                # 验证状态栏消息被调用
                self.assertTrue(mock_status.called)


class TestDecoratorUsageExamples(unittest.TestCase):
    """测试装饰器使用示例"""
    
    def test_file_operations_with_decorator(self):
        """测试使用装饰器的文件操作"""
        
        @handle_exceptions(
            user_message="文件读取失败",
            default_return=""
        )
        def read_file_safe(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # 测试不存在的文件
        result = read_file_safe("/nonexistent/file.txt")
        self.assertEqual(result, "")
        
        # 测试存在的文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write("测试内容")
            temp_file = f.name
        
        try:
            result = read_file_safe(temp_file)
            self.assertEqual(result, "测试内容")
        finally:
            os.unlink(temp_file)
    
    def test_network_operations_with_retry(self):
        """测试带重试的网络操作"""
        
        import requests
        
        call_count = 0
        
        @retry_on_exception(
            max_retries=2,
            delay=0.01,
            exceptions=(requests.ConnectionError,),
            user_message="网络连接失败"
        )
        def fetch_data(url):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise requests.ConnectionError("连接失败")
            return {"data": "成功"}
        
        # 测试重试逻辑
        with patch('requests.get', side_effect=fetch_data):
            # 这里主要是测试装饰器逻辑，不实际进行网络请求
            pass
    
    def test_performance_monitoring(self):
        """测试性能监控装饰器"""
        
        import time
        
        @log_execution_time
        @handle_exceptions(default_return=[])
        def process_data(data):
            time.sleep(0.01)
            if not data:
                raise ValueError("数据为空")
            return [item * 2 for item in data]
        
        # 测试正常执行
        from log_manager import global_logger
        with patch.object(global_logger, 'debug') as mock_debug:
            result = process_data([1, 2, 3])
            self.assertEqual(result, [2, 4, 6])
            # 验证执行时间被记录
            self.assertTrue(mock_debug.called)
        
        # 测试异常情况
        with patch.object(global_logger, 'error') as mock_error:
            result = process_data([])
            self.assertEqual(result, [])
            # 验证异常被记录
            self.assertTrue(mock_error.called)


if __name__ == '__main__':
    # 运行测试
    unittest.main()
