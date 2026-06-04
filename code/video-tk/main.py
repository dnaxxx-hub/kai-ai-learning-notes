#!/usr/bin/env python3
"""视频工具箱 CLI"""
import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(__file__))

from ffmpeg_wrapper import get_ffmpeg_path
from video_info import print_info
from video_edit import (
    trim_video, extract_frames, extract_frame,
    convert_format, resize_video, extract_audio
)
from gifmaker import make_gif


def build_parser():
    """构建参数解析器"""
    parser = argparse.ArgumentParser(description='视频工具箱')
    sub = parser.add_subparsers(dest='command', required=True)

    p_info = sub.add_parser('info', help='查看视频信息')
    p_info.add_argument('input', help='输入文件')

    p_trim = sub.add_parser('trim', help='剪辑片段')
    p_trim.add_argument('input')
    p_trim.add_argument('-o', '--output', default='trimmed.mp4')
    p_trim.add_argument('-s', '--start', default='00:00:00')
    p_trim.add_argument('-d', '--duration')
    p_trim.add_argument('-e', '--end')

    p_frames = sub.add_parser('frames', help='提取帧')
    p_frames.add_argument('input')
    p_frames.add_argument('-o', '--output', default='frames')
    p_frames.add_argument('--fps', type=float, default=1)
    p_frames.add_argument('--quality', type=int, default=3)

    p_frame = sub.add_parser('frame', help='提取单帧')
    p_frame.add_argument('input')
    p_frame.add_argument('-o', '--output', default='frame.jpg')
    p_frame.add_argument('-t', '--time', default='00:00:01')

    p_conv = sub.add_parser('convert', help='格式转换')
    p_conv.add_argument('input')
    p_conv.add_argument('-o', '--output', default='output.mp4')
    p_conv.add_argument('--codec')
    p_conv.add_argument('--crf', type=int, default=23)

    p_resize = sub.add_parser('resize', help='缩放')
    p_resize.add_argument('input')
    p_resize.add_argument('-o', '--output', default='resized.mp4')
    p_resize.add_argument('-w', '--width', type=int, default=720)

    p_audio = sub.add_parser('audio', help='提取音频')
    p_audio.add_argument('input')
    p_audio.add_argument('-o', '--output', default='audio.mp3')

    p_gif = sub.add_parser('gif', help='生成 GIF')
    p_gif.add_argument('input')
    p_gif.add_argument('-o', '--output', default='output.gif')
    p_gif.add_argument('-s', '--start', default='00:00:00')
    p_gif.add_argument('-d', '--duration', default='3')
    p_gif.add_argument('-w', '--width', type=int, default=480)
    p_gif.add_argument('--fps', type=int, default=10)

    return parser


def check_ffmpeg_available():
    """检查并提示 FFmpeg 安装"""
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        print("❌ FFmpeg not found!")
        print("   Install: https://ffmpeg.org/download.html")
        print("   Windows: choco install ffmpeg")
        print("   macOS:   brew install ffmpeg")
        print("   Linux:   apt install ffmpeg")
        sys.exit(1)
    return ffmpeg_path


def main():
    parser = build_parser()
    args = parser.parse_args()

    # info 命令不需要 ffmpeg 本地检查（用 ffprobe），但最终还是要
    ffmpeg_path = check_ffmpeg_available()
    if args.command in ('trim', 'frames', 'frame', 'convert',
                        'resize', 'audio', 'gif'):
        print(f"✅ FFmpeg found: {ffmpeg_path}")

    result = None

    if args.command == 'info':
        print_info(args.input)
    elif args.command == 'trim':
        result = trim_video(args.input, args.output,
                            args.start, args.duration, args.end)
    elif args.command == 'frames':
        result = extract_frames(args.input, args.output,
                                args.fps, args.quality)
    elif args.command == 'frame':
        result = extract_frame(args.input, args.output, args.time)
    elif args.command == 'convert':
        result = convert_format(args.input, args.output,
                                args.codec, args.crf)
    elif args.command == 'resize':
        result = resize_video(args.input, args.output, args.width)
    elif args.command == 'audio':
        result = extract_audio(args.input, args.output)
    elif args.command == 'gif':
        result = make_gif(args.input, args.output,
                          args.start, args.duration, args.width, args.fps)

    if result is not None:
        if result['success']:
            print(f"✅ {args.command}: {args.input} → {args.output}")
        else:
            err = result.get('error') or result.get('stderr', 'Unknown error')
            print(f"❌ {args.command}: {err}")


if __name__ == '__main__':
    main()
