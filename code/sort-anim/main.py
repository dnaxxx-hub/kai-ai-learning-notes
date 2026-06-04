#!/usr/bin/env python3
"""排序算法动画器 CLI"""
import sys
import os
import random
sys.path.insert(0, os.path.dirname(__file__))

from sorter import get_algorithms, ALGORITHM_NAMES
from animator import SortAnimator

def main():
    import argparse
    parser = argparse.ArgumentParser(description='排序算法动画器')
    parser.add_argument('algorithm', nargs='?', default='bubble',
                        choices=list(get_algorithms().keys()),
                        help='排序算法')
    parser.add_argument('-n', '--size', type=int, default=15,
                        help='数组大小 (默认 15)')
    parser.add_argument('-s', '--speed', type=float, default=0.05,
                        help='帧延迟秒数 (默认 0.05)')
    parser.add_argument('-r', '--random', action='store_true',
                        help='使用随机数据')
    parser.add_argument('--list', action='store_true',
                        help='列出所有算法')
    parser.add_argument('--all', action='store_true',
                        help='运行所有算法')

    args = parser.parse_args()

    if args.list:
        print("支持的排序算法:")
        for key, name in ALGORITHM_NAMES.items():
            print(f"  {key:12} — {name}")
        return

    if args.random:
        data = [random.randint(1, 99) for _ in range(args.size)]
    else:
        # 默认：部分有序（更容易看到算法行为）
        data = [50, 30, 80, 10, 90, 40, 60, 20, 70, 5, 95, 35, 85, 15, 75][:args.size]

    animator = SortAnimator(len(data), args.speed)

    if args.all:
        for key, algo_fn in get_algorithms().items():
            name = ALGORITHM_NAMES[key]
            animator.frames = 0
            data_copy = list(data)
            gen = algo_fn(data_copy)
            animator.animate(gen, name, data_copy)
            input("\n按 Enter 继续下一个...")
    else:
        algo_fn = get_algorithms()[args.algorithm]
        name = ALGORITHM_NAMES[args.algorithm]
        gen = algo_fn(data)
        animator.animate(gen, name, data)

if __name__ == '__main__':
    main()
