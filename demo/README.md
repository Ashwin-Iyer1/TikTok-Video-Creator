# Synthetic media fixtures

Both videos were generated locally with FFmpeg 8.1. They contain test patterns, not third-party footage. `top.mp4` is eight seconds of 640×360 `testsrc2` with a 440 Hz synthetic tone; `bottom.mp4` is three seconds of 480×480 `testsrc`, silent. Both are 30 fps, H.264/yuv420p with fast-start metadata.

Generation commands (run in the repository root; `-n` refuses replacement):

```sh
ffmpeg -hide_banner -loglevel error -n -f lavfi -i testsrc2=size=640x360:rate=30 -f lavfi -i sine=frequency=440:sample_rate=48000 -t 8 -c:v libx264 -preset fast -crf 24 -pix_fmt yuv420p -c:a aac -movflags +faststart demo/top.mp4
ffmpeg -hide_banner -loglevel error -n -f lavfi -i testsrc=size=480x480:rate=30 -t 3 -c:v libx264 -preset fast -crf 24 -pix_fmt yuv420p -movflags +faststart demo/bottom.mp4
```

The different durations exercise bottom-source looping. No social account, online download, or personal media is used in automated verification.
