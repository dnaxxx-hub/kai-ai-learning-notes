# LLM推理编排网关 — 深度实战笔记

> 日期：2026-05-28 11:30
> 项目：`projects/llm_gateway/`
> 依赖：python-flow-engine + Ollama (本地) + 5070Ti GPU

---

## 1. 系统架构

### 1.1 组件

| 组件 | 文件 | 行数 | 职责 |
|------|------|:----:|------|
| OllamaClient | `ollama_client.py` | 294 | Ollama API封装：流式/非流式/重试/超时 |
| LLMNode | `llm_nodes.py` | 442 | Pipeline节点，包装单个模型调用 |
| ReviewChain | `llm_nodes.py` | — | 3级串行：生成→审查→改进 |
| ModelComparison | `llm_nodes.py` | — | 多模型并行回答→汇总对比 |
| RouterNode | `llm_nodes.py` | — | 条件路由：短文本→小模型,长文本→大模型 |
| LLMGateway | `gateway.py` | 172 | 高级接口，3个场景一键调用 |

### 1.2 三种编排模式

**1. 串行 (Serial) — ReviewChain**
```
qwen3.5 (生成代码) >> gemma3 (审查质量) >> deepseek-r1 (改进建议)
```
每个节点输出传递给下一个节点作为输入。

**2. 并行 (Parallel) — ModelComparison**
```
deepseek-r1 ----\
                  --> gemma3 (汇总对比)
qwen3.5 ---------/
```
两个模型通过 `//` 并行执行，输出合并后由汇总模型分析。

**3. 条件路由 (Conditional) — RouterNode**
```
输入 --> RouterNode --[short]--> qwen3.5 (摘要)
                     --[long]--> gemma3 (详细分析)
```
RouterNode 检查内容长度，使用 `connect(..., condition=...)` 路由。

---

## 2. 关键技术实现

### 2.1 OllamaClient 封装

```python
class OllamaClient:
    def generate(self, model, prompt, system=None, stream=False,
                 num_predict=512, temperature=0.7):
        # POST to http://localhost:11434/api/generate
        # Returns: {"response": str, "eval_count": int,
        #           "total_duration_ns": int}
```

关键设计：
- 使用 `requests.Session` 复用连接
- 指数退避重试（base 1s, 2x）
- 流式/非流式统一接口
- 支持 `system` 和 `thinking` 字段（deepseek-r1 思维链）

### 2.2 LLMNode — Pipeline + LLM 桥接

```python
class LLMNode(Node):
    def __init__(self, model, prompt_template, ...):
        super().__init__(fn=self._call_ollama, ...)

    def _call_ollama(self, context, data):
        prompt = self.prompt_template.format(input=data)
        result = get_client().generate(self.model, prompt)
        # 记录到 context["llm_calls"] 供下游使用
        return result["response"]
```

关键发现：
- Pipeline 的 data 参数在前序节点执行后会被覆写
- LLM 输出通过 `context` 共享（`context["llm_calls"]`）
- 每个 LLMNode 调用耗时 ~10-60s（取决于模型和 GPU 负载）

### 2.3 数据传递策略

ReviewChain 的数据流：
1. Generator 接收原始 prompt，输出代码/内容
2. Reviewer 接收 generator 的输出作为 input
3. Improver 接收 reviewer 的输出作为 input
4. 全部通过 `>>` 操作符保证顺序

ModelComparison 的数据流：
1. 同一个 question 输入给两个模型节点
2. `//` 让两者并行执行
3. 各自输出累积在 context
4. Comparator 节点作为串行后继接收最后一个节点的输出和 context

### 2.4 RouterNode 条件路由

```python
class RouterNode(Node):
    def _route_fn(self, context, data):
        length = len(str(data))
        context["route"] = "short" if length < 200 else "long"
        return data

# 条件函数
def short_text_condition(ctx, data): return ctx.get("route") == "short"
def long_text_condition(ctx, data): return ctx.get("route") == "long"

# 连接
pipe.connect(router, small_model, "conditional", condition=short_text_condition)
```

---

## 3. 可用模型

| 模型 | 大小 | 用途 | 延迟 |
|------|:----:|------|:----:|
| qwen3.5:9b | 6.6GB | 通用生成/摘要 | ~10-20s |
| deepseek-r1:8b | 5.2GB | 推理/审查/CoT | ~20-40s |
| gemma3:12b | 8.1GB | 高质生成/汇总 | ~15-30s |
| gemma4:latest | 9.6GB | — | — |
| gemma4:26b | 17GB | — | — |

---

## 4. 实战收获

### 4.1 Pipeline 编排 LLM 的适配模式

1. **LLM 节点天然适合串行**：前序输出 = 后序输入
2. **并行加速效果有限**：因为 GPU 显存限制，多个模型无法真正同时运行
3. **条件路由适合节约资源**：简单任务用小模型，复杂任务用大模型
4. **Context 是 LLM 编排的核心**：记录调用链、耗时、Token 用量

### 4.2 SSL/Ollama 连接注意事项

- Ollama API 使用纯 HTTP（localhost），无需 SSL
- `requests` 默认超时 60s，需手动调大（模型推理可达 120s）
- 流式模式（stream=True）可实时看到 token 输出，但非流式更简单可靠

### 4.3 改进空间

1. **真正的并行**：多 GPU 或多实例才能实现真正并行
2. **缓存机制**：相同 prompt 命中缓存省去推理
3. **Token 预算管理**：cost limit / max total tokens
4. **模型 fallback**：大模型超时自动降级到小模型
5. **结构化输出**：强制 JSON Schema 输出

---

## 5. 目录结构

```
projects/llm_gateway/
├── ollama_client.py    # Ollama API 封装 (~300行)
├── llm_nodes.py        # Pipeline 节点定义 (~450行)
├── gateway.py          # 高级编排网关 (~170行)
├── demo.py             # 3个场景测试 (~270行)
└── _test_*.py          # 测试脚本
```

## 6. 运行

```bash
# Ollama 必须运行中
cd projects/llm_gateway
python demo.py          # 完整演示（需要等待推理完成）
python _test_single.py   # 单次模型调用测试
python _test_chain.py    # 串行链测试
python _test_parallel.py # 并行对比测试
```
## 关键发现：思考模型 vs 直接输出模型

测试验证（2026-05-28 11:40）：

| 模型 | 类型 | 响应字段 | 延迟(50token) | 说明 |
|------|------|:--------:|:------------:|------|
| gemma3:12b | 直接输出 | response | **1.65s** | 无thinking字段, response直接填充 |
| qwen3.5:9b | 思维链 | thinking | **11.45s** | thinking字段先填满, 完成思考后填充response |
| deepseek-r1:8b | 思维链 | thinking | ~15-20s | 类似qwen3.5 |

**解决方案**：
- ollama_client.py 增加思维链检测：response为空但有thinking时从thinking提取最后一行
- 思考模型需要足够大的 num_predict (>=1024) 才能完成"思考+输出"两个阶段
- 非思考模型（gemma3）响应稳定可靠，适合 Pipeline 快速编排
- 推理延迟瓶颈在GPU推理时间（5070Ti），不在Pipeline路由开销（<5ms）
