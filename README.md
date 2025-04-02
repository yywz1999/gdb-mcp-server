# GDB MCP 服务器

一个支持人工智能辅助调试的 GDB MCP (Model Context Protocol) 服务器。该服务器允许 AI 代理和其他工具通过 MCP 协议与 GDB 进行交互。

> **注意**：本项目目前处于开发阶段。我们欢迎社区成员提出建议和反馈，帮助我们改进这个工具。

项目地址：https://github.com/yywz1999/gdb-mcp-server

## 特性

- 发现并附加到现有的 GDB 进程
- 通过终端窗口与 GDB 通信（macOS 上优化支持 iTerm2）
- 支持 MCP 协议，便于与 AI 助手集成
- 智能处理 GDB 命令阻塞，自动发送中断信号
- 支持多架构、多主机和远程调试场景
- 通过简单的函数调用执行常见的 GDB 调试操作：
  - 设置和删除断点
  - 单步执行代码
  - 检查内存
  - 查看寄存器和堆栈跟踪
  - 反汇编代码
  - 获取局部变量

## 演示视频

项目包含一个演示视频，展示了如何使用 GDB MCP 服务器进行附加调试的完整工作流程：

https://github.com/user-attachments/assets/dbb5c2dc-1bc9-4a19-86d7-c967725bc145

通过观看此视频，您可以更直观地了解 GDB MCP 服务器如何简化多架构和远程调试场景。

## 使用说明（以Cursor为例）

1. 下载项目并验证：
``` shell
git clone https://github.com/yywz1999/gdb-mcp-server.git
cd gdb-mcp-server
python3 -m pip install -r requirements.txt
python3 ~/MCP_server/gdb-mcp-server/mcp_server.py
```
结果如下图所示，即为环境正常
<img width="1440" alt="image" src="https://github.com/user-attachments/assets/03437c53-2f93-414c-b5bf-0405b5bbe8f9" />

2. 配置Cursor：
<img width="553" alt="image" src="https://github.com/user-attachments/assets/e697d13f-27bf-410d-9cfe-05256e513dd2" />



## 最新改进

### 1. 增强的 iTerm2 支持
- 优化了 iTerm2 会话查找和交互机制
- 使用直接命令写入方式，无需切换窗口焦点
- 支持基于会话内容识别 GDB 会话

### 2. 智能阻塞处理
- 自动检测可能导致阻塞的命令（如远程连接、继续执行等）
- 使用超时机制识别阻塞状态
- 在检测到阻塞时自动发送中断信号
- 提取并返回部分执行结果

### 3. 更可靠的输出捕获
- 使用唯一标记标识命令输出范围
- 智能移除 GDB 提示符和命令回显
- 多尝试机制确保命令响应可靠性

## 技术实现简介

GDB MCP 服务器使用以下技术实现 GDB 的控制和通信：

1. **MCP 协议实现**：使用 [FastMCP](https://github.com/jlowin/fastmcp) 库提供符合 Model Context Protocol 规范的工具接口

2. **多种通信策略**：
   - **AppleScript**：在 macOS 上与 iTerm2 通信（推荐）
   - **pexpect**：直接与 GDB 进程通信（Linux 优先）
   - **键盘模拟**：作为最后的回退方案

3. **进程发现**：自动查找系统中运行的 GDB 进程，无需用户手动指定进程 ID

## 测试环境

- 操作系统：macOS（Intel架构）
- Python版本：Python 3.11
- 终端：iTerm2

## 安装

1. 克隆仓库：
   ```bash
   git clone https://github.com/yywz1999/gdb-mcp-server.git
   cd gdb-mcp-server
   ```

2. 安装依赖：
   ```bash
   python3 -m pip install -r requirements.txt
   ```

## 使用方法

1. 启动服务器：
   ```bash
   python3 mcp_server.py
   ```

2. 使用 MCP 协议通过服务器与 GDB 交互。服务器提供以下工具函数：

   ### 系统工具
   - `sys_find_gdb_processes` - 查找所有运行的 GDB 进程
   - `sys_attach_to_gdb` - 附加到 GDB 进程
   - `sys_start_gdb_with_remote` - 启动 GDB 并连接到远程目标

   ### GDB 调试工具
   - `gdb_execute_command` - 执行任意 GDB 命令
   - `gdb_set_breakpoint` - 设置断点
   - `gdb_delete_breakpoint` - 删除断点
   - `gdb_step` - 单步执行
   - `gdb_next` - 执行到下一行
   - `gdb_finish` - 执行到函数返回
   - `gdb_continue` - 继续执行
   - `gdb_get_registers` - 获取寄存器值
   - `gdb_examine_memory` - 检查内存
   - `gdb_get_stack` - 获取堆栈跟踪
   - `gdb_get_locals` - 获取局部变量
   - `gdb_disassemble` - 反汇编代码
   - `gdb_connect_remote` - 连接到远程调试目标

## macOS 上的最佳实践

在 macOS 上使用 GDB MCP 服务器时，建议：

1. 使用 iTerm2 作为终端模拟器（提供最佳支持）
2. 确保 GDB 终端窗口在启动服务器前已打开
3. 对于远程调试，建议先手动在 GDB 中设置相关配置，然后通过 MCP 服务器附加

## 故障排除

### macOS 上的常见问题

1. **窗口激活问题**：如果 GDB 窗口无法正确激活，尝试手动将其置于前台
2. **输入法状态**：确保 GDB 终端未处于中文或其他输入法状态
3. **命令阻塞**：对于阻塞的命令（如 target remote），服务器会自动发送中断信号

### Linux 上的常见问题

1. **TTY 权限**：确保当前用户有权限访问 GDB 进程的 TTY 设备
2. **pexpect 依赖**：确保已安装 pexpect 库

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件
