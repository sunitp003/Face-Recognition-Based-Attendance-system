"""Download the official OpenCV Zoo YuNet and SFace ONNX models."""
import os
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(ROOT, "models")
MODELS = {
    "face_detection_yunet_2023mar.onnx":
        "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
    "face_recognition_sface_2021dec.onnx":
        "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
}


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)
    for filename, url in MODELS.items():
        destination = os.path.join(MODEL_DIR, filename)
        if os.path.isfile(destination) and os.path.getsize(destination) > 100_000:
            print(f"Already present: {destination}")
            continue
        temporary = destination + ".download"
        print(f"Downloading {filename} ...")
        urllib.request.urlretrieve(url, temporary)
        if not os.path.isfile(temporary) or os.path.getsize(temporary) < 100_000:
            raise RuntimeError(f"Download appears incomplete: {filename}")
        os.replace(temporary, destination)
        print(f"Saved: {destination}")


if __name__ == "__main__":
    main()
