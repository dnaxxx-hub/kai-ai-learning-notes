import unittest
import json, os, tempfile, shutil
from document import Document
from collection import Collection
from query import match_document, sort_documents, project_document
from db import Database

class TestDocument(unittest.TestCase):
    """测试 Document 类"""

    def test_auto_id(self):
        """文档自动生成 _id"""
        doc = Document({'name': 'Alice'})
        self.assertIsNotNone(doc['_id'])
        self.assertIn('_created', doc._data)
        self.assertIn('_updated', doc._data)

    def test_get_set(self):
        """文档读写"""
        doc = Document({'name': 'Alice', 'age': 30})
        self.assertEqual(doc['name'], 'Alice')
        doc['age'] = 31
        self.assertEqual(doc['age'], 31)

    def test_nested_path(self):
        """嵌套文档点号路径"""
        doc = Document({'user': {'name': 'Bob', 'address': {'city': 'Beijing'}}})
        self.assertEqual(doc['user.name'], 'Bob')
        self.assertEqual(doc['user.address.city'], 'Beijing')

    def test_get_default(self):
        """get 方法默认值"""
        doc = Document({'name': 'Alice'})
        self.assertEqual(doc.get('age', 0), 0)
        self.assertIsNone(doc.get('nonexistent'))

    def test_to_dict_json(self):
        """序列化"""
        doc = Document({'name': 'Alice'})
        d = doc.to_dict()
        self.assertEqual(d['name'], 'Alice')
        j = doc.to_json()
        self.assertIn('Alice', j)


class TestQuery(unittest.TestCase):
    """测试查询引擎"""

    def setUp(self):
        self.docs = [
            Document({'name': 'Alice', 'age': 30, 'city': 'Beijing'}),
            Document({'name': 'Bob', 'age': 25, 'city': 'Shanghai'}),
            Document({'name': 'Charlie', 'age': 35, 'city': 'Beijing'}),
            Document({'name': 'David', 'age': 28, 'city': 'Shenzhen'}),
        ]

    def test_eq(self):
        """$eq 操作符"""
        result = [d for d in self.docs if match_document(d, {'name': {'$eq': 'Alice'}})]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Alice')

    def test_ne(self):
        """$ne 操作符"""
        result = [d for d in self.docs if match_document(d, {'city': {'$ne': 'Beijing'}})]
        self.assertEqual(len(result), 2)

    def test_gt_lt(self):
        """$gt 和 $lt 操作符"""
        result = [d for d in self.docs if match_document(d, {'age': {'$gt': 28}})]
        self.assertEqual(len(result), 2)
        result = [d for d in self.docs if match_document(d, {'age': {'$lt': 30}})]
        self.assertEqual(len(result), 2)

    def test_gte_lte(self):
        """$gte 和 $lte 操作符"""
        result = [d for d in self.docs if match_document(d, {'age': {'$gte': 30}})]
        self.assertEqual(len(result), 2)
        result = [d for d in self.docs if match_document(d, {'age': {'$lte': 25}})]
        self.assertEqual(len(result), 1)

    def test_in_nin(self):
        """$in 和 $nin 操作符"""
        result = [d for d in self.docs if match_document(d, {'city': {'$in': ['Beijing', 'Shanghai']}})]
        self.assertEqual(len(result), 3)
        result = [d for d in self.docs if match_document(d, {'city': {'$nin': ['Beijing', 'Shanghai']}})]
        self.assertEqual(len(result), 1)

    def test_exists(self):
        """$exists 操作符"""
        result = [d for d in self.docs if match_document(d, {'age': {'$exists': True}})]
        self.assertEqual(len(result), 4)
        result = [d for d in self.docs if match_document(d, {'nonexistent': {'$exists': False}})]
        self.assertEqual(len(result), 4)

    def test_regex(self):
        """$regex 操作符"""
        result = [d for d in self.docs if match_document(d, {'name': {'$regex': '^A'}})]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'Alice')

    def test_and_or_not(self):
        """$and, $or, $not 逻辑操作符"""
        # $and
        result = [d for d in self.docs if match_document(d, {'$and': [{'age': {'$gt': 25}}, {'city': 'Beijing'}]})]
        self.assertEqual(len(result), 2)

        # $or
        result = [d for d in self.docs if match_document(d, {'$or': [{'name': 'Alice'}, {'name': 'Bob'}]})]
        self.assertEqual(len(result), 2)

        # $not
        result = [d for d in self.docs if match_document(d, {'age': {'$not': {'$gt': 30}}})]
        self.assertEqual(len(result), 3)

    def test_sort(self):
        """排序"""
        sorted_docs = sort_documents(self.docs, {'age': 1})
        ages = [d['age'] for d in sorted_docs]
        self.assertEqual(ages, [25, 28, 30, 35])

        sorted_docs_desc = sort_documents(self.docs, {'age': -1})
        ages_desc = [d['age'] for d in sorted_docs_desc]
        self.assertEqual(ages_desc, [35, 30, 28, 25])

    def test_projection(self):
        """字段投影"""
        doc = self.docs[0]
        projected = project_document(doc, {'name': 1, 'age': 1})
        self.assertIn('name', projected)
        self.assertIn('age', projected)
        self.assertIn('_id', projected)  # _id 始终包含

        projected_exclude = project_document(doc, {'name': 0})
        self.assertNotIn('name', projected_exclude)
        self.assertIn('age', projected_exclude)

    def test_direct_match(self):
        """直接值匹配（默认 $eq）"""
        result = [d for d in self.docs if match_document(d, {'name': 'Alice'})]
        self.assertEqual(len(result), 1)


class TestCollection(unittest.TestCase):
    """测试 Collection 类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.col = Collection('test', self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_insert_find(self):
        """插入和查询"""
        doc = self.col.insert({'name': 'Alice', 'age': 30})
        self.assertIsNotNone(doc['_id'])
        results = self.col.find({'name': 'Alice'})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Alice')

    def test_insert_many(self):
        """批量插入"""
        docs = self.col.insert([
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
        ])
        self.assertEqual(len(docs), 2)
        self.assertEqual(self.col.count(), 2)

    def test_find_one(self):
        """find_one 方法"""
        self.col.insert({'name': 'Alice', 'age': 30})
        self.col.insert({'name': 'Bob', 'age': 25})
        result = self.col.find_one({'name': 'Alice'})
        self.assertIsNotNone(result)
        self.assertEqual(result['name'], 'Alice')

    def test_find_one_not_found(self):
        """find_one 未找到"""
        result = self.col.find_one({'name': 'Nonexistent'})
        self.assertIsNone(result)

    def test_update(self):
        """更新文档"""
        self.col.insert({'name': 'Alice', 'age': 30})
        count = self.col.update({'name': 'Alice'}, {'age': 31})
        self.assertEqual(count, 1)
        result = self.col.find_one({'name': 'Alice'})
        self.assertEqual(result['age'], 31)

    def test_update_multi(self):
        """批量更新"""
        self.col.insert([
            {'name': 'Alice', 'city': 'Beijing'},
            {'name': 'Bob', 'city': 'Beijing'},
        ])
        count = self.col.update({'city': 'Beijing'}, {'city': 'Shanghai'}, multi=True)
        self.assertEqual(count, 2)
        results = self.col.find({'city': 'Shanghai'})
        self.assertEqual(len(results), 2)

    def test_delete(self):
        """删除文档"""
        self.col.insert({'name': 'Alice', 'age': 30})
        self.col.insert({'name': 'Bob', 'age': 25})
        count = self.col.delete({'name': 'Alice'})
        self.assertEqual(count, 1)
        self.assertEqual(self.col.count(), 1)

    def test_delete_multi(self):
        """批量删除"""
        self.col.insert([
            {'name': 'Alice', 'city': 'Beijing'},
            {'name': 'Bob', 'city': 'Beijing'},
        ])
        count = self.col.delete({'city': 'Beijing'}, multi=True)
        self.assertEqual(count, 2)
        self.assertEqual(self.col.count(), 0)

    def test_count(self):
        """计数"""
        self.col.insert([
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 35},
        ])
        self.assertEqual(self.col.count(), 3)
        self.assertEqual(self.col.count({'age': {'$gt': 28}}), 2)

    def test_persistence(self):
        """文件持久化"""
        self.col.insert([
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
        ])
        del self.col
        # 重新加载
        col2 = Collection('test', self.temp_dir)
        self.assertEqual(col2.count(), 2)
        results = col2.find({'name': 'Alice'})
        self.assertEqual(len(results), 1)

    def test_find_with_skip_limit(self):
        """分页查询"""
        self.col.insert([
            {'name': 'Alice', 'age': 30},
            {'name': 'Bob', 'age': 25},
            {'name': 'Charlie', 'age': 35},
        ])
        # 按年龄升序: Bob(25), Alice(30), Charlie(35)
        # skip=1, limit=1 → Alice(30)
        results = self.col.find(sort={'age': 1}, skip=1, limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Alice')

    def test_find_with_projection(self):
        """带投影的查询"""
        self.col.insert({'name': 'Alice', 'age': 30, 'city': 'Beijing'})
        results = self.col.find(projection={'name': 1, 'age': 1})
        self.assertIn('name', results[0])
        self.assertIn('age', results[0])
        self.assertIn('_id', results[0])
        self.assertNotIn('city', results[0])


class TestDatabase(unittest.TestCase):
    """测试 Database 类"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db = Database(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_collection(self):
        """获取集合"""
        col = self.db.collection('users')
        self.assertIsNotNone(col)
        self.assertEqual(col.name, 'users')

    def test_drop(self):
        """删除集合"""
        self.db.collection('users').insert({'name': 'Alice'})
        self.db.drop('users')
        # 重新获取是一个新集合
        col = self.db.collection('users')
        self.assertEqual(col.count(), 0)


if __name__ == '__main__':
    unittest.main()
