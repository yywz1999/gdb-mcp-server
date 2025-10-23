#!/usr/bin/env python3
"""
GDB MCP HTTP Server - 支持流式HTTP通信的MCP服务器
基于Flask和Server-Sent Events实现流式通信
"""

import os
import sys
import json
import logging
import traceback
import asyncio
import threading
import queue
import time
from typing import Dict, Any, Generator, Optional
from flask import Flask, request, jsonify, Response, stream_template
from flask_cors import CORS
import uuid

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('gdb-mcp-http-server')

# 导入工具函数
try:
    import gdb_tools
    logger.info("成功导入GDB工具函数")
except ImportError as e:
    logger.error(f"导入GDB工具函数失败: {e}")
    sys.exit(1)

class MCPHTTPServer:
    """MCP HTTP服务器类，支持流式通信"""

    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        CORS(self.app)  # 启用跨域支持

        # 客户端会话管理
        self.sessions = {}  # session_id -> session_data
        self.message_queues = {}  # session_id -> queue for SSE

        # 注册路由
        self._register_routes()

        logger.info(f"MCP HTTP服务器初始化完成，监听 {host}:{port}")

    def _register_routes(self):
        """注册HTTP路由"""

        @self.app.route('/health', methods=['GET'])
        def health_check():
            """健康检查端点"""
            return jsonify({
                "status": "healthy",
                "server": "GDB MCP HTTP Server",
                "version": "1.0.0",
                "timestamp": time.time()
            })

        @self.app.route('/mcp/info', methods=['GET'])
        def mcp_info():
            """MCP服务器信息"""
            return jsonify({
                "name": "GDB MCP Server",
                "version": "1.0.0",
                "description": "GDB调试工具的MCP服务器，支持HTTP流式通信",
                "transport": ["stdio", "http-streaming"],
                "capabilities": {
                    "tools": {
                        "listChanged": True
                    },
                    "resources": {},
                    "prompts": {}
                }
            })

        @self.app.route('/mcp/tools/list', methods=['GET'])
        def list_tools():
            """获取可用工具列表"""
            tools = [
                # 系统工具
                {
                    "name": "sys_find_gdb_processes",
                    "description": "查找系统中运行的所有GDB进程",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "random_string": {
                                "type": "string",
                                "description": "随机字符串参数（MCP协议要求）",
                                "default": "dummy"
                            }
                        }
                    }
                },
                {
                    "name": "sys_attach_to_gdb",
                    "description": "附加到现有的GDB进程",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID"
                            },
                            "tty_device": {
                                "type": "string",
                                "description": "TTY设备路径"
                            }
                        }
                    }
                },
                {
                    "name": "sys_start_gdb_with_remote",
                    "description": "启动GDB并连接到远程调试目标",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "target_address": {
                                "type": "string",
                                "description": "远程目标地址，如 192.168.1.100:1234"
                            },
                            "executable": {
                                "type": "string",
                                "description": "可执行文件路径（可选）"
                            }
                        },
                        "required": ["target_address"]
                    }
                },
                # GDB调试工具
                {
                    "name": "gdb_execute_command",
                    "description": "执行任意GDB命令",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "要执行的GDB命令"
                            },
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        },
                        "required": ["command"]
                    }
                },
                {
                    "name": "gdb_set_breakpoint",
                    "description": "设置断点",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "断点位置（函数名、行号或地址）"
                            },
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        },
                        "required": ["location"]
                    }
                },
                {
                    "name": "gdb_delete_breakpoint",
                    "description": "删除断点",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "number": {
                                "type": "string",
                                "description": "断点编号"
                            },
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        },
                        "required": ["number"]
                    }
                },
                {
                    "name": "gdb_step",
                    "description": "单步执行",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        }
                    }
                },
                {
                    "name": "gdb_next",
                    "description": "执行到下一行",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        }
                    }
                },
                {
                    "name": "gdb_finish",
                    "description": "执行到函数返回",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        }
                    }
                },
                {
                    "name": "gdb_continue",
                    "description": "继续执行",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        }
                    }
                },
                {
                    "name": "gdb_get_registers",
                    "description": "获取寄存器值",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        }
                    }
                },
                {
                    "name": "gdb_examine_memory",
                    "description": "检查内存",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "string",
                                "description": "内存地址"
                            },
                            "count": {
                                "type": "string",
                                "description": "检查的单元数量",
                                "default": "10"
                            },
                            "format_type": {
                                "type": "string",
                                "description": "显示格式 (x, d, i, s, c)",
                                "default": "x"
                            },
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        },
                        "required": ["address"]
                    }
                },
                {
                    "name": "gdb_get_stack",
                    "description": "获取堆栈信息",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        }
                    }
                },
                {
                    "name": "gdb_get_locals",
                    "description": "获取局部变量",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        }
                    }
                },
                {
                    "name": "gdb_disassemble",
                    "description": "反汇编代码",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "反汇编位置（函数名或地址，可选）"
                            },
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        }
                    }
                },
                {
                    "name": "gdb_connect_remote",
                    "description": "连接到远程调试目标",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "target_address": {
                                "type": "string",
                                "description": "远程目标地址"
                            },
                            "gdb_pid": {
                                "type": "string",
                                "description": "GDB进程ID（可选）"
                            }
                        },
                        "required": ["target_address"]
                    }
                }
            ]

            return jsonify({
                "tools": tools
            })

        @self.app.route('/mcp/session', methods=['POST'])
        def create_session():
            """创建新的会话"""
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {
                "created_at": time.time(),
                "last_activity": time.time(),
                "messages": []
            }
            self.message_queues[session_id] = queue.Queue()

            return jsonify({
                "session_id": session_id,
                "message": "会话创建成功"
            })

        @self.app.route('/mcp/session/<session_id>/stream', methods=['GET'])
        def stream_messages(session_id):
            """建立SSE连接，流式传输消息"""
            if session_id not in self.sessions:
                return jsonify({"error": "会话不存在"}), 404

            def generate():
                """生成SSE消息"""
                try:
                    # 发送连接确认消息
                    yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

                    # 持续监听消息队列
                    message_queue = self.message_queues[session_id]
                    while True:
                        try:
                            # 等待消息，设置超时避免阻塞
                            message = message_queue.get(timeout=1)
                            if message is None:  # 结束信号
                                break

                            # 发送SSE格式的消息
                            yield f"data: {json.dumps(message)}\n\n"

                        except queue.Empty:
                            # 发送心跳包保持连接
                            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
                            continue

                except GeneratorExit:
                    logger.info(f"SSE连接关闭: {session_id}")
                except Exception as e:
                    logger.error(f"SSE流错误 {session_id}: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return Response(
                generate(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Cache-Control'
                }
            )

        @self.app.route('/mcp/call', methods=['POST'])
        def call_tool():
            """调用工具（非流式）"""
            data = request.get_json()
            if not data:
                return jsonify({"error": "无效的JSON数据"}), 400

            tool_name = data.get('tool')
            arguments = data.get('arguments', {})
            session_id = data.get('session_id')

            if not tool_name:
                return jsonify({"error": "缺少工具名称"}), 400

            try:
                # 调用对应的工具函数
                result = self._call_tool_function(tool_name, arguments)

                response = {
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "success": True,
                    "timestamp": time.time()
                }

                # 如果有会话ID，将结果发送到消息队列
                if session_id and session_id in self.message_queues:
                    self.message_queues[session_id].put({
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": result,
                        "timestamp": time.time()
                    })

                return jsonify(response)

            except Exception as e:
                error_msg = f"调用工具 '{tool_name}' 失败: {str(e)}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")

                response = {
                    "tool": tool_name,
                    "arguments": arguments,
                    "error": error_msg,
                    "success": False,
                    "timestamp": time.time()
                }

                # 如果有会话ID，将错误发送到消息队列
                if session_id and session_id in self.message_queues:
                    self.message_queues[session_id].put({
                        "type": "tool_error",
                        "tool": tool_name,
                        "error": error_msg,
                        "timestamp": time.time()
                    })

                return jsonify(response), 500

        @self.app.route('/mcp/session/<session_id>/call', methods=['POST'])
        def call_tool_streaming(session_id):
            """流式调用工具"""
            if session_id not in self.sessions:
                return jsonify({"error": "会话不存在"}), 404

            data = request.get_json()
            if not data:
                return jsonify({"error": "无效的JSON数据"}), 400

            tool_name = data.get('tool')
            arguments = data.get('arguments', {})

            if not tool_name:
                return jsonify({"error": "缺少工具名称"}), 400

            # 在后台线程中执行工具调用
            def execute_tool():
                try:
                    # 发送开始消息
                    self.message_queues[session_id].put({
                        "type": "tool_start",
                        "tool": tool_name,
                        "arguments": arguments,
                        "timestamp": time.time()
                    })

                    # 调用工具函数
                    result = self._call_tool_function(tool_name, arguments)

                    # 发送结果消息
                    self.message_queues[session_id].put({
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": result,
                        "timestamp": time.time()
                    })

                except Exception as e:
                    error_msg = f"调用工具 '{tool_name}' 失败: {str(e)}"
                    logger.error(f"{error_msg}\n{traceback.format_exc()}")

                    # 发送错误消息
                    self.message_queues[session_id].put({
                        "type": "tool_error",
                        "tool": tool_name,
                        "error": error_msg,
                        "timestamp": time.time()
                    })

            # 启动后台线程
            thread = threading.Thread(target=execute_tool)
            thread.daemon = True
            thread.start()

            return jsonify({
                "message": "工具调用已开始",
                "tool": tool_name,
                "session_id": session_id
            })

        @self.app.route('/mcp/session/<session_id>', methods=['DELETE'])
        def close_session(session_id):
            """关闭会话"""
            if session_id not in self.sessions:
                return jsonify({"error": "会话不存在"}), 404

            # 发送结束信号
            if session_id in self.message_queues:
                self.message_queues[session_id].put(None)
                del self.message_queues[session_id]

            del self.sessions[session_id]

            return jsonify({
                "message": "会话已关闭",
                "session_id": session_id
            })

    def _call_tool_function(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用对应的工具函数"""

        # 获取工具函数映射
        tool_functions = {
            "sys_find_gdb_processes": gdb_tools.sys_find_gdb_processes,
            "sys_attach_to_gdb": gdb_tools.sys_attach_to_gdb,
            "sys_start_gdb_with_remote": gdb_tools.sys_start_gdb_with_remote,
            "gdb_execute_command": gdb_tools.gdb_execute_command,
            "gdb_set_breakpoint": gdb_tools.gdb_set_breakpoint,
            "gdb_delete_breakpoint": gdb_tools.gdb_delete_breakpoint,
            "gdb_step": gdb_tools.gdb_step,
            "gdb_next": gdb_tools.gdb_next,
            "gdb_finish": gdb_tools.gdb_finish,
            "gdb_continue": gdb_tools.gdb_continue,
            "gdb_get_registers": gdb_tools.gdb_get_registers,
            "gdb_examine_memory": gdb_tools.gdb_examine_memory,
            "gdb_get_stack": gdb_tools.gdb_get_stack,
            "gdb_get_locals": gdb_tools.gdb_get_locals,
            "gdb_disassemble": gdb_tools.gdb_disassemble,
            "gdb_connect_remote": gdb_tools.gdb_connect_remote,
        }

        if tool_name not in tool_functions:
            raise ValueError(f"未知的工具: {tool_name}")

        tool_func = tool_functions[tool_name]

        # 根据工具名称调用相应的函数
        if tool_name == "sys_find_gdb_processes":
            return tool_func(arguments.get("random_string", "dummy"))
        elif tool_name == "sys_attach_to_gdb":
            return tool_func(
                arguments.get("gdb_pid"),
                arguments.get("tty_device")
            )
        elif tool_name == "sys_start_gdb_with_remote":
            return tool_func(
                arguments.get("target_address"),
                arguments.get("executable")
            )
        elif tool_name == "gdb_execute_command":
            return tool_func(
                arguments.get("command"),
                arguments.get("gdb_pid")
            )
        elif tool_name in ["gdb_set_breakpoint", "gdb_delete_breakpoint"]:
            if tool_name == "gdb_set_breakpoint":
                return tool_func(
                    arguments.get("location"),
                    arguments.get("gdb_pid")
                )
            else:  # gdb_delete_breakpoint
                return tool_func(
                    arguments.get("number"),
                    arguments.get("gdb_pid")
                )
        elif tool_name in ["gdb_step", "gdb_next", "gdb_finish", "gdb_continue"]:
            return tool_func(arguments.get("gdb_pid"))
        elif tool_name == "gdb_get_registers":
            return tool_func(arguments.get("gdb_pid"))
        elif tool_name == "gdb_examine_memory":
            return tool_func(
                arguments.get("address"),
                arguments.get("count", "10"),
                arguments.get("format_type", "x"),
                arguments.get("gdb_pid")
            )
        elif tool_name in ["gdb_get_stack", "gdb_get_locals"]:
            return tool_func(arguments.get("gdb_pid"))
        elif tool_name == "gdb_disassemble":
            return tool_func(
                arguments.get("location", ""),
                arguments.get("gdb_pid")
            )
        elif tool_name == "gdb_connect_remote":
            return tool_func(
                arguments.get("target_address"),
                arguments.get("gdb_pid")
            )
        else:
            # 对于其他工具，直接调用
            return tool_func(**arguments)

    def run(self):
        """启动HTTP服务器"""
        logger.info(f"启动GDB MCP HTTP服务器，监听 {self.host}:{self.port}")
        logger.info("服务器信息:")
        logger.info(f"  - 健康检查: http://{self.host}:{self.port}/health")
        logger.info(f"  - MCP信息: http://{self.host}:{self.port}/mcp/info")
        logger.info(f"  - 工具列表: http://{self.host}:{self.port}/mcp/tools/list")
        logger.info(f"  - 创建会话: POST http://{self.host}:{self.port}/mcp/session")
        logger.info(f"  - 流式连接: GET http://{self.host}:{self.port}/mcp/session/<session_id>/stream")
        logger.info(f"  - 工具调用: POST http://{self.host}:{self.port}/mcp/call")

        self.app.run(
            host=self.host,
            port=self.port,
            threaded=True,
            debug=False
        )

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="GDB MCP HTTP服务器")
    parser.add_argument("--host", default="0.0.0.0", help="监听主机地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="监听端口 (默认: 8080)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="日志级别 (默认: INFO)")

    args = parser.parse_args()

    # 设置日志级别
    logging.getLogger('gdb-mcp-http-server').setLevel(getattr(logging, args.log_level))

    # 创建并启动服务器
    server = MCPHTTPServer(host=args.host, port=args.port)

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("服务器已终止")
    except Exception as e:
        logger.error(f"服务器错误: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()