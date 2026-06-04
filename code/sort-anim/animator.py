"""终端排序动画引擎"""
import os
import sys
import time

class SortAnimator:
    def __init__(self, array_size: int = 20, frame_delay: float = 0.05):
        self.size = array_size
        self.delay = frame_delay
        self.frames = 0

    def clear(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def render_bar(self, value: int, max_val: int, bar_char: str = '█'):
        """渲染一个柱状条"""
        width = self.size
        bar_len = int(value / max_val * (width - 2))
        return bar_char * max(1, bar_len)

    def render(self, arr: list, highlights: list, sorted_: list,
               algorithm_name: str, comparisons: int, swaps: int):
        """渲染一帧"""
        self.clear()
        max_val = max(arr) if arr else 1

        # 标题
        print(f"📊 {algorithm_name}")
        print(f"   比较: {comparisons}  交换: {swaps}  帧: {self.frames}")
        print()

        # 渲染数组
        for i, val in enumerate(arr):
            bar = self.render_bar(val, max_val)
            if i in highlights:
                # 高亮正在处理的元素（红色）
                bar = f"\033[91m{bar}\033[0m"
            elif i in sorted_:
                # 已排好的元素（绿色）
                bar = f"\033[92m{bar}\033[0m"
            else:
                # 普通（蓝色）
                bar = f"\033[94m{bar}\033[0m"

            print(f"{bar} {val:3d}")

        self.frames += 1

    def animate(self, sort_gen, algorithm_name: str, arr: list):
        """播放排序动画"""
        comparisons = 0
        swaps = 0

        for state, highlights, sorted_ in sort_gen:
            self.render(state, highlights, sorted_, algorithm_name, comparisons, swaps)
            comparisons += len(highlights)
            swaps += 1
            time.sleep(self.delay)

        # 最终状态
        self.render(state, [], list(range(len(state))), algorithm_name, comparisons, swaps)
        print(f"\n✅ 排序完成! 共 {self.frames} 帧")

    def run_silent(self, algorithm_name: str, arr: list):
        """静默排序（不显示动画只返回结果）"""
        from sorter import get_algorithms
        algo = get_algorithms()[algorithm_name]
        final_state = None
        for state, _, _ in algo(arr):
            final_state = state
        return final_state
