from moviepy.editor import *

def main():

    top_video = VideoFileClip(filename="clips\\top.mp4")
    bottom_video = VideoFileClip(filename="clips\\bottom_cut.mp4")
    bottom_video = bottom_video.without_audio()

    clips = [[top_video],
             [bottom_video]]

    final_clip = clips_array(clips)
    final_clip.write_videofile("clips/merged.mp4")

