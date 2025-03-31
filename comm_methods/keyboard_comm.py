#!/usr/bin/env python3
"""
键盘通信方法 - 通过模拟键盘事件向终端发送GDB命令
这是一种通用的方法，可用于各种平台
"""

import sys
import time
import logging
import subprocess
from typing import Tuple, Optional

logger = logging.getLogger('gdb-mcp-server.keyboard_comm')

class KeyboardCommunicator:
    """通过模拟键盘事件发送GDB命令的类"""
    
    def __init__(self):
        logger.info("键盘通信器初始化")
        self._check_dependencies()
    
    def _check_dependencies(self):
        """检查平台相关依赖"""
        if sys.platform == 'darwin':
            # macOS上使用AppleScript实现键盘事件
            pass
        elif sys.platform == 'linux':
            # Linux上可能需要xdotool
            try:
                subprocess.check_call(['which', 'xdotool'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logger.info("找到xdotool工具")
            except (subprocess.SubprocessError, FileNotFoundError):
                logger.warning("在Linux上未找到xdotool工具，键盘通信可能不可用")
                logger.warning("请安装xdotool: sudo apt-get install xdotool")
        elif sys.platform == 'win32':
            # Windows上可能需要pyautogui
            try:
                import pyautogui
                logger.info("找到pyautogui库")
            except ImportError:
                logger.warning("在Windows上未安装pyautogui库，键盘通信可能不可用")
                logger.warning("请安装pyautogui: python -m pip install pyautogui")
    
    def execute_command(self, command) -> Tuple[bool, str]:
        """使用键盘事件执行GDB命令"""
        if sys.platform == 'darwin':
            return self._execute_macos(command)
        elif sys.platform == 'linux':
            return self._execute_linux(command)
        elif sys.platform == 'win32':
            return self._execute_windows(command)
        else:
            return False, f"不支持的平台: {sys.platform}"
    
    def _execute_macos(self, command) -> Tuple[bool, str]:
        """在macOS上通过AppleScript模拟键盘事件"""
        # 更强大的AppleScript脚本，先激活窗口，清除输入法状态，再发送命令
        direct_script = """
        tell application "System Events"
            try
                -- 首先尝试找到并激活iTerm2
                set foundTerminal to false
                
                if application "iTerm2" is running then
                    tell application "iTerm2"
                        activate
                        delay 0.3
                    end tell
                    
                    -- 寻找可能含有GDB的窗口
                    tell application "iTerm2"
                        -- 遍历所有窗口和标签页
                        repeat with aWindow in windows
                            if foundTerminal then exit repeat
                            
                            tell aWindow
                                repeat with aTab in tabs
                                    if foundTerminal then exit repeat
                                    
                                    if (name of aTab contains "gdb") or (name of aTab contains "GDB") then
                                        select aTab
                                        set foundTerminal to true
                                        exit repeat
                                    end if
                                    
                                    -- 如果标题不含gdb，检查内容
                                    tell current session of aTab
                                        if contents contains "(gdb)" or contents contains "pwndbg" then
                                            select aTab
                                            set foundTerminal to true
                                            exit repeat
                                        end if
                                    end tell
                                end repeat
                            end tell
                        end repeat
                        
                        -- 如果没找到相关窗口，使用当前窗口
                        if not foundTerminal then
                            set frontmost to true
                        end if
                    end tell
                    
                    -- 确保窗口激活
                    delay 0.5
                    set frontmost of process "iTerm2" to true
                    
                    -- 清除可能的输入法状态
                    key code 53 -- ESC键
                    delay 0.1
                    
                    -- 发送命令
                    keystroke "{0}"
                    keystroke return
                    
                    return "sent:true:iTerm2"
                else if application "Terminal" is running then
                    -- 如果找不到iTerm2，尝试Terminal
                    tell application "Terminal"
                        activate
                        delay 0.3
                    end tell
                    
                    set frontmost of process "Terminal" to true
                    
                    -- 清除可能的输入法状态
                    key code 53 -- ESC键
                    delay 0.1
                    
                    -- 发送命令
                    keystroke "{0}"
                    keystroke return
                    
                    return "sent:true:Terminal"
                else
                    return "error:未找到活动的终端窗口"
                end if
            on error errMsg
                return "error:" & errMsg
            end try
        end tell
        """
        
        direct_script = direct_script.format(command)
        
        try:
            logger.info(f"尝试通过键盘事件发送命令: {command}")
            direct_result = subprocess.check_output(['osascript', '-e', direct_script], text=True, timeout=10).strip()
            logger.info(f"键盘事件发送结果: {direct_result}")
            
            if direct_result.startswith("sent:true"):
                app_name = direct_result.split(":", 2)[2] if direct_result.count(":") >= 2 else "未知应用"
                return True, f"命令 '{command}' 已通过键盘事件发送到 {app_name}，但无法获取输出结果。请在GDB终端中查看结果。"
            else:
                return False, f"通过键盘事件发送命令失败: {direct_result}"
        except Exception as e:
            logger.error(f"通过键盘事件发送命令时出错: {str(e)}")
            return False, f"通过键盘事件发送命令时出错: {str(e)}"
    
    def _execute_linux(self, command) -> Tuple[bool, str]:
        """在Linux上通过xdotool模拟键盘事件"""
        try:
            # 检查xdotool是否可用
            subprocess.check_call(['which', 'xdotool'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 使用xdotool发送命令
            logger.info(f"尝试通过xdotool发送命令: {command}")
            
            # 激活当前窗口
            subprocess.call(['xdotool', 'getactivewindow'])
            
            # 清除可能的输入法状态
            subprocess.call(['xdotool', 'key', 'Escape'])
            time.sleep(0.1)
            subprocess.call(['xdotool', 'type', ' '])
            time.sleep(0.1)
            subprocess.call(['xdotool', 'key', 'BackSpace'])
            time.sleep(0.1)
            
            # 发送命令
            subprocess.call(['xdotool', 'type', command])
            time.sleep(0.1)
            subprocess.call(['xdotool', 'key', 'Return'])
            
            logger.info("命令已通过xdotool发送")
            return True, f"命令 '{command}' 已通过xdotool发送，但无法获取输出结果。请在GDB终端中查看结果。"
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.error(f"使用xdotool发送命令失败: {str(e)}")
            return False, f"使用xdotool发送命令失败: {str(e)}"
    
    def _execute_windows(self, command) -> Tuple[bool, str]:
        """在Windows上通过pyautogui模拟键盘事件"""
        try:
            import pyautogui
            
            logger.info(f"尝试通过pyautogui发送命令: {command}")
            
            # 发送Escape键清除可能的输入法状态
            pyautogui.press('escape')
            time.sleep(0.1)
            pyautogui.write(' ')
            time.sleep(0.1)
            pyautogui.press('backspace')
            time.sleep(0.1)
            
            # 发送命令
            pyautogui.write(command)
            time.sleep(0.1)
            pyautogui.press('enter')
            
            logger.info("命令已通过pyautogui发送")
            return True, f"命令 '{command}' 已通过键盘模拟发送，但无法获取输出结果。请在GDB终端中查看结果。"
        except ImportError:
            logger.error("未安装pyautogui库，无法使用键盘模拟")
            return False, "未安装pyautogui库，无法使用键盘模拟。请执行 'python -m pip install pyautogui' 安装。"
        except Exception as e:
            logger.error(f"使用pyautogui发送命令时出错: {str(e)}")
            return False, f"使用pyautogui发送命令时出错: {str(e)}" 