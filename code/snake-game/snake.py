"""
snake.py — 蛇 + 食物 + 碰撞逻辑

Board 类管理二维网格，蛇位用双端队列，食物随机生成。
纯标准库，零依赖。
"""

import random
from collections import deque

# 方向常量
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# 方向映射（用于键盘输入）
DIRECTION_MAP = {
    'w': UP, 'W': UP,
    's': DOWN, 'S': DOWN,
    'a': LEFT, 'A': LEFT,
    'd': RIGHT, 'D': RIGHT,
}

# 方向键映射（ANSI 转义序列 → 方向）
ARROW_MAP = {
    'H': UP,    # Up
    'P': DOWN,  # Down
    'K': LEFT,  # Left
    'M': RIGHT, # Right
}

OPPOSITE = {
    UP: DOWN,
    DOWN: UP,
    LEFT: RIGHT,
    RIGHT: LEFT,
}


class Board:
    """游戏棋盘，管理蛇和食物"""

    def __init__(self, width=20, height=20):
        self.width = width
        self.height = height
        self.snake = deque()
        self.direction = RIGHT
        self.next_direction = RIGHT
        self.food = None
        self.score = 0
        self.high_score = 0
        self.game_over = False
        self.won = False
        self._init_snake()

    def _init_snake(self):
        """初始化蛇（3 节，居中偏左）"""
        self.snake.clear()
        start_x = self.width // 4
        start_y = self.height // 2
        for i in range(3):
            self.snake.append((start_x - i, start_y))
        self.direction = RIGHT
        self.next_direction = RIGHT
        self.score = 0
        self.game_over = False
        self.won = False

    def set_direction(self, direction):
        """设置下一帧的方向（防止180°掉头）"""
        if direction and direction != OPPOSITE.get(self.direction):
            self.next_direction = direction

    def _place_food(self):
        """在空白位置随机放置食物"""
        snake_set = set(self.snake)
        empty = [(x, y) for x in range(1, self.width - 1)
                 for y in range(1, self.height - 1)
                 if (x, y) not in snake_set]
        if not empty:
            # 蛇填满了整个空间 → 胜利
            self.won = True
            self.game_over = True
            self.food = None
            return
        self.food = random.choice(empty)

    def tick(self):
        """推进一帧：移动蛇，检测碰撞，吃食物
        返回：'move' / 'eat' / 'crash' / 'win'
        """
        if self.game_over:
            return 'game_over'

        # 应用方向
        self.direction = self.next_direction

        # 计算新蛇头
        dx, dy = self.direction
        head = self.snake[0]
        new_head = (head[0] + dx, head[1] + dy)

        # 撞墙检测
        if (new_head[0] <= 0 or new_head[0] >= self.width - 1 or
                new_head[1] <= 0 or new_head[1] >= self.height - 1):
            self.game_over = True
            return 'crash'

        # 自碰撞检测（注意：蛇尾即将移除，需特殊处理）
        tail = self.snake[-1]
        snake_without_tail = list(self.snake)[:-1]
        if new_head in snake_without_tail:
            self.game_over = True
            return 'crash'

        # 移动
        self.snake.appendleft(new_head)

        # 吃食物
        if self.food and new_head == self.food:
            self.score += 1
            self._place_food()
            if self.won:
                return 'win'
            return 'eat'

        # 移除蛇尾
        self.snake.pop()
        return 'move'

    def restart(self):
        """重启游戏"""
        self._init_snake()
        self._place_food()

    def reset(self):
        """重启游戏（同 restart）"""
        self.restart()

    def get_snake_positions(self):
        """返回蛇的位置列表（蛇头在前）"""
        return list(self.snake)
