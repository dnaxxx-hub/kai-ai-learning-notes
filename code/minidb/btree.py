"""B+Tree — balanced tree for key-value storage."""


class BPlusTreeNode:
    def __init__(self, is_leaf=False):
        self.is_leaf = is_leaf
        self.keys = []
        self.children = []
        self.next = None
        self.parent = None

    def __repr__(self):
        tag = "Leaf" if self.is_leaf else "Internal"
        return "%s(keys=%s)" % (tag, self.keys)


class BPlusTree:
    def __init__(self, order=4):
        self.order = order
        self.max_keys = order - 1
        self.min_keys = (order - 1) // 2
        self.root = BPlusTreeNode(is_leaf=True)

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

    def _split(self, node):
        new_node = BPlusTreeNode(is_leaf=node.is_leaf)
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
            parent = BPlusTreeNode(is_leaf=False)
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
        """合并 parent.children[idx] 和 parent.children[idx+1]"""
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
                # Remove the right child which has been absorbed
                parent.children.pop(idx + 1)

                mid = len(left.keys) // 2
                new_node = BPlusTreeNode(is_leaf=False)
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

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self):
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
        return {'order': self.order, 'root_id': self.root.node_id, 'nodes': nodes}

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
        return tree
