"""演示：正则表达式引擎"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from matcher import Regex


def demo():
    print("=" * 45)
    print("🔍 正则表达式引擎 · 手工 NFA 实现")
    print("=" * 45)

    tests = [
        ("字面匹配",    "hello",       "hello world",    False),
        ("完全匹配",    "hello",       "hello",           True),
        ("选择",        "cat|dog",     "I have a cat",    False),
        ("重复 *",      "ab*c",        "abbc",            True),
        ("重复 +",      "ab+c",        "ac",              False),
        ("可选 ?",      "colou?r",     "color",           True),
        ("可选 ?",      "colou?r",     "colour",          True),
        ("分组",        "(ab)+",       "abab",            True),
        ("通配符",      "h.t",         "hot",             True),
        ("通配符",      "h.t",         "hzt",             True),
        ("组合",        "a(b|c)*d",    "abcd",            True),
        ("组合",        "a(b|c)*d",    "abbccd",          True),
        ("复杂",        "a(b|c)*d",    "ad",              True),
    ]

    all_pass = True
    for name, pattern, text, expected in tests:
        try:
            regex = Regex(pattern)
            result = regex.match(text)
            status = "✅" if result == expected else "❌"
            if result != expected:
                all_pass = False
            label = '完全匹配' if result else '不匹配'
            print(f"{status} {name}: /{pattern}/ ~ {text!r:20s} → {label}")
        except Exception as e:
            print(f"❌ {name}: /{pattern}/ → 错误: {e}")
            all_pass = False

    print(f"\n{'🎉 全部通过!' if all_pass else '⚠️ 部分失败'}")
    print("")

    # 搜索演示
    print("🔎 搜索演示:")
    regex = Regex("\\d+")
    text = "abc123def456ghi789"
    print(f"  文本: {text!r}")
    print(f"  模式: \\d+")
    print(f"  搜索: {regex.search(text)!r}")
    print(f"  全部: {regex.findall(text)!r}")


if __name__ == '__main__':
    demo()
