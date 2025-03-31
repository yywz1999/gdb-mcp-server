#!/usr/bin/env python3
"""
GDB通信接口 - 整合各种通信方法，提供统一的接口
"""

import sys
import logging
from typing import Tuple, List, Dict, Any, Optional

# 导入三种通信方法
from .pexpect_comm import PexpectCommunicator
from .applescript_comm import AppleScriptCommunicator
from .keyboard_comm import KeyboardCommunicator

logger = logging.getLogger('gdb-mcp-server.gdb_communicator')

class GdbCommunicator:
    """GDB通信接口类，整合多种通信方法"""
    
    def __init__(self):
        """初始化通信接口"""
        # 创建各种通信方法的实例
        self.pexpect_comm = PexpectCommunicator()
        self.applescript_comm = AppleScriptCommunicator() if sys.platform == 'darwin' else None
        self.keyboard_comm = KeyboardCommunicator()
        
        # 控制状态
        self.gdb_pid = None
        self.tty_device = None
        self.connected = False
        self.preferred_method = None  # 存储上一次成功的通信方法
        
        logger.info("GDB通信接口初始化完成")
    
    def attach_to_gdb(self, gdb_pid=None, tty_device=None) -> bool:
        """附加到GDB进程"""
        logger.info(f"尝试附加到GDB进程: PID={gdb_pid}, TTY={tty_device}")
        
        if gdb_pid is not None:
            self.gdb_pid = str(gdb_pid)
        if tty_device is not None:
            self.tty_device = tty_device
        
        # 在macOS上，使用AppleScript查找GDB窗口
        if sys.platform == 'darwin' and self.applescript_comm:
            logger.info("在macOS上，优先使用AppleScript查找GDB窗口")
            # 将GDB PID传递给AppleScript通信器
            if self.gdb_pid:
                self.applescript_comm.gdb_pid = self.gdb_pid
                
            found = self.applescript_comm.find_gdb_window()
            if found:
                logger.info("使用AppleScript找到GDB窗口")
                self.connected = True
                self.preferred_method = "applescript"
                return True
            else:
                logger.warning("使用AppleScript未找到GDB窗口，但仍将尝试使用AppleScript通信")
                # 即使未找到窗口，仍尝试使用AppleScript通信
                if self.gdb_pid or self.tty_device:
                    self.connected = True
                    self.preferred_method = "applescript"
                    return True
        
        # 尝试使用pexpect连接（非macOS平台）
        if sys.platform != 'darwin':
            logger.info("尝试使用pexpect附加到GDB进程")
            if self.pexpect_comm.initialize_connection(self.gdb_pid, self.tty_device):
                self.preferred_method = "pexpect"
                self.connected = True
                logger.info(f"使用pexpect方式成功附加到GDB进程 PID={self.gdb_pid}, TTY={self.tty_device}")
                return True
            
            # 如果pexpect连接失败，但有PID或TTY信息，使用键盘模拟
            if self.gdb_pid or self.tty_device:
                self.connected = True
                self.preferred_method = "keyboard" 
                logger.info(f"将使用键盘模拟方法与GDB进程 PID={self.gdb_pid} 通信")
                return True
        
        # 如果到这里还未连接，但有PID或TTY信息，在macOS上使用AppleScript
        if (self.gdb_pid or self.tty_device) and sys.platform == 'darwin' and self.applescript_comm:
            self.connected = True
            self.preferred_method = "applescript"
            logger.info(f"将尝试使用AppleScript与GDB进程 PID={self.gdb_pid} 通信")
            return True
        
        logger.error("附加到GDB进程失败")
        return False
    
    def execute_command(self, command, gdb_pid=None) -> Tuple[bool, str]:
        """执行GDB命令"""
        logger.info(f"执行GDB命令: {command}")
        
        # 如果提供了新的GDB PID，尝试切换
        if gdb_pid is not None and gdb_pid != self.gdb_pid:
            logger.info(f"切换到GDB进程: {gdb_pid}")
            success = self.attach_to_gdb(gdb_pid)
            if not success:
                return False, f"无法附加到GDB进程 PID={gdb_pid}"
        
        # 如果没有连接到GDB进程，返回错误
        if not self.connected:
            return False, "未连接到GDB进程"
        
        # 对于macOS系统，始终使用AppleScript方法
        if sys.platform == 'darwin':
            logger.info("在macOS平台上，始终使用AppleScript方法")
            
            # 尝试AppleScript通信
            if self.applescript_comm:
                # 确保AppleScript通信器知道当前的GDB PID
                if self.gdb_pid:
                    self.applescript_comm.gdb_pid = self.gdb_pid
                
                success, output = self.applescript_comm.execute_command(command)
                if success:
                    self.preferred_method = "applescript"
                    return success, output
                
                logger.warning("AppleScript方法执行失败，但在macOS上我们依然不使用其他方法")
                return False, "AppleScript方法执行失败，无法执行命令。请确保您的iTerm2窗口已经打开并包含GDB会话。"
            else:
                logger.error("在macOS上无法初始化AppleScript通信器")
                return False, "在macOS上无法初始化AppleScript通信器，无法执行命令"
        
        # 对于非macOS系统，优先使用pexpect方法
        logger.info("在非macOS平台上，优先使用pexpect方法")
        success, output = self.pexpect_comm.execute_command(command)
        if success:
            self.preferred_method = "pexpect"
            return success, output
        
        # 在非macOS系统上，最后才尝试键盘模拟方法
        logger.info("尝试使用键盘模拟方法执行命令")
        success, output = self.keyboard_comm.execute_command(command)
        if success:
            self.preferred_method = "keyboard"
            return success, output
        
        # 所有方法都失败了
        logger.error("所有通信方法都失败，无法执行命令")
        return False, "无法与GDB进程通信，所有方法都失败"
    
    def start_gdb_with_remote(self, target_address, executable=None) -> Tuple[bool, str]:
        """启动GDB并连接到远程目标"""
        logger.info(f"启动GDB并连接到远程目标: {target_address}")
        
        # 使用pexpect启动新的GDB进程并连接
        success, output = self.pexpect_comm.start_gdb_with_remote(target_address, executable)
        if success:
            self.connected = True
            self.preferred_method = "pexpect"
            # 获取GDB进程ID
            import psutil
            self.gdb_pid = str(self.pexpect_comm.gdb_pexpect.pid)
            logger.info(f"成功启动GDB进程 PID={self.gdb_pid} 并连接到远程目标")
            return True, output
        
        logger.error(f"启动GDB并连接到远程目标失败: {output}")
        return False, output
    
    def get_communication_status(self) -> Dict[str, Any]:
        """获取当前通信状态的信息"""
        status = {
            "connected": self.connected,
            "gdb_pid": self.gdb_pid,
            "tty_device": self.tty_device,
            "preferred_method": self.preferred_method,
            "available_methods": []
        }
        
        # 检查各种通信方法的可用性
        try:
            import pexpect
            status["available_methods"].append("pexpect")
        except ImportError:
            pass
        
        if sys.platform == 'darwin':
            status["available_methods"].append("applescript")
        
        status["available_methods"].append("keyboard")
        
        return status 