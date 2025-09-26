import os
import sys
import logging

def _pyi_rth_vlc():
    """VLC运行时hook，确保打包后VLC能正常工作"""
    try:
        # 在打包模式下设置VLC插件路径
        if getattr(sys, 'frozen', False):
            # 获取临时解压目录
            vlc_dir = os.path.join(sys._MEIPASS, 'vlc')
            
            # 检查VLC目录是否存在
            if not os.path.exists(vlc_dir):
                logging.warning(f"VLC目录不存在: {vlc_dir}")
                return
                
            # 设置VLC插件路径
            vlc_plugin_path = os.path.join(vlc_dir, 'plugins')
            if os.path.exists(vlc_plugin_path):
                os.environ['VLC_PLUGIN_PATH'] = vlc_plugin_path
                logging.info(f"设置VLC插件路径: {vlc_plugin_path}")
            else:
                logging.warning(f"VLC插件路径不存在: {vlc_plugin_path}")
                
            # 确保DLL文件能被找到
            if sys.platform == 'win32':
                # 添加VLC目录到PATH
                current_path = os.environ.get('PATH', '')
                if vlc_dir not in current_path:
                    os.environ['PATH'] = vlc_dir + os.pathsep + current_path
                    logging.info(f"添加VLC目录到PATH: {vlc_dir}")
                    
            # 设置其他VLC相关环境变量
            os.environ['VLC_VERBOSE'] = '0'  # 禁用详细日志
            os.environ['VLC_PLUGIN_PATH'] = vlc_plugin_path
            
        else:
            # 开发模式下的VLC配置
            logging.info("开发模式：使用系统VLC配置")
            
    except Exception as e:
        logging.error(f"VLC运行时hook执行失败: {e}")

# 立即执行hook
try:
    _pyi_rth_vlc()
except Exception as e:
    print(f"VLC运行时hook初始化失败: {e}")
