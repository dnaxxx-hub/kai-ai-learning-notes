"""排序算法 — 每一步 yield 数组状态"""
import random

def bubble_sort(arr):
    """冒泡排序"""
    a = list(arr)
    n = len(a)
    for i in range(n):
        for j in range(n - i - 1):
            yield list(a), [j, j+1], []
            if a[j] > a[j+1]:
                a[j], a[j+1] = a[j+1], a[j]
    yield list(a), [], list(range(n))

def selection_sort(arr):
    """选择排序"""
    a = list(arr)
    n = len(a)
    for i in range(n):
        min_idx = i
        for j in range(i + 1, n):
            yield list(a), [j], [i]
            if a[j] < a[min_idx]:
                min_idx = j
        a[i], a[min_idx] = a[min_idx], a[i]
        yield list(a), [i], list(range(i + 1))
    yield list(a), [], list(range(n))

def insertion_sort(arr):
    """插入排序"""
    a = list(arr)
    n = len(a)
    for i in range(1, n):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            yield list(a), [j, j + 1], list(range(i))
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
        yield list(a), [j + 1], list(range(i + 1))
    yield list(a), [], list(range(n))

def quick_sort(arr):
    """快速排序"""
    a = list(arr)
    def _quick(l, r):
        if l >= r:
            if l == r:
                yield list(a), [], [l]
            return
        pivot = a[r]
        i = l - 1
        for j in range(l, r):
            yield list(a), [j, r], list(range(l, j + 1))
            if a[j] <= pivot:
                i += 1
                a[i], a[j] = a[j], a[i]
        a[i + 1], a[r] = a[r], a[i + 1]
        p = i + 1
        yield list(a), [p], list(range(l, r + 1))
        yield from _quick(l, p - 1)
        yield from _quick(p + 1, r)

    yield from _quick(0, len(a) - 1)
    yield list(a), [], list(range(len(a)))

def merge_sort(arr):
    """归并排序"""
    a = list(arr)
    def _merge(l, m, r):
        left = a[l:m+1]
        right = a[m+1:r+1]
        i = j = 0
        k = l
        while i < len(left) and j < len(right):
            yield list(a), [k], list(range(l, r + 1))
            if left[i] <= right[j]:
                a[k] = left[i]
                i += 1
            else:
                a[k] = right[j]
                j += 1
            k += 1
        while i < len(left):
            yield list(a), [k], list(range(l, r + 1))
            a[k] = left[i]
            i += 1
            k += 1
        while j < len(right):
            yield list(a), [k], list(range(l, r + 1))
            a[k] = right[j]
            j += 1
            k += 1

    def _msort(l, r):
        if l >= r:
            yield list(a), [], [l]
            return
        m = (l + r) // 2
        yield from _msort(l, m)
        yield from _msort(m + 1, r)
        yield from _merge(l, m, r)

    yield from _msort(0, len(a) - 1)
    yield list(a), [], list(range(len(a)))

def heap_sort(arr):
    """堆排序"""
    a = list(arr)
    n = len(a)

    def heapify(n, i):
        largest = i
        l = 2 * i + 1
        r = 2 * i + 2
        if l < n and a[l] > a[largest]:
            largest = l
        if r < n and a[r] > a[largest]:
            largest = r
        if largest != i:
            yield list(a), [i, largest], []
            a[i], a[largest] = a[largest], a[i]
            yield from heapify(n, largest)

    # 建堆
    for i in range(n // 2 - 1, -1, -1):
        yield from heapify(n, i)

    # 排序
    for i in range(n - 1, 0, -1):
        yield list(a), [0, i], list(range(i, n))
        a[0], a[i] = a[i], a[0]
        yield from heapify(i, 0)

    yield list(a), [], list(range(n))

def get_algorithms():
    return {
        'bubble': bubble_sort,
        'selection': selection_sort,
        'insertion': insertion_sort,
        'quick': quick_sort,
        'merge': merge_sort,
        'heap': heap_sort,
    }

ALGORITHM_NAMES = {
    'bubble': '冒泡排序 O(n²)',
    'selection': '选择排序 O(n²)',
    'insertion': '插入排序 O(n²)',
    'quick': '快速排序 O(n log n)',
    'merge': '归并排序 O(n log n)',
    'heap': '堆排序 O(n log n)',
}
