from parser import parse, Document, ExtendsNode, BlockNode, TextNode
from compiler import Compiler
from filters import default_filters


class Template:
    def __init__(self, source, name='<template>', engine=None):
        self.source = source
        self.name = name
        self.engine = engine
        self._doc = parse(source)
        self._compiler = Compiler(engine)
        code = self._compiler.compile(self._doc)

        # Resolve template inheritance
        inherits_from = None
        for node in self._doc.body:
            if isinstance(node, ExtendsNode):
                inherits_from = node.template
                break

        if inherits_from and engine and engine.loader:
            # Load parent template and merge blocks
            parent_source = engine.loader(inherits_from)
            parent_doc = parse(parent_source)

            # Merge child blocks into parent
            child_blocks = {}
            for node in self._doc.body:
                if isinstance(node, BlockNode):
                    child_blocks[node.name] = node.body

            # Now re-parse parent with blocks replaced
            merged_body = self._merge_blocks(parent_doc.body, child_blocks)
            merged_doc = Document(merged_body)
            code = self._compiler.compile(merged_doc)

        ns = {
            '_get': lambda ctx, k: ctx.get(k, ''),
            '_getattr': lambda obj, attr: getattr(obj, attr, '') if hasattr(obj, attr) else obj.get(attr, '') if isinstance(obj, dict) else '',
        }
        exec(code, ns, ns)
        self._render = ns['render']

    def _merge_blocks(self, parent_body, child_blocks):
        """Replace block nodes in parent_body with child blocks."""
        result = []
        for node in parent_body:
            if isinstance(node, BlockNode):
                if node.name in child_blocks:
                    result.extend(child_blocks[node.name])
                else:
                    result.append(node)
            else:
                result.append(node)
        return result

    def render(self, context=None):
        context = context or {}
        if self.engine:
            ctx = dict(self.engine.globals)
            ctx.update(context)
            filters_dict = self.engine.filters if self.engine else default_filters
            return self._render(ctx, filters_dict, self.engine)
        return self._render(context, default_filters, None)


class Environment:
    def __init__(self, loader=None, autoescape=False):
        self.loader = loader  # (template_name) → source
        self.filters = dict(default_filters)
        self.globals = {}
        self.blocks = {}
        self.autoescape = autoescape

    def add_filter(self, name, func):
        self.filters[name] = func

    def from_string(self, source):
        return Template(source, engine=self)

    def get_template(self, name):
        if self.loader:
            source = self.loader(name)
            return Template(source, name=name, engine=self)
        raise ValueError(f'No loader configured: {name}')

    def render_template(self, name, context=None):
        template = self.get_template(name)
        return template.render(context)
