OCR Web Application

This project is a Flask-based OCR (Optical Character Recognition) Web Application that extracts text from images using PaddleOCR, EasyOCR, and Tesseract-OCR. It supports real-time progress updates, live streaming of OCR results, and enhanced image preprocessing.

Features

Multi-OCR Engine - Supports EasyOCR, PaddleOCR, and Tesseract-OCR
 Multi-Language Support - Works for both English & Nepali text
 Image Preprocessing - Enhances image clarity for better OCR accuracy
 Real-Time Progress Tracking - Live updates on OCR processing status
 Live Streaming OCR - See results as text is extracted
Frontend with Crop & Enhancement - Allows users to crop images before OCR
 Nepali Typing Support - Enables seamless Nepali text conversion in the editor

 1️⃣ Installation Guide

1. Install Dependencies

Ensure you have Python 3.8+ installed. Then, run:

pip install -r requirements.txt

2. Install Tesseract OCR (Required for Pytesseract)

Windows:  Download & Install

After installation, add this to your Python script:

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

2️⃣ Running the Project

Start the Flask 

python app.py