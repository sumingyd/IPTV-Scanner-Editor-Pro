import os
import sys

def _pyi_rth_vlc():
    # 在打包模式下设置VLC插件路径
    if getattr(sys, 'frozen', False):
        # 获取临时解压目录
        vlc_dir = os.path.join(sys._MEIPASS, 'vlc')
        # 设置VLC插件路径
        os.environ['VLC_PLUGIN_PATH'] = os.path.join(vlc_dir, 'plugins')
        # 确保DLL文件能被找到
        if sys.platform == 'win32':
            os.environ['PATH'] = vlc_dir + os.pathsep + os.environ['PATH']

# 立即执行hook
_pyi_rth_vlc()
