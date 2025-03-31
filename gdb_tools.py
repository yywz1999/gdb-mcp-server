#!/usr/bin/env python3
"""
GDB MCP工具函数 - 包含所有与GDB交互的MCP工具函数
"""

import os
import sys
import json
import logging
import traceback
from typing import Dict, List, Any, Optional, Union, Tuple

# 导入GDB通信器
from comm_methods.gdb_communicator import GdbCommunicator

# 设置日志记录器
logger = logging.getLogger('gdb-mcp-server.tools')

# 全局变量
gdb_communicator = None

def init_communicator():
    """初始化GDB通信器"""
    global gdb_communicator
    if gdb_communicator is None:
        from comm_methods.gdb_communicator import GdbCommunicator
        gdb_communicator = GdbCommunicator()
        logger.info("GDB工具通信器初始化完成")
    return gdb_communicator

# 系统相关工具
def sys_find_gdb_processes(random_string="dummy") -> Dict[str, Any]:
    """查找系统中运行的所有GDB进程"""
    logger.info("调用find_gdb_processes工具")
    
    try:
        import subprocess
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
    except Exception as e:
        logger.error(f"查找GDB进程时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "output": f"错误: {str(e)}",
            "formatted_result": f"查找GDB进程时出错: {str(e)}",
            "processes": [],
            "has_output": True
        }

def sys_attach_to_gdb(gdb_pid=None, tty_device=None) -> Dict[str, Any]:
    """附加到现有的GDB进程"""
    logger.info(f"调用attach_to_gdb工具: gdb_pid={gdb_pid}, tty_device={tty_device}")
    
    comm = init_communicator()
    is_attached = comm.attach_to_gdb(gdb_pid, tty_device)
    
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

# GDB相关工具
def gdb_execute_command(command, gdb_pid=None) -> Dict[str, Any]:
    """执行GDB命令"""
    logger.info(f"调用execute_command工具: command={command}, gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    
    # 执行命令
    comm = init_communicator()
    success, output = comm.execute_command(command, gdb_pid)
    
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

def gdb_set_breakpoint(location, gdb_pid=None) -> Dict[str, Any]:
    """设置断点"""
    logger.info(f"调用set_breakpoint工具: location={location}, gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command(f"break {location}", gdb_pid)
    
    # 检测命令是否发送成功但无法获取结果
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    # 检查是否出现阻塞情况
    blocked = "命令执行时阻塞" in output and "已发送中断信号" in output
    
    if success:
        if blocked:
            result_message = f"设置断点 '{location}' 时出现阻塞并已中断: {output}"
            logger.warning(f"设置断点时出现阻塞: {location}")
        else:
            result_message = f"设置断点 '{location}': {output}"
    else:
        result_message = f"设置断点 '{location}' 失败: {output}"
    
    logger.info(f"set_breakpoint返回: success={success}")
    logger.debug(f"set_breakpoint输出: {output}")
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": result_message,
        "has_output": not command_sent_but_no_output,
        "blocked": blocked
    }

def gdb_delete_breakpoint(number, gdb_pid=None) -> Dict[str, Any]:
    """删除断点"""
    logger.info(f"调用delete_breakpoint工具: number={number}, gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command(f"delete {number}", gdb_pid)
    
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

def gdb_step(gdb_pid=None) -> Dict[str, Any]:
    """单步执行"""
    logger.info(f"调用step工具: gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command("step", gdb_pid)
    
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

def gdb_next(gdb_pid=None) -> Dict[str, Any]:
    """下一步执行"""
    logger.info(f"调用next工具: gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command("next", gdb_pid)
    
    # 检测命令是否发送成功但无法获取结果
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    if success:
        result_message = f"下一步执行: {output}"
    else:
        result_message = f"下一步执行失败: {output}"
    
    logger.info(f"next返回: success={success}")
    logger.debug(f"next输出: {output}")
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": result_message,
        "has_output": not command_sent_but_no_output
    }

def gdb_finish(gdb_pid=None) -> Dict[str, Any]:
    """运行至函数返回"""
    logger.info(f"调用finish工具: gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command("finish", gdb_pid)
    
    # 检测命令是否发送成功但无法获取结果
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    if success:
        result_message = f"运行至函数返回: {output}"
    else:
        result_message = f"运行至函数返回失败: {output}"
    
    logger.info(f"finish返回: success={success}")
    logger.debug(f"finish输出: {output}")
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": result_message,
        "has_output": not command_sent_but_no_output
    }

def gdb_continue(gdb_pid=None) -> Dict[str, Any]:
    """继续执行"""
    logger.info(f"调用continue_execution工具: gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command("continue", gdb_pid)
    
    # 检测命令是否发送成功但无法获取结果
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    # 检查是否出现阻塞情况
    blocked = "命令执行时阻塞" in output and "已发送中断信号" in output
    
    if success:
        if blocked:
            result_message = f"继续执行时出现阻塞并已中断: {output}"
            logger.warning("继续执行命令时出现阻塞")
        else:
            result_message = f"继续执行: {output}"
    else:
        result_message = f"继续执行失败: {output}"
    
    logger.info(f"continue_execution返回: success={success}")
    logger.debug(f"continue_execution输出: {output}")
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": result_message,
        "has_output": not command_sent_but_no_output,
        "blocked": blocked
    }

def gdb_get_registers(gdb_pid=None) -> Dict[str, Any]:
    """获取寄存器值"""
    logger.info(f"调用get_registers工具: gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command("info registers", gdb_pid)
    
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

def gdb_examine_memory(address, count="10", format_type="x", gdb_pid=None) -> Dict[str, Any]:
    """检查内存"""
    logger.info(f"调用examine_memory工具: address={address}, count={count}, format_type={format_type}, gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    # 确保count是字符串类型
    count = str(count)
    
    command = f"x/{count}{format_type} {address}"
    
    comm = init_communicator()
    success, output = comm.execute_command(command, gdb_pid)
    
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

def gdb_get_stack(gdb_pid=None) -> Dict[str, Any]:
    """获取堆栈信息"""
    logger.info(f"调用get_stack工具: gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command("backtrace", gdb_pid)
    
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
        "command": "backtrace",
        "has_output": not command_sent_but_no_output
    }

def gdb_get_locals(gdb_pid=None) -> Dict[str, Any]:
    """获取局部变量"""
    logger.info(f"调用get_locals工具: gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command("info locals", gdb_pid)
    
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

def gdb_disassemble(location="", gdb_pid=None) -> Dict[str, Any]:
    """反汇编代码"""
    logger.info(f"调用disassemble工具: location={location}, gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    command = "disassemble" if not location else f"disassemble {location}"
    
    comm = init_communicator()
    success, output = comm.execute_command(command, gdb_pid)
    
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

def gdb_connect_remote(target_address, gdb_pid=None) -> Dict[str, Any]:
    """连接到远程调试目标"""
    logger.info(f"调用connect_remote工具: target_address={target_address}, gdb_pid={gdb_pid}")
    # 强制转换gdb_pid为字符串类型(如果提供了)
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    command = f"target remote {target_address}"
    
    comm = init_communicator()
    success, output = comm.execute_command(command, gdb_pid)
    
    # 检测命令是否发送成功但无法获取结果
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    # 检查是否出现阻塞情况
    blocked = "命令执行时阻塞" in output and "已发送中断信号" in output
    
    # 处理阻塞和连接情况
    if success:
        if blocked:
            # 连接已经建立但可能被中断了，尝试提取从输出中得到的信息
            result_message = f"连接到远程调试目标 '{target_address}'，但过程中出现阻塞并已中断: {output}"
            logger.info("远程连接已建立但过程中被中断")
        else:
            result_message = f"连接到远程调试目标 '{target_address}': {output}"
    else:
        result_message = f"连接到远程调试目标 '{target_address}' 失败: {output}"
    
    logger.info(f"connect_remote返回: success={success}")
    logger.debug(f"connect_remote输出: {output}")
    
    # 如果连接成功，尝试获取远程目标的基本信息
    target_info = ""
    if success and not command_sent_but_no_output and not blocked:
        try:
            # 尝试获取共享库信息
            _, lib_output = comm.execute_command("info sharedlibrary", gdb_pid)
            if lib_output and not ("通过键盘事件发送" in lib_output or "请在GDB终端中" in lib_output):
                target_info += f"\n共享库信息:\n{lib_output}"
            
            # 尝试获取寄存器信息
            _, reg_output = comm.execute_command("info registers", gdb_pid)
            if reg_output and not ("通过键盘事件发送" in reg_output or "请在GDB终端中" in reg_output):
                target_info += f"\n寄存器信息:\n{reg_output}"
        except Exception as e:
            logger.error(f"获取远程调试附加信息时出错: {str(e)}")
    
    if target_info:
        result_message += f"\n\n远程目标信息:{target_info}"
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": result_message,
        "command": command,
        "target_address": target_address,
        "has_output": not command_sent_but_no_output,
        "has_target_info": bool(target_info),
        "blocked": blocked
    }

def sys_start_gdb_with_remote(target_address, executable=None) -> Dict[str, Any]:
    """启动GDB并连接到远程调试目标"""
    logger.info(f"调用start_gdb_with_remote工具: target_address={target_address}, executable={executable}")
    
    comm = init_communicator()
    success, output = comm.start_gdb_with_remote(target_address, executable)
    
    if success:
        result_message = f"启动GDB并连接到远程目标 '{target_address}' 成功"
        if executable:
            result_message += f"，加载程序: {executable}"
    else:
        result_message = f"启动GDB并连接到远程目标 '{target_address}' 失败: {output}"
    
    logger.info(f"start_gdb_with_remote返回: success={success}")
    logger.debug(f"start_gdb_with_remote输出: {output[:100] if len(output) > 100 else output}...")
    
    return {
        "success": success,
        "output": output,
        "formatted_result": result_message,
        "target_address": target_address,
        "executable": executable,
        "has_output": True
    } 