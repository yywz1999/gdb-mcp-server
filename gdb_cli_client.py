#!/usr/bin/env python3
"""
GDB MCP 命令行客户端
用于直接测试MCP服务器功能，不依赖Cursor
"""

import sys
import json
import subprocess
import time
import argparse
import os

class GdbMcpClient:
    """GDB MCP客户端类"""
    
    def __init__(self, server_path="mcp_server.py"):
        """初始化客户端"""
        self.server_path = server_path
        self.server_process = None
        self.start_server()
    
    def start_server(self):
        """启动MCP服务器"""
        print(f"启动MCP服务器: {self.server_path}")
        self.server_process = subprocess.Popen(
            ["python3", self.server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        # 等待服务器启动
        time.sleep(1)
        print("MCP服务器已启动")
    
    def send_request(self, method, params=None, timeout=10):
        """发送请求到MCP服务器"""
        if not self.server_process:
            print("错误: MCP服务器未运行")
            return None
        
        if not params:
            params = {}
        
        request = {
            "method": method,
            "params": params
        }
        
        request_json = json.dumps(request)
        print(f"\n发送请求: {request_json}")
        
        try:
            self.server_process.stdin.write(request_json + "\n")
            self.server_process.stdin.flush()
            
            # 等待响应,带超时
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.server_process.stdout.readable():
                    response = self.server_process.stdout.readline().strip()
                    if response:
                        try:
                            return json.loads(response)
                        except json.JSONDecodeError:
                            print(f"错误: 无法解析响应: {response}")
                            return None
                time.sleep(0.1)
            
            print(f"错误: 请求超时 ({timeout}秒)")
            return None
            
        except Exception as e:
            print(f"错误: 发送请求失败: {str(e)}")
            return None
    
    def find_gdb_processes(self):
        """查找GDB进程"""
        print("查找GDB进程...")
        response = self.send_request("find_gdb_processes")
        if response and response.get("success"):
            result = response.get("result", {})
            processes = result.get("processes", [])
            print(f"找到 {len(processes)} 个GDB进程:")
            for i, proc in enumerate(processes):
                print(f"  [{i+1}] PID: {proc['pid']}, 命令: {proc['command']}, TTY: {proc['tty']}")
            return processes
        else:
            error = response.get("error") if response else "未知错误"
            print(f"查找GDB进程失败: {error}")
            return []
    
    def attach_to_gdb(self, gdb_pid=None):
        """附加到GDB进程"""
        params = {}
        if gdb_pid:
            params["gdb_pid"] = gdb_pid
        
        print(f"附加到GDB进程{' '+str(gdb_pid) if gdb_pid else ''}...")
        response = self.send_request("attach_to_gdb", params)
        if response and response.get("success"):
            result = response.get("result", {})
            success = result.get("success", False)
            message = result.get("message", "")
            if success:
                print(f"附加成功: {message}")
                return True
            else:
                print(f"附加失败: {message}")
                return False
        else:
            error = response.get("error") if response else "未知错误"
            print(f"附加到GDB进程失败: {error}")
            return False
    
    def set_breakpoint(self, location, gdb_pid=None):
        """设置断点"""
        params = {"location": location}
        if gdb_pid:
            params["gdb_pid"] = gdb_pid
        
        print(f"设置断点 '{location}'...")
        response = self.send_request("set_breakpoint", params)
        if response and response.get("success"):
            result = response.get("result", {})
            success = result.get("success", False)
            output = result.get("output", "")
            if success:
                print(f"断点设置成功: {output}")
                return True
            else:
                print(f"断点设置失败: {output}")
                return False
        else:
            error = response.get("error") if response else "未知错误"
            print(f"设置断点失败: {error}")
            return False
    
    def execute_command(self, command, gdb_pid=None):
        """执行GDB命令"""
        params = {"command": command}
        if gdb_pid:
            params["gdb_pid"] = gdb_pid
        
        print(f"执行命令 '{command}'...")
        response = self.send_request("execute_command", params)
        if response and response.get("success"):
            result = response.get("result", {})
            success = result.get("success", False)
            output = result.get("output", "")
            if success:
                print(f"命令执行成功: {output}")
                return True
            else:
                print(f"命令执行失败: {output}")
                return False
        else:
            error = response.get("error") if response else "未知错误"
            print(f"执行命令失败: {error}")
            return False
    
    def step(self, gdb_pid=None):
        """单步执行"""
        params = {}
        if gdb_pid:
            params["gdb_pid"] = gdb_pid
        
        print("单步执行...")
        response = self.send_request("step", params)
        if response and response.get("success"):
            result = response.get("result", {})
            success = result.get("success", False)
            output = result.get("output", "")
            if success:
                print(f"单步执行成功: {output}")
                return True
            else:
                print(f"单步执行失败: {output}")
                return False
        else:
            error = response.get("error") if response else "未知错误"
            print(f"单步执行失败: {error}")
            return False
    
    def continue_execution(self, gdb_pid=None):
        """继续执行"""
        params = {}
        if gdb_pid:
            params["gdb_pid"] = gdb_pid
        
        print("继续执行...")
        response = self.send_request("continue_execution", params)
        if response and response.get("success"):
            result = response.get("result", {})
            success = result.get("success", False)
            output = result.get("output", "")
            if success:
                print(f"继续执行成功: {output}")
                return True
            else:
                print(f"继续执行失败: {output}")
                return False
        else:
            error = response.get("error") if response else "未知错误"
            print(f"继续执行失败: {error}")
            return False
    
    def get_registers(self, gdb_pid=None):
        """获取寄存器值"""
        params = {}
        if gdb_pid:
            params["gdb_pid"] = gdb_pid
        
        print("获取寄存器值...")
        response = self.send_request("get_registers", params)
        if response and response.get("success"):
            result = response.get("result", {})
            success = result.get("success", False)
            output = result.get("output", "")
            if success:
                print(f"获取寄存器值成功: {output}")
                return True
            else:
                print(f"获取寄存器值失败: {output}")
                return False
        else:
            error = response.get("error") if response else "未知错误"
            print(f"获取寄存器值失败: {error}")
            return False
    
    def get_stack(self, gdb_pid=None):
        """获取调用栈"""
        params = {}
        if gdb_pid:
            params["gdb_pid"] = gdb_pid
        
        print("获取调用栈...")
        response = self.send_request("get_stack", params)
        if response and response.get("success"):
            result = response.get("result", {})
            success = result.get("success", False)
            output = result.get("output", "")
            if success:
                print(f"获取调用栈成功: {output}")
                return True
            else:
                print(f"获取调用栈失败: {output}")
                return False
        else:
            error = response.get("error") if response else "未知错误"
            print(f"获取调用栈失败: {error}")
            return False
    
    def close(self):
        """关闭客户端和服务器"""
        if self.server_process:
            print("\n关闭MCP服务器...")
            self.server_process.terminate()
            self.server_process.wait(timeout=5)
            self.server_process = None
            print("MCP服务器已关闭")

def run_interactive_mode(client):
    """运行交互模式"""
    print("\n==== GDB MCP 命令行客户端 ====")
    print("输入 'help' 查看可用命令，输入 'exit' 退出")
    
    while True:
        try:
            cmd = input("\n> ").strip()
            if not cmd:
                continue
            
            if cmd == "exit":
                break
            
            if cmd == "help":
                print("""
可用命令:
  find                     - 查找GDB进程
  attach [pid]             - 附加到GDB进程
  break <location>         - 设置断点
  delete <number>          - 删除断点
  step                     - 单步执行
  continue                 - 继续执行
  info registers           - 获取寄存器值
  backtrace                - 获取调用栈
  cmd <gdb_command>        - 执行GDB命令
  exit                     - 退出客户端
                """)
                continue
            
            parts = cmd.split()
            command = parts[0]
            
            if command == "find":
                client.find_gdb_processes()
            
            elif command == "attach":
                gdb_pid = parts[1] if len(parts) > 1 else None
                client.attach_to_gdb(gdb_pid)
            
            elif command == "break":
                if len(parts) < 2:
                    print("错误: 缺少断点位置")
                    continue
                client.set_breakpoint(parts[1])
            
            elif command == "delete":
                if len(parts) < 2:
                    print("错误: 缺少断点编号")
                    continue
                client.execute_command(f"delete {parts[1]}")
            
            elif command == "step":
                client.step()
            
            elif command == "continue":
                client.continue_execution()
            
            elif command == "info" and len(parts) > 1 and parts[1] == "registers":
                client.get_registers()
            
            elif command == "backtrace":
                client.get_stack()
            
            elif command == "cmd":
                if len(parts) < 2:
                    print("错误: 缺少GDB命令")
                    continue
                cmd_to_execute = " ".join(parts[1:])
                client.execute_command(cmd_to_execute)
            
            else:
                print(f"未知命令: {command}")
                print("输入 'help' 查看可用命令")
            
        except KeyboardInterrupt:
            print("\n中断输入")
            continue
        
        except Exception as e:
            print(f"错误: {str(e)}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="GDB MCP 命令行客户端")
    parser.add_argument("--server", default="mcp_server.py", help="MCP服务器路径")
    parser.add_argument("--command", help="执行单个命令后退出")
    args = parser.parse_args()
    
    # 为server路径添加绝对路径
    if not os.path.isabs(args.server):
        # 使用当前脚本所在目录作为相对路径的基准
        base_dir = os.path.dirname(os.path.abspath(__file__))
        args.server = os.path.join(base_dir, args.server)
    
    client = GdbMcpClient(args.server)
    
    try:
        if args.command:
            # 执行单个命令
            if args.command == "find":
                client.find_gdb_processes()
            elif args.command.startswith("attach"):
                parts = args.command.split()
                gdb_pid = parts[1] if len(parts) > 1 else None
                client.attach_to_gdb(gdb_pid)
            elif args.command.startswith("break"):
                parts = args.command.split()
                if len(parts) > 1:
                    client.set_breakpoint(parts[1])
                else:
                    print("错误: 缺少断点位置")
            else:
                print(f"未知命令: {args.command}")
        else:
            # 交互模式
            run_interactive_mode(client)
    finally:
        client.close()

if __name__ == "__main__":
    main() 