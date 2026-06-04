"""GIF 生成器"""
import os
from ffmpeg_wrapper import run_ffmpeg


def make_gif(input_path: str, output_path: str = 'output.gif',
             start: str = "00:00:00", duration: str = "3",
             width: int = 480, fps: int = 10) -> dict:
    """从视频片段生成高质量 GIF（两步法：调色板生成 + GIF 生成）"""
    if not os.path.exists(input_path):
        return {'success': False, 'error': f'File not found: {input_path}'}

    out_dir = os.path.dirname(output_path) or '.'
    palette_path = os.path.join(out_dir, '_palette.png')

    # 第一步：生成调色板
    palette_args = [
        '-i', input_path,
        '-ss', start,
        '-t', duration,
        '-vf', f'fps={fps},scale={width}:-1:flags=lanczos,palettegen=stats_mode=diff',
        '-y', palette_path,
    ]

    result = run_ffmpeg(palette_args)
    if not result['success']:
        return result

    # 第二步：用调色板生成 GIF
    gif_args = [
        '-i', input_path,
        '-i', palette_path,
        '-ss', start,
        '-t', duration,
        '-lavfi',
        f'fps={fps},scale={width}:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5',
        '-y', output_path,
    ]

    result = run_ffmpeg(gif_args)

    # 清理临时调色板
    try:
        if os.path.exists(palette_path):
            os.remove(palette_path)
    except Exception:
        pass

    return result


def make_simple_gif(input_path: str, output_path: str = 'simple.gif',
                    duration: str = "3", width: int = 480,
                    fps: int = 10, max_colors: int = 128) -> dict:
    """简单版 GIF（一步法，内嵌调色板，适合快速预览）"""
    if not os.path.exists(input_path):
        return {'success': False, 'error': f'File not found: {input_path}'}

    args = [
        '-i', input_path,
        '-t', duration,
        '-vf',
        f'scale={width}:-1,fps={fps},split[s0][s1];'
        f'[s0]palettegen=max_colors={max_colors}[p];[s1][p]paletteuse',
        '-y', output_path,
    ]
    return run_ffmpeg(args)
