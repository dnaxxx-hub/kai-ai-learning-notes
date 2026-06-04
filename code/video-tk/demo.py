"""演示：视频工具箱功能展示"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ffmpeg_wrapper import get_ffmpeg_path, run_ffmpeg
from video_info import get_info, format_duration


def demo():
    print("=" * 50)
    print("📹 视频工具箱 - 功能演示")
    print("=" * 50)

    # 检查 FFmpeg
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        print(f"\n✅ FFmpeg: {ffmpeg}")
    else:
        print("\n❌ FFmpeg not found")
        print("   This is a wrapper tool — install ffmpeg to use video features")
        print("   https://ffmpeg.org/download.html")
        return

    # 生成一个测试视频（使用 ffmpeg 内置测试源）
    print("\n🎬 生成测试视频...")
    test_video = "_test_demo.mp4"

    result = run_ffmpeg([
        '-f', 'lavfi', '-i', 'testsrc=duration=3:size=640x480:rate=30',
        '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3',
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-c:a', 'aac',
        '-y', test_video,
    ])

    if result['success']:
        print("   ✅ 测试视频已生成 (3秒, 640x480, 30fps)")
    else:
        print(f"   ❌ 生成失败: {result.get('stderr', '')[:100]}")
        return

    # 查看信息
    info = get_info(test_video)
    if 'video' in info:
        v = info['video']
        print(f"\n📊 视频信息:")
        print(f"   分辨率: {v['width']}x{v['height']}")
        print(f"   FPS: {v['fps']}")
        print(f"   编码: {v['codec']}")
    if 'duration_s' in info:
        print(f"   时长: {format_duration(info['duration_s'])}")

    # 提取单帧
    print("\n🖼️ 提取单帧...")
    result = run_ffmpeg([
        '-i', test_video, '-ss', '00:00:01',
        '-vframes', '1', '-y', '_frame.jpg',
    ])
    if result['success']:
        frame_size = os.path.getsize('_frame.jpg')
        print(f"   ✅ 帧已提取: _frame.jpg ({frame_size/1024:.0f} KB)")

    # 转换格式
    print("\n🔄 格式转换: mp4 → webm...")
    result = run_ffmpeg([
        '-i', test_video,
        '-c:v', 'libvpx', '-crf', '23',
        '-b:v', '500k',
        '-y', '_converted.webm',
    ])
    if result['success']:
        webm_size = os.path.getsize('_converted.webm')
        print(f"   ✅ 转换完成: _converted.webm ({webm_size/1024:.0f} KB)")

    # 生成 GIF
    print("\n🎞️ 生成 GIF (前2秒, 320px宽)...")
    result = run_ffmpeg([
        '-i', test_video, '-t', '2',
        '-vf', 'scale=320:-1,fps=10',
        '-y', '_demo.gif',
    ])
    if result['success']:
        gif_size = os.path.getsize('_demo.gif')
        print(f"   ✅ GIF 生成: _demo.gif ({gif_size/1024:.0f} KB)")

    # 提取音频
    print("\n🔊 提取音频...")
    result = run_ffmpeg([
        '-i', test_video, '-vn',
        '-acodec', 'libmp3lame', '-y', '_audio.mp3',
    ])
    if result['success']:
        audio_size = os.path.getsize('_audio.mp3')
        print(f"   ✅ 音频提取: _audio.mp3 ({audio_size/1024:.0f} KB)")

    # 清理
    print("\n🧹 清理测试文件...")
    for f in ['_test_demo.mp4', '_frame.jpg', '_converted.webm',
              '_demo.gif', '_audio.mp3']:
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass
    print("   ✅ 已清理")

    print("\n🎉 视频工具箱功能演示完成!")
    print("   支持: 信息查看 | 帧提取 | 格式转换 | 剪辑 | GIF | 音频提取")


if __name__ == '__main__':
    demo()
