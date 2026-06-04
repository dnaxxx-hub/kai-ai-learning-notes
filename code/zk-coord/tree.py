from znode import ZNode


class ZNodeTree:
    """树形命名空间"""

    def __init__(self):
        self.root = ZNode('/', b'', ZNode.PERSISTENT)

    def create(self, path, data=b'', node_type=ZNode.PERSISTENT, owner_session=None):
        """创建节点，支持顺序节点"""
        if path == '/':
            return None

        # 解析路径
        parts = path.strip('/').split('/')
        parent_path = '/' + '/'.join(parts[:-1])
        child_name = parts[-1]

        # 处理顺序节点
        if node_type in (ZNode.PERSISTENT_SEQUENTIAL, ZNode.EPHEMERAL_SEQUENTIAL):
            parent = self._get_node(parent_path)
            if parent is None:
                return None
            seq_num = len(parent.children) + 1
            child_name = f'{child_name}{seq_num:010d}'
            path = parent_path.rstrip('/') + '/' + child_name if parent_path != '/' else '/' + child_name

        parent = self._get_node(parent_path)
        if parent is None:
            return None

        if child_name in parent.children:
            return None

        node = ZNode(path, data, node_type, owner_session)
        parent.children[child_name] = node
        parent.cversion += 1
        return node

    def delete(self, path, version=-1):
        """删除节点（必须没有子节点）"""
        if path == '/':
            return False

        parent_path, child_name = self._split_path(path)
        parent = self._get_node(parent_path)
        if parent is None or child_name not in parent.children:
            return False

        node = parent.children[child_name]
        if node.children:
            return False  # 有子节点不能删除

        if version != -1 and node.version != version:
            return False

        del parent.children[child_name]
        parent.cversion += 1
        return True

    def set_data(self, path, data, version=-1):
        """设置节点数据"""
        node = self._get_node(path)
        if node is None:
            return None
        if version != -1 and node.version != version:
            return None
        node.update_data(data)
        return node

    def get_data(self, path):
        """获取节点数据"""
        node = self._get_node(path)
        if node is None:
            return None
        return node.data

    def get_children(self, path):
        """获取子节点列表"""
        node = self._get_node(path)
        if node is None:
            return None
        return sorted(node.children.keys())

    def exists(self, path):
        """检查节点是否存在"""
        return self._get_node(path) is not None

    def _get_node(self, path):
        """根据路径查找节点"""
        if path == '/':
            return self.root

        parts = path.strip('/').split('/')
        node = self.root
        for part in parts:
            if part not in node.children:
                return None
            node = node.children[part]
        return node

    def _split_path(self, path):
        """将路径分割为父路径和子节点名"""
        if '/' not in path.strip('/'):
            return '/', path.strip('/')
        parts = path.strip('/').split('/')
        parent_path = '/' + '/'.join(parts[:-1])
        return parent_path, parts[-1]

    def clean_ephemeral(self, session_id):
        """清理某个 session 的所有临时节点"""
        removed = []
        self._clean_ephemeral_recursive(self.root, session_id, removed)
        return removed

    def _clean_ephemeral_recursive(self, node, session_id, removed):
        to_del = []
        for name, child in list(node.children.items()):
            if child.is_ephemeral() and child.owner_session == session_id:
                to_del.append(name)
                removed.append(child.path)
            else:
                self._clean_ephemeral_recursive(child, session_id, removed)
        for name in to_del:
            del node.children[name]
        if to_del:
            node.cversion += 1

    def stat(self, path):
        """获取节点状态"""
        node = self._get_node(path)
        return node.to_dict() if node else None
