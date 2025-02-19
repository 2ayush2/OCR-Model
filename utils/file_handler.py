ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "tiff", "bmp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
