import json, os
from document import Document
from query import match_document, sort_documents, project_document, _is_operator_dict

class Collection:
    def __init__(self, name, db_path=None):
        self.name = name
        self.db_path = db_path
        self.documents = {}  # {doc_id: Document}
        self._load()

    def insert(self, data):
        """插入文档"""
        if isinstance(data, list):
            docs = []
            for d in data:
                doc = Document(d)
                self.documents[doc['_id']] = doc
                docs.append(doc)
            self._save()
            return docs
        doc = Document(data)
        self.documents[doc['_id']] = doc
        self._save()
        return doc

    def find(self, query=None, projection=None, sort=None, skip=0, limit=None):
        """查询文档"""
        query = query or {}
        results = []
        for doc in self.documents.values():
            if match_document(doc, query):
                results.append(doc)

        if sort:
            results = sort_documents(results, sort)

        if limit:
            results = results[skip:skip + limit]
        elif skip:
            results = results[skip:]

        if projection:
            results = [project_document(d, projection) for d in results]
        else:
            results = [d.to_dict() for d in results]

        return results

    def find_one(self, query=None):
        """查询单个"""
        results = self.find(query, limit=1)
        return results[0] if results else None

    def update(self, query, update_data, multi=True):
        """更新文档"""
        count = 0
        for doc_id, doc in self.documents.items():
            if match_document(doc, query):
                for key, value in update_data.items():
                    if key.startswith('$'):
                        continue
                    doc[key] = value
                count += 1
                if not multi:
                    break
        self._save()
        return count

    def delete(self, query, multi=True):
        """删除文档"""
        to_delete = []
        for doc_id, doc in self.documents.items():
            if match_document(doc, query):
                to_delete.append(doc_id)
                if not multi:
                    break
        for doc_id in to_delete:
            del self.documents[doc_id]
        self._save()
        return len(to_delete)

    def count(self, query=None):
        """计数"""
        if not query:
            return len(self.documents)
        return len(self.find(query))

    def _save(self):
        if not self.db_path:
            return
        path = os.path.join(self.db_path, f'{self.name}.json')
        data = [doc.to_dict() for doc in self.documents.values()]
        os.makedirs(self.db_path, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not self.db_path:
            return
        path = os.path.join(self.db_path, f'{self.name}.json')
        if not os.path.exists(path):
            return
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data:
            doc = Document(item.get('_data', item))
            self.documents[doc['_id']] = doc
