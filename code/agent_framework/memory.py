"""
memory.py — 记忆模块
====================
包含:
1. 对话记忆（ConversationMemory）— 存储对话历史
2. 向量内存检索（VectorMemory）— 基于 TF-IDF 的语义检索
3. 记忆系统组合（MemorySystem）— 整合短期+长期记忆

零外部依赖实现 TF-IDF，纯 Python 3.11+
"""

from __future__ import annotations
import math
import re
import time
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


# ─── 文本预处理 ───────────────────────────────────────────

_WORD_PATTERN = re.compile(r"[a-zA-Z0-9\u4e00-\u9fff]+")


def tokenize(text: str) -> List[str]:
    """中文+英文分词——简单的基于正则的分词"""
    return [t.lower() for t in _WORD_PATTERN.findall(text) if len(t) > 1]


def compute_tf(tokens: List[str]) -> Dict[str, float]:
    """计算词频 (Term Frequency)"""
    total = len(tokens)
    if total == 0:
        return {}
    counter = Counter(tokens)
    return {word: count / total for word, count in counter.items()}


def compute_idf(documents: List[List[str]]) -> Dict[str, float]:
    """计算逆文档频率 (Inverse Document Frequency)"""
    n_docs = len(documents)
    if n_docs == 0:
        return {}
    df: Dict[str, int] = {}
    for doc in documents:
        for word in set(doc):
            df[word] = df.get(word, 0) + 1
    return {word: math.log((n_docs + 1) / (freq + 1)) + 1 for word, freq in df.items()}


def cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """计算两个向量的余弦相似度"""
    dot = 0.0
    for word, val in vec_a.items():
        if word in vec_b:
            dot += val * vec_b[word]

    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ─── 记忆条目 ─────────────────────────────────────────────

@dataclass
class MemoryItem:
    """单条记忆条目"""
    id: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 1.0  # 1-10 重要性评分

    # 内部缓存
    _tokens: List[str] = field(default_factory=list, repr=False)
    _tf_vector: Dict[str, float] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        if not self._tokens:
            self._tokens = tokenize(self.content)
            self._tf_vector = compute_tf(self._tokens)

    def tokens(self) -> List[str]:
        if not self._tokens:
            self._tokens = tokenize(self.content)
            self._tf_vector = compute_tf(self._tokens)
        return self._tokens

    def tf_vector(self) -> Dict[str, float]:
        if not self._tf_vector:
            self._tokens = tokenize(self.content)
            self._tf_vector = compute_tf(self._tokens)
        return self._tf_vector


# ─── TF-IDF 内存检索 ─────────────────────────────────────

class TFIDFVectorMemory:
    """
    基于 TF-IDF 的向量内存检索。
    零外部依赖，纯 Python 实现。

    类似 Chroma/Pinecone 的语义搜索能力，
    但完全用 TF-IDF + 余弦相似度实现。
    """

    def __init__(self):
        self._items: List[MemoryItem] = []
        self._idf: Dict[str, float] = {}
        self._dirty: bool = True

    def add(self, content: str, metadata: Optional[Dict] = None,
            importance: float = 1.0) -> MemoryItem:
        """添加一条记忆"""
        item = MemoryItem(
            id=f"mem_{int(time.time() * 1000)}_{len(self._items)}",
            content=content,
            metadata=metadata or {},
            importance=importance,
        )
        self._items.append(item)
        self._dirty = True
        return item

    def add_item(self, item: MemoryItem):
        """直接添加 MemoryItem"""
        self._items.append(item)
        self._dirty = True

    def _rebuild_idf(self):
        """重建 IDF（当有新增文档时）"""
        documents = [item.tokens() for item in self._items]
        self._idf = compute_idf(documents)
        self._dirty = False

    def _tfidf_vector(self, tf: Dict[str, float]) -> Dict[str, float]:
        """计算 TF-IDF 向量"""
        if self._dirty:
            self._rebuild_idf()
        return {word: tf_val * self._idf.get(word, 1.0)
                for word, tf_val in tf.items()}

    def search(self, query: str, top_k: int = 5,
               min_score: float = 0.0) -> List[Tuple[MemoryItem, float]]:
        """
        检索与 query 语义相关的记忆。

        参数:
            query: 查询字符串
            top_k: 返回前 k 条结果
            min_score: 最低相似度阈值

        返回:
            [(MemoryItem, score), ...] 按相似度降序
        """
        if not self._items:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        query_tf = compute_tf(query_tokens)
        query_vec = self._tfidf_vector(query_tf)

        scored: List[Tuple[MemoryItem, float]] = []
        for item in self._items:
            item_vec = self._tfidf_vector(item.tf_vector())
            score = cosine_similarity(query_vec, item_vec)

            # 重要性加权
            weighted_score = score * (item.importance / 5.0)

            if weighted_score >= min_score:
                scored.append((item, weighted_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def get_recent(self, n: int = 10) -> List[MemoryItem]:
        """获取最近的 n 条记忆"""
        items = sorted(self._items, key=lambda x: x.timestamp, reverse=True)
        return items[:n]

    def remove(self, item_id: str) -> bool:
        """删除一条记忆"""
        for i, item in enumerate(self._items):
            if item.id == item_id:
                self._items.pop(i)
                self._dirty = True
                return True
        return False

    def clear(self):
        """清空所有记忆"""
        self._items.clear()
        self._idf.clear()
        self._dirty = True

    def __len__(self) -> int:
        return len(self._items)

    def stats(self) -> Dict[str, Any]:
        """统计信息"""
        return {
            "total_items": len(self._items),
            "vocabulary_size": len(self._idf),
            "oldest": min((i.timestamp for i in self._items), default=0),
            "newest": max((i.timestamp for i in self._items), default=0),
        }


# ─── 对话记忆 ─────────────────────────────────────────────

class ConversationMemory:
    """
    对话记忆——存储和管理对话历史。
    支持滑动窗口，防止上下文溢出。
    """

    def __init__(self, max_turns: int = 50):
        self.max_turns = max_turns
        self._conversations: Dict[str, List[Dict[str, str]]] = {}

    def add_message(self, conversation_id: str, role: str, content: str):
        """添加一条消息到指定对话"""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        self._conversations[conversation_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })
        # 滑动窗口：超过最大轮数时裁剪最早的历史
        if len(self._conversations[conversation_id]) > self.max_turns * 2:
            excess = len(self._conversations[conversation_id]) - self.max_turns * 2
            self._conversations[conversation_id] = self._conversations[conversation_id][excess:]

    def get_history(self, conversation_id: str,
                    last_n: Optional[int] = None) -> List[Dict[str, str]]:
        """获取对话历史"""
        conv = self._conversations.get(conversation_id, [])
        if last_n is not None:
            return conv[-last_n:]
        return conv

    def summarize(self, conversation_id: str, llm_summarize_fn=None) -> str:
        """
        生成对话摘要。

        如果提供了 llm_summarize_fn，则用 LLM 压缩；
        否则用简单的截断摘要（保留最近 + 最早的摘要）。
        """
        conv = self._conversations.get(conversation_id, [])
        if not conv:
            return ""

        if llm_summarize_fn:
            return llm_summarize_fn(conv)

        # 简单摘要：保留开头 + 结尾若干条
        if len(conv) <= 10:
            return self._format_messages(conv)

        head = self._format_messages(conv[:3])
        tail = self._format_messages(conv[-5:])
        return f"[对话开始]\n{head}\n... (中间省略 {len(conv) - 8} 条消息) ...\n{tail}"

    def _format_messages(self, messages: List[Dict]) -> str:
        lines = []
        for m in messages:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            lines.append(f"[{role}]: {content[:200]}")
        return "\n".join(lines)

    def clear(self, conversation_id: Optional[str] = None):
        """清空指定对话或所有对话"""
        if conversation_id:
            self._conversations.pop(conversation_id, None)
        else:
            self._conversations.clear()


# ─── 综合记忆系统 ─────────────────────────────────────────

@dataclass
class MemorySystem:
    """
    综合记忆系统——整合短期（对话记忆）和长期（TF-IDF 检索）记忆。

    架构:
    ┌──────────────┐
    │  短期记忆     │ ← ConversationMemory (对话历史)
    ├──────────────┤
    │  长期记忆     │ ← TFIDFVectorMemory (语义检索)
    ├──────────────┤
    │  工作区       │ ← 当前会话状态
    └──────────────┘
    """

    short_term: ConversationMemory = field(default_factory=ConversationMemory)
    long_term: TFIDFVectorMemory = field(default_factory=TFIDFVectorMemory)
    working_memory: Dict[str, Any] = field(default_factory=dict)

    def remember_conversation(self, conv_id: str, role: str, content: str):
        """记录对话——同时存入短期和长期记忆"""
        self.short_term.add_message(conv_id, role, content)
        if len(content) > 5:  # 有意义的对话才存长期
            self.long_term.add(
                content=content,
                metadata={"conv_id": conv_id, "role": role},
                importance=1.0,
            )

    def recall(self, query: str, top_k: int = 5) -> List[Tuple[MemoryItem, float]]:
        """从长期记忆检索相关内容"""
        return self.long_term.search(query, top_k=top_k, min_score=0.05)

    def get_recent_context(self, conv_id: str, n: int = 10) -> str:
        """获取近期对话上下文作为 LLM 上下文的一部分"""
        history = self.short_term.get_history(conv_id, last_n=n)
        items = [f"{m['role']}: {m['content']}" for m in history]
        return "\n".join(items)

    def build_context(self, conv_id: str, query: str) -> str:
        """
        构建增强上下文：对话历史 + 检索到的记忆。
        这是 RAG 的基本模式——检索增强生成。
        """
        recent = self.get_recent_context(conv_id)
        retrieved = self.recall(query, top_k=3)

        parts = ["## 近期对话历史", recent]

        if retrieved:
            memories = "\n".join(
                f"- [{r[0].metadata.get('role', 'mem')}]: {r[0].content[:200]}"
                for r in retrieved
            )
            parts.append("## 相关记忆")
            parts.append(memories)

        return "\n\n".join(parts)

    def stats(self) -> Dict[str, Any]:
        return {
            "short_term_conversations": len(self.short_term._conversations),
            "long_term_items": len(self.long_term),
        }
