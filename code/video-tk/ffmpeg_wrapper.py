"""FFmpeg 核心包装 — 纯 subprocess 调用"""
import subprocess
import json
import os


def check_ffmpeg() -> bool:
    """检查系统是否安装了 ffmpeg"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_ffmpeg_path():
    """获取 ffmpeg 路径"""
    if os.name == 'nt':
        candidates = [
            'ffmpeg',
            r'C:\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        ]
    else:
        candidates = ['ffmpeg']

    for c in candidates:
        try:
            subprocess.run([c, '-version'], capture_output=True, timeout=3)
            return c
        except Exception:
            continue
    return None


def run_ffmpeg(args: list, timeout: int = 300) -> dict:
    """运行 ffmpeg 命令"""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg not found!\n"
            "Install: https://ffmpeg.org/download.html\n"
            "  Windows: choco install ffmpeg  or  winget install ffmpeg\n"
            "  macOS:   brew install ffmpeg\n"
            "  Linux:   apt install ffmpeg"
        )

    cmd = [ffmpeg] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=timeout
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def probe_video(filepath: str) -> dict:
    """使用 ffprobe 获取视频信息"""
    ffmpeg = get_ffmpeg_path()
    ffprobe = ffmpeg.replace('ffmpeg', 'ffprobe') if ffmpeg else 'ffprobe'

    try:
        result = subprocess.run(
            [ffprobe, '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', filepath],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {'error': result.stderr}
    except Exception as e:
        return {'error': str(e)}
