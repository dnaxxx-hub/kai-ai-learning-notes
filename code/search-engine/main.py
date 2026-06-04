"""main.py — CLI 入口"""

import argparse
import json
from analyzer import Analyzer
from indexer import InvertedIndex
from searcher import Searcher
from store import save_index, load_index


def cmd_index(args):
    """构建索引"""
    index = InvertedIndex()
    count = 0
    for line in args.file:
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t', 2)
        if len(parts) == 3:
            doc_id, title, body = parts
        elif len(parts) == 2:
            doc_id, body = parts
            title = ''
        else:
            continue
        index.add_document(doc_id, title=title, body=body)
        count += 1

    if args.output:
        save_index(index, args.output)
        print(f"Saved index to {args.output}")

    print(f"Indexed {count} documents, {len(index.inverted)} unique terms")


def cmd_search(args):
    """搜索"""
    index = load_index(args.index) if args.index else _create_sample_index()
    searcher = Searcher(index)

    mode = 'boolean' if args.boolean else 'ranking'

    results = searcher.search(args.query, top_k=args.top_k, mode=mode)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"Query: {args.query}")
        print(f"Mode: {mode}")
        print(f"Results: {len(results)}")
        print("-" * 60)
        for r in results:
            print(f"[{r['doc_id']}] {r.get('title', '')} (score: {r['score']})")
            if r.get('snippet'):
                print(f"  {r['snippet']}")
            print()


def _create_sample_index():
    """创建示例索引"""
    index = InvertedIndex()
    samples = [
        ('1', 'Python Tutorial',
         'Python is a programming language. Learn Python for data science and web development.'),
        ('2', 'Machine Learning Guide',
         'Machine learning is a subset of artificial intelligence. Deep learning and neural networks.'),
        ('3', 'Data Science Basics',
         'Data science involves statistics, machine learning, and data analysis. Python is widely used.'),
        ('4', 'Deep Learning Tutorial',
         'Deep learning uses neural networks with many layers. It is a subset of machine learning.'),
        ('5', 'Web Development with Python',
         'Build web applications using Python frameworks like Django and Flask.'),
    ]
    for doc_id, title, body in samples:
        index.add_document(doc_id, title=title, body=body)
    return index


def main():
    parser = argparse.ArgumentParser(description='Search Engine CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # index 命令
    index_parser = subparsers.add_parser('index', help='Build index from file')
    index_parser.add_argument('file', type=argparse.FileType('r', encoding='utf-8'),
                              help='TSV file (doc_id\\ttitle\\tbody)')
    index_parser.add_argument('-o', '--output', default='index.json',
                              help='Output index file (default: index.json)')

    # search 命令
    search_parser = subparsers.add_parser('search', help='Search indexed documents')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('-i', '--index', default='',
                               help='Index file (default: sample index)')
    search_parser.add_argument('-k', '--top-k', type=int, default=10,
                               help='Top K results (default: 10)')
    search_parser.add_argument('--boolean', action='store_true',
                               help='Use boolean search mode')
    search_parser.add_argument('--json', action='store_true',
                               help='Output as JSON')

    # serve 命令
    serve_parser = subparsers.add_parser('serve', help='Start HTTP server')
    serve_parser.add_argument('--host', default='localhost', help='Host (default: localhost)')
    serve_parser.add_argument('--port', type=int, default=8000, help='Port (default: 8000)')

    args = parser.parse_args()

    if args.command == 'index':
        cmd_index(args)
    elif args.command == 'search':
        cmd_search(args)
    elif args.command == 'serve':
        from server import run_server
        run_server(host=args.host, port=args.port)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
