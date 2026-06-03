# Ollama 本地 Agent 落地实战

## 1. 环境搭建与模型运行

### Ollama 基础使用
```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 拉取并运行模型
ollama pull deepseek-r1:7b    # 深度求索 R1（含思维链）
ollama pull qwen2.5:7b       # 通义千问 2.5
ollama pull llama3.2:3b      # Meta LLaMA 3.2（轻量）

# 运行交互式对话
ollama run deepseek-r1:7b
```

### API 接口
Ollama 提供原生 REST API，默认 `http://localhost:11434`：
```python
import requests

response = requests.post("http://localhost:11434/api/chat", json={
    "model": "deepseek-r1:7b",
    "messages": [{"role": "user", "content": "什么是 Agent？"}],
    "stream": False
})
print(response.json()["message"]["content"])
```

## 2. LangChain 集成

```python
from langchain_ollama import ChatOllama
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool
from langchain.prompts import PromptTemplate

# 初始化模型
llm = ChatOllama(
    model="qwen2.5:7b",
    temperature=0.7,
    num_predict=4096
)

# 定义工具
@tool
def calculate(expr: str) -> str:
    """计算数学表达式"""
    return str(eval(expr))

# 创建 ReAct Agent
agent = create_react_agent(llm, [calculate], PromptTemplate(...))
executor = AgentExecutor(agent=agent, tools=[calculate])
result = executor.invoke({"input": "计算 3.14 * 2.5 的结果"})
```

## 3. Function Calling 工具调用

Ollama 支持原生工具调用（部分模型）：

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "获取天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"}
            },
            "required": ["city"]
        }
    }
}]

response = requests.post("http://localhost:11434/api/chat", json={
    "model": "qwen2.5:7b",
    "messages": [{"role": "user", "content": "北京天气如何？"}],
    "tools": tools,
    "stream": False
})
```

## 4. ReAct 循环实现

### 手动 ReAct 循环
```python
MAX_ITERATIONS = 5

def react_loop(query: str, tools: dict):
    messages = [{"role": "user", "content": query}]
    
    for i in range(MAX_ITERATIONS):
        # 思考步骤
        response = llm.invoke(messages + [{"role": "system", 
            "content": "逐步思考：Thought → Action → Observation → Final Answer"}])
        messages.append({"role": "assistant", "content": response.content})
        
        # 提取行动
        if "Final Answer:" in response.content:
            return response.content.split("Final Answer:")[-1].strip()
        
        # 执行工具
        action = parse_action(response.content)  # 自定义解析
        if action and action["name"] in tools:
            obs = tools[action["name"]](**action["args"])
            messages.append({"role": "tool", "content": str(obs)})
    
    return "达到最大迭代次数"
```

## 5. 本地知识库 RAG

### 文档分块 (Chunking)
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=128,
    separators=["\n\n", "\n", "。", ".", " "]
)
chunks = splitter.split_text(document)
```

### 向量化与检索
```python
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

embeddings = OllamaEmbeddings(model="nomic-embed-text")
vectorstore = Chroma.from_texts(
    texts=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db"
)

# 检索
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
docs = retriever.invoke("什么是 Agent？")
```

### RAG 完整流程
```python
def rag_query(query: str) -> str:
    docs = retriever.invoke(query)
    context = "\n\n".join([d.page_content for d in docs])
    
    prompt = f"""基于以下上下文回答问题：
{context}

问题：{query}"""
    return llm.invoke(prompt).content
```

## 6. 多模型切换

```python
MODEL_REGISTRY = {
    "deepseek": ChatOllama(model="deepseek-r1:7b", temperature=0.3),
    "qwen": ChatOllama(model="qwen2.5:7b", temperature=0.7),
    "llama": ChatOllama(model="llama3.2:3b"),
    "embed": OllamaEmbeddings(model="nomic-embed-text"),
}

def switch_model(task: str):
    """根据任务类型自动切换模型"""
    if task in ["math", "logic"]:
        return MODEL_REGISTRY["deepseek"]  # 推理强
    elif task in ["creative", "chat"]:
        return MODEL_REGISTRY["qwen"]      # 对话强
    else:
        return MODEL_REGISTRY["llama"]     # 通用轻量
```

## 总结
Ollama 让本地 LLM 部署变得前所未有的简单。结合 LangChain 的 Agent 框架和向量数据库，可以在消费级硬件上构建完整的本地 AI Agent 系统，实现数据隐私保护下的智能化应用。
