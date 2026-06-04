"""色彩调整"""
from bmp import Image
import math


def brightness(img: Image, delta: float = 30) -> Image:
    """亮度调整 (delta: -255 ~ 255)"""
    result = img.copy()
    for y in range(img.height):
        for x in range(img.width):
            for c in range(img.channels):
                val = img.pixels[y][x][c] + delta
                result.pixels[y][x][c] = max(0, min(255, int(val)))
    return result


def contrast(img: Image, gain: float = 1.5) -> Image:
    """对比度调整 (gain: 0.0 ~ 3.0)"""
    result = img.copy()
    for y in range(img.height):
        for x in range(img.width):
            for c in range(img.channels):
                # 以 128 为基准
                val = 128 + (img.pixels[y][x][c] - 128) * gain
                result.pixels[y][x][c] = max(0, min(255, int(val)))
    return result


def gamma_correct(img: Image, gamma: float = 2.2) -> Image:
    """Gamma 校正 (gamma > 1 压暗，< 1 提亮)"""
    result = img.copy()
    inv_gamma = 1.0 / gamma
    for y in range(img.height):
        for x in range(img.width):
            for c in range(img.channels):
                normalized = img.pixels[y][x][c] / 255.0
                corrected = normalized ** inv_gamma
                result.pixels[y][x][c] = max(0, min(255, int(corrected * 255)))
    return result


def invert(img: Image) -> Image:
    """颜色反转"""
    result = img.copy()
    for y in range(img.height):
        for x in range(img.width):
            for c in range(img.channels):
                result.pixels[y][x][c] = 255 - img.pixels[y][x][c]
    return result


def sepia(img: Image) -> Image:
    """复古色调"""
    result = img.copy()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = img.pixels[y][x][:3]
            nr = int(0.393 * r + 0.769 * g + 0.189 * b)
            ng = int(0.349 * r + 0.686 * g + 0.168 * b)
            nb = int(0.272 * r + 0.534 * g + 0.131 * b)
            result.pixels[y][x] = [min(255, nr), min(255, ng), min(255, nb)]
    return result


def threshold(img: Image, level: int = 128) -> Image:
    """二值化"""
    gray = img if img.channels == 1 else img.to_grayscale()
    result = Image(gray.width, gray.height, 1)
    for y in range(gray.height):
        for x in range(gray.width):
            result.pixels[y][x][0] = 255 if gray.pixels[y][x][0] > level else 0
    return result


def posterize(img: Image, levels: int = 4) -> Image:
    """色调分离"""
    result = img.copy()
    step = 256 // levels
    for y in range(img.height):
        for x in range(img.width):
            for c in range(img.channels):
                val = (img.pixels[y][x][c] // step) * step + step // 2
                result.pixels[y][x][c] = min(255, val)
    return result
