#!/usr/bin/env python3
"""
demo.py — 贪吃蛇演示 + 自动回放

AI 控制的蛇自动寻路（简单贪心算法），展示游戏效果。
按 Q 退出演示。
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from snake import Board, UP, DOWN, LEFT, RIGHT, OPPOSITE
from renderer import (
    clear_screen, hide_cursor, show_cursor, render_demo,
)


class Demo:
    """自动演示模式"""

    def __init__(self, width=20, height=20):
        self.board = Board(width, height)
        self.delay = 0.12
        self.running = True
        self.total_moves = 0
        self.max_moves = 5000  # 防止无限循环

    def _get_input(self):
        """检查键盘输入（非阻塞）"""
        if os.name == 'nt':
            import msvcrt
            if msvcrt.kbhit():
                ch = msvcrt.getch()
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
                    return sys.stdin.read(1)
                return None
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _choose_direction(self):
        """简单贪心算法选择方向：朝食物方向走，避免碰撞"""
        head = self.board.snake[0]
        food = self.board.food
        if food is None:
            return self.board.direction

        # 计算到食物的方向
        dx = food[0] - head[0]
        dy = food[1] - head[1]

        # 蛇身集合（不含蛇尾，因为蛇尾即将移除）
        snake_set = set(self.board.snake)

        # 优先方向：先水平再垂直 或 先垂直再水平（交替以避免陷阱）
        move_priority = []
        if abs(dx) >= abs(dy):
            if dx > 0:
                move_priority.append(RIGHT)
            elif dx < 0:
                move_priority.append(LEFT)
            if dy > 0:
                move_priority.append(DOWN)
            elif dy < 0:
                move_priority.append(UP)
        else:
            if dy > 0:
                move_priority.append(DOWN)
            elif dy < 0:
                move_priority.append(UP)
            if dx > 0:
                move_priority.append(RIGHT)
            elif dx < 0:
                move_priority.append(LEFT)

        # 备选：所有可行方向（排除掉头和180°反向）
        candidates = [UP, DOWN, LEFT, RIGHT]
        opposite = OPPOSITE.get(self.board.direction)
        random.shuffle(candidates)

        # 先试优先方向
        for d in move_priority:
            if d == opposite:
                continue
            nx, ny = head[0] + d[0], head[1] + d[1]
            if (nx <= 0 or nx >= self.board.width - 1 or
                    ny <= 0 or ny >= self.board.height - 1):
                continue
            if (nx, ny) not in snake_set:
                return d

        # 再试所有方向
        for d in candidates:
            if d == opposite:
                continue
            nx, ny = head[0] + d[0], head[1] + d[1]
            if (nx <= 0 or nx >= self.board.width - 1 or
                    ny <= 0 or ny >= self.board.height - 1):
                continue
            if (nx, ny) not in snake_set:
                return d

        # 无路可走
        return self.board.direction

    def run(self):
        """运行演示"""
        hide_cursor()
        self.board.restart()
        self.board._place_food()

        # 用恒定方向初始化
        self.board.direction = RIGHT
        self.board.next_direction = RIGHT

        try:
            while self.running:
                # 检查退出
                key = self._get_input()
                if key and key.lower() == 'q':
                    break

                # AI 选择方向
                direction = self._choose_direction()
                self.board.set_direction(direction)

                # 推进
                result = self.board.tick()
                self.total_moves += 1

                if result in ('crash', 'game_over', 'win'):
                    break

                # 渲染
                clear_screen()
                speed = 1.0 / self.delay if self.delay > 0 else 999
                render_demo(self.board, speed, self.total_moves)

                time.sleep(self.delay)

                if self.total_moves >= self.max_moves:
                    break

            # 显示结果
            clear_screen()
            if self.board.won:
                print(f'\n  🎉 演示完成！蛇填满了整个地图！得分: {self.board.score}')
            elif self.board.game_over:
                print(f'\n  💀 演示结束 - 蛇撞了。得分: {self.board.score}')
            else:
                print(f'\n  👋 演示结束。得分: {self.board.score}')
            print(f'  总步数: {self.total_moves}')

        finally:
            show_cursor()


def run_demo(width=20, height=20):
    """运行演示的便捷入口"""
    demo = Demo(width, height)
    demo.run()


if __name__ == '__main__':
    try:
        run_demo()
    except KeyboardInterrupt:
        print("\n👋 再见！")
        sys.exit(0)
