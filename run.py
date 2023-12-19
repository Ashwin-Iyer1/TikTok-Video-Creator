import Progs.video_dl as video_dl 
import Progs.video_splitter as video_splitter
import Progs.resize as resize
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from moviepy.editor import *

video_link = input("Video link for top video(youtube or file location): ")
bottom_video_link = input("Video link for bottom video(youtube or file location): ")
length = input("Each clip length: ")


if bottom_video_link.find("https") != -1:
    video_dl.main(bottom_video_link, "bottom")
if video_link.find("https") != -1:
    video_dl.main(video_link, "top")


top_mov = VideoFileClip("clips/top.mp4")
bottom_mov = VideoFileClip("clips/bottom.mp4")


#compare video lengths
print("Cutting videos...")
top_duration = top_mov.duration
print(top_duration)
bottom_duration = bottom_mov.duration
print(bottom_duration)
if top_duration < bottom_duration:
    print("Shortening Bottom Video...")
    ffmpeg_extract_subclip("clips/bottom.mp4", 0, top_duration, targetname="clips/bottom_cut.mp4")
elif top_duration > bottom_duration:
    print("Looping Bottom Video...")
    num_repeats = int(top_duration / bottom_duration) + 1
    # Create a looped version of the bottom video
    looped_bottom = concatenate_videoclips([bottom_mov] * num_repeats, method="compose").subclip(0, top_duration)
    #concatenate all bottom_mov clips
    looped_bottom.write_videofile("clips/bottom_cut.mp4", codec="libx264", audio_codec="aac")

print("Resizing videos...")
resize.main()

print("Splitting Videos...")
video_splitter.main("clips/merged.mp4", "FinishedClip", length)