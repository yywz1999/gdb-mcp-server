# GDB MCP 服务器

> **注意**：本项目目前处于开发阶段，这个仓库是阶段性成果的测试demo。我们非常欢迎社区成员提出建议和反馈，帮助我们改进这个工具。如果您有任何想法或发现任何问题，请不要犹豫，提交issue或pull request。

一个支持人工智能辅助调试的 GDB MCP (Model Context Protocol) 服务器。该服务器允许 AI 代理和其他工具通过 MCP 协议与 GDB 进行交互。

## 特性

- 发现并附加到现有的 GDB 进程
- 通过终端窗口与 GDB 通信（macOS 上的 iTerm2/Terminal.app）
- 支持 MCP 协议，便于与 AI 助手集成
- 支持多架构、多主机和远程调试场景，可通过单个接口处理复杂的调试环境
- 通过简单的函数调用执行常见的 GDB 调试操作：
  - 设置和删除断点
  - 单步执行代码
  - 检查内存
  - 查看寄存器和堆栈跟踪
  - 反汇编代码
  - 获取局部变量

## 演示视频

项目包含一个演示视频 [附加调试演示.mp4](./附加调试演示.mp4)，展示了如何使用 GDB MCP 服务器进行附加调试的完整工作流程。该视频展示了在实际环境中进行跨架构调试的场景，包括：



https://github.com/user-attachments/assets/dbb5c2dc-1bc9-4a19-86d7-c967725bc145



通过观看此视频，您可以更直观地了解 GDB MCP 服务器如何简化多架构和远程调试场景。

## 技术实现原理

### 1. MCP 协议实现

本项目使用了 [FastMCP](https://github.com/jlowin/fastmcp) 库实现 Model Context Protocol，以提供标准化的 AI 工具接口。FastMCP 是一个轻量级的 Python 库，专为 AI 助手和工具交互设计，提供以下优势：

- 符合 MCP 规范的工具注册与调用
- 简化的 API 设计，方便工具函数定义
- 与 Cursor AI 的无缝集成
- 支持多种传输方式（标准输入/输出、HTTP等）

在代码中，我们通过以下方式使用 FastMCP：

```python
from fastmcp import FastMCP

# 创建 MCP 服务实例
mcp = FastMCP("GDB", log_level="INFO")

# 注册工具函数
@mcp.tool(name="mcp__find_gdb_processes")
def find_gdb_processes():
    # 工具函数实现
    ...

# 启动服务器
mcp.run()
```

### 2. GDB 控制机制

本项目通过多种方式控制 GDB 调试器，确保可以在不同环境中可靠地工作：

#### 2.1 进程发现

使用 `ps` 命令和正则表达式匹配来查找系统中运行的 GDB 进程：

```python
def find_gdb_processes(self):
    cmd = ["ps", "-eo", "pid,tty,command"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    output, _ = process.communicate()
    
    processes = []
    for line in output.decode('utf-8').split('\n'):
        if 'gdb' in line:
            # 解析进程信息，提取 PID、TTY 和命令
            ...
            processes.append({"pid": pid, "tty": tty, "cmd": cmd})
    
    return processes
```

#### 2.2 终端通信

在 macOS 上，使用 AppleScript 与 iTerm2 或 Terminal.app 通信，实现 GDB 命令的发送和输出的捕获：

```python
def execute_command(self, command, gdb_pid=None):
    # 构建 AppleScript
    script = """
    tell application "iTerm2"
        # 查找包含 GDB 的终端会话
        # 发送命令和特殊标记
        # 捕获命令输出
        ...
    end tell
    """
    
    # 执行 AppleScript
    result = subprocess.check_output(['osascript', '-e', script])
    
    # 解析结果
    # ...
    
    return output
```

为确保可靠性，我们实现了多层捕获机制：

1. **标记识别**：在命令执行前后发送特殊标记，以准确定位输出的起始和结束位置
2. **多终端支持**：优先使用 iTerm2，如果失败则尝试 Terminal.app
3. **键盘事件回退**：如果脚本方法失败，使用系统事件模拟键盘输入

#### 2.3 多平台支持

在 Linux 上，通过 TTY 设备文件直接写入命令：

```python
def execute_command_linux(self, command, tty_device):
    with open(tty_device, 'w') as tty:
        tty.write(command + '\n')
    # 通过其他方式捕获输出
    ...
```

### 3. 工具函数实现

核心功能通过一系列工具函数实现，每个函数都通过 MCP 协议暴露：

```python
@mcp.tool(name="mcp__execute_command")
def execute_command(command, gdb_pid=None):
    """执行GDB命令"""
    success, output = gdb_controller.execute_command(command, gdb_pid)
    
    # 格式化和处理输出
    ...
    
    return {
        "success": success, 
        "output": output, 
        "formatted_result": result_message,
        "command_type": cmd_type
    }
```

类似的工具函数包括：`set_breakpoint`、`get_registers`、`get_stack`、`disassemble` 等。

### 4. 多架构和远程调试支持

GDB MCP 服务器的一个显著优势是能够处理复杂的调试场景，包括：

- **跨架构调试**：同时支持 x86_64、ARM64、MIPS 等多种架构的程序调试
- **远程主机调试**：通过 GDB 的远程调试功能连接到远程目标机器
- **混合环境调试**：在同一界面中切换不同的调试目标和架构


通过抽象底层的 GDB 命令交互，GDB MCP 服务器提供了统一的接口，使开发人员能够专注于调试逻辑而非环境差异。例如，同一个 `get_registers` 调用可以适应不同的架构，自动解析寄存器输出：

```python
# 同一接口，不同架构自动适配
client.get_registers()  # 在 x86_64 上
client.get_registers()  # 在 ARM64 上
```

## 安装

1. 克隆仓库：
   ```bash
   git clone https://github.com/yywz1999/gdb-mcp-server.git
   cd gdb-mcp-server
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 使用方法

1. 启动服务器：
   ```bash
   ./run_mcp.sh
   ```
   或者
   ```bash
   python3 mcp_server.py
   ```

2. 使用 MCP 协议通过服务器与 GDB 交互。服务器提供以下方法：
   - `find_gdb_processes` - 查找所有运行的 GDB 进程
   - `attach_to_gdb` - 附加到 GDB 进程
   - `execute_command` - 执行 GDB 命令
   - `set_breakpoint` - 设置断点
   - `delete_breakpoint` - 删除断点
   - `step` - 单步执行
   - `continue_execution` - 继续执行
   - `get_registers` - 获取寄存器值
   - `examine_memory` - 检查内存
   - `get_stack` - 获取堆栈跟踪
   - `get_locals` - 获取局部变量
   - `disassemble` - 反汇编代码

## 示例

`examples` 目录包含示例代码和演示脚本，帮助您快速上手：

- `test_program.c` - 一个带有多个函数的简单C程序，用于调试演示
- `debug_demo.py` - 一个使用GDB MCP客户端进行调试的演示程序

有关使用示例的详细说明，请参阅[示例说明文档](examples/README.md)。

## 复杂调试场景

GDB MCP 服务器特别适合处理复杂的调试场景，例如：

1. **嵌入式系统调试**：通过远程 GDB 服务器连接到嵌入式设备，并使用相同的接口进行调试
2. **多进程应用调试**：同时附加到多个相关进程，协调调试复杂的分布式应用
3. **内核和用户空间混合调试**：在同一会话中调试内核和用户空间程序
4. **跨平台调试**：使用相同的客户端代码调试不同平台上的程序


## 调试指南

有关使用GDB MCP进行调试的全面指南，包括最佳实践和故障排除，请参阅[调试指南](DEBUGGING_GUIDE.md)。

## Cursor 集成

该服务器可以与 Cursor AI 集成，提供 AI 辅助调试功能。主要实现方式是：

1. 通过 MCP 协议将 GDB 功能暴露给 Cursor
2. 使用 Cursor 插件系统注册 GDB 工具
3. 在 Cursor 的聊天界面中调用 GDB 命令

## API参考

### MCP协议

支持以下MCP方法：

- `attach_to_gdb` - 附加到GDB进程
- `execute_command` - 执行GDB命令
- `set_breakpoint` - 设置断点
- `delete_breakpoint` - 删除断点
- `step` - 单步执行
- `continue_execution` - 继续执行
- `get_registers` - 获取寄存器值
- `examine_memory` - 检查内存
- `get_stack` - 获取堆栈信息
- `get_locals` - 获取局部变量
- `disassemble` - 反汇编代码

## 配置与性能优化

### 标记识别机制

为了准确捕获命令输出，我们使用了唯一的时间戳标记：

```python
time_id = int(time.time())
output_marker = f"<<<GDB_OUTPUT_START_{time_id}>>>"
end_marker = f"<<<GDB_OUTPUT_END_{time_id}>>>"
```

这些标记发送到终端，然后从捕获的文本中提取出标记之间的内容。

### 超时控制

为避免在命令执行时无限等待，我们实现了超时机制：

```python
try:
    result = subprocess.check_output(['osascript', '-e', script], timeout=10)
except subprocess.TimeoutExpired:
    # 处理超时情况
```

### 延迟优化

在命令执行后添加适当的延迟，确保输出完全生成：

```python
# 发送命令
write text "{command}"
# 等待响应
delay 1.0
```

## 平台支持

- macOS：完整支持，包括iTerm2和Terminal.app集成
- Linux：基本支持，需要安装xdotool
- Windows：暂不支持

## 许可证

MIT License
