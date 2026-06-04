"""视频工具箱测试"""
import unittest
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from ffmpeg_wrapper import check_ffmpeg, get_ffmpeg_path, run_ffmpeg, probe_video
from video_info import get_info, format_duration, eval_fps
from video_edit import trim_video, extract_frame, convert_format
from gifmaker import make_gif


class TestFFmpegWrapper(unittest.TestCase):
    """测试核心包装"""
    def test_check_ffmpeg_returns_bool(self):
        result = check_ffmpeg()
        self.assertIsInstance(result, bool)

    def test_get_ffmpeg_path(self):
        path = get_ffmpeg_path()
        if path:
            self.assertTrue(os.path.exists(path) or path == 'ffmpeg')

    def test_probe_invalid_file(self):
        data = probe_video('nonexistent.mp4')
        self.assertIn('error', data)


class TestVideoInfo(unittest.TestCase):
    """测试视频信息提取"""
    def test_get_info_nonexistent(self):
        info = get_info('nonexistent.mp4')
        self.assertIn('error', info)

    def test_format_duration(self):
        self.assertIn('s', format_duration(5))
        self.assertIn('m', format_duration(120))
        self.assertIn('h', format_duration(4000))

    def test_eval_fps(self):
        self.assertAlmostEqual(eval_fps('30000/1001'), 29.97, delta=0.01)
        self.assertEqual(eval_fps('30/1'), 30.0)
        self.assertEqual(eval_fps(''), 0)


class TestVideoEdit(unittest.TestCase):
    """测试视频编辑"""
    def test_trim_nonexistent(self):
        result = trim_video('nonexistent.mp4', 'out.mp4',
                            '00:00:00', '00:00:10')
        self.assertFalse(result['success'])

    def test_convert_nonexistent(self):
        result = convert_format('nonexistent.mp4', 'out.mp4')
        self.assertFalse(result['success'])

    def test_extract_frame_nonexistent(self):
        result = extract_frame('nonexistent.mp4', 'frame.jpg', '00:00:01')
        self.assertFalse(result['success'])


class TestGifMaker(unittest.TestCase):
    """测试 GIF 生成"""
    def test_make_gif_nonexistent(self):
        result = make_gif('nonexistent.mp4', 'out.gif')
        self.assertFalse(result['success'])


class TestDemoFfprobeCheck(unittest.TestCase):
    """检查 ffprobe 是否可用（如果 ffmpeg 在就应该是）"""
    def test_ffprobe_exists(self):
        ffmpeg = get_ffmpeg_path()
        if ffmpeg:
            result = run_ffmpeg(['-version'])
            self.assertIsNotNone(result)
            self.assertTrue(result['success'])


if __name__ == '__main__':
    unittest.main()
