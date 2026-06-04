"""
orchestrator.py — 多Agent协调核心
===================================
支持:
- Agent 间消息传递
- 任务委派与结果聚合
- 三种协作模式: 主管-工人 / 对等 / 辩论

类比 AutoGen 的 GroupChat 和 CrewAI 的 Process。
"""

from __future__ import annotations
import json
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from enum import Enum

from .core import BaseAgent, AgentContext, JSON


# ─── 消息 ─────────────────────────────────────────────────

@dataclass
class AgentMessage:
    """Agent 间传递的消息"""
    sender: str
    recipient: str  # "*" 表示广播
    content: Any
    msg_type: str = "text"  # text / tool_call / result / error
    msg_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.msg_id:
            self.msg_id = f"msg_{int(self.timestamp * 1000)}_{hash(self.sender + self.recipient) % 10000}"


# ─── 协作模式 ─────────────────────────────────────────────

class CollaborationMode(Enum):
    """协作模式"""
    ORCHESTRATOR_WORKERS = "orchestrator_workers"  # 主管-工人
    PEER_TO_PEER = "peer_to_peer"                  # 对等
    DEBATE = "debate"                              # 辩论


# ─── Agent 节点 ───────────────────────────────────────────

@dataclass
class AgentNode:
    """Agent 节点——包装 BaseAgent 使其可参与协作"""
    agent: BaseAgent
    role: str  # "orchestrator" | "worker" | "peer" | "debater"
    capabilities: List[str] = field(default_factory=list)
    max_concurrent_tasks: int = 3

    def handle_message(self, msg: AgentMessage) -> AgentMessage:
        """处理收到的消息并返回响应"""
        if msg.msg_type == "task":
            # 收到任务→执行
            result = self.agent.run(str(msg.content))
            last_msg = result.messages[-1] if result.messages else ""
            return AgentMessage(
                sender=self.agent.name,
                recipient=msg.sender,
                content=last_msg.get("content", str(last_msg)) if isinstance(last_msg, dict) else str(last_msg),
                msg_type="result",
                metadata={"context": result},
            )
        elif msg.msg_type == "query":
            response = self.agent.run(str(msg.content))
            last_msg = response.messages[-1] if response.messages else ""
            return AgentMessage(
                sender=self.agent.name,
                recipient=msg.sender,
                content=last_msg.get("content", str(last_msg)) if isinstance(last_msg, dict) else str(last_msg),
                msg_type="result",
            )
        return AgentMessage(
            sender=self.agent.name,
            recipient=msg.sender,
            content=f"Unknown message type: {msg.msg_type}",
            msg_type="error",
        )


# ─── 消息总线 ─────────────────────────────────────────────

class MessageBus:
    """
    消息总线——Agent 间的通信中枢。
    支持点对点、广播、订阅模式。
    """

    def __init__(self):
        self._agents: Dict[str, AgentNode] = {}
        self._message_log: List[AgentMessage] = []
        self._max_log = 1000
        self._lock = threading.Lock()

    def register(self, node: AgentNode):
        """注册 Agent 节点到总线"""
        self._agents[node.agent.name] = node

    def unregister(self, name: str):
        """从总线注销"""
        self._agents.pop(name, None)

    def send(self, msg: AgentMessage) -> Optional[AgentMessage]:
        """
        发送消息。
        - 如果 recipient="*"，广播给所有 Agent
        - 如果指定 recipient，点对点发送
        - 返回响应（如果有）
        """
        with self._lock:
            self._message_log.append(msg)
            if len(self._message_log) > self._max_log:
                self._message_log = self._message_log[-self._max_log:]

        if msg.recipient == "*":
            # 广播
            responses = []
            for name, node in self._agents.items():
                if name != msg.sender:
                    resp = node.handle_message(msg)
                    responses.append(resp)
            return responses[0] if responses else None
        else:
            # 点对点
            node = self._agents.get(msg.recipient)
            if node is None:
                return AgentMessage(
                    sender="bus",
                    recipient=msg.sender,
                    content=f"Agent '{msg.recipient}' not found",
                    msg_type="error",
                )
            return node.handle_message(msg)

    def broadcast(self, msg: AgentMessage) -> List[AgentMessage]:
        """广播消息给所有 Agent（自己除外）"""
        msg.recipient = "*"
        responses = []
        for name, node in self._agents.items():
            if name != msg.sender:
                resp = node.handle_message(msg)
                responses.append(resp)
        return responses

    def get_message_log(self, last_n: int = 10) -> List[AgentMessage]:
        """获取最近的消息记录"""
        return self._message_log[-last_n:]

    @property
    def agent_names(self) -> List[str]:
        return list(self._agents.keys())


# ─── 协调器 ───────────────────────────────────────────────

@dataclass
class Task:
    """一个可委派的子任务"""
    id: str
    description: str
    assigned_to: Optional[str] = None
    result: Optional[Any] = None
    status: str = "pending"  # pending / running / completed / failed
    priority: int = 5


class Orchestrator:
    """
    多Agent 协调核心。

    支持三种协作模式:
    1. ORCHESTRATOR_WORKERS: 主管分配任务给工人
    2. PEER_TO_PEER: Agent 自由通信与合作
    3. DEBATE: 多个 Agent 独立分析后汇总
    """

    def __init__(self, bus: Optional[MessageBus] = None):
        self.bus = bus or MessageBus()
        self.mode = CollaborationMode.ORCHESTRATOR_WORKERS

    def add_agent(self, agent: BaseAgent, role: str = "worker",
                  capabilities: Optional[List[str]] = None):
        """添加 Agent 到协作网络"""
        node = AgentNode(
            agent=agent,
            role=role,
            capabilities=capabilities or [],
        )
        self.bus.register(node)

    # ── 模式 1: 主管-工人 ───────────────────────────────

    def orchestrator_workers(
        self,
        orchestrator_agent: BaseAgent,
        query: str,
    ) -> Dict[str, Any]:
        """
        主管-工人模式：
        1. 主管（orchestrator）分析任务并拆解
        2. 分配给合适的工人 Agent
        3. 收集结果并聚合
        """
        workers = [
            n for n in self.bus._agents.values()
            if n.role == "worker"
        ]

        if not workers:
            return {"error": "No worker agents available"}

        # 主管制定计划
        plan_prompt = (
            f"你是一个协调主管。用户请求: {query}\n"
            f"可用工人: {[w.agent.name for w in workers]}\n"
            f"请将任务拆解为子任务，每个子任务分配给最适合的工人。"
        )
        plan_result = orchestrator_agent.run(plan_prompt)

        # 委派子任务给工人
        tasks: List[Task] = []
        for i, worker in enumerate(workers):
            task = Task(
                id=f"task_{i}",
                description=f"Part of: {query}",
                assigned_to=worker.agent.name,
                status="running",
            )
            tasks.append(task)

        # 并行执行（顺序执行，因为是在同步环境中）
        results = {}
        for task in tasks:
            msg = AgentMessage(
                sender=orchestrator_agent.name,
                recipient=task.assigned_to,
                content=task.description,
                msg_type="task",
            )
            response = self.bus.send(msg)
            if response:
                task.result = response.content
                task.status = "completed"
                results[task.assigned_to] = response.content
            else:
                task.status = "failed"
                results[task.assigned_to] = "No response"

        # 聚合结果
        aggregate_prompt = (
            f"原始请求: {query}\n\n"
            f"子任务结果:\n"
            + "\n".join(f"[{k}]: {v}" for k, v in results.items())
            + "\n\n请汇总这些结果为用户生成一个完整的回答。"
        )
        final_result = orchestrator_agent.run(aggregate_prompt)
        last_msg = final_result.messages[-1] if final_result.messages else {}

        return {
            "tasks": [
                {"id": t.id, "assigned_to": t.assigned_to, "status": t.status}
                for t in tasks
            ],
            "results": results,
            "final_answer": last_msg.get("content", str(last_msg)) if isinstance(last_msg, dict) else str(last_msg),
        }

    # ── 模式 2: 对等方式 ───────────────────────────────

    def peer_to_peer(self, initiator: str, query: str) -> List[AgentMessage]:
        """
        对等方式：
        发起者发送查询，所有 peer Agent 自由响应。
        """
        msg = AgentMessage(
            sender=initiator,
            recipient="*",
            content=query,
            msg_type="query",
        )
        return self.bus.broadcast(msg)

    # ── 模式 3: 辩论模式 ───────────────────────────────

    def debate(
        self,
        debaters: List[BaseAgent],
        arbiter: BaseAgent,
        query: str,
    ) -> Dict[str, Any]:
        """
        辩论模式：
        1. 多个辩论者独立分析并给出观点
        2. 辩论者之间互评
        3. 仲裁者综合所有观点给出最终结论
        """
        # Round 1: 独立分析
        opinions = {}
        for agent in debaters:
            result = agent.run(f"请分析以下问题，给出你的观点和论据:\n{query}")
            last_msg = result.messages[-1] if result.messages else {}
            opinions[agent.name] = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)

        # Round 2: 互评（简单版本）
        critiques = {}
        for name, opinion in opinions.items():
            other_opinions = {k: v for k, v in opinions.items() if k != name}
            critique_prompt = (
                f"你的观点: {opinion}\n\n"
                f"其他人的观点:\n"
                + "\n".join(f"[{k}]: {v[:200]}" for k, v in other_opinions.items())
                + "\n\n请分析其他人的观点，指出你同意和不同意的地方。"
            )
            # 用第一个辩论者模拟互评
            critique_result = debaters[0].run(critique_prompt)
            last_msg = critique_result.messages[-1] if critique_result.messages else {}
            critiques[name] = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)

        # Round 3: 仲裁
        arbiter_prompt = (
            f"原始问题: {query}\n\n"
            f"各方观点:\n"
            + "\n".join(f"[{k}]: {v[:500]}" for k, v in opinions.items())
            + "\n\n互评摘要:\n"
            + "\n".join(f"[{k}]: {v[:200]}" for k, v in critiques.items())
            + "\n\n作为仲裁者，请综合分析所有观点并给出最终结论。"
        )
        final_result = arbiter.run(arbiter_prompt)
        last_msg = final_result.messages[-1] if final_result.messages else {}

        return {
            "opinions": opinions,
            "critiques": critiques,
            "final_verdict": last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg),
        }

    # ── 自动模式选择 ───────────────────────────────────

    def run(self, query: str, mode: Optional[CollaborationMode] = None,
            orchestrator_agent: Optional[BaseAgent] = None,
            debaters: Optional[List[BaseAgent]] = None,
            arbiter: Optional[BaseAgent] = None) -> Dict[str, Any]:
        """
        自动运行指定的协作模式。
        """
        effective_mode = mode or self.mode

        if effective_mode == CollaborationMode.ORCHESTRATOR_WORKERS:
            if orchestrator_agent is None:
                return {"error": "orchestrator_agent required for this mode"}
            return self.orchestrator_workers(orchestrator_agent, query)

        elif effective_mode == CollaborationMode.PEER_TO_PEER:
            initiator = list(self.bus._agents.keys())[0] if self.bus._agents else "unknown"
            responses = self.peer_to_peer(initiator, query)
            return {
                "mode": "peer_to_peer",
                "responses": [
                    {"from": r.sender, "content": r.content[:200]}
                    for r in responses
                ],
            }

        elif effective_mode == CollaborationMode.DEBATE:
            if not debaters or arbiter is None:
                return {"error": "debaters and arbiter required for this mode"}
            return self.debate(debaters, arbiter, query)

        return {"error": f"Unknown mode: {effective_mode}"}
