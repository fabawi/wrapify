import argparse
import cv2
import sounddevice as sd
import numpy as np

from wrapify.connect.wrapper import MiddlewareCommunicator

"""
Camera and Microphone listener + publisher

Here we demonstrate 
1. Using the Image and AudioChunk messages
2. Single return wrapper functionality in conjunction with synchronous callbacks
3. The spawning of multiple processes specifying different functionality for listeners and publishers


Run:
    # Alternative 1
    # On machine 1 (or process 1): The audio stream publishing
    python3 cam_mic.py --mode publish --stream audio
    # On machine 2 (or process 2): The video stream publishing
    python3 cam_mic.py --mode publish --stream video
    # On machine 3 (or process 3): The audio stream listening
    python3 cam_mic.py --mode listen --stream audio
    # On machine 4 (or process 4): The video stream publishing
    python3 cam_mic.py --mode listen --stream video
    
    # Alternative 2 (concurrent audio and video publishing)
    # On machine 1 (or process 1): The audio/video stream publishing
    python3 cam_mic.py --mode publish --stream audio video
    # On machine 2 (or process 2): The audio/video stream listening
    python3 cam_mic.py --mode listen --stream video video
"""


class CamMic(MiddlewareCommunicator):
    def __init__(self, *args, stream=("audio", "video"),
                 aud_rate=44100, aud_chunk=10000, aud_channels=1,
                 img_width=320, img_height=240, **kwargs):
        super(MiddlewareCommunicator, self).__init__()
        self.aud_rate = aud_rate
        self.aud_chunk = aud_chunk
        self.aud_channels = aud_channels
        self.img_width = img_width
        self.img_height = img_height

        if "audio" in stream:
            self.enable_audio = True
        else:
            self.enable_audio = False
        if "video" in stream:
            self.vid_cap = cv2.VideoCapture(0)
            self.enable_video = True
        else:
            self.enable_video = False

    @MiddlewareCommunicator.register("Image", "CamMic", "/cam_mic/cam_feed",
                                     carrier="", width="$img_width", height="$img_height", rgb=True)
    def collect_cam(self, img_width=320, img_height=240):
        if self.vid_cap.isOpened():
            # capture the video stream from the webcam
            grabbed, img = self.vid_cap.read()
            if not grabbed:
                img = np.random.random((img_width, img_height, 3)) * 255
        else:
            img = np.random.random((img_width, img_height, 3)) * 255
        return img,

    @MiddlewareCommunicator.register("AudioChunk", "CamMic", "/cam_mic/audio_feed",
                                     carrier="", rate="$aud_rate", chunk="$aud_chunk", channels="$aud_channels")
    def collect_mic(self, aud=None, aud_rate=44100, aud_chunk=int(44100/5), aud_channels=1):
        aud = aud, aud_rate
        return aud,

    def capture_cam_mic(self):
        if self.enable_audio:
            # capture the audio stream from the microphone
            with sd.InputStream(device=0, channels=self.aud_channels, callback=self.__mic_callback__,
                            blocksize=self.aud_chunk,
                            samplerate=self.aud_rate):
                while True:
                    pass
        elif self.enable_video:
            while True:
                self.collect_cam()

    def __mic_callback__(self, audio, frames, time, status):
        if self.enable_video:
            self.collect_cam(img_width=self.img_width, img_height=self.img_height)
        self.collect_mic(audio, aud_rate=self.aud_rate, aud_chunk=self.aud_chunk, aud_channels=self.aud_channels)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.vid_cap.release()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="publish", choices={"publish", "listen"}, help="The transmission mode")
    parser.add_argument("--stream", nargs="+", default=["video", "audio"], choices={"video", "audio"}, help="The streamed sensor data")
    parser.add_argument("--img-width", type=int, default=320, help="The image width")
    parser.add_argument("--img-height", type=int, default=240, help="The image height")
    parser.add_argument("--aud-rate", type=int, default=44100, help="The audio sampling rate")
    parser.add_argument("--aud-channels", type=int, default=1, help="The audio channels")
    parser.add_argument("--aud-chunk", type=int, default=10000, help="The transmitted audio chunk size")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    cam_mic = CamMic(stream=args.stream)
    if args.mode == "publish":
        cam_mic.activate_communication("collect_cam", mode="publish")
        cam_mic.activate_communication("collect_mic", mode="publish")
        cam_mic.capture_cam_mic()
    if args.mode == "listen":
        cam_mic.activate_communication("collect_cam", mode="listen")
        cam_mic.activate_communication("collect_mic", mode="listen")
        while True:
            if "audio" in args.stream:
                aud, = cam_mic.collect_mic(aud_rate=args.aud_rate, aud_chunk=args.aud_chunk, aud_channels=args.aud_channels)
            else:
                aud = None
            if "video" in args.stream:
                img, = cam_mic.collect_cam(img_width=args.img_width, img_height=args.img_height)
            else:
                img = None
            if img is not None:
                cv2.imshow("Received Image", img)
                cv2.waitKey(1)
            if aud is not None:
                print(aud)
                sd.play(aud[0].flatten(), samplerate=aud[1])
                sd.wait(1)
