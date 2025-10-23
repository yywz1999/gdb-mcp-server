# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a GDB MCP (Model Context Protocol) Server that enables AI-assisted debugging by providing a standardized interface for interacting with GDB (GNU Debugger) through the MCP protocol. The server allows AI agents and other tools to perform debugging operations programmatically.

## Development Commands

### Installation and Setup
```bash
# Install dependencies
python3 -m pip install -r requirements.txt

# Alternative installation using pyproject.toml
pip install -e .
```

### Running the Server
```bash
# Start the MCP server
python3 mcp_server.py
```

### Development Tools
```bash
# Code formatting (if dev dependencies installed)
black .

# Import sorting
isort .

# Type checking
mypy .
```

## Architecture

### Core Components

1. **mcp_server.py** - Main MCP server entry point using FastMCP library
2. **gdb_tools.py** - All MCP tool functions that interface with GDB
3. **comm_methods/** - Communication strategies for different platforms:
   - `gdb_communicator.py` - Unified communication interface
   - `pexpect_comm.py` - Direct GDB process communication (Linux优先)
   - `applescript_comm.py` - iTerm2 communication via AppleScript (macOS)
   - `keyboard_comm.py` - Keyboard simulation fallback method

### Communication Strategy

The server uses a multi-platform communication approach:
- **macOS**: AppleScript with iTerm2 (preferred) for seamless integration
- **Linux**: pexpect for direct process communication
- **Windows**: Keyboard simulation as fallback
- **Fallback**: Keyboard simulation available on all platforms

### Key Features

- **Process Discovery**: Automatically finds running GDB processes using `ps` command
- **Smart Blocking Handling**: Detects and handles blocking commands (like remote connections) with automatic interrupt signals
- **Output Capture**: Uses unique markers to identify command output ranges and intelligently removes GDB prompts
- **Multi-architecture Support**: Handles cross-platform and remote debugging scenarios

## MCP Tools Architecture

### System Tools
- `sys_find_gdb_processes` - Discover running GDB processes
- `sys_attach_to_gdb` - Attach to existing GDB process by PID or TTY
- `sys_start_gdb_with_remote` - Start new GDB instance with remote connection

### GDB Debugging Tools
- `gdb_execute_command` - Execute arbitrary GDB commands
- `gdb_set_breakpoint`/`gdb_delete_breakpoint` - Breakpoint management
- `gdb_step`/`gdb_next`/`gdb_finish`/`gdb_continue` - Execution control
- `gdb_get_registers`/`gdb_examine_memory`/`gdb_get_stack`/`gdb_get_locals` - State inspection
- `gdb_disassemble` - Code disassembly
- `gdb_connect_remote` - Remote debugging connections

## Platform-Specific Notes

### macOS (Development Environment)
- Requires iTerm2 for optimal AppleScript integration
- Uses window content detection to find GDB sessions
- Direct command writing without window focus switching
- Ensure GDB terminal is open before starting server

### Linux
- Uses pexpect for direct process communication
- Requires proper TTY device permissions
- Generally more reliable than terminal automation approaches

## Testing and Validation

The project has been tested on:
- macOS (Intel architecture) with Python 3.11 and iTerm2
- Supports cross-platform debugging scenarios

## Important Implementation Details

- All GDB PID parameters are converted to strings for consistency
- The server includes intelligent timeout mechanisms for blocking operations
- Command output is processed to remove GDB prompts and command echoes
- The FastMCP library provides the MCP protocol implementation
- Global communicator instance ensures persistent GDB connections across tool calls