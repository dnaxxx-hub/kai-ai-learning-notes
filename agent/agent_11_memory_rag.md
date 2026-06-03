# Agent 记忆系统

## 1. 短期记忆（对话历史）

### 滑动窗口实现
```python
class ShortTermMemory:
    def __init__(self, max_tokens=4096):
        self.messages = []
        self.max_tokens = max_tokens
    
    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self._trim()
    
    def _trim(self):
        """超出窗口时丢弃最早的对话"""
        total = sum(self._count_tokens(m) for m in self.messages)
        while total > self.max_tokens and len(self.messages) > 2:
            removed = self.messages.pop(0)
            total -= self._count_tokens(removed)
    
    def _count_tokens(self, msg):
        return len(msg["content"]) // 2  # 粗略估算
    
    def get_context(self) -> list:
        return self.messages
```

### 总结压缩
```python
def summarize_history(messages: list) -> str:
    """当窗口满时，压缩历史为摘要"""
    full_text = "\n".join(m["content"] for m in messages)
    summary = llm.invoke(f"压缩以下对话为关键信息摘要：\n{full_text}")
    return summary
```

## 2. 长期记忆（向量存储）

### 架构
```
短期记忆（对话缓冲） → 达到阈值 → 总结/压缩 → 写入长期记忆（向量库）
长期记忆 → 检索相关片段 → 注入短期记忆上下文
```

### QA 摘要存储
```python
class LongTermMemory:
    def __init__(self):
        self.vector_store = Chroma(embedding_function=embeddings)
        self.summary_store = {}
    
    def store_interaction(self, query: str, response: str):
        """存储问答对为向量"""
        # 1. 生成摘要
        summary = llm.invoke(f"总结以下对话：Q:{query} A:{response}")
        
        # 2. 向量化存储（原始问答 + 摘要）
        self.vector_store.add_texts(
            texts=[f"Q: {query}\nA: {response}", summary],
            metadatas=[{"type": "qa"}, {"type": "summary"}]
        )
    
    def recall(self, query: str, k=3):
        """检索相关记忆"""
        docs = self.vector_store.similarity_search(query, k=k)
        return "\n\n".join(d.page_content for d in docs)
```

## 3. 工作记忆（任务上下文）

```python
class WorkingMemory:
    """类似人类的工作记忆——当前正在处理的任务状态"""
    def __init__(self):
        self.current_task = None
        self.subtasks = []
        self.context = {}       # 当前上下文变量
        self.state = "idle"     # idle / processing / paused
        self.stack = []         # 调用栈
    
    def push_context(self, task: str, variables: dict):
        self.stack.append({
            "task": self.current_task,
            "context": self.context.copy()
        })
        self.current_task = task
        self.context.update(variables)
    
    def pop_context(self):
        prev = self.stack.pop()
        self.current_task = prev["task"]
        self.context = prev["context"]
```

## 4. RAG 深度技术

### 分块策略对比
```python
# 语义分块（优于固定大小）
from langchain.text_splitter import SemanticChunker

semantic_splitter = SemanticChunker(
    embeddings=embeddings,
    breakpoint_threshold_type="percentile"  # / standard / gradient
)

# 递归字符分块（推荐）
recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=128,
    separators=["\n\n", "\n", "。", ".", "!", "?", " ", ""]
)
```

### Multi-Query 检索
```python
def multi_query_retrieval(query: str, k=3):
    """生成多个角度的查询以提升召回"""
    queries = llm.invoke(
        f"为以下问题生成3个不同角度的检索查询：{query}"
    ).split("\n")
    
    all_docs = []
    for q in [query] + queries:
        docs = vectorstore.similarity_search(q, k=k)
        all_docs.extend(docs)
    
    # 去重后返回
    seen = set()
    unique_docs = []
    for d in all_docs:
        if d.page_content not in seen:
            seen.add(d.page_content)
            unique_docs.append(d)
    return unique_docs[:k]
```

### HyDE（假设文档嵌入）
```python
def hyde_retrieval(query: str, k=3):
    """先生成假设文档，再用假设文档去检索"""
    hypothetical_doc = llm.invoke(
        f"请写出一个能完美回答以下问题的文档片段：{query}"
    )
    # 用假设文档的嵌入去检索
    return vectorstore.similarity_search(hypothetical_doc, k=k)
```

## 5. 记忆压缩与遗忘

```python
class MemoryManager:
    def __init__(self):
        self.memories = []
        self.importance_threshold = 0.5
    
    async def consolidate(self):
        """定期压缩记忆"""
        old_memories = [m for m in self.memories 
                       if m.age > 7 and m.importance < 0.3]
        
        # 遗忘（删除低频低重要性记忆）
        for m in old_memories:
            self.memories.remove(m)
        
        # 合并相似记忆
        clusters = self._cluster_memories(self.memories)
        for cluster in clusters:
            if len(cluster) > 3:
                merged = self._merge(cluster)
                for m in cluster:
                    self.memories.remove(m)
                self.memories.append(merged)
    
    def _cluster_memories(self, memories):
        """向量聚类"""
        texts = [m.content for m in memories]
        vectors = embeddings.embed_documents(texts)
        return self._kmeans(vectors, k=len(texts)//3)
```

## 记忆系统完整架构

```
用户输入
    │
    ▼
┌─────────────┐
│ 工作记忆    │ ← 当前任务上下文、调用栈
│ (Working)   │
└──────┬──────┘
       │
┌──────▼──────┐
│ 短期记忆    │ ← 滑动窗口对话历史
│ (Short-Term)│
└──────┬──────┘
       │ 窗口满时压缩
       ▼
┌─────────────┐
│ 长期记忆    │ ← 向量库 + 摘要存储
│ (Long-Term) │
│  + RAG      │
└─────────────┘
```

## 总结
记忆系统是 Agent 从"无状态调用"进化到"有状态智能体"的关键。短期记忆负责即时对话、长期记忆提供知识沉淀、工作记忆追踪任务状态。配合 RAG 的 Multi-query 和 HyDE 技术，能显著提升检索质量。记忆压缩和遗忘机制则防止无限膨胀。
