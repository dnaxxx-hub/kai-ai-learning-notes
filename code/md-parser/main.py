#!/usr/bin/env python3
"""Markdown 解析器 CLI — Markdown → HTML"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from parser import parse_markdown
from renderer import render, render_standalone


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Markdown → HTML 转换器')
    parser.add_argument('input', nargs='?', help='输入 Markdown 文件')
    parser.add_argument('-o', '--output', help='输出 HTML 文件')
    parser.add_argument('-s', '--stdin', action='store_true', help='从 stdin 读取')
    parser.add_argument('--standalone', action='store_true', help='生成完整的 HTML 文档（含头部和样式）')
    parser.add_argument('--title', default='Markdown', help='HTML 文档标题（仅 standalone 模式）')

    args = parser.parse_args()

    if args.stdin or (not args.input and not sys.stdin.isatty()):
        text = sys.stdin.read()
    elif args.input:
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        # 交互模式
        print("📝 Markdown 解析器 (输入一行 Markdown):")
        line = sys.stdin.readline().strip()
        ast = parse_markdown(line)
        if args.standalone:
            html = render_standalone(ast, args.title)
        else:
            html = render(ast)
        print(html)
        return

    ast = parse_markdown(text)
    if args.standalone:
        html = render_standalone(ast, args.title)
    else:
        html = render(ast)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✅ 已转换 → {args.output}")
    else:
        print(html)


if __name__ == '__main__':
    main()
