"""迷你 GraphQL 类型系统"""

SCALAR_TYPES = {'String', 'Int', 'Float', 'Boolean', 'ID'}

# 标量类型快捷方式
String = 'String'
Int = 'Int'
Float = 'Float'
Boolean = 'Boolean'
ID = 'ID'


class Field:
    """字段定义"""

    def __init__(self, field_type, resolver=None, args=None, name=''):
        self.field_type = field_type  # 类型名(str) 或 ObjectType
        self.name = name
        self.resolver = resolver or (
            lambda root, **kwargs: root.get(self.name)
            if isinstance(root, dict)
            else getattr(root, self.name, None)
        )
        self.args = args or {}

    def __repr__(self):
        return f"Field({self.name}: {self.field_type})"


class ObjectType:
    """对象类型"""

    def __init__(self, name, fields):
        self.name = name
        self._fields = {}
        for f_name, f_def in fields.items():
            if isinstance(f_def, Field):
                f_def.name = f_name
                self._fields[f_name] = f_def
            else:
                # 快捷方式: {'name': str} -> Field(str, name=f_name)
                self._fields[f_name] = Field(f_def, name=f_name)

    def get_field(self, name):
        field = self._fields.get(name)
        if field is None:
            raise ValueError(f"未知字段: {self.name}.{name}")
        return field

    def get_fields(self):
        return dict(self._fields)

    def __repr__(self):
        return f"ObjectType({self.name})"


class Schema:
    """Schema 定义"""

    def __init__(self, query_type=None, mutation_type=None):
        self.query_type = query_type
        self.mutation_type = mutation_type

    def get_query_type(self):
        return self.query_type

    def get_mutation_type(self):
        return self.mutation_type
