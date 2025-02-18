import os
import cv2
import numpy as np
from flask import Flask, request, render_template, jsonify
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

# Initialize PaddleOCR with correct language settings
ocr_model = PaddleOCR(use_angle_cls=True, lang="en")

def enhance_image(image_path):
    """Preprocess image to enhance readability before OCR."""
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)

    # Apply Super-Resolution (AI-Based)
    image = cv2.resize(image, (image.shape[1] * 3, image.shape[0] * 3), interpolation=cv2.INTER_CUBIC)

    # Noise Reduction (Bilateral Filter)
    image = cv2.bilateralFilter(image, 9, 75, 75)

    # Adaptive Thresholding
    image = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

    # Contrast Enhancement
    pil_image = Image.fromarray(image)
    enhancer = ImageEnhance.Contrast(pil_image)
    image = np.array(enhancer.enhance(2.5))  # Increase contrast

    enhanced_path = os.path.join(app.config["UPLOAD_FOLDER"], "enhanced.png")
    cv2.imwrite(enhanced_path, image)
    return enhanced_path

def extract_text(filepath):
    """Extract text using multiple OCR engines with retries and enhancements."""
    print("[INFO] Enhancing Image for OCR...")
    enhanced_image = enhance_image(filepath)

    print("[INFO] Running Tesseract OCR...")
    text_tesseract = pytesseract.image_to_string(Image.open(enhanced_image), config="--oem 3 --psm 6", lang="eng+nep")

    print("[INFO] Running EasyOCR...")
    reader = easyocr.Reader(["en", "ne"])
    text_easyocr = "\n".join(reader.readtext(enhanced_image, detail=0))

    print("[INFO] Running PaddleOCR...")
    result = ocr_model.ocr(enhanced_image, cls=True)

    text_paddleocr = ""
    if result and result[0] is not None:
        text_paddleocr = "\n".join([line[1][0] for line in result[0] if line])

    # Retry with different enhancements if text is not extracted properly
    if not text_tesseract.strip() and not text_easyocr.strip() and not text_paddleocr.strip():
        print("[WARNING] No text detected. Retrying with modified preprocessing...")
        text_tesseract = pytesseract.image_to_string(Image.open(enhanced_image), config="--oem 3 --psm 4", lang="eng+nep")

    if not text_tesseract.strip() and not text_easyocr.strip() and not text_paddleocr.strip():
        return "❌ No text detected. Try enhancing the image manually."

    return f"Tesseract OCR:\n{text_tesseract}\nEasyOCR:\n{text_easyocr}\nPaddleOCR:\n{text_paddleocr}"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/crop_ocr", methods=["POST"])
def crop_ocr():
    """Handles cropped image upload and performs OCR"""
    try:
        if "image" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["image"]
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)

        extracted_text = extract_text(filepath)
        return jsonify({"text": extracted_text})

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("[INFO] Flask OCR Server is Running...")
    app.run(debug=True)
