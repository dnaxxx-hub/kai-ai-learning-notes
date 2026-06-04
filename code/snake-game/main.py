#!/usr/bin/env python3
"""
main.py — 贪吃蛇游戏入口
"""

import sys
import os

# 确保可以导入同级模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game import run_game


if __name__ == '__main__':
    try:
        run_game(width=20, height=20)
    except KeyboardInterrupt:
        print("\n👋 再见！")
        sys.exit(0)
