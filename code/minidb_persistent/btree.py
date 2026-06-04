"""B+Tree — balanced tree for key-value storage with serialization support."""

import json
import struct
import os

# ── Page format constants ──────────────────────────
PAGE_SIZE = 4096
NODE_HEADER_FMT = '!Biii'  # is_leaf(B:1), num_keys(i), next_page(i), self_id(i)
# All int fields use 'i' (signed) to allow -1 sentinel for next_page
NODE_HEADER_SIZE = struct.calcsize(NODE_HEADER_FMT)


class BPlusTreeNode:
    __slots__ = ('is_leaf', 'keys', 'children', 'next', 'parent', 'node_id')

    def __init__(self, is_leaf=False):
        self.is_leaf = is_leaf
        self.keys = []
        self.children = []  # For leaf: values. For internal: child node refs
        self.next = None
        self.parent = None
        self.node_id = -1

    def __repr__(self):
        tag = "Leaf" if self.is_leaf else "Internal"
        return "%s(id=%d, keys=%s)" % (tag, self.node_id, self.keys)


class BPlusTree:
    def __init__(self, order=4):
        self.order = order
        self.max_keys = order - 1
        self.min_keys = max((order - 1) // 2, 1)
        self.root = BPlusTreeNode(is_leaf=True)
        self.root.node_id = 0
        self._next_id = 1

    def _alloc_id(self):
        nid = self._next_id
        self._next_id += 1
        return nid

    def _find_leaf(self, key):
        node = self.root
        while not node.is_leaf:
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            if i >= len(node.children):
                i = len(node.children) - 1
            node = node.children[i]
        return node

    def search(self, key):
        leaf = self._find_leaf(key)
        for i, k in enumerate(leaf.keys):
            if k == key:
                return leaf.children[i]
        return None

    # ── 插入 ──────────────────────────────────────────

    def insert(self, key, value):
        leaf = self._find_leaf(key)
        for i, k in enumerate(leaf.keys):
            if k == key:
                leaf.children[i] = value
                return
        i = 0
        while i < len(leaf.keys) and key > leaf.keys[i]:
            i += 1
        leaf.keys.insert(i, key)
        leaf.children.insert(i, value)
        if len(leaf.keys) > self.max_keys:
            self._split(leaf)

    def _make_node(self, is_leaf):
        n = BPlusTreeNode(is_leaf=is_leaf)
        n.node_id = self._alloc_id()
        return n

    def _split(self, node):
        new_node = self._make_node(is_leaf=node.is_leaf)
        mid = len(node.keys) // 2

        if node.is_leaf:
            mid_key = node.keys[mid]
            new_node.keys = node.keys[mid:]
            new_node.children = node.children[mid:]
            node.keys = node.keys[:mid]
            node.children = node.children[:mid]
            new_node.next = node.next
            node.next = new_node
        else:
            mid_key = node.keys[mid]
            new_node.keys = node.keys[mid + 1:]
            new_node.children = node.children[mid + 1:]
            node.keys = node.keys[:mid]
            node.children = node.children[:mid + 1]
            for c in new_node.children:
                if c is not None:
                    c.parent = new_node

        new_node.parent = node.parent
        parent = node.parent
        if parent is None:
            parent = self._make_node(is_leaf=False)
            parent.keys = [mid_key]
            parent.children = [node, new_node]
            node.parent = parent
            new_node.parent = parent
            self.root = parent
            return

        i = 0
        while i < len(parent.keys) and mid_key > parent.keys[i]:
            i += 1
        parent.keys.insert(i, mid_key)
        parent.children.insert(i + 1, new_node)

        if len(parent.keys) > self.max_keys:
            self._split(parent)

    # ── 删除 ──────────────────────────────────────────

    def delete(self, key):
        leaf = self._find_leaf(key)
        idx = -1
        for i, k in enumerate(leaf.keys):
            if k == key:
                idx = i
                break
        if idx == -1:
            return False

        leaf.keys.pop(idx)
        leaf.children.pop(idx)

        if leaf is self.root:
            return True

        if len(leaf.keys) >= self.min_keys:
            return True

        self._fix_underflow(leaf)
        return True

    def _fix_underflow(self, node):
        if node is self.root or node.parent is None:
            return
        parent = node.parent
        try:
            idx = parent.children.index(node)
        except ValueError:
            return

        if idx > 0 and len(parent.children[idx - 1].keys) > self.min_keys:
            self._borrow_left(parent, idx)
            return
        if idx < len(parent.children) - 1 and len(parent.children[idx + 1].keys) > self.min_keys:
            self._borrow_right(parent, idx)
            return
        if idx > 0:
            self._merge(parent, idx - 1)
        else:
            self._merge(parent, idx)

    def _borrow_left(self, parent, idx):
        node = parent.children[idx]
        left = parent.children[idx - 1]
        if node.is_leaf:
            k, v = left.keys.pop(), left.children.pop()
            node.keys.insert(0, k)
            node.children.insert(0, v)
            parent.keys[idx - 1] = node.keys[0]
        else:
            k, c = left.keys.pop(), left.children.pop()
            sep = parent.keys[idx - 1]
            parent.keys[idx - 1] = k
            node.keys.insert(0, sep)
            node.children.insert(0, c)
            if c is not None:
                c.parent = node

    def _borrow_right(self, parent, idx):
        node = parent.children[idx]
        right = parent.children[idx + 1]
        if node.is_leaf:
            k, v = right.keys.pop(0), right.children.pop(0)
            node.keys.append(k)
            node.children.append(v)
            parent.keys[idx] = right.keys[0] if right.keys else 0
        else:
            k, c = right.keys.pop(0), right.children.pop(0)
            sep = parent.keys[idx]
            parent.keys[idx] = k
            node.keys.append(sep)
            node.children.append(c)
            if c is not None:
                c.parent = node

    def _merge(self, parent, idx):
        left = parent.children[idx]
        right = parent.children[idx + 1]
        if left.is_leaf:
            left.keys.extend(right.keys)
            left.children.extend(right.children)
            left.next = right.next
            parent.keys.pop(idx)
        else:
            sep = parent.keys.pop(idx)
            left.keys.append(sep)
            left.keys.extend(right.keys)
            left.children.extend(right.children)
            for c in right.children:
                if c is not None:
                    c.parent = left
            if len(left.keys) > self.max_keys:
                parent.children.pop(idx + 1)
                mid = len(left.keys) // 2
                new_node = self._make_node(is_leaf=False)
                mid_key = left.keys[mid]
                new_node.keys = left.keys[mid + 1:]
                new_node.children = left.children[mid + 1:]
                left.keys = left.keys[:mid]
                left.children = left.children[:mid + 1]
                for c in new_node.children:
                    if c is not None:
                        c.parent = new_node
                new_node.parent = parent
                pi = max(idx, 0)
                while pi < len(parent.keys) and mid_key > parent.keys[pi]:
                    pi += 1
                parent.keys.insert(pi, mid_key)
                parent.children.insert(pi + 1, new_node)
                if len(parent.keys) > self.max_keys:
                    self._split(parent)
                return
        parent.children.pop(idx + 1)
        if parent is self.root and len(parent.keys) == 0:
            self.root = left
            left.parent = None
            left.node_id = 0
        elif parent is not self.root and len(parent.keys) < self.min_keys:
            self._fix_underflow(parent)

    # ── 范围查询 ──────────────────────────────────────

    def range_query(self, start, end=None):
        leaf = self._find_leaf(start)
        results = []
        while leaf:
            for i, k in enumerate(leaf.keys):
                if k >= start:
                    if end is not None and k >= end:
                        return results
                    results.append((k, leaf.children[i]))
            leaf = leaf.next
        return results

    # ── 统计 ──────────────────────────────────────────

    def stats(self):
        h = 0
        n = self.root
        while not n.is_leaf and n.children:
            h += 1
            n = n.children[0]
        tn = [0]
        tk = [0]

        def walk(node):
            tn[0] += 1
            tk[0] += len(node.keys)
            if not node.is_leaf:
                for c in node.children:
                    walk(c)

        walk(self.root)
        return {
            'order': self.order, 'height': h,
            'total_nodes': tn[0], 'total_keys': tk[0],
            'root_keys': len(self.root.keys), 'root_is_leaf': self.root.is_leaf,
        }

    # ── 序列化（JSON-based, binary-friendly）──────────

    def to_dict(self):
        """Serialize entire tree to a nested dict structure."""
        node_ids = {}
        counter = [0]

        def assign(n):
            n.node_id = counter[0]
            counter[0] += 1
            node_ids[n.node_id] = n
            if not n.is_leaf:
                for c in n.children:
                    assign(c)

        assign(self.root)
        nodes = {}
        for nid, n in node_ids.items():
            d = {'is_leaf': n.is_leaf, 'keys': list(n.keys),
                 'next': n.next.node_id if n.next else -1}
            if n.is_leaf:
                d['values'] = list(n.children)
            else:
                d['children'] = [c.node_id for c in n.children]
            nodes[nid] = d
        return {'order': self.order, 'root_id': self.root.node_id,
                'next_id': self._next_id, 'nodes': nodes}

    @classmethod
    def from_dict(cls, data):
        tree = cls(order=data['order'])
        all_nodes = {}
        for nid_str, ndata in data['nodes'].items():
            nid = int(nid_str)
            n = BPlusTreeNode(is_leaf=ndata['is_leaf'])
            n.keys = list(ndata['keys'])
            n.node_id = nid
            all_nodes[nid] = n

        # First pass: build structure
        for nid_str, ndata in data['nodes'].items():
            nid = int(nid_str)
            n = all_nodes[nid]
            if n.is_leaf:
                n.children = list(ndata['values'])
                nd = ndata['next']
                n.next = all_nodes.get(nd) if nd >= 0 else None
            else:
                n.children = [all_nodes[cid] for cid in ndata['children']]
                for c in n.children:
                    if c is not None:
                        c.parent = n

        tree.root = all_nodes[data['root_id']]
        tree.root.parent = None
        tree._next_id = data.get('next_id', len(all_nodes))
        return tree

    # ── Binary page-level serialization ───────────────

    def serialize_to_pages(self):
        """Serialize tree to a list of (page_id, bytes) pairs. Each node gets one page."""
        pages = []
        nodes_by_id = {}

        # Collect all nodes
        def walk(n):
            if n.node_id < 0:
                n.node_id = self._alloc_id()
            nodes_by_id[n.node_id] = n
            if not n.is_leaf:
                for c in n.children:
                    walk(c)

        # Reassign IDs to ensure contiguous
        counter = [0]
        def reassign(n):
            n.node_id = counter[0]
            counter[0] += 1
            if not n.is_leaf:
                for c in n.children:
                    reassign(c)

        # Ensure root has proper ID
        self.root.node_id = 0 if self.root.node_id < 0 else self.root.node_id
        reassign(self.root)
        self._next_id = counter[0]
        walk(self.root)

        for nid in sorted(nodes_by_id.keys()):
            n = nodes_by_id[nid]
            page_data = self._serialize_node(n, nodes_by_id)
            pages.append((nid, page_data))
        return pages

    def _serialize_node(self, node, all_nodes):
        """Serialize a single BPlusTreeNode into a fixed-size page."""
        data = bytearray(PAGE_SIZE)
        off = 0

        is_leaf = 1 if node.is_leaf else 0
        nk = len(node.keys)
        next_id = node.next.node_id if node.next else -1
        # Pack node_id as positive only for self_id; next_id can be -1 as sentinel
        struct.pack_into(NODE_HEADER_FMT, data, off, is_leaf, nk, next_id, node.node_id)
        off += NODE_HEADER_SIZE

        # Pack keys (4 bytes each, signed int)
        for k in node.keys:
            struct.pack_into('!i', data, off, k)
            off += 4

        if node.is_leaf:
            # For leaf: values stored as JSON after keys
            values_bytes = json.dumps(node.children, ensure_ascii=False).encode('utf-8')
            struct.pack_into('!I', data, off, len(values_bytes))
            off += 4
            end = min(off + len(values_bytes), PAGE_SIZE)
            data[off:end] = values_bytes[:end - off]
        else:
            # For internal: children IDs as ints
            for c in node.children:
                cid = c.node_id if c else -1
                struct.pack_into('!i', data, off, cid)
                off += 4

        return bytes(data)

    @classmethod
    def deserialize_from_pages(cls, pages_dict, order=4):
        """Rebuild tree from a dict of {page_id: bytes}."""
        tree = cls(order=order)
        all_nodes = {}

        # First pass: create all nodes
        for pid, raw in pages_dict.items():
            pid = int(pid)
            is_leaf_v, num_keys, next_p, self_id = struct.unpack_from(NODE_HEADER_FMT, raw, 0)
            n = BPlusTreeNode(is_leaf=bool(is_leaf_v))
            n.node_id = self_id
            all_nodes[pid] = n

        # Second pass: populate keys and children
        for pid, raw in pages_dict.items():
            pid = int(pid)
            is_leaf_v, num_keys, next_p, self_id = struct.unpack_from(NODE_HEADER_FMT, raw, 0)
            n = all_nodes[pid]
            off = NODE_HEADER_SIZE

            # Read keys
            keys = []
            for _ in range(num_keys):
                k = struct.unpack_from('!i', raw, off)[0]
                keys.append(k)
                off += 4
            n.keys = keys

            if bool(is_leaf_v):
                # Read values length and JSON
                if num_keys > 0:
                    vlen = struct.unpack_from('!I', raw, off)[0]
                    off += 4
                    values_json = raw[off:off + vlen].decode('utf-8', errors='replace')
                    n.children = json.loads(values_json)
                else:
                    n.children = []
                if next_p >= 0 and next_p in all_nodes:
                    n.next = all_nodes[next_p]
            else:
                child_ids = []
                for _ in range(num_keys + 1):
                    cid = struct.unpack_from('!i', raw, off)[0]
                    child_ids.append(cid)
                    off += 4
                n.children = [all_nodes.get(cid) for cid in child_ids]
                for c in n.children:
                    if c is not None:
                        c.parent = n

        root_id = 0  # Always page 0 is root
        if root_id in all_nodes:
            tree.root = all_nodes[root_id]
        tree.root.parent = None
        tree._next_id = len(all_nodes)
        return tree


if __name__ == '__main__':
    # Quick test
    t = BPlusTree(order=4)
    for i in range(50):
        t.insert(i, f'val-{i}')
    print("Stats:", t.stats())
    print("Search 25:", t.search(25))
    print("Range [10,20):", t.range_query(10, 20))

    d = t.to_dict()
    t2 = BPlusTree.from_dict(d)
    print("Re-loaded search 25:", t2.search(25))
    print("Range [10,20):", t2.range_query(10, 20))

    pages = t.serialize_to_pages()
    pages_dict = {pid: data for pid, data in pages}
    t3 = BPlusTree.deserialize_from_pages(pages_dict)
    print("Binary reload search 25:", t3.search(25))
