from moviepy.editor import *
import math
def main(vid_loc):

    full_video = (vid_loc)

    clip = VideoFileClip(full_video)
    video_length = clip.duration
    print(video_length)
    clipped_length = input("Video length: ")
    clipped_length = int(clipped_length)
    amt_clips = math.floor(video_length / clipped_length)

    for i in range(amt_clips+1):
        if clipped_length * (i + 1) > video_length:
            start_time = i * clipped_length
            end_time = video_length
            clip = VideoFileClip(full_video).subclip(start_time, end_time)
            clip.write_videofile("clips/clip" + str(i) + ".mp4")
            print("Clip " + str(i) + " created")
        else:
            start_time = i * clipped_length
            end_time = (i + 1) * clipped_length
            clip = VideoFileClip(full_video).subclip(start_time, end_time)
            clip.write_videofile("clips/clip" + str(i+1) + ".mp4")
            print("Clip " + str(i) + " created")

