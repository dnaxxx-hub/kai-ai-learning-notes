"""演示：图像处理全流程"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from bmp import save_bmp
import generate as gen
import filters as flt
import transforms as tra


def demo():
    print("=" * 45)
    print("📷 纯数学图像处理器 · 全功能演示")
    print("=" * 45)

    os.makedirs("_demo_output", exist_ok=True)

    # 1. 生成测试图案
    print("\n1️⃣ 生成测试图案...")
    patterns = [
        ("rainbow", gen.rainbow(200, 200)),
        ("gradient", gen.gradient(200, 200)),
        ("checker", gen.checkerboard(200, 200)),
        ("mandelbrot", gen.mandelbrot(300, 300, 50)),
        ("julia", gen.julia_set(300, 300, -0.7, 0.27, 50)),
    ]
    for name, img in patterns:
        save_bmp(img, f"_demo_output/{name}.bmp")
        print(f"   ✅ {name}.bmp ({img.width}x{img.height})")

    # 2. 创建测试图用于滤镜
    img = gen.rainbow(200, 200)
    save_bmp(img, "_demo_output/source.bmp")

    # 3. 滤镜效果
    print("\n2️⃣ 滤镜效果...")
    filters = [
        ("gaussian_blur", flt.gaussian_blur(img, 2.0)),
        ("edge_detect", flt.edge_detect(img, 80)),
        ("sharpen", flt.sharpen(img)),
        ("emboss", flt.emboss(img)),
        ("noise", flt.add_noise(img, 0.03)),
    ]
    for name, result in filters:
        save_bmp(result, f"_demo_output/{name}.bmp")
        print(f"   ✅ {name}.bmp")

    # 4. 色彩变换
    print("\n3️⃣ 色彩变换...")
    transforms = [
        ("sepia", tra.sepia(img)),
        ("invert", tra.invert(img)),
        ("grayscale", img.to_grayscale()),
        ("threshold", tra.threshold(img)),
        ("posterize", tra.posterize(img, 4)),
        ("brightness", tra.brightness(img, 50)),
        ("contrast", tra.contrast(img, 1.5)),
        ("gamma", tra.gamma_correct(img, 0.5)),
    ]
    for name, result in transforms:
        save_bmp(result, f"_demo_output/{name}.bmp")
        print(f"   ✅ {name}.bmp")

    # 5. 清理
    import shutil
    shutil.rmtree("_demo_output")
    print("\n🧹 已清理临时文件")
    print("\n🎉 演示完成! 生成: 5种图案 + 5种滤镜 + 8种色彩变换")


if __name__ == '__main__':
    demo()
