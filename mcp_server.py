#!/usr/bin/env python3
"""
GDB MCP Server - 代理服务器
实现Model Context Protocol标准，为GDB调试提供AI辅助功能
"""

import os
import sys
import logging
import traceback
from typing import Dict

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('gdb-mcp-server')

# 使用FastMCP库
from fastmcp import FastMCP
logger.info("成功导入FastMCP库")

# 导入工具函数
import gdb_tools
logger.info("成功导入GDB工具函数")

# 创建FastMCP实例
logger.info("使用FastMCP实现MCP服务器")
mcp = FastMCP("GDB", log_level="INFO")
    
# 注册工具函数
# 系统相关工具
@mcp.tool(name="sys_find_gdb_processes")
def sys_find_gdb_processes(random_string="dummy") -> Dict:
    """查找系统中运行的所有GDB进程"""
    return gdb_tools.sys_find_gdb_processes(random_string)

@mcp.tool(name="sys_attach_to_gdb")
def sys_attach_to_gdb(gdb_pid=None, tty_device=None) -> Dict:
    """附加到现有的GDB进程"""
    return gdb_tools.sys_attach_to_gdb(gdb_pid, tty_device)

@mcp.tool(name="sys_start_gdb_with_remote")
def sys_start_gdb_with_remote(target_address, executable=None) -> Dict:
    """启动GDB并连接到远程调试目标"""
    return gdb_tools.sys_start_gdb_with_remote(target_address, executable)

# GDB命令工具
@mcp.tool(name="gdb_execute_command")
def gdb_execute_command(command, gdb_pid=None) -> Dict:
    """执行GDB命令"""
    return gdb_tools.gdb_execute_command(command, gdb_pid)

@mcp.tool(name="gdb_set_breakpoint")
def gdb_set_breakpoint(location, gdb_pid=None) -> Dict:
    """设置断点"""
    return gdb_tools.gdb_set_breakpoint(location, gdb_pid)

@mcp.tool(name="gdb_delete_breakpoint")
def gdb_delete_breakpoint(number, gdb_pid=None) -> Dict:
    """删除断点"""
    return gdb_tools.gdb_delete_breakpoint(number, gdb_pid)

@mcp.tool(name="gdb_step")
def gdb_step(gdb_pid=None) -> Dict:
    """单步执行"""
    return gdb_tools.gdb_step(gdb_pid)

@mcp.tool(name="gdb_next")
def gdb_next(gdb_pid=None) -> Dict:
    """下一步执行"""
    return gdb_tools.gdb_next(gdb_pid)

@mcp.tool(name="gdb_finish")
def gdb_finish(gdb_pid=None) -> Dict:
    """运行至函数返回"""
    return gdb_tools.gdb_finish(gdb_pid)

@mcp.tool(name="gdb_continue")
def gdb_continue(gdb_pid=None) -> Dict:
    """继续执行"""
    return gdb_tools.gdb_continue(gdb_pid)

@mcp.tool(name="gdb_get_registers")
def gdb_get_registers(gdb_pid=None) -> Dict:
    """获取寄存器值"""
    return gdb_tools.gdb_get_registers(gdb_pid)

@mcp.tool(name="gdb_examine_memory")
def gdb_examine_memory(address, count="10", format_type="x", gdb_pid=None) -> Dict:
    """检查内存"""
    return gdb_tools.gdb_examine_memory(address, count, format_type, gdb_pid)

@mcp.tool(name="gdb_get_stack")
def gdb_get_stack(gdb_pid=None) -> Dict:
    """获取堆栈信息"""
    return gdb_tools.gdb_get_stack(gdb_pid)

@mcp.tool(name="gdb_get_locals")
def gdb_get_locals(gdb_pid=None) -> Dict:
    """获取局部变量"""
    return gdb_tools.gdb_get_locals(gdb_pid)

@mcp.tool(name="gdb_disassemble")
def gdb_disassemble(location="", gdb_pid=None) -> Dict:
    """反汇编代码"""
    return gdb_tools.gdb_disassemble(location, gdb_pid)

@mcp.tool(name="gdb_connect_remote")
def gdb_connect_remote(target_address, gdb_pid=None) -> Dict:
    """连接到远程调试目标"""
    return gdb_tools.gdb_connect_remote(target_address, gdb_pid)

if __name__ == "__main__":
    logger.info("启动GDB MCP服务器")
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("GDB MCP服务器已终止")
    except Exception as e:
        logger.error(f"GDB MCP服务器错误: {str(e)}")
        logger.error(traceback.format_exc())