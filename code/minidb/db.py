"""MiniDB — 文件持久化的 B+树键值存储"""

import os
import pickle
from btree import BPlusTree
from pager import Pager, PAGE_SIZE


class MiniDB:
    def __init__(self, filename='minidb.dat', order=4):
        self.filename = filename
        self.order = order
        self.tree = BPlusTree(order)
        self.pager = Pager(filename)
        self._dirty = False

    def put(self, key, value):
        self.tree.insert(key, value)
        self._dirty = True

    def get(self, key):
        return self.tree.search(key)

    def delete(self, key):
        result = self.tree.delete(key)
        if result:
            self._dirty = True
        return result

    def range(self, start, end=None):
        if end is not None:
            return self.tree.range_query(start, end)
        return self.tree.range_query(start)

    def save(self):
        if not self._dirty:
            return

        tree_dict = self.tree.to_dict()
        data = pickle.dumps(tree_dict)
        data = data + b'\x00' * (PAGE_SIZE - len(data))
        data = data[:PAGE_SIZE]

        # Truncate the file and write a fresh page 0
        self.pager.close()

        with open(self.filename, 'wb') as f:
            f.write(data)
            f.flush()

        # Reopen pager
        self.pager = Pager(self.filename)
        self.pager._ensure_open('rb+')
        self._dirty = False

    def load(self):
        if not os.path.exists(self.filename):
            return False

        try:
            self.pager._ensure_open('rb+')
            if self.pager._num_pages < 1:
                return False

            page = self.pager.read_page(0)
            raw = page.data
            # Strip null bytes
            end = len(raw)
            while end > 0 and raw[end-1] == 0:
                end -= 1
            tree_dict = pickle.loads(raw[:end])

            self.tree = BPlusTree.from_dict(tree_dict)
            self.order = tree_dict['order']
            self._dirty = False
            return True

        except Exception as e:
            print(f"加载数据时出错: {e}")
            import traceback
            traceback.print_exc()
            return False

    def stats(self):
        return self.tree.stats()

    def close(self):
        if self._dirty:
            self.save()
        self.pager.close()
