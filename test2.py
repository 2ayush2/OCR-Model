import os
import cv2
import numpy as np
import time
import threading
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from flask_cors import CORS
import easyocr
from paddleocr import PaddleOCR
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize OCR Models
paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", det_db_box_thresh=0.5, rec_algorithm="CRNN")
easyocr_reader = easyocr.Reader(["en", "ne"])  # English + Nepali

# Load SuryaOCR models only once at startup
detection_predictor = DetectionPredictor()
recognition_predictor = RecognitionPredictor()

ocr_progress = {"status": "Idle", "progress": 0}
processing_lock = threading.Lock()

def enhance_image(image_path):
    """Enhances image for better OCR performance"""
    image = cv2.imread(image_path)
    if image is None:
        return image_path

    target_width = 1200
    aspect_ratio = target_width / image.shape[1]
    new_size = (target_width, int(image.shape[0] * aspect_ratio))
    image = cv2.resize(image, new_size, interpolation=cv2.INTER_LINEAR)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 5)

    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    enhanced_path = os.path.join(app.config["UPLOAD_FOLDER"], "enhanced.png")
    cv2.imwrite(enhanced_path, binary)
    return enhanced_path

def run_ocr_models(image_path, response_dict):
    """Runs OCR using EasyOCR, PaddleOCR, and SuryaOCR in parallel"""
    global ocr_progress
    try:
        with processing_lock:
            ocr_progress["status"] = "Enhancing Image for OCR..."
            ocr_progress["progress"] = 10
            enhanced_image_path = enhance_image(image_path)
            time.sleep(1)

            results = {"easyocr": "", "paddleocr": "", "suryaocr": ""}

            def run_easyocr():
                ocr_progress["status"] = "Running EasyOCR..."
                ocr_progress["progress"] = 30
                results["easyocr"] = "\n".join(easyocr_reader.readtext(enhanced_image_path, detail=0))

            def run_paddleocr():
                ocr_progress["status"] = "Running PaddleOCR..."
                ocr_progress["progress"] = 50
                result = paddle_ocr.ocr(enhanced_image_path, cls=True)
                if result and result[0]:
                    results["paddleocr"] = "\n".join([line[1][0] for line in result[0] if line])

            def run_suryaocr():
                ocr_progress["status"] = "Running SuryaOCR..."
                ocr_progress["progress"] = 70
                from PIL import Image
                image = Image.open(enhanced_image_path)
                predictions = recognition_predictor([image], [["en", "ne"]], detection_predictor)
                results["suryaocr"] = "\n".join([line.text for line in predictions[0].text_lines])

            threads = [
                threading.Thread(target=run_easyocr),
                threading.Thread(target=run_paddleocr),
                threading.Thread(target=run_suryaocr),
            ]
            
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            response_dict["results"] = results  # Store results separately
            ocr_progress["status"] = "Completed ✅"
            ocr_progress["progress"] = 100
    except Exception as e:
        response_dict["error"] = f"OCR Failed: {str(e)}"
        ocr_progress["status"] = f"Error: {str(e)}"
        ocr_progress["progress"] = 0

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/crop_ocr", methods=["POST"])
def crop_ocr():
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
    
    response_dict = {}
    thread = threading.Thread(target=run_ocr_models, args=(filepath, response_dict))
    thread.start()
    thread.join()
    
    return jsonify({"message": "OCR Completed", "results": response_dict.get("results", {})})

@app.route("/ocr_progress", methods=["GET"])
def get_ocr_progress():
    return jsonify(ocr_progress)

if __name__ == "__main__":
    print("[INFO] Flask OCR Server is Running...")
    app.run(debug=True, threaded=True)
