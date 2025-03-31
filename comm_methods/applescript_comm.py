#!/usr/bin/env python3
"""
AppleScript通信方法 - 通过AppleScript与GDB进程通信
主要用于macOS系统
"""

import sys
import time
import logging
import subprocess
from typing import Tuple, Optional
import traceback

logger = logging.getLogger('gdb-mcp-server.applescript_comm')

class AppleScriptCommunicator:
    """使用AppleScript与GDB通信的类"""
    
    def __init__(self):
        logger.info("AppleScript通信器初始化")
        self._check_platform()
        self.gdb_pid = None  # 添加gdb_pid属性
    
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
            
        # 构建仅查找但不激活的AppleScript脚本
        find_script = """
        tell application "iTerm2"
            try
                set foundGDB to false
                
                -- 遍历所有窗口和标签页查找GDB进程
                repeat with aWindow in windows
                    if foundGDB then exit repeat
                    
                    repeat with aTab in tabs of aWindow
                        if foundGDB then exit repeat
                        
                        repeat with aSession in sessions of aTab
                            if foundGDB then exit repeat
                            
                            try
                                -- 获取会话中的文本内容
                                set sessionText to text of aSession
                                
                                -- 查找GDB提示符或其他GDB相关内容
                                if sessionText contains "(gdb)" or sessionText contains "pwndbg>" or sessionText contains "gef>" then
                                    set foundGDB to true
                                    exit repeat
                                end if
                            on error errMsg
                                -- 继续下一个会话
                            end try
                        end repeat
                    end repeat
                end repeat
                
                return foundGDB
            on error errMsg
                return false
            end try
        end tell
        """
        
        try:
            result = subprocess.check_output(['osascript', '-e', find_script], text=True, timeout=5).strip()
            logger.info(f"GDB窗口查找结果: {result}")
            return result.lower() == "true"
        except Exception as e:
            logger.warning(f"查找GDB窗口时出错: {str(e)}")
            return False
    
    # 保留旧方法名称以兼容已有代码
    activate_gdb_window = find_gdb_window
    
    def execute_command(self, command) -> Tuple[bool, str]:
        """使用AppleScript执行GDB命令"""
        if sys.platform != 'darwin':
            return False, "当前平台不是macOS，无法使用AppleScript通信方式"
            
        # 首先生成一个唯一标记，以便识别输出
        time_id = int(time.time())
        output_marker = f"<<<GDB_OUTPUT_START_{time_id}>>>"
        end_marker = f"<<<GDB_OUTPUT_END_{time_id}>>>"
        
        # 获取GDB PID，如果有的话
        gdb_pid = self.gdb_pid if hasattr(self, 'gdb_pid') and self.gdb_pid else ""
        
        # 特殊处理可能导致阻塞的命令
        might_block = False
        # 检查是否是可能阻塞的命令（如target remote, continue等）
        if "target remote" in command or command.strip() in ["c", "continue", "run", "r"]:
            logger.info(f"检测到可能阻塞的命令: {command}")
            might_block = True
        
        # 简化的指令执行方式
        # 1. 先发送标记和命令
        pre_script = f"""
        tell application "iTerm2"
            try
                set frontWindow to current window
                set frontTab to current tab of frontWindow
                set frontSession to current session of frontTab
                
                tell frontSession
                    -- 发送输出标记
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
            # 执行前置脚本
            pre_result = subprocess.check_output(['osascript', '-e', pre_script], text=True, timeout=3).strip()
            if not pre_result.startswith("success"):
                logger.error(f"发送命令失败: {pre_result}")
                return False, f"发送命令失败: {pre_result}"
            
            # 2. 尝试最多3次获取输出，检查是否有回显
            max_attempts = 3 if might_block else 1
            got_response = False
            content = ""
            
            for attempt in range(max_attempts):
                # 等待一段时间
                time.sleep(1.0)
                
                # 检查输出
                check_script = f"""
                tell application "iTerm2"
                    try
                        set frontWindow to current window
                        set frontTab to current tab of frontWindow
                        set frontSession to current session of frontTab
                        
                        tell frontSession
                            -- 获取当前内容
                            set currentContent to text of frontSession
                            
                            -- 检查是否包含输出标记
                            if currentContent contains "{output_marker}" then
                                -- 尝试发送结束标记
                                write text "echo '{end_marker}'"
                                delay 0.2
                                
                                -- 再次获取内容
                                set finalContent to text of frontSession
                                
                                -- 返回内容
                                return finalContent
                            else
                                -- 没有找到输出标记，可能是命令没有产生任何输出
                                -- 尝试发送一个测试命令来检查终端是否响应
                                write text "echo 'GDB_TEST_{attempt}'"
                                delay 0.2
                                
                                -- 再次获取内容
                                set testContent to text of frontSession
                                
                                if testContent contains "GDB_TEST_{attempt}" then
                                    -- 终端响应正常，只是命令没有输出
                                    write text "echo '{end_marker}'"
                                    delay 0.2
                                    return testContent
                                else
                                    -- 终端没有响应，可能阻塞了
                                    return "no_response: " & currentContent
                                end if
                            end if
                        end tell
                    on error errMsg
                        return "error: " & errMsg
                    end try
                end tell
                """
                
                check_result = subprocess.check_output(['osascript', '-e', check_script], text=True, timeout=3).strip()
                
                if check_result.startswith("error:"):
                    logger.warning(f"检查输出时出错: {check_result}")
                    continue
                
                if check_result.startswith("no_response:"):
                    logger.warning(f"检测到可能的阻塞 (尝试 {attempt+1}/{max_attempts})")
                    content = check_result.replace("no_response: ", "")
                    
                    # 如果是最后一次尝试且没有响应，判定为阻塞
                    if attempt == max_attempts - 1:
                        got_response = False
                        break
                else:
                    # 有响应
                    content = check_result
                    got_response = True
                    break
            
            # 3. 如果判断为阻塞，发送中断信号
            if not got_response and might_block:
                logger.warning(f"命令执行阻塞，发送中断信号")
                
                interrupt_script = """
                tell application "iTerm2"
                    try
                        set frontWindow to current window
                        set frontTab to current tab of frontWindow
                        set frontSession to current session of frontTab
                        
                        tell frontSession
                            -- 发送Ctrl+C中断
                            write text (ASCII character 3)
                            delay 0.5
                            
                            -- 发送结束标记
                            write text "echo '<<<GDB_INTERRUPTED>>>'"
                            
                            return "interrupted"
                        end tell
                    on error errMsg
                        return "error: " & errMsg
                    end try
                end tell
                """
                
                interrupt_result = subprocess.check_output(['osascript', '-e', interrupt_script], text=True, timeout=3).strip()
                logger.info(f"中断命令结果: {interrupt_result}")
                
                # 尝试从内容中提取有用的信息
                partial_output = ""
                if output_marker in content:
                    parts = content.split(output_marker, 1)
                    if len(parts) > 1:
                        partial_output = parts[1]
                
                if partial_output:
                    return True, f"命令执行时阻塞，已发送中断信号。部分输出：\n{partial_output}"
                else:
                    return True, f"命令执行时阻塞，已发送中断信号。请在GDB终端中查看结果。"
            
            # 4. 处理输出
            # 提取输出内容
            output_value = ""
            if output_marker in content:
                # 使用简单的字符串分割提取输出
                parts = content.split(output_marker, 1)
                if len(parts) > 1:
                    after_marker = parts[1]
                    if end_marker in after_marker:
                        output_parts = after_marker.split(end_marker, 1)
                        output_value = output_parts[0]
                        
                        # 尝试清理输出（移除命令本身）
                        if command in output_value:
                            cmd_parts = output_value.split(command, 1)
                            if len(cmd_parts) > 1:
                                output_value = cmd_parts[1]
            
            # 无论是否提取到输出，都认为命令执行成功（只要终端响应）
            if got_response:
                if output_value:
                    logger.info(f"成功执行命令并获取输出: {command}")
                    return True, output_value.strip()
                else:
                    logger.info(f"成功执行命令，但没有输出: {command}")
                    return True, f"命令 '{command}' 已成功执行，但没有捕获到输出。请在GDB终端中查看结果。"
            else:
                logger.warning(f"执行命令时未获得响应: {command}")
                return False, "执行命令时未获得终端响应，可能出现异常。"
            
        except Exception as e:
            logger.error(f"执行命令时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"执行命令时出错: {str(e)}" 