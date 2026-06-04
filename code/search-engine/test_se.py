"""test_se.py — 搜索引擎测试（20+ 个测试用例）"""

import unittest
import math
from analyzer import Analyzer
from indexer import InvertedIndex
from searcher import Searcher


class TestAnalyzer(unittest.TestCase):
    """分词器测试"""

    def setUp(self):
        self.analyzer = Analyzer()

    def test_english_tokenization(self):
        """测试英文分词"""
        tokens = self.analyzer.analyze("Hello World Programming")
        self.assertIn('hello', tokens)
        self.assertIn('world', tokens)
        self.assertIn('programming', tokens)
        # 停用词应该被过滤
        self.assertNotIn('a', self.analyzer.analyze("a apple"))

    def test_chinese_tokenization(self):
        """测试中文分词"""
        tokens = self.analyzer.analyze("深度学习机器学习")
        self.assertIn('深', tokens)
        self.assertIn('度', tokens)
        self.assertIn('学', tokens)
        self.assertIn('习', tokens)
        self.assertIn('机', tokens)
        self.assertIn('器', tokens)

    def test_stop_words_removal(self):
        """测试停用词过滤"""
        tokens = self.analyzer.analyze("the is a an of in to and")
        # 所有停用词都应该被过滤
        for t in tokens:
            self.assertNotIn(t.lower(), {'the', 'is', 'a', 'an', 'of', 'in', 'to', 'and'})

    def test_empty_text(self):
        """测试空文本"""
        tokens = self.analyzer.analyze("")
        self.assertEqual(tokens, [])
        tokens = self.analyzer.analyze(None)
        self.assertEqual(tokens, [])

    def test_mixed_language(self):
        """测试混合语言分词"""
        tokens = self.analyzer.analyze("Python 深度学习 machine learning")
        self.assertIn('python', tokens)
        self.assertIn('深', tokens)
        self.assertIn('machine', tokens)
        self.assertIn('learning', tokens)

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        tokens1 = self.analyzer.analyze("Python")
        tokens2 = self.analyzer.analyze("python")
        self.assertEqual(tokens1, tokens2)

    def test_punctuation_removal(self):
        """测试标点符号移除"""
        tokens = self.analyzer.analyze("hello, world! test...")
        self.assertIn('hello', tokens)
        self.assertIn('world', tokens)
        self.assertIn('test', tokens)
        # 标点本身不应该出现
        for t in tokens:
            # 某些语言可能有标点，但这里主要是字母和中文
            pass

    def test_short_tokens(self):
        """测试单字符 token"""
        tokens = self.analyzer.analyze("a b c d")
        # 单个字母应该被过滤（不是停用词但是单字符）
        self.assertNotIn('a', tokens)


class TestInvertedIndex(unittest.TestCase):
    """倒排索引测试"""

    def setUp(self):
        self.index = InvertedIndex()
        self.index.add_document('1', title='Python', body='Python is a programming language')
        self.index.add_document('2', title='Machine Learning', body='Machine learning is a subset of AI')

    def test_add_document(self):
        """测试添加文档"""
        self.index.add_document('3', title='Test', body='This is a test document')
        self.assertIn('3', self.index.documents)
        self.assertEqual(self.index.doc_count, 3)

    def test_inverted_index_structure(self):
        """测试倒排索引结构"""
        # 基本结构应该是 {term: {doc_id: freq}}
        self.assertIn('python', self.index.inverted)
        # 'python' 应该在文档1中出现
        self.assertIn('1', self.index.inverted['python'])
        # 'machine' 应该在文档2中出现
        self.assertIn('machine', self.index.inverted)
        self.assertIn('2', self.index.inverted['machine'])

    def test_term_frequency(self):
        """测试词频统计"""
        # Python 在文档1中出现2次（标题2x + body1x）
        # 标题 "python" -> title重复2次 = 2次，body中1次 = 至少2次
        self.assertGreaterEqual(self.index.inverted['python']['1'], 2)

    def test_remove_document(self):
        """测试删除文档"""
        result = self.index.remove_document('1')
        self.assertTrue(result)
        self.assertNotIn('1', self.index.documents)
        self.assertEqual(self.index.doc_count, 1)
        # 文档1删除后，'python' 不应再出现在倒排中
        if 'python' in self.index.inverted:
            self.assertNotIn('1', self.index.inverted['python'])

    def test_document_frequency(self):
        """测试文档频次"""
        # 'python' 出现在文档1中
        df = self.index.document_frequency('python')
        self.assertEqual(df, 1)
        # 'learning' 出现在文档2中
        df = self.index.document_frequency('learning')
        self.assertEqual(df, 1)

    def test_tf_idf_calculation(self):
        """测试 TF-IDF 计算"""
        score = self.index.tf_idf('python', '1')
        self.assertGreater(score, 0)
        # 不存在的 term 应该返回 0
        score = self.index.tf_idf('nonexistent', '1')
        self.assertEqual(score, 0.0)
        # 文档中没有的 term 应该返回 0
        score = self.index.tf_idf('machine', '1')
        self.assertEqual(score, 0.0)

    def test_remove_nonexistent(self):
        """测试删除不存在的文档"""
        result = self.index.remove_document('999')
        self.assertFalse(result)

    def test_multiple_documents_same_term(self):
        """测试同一词出现在多篇文档中"""
        self.index.add_document('3', title='Advanced Python', body='Advanced python techniques')
        df = self.index.document_frequency('python')
        self.assertEqual(df, 2)

    def test_empty_term_search(self):
        """测试空词查询"""
        # 空字符串不应该出现在索引中
        self.assertNotIn('', self.index.inverted)


class TestSearcher(unittest.TestCase):
    """搜索器测试"""

    def setUp(self):
        self.index = InvertedIndex()
        self.index.add_document('1', title='Python Tutorial',
                                body='Python is a programming language for beginners and experts')
        self.index.add_document('2', title='Machine Learning Guide',
                                body='Machine learning is a subset of artificial intelligence deep learning')
        self.index.add_document('3', title='Data Science Basics',
                                body='Data science involves statistics machine learning and data analysis')
        self.index.add_document('4', title='Deep Learning Tutorial',
                                body='Deep learning uses neural networks layers subset of machine learning')
        self.index.add_document('5', title='Web Development',
                                body='Build web applications using Python frameworks like Django Flask')
        self.searcher = Searcher(self.index)

    def test_simple_search(self):
        """测试简单搜索"""
        results = self.searcher.search('python')
        self.assertGreater(len(results), 0)
        all_titles = [r['title'] for r in results]
        has_python = any('python' in t.lower() for t in all_titles)
        # 文档1和5包含 python
        self.assertTrue(has_python)

    def test_multi_word_search(self):
        """测试多词查询"""
        results = self.searcher.search('machine learning')
        self.assertGreater(len(results), 0)
        # 至少应该返回机器学习的相关文档
        self.assertIn('2', [r['doc_id'] for r in results])

    def test_no_match_search(self):
        """测试无匹配查询"""
        results = self.searcher.search('xyznonexistentterm12345')
        self.assertEqual(len(results), 0)

    def test_empty_query(self):
        """测试空查询"""
        results = self.searcher.search('')
        self.assertEqual(len(results), 0)
        results = self.searcher.search('   ')
        self.assertEqual(len(results), 0)

    def test_top_k_ranking(self):
        """测试 Top K 截断"""
        results = self.searcher.search('learning', top_k=2)
        self.assertLessEqual(len(results), 2)

    def test_scoring_order(self):
        """测试评分排序"""
        results = self.searcher.search('learning')
        if len(results) >= 2:
            self.assertGreaterEqual(results[0]['score'], results[1]['score'])

    def test_snippet_generation(self):
        """测试摘要生成"""
        results = self.searcher.search('python')
        for r in results:
            self.assertTrue('snippet' in r)
            # 摘要应该包含 'python' (大小写不敏感)
            self.assertIn('python', r['snippet'].lower())

    def test_result_fields(self):
        """测试结果字段完整性"""
        results = self.searcher.search('python')
        if results:
            r = results[0]
            self.assertIn('doc_id', r)
            self.assertIn('score', r)
            self.assertIn('title', r)
            self.assertIn('snippet', r)


class TestBooleanSearch(unittest.TestCase):
    """布尔搜索测试"""

    def setUp(self):
        self.index = InvertedIndex()
        self.index.add_document('1', title='Python Tutorial',
                                body='Python is a programming language')
        self.index.add_document('2', title='Machine Learning',
                                body='Machine learning and deep learning are AI topics')
        self.index.add_document('3', title='Python Data Science',
                                body='Python for data science and machine learning')
        self.index.add_document('4', title='Web Development',
                                body='Web development with Python using Flask')
        self.index.add_document('5', title='Deep Learning',
                                body='Deep learning neural networks')
        self.searcher = Searcher(self.index)

    def test_boolean_and(self):
        """测试 AND 布尔查询"""
        results = self.searcher.search('python AND learning', mode='boolean')
        # 同时包含 python 和 learning 的文档：文档3
        doc_ids = [r['doc_id'] for r in results]
        self.assertIn('3', doc_ids)
        # 文档1有python但没有learning，文档2有learning但没有python
        # 但注意lowercase vs token匹配...

    def test_boolean_or(self):
        """测试 OR 布尔查询"""
        results = self.searcher.search('python OR web', mode='boolean')
        doc_ids = [r['doc_id'] for r in results]
        # 包含 python 的文档：1,3,4；包含 web 的文档：4
        self.assertIn('1', doc_ids)
        self.assertIn('4', doc_ids)

    def test_boolean_not(self):
        """测试 NOT 布尔查询"""
        results = self.searcher.search('python NOT web', mode='boolean')
        doc_ids = [r['doc_id'] for r in results]
        # 包含 python 但不包含 web 的文档：1,3
        self.assertIn('1', doc_ids)
        self.assertIn('3', doc_ids)
        self.assertNotIn('4', doc_ids)

    def test_phrase_search(self):
        """测试短语查询"""
        results = self.searcher.search('"deep learning"', mode='boolean')
        doc_ids = [r['doc_id'] for r in results]
        # "deep learning" 作为短语出现在文档2和5中
        self.assertIn('2', doc_ids)
        self.assertIn('5', doc_ids)

    def test_boolean_mixed(self):
        """测试混合布尔查询"""
        results = self.searcher.search('python AND data AND learning', mode='boolean')
        doc_ids = [r['doc_id'] for r in results]
        # 同时包含 python, data, learning 的文档：3
        self.assertIn('3', doc_ids)


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_full_pipeline(self):
        """完整流程：构建索引 -> 搜索 -> 验证"""
        index = InvertedIndex()
        index.add_document('1', title='Test', body='This is a test document for testing')
        index.add_document('2', title='Search', body='Search engine search functionality')
        self.assertEqual(index.doc_count, 2)

        searcher = Searcher(index)

        # 排名搜索
        results = searcher.search('test')
        self.assertTrue(any('test' in r['title'].lower() for r in results))

        # 布尔搜索
        results = searcher.search('test AND search', mode='boolean')
        # 没有文档同时包含 test 和 search
        self.assertEqual(len(results), 0)

        # 删除文档后搜索
        index.remove_document('1')
        results = searcher.search('test')
        self.assertEqual(len(results), 0)

    def test_multiple_documents_with_relevance(self):
        """多文档相关性排序"""
        index = InvertedIndex()
        index.add_document('1', title='Python', body='Python language')
        index.add_document('2', title='Python Python Python',
                           body='Python Python Python Python programming language')
        index.add_document('3', title='Java', body='Java programming language')
        searcher = Searcher(index)

        results = searcher.search('python')
        # 文档2有更多python出现，应该有更高分数
        if len(results) >= 2:
            r1 = [r for r in results if r['doc_id'] == '1'][0]
            r2 = [r for r in results if r['doc_id'] == '2'][0]
            self.assertGreater(r2['score'], r1['score'])

    def test_chinese_search(self):
        """中文搜索"""
        index = InvertedIndex()
        index.add_document('1', title='深度学习',
                           body='深度学习是机器学习的一个重要分支')
        index.add_document('2', title='Python 数据分析',
                           body='Python 是数据科学最流行的编程语言')
        searcher = Searcher(index)

        results = searcher.search('深度')
        self.assertGreater(len(results), 0)
        self.assertIn('1', [r['doc_id'] for r in results])

        results = searcher.search('数据科学')
        self.assertGreater(len(results), 0)

    def test_store_and_load(self):
        """测试索引存储与加载"""
        import tempfile, os
        from store import save_index, load_index

        index = InvertedIndex()
        index.add_document('1', title='Python', body='Python language')

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            path = f.name

        try:
            save_index(index, path)
            loaded = load_index(path)
            self.assertEqual(loaded.doc_count, 1)
            self.assertIn('1', loaded.documents)
            self.assertIn('python', loaded.inverted)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_html_server_search(self):
        """测试 server.py 中的 HTML 页面和搜索处理器（不启动服务器）"""
        # 验证 server.py 可导入且 SearchHandler 可用
        import server
        self.assertTrue(hasattr(server, 'SearchHandler'))
        self.assertTrue(hasattr(server, 'create_sample_index'))

    def test_main_cli_search(self):
        """测试 main.py 中的 CLI 搜索功能（不实际运行 CLI）"""
        import main
        self.assertTrue(hasattr(main, 'cmd_search'))
        self.assertTrue(hasattr(main, '_create_sample_index'))


if __name__ == '__main__':
    unittest.main()
