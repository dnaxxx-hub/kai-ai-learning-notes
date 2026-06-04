class Exchange:
    def __init__(self, name, exchange_type='direct'):
        self.name = name
        self.type = exchange_type   # direct / topic / fanout / headers
        self.auto_delete = False
        self._bind_headers = {}     # 用于 headers exchange 匹配

    def match(self, routing_key, headers=None):
        if self.type == 'fanout':
            return True

        if self.type == 'direct':
            return routing_key == routing_key   # 由 binding 的 routing_key 决定

        if self.type == 'topic':
            return True  # 由匹配逻辑在 engine 中处理

        if self.type == 'headers':
            if not headers:
                return False
            return all(headers.get(k) == v for k, v in self._bind_headers.items())

        return False

    @staticmethod
    def _topic_match(pattern, routing_key):
        """通配符匹配: * 匹配一个词, # 匹配0-N个词"""
        pattern_parts = pattern.split('.')
        key_parts = routing_key.split('.')

        i, j = 0, 0
        while i < len(pattern_parts) and j < len(key_parts):
            if pattern_parts[i] == '#':
                return True   # # 匹配所有剩余
            if pattern_parts[i] == '*':
                i += 1
                j += 1
            elif pattern_parts[i] == key_parts[j]:
                i += 1
                j += 1
            else:
                return False

        # 如果 pattern 已耗尽但 key 还有剩余，则不匹配
        if i >= len(pattern_parts) and j < len(key_parts):
            return False

        # 如果 pattern 还有剩余但都是 #，也能匹配
        while i < len(pattern_parts):
            if pattern_parts[i] != '#':
                return False
            i += 1

        return True
