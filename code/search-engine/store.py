"""store.py — 索引存储（JSON 序列化）"""

import json


def save_index(index, filepath):
    """将倒排索引保存为 JSON 文件"""
    data = {
        'documents': index.documents,
        'doc_count': index.doc_count,
        'inverted': {term: {str(did): freq for did, freq in postings.items()}
                     for term, postings in index.inverted.items()},
        'doc_lengths': {str(did): length for did, length in index.doc_lengths.items()},
    }
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_index(filepath, analyzer=None):
    """从 JSON 文件加载倒排索引"""
    from indexer import InvertedIndex
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    idx = InvertedIndex(analyzer)
    idx.documents = {did: doc for did, doc in data['documents'].items()}
    idx.doc_count = data['doc_count']
    idx.inverted = {term: {did: freq for did, freq in postings.items()}
                    for term, postings in data['inverted'].items()}
    idx.doc_lengths = {did: length for did, length in data['doc_lengths'].items()}
    return idx
