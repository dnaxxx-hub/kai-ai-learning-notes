import time, uuid

class ZNode:
    """ZooKeeper 节点"""

    # 节点类型常量
    PERSISTENT = 0
    EPHEMERAL = 1
    PERSISTENT_SEQUENTIAL = 2
    EPHEMERAL_SEQUENTIAL = 3

    def __init__(self, path, data=b'', node_type=PERSISTENT, owner_session=None):
        self.path = path
        self.data = data if isinstance(data, bytes) else str(data).encode()
        self.node_type = node_type
        self.owner_session = owner_session  # ephemeral 节点的 session id
        self.children = {}  # {name: ZNode}
        self.created_at = time.time()
        self.modified_at = time.time()
        self.version = 0
        self.cversion = 0   # 子节点版本
        self.aversion = 0   # ACL 版本
        self.ephemeral_owner = 0

    def is_ephemeral(self):
        return self.node_type in (self.EPHEMERAL, self.EPHEMERAL_SEQUENTIAL)

    def is_sequential(self):
        return self.node_type in (self.PERSISTENT_SEQUENTIAL, self.EPHEMERAL_SEQUENTIAL)

    def to_dict(self):
        type_names = ['PERSISTENT', 'EPHEMERAL', 'PERSISTENT_SEQUENTIAL', 'EPHEMERAL_SEQUENTIAL']
        return {
            'path': self.path,
            'data': self.data.decode('utf-8', errors='replace'),
            'node_type': type_names[self.node_type],
            'version': self.version,
            'cversion': self.cversion,
            'aversion': self.aversion,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'ephemeral_owner': self.ephemeral_owner,
            'children': list(self.children.keys()),
        }

    def update_data(self, data):
        self.data = data if isinstance(data, bytes) else str(data).encode()
        self.version += 1
        self.modified_at = time.time()
