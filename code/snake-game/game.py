"""
game.py — 游戏状态管理

管理游戏循环、输入处理、帧率控制、暂停/重启。
"""

import os
import sys
import time
from snake import Board, DIRECTION_MAP, ARROW_MAP, UP, DOWN, LEFT, RIGHT
from renderer import (
    clear_screen, hide_cursor, show_cursor, render, render_game_over,
)


class Game:
    """游戏主控制器"""

    def __init__(self, width=20, height=20):
        self.board = Board(width, height)
        self.paused = False
        self.running = True
        self.base_delay = 0.15  # 初始间隔（秒）
        self.min_delay = 0.05   # 最快间隔
        self.speed_up_every = 5  # 每吃 N 个加速
        self.speed_factor = 0.85  # 加速倍率
        self._delay = self.base_delay

    def _get_input(self):
        """获取键盘输入（非阻塞）
        返回：按键字符，或 None
        """
        if os.name == 'nt':
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                # 方向键（两个字节）
                if ch == b'\xe0':
                    ch2 = msvcrt.getch()
                    return '\x1b[A'  # 用转义序列表示方向键
                try:
                    return ch.decode('utf-8', errors='replace')
                except Exception:
                    return None
            return None
        else:
            import termios
            import tty
            import select
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                    ch = sys.stdin.read(1)
                    if ch == '\x1b':
                        # 可能为方向键 \x1b[A
                        if select.select([sys.stdin], [], [], 0.05) == ([sys.stdin], [], []):
                            seq = ch + sys.stdin.read(2)
                            return seq
                    return ch
                return None
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _parse_input(self, raw):
        """解析原始输入为方向或命令"""
        if raw is None:
            return None

        # 方向键转义序列
        if raw == '\x1b[A' or raw == '\x1bOA':
            return UP
        elif raw == '\x1b[B' or raw == '\x1bOB':
            return DOWN
        elif raw == '\x1b[D' or raw == '\x1bOD':
            return LEFT
        elif raw == '\x1b[C' or raw == '\x1bOC':
            return RIGHT

        # WASD
        if raw in DIRECTION_MAP:
            return DIRECTION_MAP[raw]

        # 命令键
        return raw

    def _update_speed(self):
        """根据分数更新游戏速度"""
        speed_steps = self.board.score // self.speed_up_every
        self._delay = max(
            self.min_delay,
            self.base_delay * (self.speed_factor ** speed_steps)
        )

    def _handle_key(self, key):
        """处理按键输入"""
        if key in (UP, DOWN, LEFT, RIGHT):
            self.board.set_direction(key)
        elif isinstance(key, str):
            k = key.lower()
            if k == 'p':
                self.paused = not self.paused
            elif k == 'r':
                self.board.restart()
                self.board._place_food()
                self._delay = self.base_delay
                self.paused = False
            elif k == 'q':
                self.running = False

    def run(self):
        """主游戏循环"""
        hide_cursor()
        self.board.restart()
        self.board._place_food()
        self._delay = self.base_delay

        try:
            while self.running:
                # 1. 处理输入
                raw = self._get_input()
                if raw is not None:
                    key = self._parse_input(raw)
                    self._handle_key(key)

                if not self.running:
                    break

                # 2. 更新游戏状态
                if not self.paused and not self.board.game_over:
                    result = self.board.tick()
                    if result == 'eat':
                        self._update_speed()
                        # 更新高分
                        if self.board.score > self.board.high_score:
                            self.board.high_score = self.board.score
                    elif result in ('crash', 'game_over', 'win'):
                        if self.board.score > self.board.high_score:
                            self.board.high_score = self.board.score

                # 3. 渲染
                clear_screen()
                render(self.board, self.paused)

                # 4. 等待
                time.sleep(self._delay)

        finally:
            show_cursor()
            clear_screen()


def run_game(width=20, height=20):
    """运行游戏的便捷入口"""
    game = Game(width, height)
    game.run()
