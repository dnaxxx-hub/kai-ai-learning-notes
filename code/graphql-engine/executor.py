"""GraphQL 查询执行器"""

from schema import Schema, ObjectType, Field, SCALAR_TYPES


class Executor:
    """查询执行器"""

    def __init__(self, schema, root_value=None):
        self.schema = schema
        self.root_value = root_value or {}

    def execute(self, query_str):
        from parser import parse_query
        doc = parse_query(query_str)

        if not doc.operations:
            return {'errors': ['没有操作']}

        op = doc.operations[0]

        if op.operation_type == 'query':
            root_type = self.schema.get_query_type()
            if root_type is None:
                return {'errors': ['Query 类型未定义']}
            return self._execute_selection_set(
                op.selections, root_type, self.root_value
            )
        elif op.operation_type == 'mutation':
            root_type = self.schema.get_mutation_type()
            if root_type is None:
                return {'errors': ['Mutation 类型未定义']}
            return self._execute_selection_set(
                op.selections, root_type, self.root_value
            )

        return {'errors': ['不支持的查询类型']}

    def _execute_selection_set(self, selections, parent_type, parent_value):
        result = {}
        errors = []

        for sel in selections:
            try:
                field_def = parent_type.get_field(sel.name)
                args = sel.args
                raw_value = field_def.resolver(parent_value, **args)
                field_type = field_def.field_type

                # 处理列表对象
                if isinstance(raw_value, list) and sel.selections:
                    items = []
                    for item in raw_value:
                        if isinstance(field_type, ObjectType):
                            sub = self._execute_selection_set(
                                sel.selections, field_type, item
                            )
                            items.append(sub.get('data', sub))
                        elif isinstance(field_type, str):
                            resolved = self._resolve_type(field_type)
                            if resolved:
                                sub = self._execute_selection_set(
                                    sel.selections, resolved, item
                                )
                                items.append(sub.get('data', sub))
                            else:
                                items.append(item)
                        else:
                            items.append(item)
                    result[sel.alias] = items

                # 处理嵌套对象 (ObjectType)
                elif isinstance(field_type, ObjectType) and sel.selections:
                    sub = self._execute_selection_set(
                        sel.selections, field_type, raw_value
                    )
                    result[sel.alias] = sub.get('data', sub)

                # 处理字符串类型名的嵌套
                elif isinstance(field_type, str) and sel.selections:
                    resolved = self._resolve_type(field_type)
                    if resolved:
                        sub = self._execute_selection_set(
                            sel.selections, resolved, raw_value
                        )
                        result[sel.alias] = sub.get('data', sub)
                    else:
                        result[sel.alias] = raw_value

                # 标量值
                else:
                    result[sel.alias] = raw_value

            except Exception as e:
                errors.append(str(e))
                result[sel.alias] = None

        return {'data': result, 'errors': errors or None}

    def _resolve_type(self, type_name):
        """根据类型名查找 ObjectType"""
        for attr in dir(self.schema):
            if attr.startswith('_'):
                continue
            val = getattr(self.schema, attr)
            if isinstance(val, ObjectType) and val.name == type_name:
                return val
        return None
