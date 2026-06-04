#!/usr/bin/env python3
import sys
from lexer import Lexer
from parser import Parser
from evaluator import Evaluator


def run_source(source: str):
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    ast = parser.parse()
    evaluator = Evaluator()
    return evaluator.evaluate(ast)


def repl():
    evaluator = Evaluator()
    print("MiniLang REPL (type 'exit()' to quit)")
    print("=" * 40)

    while True:
        try:
            line = input(">> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if line.strip().lower() in ('exit', 'exit()'):
            break

        if not line.strip():
            continue

        try:
            result = run_source(line)
            if result is not None:
                print(repr(result))
        except Exception as e:
            print(f"Error: {e}")


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            source = f.read()
        try:
            run_source(source)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
    else:
        repl()


if __name__ == '__main__':
    main()
