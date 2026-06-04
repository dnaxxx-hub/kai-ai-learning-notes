import re

def match_document(doc, query):
    """检查文档是否匹配查询条件"""
    for key, condition in query.items():
        # 顶层逻辑操作符
        if key == '$and':
            if not all(match_document(doc, subcond) for subcond in condition):
                return False
            continue
        if key == '$or':
            if not any(match_document(doc, subcond) for subcond in condition):
                return False
            continue
        if key == '$nor':
            if any(match_document(doc, subcond) for subcond in condition):
                return False
            continue
        val = doc.get(key)
        if not _match_condition(key, val, condition):
            return False
    return True

def _match_condition(key, val, condition):
    """匹配单个条件"""
    if isinstance(condition, dict) and not _is_operator_dict(condition):
        # 子文档匹配
        if not isinstance(val, dict):
            return False
        for k, v in condition.items():
            if not _match_condition(k, val.get(k), v):
                return False
        return True

    # 操作符
    if isinstance(condition, dict):
        for op, expected in condition.items():
            if op == '$eq':
                return val == expected
            if op == '$ne':
                return val != expected
            if op == '$gt':
                return val is not None and val > expected
            if op == '$gte':
                return val is not None and val >= expected
            if op == '$lt':
                return val is not None and val < expected
            if op == '$lte':
                return val is not None and val <= expected
            if op == '$in':
                return val in expected
            if op == '$nin':
                return val not in expected
            if op == '$exists':
                return (val is not None) == expected
            if op == '$regex':
                return val is not None and bool(re.search(expected, str(val)))
            if op == '$and':
                # 将 val 作为子文档检查所有子条件
                return all(match_document({'check': v}, {'check': subcond})
                          for subcond in expected)
            if op == '$or':
                return any(match_document({'check': v}, {'check': subcond})
                          for subcond in expected)
            if op == '$not':
                return not _match_condition(key, val, expected)
        return True

    # 默认 $eq
    return val == condition

def _is_operator_dict(d):
    return any(k.startswith('$') for k in d.keys())

def sort_documents(docs, sort_spec):
    """排序文档列表"""
    if not sort_spec:
        return docs

    def _sort_key(doc):
        keys = []
        for key, direction in sort_spec.items():
            val = doc.get(key) or 0
            keys.append(val if direction == 1 else -val)
        return tuple(keys)

    return sorted(docs, key=_sort_key)

def project_document(doc, fields):
    """字段投影"""
    if not fields:
        return doc
    include = [k for k, v in fields.items() if v == 1]
    exclude = [k for k, v in fields.items() if v == 0]

    result = {}
    if include:
        for field in include:
            val = doc.get(field)
            if val is not None:
                result[field] = val
        # 始终包含 _id（除非明确排除）
        if '_id' not in include and '_id' not in fields:
            result['_id'] = doc.get('_id')
    elif exclude:
        result = dict(doc.to_dict())
        for field in exclude:
            result.pop(field, None)
    return result
