"""
renderer.py — 终端渲染（ANSI 字符画）

用字符 '#' 画墙，'O' 蛇头，'o' 蛇身，'@' 食物。
颜色 ANSI 转义序列，纯标准库。
"""

import os
import sys

# ANSI 颜色
RESET = '\033[0m'
BOLD = '\033[1m'

# 前景色
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
WHITE = '\033[97m'
DARK_GREEN = '\033[32m'

# 背景
BG_BLACK = '\033[40m'

# 字符
WALL = '#'
SNAKE_HEAD = 'O'
SNAKE_BODY = 'o'
FOOD = '@'
EMPTY = ' '


def clear_screen():
    """清除终端屏幕"""
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


def hide_cursor():
    """隐藏光标"""
    sys.stdout.write('\033[?25l')
    sys.stdout.flush()


def show_cursor():
    """显示光标"""
    sys.stdout.write('\033[?25h')
    sys.stdout.flush()


def move_cursor(x, y):
    """移动光标到 (x, y)"""
    sys.stdout.write(f'\033[{y};{x}H')


def render(board, paused=False, show_border=True):
    """渲染游戏画面到终端

    Args:
        board: Board 实例
        paused: 是否暂停
        show_border: 是否在渲染区域周围显示简化的边框线
    """
    output = []
    # 头部信息
    info = (f'{BOLD}{CYAN} 🐍 贪吃蛇 {RESET}'
            f'  Score: {BOLD}{YELLOW}{board.score}{RESET}'
            f'  High: {BOLD}{YELLOW}{board.high_score}{RESET}')
    output.append(info)
    output.append('')

    snake_set = set(board.snake)
    snake_head = board.snake[0]

    for y in range(board.height):
        row = []
        for x in range(board.width):
            is_wall = (x == 0 or x == board.width - 1 or
                       y == 0 or y == board.height - 1)

            if is_wall:
                row.append(f'{WHITE}{BG_BLACK}{WALL}{RESET}')
            elif board.food and (x, y) == board.food:
                row.append(f'{RED}{BOLD}{FOOD}{RESET}')
            elif (x, y) == snake_head:
                row.append(f'{GREEN}{BOLD}{SNAKE_HEAD}{RESET}')
            elif (x, y) in snake_set:
                row.append(f'{DARK_GREEN}{SNAKE_BODY}{RESET}')
            else:
                row.append(EMPTY)
        output.append(' ' + ''.join(row))

    output.append('')

    # 控制提示
    if board.game_over:
        if board.won:
            output.append(f'  {BOLD}{YELLOW}🎉 你赢了！全部填满！{RESET}')
        else:
            output.append(f'  {BOLD}{RED}💀 游戏结束！{RESET}')
        output.append(f'  {CYAN}按 R 重新开始  |  按 Q 退出{RESET}')
    elif paused:
        output.append(f'  {BOLD}{YELLOW}⏸ 暂停中{RESET}')
        output.append(f'  {CYAN}按 P 继续  |  按 R 重新开始  |  按 Q 退出{RESET}')
    else:
        output.append(f'  {CYAN}WASD/方向键移动  P暂停  R重启  Q退出{RESET}')

    # 写入一次性输出
    sys.stdout.write('\033[J')  # 清除光标之下
    sys.stdout.write('\n'.join(output))
    sys.stdout.flush()


def render_game_over(board):
    """渲染游戏结束画面（独立模式）"""
    clear_screen()
    output = []
    if board.won:
        output.append(f'\n  {BOLD}{YELLOW}🎉 恭喜通关！你填满了整个地图！{RESET}')
    else:
        output.append(f'\n  {BOLD}{RED}💀 游戏结束{RESET}')
    output.append(f'  {CYAN}最终得分: {BOLD}{YELLOW}{board.score}{RESET}')
    output.append(f'  {CYAN}最高记录: {BOLD}{YELLOW}{board.high_score}{RESET}')
    output.append(f'\n  {WHITE}按 R 重新开始  |  按 Q 退出{RESET}')
    sys.stdout.write('\n'.join(output))
    sys.stdout.flush()


def render_demo(board, speed, total_moves):
    """渲染演示模式画面"""
    output = []
    info = (f'{BOLD}{CYAN} 🐍 演示模式{RESET}'
            f'  Score: {BOLD}{YELLOW}{board.score}{RESET}'
            f'  Moves: {total_moves}')
    output.append(info)
    output.append('')

    snake_set = set(board.snake)
    snake_head = board.snake[0]

    for y in range(board.height):
        row = []
        for x in range(board.width):
            is_wall = (x == 0 or x == board.width - 1 or
                       y == 0 or y == board.height - 1)
            if is_wall:
                row.append(f'{WHITE}{BG_BLACK}{WALL}{RESET}')
            elif board.food and (x, y) == board.food:
                row.append(f'{RED}{BOLD}{FOOD}{RESET}')
            elif (x, y) == snake_head:
                row.append(f'{GREEN}{BOLD}{SNAKE_HEAD}{RESET}')
            elif (x, y) in snake_set:
                row.append(f'{DARK_GREEN}{SNAKE_BODY}{RESET}')
            else:
                row.append(EMPTY)
        output.append(' ' + ''.join(row))

    output.append('')
    output.append(f'  {CYAN}速度: {speed:.2f} tick/s  按 Q 退出{RESET}')

    sys.stdout.write('\033[J')
    sys.stdout.write('\n'.join(output))
    sys.stdout.flush()
