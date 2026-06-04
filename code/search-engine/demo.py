"""demo.py — 搜索引擎演示"""

from analyzer import Analyzer
from indexer import InvertedIndex
from searcher import Searcher


def main():
    print("=" * 60)
    print("Search Engine Demo")
    print("=" * 60)

    # 1. 分词器演示
    print("\n--- 1. Analyzer Demo ---")
    analyzer = Analyzer()
    texts = [
        "Hello World! This is a test.",
        "Python is a great programming language",
        "机器学习是人工智能的一个子领域",
        "深度学习使用神经网络",
    ]
    for text in texts:
        tokens = analyzer.analyze(text)
        print(f"  Input: {text}")
        print(f"  Tokens: {tokens}")
        print()

    # 2. 构建索引
    print("--- 2. Building Index ---")
    index = InvertedIndex()

    documents = [
        ('1', 'Python Tutorial',
         'Python is a programming language. Learn Python for data science and web development. Python tutorial for beginners.'),
        ('2', 'Machine Learning Guide',
         'Machine learning is a subset of artificial intelligence. Deep learning and neural networks are popular topics in AI.'),
        ('3', 'Data Science Basics',
         'Data science involves statistics, machine learning, and data analysis. Python is widely used in data science.'),
        ('4', 'Deep Learning Tutorial',
         'Deep learning uses neural networks with many layers. It is a subset of machine learning focused on complex patterns.'),
        ('5', 'Web Development with Python',
         'Build web applications using Python frameworks like Django and Flask. Python makes web development easy and fun.'),
        ('6', '深度学习入门',
         '深度学习是机器学习的一个重要分支。它使用神经网络来模拟人脑的学习过程。'),
        ('7', 'Python 数据分析',
         'Python 是数据科学领域最流行的编程语言。Pandas 和 NumPy 是常用的数据分析库。'),
    ]

    for doc_id, title, body in documents:
        index.add_document(doc_id, title=title, body=body)
        print(f"  Added: [{doc_id}] {title}")

    print(f"\n  Total documents: {index.doc_count}")
    print(f"  Unique terms: {len(index.inverted)}")
    print(f"  Sample terms: {list(index.inverted.keys())[:10]}...")

    # 3. 搜索演示
    print("\n--- 3. Ranking Search ---")
    searcher = Searcher(index)

    queries = [
        "python tutorial",
        "machine learning",
        "deep learning",
        "数据科学",
    ]

    for query in queries:
        print(f"\n  Query: '{query}'")
        results = searcher.search(query, top_k=3)
        for r in results:
            print(f"    [{r['doc_id']}] {r['title']} (score: {r['score']})")
            print(f"    Snippet: {r['snippet'][:80]}...")
        if not results:
            print("    (no results)")

    # 4. 布尔搜索
    print("\n--- 4. Boolean Search ---")

    boolean_queries = [
        "python AND learning",
        "python OR deep",
        "python NOT web",
        '"deep learning"',
    ]

    for query in boolean_queries:
        print(f"\n  Query: '{query}'")
        results = searcher.search(query, top_k=5, mode='boolean')
        for r in results:
            print(f"    [{r['doc_id']}] {r['title']} (score: {r['score']})")
        if not results:
            print("    (no results)")

    # 5. 示例文档详情
    print("\n--- 5. Document Details ---")
    for doc_id in ['1', '6']:
        doc = index.documents.get(doc_id, {})
        print(f"  [{doc_id}] {doc.get('title', '')}")
        print(f"    Body: {doc.get('body', '')[:100]}...")

    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
