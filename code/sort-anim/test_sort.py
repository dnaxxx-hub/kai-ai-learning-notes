"""排序算法测试"""
import unittest
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))

from sorter import *

class TestSortingAlgorithms(unittest.TestCase):
    def setUp(self):
        self.test_cases = [
            [],
            [1],
            [1, 2, 3, 4, 5],
            [5, 4, 3, 2, 1],
            [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5],
            [42],
            [random.randint(1, 100) for _ in range(20)],
        ]

    def verify_sorted(self, arr):
        """验证数组是否升序"""
        for i in range(len(arr) - 1):
            if arr[i] > arr[i + 1]:
                return False
        return True

    def test_bubble_sort(self):
        for case in self.test_cases:
            original = list(case)
            result = None
            for state, _, _ in bubble_sort(case):
                result = state
            self.assertEqual(sorted(original), result,
                             f"Bubble sort failed on {original}")
            self.assertTrue(self.verify_sorted(result))

    def test_selection_sort(self):
        for case in self.test_cases:
            original = list(case)
            result = None
            for state, _, _ in selection_sort(case):
                result = state
            self.assertEqual(sorted(original), result,
                             f"Selection sort failed on {original}")

    def test_insertion_sort(self):
        for case in self.test_cases:
            original = list(case)
            result = None
            for state, _, _ in insertion_sort(case):
                result = state
            self.assertEqual(sorted(original), result,
                             f"Insertion sort failed on {original}")

    def test_quick_sort(self):
        for case in self.test_cases:
            original = list(case)
            result = None
            for state, _, _ in quick_sort(case):
                result = state
            self.assertEqual(sorted(original), result,
                             f"Quick sort failed on {original}")

    def test_merge_sort(self):
        for case in self.test_cases:
            original = list(case)
            result = None
            for state, _, _ in merge_sort(case):
                result = state
            self.assertEqual(sorted(original), result,
                             f"Merge sort failed on {original}")

    def test_heap_sort(self):
        for case in self.test_cases:
            original = list(case)
            result = None
            for state, _, _ in heap_sort(case):
                result = state
            self.assertEqual(sorted(original), result,
                             f"Heap sort failed on {original}")

    def test_correctness_all_algorithms(self):
        """所有算法在随机数据上正确"""
        for _ in range(10):
            data = [random.randint(1, 1000) for _ in range(50)]
            expected = sorted(data)

            for name, algo in get_algorithms().items():
                result = None
                for state, _, _ in algo(list(data)):
                    result = state
                self.assertEqual(expected, result, f"{name} failed")

class TestYieldFormat(unittest.TestCase):
    def test_bubble_yields_steps(self):
        steps = list(bubble_sort([3, 2, 1]))
        self.assertGreater(len(steps), 0)
        for state, highlights, sorted_ in steps:
            self.assertIsInstance(state, list)
            self.assertIsInstance(highlights, list)
            self.assertIsInstance(sorted_, list)

    def test_final_state_sorted(self):
        steps = list(insertion_sort([4, 2, 5, 1, 3]))
        final_state = steps[-1][0]
        self.assertEqual(final_state, [1, 2, 3, 4, 5])

if __name__ == '__main__':
    unittest.main()
