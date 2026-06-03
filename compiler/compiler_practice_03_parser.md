# 编译器实战 03 — 递归下降解析器 (Parser)

## 概述
递归下降解析器将 Token 流转换为 AST。每个语法规则对应一个解析函数。

## MiniLang 语法 (EBNF)
```
program        ::= function*
function       ::= 'func' IDENTIFIER '(' param_list ')' '->' type block
param_list     ::= (param (',' param)*)?
param          ::= IDENTIFIER ':' type
type           ::= 'int' | 'float' | 'bool' | 'string'
block          ::= '{' statement* '}'
statement      ::= var_decl ';'
                 | expr ';'
                 | 'if' '(' expr ')' block ('else' block)?
                 | 'while' '(' expr ')' block
                 | 'return' expr? ';'
var_decl       ::= 'var' IDENTIFIER ':' type ('=' expr)?
expr (top)     ::= assignment
assignment     ::= IDENTIFIER '=' expr | logical_or
logical_or     ::= logical_and ('||' logical_and)*
logical_and    ::= equality ('&&' equality)*
equality       ::= comparison (('==' | '!=') comparison)*
comparison     ::= term (('<' | '>' | '<=' | '>=') term)*
term           ::= factor (('+' | '-') factor)*
factor         ::= unary (('*' | '/') unary)*
unary          ::= ('-' | '!') unary | call_primary
call_primary   ::= primary ('(' args? ')')?
primary        ::= NUMBER | STRING | 'true' | 'false' | IDENTIFIER | '(' expr ')'
args           ::= expr (',' expr)*
```

## 优先级处理
通过多级 parse 函数实现优先级（从低到高）：
assignment < logical_or < logical_and < equality < comparison < term < factor < unary < primary
