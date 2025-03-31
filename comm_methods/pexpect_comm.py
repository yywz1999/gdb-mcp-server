#!/usr/bin/env python3
"""
Pexpect通信方法 - 通过pexpect库直接与GDB进程通信
"""

import sys
import time
import logging
import subprocess
from typing import Tuple, Optional

logger = logging.getLogger('gdb-mcp-server.pexpect_comm')

class PexpectCommunicator:
    """使用pexpect库与GDB通信的类"""
    
    def __init__(self):
        self.gdb_pexpect = None
        logger.info("Pexpect通信器初始化")
        self._check_dependencies()
    
    def _check_dependencies(self):
        """检查pexpect依赖是否安装"""
        try:
            import pexpect
            logger.info("pexpect库已安装")
        except ImportError:
            logger.warning("未安装pexpect库，无法使用此通信方式")
            logger.warning("请执行 'python3 -m pip install pexpect' 安装")
    
    def initialize_connection(self, gdb_pid=None, tty_device=None):
        """初始化pexpect与GDB的连接"""
        try:
            import pexpect
            
            if sys.platform == 'darwin':
                # 在macOS上，通过TTY连接
                if gdb_pid:
                    # 查找TTY设备
                    ps_output = subprocess.check_output(['ps', '-p', gdb_pid, '-o', 'tty'], text=True)
                    lines = ps_output.strip().split('\n')
                    if len(lines) > 1:
                        tty_name = lines[1].strip()
                        if tty_name != '?' and tty_name:
                            tty_path = f"/dev/{tty_name}"
                            logger.info(f"找到GDB进程TTY: {tty_path}")
                            try:
                                # 尝试连接到TTY
                                self.gdb_pexpect = pexpect.spawn(f'cat > {tty_path}', encoding=None)
                                # 等待一段时间
                                time.sleep(0.5)
                                # 发送一个测试命令
                                self.gdb_pexpect.sendline("echo 'GDB_TEST_CONNECTION'")
                                time.sleep(0.5)
                                
                                # 如果到这里没有报错，说明连接成功
                                logger.info(f"成功通过TTY {tty_path} 连接到GDB进程")
                                return True
                            except Exception as e:
                                logger.warning(f"通过TTY连接GDB进程失败: {str(e)}")
            
            # 如果上面的方法失败，或者不是macOS，使用伪终端方式
            if sys.platform == 'linux' and tty_device:
                try:
                    # 尝试使用Linux的伪终端连接
                    self.gdb_pexpect = pexpect.spawn(f'cat > {tty_device}', encoding=None)
                    logger.info(f"成功通过伪终端 {tty_device} 连接到GDB进程")
                    return True
                except Exception as e:
                    logger.warning(f"通过伪终端连接GDB进程失败: {str(e)}")
            
            logger.warning("无法初始化pexpect连接")
            return False
        except ImportError:
            logger.error("未安装pexpect库，无法使用直接通信方式")
            return False
        except Exception as e:
            logger.error(f"初始化pexpect连接时出错: {str(e)}")
            return False
    
    def execute_command(self, command) -> Tuple[bool, str]:
        """使用pexpect方式执行GDB命令"""
        try:
            import pexpect
            
            # 如果没有初始化pexpect连接，返回错误
            if not self.gdb_pexpect:
                return False, "未初始化pexpect连接"
            
            # 清除之前可能残留的输出
            while True:
                try:
                    self.gdb_pexpect.read_nonblocking(size=4096, timeout=0.1)
                except:
                    break
            
            # 发送命令
            self.gdb_pexpect.sendline(command)
            
            # 等待(gdb)提示符
            index = self.gdb_pexpect.expect([r'\(gdb\)', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
            
            if index == 0:
                # 获取命令输出，去除命令本身和提示符
                output = self.gdb_pexpect.before.decode('utf-8', errors='ignore')
                # 移除发送的命令和命令行回显
                lines = output.split('\n')
                if len(lines) > 0 and command in lines[0]:
                    output = '\n'.join(lines[1:])
                
                logger.info(f"成功使用pexpect执行命令: {command}")
                logger.debug(f"命令输出: {output}")
                return True, output.strip()
            else:
                logger.warning(f"pexpect执行命令超时或EOF: {command}")
                return False, "命令执行超时或遇到错误"
        
        except ImportError:
            return False, "未安装pexpect库"
        except Exception as e:
            logger.error(f"pexpect执行命令时出错: {str(e)}")
            return False, f"pexpect执行命令时出错: {str(e)}"
    
    def start_gdb_with_remote(self, target_address, executable=None) -> Tuple[bool, str]:
        """启动一个新的GDB进程并连接到远程目标"""
        try:
            import pexpect
            
            # 构建GDB命令
            gdb_cmd = "gdb"
            if executable:
                gdb_cmd += f" {executable}"
            
            # 启动GDB进程
            logger.info(f"启动GDB进程: {gdb_cmd}")
            
            # 使用pexpect启动GDB
            self.gdb_pexpect = pexpect.spawn(gdb_cmd)
            
            # 等待GDB提示符
            index = self.gdb_pexpect.expect([r'\(gdb\)', pexpect.TIMEOUT, pexpect.EOF], timeout=5)
            
            if index != 0:
                logger.error("启动GDB进程失败")
                self.gdb_pexpect = None
                return False, "启动GDB进程失败"
            
            # 连接到远程目标
            logger.info(f"连接到远程目标: {target_address}")
            self.gdb_pexpect.sendline(f"target remote {target_address}")
            
            # 等待GDB提示符
            index = self.gdb_pexpect.expect([r'\(gdb\)', pexpect.TIMEOUT, pexpect.EOF], timeout=10)
            
            if index == 0:
                # 获取连接输出
                output = self.gdb_pexpect.before.decode('utf-8', errors='ignore')
                
                # 尝试获取更多信息
                info_output = ""
                try:
                    # 获取共享库信息
                    self.gdb_pexpect.sendline("info sharedlibrary")
                    self.gdb_pexpect.expect([r'\(gdb\)', pexpect.TIMEOUT], timeout=3)
                    info_output += "共享库信息:\n" + self.gdb_pexpect.before.decode('utf-8', errors='ignore') + "\n\n"
                    
                    # 获取寄存器信息
                    self.gdb_pexpect.sendline("info registers")
                    self.gdb_pexpect.expect([r'\(gdb\)', pexpect.TIMEOUT], timeout=3)
                    info_output += "寄存器信息:\n" + self.gdb_pexpect.before.decode('utf-8', errors='ignore')
                except Exception as e:
                    logger.warning(f"获取附加信息时出错: {str(e)}")
                
                logger.info(f"成功连接到远程目标: {target_address}")
                return True, f"连接到远程目标 {target_address} 成功:\n{output}\n\n{info_output}"
            else:
                logger.error(f"连接到远程目标 {target_address} 失败")
                self.gdb_pexpect = None
                return False, f"连接到远程目标 {target_address} 失败"
        
        except ImportError:
            logger.error("未安装pexpect库，无法使用此功能")
            return False, "未安装pexpect库，无法使用此功能。请执行 'python3 -m pip install pexpect' 安装。"
        except Exception as e:
            logger.error(f"启动GDB并连接到远程目标时出错: {str(e)}")
            self.gdb_pexpect = None
            return False, f"启动GDB并连接到远程目标时出错: {str(e)}" 