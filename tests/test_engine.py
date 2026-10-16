import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

from splitframe.engine import RenderError, command, plan, probe, render

ROOT = Path(__file__).resolve().parents[1]


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.top = {'duration': 8, 'audio': True}
        self.bottom = {'duration': 3, 'audio': False}

    def test_exact_multiple_has_no_empty_tail(self):
        recipe = plan(self.top, self.bottom, {'clip': 4})
        self.assertEqual([s['frames'] for s in recipe['segments']], [120, 120])
        self.assertTrue(recipe['bottomLoops'])

    def test_partial_tail_covers_every_frame_once(self):
        recipe = plan({'duration': 8.1, 'audio': False}, self.bottom, {'clip': 3})
        self.assertEqual([s['frames'] for s in recipe['segments']], [90, 90, 63])
        self.assertEqual([s['startFrame'] for s in recipe['segments']], [0, 90, 180])

    def test_equal_sources_and_shortest_duration(self):
        self.assertFalse(plan(self.top, self.top, {})['bottomLoops'])
        self.assertEqual(plan(self.top, self.bottom, {'length': 'shortest'})['duration'], 3)

    def test_audio_and_even_dimensions(self):
        recipe = plan(self.top, self.bottom, {'audio': 'bottom', 'share': 53, 'size': '540'})
        self.assertEqual(recipe['audio'], 'none')
        self.assertEqual(recipe['topHeight'] % 2, 0)
        self.assertEqual(recipe['topHeight'] + recipe['bottomHeight'], 960)

    def test_invalid_or_unbounded_options(self):
        for options in [{'clip': 0}, {'clip': 'NaN'}, {'share': True}, {'share': 99}, {'size': '8k'}, {'fit': 'injected'}, {'audio': 'mixed'}, {'length': 'infinite'}]:
            with self.assertRaises(RenderError):
                plan(self.top, self.bottom, options)
        with self.assertRaises(RenderError):
            plan({'duration': 600, 'audio': False}, self.bottom, {'clip': 1})

    def test_command_is_argument_vector_with_loop_and_literal_paths(self):
        recipe = plan(self.top, self.bottom, {'clip': 4, 'fit': 'contain'})
        args = command(ROOT / 'demo/top.mp4', ROOT / 'demo/bottom.mp4', self.bottom, recipe, recipe['segments'][1], Path('output ; not a shell.mp4'))
        self.assertIn('-stream_loop', args)
        self.assertEqual(args[-1], 'output ; not a shell.mp4')
        self.assertIn('pad=720:640', args[args.index('-filter_complex') + 1])


class RenderTests(unittest.TestCase):
    def test_real_demo_renders_audio_and_two_exact_clips(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'render'
            result = render(ROOT / 'demo/top.mp4', ROOT / 'demo/bottom.mp4', out, {'clip': 4, 'size': '540'})
            self.assertEqual(len(result['files']), 2)
            for file in result['files']:
                meta = probe(out / file['name'])
                self.assertEqual((meta['width'], meta['height']), (540, 960))
                self.assertTrue(meta['audio'])
                self.assertAlmostEqual(meta['duration'], 4, places=2)
                count = subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', str(out / file['name'])], text=True).strip()
                self.assertEqual(count, '120')
            self.assertTrue((out / 'manifest.json').exists())
            with self.assertRaises(FileExistsError):
                render(ROOT / 'demo/top.mp4', ROOT / 'demo/bottom.mp4', out, {})

    def test_contain_has_black_bars_and_correct_panel_colors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, color in [('top', 'red'), ('bottom', 'blue')]:
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'color={color}:s=320x180:r=30', '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(root / (name + '.mp4'))], check=True)
            output = root / 'result'
            render(root / 'top.mp4', root / 'bottom.mp4', output, {'size': '540', 'fit': 'contain', 'audio': 'none'})
            pixels = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(output / 'clip-001.mp4'), '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
            def pixel(x, y):
                index = (y * 540 + x) * 3
                return pixels[index:index + 3]
            self.assertLess(max(pixel(270, 10)), 8)
            self.assertGreater(pixel(270, 240)[0], 230)
            self.assertGreater(pixel(270, 720)[2], 230)
            self.assertFalse(probe(output / 'clip-001.mp4')['audio'])

    def test_cancelled_render_never_publishes_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            event = threading.Event(); event.set()
            out = Path(directory) / 'cancelled'
            with self.assertRaises(RenderError):
                render(ROOT / 'demo/top.mp4', ROOT / 'demo/bottom.mp4', out, {}, cancel=event)
            self.assertFalse((out / 'manifest.json').exists())

    def test_inflight_cancellation_stops_encoder(self):
        with tempfile.TemporaryDirectory() as directory:
            event = threading.Event()
            out = Path(directory) / 'cancelled'
            with self.assertRaises(RenderError):
                render(ROOT / 'demo/top.mp4', ROOT / 'demo/bottom.mp4', out, {}, cancel=event, progress=lambda *_: event.set())
            self.assertFalse((out / 'manifest.json').exists())

    def test_bad_media_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'bad.mp4'
            source.write_text('not a video')
            with self.assertRaises(RenderError):
                probe(source)


if __name__ == '__main__':
    unittest.main()
