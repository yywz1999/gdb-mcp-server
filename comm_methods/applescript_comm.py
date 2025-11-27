#!/usr/bin/env python3
"""
AppleScript通信方法 - 通过AppleScript与GDB进程通信
主要用于macOS系统
"""

import sys
import time
import logging
import subprocess
from typing import Tuple, Optional, Dict
import traceback

logger = logging.getLogger('gdb-mcp-server.applescript_comm')

class AppleScriptCommunicator:
    """使用AppleScript与GDB通信的类"""
    
    def __init__(self):
        logger.info("AppleScript通信器初始化")
        self._check_platform()
        self.gdb_pid = None  # 添加gdb_pid属性
        self.last_command_time = 0  # 记录最后一次命令执行时间
        self.is_blocked = False  # GDB阻塞状态标志
    
    def _check_platform(self):
        """检查运行平台是否为macOS"""
        if sys.platform != 'darwin':
            logger.warning("当前平台不是macOS，AppleScript通信方式将不可用")
            return False
        return True
    
    def find_gdb_window(self):
        """查找包含GDB的终端窗口，而不激活它"""
        if sys.platform != 'darwin':
            logger.warning("当前平台不是macOS，无法使用AppleScript查找GDB窗口")
            return False
            
        # 使用find_gdb_session方法
        result = self.find_gdb_session()
        if result:
            logger.info("找到GDB会话")
        else:
            logger.warning("未找到GDB会话")
        return result
    
    # 保留旧方法名称以兼容已有代码
    activate_gdb_window = find_gdb_window

    def check_gdb_blocked(self) -> Dict:
        """检查GDB是否处于阻塞状态（正在运行）
        
        返回:
            Dict: 包含阻塞状态信息的字典
                - is_blocked: 是否处于阻塞状态
                - running_time: 如果阻塞，已运行时间（秒）
                - status: 状态描述
        """
        if not self.is_blocked:
            return {
                "is_blocked": False,
                "running_time": 0,
                "status": "GDB处于交互状态"
            }
        
        running_time = time.time() - self.last_command_time
        return {
            "is_blocked": True,
            "running_time": running_time,
            "status": f"GDB正在运行中，已运行 {running_time:.1f} 秒"
        }
    
    def find_gdb_session(self):
        """查找包含GDB的终端会话"""
        if sys.platform != 'darwin':
            return None
        
        find_session_script = """
        tell application "iTerm2"
            try
                set foundSession to missing value
                
                -- 遍历所有窗口和标签页查找GDB进程
                repeat with aWindow in windows
                    if foundSession is not missing value then exit repeat
                    
                    repeat with aTab in tabs of aWindow
                        if foundSession is not missing value then exit repeat
                        
                        repeat with aSession in sessions of aTab
                            try
                                -- 获取会话中的文本内容
                                set sessionText to text of aSession
                                
                                -- 查找GDB提示符或其他GDB相关内容
                                if sessionText contains "(gdb)" or sessionText contains "pwndbg>" or sessionText contains "gef>" then
                                    set foundSession to aSession
                                    exit repeat
                                end if
                            on error
                                -- 继续下一个会话
                            end try
                        end repeat
                    end repeat
                end repeat
                
                if foundSession is not missing value then
                    return "found"
                else
                    return "not_found"
                end if
            on error errMsg
                return "error: " & errMsg
            end try
        end tell
        """
        
        try:
            result = subprocess.check_output(['osascript', '-e', find_session_script], text=True, timeout=5).strip()
            return result == "found"
        except Exception as e:
            logger.warning(f"查找GDB会话时出错: {str(e)}")
            return False

    def execute_command(self, command) -> Tuple[bool, str]:
        """使用AppleScript执行GDB命令"""
        if sys.platform != 'darwin':
            return False, "当前平台不是macOS，无法使用AppleScript通信方式"
            
        # 生成唯一标记
        time_id = int(time.time())
        output_marker = f"<<<GDB_OUTPUT_START_{time_id}>>>"
        end_marker = f"<<<GDB_OUTPUT_END_{time_id}>>>"
        
        # 检查是否是可能阻塞的命令
        might_block = command.strip() in ["c", "continue", "run", "r"] or "target remote" in command
        
        # 发送命令的AppleScript - 查找包含GDB的会话而不是使用当前窗口
        send_script = f"""
        tell application "iTerm2"
            try
                set foundSession to missing value
                
                -- 遍历所有窗口和标签页查找GDB进程
                repeat with aWindow in windows
                    if foundSession is not missing value then exit repeat
                    
                    repeat with aTab in tabs of aWindow
                        if foundSession is not missing value then exit repeat
                        
                        repeat with aSession in sessions of aTab
                            try
                                -- 获取会话中的文本内容
                                set sessionText to text of aSession
                                
                                -- 查找GDB提示符或其他GDB相关内容
                                if sessionText contains "(gdb)" or sessionText contains "pwndbg>" or sessionText contains "gef>" then
                                    set foundSession to aSession
                                    exit repeat
                                end if
                            on error
                                -- 继续下一个会话
                            end try
                        end repeat
                    end repeat
                end repeat
                
                if foundSession is missing value then
                    return "error: 未找到GDB会话"
                end if
                
                tell foundSession
                    write text "echo '{output_marker}'"
                    write text "{command}"
                    return "success"
                end tell
            on error errMsg
                return "error: " & errMsg
            end try
        end tell
        """
        
        try:
            # 发送命令
            send_result = subprocess.check_output(['osascript', '-e', send_script], text=True, timeout=3).strip()
            if not send_result.startswith("success"):
                return False, f"发送命令失败: {send_result}"
            
            # 等待并检查输出
            time.sleep(0.5)  # 给命令一些执行时间
            
            # 检查输出的AppleScript - 也要查找GDB会话
            check_script = f"""
            tell application "iTerm2"
                try
                    set foundSession to missing value
                    
                    -- 遍历所有窗口和标签页查找GDB进程
                    repeat with aWindow in windows
                        if foundSession is not missing value then exit repeat
                        
                        repeat with aTab in tabs of aWindow
                            if foundSession is not missing value then exit repeat
                            
                            repeat with aSession in sessions of aTab
                                try
                                    -- 获取会话中的文本内容
                                    set sessionText to text of aSession
                                    
                                    -- 查找GDB提示符或其他GDB相关内容
                                    if sessionText contains "(gdb)" or sessionText contains "pwndbg>" or sessionText contains "gef>" then
                                        set foundSession to aSession
                                        exit repeat
                                    end if
                                on error
                                    -- 继续下一个会话
                                end try
                            end repeat
                        end repeat
                    end repeat
                    
                    if foundSession is missing value then
                        return "error: 未找到GDB会话"
                    end if
                    
                    tell foundSession
                        -- 获取当前内容
                        set currentContent to text of foundSession
                        
                        -- 检查是否有命令输出（包含START但没有END标记表示可能阻塞）
                        if currentContent contains "{output_marker}" then
                            -- 检查是否已经有结束标记
                            if currentContent contains "{end_marker}" then
                                -- 已经完成，直接返回
                                return currentContent
                            end if
                            
                            -- 发送结束标记
                            write text "echo '{end_marker}'"
                            delay 0.3
                            set updatedContent to text of foundSession
                            
                            -- 再次检查是否有结束标记
                            if updatedContent contains "{end_marker}" then
                                return updatedContent
                            else
                                -- 有START但没有END，表示阻塞
                                return "BLOCKED:" & currentContent
                            end if
                        end if
                        
                        -- 没有START标记，发送测试命令检查响应
                        write text "echo 'GDB_TEST'"
                        delay 0.2
                        set testContent to text of foundSession
                        
                        if testContent contains "GDB_TEST" then
                            -- 终端响应但没有输出
                            write text "echo '{end_marker}'"
                            delay 0.2
                            return testContent
                        else
                            -- 终端没有响应，可能阻塞
                            return "BLOCKED:" & currentContent
                        end if
                    end tell
                on error errMsg
                    return "error: " & errMsg
                end try
            end tell
            """
            
            # 检查输出
            check_result = subprocess.check_output(['osascript', '-e', check_script], text=True, timeout=3).strip()
            
            if check_result.startswith("error:"):
                return False, f"检查输出时出错: {check_result}"
            
            if check_result.startswith("BLOCKED:"):
                # 更新阻塞状态
                self.is_blocked = True
                self.last_command_time = time.time()
                
                # 提取可能的部分输出
                content = check_result[8:]  # 去掉"BLOCKED:"前缀
                if output_marker in content:
                    # 检查是否有END标记
                    if end_marker not in content:
                        # 有START但没有END，说明GDB正在阻塞执行
                        parts = content.split(output_marker, 1)
                        if len(parts) > 1:
                            partial_output = parts[1].strip()
                            if partial_output:
                                return True, f"⚠️ GDB处于阻塞状态（检测到GDB_OUTPUT_START但没有END标记）\\n程序可能正在运行或处理大量代码\\n部分输出：\\n{partial_output}"
                        
                        return True, "⚠️ GDB处于阻塞状态（检测到GDB_OUTPUT_START但没有END标记）\\n程序可能正在运行或处理大量代码"
                
                return True, "⚠️ GDB处于阻塞状态，程序可能正在运行"
            
            # 提取命令输出
            if output_marker in check_result and end_marker in check_result:
                self.is_blocked = False  # 重置阻塞状态
                parts = check_result.split(output_marker, 1)[1].split(end_marker, 1)
                output = parts[0].strip() if parts else ""
                return True, output
            
            # 没有输出但响应正常
            self.is_blocked = False
            return True, ""
            
        except subprocess.TimeoutExpired:
            logger.warning("执行命令超时")
            return False, "执行命令超时"
        except Exception as e:
            logger.error(f"执行命令时出错: {str(e)}")
            return False, f"执行命令时出错: {str(e)}" 