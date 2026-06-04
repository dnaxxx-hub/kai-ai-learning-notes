from parser import (
    Document, TextNode, VariableNode, ForNode, IfNode, SetNode,
    BlockNode, ExtendsNode, Filtered, Variable, Number, String,
    BinOp, Compare
)


class Compiler:
    def __init__(self, engine=None):
        self.engine = engine
        self._indent = 0

    def _line(self, text, indent_override=None):
        if indent_override is not None:
            return '    ' * abs(indent_override) + text
        return '    ' * self._indent + text

    def compile(self, doc):
        lines = []
        self._indent = 0
        lines.append(self._line('def render(context, filters, engine):'))
        self._indent = 1
        lines.append(self._line('_buf = []'))
        self._compile_node(doc, lines)
        lines.append(self._line('return "".join(_buf)'))
        return '\n'.join(lines)

    def _compile_node(self, node, lines):
        if isinstance(node, Document):
            for child in node.body:
                self._compile_node(child, lines)
        elif isinstance(node, TextNode):
            lines.append(self._line('_buf.append(%r)' % node.text))
        elif isinstance(node, VariableNode):
            expr_code = self._compile_expression(node.expr)
            lines.append(self._line('_buf.append(str(%s))' % expr_code))
        elif isinstance(node, ForNode):
            iter_code = self._compile_expression(node.iter_expr)
            var = node.var
            if isinstance(iter_code, tuple):
                iter_code = iter_code[0]
            lines.append(self._line('_has_items = False'))
            lines.append(self._line('for _loop_var in %s:' % iter_code))
            self._indent += 1
            lines.append(self._line('_has_items = True'))
            lines.append(self._line('%s = _loop_var' % var))
            lines.append(self._line('context[%r] = _loop_var' % var))
            for child in node.body:
                self._compile_node(child, lines)
            self._indent -= 1
            if node.else_body:
                lines.append(self._line('if not _has_items:'))
                self._indent += 1
                for child in node.else_body:
                    self._compile_node(child, lines)
                self._indent -= 1
        elif isinstance(node, IfNode):
            cond_code = self._compile_expression(node.condition)
            lines.append(self._line('if %s:' % cond_code))
            self._indent += 1
            for child in node.body:
                self._compile_node(child, lines)
            self._indent -= 1
            for cond, body in node.elifs:
                cond_code = self._compile_expression(cond)
                lines.append(self._line('elif %s:' % cond_code))
                self._indent += 1
                for child in body:
                    self._compile_node(child, lines)
                self._indent -= 1
            if node.else_body:
                lines.append(self._line('else:'))
                self._indent += 1
                for child in node.else_body:
                    self._compile_node(child, lines)
                self._indent -= 1
        elif isinstance(node, SetNode):
            expr_code = self._compile_expression(node.expr)
            lines.append(self._line('%s = %s' % (node.name, expr_code)))
            lines.append(self._line('context[%r] = %s' % (node.name, node.name)))
        elif isinstance(node, BlockNode):
            # 块定义: 编译时记录，继承时替换
            if self.engine and hasattr(self.engine, 'blocks'):
                self.engine.blocks[node.name] = node.body

    def _compile_expression(self, expr):
        if expr is None:
            return 'None'
        if isinstance(expr, Number):
            return repr(expr.value)
        if isinstance(expr, String):
            return repr(expr.value)
        if isinstance(expr, Variable):
            parts = expr.name.split('.')
            code = '_get(context, %r)' % parts[0]
            for part in parts[1:]:
                code = '(%s or {}).get(%r, "")' % (code, part)
            return code
        if isinstance(expr, Filtered):
            inner = self._compile_expression(expr.expr)
            args = ', '.join(self._compile_expression(a) for a in expr.args)
            if args:
                return 'filters.get(%r, lambda x: x)(%s, %s)' % (expr.filter_name, inner, args)
            return 'filters.get(%r, lambda x: x)(%s)' % (expr.filter_name, inner)
        if isinstance(expr, BinOp):
            left = self._compile_expression(expr.left)
            right = self._compile_expression(expr.right)
            return '(%s %s %s)' % (left, expr.op, right)
        if isinstance(expr, Compare):
            left = self._compile_expression(expr.left)
            right = self._compile_expression(expr.right)
            return '(%s %s %s)' % (left, expr.op, right)
        return 'None'
