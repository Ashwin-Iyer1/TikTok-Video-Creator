from dataclasses import dataclass
import json
import math
from pathlib import Path
import shutil
import subprocess
import threading
import time

FPS = 30
SIZES = {'540': (540, 960), '720': (720, 1280), '1080': (1080, 1920)}


class RenderError(ValueError):
    pass


def executable(name):
    path = shutil.which(name)
    if not path:
        raise RenderError(f'{name} is required on PATH. Install FFmpeg before rendering.')
    return path


def probe(path):
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in {'.mp4', '.mov', '.webm', '.mkv'}:
        raise RenderError('Choose a local MP4, MOV, WebM or MKV video.')
    try:
        result = subprocess.run([executable('ffprobe'), '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_format', '-show_streams', '-of', 'json', str(path)], capture_output=True, timeout=20)
    except subprocess.TimeoutExpired as exc:
        raise RenderError('Video metadata read timed out.') from exc
    if result.returncode:
        raise RenderError('Video metadata could not be read.')
    try:
        data = json.loads(result.stdout)
        formats = set(data.get('format', {}).get('format_name', '').split(','))
        if not formats.intersection({'mov', 'mp4', 'matroska', 'webm'}):
            raise RenderError('Only MP4/MOV and Matroska/WebM containers are supported.')
        streams = data.get('streams', [])
        video = next(stream for stream in streams if stream.get('codec_type') == 'video' and not stream.get('disposition', {}).get('attached_pic'))
        duration = float(video.get('duration') or data.get('format', {}).get('duration'))
        width, height = int(video['width']), int(video['height'])
    except (ValueError, TypeError, KeyError, StopIteration) as exc:
        raise RenderError('A finite video duration and dimensions are required.') from exc
    if not math.isfinite(duration) or not 1 / FPS <= duration <= 600:
        raise RenderError('Video duration must be between one frame and ten minutes.')
    if not 2 <= width <= 7680 or not 2 <= height <= 7680:
        raise RenderError('Video dimensions must be within 2–7680 pixels.')
    return {'duration': duration, 'width': width, 'height': height, 'audio': any(stream.get('codec_type') == 'audio' for stream in streams), 'name': path.name}


def number(value, name, minimum, maximum):
    if isinstance(value, bool):
        raise RenderError(f'{name} must be a number.')
    try:
        value = float(value)
    except (ValueError, TypeError) as exc:
        raise RenderError(f'{name} must be a number.') from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise RenderError(f'{name} must be between {minimum} and {maximum}.')
    return value


def plan(top, bottom, options):
    if not isinstance(options, dict):
        raise RenderError('Render options must be an object.')
    size = str(options.get('size', '720'))
    if size not in SIZES:
        raise RenderError('Choose a supported output size.')
    width, height = SIZES[size]
    clip_seconds = number(options.get('clip', 30), 'Clip length', 1, 180)
    share = number(options.get('share', 50), 'Top panel share', 25, 75)
    fit, audio, length = options.get('fit', 'crop'), options.get('audio', 'top'), options.get('length', 'top')
    if fit not in {'crop', 'contain'} or audio not in {'top', 'bottom', 'none'} or length not in {'top', 'shortest'}:
        raise RenderError('Unsupported layout, audio or duration mode.')
    duration = top['duration'] if length == 'top' else min(top['duration'], bottom['duration'])
    frames = math.floor(duration * FPS + 1e-6)
    clip_frames = round(clip_seconds * FPS)
    segments = [{'index': index + 1, 'startFrame': start, 'frames': min(clip_frames, frames - start), 'start': start / FPS, 'duration': min(clip_frames, frames - start) / FPS} for index, start in enumerate(range(0, frames, clip_frames))]
    if not segments or len(segments) > 60:
        raise RenderError('Plan needs 1–60 nonempty clips. Increase the clip length.')
    top_height = round(height * share / 100 / 2) * 2
    audio_present = audio != 'none' and (top if audio == 'top' else bottom)['audio']
    return {'schema': 'splitframe-plan/v1', 'width': width, 'height': height, 'topHeight': top_height, 'bottomHeight': height - top_height, 'fps': FPS, 'fit': fit, 'audio': audio if audio_present else 'none', 'requestedAudio': audio, 'length': length, 'bottomLoops': length == 'top' and duration > bottom['duration'], 'duration': frames / FPS, 'segments': segments}


def panel_filter(index, width, height, fit):
    mode = 'increase' if fit == 'crop' else 'decrease'
    size = f'scale={width}:{height}:force_original_aspect_ratio={mode}:force_divisible_by=2'
    frame = f'crop={width}:{height}' if fit == 'crop' else f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black'
    return f'[{index}:v:0]fps={FPS},{size},{frame},setsar=1,setpts=PTS-STARTPTS[v{index}]'


def command(top_path, bottom_path, bottom, recipe, segment, target):
    args = [executable('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-nostdin', '-n', '-threads', '2', '-protocol_whitelist', 'file,pipe', '-ss', f'{segment["start"]:.9f}', '-i', str(Path(top_path).resolve())]
    if recipe['length'] == 'top':
        args += ['-stream_loop', '-1']
    bottom_start = segment['start'] % bottom['duration'] if recipe['length'] == 'top' else segment['start']
    args += ['-protocol_whitelist', 'file,pipe', '-ss', f'{bottom_start:.9f}', '-i', str(Path(bottom_path).resolve())]
    filters = [panel_filter(0, recipe['width'], recipe['topHeight'], recipe['fit']), panel_filter(1, recipe['width'], recipe['bottomHeight'], recipe['fit']), '[v0][v1]vstack=inputs=2:shortest=1[out]']
    args += ['-filter_complex_threads', '2', '-filter_complex', ';'.join(filters), '-map', '[out]']
    if recipe['audio'] != 'none':
        args += ['-map', '0:a:0' if recipe['audio'] == 'top' else '1:a:0', '-af', 'apad', '-c:a', 'aac', '-b:a', '128k']
    else:
        args += ['-an']
    return args + ['-frames:v', str(segment['frames']), '-t', f'{segment["duration"]:.9f}', '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-map_metadata', '-1', str(target)]


def render(top_path, bottom_path, output, options, *, cancel=None, progress=None):
    top, bottom = probe(top_path), probe(bottom_path)
    recipe = plan(top, bottom, options)
    directory = Path(output).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    files = []
    for segment in recipe['segments']:
        if cancel and cancel.is_set():
            raise RenderError('Render cancelled. Completed clips remain in the output directory.')
        name = f'clip-{segment["index"]:03d}.mp4'
        partial = directory / f'clip-{segment["index"]:03d}.partial.mp4'
        if progress:
            progress(segment['index'] - 1, len(recipe['segments']))
        args = command(top_path, bottom_path, bottom, recipe, segment, partial)
        # File-backed stderr avoids pipe deadlock; logs stay in this render folder.
        with (directory / 'render.log').open('ab') as log:
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=log)
            started = time.monotonic()
            try:
                while process.poll() is None:
                    if (cancel and cancel.is_set()) or time.monotonic() - started > 300:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        raise RenderError('Render cancelled or exceeded the five-minute per-clip limit.')
                    time.sleep(0.1)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        if process.returncode:
            raise RenderError('FFmpeg could not render this clip. See the local render.log for diagnostics.')
        actual = probe(partial)
        if actual['width'] != recipe['width'] or actual['height'] != recipe['height'] or actual['audio'] != (recipe['audio'] != 'none') or abs(actual['duration'] - segment['duration']) > 1 / FPS + 0.01:
            raise RenderError('Rendered output did not match the planned dimensions or duration.')
        partial.rename(directory / name)
        files.append({'name': name, **segment, 'verifiedDuration': actual['duration'], 'audio': actual['audio']})
    manifest = {'schema': 'splitframe-render/v1', 'top': top, 'bottom': bottom, 'plan': recipe, 'files': files}
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if progress:
        progress(len(files), len(files))
    return manifest
