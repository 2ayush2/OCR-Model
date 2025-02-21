import os
import cv2
import numpy as np
import time
import threading
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from flask_cors import CORS
from PIL import Image
import easyocr
from paddleocr import PaddleOCR
import torch
from torchvision import transforms
from torchvision.models import vgg19
import tensorflow as tf

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize OCR Models
paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", det_db_box_thresh=0.5, rec_algorithm="CRNN")
easyocr_reader = easyocr.Reader(["en", "ne"])  # English + Nepali

# Global variable to store progress
ocr_progress = {"status": "Idle", "progress": 0}
processing_lock = threading.Lock()


def upscale_image(image):
    """Performs Super-Resolution using Deep Learning (ESRGAN)"""
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    model_path = "ESPCN_x4.pb"  # Ensure the file is correctly placed
    sr.readModel("ESPCN_x4.pb")  # Downloaded model
    sr.setModel("espcn", 4)  # Using ESRGAN x4 upscale
    upscaled = sr.upsample(image)
    return upscaled


def preprocess_image(image_path):
    """Applies advanced preprocessing techniques for OCR accuracy"""
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"⚠️ Error: Could not read image {image_path}")
        return image_path  

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Super-Resolution to enhance blurry text
    gray = upscale_image(gray)

    # Remove Noise
    gray = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)

    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Adaptive Thresholding for better text detection
    gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 5)

    # Convert grayscale result to 3-channel image
    processed_image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # Save the processed image
    enhanced_path = os.path.join(app.config["UPLOAD_FOLDER"], "enhanced.png")
    cv2.imwrite(enhanced_path, processed_image)

    return enhanced_path


def run_ocr(image_path, response_dict):
    """Runs OCR on the cropped or full image and selects the most accurate output"""
    global ocr_progress

    try:
        with processing_lock:
            ocr_progress["status"] = "Processing Image..."
            ocr_progress["progress"] = 10
            enhanced_image_path = preprocess_image(image_path)
            time.sleep(1)

            easy_text, paddle_text = None, None

            def run_easyocr():
                """Run EasyOCR for Nepali + English"""
                nonlocal easy_text
                ocr_progress["status"] = "Running EasyOCR..."
                ocr_progress["progress"] = 50
                easy_text = easyocr_reader.readtext(enhanced_image_path, detail=0)

            def run_paddleocr():
                """Run PaddleOCR"""
                nonlocal paddle_text
                ocr_progress["status"] = "Running PaddleOCR..."
                ocr_progress["progress"] = 80
                result = paddle_ocr.ocr(enhanced_image_path, cls=True)
                if result and result[0] is not None:
                    paddle_text = [line[1][0] for line in result[0] if line]

            # Run OCR in parallel
            t1 = threading.Thread(target=run_easyocr)
            t2 = threading.Thread(target=run_paddleocr)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            # Selecting the best-structured text result
            extracted_text = None
            if easy_text and len(easy_text) > len(paddle_text or ""):
                extracted_text = "\n".join(easy_text)
            else:
                extracted_text = "\n".join(paddle_text or [])

            # Ensure proper formatting and remove unwanted numbers
            extracted_text = filter_ocr_text(extracted_text)

            response_dict["text"] = extracted_text
            ocr_progress["status"] = "Completed ✅"
            ocr_progress["progress"] = 100

    except Exception as e:
        response_dict["text"] = "❌ OCR Failed"
        ocr_progress["status"] = f"Error: {str(e)}"
        ocr_progress["progress"] = 0


def filter_ocr_text(ocr_text):
    """Filters unwanted symbols & formats OCR output correctly"""
    cleaned_text = []
    seen_lines = set()
    
    for line in ocr_text.split("\n"):
        line = line.strip()

        # Remove lines with only numbers (Unwanted detections)
        if line.isdigit():
            continue  

        if line and line not in seen_lines:  # Remove duplicates
            seen_lines.add(line)
            cleaned_text.append(line)

    return "\n".join(cleaned_text)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/crop_ocr", methods=["POST"])
def crop_ocr():
    """Handles Cropped Image Upload and Performs OCR"""
    global ocr_progress

    if "image" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    if processing_lock.locked():
        return jsonify({"error": "OCR is already in progress. Please wait."}), 429

    file = request.files["image"]
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    ocr_progress["status"] = "Starting OCR..."
    ocr_progress["progress"] = 5

    # Run OCR in a separate thread
    response_dict = {"text": ""}
    thread = threading.Thread(target=run_ocr, args=(filepath, response_dict))
    thread.start()
    thread.join()

    return jsonify({"message": "OCR Completed", "text": response_dict["text"]})


@app.route("/ocr_progress", methods=["GET"])
def get_ocr_progress():
    """Endpoint to get live OCR progress."""
    return jsonify(ocr_progress)


if __name__ == "__main__":
    print("[INFO] Flask OCR Server is Running...")
    app.run(debug=True, threaded=True)
