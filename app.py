import os
import cv2
import numpy as np
import time
import threading
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from flask_cors import CORS
from PIL import Image, ImageEnhance
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
paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", det_db_box_thresh=0.7, rec_algorithm="SVTR_LCNet")
easyocr_reader = easyocr.Reader(["en", "ne"])

# Global variable to store progress
ocr_progress = {"status": "Idle", "progress": 0}
processing_lock = threading.Lock()  # Prevent multiple OCR processes


def enhance_image(image_path):
    """Enhance the image to improve OCR accuracy."""
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    # Resize image (Super-Resolution)
    image = cv2.resize(image, (image.shape[1] * 4, image.shape[0] * 4), interpolation=cv2.INTER_CUBIC)

    # Noise Reduction
    image = cv2.fastNlMeansDenoising(image, None, 30, 7, 21)
    image = cv2.bilateralFilter(image, 9, 75, 75)

    # Adaptive Thresholding
    image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    # Histogram Equalization
    image = cv2.equalizeHist(image)

    # Increase Contrast
    pil_image = Image.fromarray(image)
    enhancer = ImageEnhance.Contrast(pil_image)
    image = np.array(enhancer.enhance(3))

    enhanced_path = os.path.join(app.config["UPLOAD_FOLDER"], "enhanced.png")
    cv2.imwrite(enhanced_path, image)
    return enhanced_path


def run_ocr(image_path, response_dict):
    """OCR Process in a separate thread with live progress updates."""
    global ocr_progress

    try:
        with processing_lock:  # Ensure only one OCR runs at a time
            ocr_progress["status"] = "Enhancing Image for OCR..."
            ocr_progress["progress"] = 10
            enhanced_image_path = enhance_image(image_path)
            time.sleep(1)

            ocr_progress["status"] = "Running Tesseract OCR..."
            ocr_progress["progress"] = 30
            text_tesseract = pytesseract.image_to_string(Image.open(enhanced_image_path), lang="eng+nep")
            time.sleep(1)

            ocr_progress["status"] = "Running EasyOCR..."
            ocr_progress["progress"] = 60
            text_easyocr = "\n".join(easyocr_reader.readtext(enhanced_image_path, detail=0))
            time.sleep(1)

            ocr_progress["status"] = "Running PaddleOCR..."
            ocr_progress["progress"] = 80
            result = paddle_ocr.ocr(enhanced_image_path, cls=True)

            text_paddleocr = ""
            if result and result[0] is not None:
                text_paddleocr = "\n".join([line[1][0] for line in result[0] if line])

            extracted_text = f"Tesseract OCR:\n{text_tesseract}\nEasyOCR:\n{text_easyocr}\nPaddleOCR:\n{text_paddleocr}"
            response_dict["text"] = extracted_text
            ocr_progress["status"] = "Completed ✅"
            ocr_progress["progress"] = 100
    except Exception as e:
        response_dict["text"] = "❌ OCR Failed"
        ocr_progress["status"] = f"Error: {str(e)}"
        ocr_progress["progress"] = 0


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
        return jsonify({"error": "OCR is already in progress. Please wait."}), 429  # Too Many Requests

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
    thread.join()  # Wait for OCR to finish

    return jsonify({"message": "OCR Completed", "text": response_dict["text"]})  # Ensure text is returned

@app.route("/ocr_progress", methods=["GET"])
def get_ocr_progress():
    """Endpoint to get live OCR progress."""
    return jsonify(ocr_progress)


if __name__ == "__main__":
    print("[INFO] Flask OCR Server is Running...")
    app.run(debug=True, threaded=True)
