from nodes import *
from environment import Environment
from builtins_mod import get_builtins


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class Evaluator:
    def __init__(self):
        self.global_env = Environment()
        # 加载内置函数
        for name, func in get_builtins().items():
            self.global_env.define(name, func)

    def evaluate(self, node, env=None):
        if env is None:
            env = self.global_env

        if isinstance(node, Program):
            result = None
            for stmt in node.statements:
                result = self.evaluate(stmt, env)
            return result

        elif isinstance(node, Block):
            block_env = Environment(env)
            result = None
            for stmt in node.statements:
                result = self.evaluate(stmt, block_env)
            return result

        elif isinstance(node, Number):
            return node.value

        elif isinstance(node, String):
            return node.value

        elif isinstance(node, Boolean):
            return node.value

        elif isinstance(node, Nil):
            return None

        elif isinstance(node, Identifier):
            return env.get(node.name)

        elif isinstance(node, BinaryOp):
            left = self.evaluate(node.left, env)
            right = self.evaluate(node.right, env)

            if node.operator == '+':
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) + str(right)
                return left + right
            elif node.operator == '-':
                return left - right
            elif node.operator == '*':
                return left * right
            elif node.operator == '/':
                return left / right
            elif node.operator == '%':
                return left % right
            elif node.operator == '==':
                return left == right
            elif node.operator == '!=':
                return left != right
            elif node.operator == '<':
                return left < right
            elif node.operator == '>':
                return left > right
            elif node.operator == '<=':
                return left <= right
            elif node.operator == '>=':
                return left >= right
            elif node.operator == 'and':
                return left and right
            elif node.operator == 'or':
                return left or right

        elif isinstance(node, UnaryOp):
            operand = self.evaluate(node.operand, env)
            if node.operator == '-':
                return -operand
            elif node.operator == 'not':
                return not operand

        elif isinstance(node, VarDecl):
            value = None
            if node.initializer:
                value = self.evaluate(node.initializer, env)
            env.define(node.name, value)
            return None

        elif isinstance(node, Assign):
            value = self.evaluate(node.value, env)
            env.assign(node.name, value)
            return value

        elif isinstance(node, If):
            condition = self.evaluate(node.condition, env)
            if condition:
                return self.evaluate(node.then_branch, env)
            elif node.else_branch:
                return self.evaluate(node.else_branch, env)
            return None

        elif isinstance(node, While):
            result = None
            while self.evaluate(node.condition, env):
                try:
                    result = self.evaluate(node.body, env)
                except ReturnSignal as e:
                    return e.value
            return result

        elif isinstance(node, FunctionDef):
            fn = UserFunction(node.name, node.params, node.body, env)
            env.define(node.name, fn)
            return None

        elif isinstance(node, Return):
            value = None
            if node.value:
                value = self.evaluate(node.value, env)
            raise ReturnSignal(value)

        elif isinstance(node, Call):
            callee = self.evaluate(node.callee, env)
            args = [self.evaluate(arg, env) for arg in node.arguments]

            if isinstance(callee, UserFunction):
                # 创建函数作用域
                fn_env = Environment(callee.env)
                for i, param in enumerate(callee.params):
                    fn_env.define(param, args[i] if i < len(args) else None)
                try:
                    return self.evaluate(callee.body, fn_env)
                except ReturnSignal as e:
                    return e.value

            elif callable(callee):
                return callee(*args)

            raise RuntimeError(f"Can't call {type(callee)}")

        elif isinstance(node, ListLiteral):
            return [self.evaluate(elem, env) for elem in node.elements]

        elif isinstance(node, Index):
            target = self.evaluate(node.target, env)
            index = self.evaluate(node.index, env)
            return target[index]

        elif isinstance(node, Print):
            value = self.evaluate(node.expression, env)
            print(value)
            return None

        raise RuntimeError(f"Unknown node type: {type(node)}")


class UserFunction:
    def __init__(self, name, params, body, env):
        self.name = name
        self.params = params
        self.body = body
        self.env = env

    def __repr__(self):
        return f"<fn {self.name}({', '.join(self.params)})>"
