import cv2

def show_stream(frame):
    cv2.imshow("Stream", frame)
    cv2.waitKey(1)