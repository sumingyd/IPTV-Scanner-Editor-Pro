#!/usr/bin/env python3
"""
简单UI更新测试 - 验证频道添加和更新时UI是否实时刷新
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from PyQt6 import QtWidgets, QtCore, QtGui
from channel_model import ChannelListModel
import time

class TestWindow(QtWidgets.QMainWindow):
    """测试窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UI更新测试")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建频道模型
        self.model = ChannelListModel()
        
        # 创建表格视图
        self.table_view = QtWidgets.QTableView()
        self.table_view.setModel(self.model)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        
        # 创建按钮
        self.add_single_btn = QtWidgets.QPushButton("添加单个频道")
        self.add_batch_btn = QtWidgets.QPushButton("添加批量频道")
        self.update_channel_btn = QtWidgets.QPushButton("更新频道信息")
        self.clear_btn = QtWidgets.QPushButton("清空列表")
        
        # 创建状态标签
        self.status_label = QtWidgets.QLabel("就绪")
        
        # 布局
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QtWidgets.QVBoxLayout()
        button_layout = QtWidgets.QHBoxLayout()
        
        button_layout.addWidget(self.add_single_btn)
        button_layout.addWidget(self.add_batch_btn)
        button_layout.addWidget(self.update_channel_btn)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        layout.addWidget(self.table_view)
        layout.addWidget(self.status_label)
        
        central_widget.setLayout(layout)
        
        # 连接信号
        self.add_single_btn.clicked.connect(self.add_single_channel)
        self.add_batch_btn.clicked.connect(self.add_batch_channels)
        self.update_channel_btn.clicked.connect(self.update_channel_info)
        self.clear_btn.clicked.connect(self.clear_channels)
        
        # 计数器
        self.channel_counter = 0
        
    def add_single_channel(self):
        """添加单个频道"""
        self.channel_counter += 1
        channel = {
            'url': f'http://example.com/single{self.channel_counter}.m3u8',
            'name': f'单个频道{self.channel_counter}',
            'raw_name': f'单个频道{self.channel_counter}',
            'valid': True,
            'latency': 100,
            'resolution': '1920x1080',
            'status': '有效',
            'group': '测试分组',
            'logo_url': f'http://example.com/logo{self.channel_counter}.png'
        }
        
        print(f"添加单个频道: {channel['name']}")
        self.model.add_channel(channel)
        
        # 强制刷新UI
        self.model.update_view()
        
        self.status_label.setText(f"已添加单个频道: {channel['name']}")
        print(f"频道数量: {self.model.rowCount()}")
        
    def add_batch_channels(self):
        """添加批量频道"""
        channels = []
        for i in range(3):
            self.channel_counter += 1
            channel = {
                'url': f'http://example.com/batch{self.channel_counter}.m3u8',
                'name': f'批量频道{self.channel_counter}',
                'raw_name': f'批量频道{self.channel_counter}',
                'valid': True,
                'latency': 100 + i,
                'resolution': '1920x1080',
                'status': '有效',
                'group': '批量分组',
                'logo_url': f'http://example.com/logo_batch{self.channel_counter}.png'
            }
            channels.append(channel)
        
        print(f"批量添加 {len(channels)} 个频道")
        self.model.add_channel({'batch': True, 'channels': channels})
        
        # 强制刷新UI
        self.model.update_view()
        
        self.status_label.setText(f"已批量添加 {len(channels)} 个频道")
        print(f"频道数量: {self.model.rowCount()}")
        
    def update_channel_info(self):
        """更新频道信息"""
        if self.model.rowCount() == 0:
            self.status_label.setText("没有频道可更新")
            return
            
        # 更新第一个频道
        new_channel_info = {
            'url': 'http://example.com/updated.m3u8',
            'name': '更新后的频道',
            'raw_name': '更新后的频道',
            'valid': True,
            'latency': 50,
            'resolution': '1280x720',
            'status': '有效',
            'group': '更新后的分组',
            'logo_url': 'http://example.com/updated_logo.png'
        }
        
        print("更新频道信息...")
        success = self.model.update_channel(0, new_channel_info)
        
        if success:
            self.status_label.setText("频道信息更新成功")
            print("频道信息更新成功")
        else:
            self.status_label.setText("频道信息更新失败")
            print("频道信息更新失败")
            
    def clear_channels(self):
        """清空频道列表"""
        self.model.clear()
        self.status_label.setText("频道列表已清空")
        print("频道列表已清空")

def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    
    window = TestWindow()
    window.show()
    
    print("UI更新测试程序已启动")
    print("请点击按钮测试频道添加和更新功能")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
