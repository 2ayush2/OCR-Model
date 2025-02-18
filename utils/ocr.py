import pytesseract
from PIL import Image
import cv2

def extract_text(filepath):
    image = cv2.imread(filepath)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return pytesseract.image_to_string(Image.fromarray(image), lang="eng+nep")
