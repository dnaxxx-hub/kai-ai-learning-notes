#!/usr/bin/env python3
"""图像处理器 CLI"""
import sys
import os

# 确保当前目录在路径中，即使从外部调用
sys.path.insert(0, os.path.dirname(__file__))

from bmp import save_bmp, load_bmp
import generate as gen
import filters as flt
import transforms as tra


def main():
    import argparse
    parser = argparse.ArgumentParser(description='纯数学图像处理器')
    sub = parser.add_subparsers(dest='command', required=True)

    # generate
    p_gen = sub.add_parser('gen', help='生成测试图案')
    p_gen.add_argument('type', choices=['solid', 'gradient', 'checker', 'rainbow',
                                        'mandelbrot', 'julia'])
    p_gen.add_argument('-o', '--output', default='output.bmp')
    p_gen.add_argument('-w', '--width', type=int, default=400)
    p_gen.add_argument('--height', type=int)
    p_gen.add_argument('--color', nargs=3, type=int, default=[200, 100, 50],
                       help='solid: R G B')
    p_gen.add_argument('--c-real', type=float, default=-0.7, help='Julia: c real')
    p_gen.add_argument('--c-imag', type=float, default=0.27, help='Julia: c imag')
    p_gen.add_argument('--max-iter', type=int, default=100)

    # filter
    p_flt = sub.add_parser('filter', help='应用滤镜')
    p_flt.add_argument('filter_name', choices=['blur', 'gaussian', 'sharpen',
                                               'edge', 'emboss', 'noise'])
    p_flt.add_argument('input')
    p_flt.add_argument('-o', '--output', default='filtered.bmp')

    # transform
    p_tra = sub.add_parser('transform', help='色彩调整')
    p_tra.add_argument('transform_name', choices=['brightness', 'contrast',
                                                  'gamma', 'invert', 'sepia',
                                                  'threshold', 'posterize'])
    p_tra.add_argument('input')
    p_tra.add_argument('-o', '--output', default='transformed.bmp')

    args = parser.parse_args()

    if args.command == 'gen':
        height = args.height or args.width
        types = {
            'solid': lambda: gen.solid_color(args.width, height, *args.color),
            'gradient': lambda: gen.gradient(args.width, height),
            'checker': lambda: gen.checkerboard(args.width, height),
            'rainbow': lambda: gen.rainbow(args.width, height),
            'mandelbrot': lambda: gen.mandelbrot(args.width, height, args.max_iter),
            'julia': lambda: gen.julia_set(args.width, height, args.c_real,
                                           args.c_imag, args.max_iter),
        }
        img = types[args.type]()
        save_bmp(img, args.output)
        print(f"✅ 已生成 {args.type} → {args.output} ({img.width}x{img.height})")

    elif args.command == 'filter':
        img = load_bmp(args.input)
        filters = {
            'blur': lambda: flt.box_blur(img),
            'gaussian': lambda: flt.gaussian_blur(img),
            'sharpen': lambda: flt.sharpen(img),
            'edge': lambda: flt.edge_detect(img),
            'emboss': lambda: flt.emboss(img),
            'noise': lambda: flt.add_noise(img),
        }
        result = filters[args.filter_name]()
        save_bmp(result, args.output)
        print(f"✅ 已应用 {args.filter_name} → {args.output}")

    elif args.command == 'transform':
        img = load_bmp(args.input)
        transforms = {
            'brightness': lambda: tra.brightness(img),
            'contrast': lambda: tra.contrast(img),
            'gamma': lambda: tra.gamma_correct(img),
            'invert': lambda: tra.invert(img),
            'sepia': lambda: tra.sepia(img),
            'threshold': lambda: tra.threshold(img),
            'posterize': lambda: tra.posterize(img),
        }
        result = transforms[args.transform_name]()
        save_bmp(result, args.output)
        print(f"✅ 已应用 {args.transform_name} → {args.output}")


if __name__ == '__main__':
    main()
