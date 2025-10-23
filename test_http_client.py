#!/usr/bin/env python3
"""
GDB MCP HTTP服务器测试客户端
用于测试HTTP流式通信功能
"""

import requests
import json
import time
import threading
import sys
from typing import Optional

class MCPHTTPClient:
    """MCP HTTP客户端"""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.session_id = None

    def health_check(self) -> bool:
        """健康检查"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"健康检查失败: {e}")
            return False

    def get_mcp_info(self) -> dict:
        """获取MCP服务器信息"""
        try:
            response = requests.get(f"{self.base_url}/mcp/info", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"获取MCP信息失败: {response.status_code}")
                return {}
        except Exception as e:
            print(f"获取MCP信息异常: {e}")
            return {}

    def list_tools(self) -> list:
        """获取工具列表"""
        try:
            response = requests.get(f"{self.base_url}/mcp/tools/list", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("tools", [])
            else:
                print(f"获取工具列表失败: {response.status_code}")
                return []
        except Exception as e:
            print(f"获取工具列表异常: {e}")
            return []

    def create_session(self) -> bool:
        """创建会话"""
        try:
            response = requests.post(f"{self.base_url}/mcp/session", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.session_id = data.get("session_id")
                print(f"会话创建成功: {self.session_id}")
                return True
            else:
                print(f"创建会话失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"创建会话异常: {e}")
            return False

    def call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """调用工具（非流式）"""
        if arguments is None:
            arguments = {}

        data = {
            "tool": tool_name,
            "arguments": arguments
        }

        if self.session_id:
            data["session_id"] = self.session_id

        try:
            response = requests.post(
                f"{self.base_url}/mcp/call",
                json=data,
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"调用工具失败: {response.status_code}")
                print(f"错误响应: {response.text}")
                return {}
        except Exception as e:
            print(f"调用工具异常: {e}")
            return {}

    def call_tool_streaming(self, tool_name: str, arguments: dict = None):
        """流式调用工具"""
        if arguments is None:
            arguments = {}

        if not self.session_id:
            print("需要先创建会话")
            return

        data = {
            "tool": tool_name,
            "arguments": arguments
        }

        try:
            response = requests.post(
                f"{self.base_url}/mcp/session/{self.session_id}/call",
                json=data,
                timeout=5
            )
            if response.status_code == 200:
                print(f"工具 '{tool_name}' 已开始执行")
                return True
            else:
                print(f"启动流式工具调用失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"启动流式工具调用异常: {e}")
            return False

    def listen_messages(self, callback=None, timeout: int = 30):
        """监听流式消息"""
        if not self.session_id:
            print("需要先创建会话")
            return

        try:
            response = requests.get(
                f"{self.base_url}/mcp/session/{self.session_id}/stream",
                stream=True,
                timeout=timeout
            )

            if response.status_code == 200:
                print("开始监听流式消息...")

                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            try:
                                message = json.loads(line[6:])

                                if callback:
                                    callback(message)
                                else:
                                    # 默认处理
                                    msg_type = message.get('type', 'unknown')
                                    if msg_type == 'connected':
                                        print(f"[CONNECTED] 连接已建立")
                                    elif msg_type == 'heartbeat':
                                        print(f"[HEARTBEAT] 心跳: {time.strftime('%H:%M:%S')}")
                                    elif msg_type == 'tool_start':
                                        print(f"[START] 开始执行工具: {message.get('tool')}")
                                    elif msg_type == 'tool_result':
                                        print(f"[RESULT] 工具执行完成: {message.get('tool')}")
                                        result = message.get('result', {})
                                        if result.get('success'):
                                            print(f"   结果: {result.get('formatted_result', 'N/A')}")
                                        else:
                                            print(f"   失败: {result.get('formatted_result', 'N/A')}")
                                    elif msg_type == 'tool_error':
                                        print(f"[ERROR] 工具执行错误: {message.get('tool')}")
                                        print(f"   错误: {message.get('error', 'N/A')}")
                                    elif msg_type == 'error':
                                        print(f"[SERVER_ERROR] 服务器错误: {message.get('message', 'N/A')}")
                                    else:
                                        print(f"[UNKNOWN] 未知消息: {message}")

                            except json.JSONDecodeError:
                                print(f"无法解析消息: {line}")
            else:
                print(f"监听消息失败: {response.status_code}")

        except Exception as e:
            print(f"监听消息异常: {e}")

    def close_session(self):
        """关闭会话"""
        if not self.session_id:
            return

        try:
            response = requests.delete(
                f"{self.base_url}/mcp/session/{self.session_id}",
                timeout=5
            )
            if response.status_code == 200:
                print(f"会话 {self.session_id} 已关闭")
                self.session_id = None
            else:
                print(f"关闭会话失败: {response.status_code}")
        except Exception as e:
            print(f"关闭会话异常: {e}")

def test_basic_functionality(client: MCPHTTPClient):
    """测试基本功能"""
    print("\n" + "="*50)
    print("测试基本功能")
    print("="*50)

    # 健康检查
    print("1. 健康检查...")
    if client.health_check():
        print("[OK] 服务器健康")
    else:
        print("[ERROR] 服务器不健康")
        return False

    # 获取MCP信息
    print("\n2. 获取MCP服务器信息...")
    info = client.get_mcp_info()
    if info:
        print(f"[OK] 服务器名称: {info.get('name', 'Unknown')}")
        print(f"   版本: {info.get('version', 'Unknown')}")
        print(f"   描述: {info.get('description', 'Unknown')}")
    else:
        print("[ERROR] 无法获取服务器信息")
        return False

    # 获取工具列表
    print("\n3. 获取工具列表...")
    tools = client.list_tools()
    if tools:
        print(f"[OK] 找到 {len(tools)} 个工具:")
        for tool in tools[:5]:  # 只显示前5个
            print(f"   - {tool.get('name')}: {tool.get('description', 'No description')}")
        if len(tools) > 5:
            print(f"   ... 还有 {len(tools) - 5} 个工具")
    else:
        print("[ERROR] 无法获取工具列表")
        return False

    return True

def test_gdb_operations(client: MCPHTTPClient):
    """测试GDB操作"""
    print("\n" + "="*50)
    print("测试GDB操作")
    print("="*50)

    # 创建会话
    print("1. 创建会话...")
    if not client.create_session():
        print("[ERROR] 无法创建会话")
        return False

    # 测试查找GDB进程
    print("\n2. 查找GDB进程...")
    result = client.call_tool("sys_find_gdb_processes", {"random_string": "test"})
    if result and result.get("success"):
        print("[OK] GDB进程查找成功")
        processes = result.get("result", {}).get("processes", [])
        if processes:
            print(f"   找到 {len(processes)} 个GDB进程:")
            for proc in processes[:3]:  # 只显示前3个
                print(f"   - PID: {proc.get('pid')}, CMD: {proc.get('cmd', 'Unknown')}")
        else:
            print("   没有找到运行中的GDB进程")
    else:
        print("[WARNING] GDB进程查找失败或无进程")

    # 测试执行简单命令（不需要实际GDB连接）
    print("\n3. 测试命令执行...")
    # 这里只是测试API调用，实际执行需要GDB进程
    result = client.call_tool("gdb_execute_command", {"command": "help"})
    if result:
        print("[OK] 命令调用API正常")
        success = result.get("success")
        if success:
            print("   命令执行成功")
        else:
            print(f"   命令执行失败（预期行为）: {result.get('error', 'Unknown error')}")
    else:
        print("[ERROR] 命令调用API失败")

    return True

def test_streaming(client: MCPHTTPClient):
    """测试流式通信"""
    print("\n" + "="*50)
    print("测试流式通信")
    print("="*50)

    if not client.session_id:
        print("需要先创建会话")
        if not client.create_session():
            print("[ERROR] 无法创建会话")
            return False

    # 启动消息监听线程
    def message_listener():
        client.listen_messages(timeout=10)

    listener_thread = threading.Thread(target=message_listener)
    listener_thread.daemon = True
    listener_thread.start()

    # 等待监听器启动
    time.sleep(1)

    # 启动流式工具调用
    print("启动流式GDB进程查找...")
    if client.call_tool_streaming("sys_find_gdb_processes", {"random_string": "streaming_test"}):
        print("[OK] 流式调用已启动")
        time.sleep(5)  # 等待消息处理
    else:
        print("[ERROR] 流式调用启动失败")

    return True

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="GDB MCP HTTP服务器测试客户端")
    parser.add_argument("--url", default="http://localhost:8080", help="服务器地址")
    parser.add_argument("--test", choices=["basic", "gdb", "streaming", "all"],
                       default="all", help="测试类型")
    parser.add_argument("--timeout", type=int, default=30, help="超时时间（秒）")

    args = parser.parse_args()

    print("GDB MCP HTTP服务器测试客户端")
    print(f"服务器地址: {args.url}")
    print(f"测试类型: {args.test}")
    print("="*60)

    # 创建客户端
    client = MCPHTTPClient(args.url)

    try:
        # 根据参数执行测试
        if args.test in ["basic", "all"]:
            if not test_basic_functionality(client):
                print("基本功能测试失败")
                return 1

        if args.test in ["gdb", "all"]:
            if not test_gdb_operations(client):
                print("GDB操作测试失败")

        if args.test in ["streaming", "all"]:
            if not test_streaming(client):
                print("流式通信测试失败")

        print("\n" + "="*60)
        print("测试完成")

    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理会话
        if client.session_id:
            client.close_session()

    return 0

if __name__ == "__main__":
    sys.exit(main())