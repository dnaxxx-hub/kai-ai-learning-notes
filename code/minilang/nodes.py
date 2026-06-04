from dataclasses import dataclass
from typing import List, Optional

class ASTNode:
    pass

@dataclass
class Program(ASTNode):
    statements: List[ASTNode]

@dataclass
class Number(ASTNode):
    value: float | int

@dataclass
class String(ASTNode):
    value: str

@dataclass
class Boolean(ASTNode):
    value: bool

@dataclass
class Nil(ASTNode):
    pass

@dataclass
class Identifier(ASTNode):
    name: str

@dataclass
class BinaryOp(ASTNode):
    operator: str  # +, -, *, /, ==, !=, <, >, <=, >=, and, or
    left: ASTNode
    right: ASTNode

@dataclass
class UnaryOp(ASTNode):
    operator: str  # -, not
    operand: ASTNode

@dataclass
class Assign(ASTNode):
    name: str
    value: ASTNode

@dataclass
class VarDecl(ASTNode):
    name: str
    initializer: Optional[ASTNode]

@dataclass
class If(ASTNode):
    condition: ASTNode
    then_branch: ASTNode
    else_branch: Optional[ASTNode]

@dataclass
class While(ASTNode):
    condition: ASTNode
    body: ASTNode

@dataclass
class Block(ASTNode):
    statements: List[ASTNode]

@dataclass
class Call(ASTNode):
    callee: ASTNode
    arguments: List[ASTNode]

@dataclass
class FunctionDef(ASTNode):
    name: str
    params: List[str]
    body: ASTNode

@dataclass
class Return(ASTNode):
    value: Optional[ASTNode]

@dataclass
class ListLiteral(ASTNode):
    elements: List[ASTNode]

@dataclass
class Index(ASTNode):
    target: ASTNode
    index: ASTNode

@dataclass
class Print(ASTNode):
    expression: ASTNode
