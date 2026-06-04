"""测试图案生成"""
from bmp import Image
import math
import random


def solid_color(width: int, height: int, r: int, g: int, b: int) -> Image:
    """纯色图像"""
    img = Image(width, height)
    for y in range(height):
        for x in range(width):
            img.pixels[y][x] = [r, g, b]
    return img


def gradient(width: int, height: int) -> Image:
    """水平渐变"""
    img = Image(width, height)
    for y in range(height):
        for x in range(width):
            r = int(x / width * 255)
            g = int(y / height * 255)
            b = 255 - r
            img.pixels[y][x] = [r, g, b]
    return img


def checkerboard(width: int, height: int, size: int = 32) -> Image:
    """棋盘格"""
    img = Image(width, height)
    for y in range(height):
        for x in range(width):
            if ((x // size) + (y // size)) % 2 == 0:
                img.pixels[y][x] = [255, 255, 255]
            else:
                img.pixels[y][x] = [0, 0, 0]
    return img


def rainbow(width: int, height: int) -> Image:
    """彩虹"""
    img = Image(width, height)
    for y in range(height):
        for x in range(width):
            hue = (x / width) * 360
            # HSV to RGB (简化版)
            h = hue / 60
            i = int(h)
            f = h - i
            q = int(255 * (1 - f))
            t = int(255 * f)
            i = i % 6
            if i == 0:
                img.pixels[y][x] = [255, t, 0]
            elif i == 1:
                img.pixels[y][x] = [q, 255, 0]
            elif i == 2:
                img.pixels[y][x] = [0, 255, t]
            elif i == 3:
                img.pixels[y][x] = [0, q, 255]
            elif i == 4:
                img.pixels[y][x] = [t, 0, 255]
            else:
                img.pixels[y][x] = [255, 0, q]
    return img


def mandelbrot(width: int, height: int, max_iter: int = 100) -> Image:
    """Mandelbrot 分形"""
    img = Image(width, height)
    for y in range(height):
        for x in range(width):
            zx = (x / width) * 3.0 - 2.0
            zy = (y / height) * 3.0 - 1.5
            c = complex(zx, zy)
            z = 0j
            for i in range(max_iter):
                z = z * z + c
                if abs(z) > 2:
                    break

            val = int(i / max_iter * 255)
            img.pixels[y][x] = [val, val // 2, 255 - val]

    return img


def julia_set(width: int, height: int, c_real: float = -0.7,
              c_imag: float = 0.27, max_iter: int = 100) -> Image:
    """Julia 集分形"""
    img = Image(width, height)
    c = complex(c_real, c_imag)

    for y in range(height):
        for x in range(width):
            zx = (x / width) * 4.0 - 2.0
            zy = (y / height) * 4.0 - 2.0
            z = complex(zx, zy)

            for i in range(max_iter):
                z = z * z + c
                if abs(z) > 2:
                    break

            val = int(i / max_iter * 255)
            img.pixels[y][x] = [val, int(val * 0.3), 255 - val]

    return img
