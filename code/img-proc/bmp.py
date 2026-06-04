"""BMP 图像读写 — 完全手动构造，无外部依赖"""
import struct
import os


class Image:
    """内存图像"""
    def __init__(self, width: int, height: int, channels: int = 3):
        self.width = width
        self.height = height
        self.channels = channels  # 3 = RGB, 1 = Grayscale
        # 像素数据 [height][width][channels]，0-255
        self.pixels = [[[0] * channels for _ in range(width)] for _ in range(height)]

    def get_pixel(self, x: int, y: int) -> list:
        """获取像素（带边界裁切）"""
        x = max(0, min(x, self.width - 1))
        y = max(0, min(y, self.height - 1))
        return self.pixels[y][x]

    def set_pixel(self, x: int, y: int, color: list):
        """设置像素"""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = [max(0, min(255, int(c))) for c in color]

    def copy(self):
        """深拷贝"""
        img = Image(self.width, self.height, self.channels)
        for y in range(self.height):
            for x in range(self.width):
                img.pixels[y][x] = list(self.pixels[y][x])
        return img

    def to_grayscale(self):
        """转灰度"""
        if self.channels == 1:
            return self.copy()
        gray = Image(self.width, self.height, 1)
        for y in range(self.height):
            for x in range(self.width):
                r, g, b = self.pixels[y][x][:3]
                gray.pixels[y][x][0] = int(0.299 * r + 0.587 * g + 0.114 * b)
        return gray


def save_bmp(img: Image, filename: str):
    """保存 BMP 文件（24位或8位）"""
    width = img.width
    height = img.height
    channels = img.channels

    # 行对齐到 4 字节
    row_size = ((width * channels + 3) // 4) * 4
    pixel_data_size = row_size * height
    file_size = 14 + 40 + pixel_data_size

    with open(filename, 'wb') as f:
        # BITMAPFILEHEADER (14 bytes)
        f.write(b'BM')                                 # bfType
        f.write(struct.pack('<I', file_size))           # bfSize
        f.write(struct.pack('<H', 0))                   # bfReserved1
        f.write(struct.pack('<H', 0))                   # bfReserved2
        f.write(struct.pack('<I', 14 + 40))             # bfOffBits

        # BITMAPINFOHEADER (40 bytes)
        f.write(struct.pack('<I', 40))                  # biSize
        f.write(struct.pack('<i', width))               # biWidth
        f.write(struct.pack('<i', height))              # biHeight (positive = bottom-up)
        f.write(struct.pack('<H', 1))                   # biPlanes
        f.write(struct.pack('<H', channels * 8))        # biBitCount (24 or 8)
        f.write(struct.pack('<I', 0))                   # biCompression (0 = none)
        f.write(struct.pack('<I', pixel_data_size))     # biSizeImage
        f.write(struct.pack('<i', 2835))                # biXPelsPerMeter (72 DPI)
        f.write(struct.pack('<i', 2835))                # biYPelsPerMeter
        f.write(struct.pack('<I', 0))                   # biClrUsed
        f.write(struct.pack('<I', 0))                   # biClrImportant

        # 像素数据 (BGR format, bottom-up)
        for y in range(height - 1, -1, -1):
            row = bytearray()
            for x in range(width):
                px = img.pixels[y][x]
                if channels == 3:
                    row.append(px[2])  # B
                    row.append(px[1])  # G
                    row.append(px[0])  # R
                else:
                    row.append(px[0])
                    row.append(px[0])
                    row.append(px[0])
            # 对齐到 4 字节
            padding = row_size - len(row)
            row.extend([0] * padding)
            f.write(bytes(row))


def load_bmp(filename: str) -> Image:
    """加载 BMP 文件"""
    with open(filename, 'rb') as f:
        data = f.read()

    # 检查 BMP 签名
    if data[:2] != b'BM':
        raise ValueError("Not a BMP file")

    # 解析文件头
    width = struct.unpack('<i', data[18:22])[0]
    height = struct.unpack('<i', data[22:26])[0]
    bpp = struct.unpack('<H', data[28:30])[0]
    # 只支持 24-bit
    if bpp != 24:
        raise ValueError(f"Only 24-bit BMP supported, got {bpp}-bit")

    img = Image(width, height, 3)
    row_size = ((width * 3 + 3) // 4) * 4
    pixel_offset = struct.unpack('<I', data[10:14])[0]

    for y in range(height - 1, -1, -1):
        row_start = pixel_offset + (height - 1 - y) * row_size
        row_data = data[row_start:row_start + width * 3]
        for x in range(width):
            offset = x * 3
            b = row_data[offset]
            g = row_data[offset + 1]
            r = row_data[offset + 2]
            img.pixels[y][x] = [r, g, b]

    return img
