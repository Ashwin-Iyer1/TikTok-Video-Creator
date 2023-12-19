from pytube import YouTube
# from youtube_transcript_api import YouTubeTranscriptApi 

def main(video_link):

    yt = YouTube(video_link)
    video_streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc()
    print("Available Resolutions:")
    for i, stream in enumerate(video_streams):
        print(f"{i + 1}. Resolution: {stream.resolution}")
    selected_resolution_index = int(input("Enter the number corresponding to the resolution you want to download: ")) - 1
    selected_stream = video_streams[selected_resolution_index]
    selected_stream.download(filename="clips/video.mp4")
    return("Completed")

#Captions stuff, working but not needed until caption adder is working

# try:
#     find_v = video_link.find("v=")
# except ValueError:
#     find_v = video_link.find("be/")
# id = (video_link[find_v+2:])
# srt = YouTubeTranscriptApi.get_transcript(id)
# f = open("captions.txt", "w")
# f.write(str(srt))
