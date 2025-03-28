# GDB MCP 调试指南

本指南详细介绍如何使用GDB MCP服务器进行调试，包括常见问题的解决方法和最佳实践。

## 目录
1. [基本调试流程](#基本调试流程)
2. [常用GDB命令](#常用GDB命令)
3. [与AI助手集成](#与AI助手集成)
4. [故障排除](#故障排除)
5. [高级使用技巧](#高级使用技巧)

## 基本调试流程

### 1. 启动服务器

首先，启动GDB MCP服务器：

```bash
./run_mcp.sh
```

或

```bash
python3 mcp_server.py
```

### 2. 查找GDB进程

如果您已经有GDB进程在运行，可以使用以下方法查找它们：

```python
from gdb_client import GdbClient

client = GdbClient()
processes = client.find_gdb_processes()
print(processes)
```

### 3. 附加到GDB进程

选择一个GDB进程进行附加：

```python
success, message = client.attach_to_gdb(gdb_pid="12345")  # 替换为实际的GDB进程ID
print(message)
```

### 4. 设置断点

在关键代码位置设置断点：

```python
success, output = client.set_breakpoint("main")  # 在main函数处设置断点
print(output)
```

### 5. 执行程序

开始或继续执行程序：

```python
success, output = client.execute_command("run")  # 运行程序
print(output)

# 或继续执行
success, output = client.continue_execution()
print(output)
```

### 6. 检查状态

检查程序状态，包括寄存器、堆栈和变量：

```python
# 获取寄存器值
success, output = client.get_registers()
print(output)

# 获取堆栈跟踪
success, output = client.get_stack()
print(output)

# 获取局部变量
success, output = client.get_locals()
print(output)
```

## 常用GDB命令

以下是一些常用GDB命令，可以通过`execute_command`方法执行：

- `break <location>` - 设置断点
- `delete <number>` - 删除断点
- `step` - 单步执行，进入函数
- `next` - 单步执行，不进入函数
- `continue` - 继续执行
- `info registers` - 显示寄存器信息
- `info locals` - 显示局部变量
- `bt` - 显示堆栈跟踪
- `x/<count><format> <address>` - 检查内存
- `disassemble <function>` - 反汇编函数

示例：

```python
success, output = client.execute_command("info breakpoints")  # 列出所有断点
print(output)
```

## 与AI助手集成

GDB MCP服务器设计为可与AI助手集成，特别是Cursor AI。以下是一些集成建议：

1. 在调试会话开始时，让AI助手了解正在调试的程序和目标。
2. 使用AI助手分析堆栈跟踪和寄存器状态，寻找异常。
3. 让AI助手提供下一步调试的建议。

示例交互：

```
用户: "在main函数第10行设置断点"
AI: [设置断点并确认]

用户: "运行程序并在断点停下后检查寄存器状态"
AI: [运行程序，显示寄存器状态，并分析]
```

## 故障排除

### 服务器不响应

如果服务器不响应，尝试以下步骤：

1. 检查服务器进程是否仍在运行：
   ```bash
   ps aux | grep mcp_server.py
   ```

2. 如果服务器进程已死亡，重新启动：
   ```bash
   ./run_mcp.sh
   ```

3. 如果问题持续，检查日志（如果有）：
   ```bash
   tail -f mcp_server.log
   ```

### 无法附加到GDB进程

如果无法附加到GDB进程，确保：

1. GDB确实在运行，并且可以被当前用户访问。
2. 使用正确的GDB进程ID。
3. 在macOS上，终端有正确的权限。

### 断点设置失败

断点设置失败可能有多种原因：

1. 函数名或行号不存在。
2. 程序没有调试信息（编译时需要使用`-g`标志）。
3. 程序尚未加载。

## 高级使用技巧

### 自定义GDB命令

您可以执行自定义GDB命令：

```python
success, output = client.execute_command("define my_cmd\necho Hello, custom command!\\n\nend")
print(output)

# 然后使用自定义命令
success, output = client.execute_command("my_cmd")
print(output)
```

### 条件断点

设置条件断点：

```python
success, output = client.execute_command("break main if argc > 1")
print(output)
```

### 使用Python脚本自动化调试

您可以创建Python脚本来自动化常见的调试工作流：

```python
def analyze_memory_leak(client, suspect_function):
    """分析内存泄漏"""
    # 设置断点
    client.set_breakpoint(f"{suspect_function}")
    # 运行直到断点
    client.execute_command("run")
    # 记录内存使用
    before = client.execute_command("info proc mappings")
    # 继续执行
    client.continue_execution()
    # 再次检查内存
    after = client.execute_command("info proc mappings")
    # 比较并分析结果
    return compare_memory_usage(before, after)
```

希望这个调试指南对你有所帮助！如有任何问题，请随时提问。 