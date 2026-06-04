"""视频编辑操作"""
import os
from ffmpeg_wrapper import run_ffmpeg


def trim_video(input_path: str, output_path: str,
               start: str = "00:00:00", duration: str = None,
               end: str = None) -> dict:
    """剪辑视频片段"""
    if not os.path.exists(input_path):
        return {'success': False, 'error': f'File not found: {input_path}'}

    args = ['-i', input_path, '-ss', start]

    if duration:
        args.extend(['-t', duration])
    elif end:
        args.extend(['-to', end])

    args.extend(['-c', 'copy', '-y', output_path])
    return run_ffmpeg(args)


def extract_frames(input_path: str, output_dir: str,
                   fps: float = 1, quality: int = 3) -> dict:
    """提取帧为图片"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_pattern = os.path.join(output_dir, 'frame_%04d.jpg')
    args = [
        '-i', input_path,
        '-vf', f'fps={fps}',
        '-q:v', str(quality),
        '-y', output_pattern,
    ]
    return run_ffmpeg(args)


def extract_frame(input_path: str, output_path: str,
                  time: str = "00:00:01") -> dict:
    """提取单帧"""
    if not os.path.exists(input_path):
        return {'success': False, 'error': f'File not found: {input_path}'}

    args = [
        '-i', input_path,
        '-ss', time,
        '-vframes', '1',
        '-y', output_path,
    ]
    return run_ffmpeg(args)


def convert_format(input_path: str, output_path: str,
                   codec: str = None, crf: int = 23,
                   preset: str = 'medium') -> dict:
    """格式转换"""
    if not os.path.exists(input_path):
        return {'success': False, 'error': f'File not found: {input_path}'}

    args = ['-i', input_path]

    if codec:
        args.extend(['-c:v', codec])
    else:
        ext = os.path.splitext(output_path)[1].lower()
        if ext == '.mp4':
            args.extend(['-c:v', 'libx264'])
        elif ext == '.webm':
            args.extend(['-c:v', 'libvpx'])
        elif ext == '.avi':
            args.extend(['-c:v', 'mpeg4'])

    args.extend(['-crf', str(crf), '-preset', preset, '-y', output_path])
    return run_ffmpeg(args)


def resize_video(input_path: str, output_path: str,
                 width: int = 720) -> dict:
    """缩放视频"""
    args = [
        '-i', input_path,
        '-vf', f'scale={width}:-2',
        '-c:v', 'libx264',
        '-crf', '23',
        '-preset', 'medium',
        '-y', output_path,
    ]
    return run_ffmpeg(args)


def extract_audio(input_path: str, output_path: str) -> dict:
    """提取音频"""
    args = [
        '-i', input_path,
        '-vn',
        '-acodec', 'libmp3lame' if output_path.endswith('.mp3') else 'copy',
        '-y', output_path,
    ]
    return run_ffmpeg(args)
