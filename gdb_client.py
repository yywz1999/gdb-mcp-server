#!/usr/bin/env python3
"""
GDB客户端
用于与统一GDB服务器通信
"""

import requests
import json
import logging
from typing import Dict, Any, Tuple, List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('gdb-client')

class GdbClient:
    """GDB客户端类"""
    
    def __init__(self, host: str = 'localhost', port: int = 13946):
        """初始化GDB客户端
        
        参数:
            host: GDB服务器主机名
            port: GDB服务器端口号
        """
        self.base_url = f"http://{host}:{port}"
        self.api_url = f"{self.base_url}/api"
        self.mcp_url = f"{self.base_url}/mcp"
    
    def _request(self, endpoint: str, method: str = 'GET', data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送HTTP请求到服务器
        
        参数:
            endpoint: API端点
            method: HTTP方法(GET或POST)
            data: 要发送的数据
            
        返回:
            dict: 服务器响应
        """
        url = f"{self.api_url}/{endpoint}"
        try:
            if method == 'GET':
                response = requests.get(url)
            else:  # POST
                response = requests.post(url, json=data)
            return response.json()
        except requests.RequestException as e:
            return {
                "success": False,
                "message": f"与服务器通信时出错: {str(e)}",
                "output": ""
            }
    
    def _mcp_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送MCP请求到服务器
        
        参数:
            method: MCP方法名
            params: 方法参数
            
        返回:
            dict: MCP响应
        """
        try:
            response = requests.post(self.mcp_url, json={
                "method": method,
                "params": params or {}
            })
            return response.json()
        except requests.RequestException as e:
            return {
                "success": False,
                "error": f"MCP请求出错: {str(e)}"
            }
    
    def status(self) -> bool:
        """检查GDB是否运行
        
        返回:
            bool: GDB是否运行
        """
        result = self._request('status')
        return result.get('isRunning', False)
    
    def attach(self, pid: Optional[int] = None, tty: Optional[str] = None) -> Tuple[bool, str]:
        """附加到GDB进程
        
        参数:
            pid: GDB进程的PID(可选)
            tty: TTY设备路径(可选)
            
        返回:
            tuple: (成功标志, 消息)
        """
        result = self._request('attach', method='POST', data={'pid': pid, 'tty': tty})
        return result.get('success', False), result.get('message', '')
    
    def execute(self, command: str, pid: Optional[int] = None) -> Tuple[bool, str]:
        """执行GDB命令
        
        参数:
            command: 要执行的GDB命令
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        result = self._request('execute', method='POST', data={
            'command': command,
            'pid': pid
        })
        return result.get('success', False), result.get('output', '')
    
    def set_breakpoint(self, location: str, pid: Optional[int] = None) -> Tuple[bool, str]:
        """设置断点
        
        参数:
            location: 断点位置(函数名、行号等)
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        # 使用MCP协议
        result = self._mcp_request('set_breakpoint', {
            'location': location,
            'gdb_pid': pid
        })
        return result.get('success', False), result.get('output', '')
    
    def delete_breakpoint(self, number: str, pid: Optional[int] = None) -> Tuple[bool, str]:
        """删除断点
        
        参数:
            number: 断点编号
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        result = self._mcp_request('delete_breakpoint', {
            'number': number,
            'gdb_pid': pid
        })
        return result.get('success', False), result.get('output', '')
    
    def step(self, pid: Optional[int] = None) -> Tuple[bool, str]:
        """单步执行
        
        参数:
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        result = self._mcp_request('step', {'gdb_pid': pid})
        return result.get('success', False), result.get('output', '')
    
    def continue_execution(self, pid: Optional[int] = None) -> Tuple[bool, str]:
        """继续执行
        
        参数:
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        result = self._mcp_request('continue_execution', {'gdb_pid': pid})
        return result.get('success', False), result.get('output', '')
    
    def get_registers(self, pid: Optional[int] = None) -> Tuple[bool, str]:
        """获取寄存器值
        
        参数:
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        result = self._mcp_request('get_registers', {'gdb_pid': pid})
        return result.get('success', False), result.get('output', '')
    
    def examine_memory(self, address: str, count: str = '10', format_type: str = 'x', pid: Optional[int] = None) -> Tuple[bool, str]:
        """检查内存
        
        参数:
            address: 内存地址
            count: 显示的单元数
            format_type: 格式类型(x为十六进制,d为十进制等)
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        result = self._mcp_request('examine_memory', {
            'address': address,
            'count': count,
            'format_type': format_type,
            'gdb_pid': pid
        })
        return result.get('success', False), result.get('output', '')
    
    def get_stack(self, pid: Optional[int] = None) -> Tuple[bool, str]:
        """获取堆栈信息
        
        参数:
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        result = self._mcp_request('get_stack', {'gdb_pid': pid})
        return result.get('success', False), result.get('output', '')
    
    def get_locals(self, pid: Optional[int] = None) -> Tuple[bool, str]:
        """获取局部变量
        
        参数:
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        result = self._mcp_request('get_locals', {'gdb_pid': pid})
        return result.get('success', False), result.get('output', '')
    
    def disassemble(self, location: str = '', pid: Optional[int] = None) -> Tuple[bool, str]:
        """反汇编代码
        
        参数:
            location: 要反汇编的位置(函数名、地址范围等)
            pid: 目标GDB进程的PID(可选)
            
        返回:
            tuple: (成功标志, 输出)
        """
        result = self._mcp_request('disassemble', {
            'location': location,
            'gdb_pid': pid
        })
        return result.get('success', False), result.get('output', '')

# 命令行接口
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python gdb_client.py <命令>")
        sys.exit(1)
    
    client = GdbClient()
    command = sys.argv[1]
    
    if command == "status":
        is_running = client.status()
        print(f"GDB运行状态: {'运行中' if is_running else '未运行'}")
    
    elif command == "attach":
        if len(sys.argv) > 2:
            success, message = client.attach(int(sys.argv[2]))
        else:
            success, message = client.attach()
        print(f"附加到GDB: {'成功' if success else '失败'}")
        print(message)
    
    elif command == "exec":
        if len(sys.argv) < 3:
            print("用法: python gdb_client.py exec <gdb命令>")
            sys.exit(1)
        gdb_command = sys.argv[2]
        success, output = client.execute(gdb_command)
        print(f"命令执行: {'成功' if success else '失败'}")
        print(output)
    
    else:
        print(f"未知命令: {command}")
        print("可用命令: status, attach, exec")
        sys.exit(1)