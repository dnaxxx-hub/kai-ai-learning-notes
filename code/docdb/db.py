import os
from collection import Collection

class Database:
    def __init__(self, path='docdb_data'):
        self.path = path
        self.collections = {}

    def collection(self, name):
        if name not in self.collections:
            self.collections[name] = Collection(name, self.path)
        return self.collections[name]

    def drop(self, name):
        if name in self.collections:
            del self.collections[name]
        # 也删除持久化文件
        file_path = os.path.join(self.path, f'{name}.json')
        if os.path.exists(file_path):
            os.remove(file_path)
