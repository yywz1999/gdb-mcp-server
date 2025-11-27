#!/usr/bin/env python3
"""GDB MCP工具函数"""

import logging
import traceback
from typing import Dict, Any
from comm_methods.gdb_communicator import GdbCommunicator

logger = logging.getLogger('gdb-mcp-server.tools')
gdb_communicator = None

def init_communicator():
    """初始化GDB通信器"""
    global gdb_communicator
    if gdb_communicator is None:
        gdb_communicator = GdbCommunicator()
        logger.info("通信器初始化完成")
    return gdb_communicator
def sys_find_gdb_processes(random_string="dummy") -> Dict[str, Any]:
    """查找系统中运行的所有GDB进程"""
    try:
        import subprocess
        processes = []
        cmd = ["ps", "-eo", "pid,tty,command"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        output, _ = process.communicate()
        output = output.decode('utf-8').strip()
        
        for line in output.split('\n')[1:]:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            
            pid = parts[0]
            tty = parts[1]
            cmd = ' '.join(parts[2:])
            
            if 'gdb' in cmd.lower():
                if '.py' in cmd or 'python' in cmd.lower():
                    continue
                    
                processes.append({
                    "pid": pid,
                    "tty": tty if tty != '?' else "未知",
                    "cmd": cmd
                })
        
        if processes:
            formatted_processes = [f"PID: {p['pid']}, TTY: {p['tty']}, CMD: {p['cmd']}" for p in processes]
            result_message = f"找到 {len(processes)} 个GDB进程:\n" + "\n".join(formatted_processes)
        else:
            result_message = "未找到任何GDB进程"
        
        return {
            "success": True,
            "output": str(processes),
            "formatted_result": result_message,
            "processes": processes,
            "has_output": True
        }
    except Exception as e:
        logger.error(f"查找GDB进程出错: {str(e)}")
        return {
            "success": False,
            "output": f"错误: {str(e)}",
            "formatted_result": f"查找GDB进程出错: {str(e)}",
            "processes": [],
            "has_output": True
        }

def sys_attach_to_gdb(gdb_pid=None, tty_device=None) -> Dict[str, Any]:
    """附加到现有的GDB进程"""
    comm = init_communicator()
    is_attached = comm.attach_to_gdb(gdb_pid, tty_device)
    
    if is_attached:
        if gdb_pid:
            result_message = f"成功附加到GDB进程 PID: {gdb_pid}"
        elif tty_device:
            result_message = f"成功附加到GDB终端 TTY: {tty_device}"
        else:
            result_message = "成功附加到GDB进程"
    else:
        if gdb_pid:
            result_message = f"附加到GDB进程 PID: {gdb_pid} 失败"
        elif tty_device:
            result_message = f"附加到GDB终端 TTY: {tty_device} 失败"
        else:
            result_message = "附加失败，未提供PID或TTY"
    
    return {
        "success": is_attached,
        "output": f"PID: {gdb_pid}, TTY: {tty_device}",
        "formatted_result": result_message,
        "is_attached": is_attached,
        "gdb_pid": gdb_pid,
        "tty_device": tty_device,
        "has_output": True
    }

# GDB相关工具
def gdb_execute_command(command, gdb_pid=None) -> Dict[str, Any]:
    """执行GDB命令"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    
    comm = init_communicator()
    success, output = comm.execute_command(command, gdb_pid)
    
    cmd_type = command.split()[0] if " " in command else command
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    result_message = f"执行命令: {command}\n{output}" if success else f"命令执行失败: {output}"
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": result_message,
        "command_type": cmd_type,
        "has_output": not command_sent_but_no_output
    }

def gdb_set_breakpoint(location, gdb_pid=None) -> Dict[str, Any]:
    """设置断点"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command(f"break {location}", gdb_pid)
    
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    blocked = "阻塞" in output and "中断" in output
    
    if success:
        result_message = f"设置断点 '{location}': {output}"
    else:
        result_message = f"设置断点失败: {output}"
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": result_message,
        "has_output": not command_sent_but_no_output,
        "blocked": blocked
    }

def gdb_delete_breakpoint(number, gdb_pid=None) -> Dict[str, Any]:
    """删除断点"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command(f"delete {number}", gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"删除断点 #{number}: {output}" if success else f"删除断点失败: {output}",
        "has_output": not command_sent_but_no_output
    }

def gdb_step(gdb_pid=None) -> Dict[str, Any]:
    """单步执行"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    comm = init_communicator()
    success, output = comm.execute_command("step", gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"单步执行: {output}" if success else f"单步执行失败: {output}",
        "has_output": not command_sent_but_no_output
    }

def gdb_next(gdb_pid=None) -> Dict[str, Any]:
    """下一步执行"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    comm = init_communicator()
    success, output = comm.execute_command("next", gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"下一步执行: {output}" if success else f"下一步执行失败: {output}",
        "has_output": not command_sent_but_no_output
    }

def gdb_finish(gdb_pid=None) -> Dict[str, Any]:
    """运行至函数返回"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    comm = init_communicator()
    success, output = comm.execute_command("finish", gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"运行至函数返回: {output}" if success else f"运行至函数返回失败: {output}",
        "has_output": not command_sent_but_no_output
    }

def gdb_continue(gdb_pid=None) -> Dict[str, Any]:
    """继续执行"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    comm = init_communicator()
    success, output = comm.execute_command("continue", gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    blocked = "阻塞" in output and "中断" in output
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"继续执行: {output}" if success else f"继续执行失败: {output}",
        "has_output": not command_sent_but_no_output,
        "blocked": blocked
    }

def gdb_get_registers(gdb_pid=None) -> Dict[str, Any]:
    """获取寄存器值"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    comm = init_communicator()
    success, output = comm.execute_command("info registers", gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"寄存器值: {output}" if success else f"获取寄存器值失败: {output}",
        "command": "info registers",
        "has_output": not command_sent_but_no_output
    }

def gdb_examine_memory(address, count="10", format_type="x", gdb_pid=None) -> Dict[str, Any]:
    """检查内存"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    count = str(count)
    command = f"x/{count}{format_type} {address}"
    
    comm = init_communicator()
    success, output = comm.execute_command(command, gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"检查内存 {address}: {output}" if success else f"检查内存失败: {output}",
        "command": command,
        "has_output": not command_sent_but_no_output
    }

def gdb_get_stack(gdb_pid=None) -> Dict[str, Any]:
    """获取堆栈信息"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    comm = init_communicator()
    success, output = comm.execute_command("backtrace", gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"堆栈回溯: {output}" if success else f"获取堆栈失败: {output}",
        "command": "backtrace",
        "has_output": not command_sent_but_no_output
    }

def gdb_get_locals(gdb_pid=None) -> Dict[str, Any]:
    """获取局部变量"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    comm = init_communicator()
    success, output = comm.execute_command("info locals", gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"局部变量: {output}" if success else f"获取局部变量失败: {output}",
        "command": "info locals",
        "has_output": not command_sent_but_no_output
    }

def gdb_disassemble(location="", gdb_pid=None) -> Dict[str, Any]:
    """反汇编代码"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
    command = "disassemble" if not location else f"disassemble {location}"
    
    comm = init_communicator()
    success, output = comm.execute_command(command, gdb_pid)
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": f"反汇编{' '+location if location else ''}: {output}" if success else f"反汇编失败: {output}",
        "command": command,
        "has_output": not command_sent_but_no_output
    }

def gdb_connect_remote(target_address, gdb_pid=None) -> Dict[str, Any]:
    """连接到远程调试目标"""
    if gdb_pid is not None:
        gdb_pid = str(gdb_pid)
        
    command = f"target remote {target_address}"
    comm = init_communicator()
    success, output = comm.execute_command(command, gdb_pid)
    
    command_sent_but_no_output = ("通过键盘事件发送" in output or "请在GDB终端中" in output)
    blocked = "阻塞" in output and "中断" in output
    
    result_message = f"连接远程目标 '{target_address}': {output}" if success else f"连接失败: {output}"
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": result_message,
        "command": command,
        "target_address": target_address,
        "has_output": not command_sent_but_no_output,
        "blocked": blocked
    }

def check_gdb_blocked() -> Dict:
    """检查GDB是否处于阻塞状态"""
    try:
        communicator = init_communicator()
        if not communicator or not hasattr(communicator, 'check_gdb_blocked'):
            return {"success": False, "blocked": False, "running_time": 0, "message": "不支持阻塞检测"}
        
        status = communicator.check_gdb_blocked()
        return {
            "success": True,
            "blocked": status["is_blocked"],
            "running_time": status["running_time"],
            "message": status["status"]
        }
    except Exception as e:
        logger.error(f"检查阻塞状态出错: {str(e)}")
        return {"success": False, "blocked": False, "running_time": 0, "message": f"出错: {str(e)}"} 