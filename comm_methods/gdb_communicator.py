#!/usr/bin/env python3
"""
GDB通信接口 - 整合各种通信方法，提供统一的接口
"""

import sys
import logging
from typing import Tuple, List, Dict, Any, Optional

# 导入所有通信方法
from .pexpect_comm import PexpectCommunicator
from .applescript_comm import AppleScriptCommunicator
from .keyboard_comm import KeyboardCommunicator
from .tmux_comm import TmuxCommunicator

logger = logging.getLogger('gdb-mcp-server.gdb_communicator')

class GdbCommunicator:
    """GDB通信接口类，整合多种通信方法"""
    
    def __init__(self):
        """初始化通信接口"""
        # 创建各种通信方法的实例
        self.pexpect_comm = PexpectCommunicator()
        self.applescript_comm = AppleScriptCommunicator() if sys.platform == 'darwin' else None
        self.tmux_comm = TmuxCommunicator() if sys.platform != 'darwin' else None
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
        
        # 在Linux平台上，优先使用tmux
        if sys.platform != 'darwin':
            # 首先尝试使用tmux
            if self.tmux_comm:
                logger.info("在Linux上，优先尝试使用tmux查找GDB会话")
                if self.tmux_comm.find_gdb_window():
                    self.preferred_method = "tmux"
                    self.connected = True
                    logger.info(f"使用tmux方式成功找到GDB会话")
                    return True
                else:
                    logger.info("未找到tmux GDB会话，将尝试其他方法")
            
            # 如果tmux失败，尝试使用pexpect连接
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
        
        # 对于非macOS系统，优先使用tmux方法
        logger.info("在非macOS平台上，优先使用tmux方法")
        if self.tmux_comm and self.preferred_method == "tmux":
            success, output = self.tmux_comm.execute_command(command)
            if success:
                return success, output
            else:
                logger.warning("tmux方法执行失败，尝试其他方法")
        
        # 如果tmux失败，尝试pexpect方法
        logger.info("尝试使用pexpect方法执行命令")
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
    
    def check_gdb_blocked(self) -> Dict[str, Any]:
        """检查GDB是否处于阻塞状态
        
        返回:
            Dict: 包含阻塞状态信息的字典
                - is_blocked: 是否处于阻塞状态
                - running_time: 如果阻塞，已运行时间（秒）
                - status: 状态描述
        """
        if not self.connected:
            return {
                "is_blocked": False,
                "running_time": 0,
                "status": "未连接到GDB进程"
            }
        
        # 根据当前使用的通信方法检查阻塞状态
        if self.preferred_method == "applescript" and self.applescript_comm:
            return self.applescript_comm.check_gdb_blocked()
        elif self.preferred_method == "tmux" and self.tmux_comm:
            return self.tmux_comm.check_gdb_blocked()
        elif self.preferred_method == "pexpect":
            # pexpect方法可以通过检查进程状态来判断
            if hasattr(self.pexpect_comm, 'check_gdb_blocked'):
                return self.pexpect_comm.check_gdb_blocked()
        
        # 默认返回未阻塞
        return {
            "is_blocked": False,
            "running_time": 0,
            "status": "当前通信方法不支持阻塞检测"
        }
    
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
        if sys.platform == 'darwin':
            status["available_methods"].append("applescript")
        else:
            # Linux平台
            # 检查tmux是否可用
            try:
                import subprocess
                subprocess.check_call(['which', 'tmux'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                status["available_methods"].append("tmux")
            except:
                pass
            
            # 检查pexpect是否可用
            try:
                import pexpect
                status["available_methods"].append("pexpect")
            except ImportError:
                pass
        
        status["available_methods"].append("keyboard")
        
        return status 