#!/usr/bin/env python3
"""正则表达式引擎 CLI"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from matcher import Regex


def main():
    import argparse
    parser = argparse.ArgumentParser(description='手写正则表达式引擎')
    parser.add_argument('pattern', help='正则表达式')
    parser.add_argument('text', nargs='?', help='匹配文本')
    parser.add_argument('-m', '--match', action='store_true', help='完全匹配')
    parser.add_argument('-s', '--search', action='store_true', default=True, help='搜索子串 (默认)')
    parser.add_argument('-a', '--all', action='store_true', help='查找所有匹配')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示 NFA 信息')

    args = parser.parse_args()

    try:
        regex = Regex(args.pattern)
    except Exception as e:
        print(f"❌ 编译失败: {e}")
        sys.exit(1)

    if args.verbose:
        print(f"📐 正则: {args.pattern}")
        print(f"📦 NFA 已编译")

    if args.text:
        if args.match:
            result = regex.match(args.text)
            print(f"完全匹配: {result}")
        elif args.all:
            results = regex.findall(args.text)
            print(f"找到 {len(results)} 个匹配: {results}")
        else:
            result = regex.search(args.text)
            print(f"匹配: {result or '无匹配'}")
    else:
        # 交互模式
        print(f"📐 正则: {args.pattern}")
        print("输入文本 (空行退出):")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                break
            result = regex.search(line)
            print(f"  → {result or '无匹配'}")


if __name__ == '__main__':
    main()
