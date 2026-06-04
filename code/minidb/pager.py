"""Pager — 页面管理器，将 B+树持久化到文件。"""
import struct
import pickle
from collections import OrderedDict

PAGE_SIZE = 4096
# Header: is_leaf(?), num_keys(I), next_page(i), parent_page(i)
HEADER_FMT = '!?Iii'
HEADER_SIZE = struct.calcsize(HEADER_FMT)


class Page:
    def __init__(self, page_id=0, data=b''):
        self.page_id = page_id
        self.is_dirty = False
        self.data = data if data else b'\x00' * PAGE_SIZE

    def __repr__(self):
        return f"Page(id={self.page_id}, dirty={self.is_dirty})"


class Pager:
    def __init__(self, filename, page_size=PAGE_SIZE):
        self.filename = filename
        self.page_size = page_size
        self.cache = OrderedDict()
        self.cache_limit = 100
        self._file = None
        self._num_pages = 0

    def _ensure_open(self, mode='rb+'):
        if self._file is not None:
            return
        try:
            self._file = open(self.filename, mode)
        except FileNotFoundError:
            self._file = open(self.filename, 'wb+')
        self._file.seek(0, 2)
        self._num_pages = self._file.tell() // self.page_size

    def read_page(self, page_id):
        if page_id < 0:
            raise ValueError(f"Invalid page_id: {page_id}")
        if page_id in self.cache:
            self.cache.move_to_end(page_id)
            return self.cache[page_id]
        self._ensure_open()
        if page_id >= self._num_pages:
            raise ValueError(f"page_id {page_id} >= {self._num_pages}")
        self._file.seek(page_id * self.page_size)
        data = self._file.read(self.page_size)
        if len(data) < self.page_size:
            data += b'\x00' * (self.page_size - len(data))
        page = Page(page_id=page_id, data=data)
        self._cache(page)
        return page

    def write_page(self, page):
        self._ensure_open()
        self._file.seek(page.page_id * self.page_size)
        self._file.write(page.data)
        self._file.flush()
        page.is_dirty = False
        if page.page_id in self.cache:
            self.cache[page.page_id].is_dirty = False

    def allocate_page(self):
        self._ensure_open()
        pid = self._num_pages
        self._num_pages += 1
        self._file.seek(pid * self.page_size)
        self._file.write(b'\x00' * self.page_size)
        self._file.flush()
        page = Page(page_id=pid)
        self._cache(page)
        return page

    def _cache(self, page):
        self.cache[page.page_id] = page
        if len(self.cache) > self.cache_limit:
            eid, ep = self.cache.popitem(last=False)
            if ep.is_dirty:
                self.write_page(ep)

    def flush(self):
        for p in list(self.cache.values()):
            if p.is_dirty:
                self.write_page(p)
        if self._file:
            self._file.flush()

    def close(self):
        self.flush()
        if self._file:
            self._file.close()
            self._file = None

    def set_num_pages(self, n):
        self._num_pages = n


# ── 序列化/反序列化 ──────────────────────────────────

def serialize_node(page, node, all_nodes):
    """序列化 B+树节点到 Page。

    Layout:
      Header (HEADER_SIZE)
      node_id (int, 4 bytes)
      keys: int * num_keys (4 bytes each)
      If leaf: values: (len:4, data) * num_keys
      Else: children_ids: int * (num_keys+1)
    """
    data = bytearray(PAGE_SIZE)
    off = 0

    is_leaf = 1 if node.is_leaf else 0
    nk = len(node.keys)
    np_ = node.next.node_id if node.next else -1
    pp_ = node.parent.node_id if node.parent else -1
    struct.pack_into(HEADER_FMT, data, off, is_leaf, nk, np_, pp_)
    off += HEADER_SIZE

    # node_id
    nid = node.node_id if hasattr(node, 'node_id') else page.page_id
    struct.pack_into('!i', data, off, nid)
    off += 4

    # keys
    for k in node.keys:
        struct.pack_into('!i', data, off, k)
        off += 4

    if node.is_leaf:
        for v in node.children:
            ser = pickle.dumps(v)
            vl = len(ser)
            struct.pack_into('!I', data, off, vl)
            off += 4
            data[off:off + vl] = ser
            off += vl
    else:
        for c in node.children:
            cid = c.node_id if hasattr(c, 'node_id') else -1
            struct.pack_into('!i', data, off, cid)
            off += 4

    page.data = bytes(data)
    page.is_dirty = True


def deserialize_node(page, all_nodes=None):
    """从 Page 反序列化 B+树节点。"""
    data = page.data
    off = 0

    is_leaf_v, num_keys, next_p, parent_p = struct.unpack_from(HEADER_FMT, data, off)
    off += HEADER_SIZE

    stored_nid = struct.unpack_from('!i', data, off)[0]
    off += 4

    from btree import BPlusTreeNode as BNode

    node = BNode(is_leaf=bool(is_leaf_v))
    node.node_id = stored_nid

    keys = []
    for _ in range(num_keys):
        k = struct.unpack_from('!i', data, off)[0]
        keys.append(k)
        off += 4
    node.keys = keys

    if bool(is_leaf_v):
        values = []
        for _ in range(num_keys):
            vl = struct.unpack_from('!I', data, off)[0]
            off += 4
            v = pickle.loads(data[off:off + vl])
            values.append(v)
            off += vl
        node.children = values
        if next_p >= 0 and all_nodes and next_p in all_nodes:
            node.next = all_nodes[next_p]
    else:
        child_ids = []
        for _ in range(num_keys + 1):
            cid = struct.unpack_from('!i', data, off)[0]
            child_ids.append(cid)
            off += 4
        if all_nodes:
            node.children = [all_nodes[cid] for cid in child_ids if cid in all_nodes]
            for c in node.children:
                c.parent = node
        else:
            node.children = child_ids

    if parent_p >= 0 and all_nodes and parent_p in all_nodes:
        node.parent = all_nodes[parent_p]

    return node
