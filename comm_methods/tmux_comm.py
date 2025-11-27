#!/usr/bin/env python3
"""Tmux通信方法 - 通过tmux终端直接与GDB通信"""

import logging
import re
import subprocess
import time
from typing import Tuple

logger = logging.getLogger("gdb-mcp-server.tmux_comm")


class TmuxCommunicator:
    """使用tmux终端与GDB通信的类"""

    def __init__(self):
        self.tmux_session_name = None
        self.last_command_time = 0.0
        self.is_blocked = False
        self._gdb_pattern = re.compile(r"\bgdb(?:-multiarch)?\b", re.IGNORECASE)
        logger.info("Tmux通信器初始化")
        self._check_dependencies()

    def _check_dependencies(self):
        """检查tmux是否可用"""
        try:
            subprocess.check_call(
                ["which", "tmux"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            logger.info("找到tmux工具")
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning("未找到tmux，请安装: sudo apt-get install tmux")

    def find_gdb_window(self):
        """查找包含GDB的tmux窗口"""
        try:
            cmd = [
                "tmux",
                "list-panes",
                "-a",
                "-F",
                "#{session_name}  ->  #{pane_current_command}",
            ]
            output = subprocess.check_output(cmd, text=True).strip()
            if not output:
                return False

            for line in output.splitlines():
                if "->" not in line:
                    continue
                session_part, command_part = line.split("->", 1)
                session_name = session_part.strip()
                command = command_part.strip()
                if not session_name or not command:
                    continue

                command_lower = command.lower()
                if "gdbserver" in command_lower:
                    continue

                if self._gdb_pattern.search(command):
                    self.tmux_session_name = session_name
                    return True
            return False
        except Exception as exc:
            logger.error(f"查找GDB窗口失败: {exc}")
            return False

    def start_gdb(self, executable):
        """启动或附加到 tmux 中的 gdb 会话"""
        cmd = ["tmux", "has-session", "-t", "gdb_session"]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            logger.info("发现 tmux 会话")
            if not self.find_gdb_window():
                command = f"gdb -q {executable}"
                start_cmd = ["tmux", "send-keys", "-t", "gdb_session", command, "Enter"]
                cmd_result = subprocess.run(start_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if cmd_result.returncode == 0:
                    self.tmux_session_name = "gdb_session"
                    return True, f"启动gdb调试{executable}成功"
                return False, f"启动gdb调试{executable}失败"
            return True, "已经存在运行中的gdb，请直接附加"

        logger.info("未发现 tmux 会话，尝试在新的终端中启动")
        tmux_result = subprocess.run(
            ["gnome-terminal", "--", "tmux", "new-session", "-A", "-s", "gdb_session"],
            capture_output=True,
            text=True,
        )
        if tmux_result.returncode != 0:
            return False, f"启动gdb调试{executable}失败"

        command = f"gdb -q {executable}"
        start_cmd = ["tmux", "send-keys", "-t", "gdb_session", command, "Enter"]
        cmd_result = subprocess.run(start_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if cmd_result.returncode == 0:
            self.tmux_session_name = "gdb_session"
            return True, f"启动gdb调试{executable}成功"
        return False, f"启动gdb调试{executable}失败"

    def check_gdb_blocked(self):
        """报告GDB是否阻塞"""
        if not self.is_blocked:
            return {"is_blocked": False, "running_time": 0, "status": "GDB处于交互状态"}
        running_time = time.time() - self.last_command_time
        return {
            "is_blocked": True,
            "running_time": running_time,
            "status": f"GDB运行中，已运行 {running_time:.1f} 秒",
        }

    def _require_session(self):
        if self.tmux_session_name:
            return True
        if self.find_gdb_window():
            return True
        return False

    def execute_command(self, command) -> Tuple[bool, str]:
        """使用tmux方式执行GDB命令"""
        try:
            if not self._require_session():
                return False, "未找到GDB的tmux会话，请先启动或附加"

            target = self.tmux_session_name
            time_id = int(time.time())
            output_marker = f"<<<GDB_OUTPUT_START_{time_id}>>>"
            end_marker = f"<<<GDB_OUTPUT_END_{time_id}>>>"
            might_block = command.strip() in {"c", "continue", "run", "r"} or "target remote" in command

            cmds = [
                ["tmux", "send-keys", "-t", target, f"echo {output_marker}", "Enter"],
                ["tmux", "send-keys", "-t", target, command, "Enter"],
            ]
            for tmux_cmd in cmds:
                subprocess.check_output(tmux_cmd, text=True, timeout=3)

            max_attempts = 3 if might_block else 1
            got_response = False
            content = ""

            capture_cmd = ["tmux", "capture-pane", "-p", "-t", target, "-S", "-", "-E", "-"]

            for attempt in range(max_attempts):
                time.sleep(1)
                pane_text = subprocess.check_output(capture_cmd, text=True, timeout=3).strip()

                if output_marker not in pane_text:
                    test_cmd = ["tmux", "send-keys", "-t", target, f"echo GDB_TEST_{attempt}", "Enter"]
                    subprocess.check_output(test_cmd, text=True, timeout=3)
                    time.sleep(0.2)
                    pane_text = subprocess.check_output(capture_cmd, text=True, timeout=3).strip()

                if output_marker in pane_text:
                    if end_marker not in pane_text:
                        end_cmd = ["tmux", "send-keys", "-t", target, f"echo {end_marker}", "Enter"]
                        subprocess.check_output(end_cmd, text=True, timeout=3)
                        time.sleep(0.2)
                        pane_text = subprocess.check_output(capture_cmd, text=True, timeout=3).strip()

                    if end_marker in pane_text:
                        content = pane_text
                        got_response = True
                        break

                logger.warning("检测到可能的阻塞 (%s/%s)", attempt + 1, max_attempts)
                content = pane_text

            if not got_response and might_block:
                interrupt_cmds = [
                    ["tmux", "send-keys", "-t", target, "C-c"],
                    ["tmux", "send-keys", "-t", target, "echo <<<GDB_INTERRUPTED>>>", "Enter"],
                ]
                for cmd in interrupt_cmds:
                    subprocess.check_output(cmd, text=True, timeout=3)
                self.is_blocked = True
                self.last_command_time = time.time()
                return True, "命令执行阻塞，已发送中断信号。"

            if not got_response:
                return False, "执行命令时未获得终端响应，可能出现异常。"

            self.is_blocked = False

            if output_marker in content and end_marker in content:
                data = content.split(output_marker, 1)[1]
                output_value = data.split(end_marker, 1)[0]
                cleaned = output_value.replace(command, "", 1).strip()
                return True, cleaned

            return True, ""

        except Exception as exc:
            logger.error(f"执行命令失败: {exc}")
            return False, f"执行命令失败: {exc}"

