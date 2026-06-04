"""searcher.py — 搜索器（TF-IDF 排序 + 布尔逻辑）"""

import re
from analyzer import Analyzer


class Searcher:
    """搜索器"""

    def __init__(self, index):
        self.index = index
        self.analyzer = index.analyzer

    def search(self, query, top_k=10, mode='ranking'):
        """搜索入口"""
        if mode == 'boolean':
            return self._boolean_search(query, top_k)
        return self._ranking_search(query, top_k)

    def _ranking_search(self, query, top_k=10):
        """TF-IDF 排序搜索"""
        tokens = self.analyzer.analyze(query)
        if not tokens:
            return []

        # 收集匹配文档
        scores = {}
        matched_terms = set()

        for term in tokens:
            posting = self.index.inverted.get(term, {})
            if not posting:
                continue
            matched_terms.add(term)
            for doc_id in posting:
                score = self.index.tf_idf(term, doc_id)
                scores[doc_id] = scores.get(doc_id, 0) + score

        if not scores:
            return []

        # 按评分排序
        ranked = sorted(scores.items(), key=lambda x: -x[1])

        results = []
        for doc_id, score in ranked[:top_k]:
            doc = self.index.documents.get(doc_id, {})
            body = doc.get('body', '')
            results.append({
                'doc_id': doc_id,
                'score': round(score, 4),
                'title': doc.get('title', ''),
                'body': body[:200] + '...' if len(body) > 200 else body,
                'url': doc.get('url', ''),
                'snippet': self._generate_snippet(body, tokens),
            })

        return results

    def _boolean_search(self, query, top_k=10):
        """布尔查询：支持 AND / OR / NOT"""
        query = query.strip()

        # 提取短语查询
        phrase_matches = re.findall(r'"([^"]+)"', query)
        remaining = query
        for pm in phrase_matches:
            remaining = remaining.replace(f'"{pm}"', '').strip()

        # 解析剩余词
        terms = remaining.split() if remaining else []

        # 左结合解析布尔表达式
        result_set = None
        current_op = 'OR'

        for token in terms:
            token_upper = token.upper()
            if token_upper in ('AND', 'OR', 'NOT'):
                current_op = token_upper
                continue

            term_set = set(self.index.inverted.get(token, {}).keys())

            if current_op == 'NOT':
                if result_set is None:
                    all_docs = set(self.index.documents.keys())
                    result_set = all_docs - term_set
                else:
                    result_set -= term_set
            elif current_op == 'AND':
                if result_set is None:
                    result_set = term_set
                else:
                    result_set &= term_set
            else:  # OR
                if result_set is None:
                    result_set = term_set
                else:
                    result_set |= term_set

            current_op = 'OR'

        # 短语匹配：与结果集求交集
        for phrase in phrase_matches:
            phrase_docs = self._phrase_search(phrase)
            if result_set is None:
                result_set = phrase_docs
            else:
                result_set &= phrase_docs

        if result_set is None:
            return []

        # TF-IDF 排序
        all_query_text = remaining + ' ' + ' '.join(phrase_matches)
        scored = []
        for doc_id in result_set:
            score = sum(self.index.tf_idf(t, doc_id)
                       for t in self.analyzer.analyze(all_query_text))
            scored.append((doc_id, score))

        scored.sort(key=lambda x: -x[1])

        results = []
        for doc_id, score in scored[:top_k]:
            doc = self.index.documents.get(doc_id, {})
            results.append({
                'doc_id': doc_id,
                'score': round(score, 4),
                'title': doc.get('title', ''),
                'snippet': self._generate_snippet(
                    doc.get('body', ''),
                    self.analyzer.analyze(all_query_text)
                ),
            })

        return results

    def _phrase_search(self, phrase):
        """短语搜索：词在文档中出现且相邻"""
        tokens = self.analyzer.analyze(phrase)
        if not tokens:
            return set()

        if len(tokens) < 2:
            return set(self.index.inverted.get(tokens[0], {}).keys())

        # 滑动窗口检查
        result = set()
        first_term_docs = set(self.index.inverted.get(tokens[0], {}).keys())

        for doc_id in first_term_docs:
            doc = self.index.documents.get(doc_id, {}).get('body', '')
            doc_tokens = self.analyzer.analyze(doc)

            for i in range(len(doc_tokens) - len(tokens) + 1):
                if doc_tokens[i:i + len(tokens)] == tokens:
                    result.add(doc_id)
                    break

        return result

    def _generate_snippet(self, body, query_tokens, max_len=150):
        """生成搜索结果摘要"""
        if not body or not query_tokens:
            return body[:max_len] if body else ''

        body_lower = body.lower()

        # 查找第一个匹配位置
        first_pos = len(body)
        for token in query_tokens:
            pos = body_lower.find(token.lower())
            if pos != -1 and pos < first_pos:
                first_pos = pos

        if first_pos == len(body):
            return body[:max_len]

        start = max(0, first_pos - 50)
        end = min(len(body), first_pos + max_len)

        snippet = body[start:end]
        if start > 0:
            snippet = '...' + snippet
        if end < len(body):
            snippet = snippet + '...'

        return snippet
