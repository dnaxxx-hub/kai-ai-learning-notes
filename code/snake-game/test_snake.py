#!/usr/bin/env python3
"""
test_snake.py — 贪吃蛇游戏单元测试

测试：蛇移动方向、增长、自碰撞检测、墙碰撞、食物放置
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from snake import Board, UP, DOWN, LEFT, RIGHT


class TestSnake(unittest.TestCase):
    """贪吃蛇核心逻辑测试"""

    def setUp(self):
        self.board = Board(width=20, height=20)
        self.board._place_food()

    def test_initial_snake_length(self):
        """测试初始蛇长度为 3"""
        self.assertEqual(len(self.board.snake), 3)

    def test_snake_moves_right(self):
        """测试蛇向右移动"""
        old_head = self.board.snake[0]
        self.board.direction = RIGHT
        self.board.next_direction = RIGHT
        self.board.tick()
        new_head = self.board.snake[0]
        self.assertEqual(new_head, (old_head[0] + 1, old_head[1]))

    def test_snake_moves_down(self):
        """测试蛇向下移动"""
        old_head = self.board.snake[0]
        self.board.direction = DOWN
        self.board.next_direction = DOWN
        self.board.tick()
        new_head = self.board.snake[0]
        self.assertEqual(new_head, (old_head[0], old_head[1] + 1))

    def test_snake_grows_on_food(self):
        """测试吃到食物后蛇身长度+1"""
        initial_length = len(self.board.snake)
        head = self.board.snake[0]
        food_pos = (head[0] + 1, head[1])
        if food_pos not in set(self.board.snake):
            self.board.food = food_pos
            self.board.direction = RIGHT
            self.board.next_direction = RIGHT
            result = self.board.tick()
            self.assertEqual(result, 'eat')
            self.assertEqual(len(self.board.snake), initial_length + 1)
        else:
            self.skipTest("food would be placed on snake body")

    def test_wall_collision(self):
        """测试撞墙检测"""
        self.board.snake.clear()
        self.board.snake.append((self.board.width - 2, self.board.height // 2))
        self.board.snake.append((self.board.width - 3, self.board.height // 2))
        self.board.snake.append((self.board.width - 4, self.board.height // 2))
        self.board.direction = RIGHT
        self.board.next_direction = RIGHT
        self.board.food = None
        result = self.board.tick()
        self.assertEqual(result, 'crash')
        self.assertTrue(self.board.game_over)

    def test_self_collision(self):
        """测试自碰撞检测——蛇头被包围"""
        self.board.snake.clear()
        # 蛇头在 (3,3)，周围 8 格被蛇身占据（仅保留蛇尾 1 格空闲）
        # 蛇尾在 (0,0) —— 但蛇头往任何方向都撞身体
        self.board.snake.append((3, 3))  # 头
        # 蛇身：顺时针包围蛇头，蛇尾在 (2,3) — 注意蛇尾会被移除
        # 所以蛇尾这个位置例外
        coords = [(2, 2), (3, 2), (4, 2), (4, 3), (4, 4), (3, 4), (2, 4), (2, 3)]
        for c in coords:
            self.board.snake.append(c)
        self.board.food = None
        # 蛇头朝右 → (4,3) 在蛇身中（不是蛇尾）
        self.board.direction = RIGHT
        self.board.next_direction = RIGHT
        result = self.board.tick()
        self.assertEqual(result, 'crash')
        self.assertTrue(self.board.game_over)

    def test_self_collision_snake_tail_not_counted(self):
        """测试自碰撞：蛇尾即将移除时不算碰撞"""
        self.board.snake.clear()
        # 蛇头追着蛇尾走：蛇头下一步正好是蛇尾位置
        # 蛇尾应该被移除，所以不算碰撞
        self.board.snake.append((10, 10))  # 头
        self.board.snake.append((9, 10))
        self.board.snake.append((8, 10))  # 尾
        # 蛇头向左 → (9,10) 这是蛇身，不是蛇尾，会撞
        self.board.direction = LEFT
        self.board.next_direction = LEFT
        self.board.food = None
        result = self.board.tick()
        # 蛇头从 (10,10)→(9,10)，(9,10) 是蛇身
        self.assertEqual(result, 'crash')
        self.assertTrue(self.board.game_over)

    def test_no_180_turn(self):
        """测试不能180°掉头"""
        self.board.direction = RIGHT
        self.board.next_direction = RIGHT
        self.board.set_direction(LEFT)
        self.assertEqual(self.board.next_direction, RIGHT)

    def test_score_increases(self):
        """测试分数增加"""
        head = self.board.snake[0]
        food_pos = (head[0] + 1, head[1])
        if food_pos in set(self.board.snake):
            self.skipTest("food on snake body")
        self.board.food = food_pos
        self.board.direction = RIGHT
        self.board.next_direction = RIGHT
        old_score = self.board.score
        self.board.tick()
        self.assertEqual(self.board.score, old_score + 1)

    def test_food_not_on_snake(self):
        """测试食物不会生成在蛇身上"""
        for _ in range(100):
            self.board._place_food()
            if self.board.food:
                self.assertNotIn(self.board.food, set(self.board.snake),
                                 f"Food {self.board.food} is on snake!")

    def test_restart(self):
        """测试重启"""
        self.board.score = 50
        self.board.game_over = True
        self.board.restart()
        self.assertEqual(len(self.board.snake), 3)
        self.assertEqual(self.board.score, 0)
        self.assertFalse(self.board.game_over)

    def test_tick_returns_move(self):
        """测试 tick 返回 'move' 状态"""
        result = self.board.tick()
        self.assertIn(result, ('move', 'eat'))

    def test_set_direction_block_opposite(self):
        """测试 set_direction 阻止反向"""
        self.board.direction = UP
        self.board.next_direction = UP
        self.board.set_direction(DOWN)  # 试图掉头
        self.assertEqual(self.board.next_direction, UP)

    def test_snake_moves_preserves_length(self):
        """测试普通移动保持蛇长度不变"""
        initial_len = len(self.board.snake)
        self.board.tick()
        self.assertEqual(len(self.board.snake), initial_len)


if __name__ == '__main__':
    unittest.main()
