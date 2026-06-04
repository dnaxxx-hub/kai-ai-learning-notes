import json, copy, time

class Document:
    """文档模型 — 字典包装器，自动生成 _id，支持 _created 和 _updated"""
    def __init__(self, data=None, doc_id=None):
        self._data = data or {}
        if '_id' not in self._data:
            self._data['_id'] = doc_id or self._generate_id()
        if '_created' not in self._data:
            self._data['_created'] = time.time()
        self._data['_updated'] = time.time()

    @staticmethod
    def _generate_id():
        import uuid
        return str(uuid.uuid4())

    def __getitem__(self, key):
        return self._get_by_path(key)

    def __setitem__(self, key, value):
        self._set_by_path(key, value)
        self._data['_updated'] = time.time()

    def _get_by_path(self, path):
        parts = path.split('.')
        obj = self._data
        for part in parts:
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                raise KeyError(path)
        return obj

    def _set_by_path(self, path, value):
        parts = path.split('.')
        obj = self._data
        for part in parts[:-1]:
            if part not in obj:
                obj[part] = {}
            obj = obj[part]
        obj[parts[-1]] = value

    def get(self, key, default=None):
        try:
            return self._get_by_path(key)
        except KeyError:
            return default

    def to_dict(self):
        return copy.deepcopy(self._data)

    def to_json(self):
        return json.dumps(self._data, ensure_ascii=False)
