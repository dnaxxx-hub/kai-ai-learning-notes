"""indexer.py — 倒排索引构建器（分词 + 文档频次）"""

import math
from analyzer import Analyzer


class InvertedIndex:
    """倒排索引"""

    def __init__(self, analyzer=None):
        self.analyzer = analyzer or Analyzer()
        self.documents = {}      # {doc_id: {'title': ..., 'body': ..., 'url': ...}}
        self.doc_count = 0
        self.inverted = {}       # {term: {doc_id: frequency}}
        self.doc_lengths = {}    # {doc_id: total_terms}

    def add_document(self, doc_id, title='', body='', url='', metadata=None):
        """添加文档到索引"""
        text = f"{title} {title} {body}"  # 标题权重 2x
        tokens = self.analyzer.analyze(text)

        # 词频统计
        term_freq = {}
        for token in tokens:
            term_freq[token] = term_freq.get(token, 0) + 1

        # 更新倒排索引
        for term, freq in term_freq.items():
            if term not in self.inverted:
                self.inverted[term] = {}
            self.inverted[term][doc_id] = freq

        # 存储文档
        self.documents[doc_id] = {
            'title': title,
            'body': body,
            'url': url,
            'metadata': metadata or {},
        }
        self.doc_count += 1
        self.doc_lengths[doc_id] = len(tokens)

    def remove_document(self, doc_id):
        """删除文档"""
        if doc_id not in self.documents:
            return False

        for term in list(self.inverted.keys()):
            if doc_id in self.inverted[term]:
                del self.inverted[term][doc_id]
                if not self.inverted[term]:
                    del self.inverted[term]

        del self.documents[doc_id]
        self.doc_lengths.pop(doc_id, None)
        self.doc_count -= 1
        return True

    def document_frequency(self, term):
        """文档频次"""
        posting = self.inverted.get(term, {})
        return len(posting)

    def total_documents(self):
        return self.doc_count

    def tf_idf(self, term, doc_id):
        """TF-IDF 评分"""
        posting = self.inverted.get(term)
        if not posting:
            return 0.0

        freq = posting.get(doc_id, 0)
        if freq == 0:
            return 0.0

        # TF = 1 + log10(freq)
        tf = 1 + math.log10(freq) if freq > 0 else 0

        # IDF = log10(N / df) + 1
        n = self.doc_count
        df = len(posting)
        idf = math.log10(n / (df + 1)) + 1

        return tf * idf
