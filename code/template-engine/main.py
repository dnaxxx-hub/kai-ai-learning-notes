#!/usr/bin/env python3
"""CLI + 文件渲染"""

import sys
import json
import os

from engine import Environment


def main():
    if len(sys.argv) < 2:
        print('Usage:')
        print('  python main.py "Hello {{ name }}" --context \'{"name": "world"}\'')
        print('  python main.py template.html --context \'{"name": "world"}\'')
        sys.exit(1)

    input_arg = sys.argv[1]
    context = {}
    if '--context' in sys.argv:
        idx = sys.argv.index('--context')
        if idx + 1 < len(sys.argv):
            context = json.loads(sys.argv[idx + 1])

    env = Environment()

    if os.path.isfile(input_arg):
        # File mode: render template file
        with open(input_arg, 'r', encoding='utf-8') as f:
            source = f.read()
        # Set up loader for template inheritance
        template_dir = os.path.dirname(input_arg) or '.'

        def loader(name):
            path = os.path.join(template_dir, name)
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

        env.loader = loader
        template = env.from_string(source)
        result = template.render(context)
    else:
        # String mode: render inline template
        template = env.from_string(input_arg)
        result = template.render(context)

    print(result)


if __name__ == '__main__':
    main()
