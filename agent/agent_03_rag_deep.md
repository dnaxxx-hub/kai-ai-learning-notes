# AI Agent #3：RAG 深度 — 检索增强生成

> 2026-05-17
> 前置知识：Agent 工具调用（#2）、Embedding 基础

## RAG 基本流程

```
用户查询
    ↓
[Embedding] → 向量检索
    ↓              ─── 知识库
[相关文档] ← ┘
    ↓
[LLM 生成] → 最终回答
```

## 四个关键设计维度

### 1. 分块策略（Chunking）

| 策略 | 方法 | 适用场景 | 经验值 |
|:----|:----|:--------|:------|
| 固定长度 | 按 token 数切 | 通用文档 | 256-1024 tokens |
| 语义分块 | 按段落/标题切 | 技术文档 | 跟标题层级走 |
| 递归分块 | 从大到小递归切 | 长文档 | LangChain 默认 1000/200 |
| 滑动窗口 | 重叠分块 | 需要上下文的问答 | 重叠 10-20% |

**代码片段**：
```python
def recursive_chunk(text, max_tokens=500, overlap=50):
    """递归分块：先按 ## 标题切，超长再按段落切"""
    sections = re.split(r'(?=^#{2,3} )', text, flags=re.MULTILINE)
    chunks = []
    for sec in sections:
        tokens = count_tokens(sec)
        if tokens <= max_tokens:
            chunks.append(sec)
        else:
            # 继续按段落细分
            paras = sec.split('\n\n')
            # 合并到 max_tokens
    return chunks
```

### 2. Embedding 选择

| 模型 | 维度 | 适合 | 我们用的 |
|:----|:---:|:----|:--------|
| nomic-embed-text | 768 | 通用，本地运行 | ✅ 已配置 |
| text-embedding-3-small | 1536 | 生产级精度 | API需联网 |
| bge-large-zh | 1024 | 中文场景 | 可选 |

**nomic-embed-text 本地经验**：
- 模型文件：nomic-embed-text-v1.5.Q8_0.gguf（~66MB）
- 延迟：5-15ms 每查询（CPU）
- 效果：技术文档检索足够好
- `openclaw memory status --deep` 验证生效

### 3. 检索策略

#### 基础检索
```python
from sklearn.metrics.pairwise import cosine_similarity

def basic_retrieve(query_emb, all_embs, top_k=5):
    scores = cosine_similarity([query_emb], all_embs)[0]
    top_indices = scores.argsort()[-top_k:][::-1]
    return top_indices, scores[top_indices]
```

#### 混合检索
```
向量检索（语义匹配） + 关键词检索（精确匹配）
```

混合检索显著优于纯向量检索，尤其是在代码和技术术语场景。

#### 重排序（Reranking）
```
向量检索返回 Top-50 → 交叉编码器重排序 → Top-5
```
交叉编码器相比双编码器慢但精度更高。在本地资源受限时，可以跳过多做一轮过滤。

### 4. 上下文管理

**核心问题**：LLM 上下文窗口有限（<ctx>nomic-embed-text</ctx>）。

**解决方案**：

```
┌─────────────────────────────────────┐
│          LLM 输入                    │
├─────────────────────────────────────┤
│ 系统提示（固定）       ~500 tokens   │
│ 检索文档 1            ~500 tokens   │
│ 检索文档 2            ~500 tokens   │
│ ...                                  │
│ 用户查询              ~50 tokens    │
├─────────────────────────────────────┤
│ 总计限制：约 4K tokens（本地模型）     │
└─────────────────────────────────────┘
```

- 优先放入相关性最高的文档
- 如果文档太长，只放包含匹配句子的段落
- 记忆中的已有上下文优先于新检索

## 我们系统的 RAG 实现

在我们的知识系统中，RAG 三环记忆检索架构：

```
用户查询
    ↓
① 记忆检索（memory_search）
   → MEMORY.md + memory/*.md
   → 语义搜索 + keyword搜索
   → 返回 top snippets + path + lines
    ↓
② 精确读取（memory_get）
   → 从匹配文件拉取需要的行
   → 保持上下文精简
    ↓
③ LLM 回答生成
```

**关键观察**：
- Semantic search 返回相关性高但有时遗漏精确术语 → 混合搜索更好
- `path + lines` 指向引用非常重要 → 可信来源
- 只拉取需要的行，不拉整个文件 → 节省 token

## 进阶技巧

1. **Query 重写**：把"它"替换为明确指代 → "Python的GIL是什么"
2. **HyDE（Hypothetical Document Embeddings）**：先让LLM生成假设回答，用这个假设回答去检索
3. **RAG-Fusion**：多次检索 → 融合结果 → 去重 → 重排序
4. **Self-RAG**：LLM自己判断是否需要检索、检索结果是否相关

## 参考

- "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (Lewis et al., 2020)
- "Lost in the Middle: How Language Models Use Long Contexts" (Liu et al., 2023)
- LangChain RAG 文档
