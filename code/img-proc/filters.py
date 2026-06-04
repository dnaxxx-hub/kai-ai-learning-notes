"""图像滤波器"""
from bmp import Image
import math
import random


def _apply_convolution(img: Image, kernel: list) -> Image:
    """卷积操作"""
    k_size = len(kernel)
    k_half = k_size // 2
    result = img.copy()

    for y in range(img.height):
        for x in range(img.width):
            for c in range(img.channels):
                total = 0.0
                for ky in range(k_size):
                    for kx in range(k_size):
                        px = img.get_pixel(x + kx - k_half, y + ky - k_half)
                        total += px[c] * kernel[ky][kx]
                result.pixels[y][x][c] = max(0, min(255, int(total)))

    return result


def gaussian_blur(img: Image, radius: float = 1.5) -> Image:
    """高斯模糊"""
    k_size = int(radius * 3 + 1)
    if k_size % 2 == 0:
        k_size += 1

    kernel = []
    sigma = radius
    sigma2 = sigma * sigma
    total = 0.0

    for ky in range(k_size):
        row = []
        for kx in range(k_size):
            dx = kx - k_size // 2
            dy = ky - k_size // 2
            val = math.exp(-(dx*dx + dy*dy) / (2 * sigma2)) / (2 * math.pi * sigma2)
            row.append(val)
            total += val
        kernel.append(row)

    # 归一化
    for y in range(k_size):
        for x in range(k_size):
            kernel[y][x] /= total

    return _apply_convolution(img, kernel)


def box_blur(img: Image, size: int = 3) -> Image:
    """均值模糊（方框滤波）"""
    kernel = [[1.0 / (size * size)] * size for _ in range(size)]
    return _apply_convolution(img, kernel)


def sharpen(img: Image, strength: float = 0.5) -> Image:
    """锐化"""
    kernel = [
        [0, -strength, 0],
        [-strength, 1 + 4*strength, -strength],
        [0, -strength, 0]
    ]
    return _apply_convolution(img, kernel)


def edge_detect(img: Image, threshold: int = 100) -> Image:
    """Sobel 边缘检测"""
    gray = img if img.channels == 1 else img.to_grayscale()
    result = Image(gray.width, gray.height, 1)

    sobel_x = [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]
    sobel_y = [[-1, -2, -1], [0, 0, 0], [1, 2, 1]]

    for y in range(gray.height):
        for x in range(gray.width):
            gx = 0.0
            gy = 0.0
            for ky in range(3):
                for kx in range(3):
                    px = gray.get_pixel(x + kx - 1, y + ky - 1)[0]
                    gx += px * sobel_x[ky][kx]
                    gy += px * sobel_y[ky][kx]

            mag = math.sqrt(gx*gx + gy*gy)
            val = 255 if mag > threshold else 0
            result.pixels[y][x][0] = val

    return result


def emboss(img: Image) -> Image:
    """浮雕效果"""
    kernel = [[-2, -1, 0], [-1, 1, 1], [0, 1, 2]]
    result = _apply_convolution(img, kernel)
    # 加 128 偏移让浮雕可见
    for y in range(result.height):
        for x in range(result.width):
            for c in range(result.channels):
                result.pixels[y][x][c] = max(0, min(255, result.pixels[y][x][c] + 128))
    return result


def add_noise(img: Image, intensity: float = 0.05) -> Image:
    """添加椒盐噪声"""
    result = img.copy()
    num_pixels = int(img.width * img.height * intensity)
    for _ in range(num_pixels):
        x = random.randint(0, img.width - 1)
        y = random.randint(0, img.height - 1)
        val = 255 if random.random() > 0.5 else 0
        for c in range(img.channels):
            result.pixels[y][x][c] = val
    return result
