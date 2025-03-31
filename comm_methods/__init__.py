"""
通信方法包 - 包含与GDB进程通信的各种方法
"""

# 从各个模块导入通信方法
from .pexpect_comm import PexpectCommunicator
from .applescript_comm import AppleScriptCommunicator 
from .keyboard_comm import KeyboardCommunicator 