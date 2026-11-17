# import cv2
# import os

# # def face_detect(path, roll, branch, batch, root):
# #     """
# #     Detects faces from images inside the student's roll number folder
# #     and saves processed face images into the correct dataset structure.

# #     Args:
# #         path (str): Path to the roll number folder containing images.
# #         roll (str): Student's roll number.
# #         branch (str): Student's branch.
# #         batch (str): Student's batch.
# #         root (str): Root directory of the project.

# #     Returns:
# #         int: 1 if face detection is successful.
# #     """
# #     print("🔍 Detecting faces in:", path)

# #     detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# #     # Ensure the target folder exists for processed images
# #     target_dir = os.path.join(root, "dataset", batch, branch, roll)
# #     os.makedirs(target_dir, exist_ok=True)

# #     images = os.listdir(path)
# #     print("📂 Found images:", images)

# #     temp = 0
# #     for img_name in images:
# #         img_path = os.path.join(path, img_name)

# #         try:
# #             image = cv2.imread(img_path)
# #             if image is None:
# #                 print(f"⚠️ Skipping invalid image: {img_path}")
# #                 continue

# #             gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
# #             faces = detector.detectMultiScale(gray, 1.3, 5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)

# #             for x, y, w, h in faces:
# #                 temp += 1
# #                 face_img = gray[y:y+h, x:x+w]
# #                 save_path = os.path.join(target_dir, f"{roll}_{temp}.jpg")
# #                 cv2.imwrite(save_path, face_img)
# #                 print(f"✅ Face detected and saved: {save_path}")

# #         except Exception as e:
# #             print(f"❌ Error processing {img_path}: {e}")
# #             continue

# #     return 1


# import cv2
# import os

# def face_detect(path, roll, branch, batch, root):
#     """
#     Detects faces from images inside the student's roll number folder
#     and saves processed face images into the correct dataset structure.

#     Args:
#         path (str): Path to the roll number folder containing images.
#         roll (str): Student's roll number.
#         branch (str): Student's branch.
#         batch (str): Student's batch.
#         root (str): Root directory of the project.

#     Returns:
#         int: 1 if face detection is successful.
#     """
#     print("🔍 Detecting faces in:", path)

#     detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

#     # Ensure the target folder exists for processed images
#     target_dir = os.path.join(root, "dataset", batch, branch, roll)
#     os.makedirs(target_dir, exist_ok=True)

#     # images = os.listdir(path)
#     # print("📂 Found images:", images)

#     # temp = 0
#     # for img_name in images:
#     #     # Skip non-image files
#     #     if not img_name.lower().endswith(('.jpg', '.jpeg', '.png')):
#     #         continue

#     #     img_path = os.path.join(path, img_name)

#     #     try:
#     #         image = cv2.imread(img_path)
#     #         if image is None:
#     #             print(f"⚠️ Skipping invalid image: {img_path}")
#     #             continue

#     #         # Resize image for better face detection
#     #         image = cv2.resize(image, (640, 480))
#     #         gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

#     #         faces = detector.detectMultiScale(gray, 1.3, 5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)

#     #         for x, y, w, h in faces:
#     #             temp += 1
#     #             face_img = gray[y:y+h, x:x+w]
#     #             save_path = os.path.join(target_dir, f"{roll}_{temp}.jpg")
#     #             cv2.imwrite(save_path, face_img)
#     #             print(f"✅ Face detected and saved: {save_path}")

#     #     except Exception as e:
#     #         print(f"❌ Error processing {img_path}: {e}")
#     #         continue




#     images = os.listdir(path)
#     print("📂 Found images:", images)

#     temp = 0
#     for img_name in images:
#         if not img_name.lower().endswith(('.jpg', '.jpeg', '.png')):
#             continue
    
#         img_path = os.path.join(path, img_name)
    
#         try:
#             image = cv2.imread(img_path)
#             if image is None:
#                 print(f"⚠️ Skipping invalid image: {img_path}")
#                 continue

#             image = cv2.resize(image, (640, 480))
#             gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
#             # Adjust minNeighbors and minSize for better accuracy
#             faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)
    
#             for x, y, w, h in faces:
#                 temp += 1
#                 face_img = gray[y:y+h, x:x+w]
#                 save_path = os.path.join(target_dir, f"{roll}_{temp}.jpg")
#                 cv2.imwrite(save_path, face_img)
#                 print(f"✅ Face detected and saved: {save_path}")
    
#         except Exception as e:
#             print(f"❌ Error processing {img_path}: {e}")
#             continue
    
#     return 1
    



import cv2
import os
import hashlib
import logging
import numpy as np

# Logging setup for better visibility of errors and skipped images
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def face_detect(path, roll, branch, batch, root):
    print(f"🔍 Detecting faces for: {roll}")

    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    target_dir = os.path.join(root, "dataset", batch, branch, roll)
    os.makedirs(target_dir, exist_ok=True)

    images = os.listdir(path)
    print("📁 Total images found:", len(images))

    temp = 0
    processed_hashes = set()

    for img_name in images:
        if not img_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue

        img_path = os.path.join(path, img_name)

        image = cv2.imread(img_path)
        if image is None:
            logging.error(f"❌ Couldn't read image: {img_path}")
            continue

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Detect faces
        faces = detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100),
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        if len(faces) == 0:
            logging.warning(f"⚠️ No face detected in: {img_name}")
            continue

        # Select the largest face (best chance it's the main face)
        largest_face = max(faces, key=lambda box: box[2] * box[3])
        x, y, w, h = largest_face

        # Add padding to avoid tight crops (optional)
        padding = 20
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)

        face_img = gray[y:y + h, x:x + w]
        face_img = cv2.resize(face_img, (150, 150))  # Standard size

        # Use hash to avoid duplicates
        face_hash = hashlib.md5(face_img.tobytes()).hexdigest()
        if face_hash in processed_hashes:
            logging.warning(f"⚠️ Duplicate face, skipping: {img_name}")
            continue

        processed_hashes.add(face_hash)

        temp += 1
        save_path = os.path.join(target_dir, f"{roll}_{temp}.jpg")
        cv2.imwrite(save_path, face_img)
        logging.info(f"✅ Saved: {save_path}")

    print(f"✅ Done. {temp} faces saved to: {target_dir}")
    return 1

def process_image(imagePath, padding=30):
    try:
        roll_no = extract_roll_no_from_path(imagePath)
        if roll_no is None:
            logging.warning(f"⚠️ Skipping: {imagePath} (No roll number found)")
            return None, None

        Id = int(roll_no)
        pilImage = Image.open(imagePath).convert("L")  # Convert image to grayscale
        imageNp = np.array(pilImage, 'uint8')

        # Load Haar Cascade for face detection
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        # Detect faces
        faces = face_cascade.detectMultiScale(imageNp, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30))

        if len(faces) > 0:
            # Use the first face detected (if multiple faces are found)
            for (x, y, w, h) in faces:
                # Ensure that padding doesn't cause the crop to go out of image bounds
                x1 = max(x - padding, 0)
                y1 = max(y - padding, 0)
                x2 = min(x + w + padding, imageNp.shape[1])
                y2 = min(y + h + padding, imageNp.shape[0])

                # Crop the face with added padding
                face_cropped = imageNp[y1:y2, x1:x2]

                # Resize the cropped face to a fixed size (200x200) for consistency
                face_resized = cv2.resize(face_cropped, (200, 200))

                return face_resized, Id

        logging.warning(f"⚠️ No face detected in: {imagePath}")
        return None, None
    except Exception as e:
        logging.error(f"❌ Error processing {imagePath}: {e}")
        return None, None

# Make sure to debug each step of your pipeline, check the roll number extraction, and make sure the dataset has proper face images.
