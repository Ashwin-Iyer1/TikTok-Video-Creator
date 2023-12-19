import cv2
import ast
import math

video = cv2.VideoCapture("video.mp4")

fourcc = cv2.VideoWriter_fourcc(*'XVID')
result = cv2.VideoWriter('filename.mp4', fourcc, math.ceil(video.get(cv2.CAP_PROP_FPS)), 
                         (int(video.get(3)), int(video.get(4))))

# Load audio
audio = cv2.VideoCapture("video.mp4")

with open('captions.txt', 'r') as file:
    file_content = file.read()

parsed_data = ast.literal_eval(file_content)
for caption in parsed_data:
    print(caption['text'] + " " + str(caption['start']))

try:
    for i in range(len(parsed_data)):
        start_frame = int(math.ceil(parsed_data[i]['start'] * video.get(cv2.CAP_PROP_FPS)))
        end_frame = int(math.ceil(parsed_data[i + 1]['start'] * video.get(cv2.CAP_PROP_FPS))) if i + 1 < len(parsed_data) else int(video.get(cv2.CAP_PROP_FRAME_COUNT))

        for frame_num in range(start_frame, end_frame):
            video.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = video.read()

            if not ret:
                break

            cv2.putText(frame, parsed_data[i]['text'], (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            result.write(frame)

            # Read and write audio frame
            ret_audio, frame_audio = audio.read()

            if not ret_audio:
                break

            result.write(frame_audio)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

except IndexError:
    print("Done")
finally:
    video.release()
    audio.release()
    result.release()
    cv2.destroyAllWindows()
