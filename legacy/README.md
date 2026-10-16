# Historical implementation

These source snapshots are inert `.py.txt` files retained for comparison with the original MoviePy/pytube experiment. They are not imported or executed by Splitframe. The original workflow used fixed paths, failed when equal-length inputs did not create `bottom_cut.mp4`, and generated an empty final clip at exact segment boundaries. The caption experiment did not preserve audio correctly.

The maintained `run.py` entry point now uses `splitframe/`. It supports local videos, real layout preview, explicit audio selection, frame-based planning and verified FFmpeg outputs. Remote video download, social uploading and captions are not part of the maintained feature set. The original implementation remains available in Git history.
