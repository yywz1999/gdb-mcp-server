#!/usr/bin/env python3
"""
GDB MCP Server - 代理服务器
实现Model Context Protocol标准，为GDB调试提供AI辅助功能
"""

import os
import sys
import json
import logging
import subprocess
import time
import traceback
from typing import Dict, List, Any, Optional, Union, Annotated, Tuple
from pathlib import Path
import argparse

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 提高日志级别以便调试
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('gdb-mcp-server')

# 使用FastMCP库
try:
    from fastmcp import FastMCP
    from pydantic import Field
    HAS_FASTMCP = True
    logger.info("成功导入FastMCP库")
except ImportError:
    HAS_FASTMCP = False
    logger.warning("FastMCP库未安装，将使用内置MCP实现")
    print("FastMCP库未安装，将使用内置MCP实现")
    print("建议安装: pip install fastmcp>=0.4.1")

# GDB控制器类
class GdbController:
    """GDB调试器控制类，处理与GDB的交互"""
    
    def __init__(self):
        self.gdb_process = None
        self.gdb_pid = None
        self.tty_device = None
        self.connected = False
        logger.info("GdbController初始化完成")
    
    def find_gdb_processes(self):
        """查找所有运行的GDB进程"""
        logger.info("查找GDB进程...")
        try:
            # 使用ps命令查找GDB进程
            processes = []
            cmd = ["ps", "-eo", "pid,tty,command"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            output, _ = process.communicate()
            output = output.decode('utf-8').strip()
            
            for line in output.split('\n')[1:]:  # 跳过标题行
                parts = line.strip().split()
                if len(parts) < 3:
                    continue
                
                pid = parts[0]
                tty = parts[1]
                cmd = ' '.join(parts[2:])
                
                # 检查命令是否包含'gdb'
                if 'gdb' in cmd:
                    processes.append({
                        "pid": pid,
                        "tty": tty if tty != '?' else "未知",
                        "cmd": cmd
                    })
            
            logger.info(f"找到 {len(processes)} 个GDB进程")
            return processes
        except Exception as e:
            logger.error(f"查找GDB进程时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def attach_to_gdb(self, gdb_pid=None, tty_device=None):
        """附加到指定的GDB进程"""
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
        
        logger.info(f"尝试附加到GDB进程 pid={gdb_pid}, tty={tty_device}")
        
        try:
            # 优先使用PID附加
            if gdb_pid:
                # 验证PID对应的进程是否为GDB
                processes = self.find_gdb_processes()
                valid_pid = any(p.get("pid") == gdb_pid for p in processes)
                
                if valid_pid:
                    self.gdb_pid = gdb_pid
                    
                    # 尝试查找对应的TTY
                    for p in processes:
                        if p.get("pid") == gdb_pid:
                            self.tty_device = p.get("tty", "未知")
                            break
                    
                    logger.info(f"成功附加到GDB进程 PID={gdb_pid}, TTY={self.tty_device}")
                    return True
                else:
                    logger.error(f"PID {gdb_pid} 不是一个有效的GDB进程")
                    return False
            
            # 如果没有指定PID，尝试使用TTY附加
            elif tty_device:
                processes = self.find_gdb_processes()
                for p in processes:
                    if p.get("tty") == tty_device:
                        self.gdb_pid = p.get("pid")
                        self.tty_device = tty_device
                        logger.info(f"成功通过TTY {tty_device} 附加到GDB进程 PID={self.gdb_pid}")
                        return True
                
                logger.error(f"找不到使用TTY {tty_device} 的GDB进程")
                return False
            
            # 如果都没有指定，尝试附加到找到的第一个GDB进程
            else:
                processes = self.find_gdb_processes()
                if processes:
                    self.gdb_pid = processes[0].get("pid")
                    self.tty_device = processes[0].get("tty", "未知")
                    logger.info(f"自动选择附加到第一个发现的GDB进程 PID={self.gdb_pid}, TTY={self.tty_device}")
                    return True
                else:
                    logger.error("找不到任何GDB进程")
                    return False
        
        except Exception as e:
            logger.error(f"附加到GDB进程时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def execute_command(self, command, gdb_pid=None) -> Tuple[bool, str]:
        """执行GDB命令"""
        logger.info(f"准备执行GDB命令: {command}")
        if not self.connected and not gdb_pid:
            logger.warning("未连接到GDB进程")
            return False, "未连接到GDB进程"
        
        if gdb_pid:
            # 确保gdb_pid是字符串
            gdb_pid = str(gdb_pid)
            logger.debug(f"将gdb_pid转换为字符串: {gdb_pid}")
            
            if gdb_pid != self.gdb_pid:
                logger.info(f"切换到GDB进程: {gdb_pid}")
                success, message = self.attach_to_gdb(gdb_pid)
                if not success:
                    return False, message
        
        try:
            actual_output = None  # 用于存储实际捕获到的输出
            execution_method = "未执行"  # 跟踪使用了哪种执行方法
            
            # 根据平台选择命令执行方式
            if sys.platform == 'darwin':
                
                # 优先使用iTerm2，更可靠地向GDB发送命令
                logger.info("尝试使用iTerm2发送命令")
                
                # 首先生成一个唯一标记，以便识别输出
                time_id = int(time.time())
                output_marker = f"<<<GDB_OUTPUT_START_{time_id}>>>"
                end_marker = f"<<<GDB_OUTPUT_END_{time_id}>>>"
                
                # 构建更可靠的iTerm2 AppleScript命令
                script = f"""
                tell application "iTerm2"
                    try
                        set foundTerminal to false
                        set commandOutput to ""
                        
                        -- 遍历所有窗口和标签页查找GDB进程
                        repeat with aWindow in windows
                            if foundTerminal then exit repeat
                            
                            repeat with aTab in tabs of aWindow
                                if foundTerminal then exit repeat
                                
                                repeat with aSession in sessions of aTab
                                    if foundTerminal then exit repeat
                                    
                                    try
                                        -- 获取会话中的进程
                                        set sessionText to text of aSession
                                        
                                        -- 查找GDB提示符
                                        if sessionText contains "(gdb)" then
                                            tell aSession
                                                -- 记录当前内容
                                                set prevContent to text of aSession
                                                
                                                -- 发送输出标记和命令
                                                write text "echo '{output_marker}'"
                                                write text "{command}"
                                                write text "echo '{end_marker}'"
                                                
                                                -- 等待响应
                                                delay 1.0
                                                
                                                -- 获取新内容
                                                set newContent to text of aSession
                                                
                                                -- 尝试提取输出
                                                set marker_start to offset of "{output_marker}" in newContent
                                                set marker_end to offset of "{end_marker}" in newContent
                                                
                                                if marker_start > 0 and marker_end > marker_start then
                                                    -- 计算标记之间的文本（包含命令和输出）
                                                    set marker_start to marker_start + (length of "{output_marker}")
                                                    set outputText to text from character marker_start to character (marker_end - 1) of newContent
                                                    
                                                    -- 提取命令执行的输出（去掉命令本身和提示符）
                                                    set cmdStartPos to offset of "{command}" in outputText
                                                    if cmdStartPos > 0 then
                                                        set cmdEndPos to cmdStartPos + (length of "{command}")
                                                        set outputAfterCmd to text from character cmdEndPos to end of outputText
                                                        
                                                        -- 查找下一个提示符位置，它标志着输出的结束
                                                        set gdbPromptPos to offset of "(gdb)" in outputAfterCmd
                                                        if gdbPromptPos > 0 then
                                                            set commandOutput to text from character 1 to character (gdbPromptPos - 1) of outputAfterCmd
                                                        else
                                                            set commandOutput to outputAfterCmd
                                                        end if
                                                    end if
                                                end if
                                            end tell
                                            set foundTerminal to true
                                            exit repeat
                                        end if
                                    on error errMsg
                                        -- 继续下一个会话
                                    end try
                                end repeat
                            end repeat
                        end repeat
                        
                        -- 如果没找到包含GDB的会话，回退到默认查找TTY的方式
                        if not foundTerminal then
                            set ttyName to "{self.tty_device.split('/')[-1] if self.tty_device else ''}"
                            -- 如果有TTY信息，按TTY查找
                            if ttyName is not "" then
                                repeat with aWindow in windows
                                    if foundTerminal then exit repeat
                                    
                                    repeat with aTab in tabs of aWindow
                                        if foundTerminal then exit repeat
                                        
                                        repeat with aSession in sessions of aTab
                                            if foundTerminal then exit repeat
                                            
                                            try
                                                if tty of aSession contains ttyName then
                                                    tell aSession
                                                        -- 记录当前内容
                                                        set prevContent to text of aSession
                                                        
                                                        -- 发送输出标记和命令
                                                        write text "echo '{output_marker}'"
                                                        write text "{command}"
                                                        write text "echo '{end_marker}'"
                                                        
                                                        -- 等待响应
                                                        delay 1.0
                                                        
                                                        -- 获取新内容
                                                        set newContent to text of aSession
                                                        
                                                        -- 尝试提取输出
                                                        set marker_start to offset of "{output_marker}" in newContent
                                                        set marker_end to offset of "{end_marker}" in newContent
                                                        
                                                        if marker_start > 0 and marker_end > marker_start then
                                                            -- 计算标记之间的文本（包含命令和输出）
                                                            set marker_start to marker_start + (length of "{output_marker}")
                                                            set outputText to text from character marker_start to character (marker_end - 1) of newContent
                                                            
                                                            -- 提取命令执行的输出（去掉命令本身和提示符）
                                                            set cmdStartPos to offset of "{command}" in outputText
                                                            if cmdStartPos > 0 then
                                                                set cmdEndPos to cmdStartPos + (length of "{command}")
                                                                set outputAfterCmd to text from character cmdEndPos to end of outputText
                                                                
                                                                -- 查找下一个提示符位置，它标志着输出的结束
                                                                set gdbPromptPos to offset of "(gdb)" in outputAfterCmd
                                                                if gdbPromptPos > 0 then
                                                                    set commandOutput to text from character 1 to character (gdbPromptPos - 1) of outputAfterCmd
                                                                else
                                                                    set commandOutput to outputAfterCmd
                                                                end if
                                                            end if
                                                        end if
                                                    end tell
                                                    set foundTerminal to true
                                                    exit repeat
                                                end if
                                            on error errMsg
                                                -- 继续下一个会话
                                            end try
                                        end repeat
                                    end repeat
                                end repeat
                            end if
                        end if
                        
                        return "success: " & foundTerminal & "|OUTPUT:" & commandOutput
                    on error errMsg
                        return "error: " & errMsg as string
                    end try
                end tell
                """
                
                try:
                    result = subprocess.check_output(['osascript', '-e', script], text=True, timeout=10).strip()
                    logger.info(f"iTerm2脚本执行结果: {result}")
                    
                    if result.startswith("success:"):
                        parts = result.split("|OUTPUT:", 1)
                        if len(parts) > 1:
                            success_value = parts[0].split(":", 1)[1].strip()
                            output_value = parts[1].strip()
                            
                            if success_value.lower() == "true":
                                logger.info(f"命令已成功发送到iTerm2: {command}")
                                
                                # 清理输出
                                output_value = output_value.strip()
                                if output_value:
                                    # 存储实际的输出结果
                                    actual_output = output_value
                                    execution_method = "iTerm2"
                                    logger.info(f"从iTerm2捕获到的输出: {output_value}")
                                else:
                                    logger.warning("从iTerm2捕获的输出为空")
                            else:
                                logger.warning("iTerm2脚本执行成功但未找到匹配的终端")
                        else:
                            logger.warning("iTerm2脚本执行成功但未返回输出数据")
                    else:
                        logger.warning(f"iTerm2脚本执行失败: {result}")
                except Exception as e:
                    logger.warning(f"使用iTerm2发送命令时出错: {str(e)}")
                
                # 如果iTerm2失败，尝试使用Terminal.app
                if not actual_output:
                    logger.info("iTerm2方法未能获取输出，尝试使用Terminal发送命令")
                    terminal_script = f"""
                    tell application "Terminal"
                        try
                            set foundTerminal to false
                            set commandOutput to ""
                            
                            -- 遍历所有窗口查找GDB
                            repeat with aWindow in windows
                                try
                                    set windowContents to contents of aWindow
                                    if windowContents contains "(gdb)" then
                                        -- 记录当前窗口内容
                                        set prevContent to contents of aWindow
                                        
                                        -- 发送输出标记和命令
                                        do script "echo '{output_marker}'" in aWindow
                                        do script "{command}" in aWindow
                                        do script "echo '{end_marker}'" in aWindow
                                        
                                        -- 等待响应
                                        delay 1.0
                                        
                                        -- 获取新内容
                                        set newContent to contents of aWindow
                                        
                                        -- 尝试提取输出
                                        set marker_start to offset of "{output_marker}" in newContent
                                        set marker_end to offset of "{end_marker}" in newContent
                                        
                                        if marker_start > 0 and marker_end > marker_start then
                                            -- 计算标记之间的文本（包含命令和输出）
                                            set marker_start to marker_start + (length of "{output_marker}")
                                            set outputText to text from character marker_start to character (marker_end - 1) of newContent
                                            
                                            -- 提取命令执行的输出（去掉命令本身和提示符）
                                            set cmdStartPos to offset of "{command}" in outputText
                                            if cmdStartPos > 0 then
                                                set cmdEndPos to cmdStartPos + (length of "{command}")
                                                set outputAfterCmd to text from character cmdEndPos to end of outputText
                                                
                                                -- 查找下一个提示符位置，它标志着输出的结束
                                                set gdbPromptPos to offset of "(gdb)" in outputAfterCmd
                                                if gdbPromptPos > 0 then
                                                    set commandOutput to text from character 1 to character (gdbPromptPos - 1) of outputAfterCmd
                                                else
                                                    set commandOutput to outputAfterCmd
                                                end if
                                            end if
                                        end if
                                        
                                        set foundTerminal to true
                                        exit repeat
                                    end if
                                on error errMsg
                                    -- 继续尝试下一个窗口
                                end try
                            end repeat
                            
                            -- 如果没找到GDB，使用前台窗口
                            if not foundTerminal then
                                -- 记录当前窗口内容
                                set prevContent to contents of front window
                                
                                -- 发送输出标记和命令
                                do script "echo '{output_marker}'" in front window
                                do script "{command}" in front window
                                do script "echo '{end_marker}'" in front window
                                
                                -- 等待响应
                                delay 1.0
                                
                                -- 获取新内容
                                set newContent to contents of front window
                                
                                -- 尝试提取输出
                                set marker_start to offset of "{output_marker}" in newContent
                                set marker_end to offset of "{end_marker}" in newContent
                                
                                if marker_start > 0 and marker_end > marker_start then
                                    -- 计算标记之间的文本（包含命令和输出）
                                    set marker_start to marker_start + (length of "{output_marker}")
                                    set outputText to text from character marker_start to character (marker_end - 1) of newContent
                                    
                                    -- 提取命令执行的输出（去掉命令本身和提示符）
                                    set cmdStartPos to offset of "{command}" in outputText
                                    if cmdStartPos > 0 then
                                        set cmdEndPos to cmdStartPos + (length of "{command}")
                                        set outputAfterCmd to text from character cmdEndPos to end of outputText
                                        
                                        -- 查找下一个提示符位置，它标志着输出的结束
                                        set gdbPromptPos to offset of "(gdb)" in outputAfterCmd
                                        if gdbPromptPos > 0 then
                                            set commandOutput to text from character 1 to character (gdbPromptPos - 1) of outputAfterCmd
                                        else
                                            set commandOutput to outputAfterCmd
                                        end if
                                    end if
                                end if
                                
                                set foundTerminal to true
                            end if
                            
                            return "success: " & foundTerminal & "|OUTPUT:" & commandOutput
                        on error errMsg
                            return "error: " & errMsg
                        end try
                    end tell
                    """
                    
                    try:
                        terminal_result = subprocess.check_output(['osascript', '-e', terminal_script], text=True, timeout=10).strip()
                        logger.info(f"Terminal脚本执行结果: {terminal_result}")
                        
                        if terminal_result.startswith("success:"):
                            parts = terminal_result.split("|OUTPUT:", 1)
                            if len(parts) > 1:
                                success_value = parts[0].split(":", 1)[1].strip()
                                output_value = parts[1].strip()
                                
                                if success_value.lower() == "true":
                                    logger.info(f"命令已成功发送到Terminal并获取输出: {command}")
                                    
                                    # 清理输出
                                    output_value = output_value.strip()
                                    if output_value:
                                        # 存储实际的输出结果
                                        actual_output = output_value
                                        execution_method = "Terminal"
                                        logger.info(f"从Terminal捕获到的输出: {output_value}")
                                    else:
                                        logger.warning("从Terminal捕获的输出为空")
                                else:
                                    logger.warning("Terminal脚本执行成功但未找到匹配的窗口")
                            else:
                                logger.warning("Terminal脚本执行成功但未返回输出数据")
                        else:
                            logger.warning(f"Terminal脚本执行失败: {terminal_result}")
                    except Exception as e:
                        logger.warning(f"使用Terminal发送命令时出错: {str(e)}")
                
                # 如果通过iTerm2和Terminal都获取不到结果，我们使用更直接的方法
                if not actual_output:
                    cmd = f'osascript -e \'tell application "iTerm2" to activate\' -e \'tell application "System Events" to keystroke "{command}" & return\''
                    try:
                        logger.info("使用键盘事件发送命令到激活的iTerm2窗口")
                        subprocess.run(cmd, shell=True, check=True)
                        execution_method = "键盘事件(iTerm2)"
                        # 这种方法无法获取输出，但至少可以发送命令
                        actual_output = f"命令 '{command}' 已通过键盘事件发送到iTerm2，但无法获取输出结果。请在GDB终端中查看结果。"
                    except Exception as e:
                        logger.warning(f"使用键盘事件发送命令时出错: {str(e)}")
                        
                        # 最后的后备方法
                        if not actual_output:
                            execution_method = "无法执行"
                            actual_output = f"无法向GDB终端发送命令 '{command}'。请手动在GDB终端中执行此命令。"
            
            elif sys.platform == 'linux' and self.tty_device:
                # Linux通过向TTY设备写入
                logger.info(f"使用TTY设备发送命令: {self.tty_device}")
                try:
                    with open(self.tty_device, 'w') as tty:
                        tty.write(command + '\n')
                    logger.info(f"命令已发送到TTY设备: {command}")
                    execution_method = "Linux TTY"
                    actual_output = f"命令 '{command}' 已发送到TTY {self.tty_device}，但无法获取输出结果。请在GDB终端中查看结果。"
                except Exception as e:
                    logger.error(f"通过TTY发送命令时出错: {str(e)}")
                    execution_method = "TTY发送失败"
                    actual_output = f"无法通过TTY设备发送命令: {str(e)}。请手动在GDB终端中执行此命令: {command}"
            
            else:
                # 默认方法：输出命令供用户复制粘贴
                logger.info(f"无法直接发送命令: {command}")
                execution_method = "无法执行"
                actual_output = f"无法直接发送GDB命令。请在GDB终端中手动执行: {command}"
            
            # 确保我们总是返回某种结果
            if not actual_output:
                actual_output = f"命令 '{command}' 已发送，但无法获取输出结果。请在GDB终端中查看。"
            
            logger.info(f"命令执行完成 [{execution_method}]: {command}")
            logger.debug(f"命令输出: {actual_output}")
            
            # 总是返回实际输出结果
            return True, actual_output
                
        except Exception as e:
            logger.error(f"执行命令时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"执行命令时出错: {str(e)}"

# 创建GDB控制器实例
gdb_controller = GdbController()

# 定义SimpleMCP类
class SimpleMCP:
    def __init__(self, name="GDB"):
        self.tools = {}
        self.name = name
        logger.info(f"SimpleMCP初始化: {name}")
    
    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            logger.info(f"注册工具: {func.__name__}")
            return func
        return decorator
    
    def handle_request(self, request_str):
        try:
            logger.info(f"收到请求: {request_str}")
            request = json.loads(request_str)
            
            # 检查是否是JSON-RPC 2.0格式的请求
            is_jsonrpc = "jsonrpc" in request and "id" in request
            
            if is_jsonrpc:
                # 处理JSON-RPC格式的请求
                logger.info("检测到JSON-RPC格式请求")
                method = request.get("method")
                params = request.get("params", {})
                request_id = request.get("id")
                
                logger.info(f"解析JSON-RPC请求: method={method}, params={params}, id={request_id}")
                
                if method in self.tools:
                    logger.info(f"调用工具: {method}")
                    try:
                        result = self.tools[method](**params)
                        logger.info(f"工具返回: {result}")
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": result
                        }
                    except Exception as e:
                        logger.error(f"工具执行出错: {str(e)}")
                        logger.error(traceback.format_exc())
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32603,
                                "message": f"内部错误: {str(e)}"
                            }
                        }
                else:
                    logger.warning(f"未知方法: {method}")
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"方法 '{method}' 不存在"
                        }
                    }
            else:
                # 处理简单的MCP请求格式
                logger.info("检测到简单格式请求")
                method = request.get("method")
                params = request.get("params", {})
                
                logger.info(f"解析简单请求: method={method}, params={params}")
                
                if method in self.tools:
                    logger.info(f"调用工具: {method}")
                    try:
                        result = self.tools[method](**params)
                        logger.info(f"工具返回: {result}")
                        response = {"success": True, "result": result}
                    except Exception as e:
                        logger.error(f"工具执行出错: {str(e)}")
                        logger.error(traceback.format_exc())
                        response = {"success": False, "error": str(e)}
                else:
                    logger.warning(f"未知方法: {method}")
                    response = {"success": False, "error": f"未知方法: {method}"}
            
            response_str = json.dumps(response)
            logger.info(f"发送响应: {response_str}")
            return response_str
        except Exception as e:
            logger.error(f"处理请求时出错: {str(e)}")
            logger.error(traceback.format_exc())
            error_resp = {"success": False, "error": str(e)}
            return json.dumps(error_resp)
    
    def run(self, transport="stdio"):
        logger.info(f"启动 {self.name} MCP服务器 (传输方式: {transport})")
        print(f"启动 {self.name} MCP服务器 (传输方式: {transport})")
        
        if transport == "stdio":
            for line in sys.stdin:
                try:
                    if not line.strip():
                        continue
                    
                    response = self.handle_request(line)
                    sys.stdout.write(response + "\n")
                    sys.stdout.flush()
                    logger.debug(f"响应已刷新到stdout: {response}")
                except Exception as e:
                    logger.error(f"处理输入行时出错: {str(e)}")
                    logger.error(traceback.format_exc())
                    error_resp = json.dumps({"success": False, "error": str(e)})
                    sys.stdout.write(error_resp + "\n")
                    sys.stdout.flush()
        elif transport == "http":
            try:
                import aiohttp
                from aiohttp import web
                import asyncio
                
                logger.info("使用HTTP传输方式")
                
                async def handle_request(request):
                    try:
                        # 读取请求体
                        request_json = await request.text()
                        logger.info(f"收到HTTP请求: {request_json}")
                        
                        # 处理请求
                        response_str = self.handle_request(request_json)
                        
                        # 返回响应
                        return web.Response(text=response_str, content_type='application/json')
                    except Exception as e:
                        logger.error(f"处理HTTP请求时出错: {str(e)}")
                        logger.error(traceback.format_exc())
                        error_resp = json.dumps({"success": False, "error": str(e)})
                        return web.Response(text=error_resp, content_type='application/json', status=500)
                
                # 创建HTTP应用
                app = web.Application()
                app.router.add_post('/mcp', handle_request)
                
                # 运行HTTP服务器
                web.run_app(app, host='127.0.0.1', port=8080)
                
            except ImportError:
                logger.error("导入aiohttp失败，无法使用HTTP传输方式")
                print("错误: 使用HTTP传输方式需要安装aiohttp库")
                print("请安装: pip install aiohttp")
                sys.exit(1)
        else:
            logger.error(f"不支持的传输方式: {transport}")
            print(f"错误: 不支持的传输方式: {transport}")
            sys.exit(1)

# 如果FastMCP可用，使用FastMCP实现MCP服务器
if HAS_FASTMCP:
    # 创建FastMCP实例
    logger.info("使用FastMCP实现MCP服务器")
    mcp = FastMCP("GDB", log_level="INFO")
    
    # 注意：这里是关键，为FastMCP定义MCP__前缀的工具
    @mcp.tool(name="mcp__find_gdb_processes")
    def find_gdb_processes(
        random_string="dummy"
    ) -> Dict[str, Any]:
        """查找系统中运行的所有GDB进程"""
        logger.info("调用find_gdb_processes工具")
        
        processes = gdb_controller.find_gdb_processes()
        
        if processes:
            formatted_processes = []
            for process in processes:
                pid = process.get("pid", "未知")
                tty = process.get("tty", "未知")
                cmd = process.get("cmd", "未知")
                formatted_processes.append(f"PID: {pid}, TTY: {tty}, CMD: {cmd}")
            
            formatted_list = "\n".join(formatted_processes)
            result_message = f"找到 {len(processes)} 个GDB进程:\n{formatted_list}"
            success = True
        else:
            result_message = "未找到任何GDB进程。"
            success = True  # 这仍然是成功的结果，只是没有找到进程
        
        logger.info(f"find_gdb_processes返回: processes={len(processes) if processes else 0}")
        
        return {
            "success": success,
            "output": str(processes),
            "formatted_result": result_message,
            "processes": processes,
            "has_output": True
        }
    
    @mcp.tool(name="mcp__attach_to_gdb")
    def attach_to_gdb(
        gdb_pid=None,
        tty_device=None
    ) -> Dict[str, Any]:
        """附加到现有的GDB进程"""
        logger.info(f"调用attach_to_gdb工具: gdb_pid={gdb_pid}, tty_device={tty_device}")
        
        is_attached = gdb_controller.attach_to_gdb(gdb_pid, tty_device)
        
        if is_attached:
            if gdb_pid:
                result_message = f"成功附加到GDB进程 PID: {gdb_pid}"
            elif tty_device:
                result_message = f"成功附加到GDB终端 TTY: {tty_device}"
            else:
                result_message = "成功附加到GDB进程"
            success = True
        else:
            if gdb_pid:
                result_message = f"附加到GDB进程 PID: {gdb_pid} 失败"
            elif tty_device:
                result_message = f"附加到GDB终端 TTY: {tty_device} 失败"
            else:
                result_message = "附加到GDB进程失败，未提供PID或TTY"
            success = False
        
        logger.info(f"attach_to_gdb返回: is_attached={is_attached}")
        
        output = f"GDB PID: {gdb_pid}, TTY: {tty_device}, 附加状态: {'成功' if is_attached else '失败'}"
        
        return {
            "success": success,
            "output": output,
            "formatted_result": result_message,
            "is_attached": is_attached,
            "gdb_pid": gdb_pid,
            "tty_device": tty_device,
            "has_output": True
        }
    
    @mcp.tool(name="mcp__execute_command")
    def execute_command(
        command,
        gdb_pid=None
    ) -> Dict[str, Any]:
        """执行GDB命令"""
        logger.info(f"调用execute_command工具: command={command}, gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
        
        # 执行命令
        success, output = gdb_controller.execute_command(command, gdb_pid)
        
        # 简化结果显示
        cmd_type = command.split()[0] if " " in command else command
        
        # 确定命令类型，用于更有意义的显示
        cmd_display = {
            "info": "信息查询",
            "bt": "堆栈回溯",
            "disassemble": "反汇编",
            "break": "设置断点",
            "delete": "删除断点",
            "step": "单步执行",
            "continue": "继续执行",
            "x": "内存查看"
        }.get(cmd_type, "GDB命令")
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            # 无论命令是否有实际输出，都返回相同结构的结果
            result_message = f"{cmd_display}命令执行: {command}\n{output}"
        else:
            result_message = f"执行{cmd_display}命令失败: {output}"
            
        logger.info(f"execute_command返回: success={success}")
        logger.debug(f"execute_command输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "command_type": cmd_type,
            "has_output": not command_sent_but_no_output
        }
    
    @mcp.tool(name="mcp__set_breakpoint")
    def set_breakpoint(
        location,
        gdb_pid=None
    ) -> Dict[str, Any]:
        """设置断点"""
        logger.info(f"调用set_breakpoint工具: location={location}, gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
            
        success, output = gdb_controller.execute_command(f"break {location}", gdb_pid)
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            result_message = f"设置断点 '{location}': {output}"
        else:
            result_message = f"设置断点 '{location}' 失败: {output}"
        
        logger.info(f"set_breakpoint返回: success={success}")
        logger.debug(f"set_breakpoint输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "has_output": not command_sent_but_no_output
        }
    
    @mcp.tool(name="mcp__delete_breakpoint")
    def delete_breakpoint(
        number,
        gdb_pid=None
    ) -> Dict[str, Any]:
        """删除断点"""
        logger.info(f"调用delete_breakpoint工具: number={number}, gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
            
        success, output = gdb_controller.execute_command(f"delete {number}", gdb_pid)
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            result_message = f"删除断点 #{number}: {output}"
        else:
            result_message = f"删除断点 #{number} 失败: {output}"
        
        logger.info(f"delete_breakpoint返回: success={success}")
        logger.debug(f"delete_breakpoint输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "has_output": not command_sent_but_no_output
        }
    
    @mcp.tool(name="mcp__step")
    def step(
        gdb_pid=None
    ) -> Dict[str, Any]:
        """单步执行"""
        logger.info(f"调用step工具: gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
            
        success, output = gdb_controller.execute_command("step", gdb_pid)
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            result_message = f"单步执行: {output}"
        else:
            result_message = f"单步执行失败: {output}"
        
        logger.info(f"step返回: success={success}")
        logger.debug(f"step输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "has_output": not command_sent_but_no_output
        }
    
    @mcp.tool(name="mcp__continue_execution")
    def continue_execution(
        gdb_pid=None
    ) -> Dict[str, Any]:
        """继续执行"""
        logger.info(f"调用continue_execution工具: gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
            
        success, output = gdb_controller.execute_command("continue", gdb_pid)
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            result_message = f"继续执行: {output}"
        else:
            result_message = f"继续执行失败: {output}"
        
        logger.info(f"continue_execution返回: success={success}")
        logger.debug(f"continue_execution输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "has_output": not command_sent_but_no_output
        }
    
    @mcp.tool(name="mcp__get_registers")
    def get_registers(
        gdb_pid=None
    ) -> Dict[str, Any]:
        """获取寄存器值"""
        logger.info(f"调用get_registers工具: gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
            
        success, output = gdb_controller.execute_command("info registers", gdb_pid)
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            result_message = f"寄存器值: {output}"
        else:
            result_message = f"获取寄存器值失败: {output}"
        
        logger.info(f"get_registers返回: success={success}")
        logger.debug(f"get_registers输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "command": "info registers",
            "has_output": not command_sent_but_no_output
        }
    
    @mcp.tool(name="mcp__examine_memory")
    def examine_memory(
        address,
        count="10",
        format_type="x",
        gdb_pid=None
    ) -> Dict[str, Any]:
        """检查内存"""
        logger.info(f"调用examine_memory工具: address={address}, count={count}, format_type={format_type}, gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
        # 确保count是字符串类型
        count = str(count)
        
        command = f"x/{count}{format_type} {address}"
        success, output = gdb_controller.execute_command(command, gdb_pid)
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            result_message = f"检查内存地址 {address}: {output}"
        else:
            result_message = f"检查内存失败: {output}"
        
        logger.info(f"examine_memory返回: success={success}")
        logger.debug(f"examine_memory输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "command": command,
            "has_output": not command_sent_but_no_output
        }
    
    @mcp.tool(name="mcp__get_stack")
    def get_stack(
        gdb_pid=None
    ) -> Dict[str, Any]:
        """获取堆栈信息"""
        logger.info(f"调用get_stack工具: gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
            
        success, output = gdb_controller.execute_command("bt", gdb_pid)
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            result_message = f"堆栈回溯: {output}"
        else:
            result_message = f"获取堆栈信息失败: {output}"
        
        logger.info(f"get_stack返回: success={success}")
        logger.debug(f"get_stack输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "command": "bt",
            "has_output": not command_sent_but_no_output
        }
    
    @mcp.tool(name="mcp__get_locals")
    def get_locals(
        gdb_pid=None
    ) -> Dict[str, Any]:
        """获取局部变量"""
        logger.info(f"调用get_locals工具: gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
            
        success, output = gdb_controller.execute_command("info locals", gdb_pid)
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            result_message = f"局部变量: {output}"
        else:
            result_message = f"获取局部变量失败: {output}"
        
        logger.info(f"get_locals返回: success={success}")
        logger.debug(f"get_locals输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "command": "info locals",
            "has_output": not command_sent_but_no_output
        }
    
    @mcp.tool(name="mcp__disassemble")
    def disassemble(
        location="",
        gdb_pid=None
    ) -> Dict[str, Any]:
        """反汇编代码"""
        logger.info(f"调用disassemble工具: location={location}, gdb_pid={gdb_pid}")
        # 强制转换gdb_pid为字符串类型(如果提供了)
        if gdb_pid is not None:
            gdb_pid = str(gdb_pid)
            
        command = "disassemble" if not location else f"disassemble {location}"
        success, output = gdb_controller.execute_command(command, gdb_pid)
        
        # 检测命令是否发送成功但无法获取结果
        command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
        
        if success:
            result_message = f"反汇编{' '+location if location else ''}: {output}"
        else:
            result_message = f"反汇编失败: {output}"
        
        logger.info(f"disassemble返回: success={success}")
        logger.debug(f"disassemble输出: {output}")
        
        return {
            "success": success, 
            "output": output, 
            "formatted_result": result_message,
            "command": command,
            "has_output": not command_sent_but_no_output
        }

else:
    # 创建简单MCP实例
    logger.info("使用内置MCP实现")
    mcp = SimpleMCP("GDB")
    logger.info("已创建SimpleMCP实例")

    # 以下是在没有FastMCP情况下的工具定义
    @mcp.tool()
    def find_gdb_processes():
        """查找系统中运行的所有GDB进程"""
        logger.info("调用find_gdb_processes工具")
        try:
            processes = gdb_controller.find_gdb_processes()
            result = []
            for pid, cmdline, tty in processes:
                result.append({
                    "pid": str(pid),
                    "command": cmdline,
                    "tty": tty or "unknown"
                })
            logger.info(f"find_gdb_processes返回 {len(result)} 个进程")
            return {
                "success": True,
                "processes": result,
                "message": f"找到 {len(result)} 个GDB进程"
            }
        except Exception as e:
            logger.error(f"find_gdb_processes出错: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "processes": [],
                "message": f"查找GDB进程时出错: {str(e)}"
            }

    @mcp.tool()
    def attach_to_gdb(gdb_pid=None, tty_device=None):
        """附加到现有的GDB进程"""
        logger.info(f"调用attach_to_gdb工具: gdb_pid={gdb_pid}, tty_device={tty_device}")
        success, message = gdb_controller.attach_to_gdb(gdb_pid, tty_device)
        logger.info(f"attach_to_gdb返回: success={success}, message={message}")
        return {"success": success, "message": message}

    @mcp.tool()
    def execute_command(command, gdb_pid=None):
        """执行GDB命令"""
        logger.info(f"调用execute_command工具: command={command}, gdb_pid={gdb_pid}")
        success, output = gdb_controller.execute_command(command, gdb_pid)
        logger.info(f"execute_command返回: success={success}, output={output}")
        return {"success": success, "output": output}

    @mcp.tool()
    def set_breakpoint(location, gdb_pid=None):
        """设置断点"""
        logger.info(f"调用set_breakpoint工具: location={location}, gdb_pid={gdb_pid}")
        success, output = gdb_controller.execute_command(f"break {location}", gdb_pid)
        logger.info(f"set_breakpoint返回: success={success}, output={output}")
        return {"success": success, "output": output}

    @mcp.tool()
    def delete_breakpoint(number, gdb_pid=None):
        """删除断点"""
        logger.info(f"调用delete_breakpoint工具: number={number}, gdb_pid={gdb_pid}")
        success, output = gdb_controller.execute_command(f"delete {number}", gdb_pid)
        logger.info(f"delete_breakpoint返回: success={success}, output={output}")
        return {"success": success, "output": output}

    @mcp.tool()
    def step(gdb_pid=None):
        """单步执行"""
        logger.info(f"调用step工具: gdb_pid={gdb_pid}")
        success, output = gdb_controller.execute_command("step", gdb_pid)
        logger.info(f"step返回: success={success}, output={output}")
        return {"success": success, "output": output}

    @mcp.tool()
    def continue_execution(gdb_pid=None):
        """继续执行"""
        logger.info(f"调用continue_execution工具: gdb_pid={gdb_pid}")
        success, output = gdb_controller.execute_command("continue", gdb_pid)
        logger.info(f"continue_execution返回: success={success}, output={output}")
        return {"success": success, "output": output}

    @mcp.tool()
    def get_registers(gdb_pid=None):
        """获取寄存器值"""
        logger.info(f"调用get_registers工具: gdb_pid={gdb_pid}")
        success, output = gdb_controller.execute_command("info registers", gdb_pid)
        logger.info(f"get_registers返回: success={success}, output={output}")
        return {"success": success, "output": output}

    @mcp.tool()
    def examine_memory(address, count="10", format_type="x", gdb_pid=None):
        """检查内存"""
        logger.info(f"调用examine_memory工具: address={address}, count={count}, format_type={format_type}, gdb_pid={gdb_pid}")
        success, output = gdb_controller.execute_command(f"x/{count}{format_type} {address}", gdb_pid)
        logger.info(f"examine_memory返回: success={success}, output={output}")
        return {"success": success, "output": output}

    @mcp.tool()
    def get_stack(gdb_pid=None):
        """获取堆栈信息"""
        logger.info(f"调用get_stack工具: gdb_pid={gdb_pid}")
        success, output = gdb_controller.execute_command("bt", gdb_pid)
        logger.info(f"get_stack返回: success={success}, output={output}")
        return {"success": success, "output": output}

    @mcp.tool()
    def get_locals(gdb_pid=None):
        """获取局部变量"""
        logger.info(f"调用get_locals工具: gdb_pid={gdb_pid}")
        success, output = gdb_controller.execute_command("info locals", gdb_pid)
        logger.info(f"get_locals返回: success={success}, output={output}")
        return {"success": success, "output": output}

    @mcp.tool()
    def disassemble(location="", gdb_pid=None):
        """反汇编代码"""
        logger.info(f"调用disassemble工具: location={location}, gdb_pid={gdb_pid}")
        command = f"disassemble {location}" if location else "disassemble"
        success, output = gdb_controller.execute_command(command, gdb_pid)
        logger.info(f"disassemble返回: success={success}, output={output}")
        return {"success": success, "output": output}

if __name__ == "__main__":
    logger.info("启动GDB MCP服务器")
    try:
        # 解析命令行参数
        parser = argparse.ArgumentParser(description="GDB MCP 服务器")
        parser.add_argument("--transport", "-t", choices=["stdio", "http"], default="stdio",
                          help="传输方式: stdio (默认) 或 http")
        parser.add_argument("--port", "-p", type=int, default=8080,
                          help="HTTP服务器端口号 (默认: 8080)")
        args = parser.parse_args()
        
        # 如果使用HTTP传输，设置端口
        if args.transport == "http" and not HAS_FASTMCP:
            logger.info(f"使用HTTP传输方式，端口: {args.port}")
            try:
                import aiohttp
                transport = "http"
            except ImportError:
                logger.error("导入aiohttp失败，将回退到stdio传输方式")
                print("错误: 使用HTTP传输方式需要安装aiohttp库")
                print("请安装: pip install aiohttp")
                print("将使用标准输入输出(stdio)传输方式继续")
                transport = "stdio"
        else:
            transport = args.transport
        
        # 运行MCP服务器
        if HAS_FASTMCP:
            # FastMCP自动处理传输方式
            logger.info(f"使用FastMCP运行MCP服务器")
            mcp.run()
        else:
            # 使用SimpleMCP，指定传输方式
            logger.info(f"使用SimpleMCP运行MCP服务器，传输方式: {transport}")
            mcp.run(transport=transport)
            
    except KeyboardInterrupt:
        logger.info("GDB MCP服务器已终止")
    except Exception as e:
        logger.error(f"GDB MCP服务器错误: {str(e)}")
        logger.error(traceback.format_exc())