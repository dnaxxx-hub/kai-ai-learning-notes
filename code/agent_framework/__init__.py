"""
Multi-Agent Collaboration Framework
====================================
A lightweight, zero-dependency multi-agent framework in pure Python.

Modules:
- core: Agent base class + tool registration system
- memory: Conversation memory + TF-IDF vector memory
- orchestrator: Multi-agent coordination core
- agents: Practical agent implementations
"""

from .core import (
    BaseAgent,
    ToolRegistry,
    ToolDef,
    AgentContext,
    LLMInterface,
    MockLLM,
    tool,
)
from .memory import (
    MemorySystem,
    ConversationMemory,
    TFIDFVectorMemory,
    MemoryItem,
)
from .orchestrator import (
    Orchestrator,
    MessageBus,
    AgentNode,
    AgentMessage,
    CollaborationMode,
    Task,
)
from .agents.coding_agent import CodingAgent, create_coding_agent
from .agents.search_agent import SearchAgent, create_search_agent
from .agents.analysis_agent import AnalysisAgent, create_analysis_agent

__version__ = "0.1.0"
__all__ = [
    # Core
    "BaseAgent", "ToolRegistry", "ToolDef", "AgentContext",
    "LLMInterface", "MockLLM", "tool",
    # Memory
    "MemorySystem", "ConversationMemory", "TFIDFVectorMemory", "MemoryItem",
    # Orchestrator
    "Orchestrator", "MessageBus", "AgentNode", "AgentMessage",
    "CollaborationMode", "Task",
    # Agents
    "CodingAgent", "SearchAgent", "AnalysisAgent",
    "create_coding_agent", "create_search_agent", "create_analysis_agent",
]
