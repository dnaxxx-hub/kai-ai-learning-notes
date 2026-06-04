"""图像处理器测试"""
import unittest
import sys
import os
import math
sys.path.insert(0, os.path.dirname(__file__))

from bmp import Image, save_bmp, load_bmp
import generate as gen
import filters as flt
import transforms as tra


class TestBMP(unittest.TestCase):
    def test_save_and_load(self):
        """测试 BMP 保存和加载的往返一致性"""
        img = Image(10, 10, 3)
        for y in range(10):
            for x in range(10):
                img.pixels[y][x] = [x * 25, y * 25, (x + y) * 12]

        save_bmp(img, '_test.bmp')
        loaded = load_bmp('_test.bmp')

        self.assertEqual(loaded.width, 10)
        self.assertEqual(loaded.height, 10)

        for y in range(10):
            for x in range(10):
                self.assertEqual(loaded.pixels[y][x], img.pixels[y][x])

        os.remove('_test.bmp')

    def test_image_copy(self):
        """测试深拷贝独立性"""
        img = Image(5, 5, 3)
        img.pixels[0][0] = [100, 150, 200]
        copy = img.copy()
        copy.pixels[0][0] = [0, 0, 0]
        self.assertEqual(img.pixels[0][0], [100, 150, 200])

    def test_grayscale(self):
        """测试灰度转换（红→约76）"""
        img = Image(3, 3, 3)
        img.pixels[0][0] = [255, 0, 0]  # Red
        gray = img.to_grayscale()
        self.assertEqual(gray.channels, 1)
        # Gray of red ≈ 76
        self.assertAlmostEqual(gray.pixels[0][0][0], 76, delta=2)


class TestGenerate(unittest.TestCase):
    def test_solid(self):
        """测试纯色生成"""
        img = gen.solid_color(10, 10, 100, 150, 200)
        self.assertEqual(img.pixels[0][0], [100, 150, 200])
        self.assertEqual(img.pixels[9][9], [100, 150, 200])

    def test_gradient(self):
        """测试渐变图案"""
        img = gen.gradient(50, 50)
        self.assertNotEqual(img.pixels[0][0], img.pixels[49][49])

    def test_checkerboard(self):
        """测试棋盘格"""
        img = gen.checkerboard(64, 64, 16)
        # Adjacent blocks should differ
        self.assertNotEqual(img.pixels[0][0], img.pixels[0][16])

    def test_mandelbrot(self):
        """测试 Mandelbrot 分形生成"""
        img = gen.mandelbrot(50, 50, 20)
        self.assertEqual(img.width, 50)
        self.assertEqual(img.height, 50)


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.img = gen.rainbow(20, 20)

    def test_box_blur(self):
        """测试均值模糊"""
        result = flt.box_blur(self.img, 3)
        self.assertEqual(result.width, self.img.width)
        self.assertEqual(result.height, self.img.height)

    def test_gaussian_blur(self):
        """测试高斯模糊"""
        result = flt.gaussian_blur(self.img, 1.5)
        self.assertEqual(result.width, self.img.width)
        self.assertEqual(result.height, self.img.height)

    def test_edge_detect(self):
        """测试边缘检测"""
        result = flt.edge_detect(self.img, 100)
        self.assertEqual(result.channels, 1)

    def test_sharpen(self):
        """测试锐化"""
        result = flt.sharpen(self.img)
        self.assertEqual(result.width, self.img.width)
        self.assertEqual(result.height, self.img.height)

    def test_emboss(self):
        """测试浮雕效果"""
        result = flt.emboss(self.img)
        self.assertEqual(result.width, self.img.width)
        self.assertEqual(result.height, self.img.height)

    def test_noise(self):
        """测试椒盐噪声"""
        result = flt.add_noise(self.img, 0.05)
        self.assertEqual(result.width, self.img.width)
        self.assertEqual(result.height, self.img.height)


class TestTransforms(unittest.TestCase):
    def setUp(self):
        self.img = gen.rainbow(20, 20)

    def test_brightness(self):
        """测试亮度调整"""
        result = tra.brightness(self.img, 50)
        self.assertEqual(result.width, self.img.width)
        self.assertEqual(result.height, self.img.height)
        # Should be brighter
        self.assertGreaterEqual(result.pixels[0][0][0], self.img.pixels[0][0][0])

    def test_contrast(self):
        """测试对比度调整"""
        result = tra.contrast(self.img, 2.0)
        self.assertEqual(result.width, self.img.width)
        self.assertEqual(result.height, self.img.height)

    def test_gamma(self):
        """测试 Gamma 校正"""
        result = tra.gamma_correct(self.img, 2.2)
        self.assertEqual(result.width, self.img.width)
        self.assertEqual(result.height, self.img.height)

    def test_invert(self):
        """测试颜色反转"""
        result = tra.invert(self.img)
        for y in range(5):
            for x in range(5):
                for c in range(3):
                    self.assertEqual(
                        result.pixels[y][x][c] + self.img.pixels[y][x][c], 255
                    )

    def test_sepia(self):
        """测试复古色调"""
        result = tra.sepia(self.img)
        self.assertEqual(result.width, self.img.width)
        self.assertEqual(result.height, self.img.height)

    def test_threshold(self):
        """测试二值化"""
        result = tra.threshold(self.img, 128)
        for y in range(result.height):
            for x in range(result.width):
                self.assertIn(result.pixels[y][x][0], [0, 255])

    def test_posterize(self):
        """测试色调分离"""
        result = tra.posterize(self.img, 4)
        for y in range(result.height):
            for x in range(result.width):
                for c in range(3):
                    self.assertIn(result.pixels[y][x][c] % 64, [0, 32])


if __name__ == '__main__':
    unittest.main()
