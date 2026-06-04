"""演示：运行 6 种排序算法对比"""
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))

from sorter import get_algorithms, ALGORITHM_NAMES
from animator import SortAnimator

def demo():
    data = [random.randint(1, 99) for _ in range(20)]
    animator = SortAnimator(len(data), 0.03)

    print("=" * 40)
    print("📊 排序算法动画演示")
    print(f"   数据: {data}")
    print(f"   大小: {len(data)} 个元素")
    print("=" * 40)
    input("按 Enter 开始...")

    for key, algo_fn in get_algorithms().items():
        name = ALGORITHM_NAMES[key]
        animator.frames = 0
        gen = algo_fn(list(data))
        animator.animate(gen, name, list(data))
        input("\n按 Enter 继续...")

if __name__ == '__main__':
    try:
        demo()
    except KeyboardInterrupt:
        print("\n\n演示结束.")
