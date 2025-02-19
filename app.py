import os
import cv2
import numpy as np
import time
import threading
import torch
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from flask_cors import CORS
from PIL import Image
import pytesseract
import easyocr
from paddleocr import PaddleOCR

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize OCR Models
paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", det_db_box_thresh=0.5, rec_algorithm="CRNN")
easyocr_reader = easyocr.Reader(["en", "ne"])

# Global variable to store progress
ocr_progress = {"status": "Idle", "progress": 0}
processing_lock = threading.Lock()


def enhance_image(image_path):
    """Deep Learning-Based Image Enhancement for OCR Accuracy"""
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    # Apply Super-Resolution using Deep Learning
    image = cv2.resize(image, (image.shape[1] * 4, image.shape[0] * 4), interpolation=cv2.INTER_CUBIC)

    # Remove Noise
    image = cv2.fastNlMeansDenoising(image, None, 30, 7, 21)

    # Apply CLAHE for Better Contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    image = clahe.apply(image)

    # Adaptive Thresholding
    image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 5)

    # Apply Sharpening Filter
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    image = cv2.filter2D(image, -1, sharpen_kernel)

    # Increase Contrast
    image = cv2.convertScaleAbs(image, alpha=1.5, beta=10)

    # Morphological Transformations to Improve Text Visibility
    kernel = np.ones((2, 2), np.uint8)
    image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)

    # Save Enhanced Image
    enhanced_path = os.path.join(app.config["UPLOAD_FOLDER"], "enhanced.png")
    cv2.imwrite(enhanced_path, image)

    return enhanced_path


def run_ocr(image_path, response_dict):
    """Runs Multi-Level OCR Extraction and Combines Results"""
    global ocr_progress

    try:
        with processing_lock:
            ocr_progress["status"] = "Enhancing Image for OCR..."
            ocr_progress["progress"] = 10
            enhanced_image_path = enhance_image(image_path)
            time.sleep(1)

            results = {}

            def run_tesseract():
                """Run Tesseract OCR"""
                ocr_progress["status"] = "Running Tesseract OCR..."
                ocr_progress["progress"] = 30
                results["tesseract"] = pytesseract.image_to_string(
                    Image.open(enhanced_image_path),
                    lang="eng+nep",
                    config="--oem 3 --psm 6"
                )

            def run_easyocr():
                """Run EasyOCR"""
                ocr_progress["status"] = "Running EasyOCR..."
                ocr_progress["progress"] = 60
                results["easyocr"] = "\n".join(
                    easyocr_reader.readtext(
                        enhanced_image_path, detail=0, contrast_ths=0.6, adjust_contrast=0.8
                    )
                )

            def run_paddleocr():
                """Run PaddleOCR"""
                ocr_progress["status"] = "Running PaddleOCR..."
                ocr_progress["progress"] = 80
                result = paddle_ocr.ocr(enhanced_image_path, cls=True)
                if result and result[0] is not None:
                    results["paddleocr"] = "\n".join([line[1][0] for line in result[0] if line])
                else:
                    results["paddleocr"] = ""

            # Run OCR in parallel threads
            t1 = threading.Thread(target=run_tesseract)
            t2 = threading.Thread(target=run_easyocr)
            t3 = threading.Thread(target=run_paddleocr)

            t1.start()
            t2.start()
            t3.start()

            t1.join()
            t2.join()
            t3.join()

            # Combine & Filter OCR Results
            extracted_text = filter_ocr_text(
                f"EasyOCR:\n{results['easyocr']}\n\n"
                f"Tesseract OCR (backup):\n{results['tesseract']}\n\n"
                f"PaddleOCR:\n{results['paddleocr']}"
            )

            response_dict["text"] = extracted_text
            ocr_progress["status"] = "Completed ✅"
            ocr_progress["progress"] = 100

    except Exception as e:
        response_dict["text"] = "❌ OCR Failed"
        ocr_progress["status"] = f"Error: {str(e)}"
        ocr_progress["progress"] = 0


def filter_ocr_text(ocr_text):
    """Post-Processing: Filters Unwanted Characters, Fixes Formatting"""
    cleaned_text = []
    for line in ocr_text.split("\n"):
        # Remove unwanted symbols
        line = line.replace("—", "").replace("•", "").strip()

        # Ensure line is meaningful
        if len(line) > 2:
            cleaned_text.append(line)

    return "\n".join(cleaned_text)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/crop_ocr", methods=["POST"])
def crop_ocr():
    """Handles Image Upload and Performs OCR"""
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
