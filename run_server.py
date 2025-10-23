#!/usr/bin/env python3
"""
GDB MCP Server 启动脚本
支持stdio和HTTP流式两种通信模式
"""

import os
import sys
import argparse
import logging
import traceback

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("gdb-mcp-launcher")


def run_stdio_server():
    """运行stdio模式的MCP服务器"""
    logger.info("启动stdio模式的MCP服务器...")

    try:
        # 导入并运行stdio服务器
        import mcp_server

        # 启动服务器
        logger.info("启动GDB MCP服务器")
        try:
            mcp_server.mcp.run()
        except KeyboardInterrupt:
            logger.info("GDB MCP服务器已终止")
        except Exception as e:
            logger.error(f"GDB MCP服务器错误: {str(e)}")
            logger.error(traceback.format_exc())
            logger.info("stdio服务器启动成功")
        except ImportError as e:
            logger.error(f"导入stdio服务器失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("stdio服务器已终止")
    except Exception as e:
        logger.error(f"stdio服务器错误: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)


def run_http_server(host="0.0.0.0", port=8080):
    """运行HTTP流式模式的MCP服务器"""
    logger.info(f"启动HTTP流式模式的MCP服务器，监听 {host}:{port}...")

    try:
        # 导入并运行HTTP服务器
        import http_server

        # 创建服务器实例
        server = http_server.MCPHTTPServer(host=host, port=port)

        # 设置日志级别
        server_logger = logging.getLogger("gdb-mcp-http-server")
        server_logger.setLevel(logging.INFO)

        logger.info("HTTP服务器启动成功")
        logger.info(f"访问 http://{host}:{port}/health 检查服务器状态")
        logger.info(f"访问 http://{host}:{port}/mcp/info 获取MCP服务器信息")

        # 启动服务器
        server.run()

    except ImportError as e:
        logger.error(f"导入HTTP服务器失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("HTTP服务器已终止")
    except Exception as e:
        logger.error(f"HTTP服务器错误: {str(e)}")
        logger.error(traceback.format_exc())
        sys.exit(1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="GDB MCP服务器启动器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s                          # 默认stdio模式
  %(prog)s --mode stdio             # stdio模式
  %(prog)s --mode http              # HTTP模式，默认端口8080
  %(prog)s --mode http --port 9000  # HTTP模式，端口9000
  %(prog)s --mode http --host localhost  # 只监听localhost
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="通信模式 (默认: stdio)",
    )

    parser.add_argument(
        "--host", default="0.0.0.0", help="HTTP服务器监听地址 (默认: 0.0.0.0)"
    )

    parser.add_argument(
        "--port", type=int, default=8080, help="HTTP服务器监听端口 (默认: 8080)"
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别 (默认: INFO)",
    )

    args = parser.parse_args()

    # 设置全局日志级别
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # 显示启动信息
    logger.info("=" * 60)
    logger.info("GDB MCP服务器启动器")
    logger.info("=" * 60)
    logger.info(f"运行模式: {args.mode}")

    if args.mode == "http":
        logger.info(f"监听地址: {args.host}:{args.port}")
        logger.info(f"日志级别: {args.log_level}")
        logger.info("")
        logger.info("HTTP服务器端点:")
        logger.info(f"  健康检查: http://{args.host}:{args.port}/health")
        logger.info(f"  MCP信息: http://{args.host}:{args.port}/mcp/info")
        logger.info(f"  工具列表: http://{args.host}:{args.port}/mcp/tools/list")
        logger.info(f"  创建会话: POST http://{args.host}:{args.port}/mcp/session")
        logger.info(
            f"  流式连接: GET http://{args.host}:{args.port}/mcp/session/<id>/stream"
        )
        logger.info(f"  工具调用: POST http://{args.host}:{args.port}/mcp/call")
    else:
        logger.info(f"日志级别: {args.log_level}")
        logger.info("")
        logger.info("stdio模式将通过标准输入输出进行MCP通信")

    logger.info("=" * 60)

    # 根据模式启动对应的服务器
    if args.mode == "stdio":
        run_stdio_server()
    else:
        run_http_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
