"""视频信息提取"""
import os
from ffmpeg_wrapper import probe_video


def eval_fps(fps_str: str) -> float:
    """解析 FPS 字符串，如 '30000/1001' → 29.97"""
    try:
        if '/' in fps_str:
            n, d = fps_str.split('/')
            return round(float(n) / float(d), 2)
        return float(fps_str)
    except Exception:
        return 0


def format_duration(seconds: float) -> str:
    """格式化时长"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h}h{m:02d}m{s:04.1f}s"
    elif m > 0:
        return f"{m}m{s:04.1f}s"
    return f"{s:.1f}s"


def get_info(filepath: str) -> dict:
    """获取视频详细信息"""
    if not os.path.exists(filepath):
        return {'error': f'File not found: {filepath}'}

    data = probe_video(filepath)
    if 'error' in data:
        return data

    info = {
        'filename': os.path.basename(filepath),
        'size_mb': os.path.getsize(filepath) / (1024 * 1024),
    }

    # 格式信息
    if 'format' in data:
        fmt = data['format']
        info.update({
            'duration_s': float(fmt.get('duration', 0)),
            'bitrate_kbps': int(fmt.get('bit_rate', 0)) // 1000,
            'format_name': fmt.get('format_name', ''),
        })

    # 流信息
    for stream in data.get('streams', []):
        codec = stream.get('codec_type', '')
        if codec == 'video':
            info['video'] = {
                'codec': stream.get('codec_name', ''),
                'width': stream.get('width', 0),
                'height': stream.get('height', 0),
                'fps': eval_fps(stream.get('r_frame_rate', '0/1')),
                'bitrate': int(stream.get('bit_rate', 0)) // 1000,
            }
        elif codec == 'audio':
            if 'audio' not in info:
                info['audio'] = []
            info['audio'].append({
                'codec': stream.get('codec_name', ''),
                'sample_rate': stream.get('sample_rate', 0),
                'channels': stream.get('channels', 0),
            })

    return info


def print_info(filepath: str):
    """打印视频信息"""
    info = get_info(filepath)
    if 'error' in info:
        print(f"❌ {info['error']}")
        return

    print(f"📹 {info['filename']}")
    print(f"   大小: {info['size_mb']:.1f} MB")
    print(f"   时长: {format_duration(info['duration_s'])}")
    print(f"   格式: {info['format_name']}")
    print(f"   码率: {info['bitrate_kbps']} kbps")

    if 'video' in info:
        v = info['video']
        print(f"\n🎬 视频流:")
        print(f"   编码: {v['codec']}")
        print(f"   分辨率: {v['width']}x{v['height']}")
        print(f"   FPS: {v.get('fps', 'N/A')}")
        if v.get('bitrate'):
            print(f"   视频码率: {v['bitrate']} kbps")

    if 'audio' in info:
        print(f"\n🔊 音频流:")
        for a in info['audio']:
            print(f"   编码: {a['codec']}")
            print(f"   采样率: {a['sample_rate']} Hz")
            print(f"   声道: {a['channels']}")
