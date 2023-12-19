import Progs.video_dl as video_dl 
import Progs.video_splitter as video_splitter

video_link = input("Video link (youtube or file location): ")

print(video_link.find("https"))
if video_link.find("https") == -1:
    video_splitter.main(video_link)
else:
    download_result = video_dl.main(video_link)
    video_splitter.main("clips\\video.mp4")
