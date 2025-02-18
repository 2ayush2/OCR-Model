document.addEventListener('DOMContentLoaded', function () {
    const inputElement = document.getElementById('fileInput');
    const previewImage = document.getElementById('preview');
    const processButton = document.getElementById('processButton');
    const liveOCRText = document.getElementById('liveOCR');
    const resultText = document.getElementById('result');
    let cropper;

    // Initialize FilePond for File Upload UI
    const pond = FilePond.create(inputElement);

    pond.on('addfile', (error, file) => {
        if (error) {
            console.error('[ERROR] File upload failed:', error);
            return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
            previewImage.src = e.target.result;
            previewImage.style.display = 'block';

            if (cropper) {
                cropper.destroy();
            }

            // Initialize Cropper.js
            cropper = new Cropper(previewImage, {
                viewMode: 2,
                autoCropArea: 1,
                scalable: true,
                zoomable: true,
                movable: true,
                cropBoxResizable: true,
                background: false,
            });

            processButton.style.display = 'inline-block';
        };
        reader.readAsDataURL(file.file);
    });

    // Send Cropped Image to Backend
    processButton.addEventListener('click', () => {
        if (!cropper) {
            alert("❌ Please select and crop an image first.");
            return;
        }

        const croppedCanvas = cropper.getCroppedCanvas();
        if (!croppedCanvas) {
            alert("❌ Failed to generate cropped image.");
            return;
        }

        croppedCanvas.toBlob((blob) => {
            const formData = new FormData();
            formData.append('image', blob, 'cropped.png');

            resultText.innerHTML = "📤 Uploading Image for OCR...";

            fetch('/crop_ocr', {
                method: 'POST',
                body: formData,
            })
            .then(response => response.json())
            .then(data => {
                resultText.innerText = "✅ Extracted Text:\n" + data.text;
            })
            .catch(error => {
                console.error('[ERROR] OCR extraction failed:', error);
                resultText.innerText = "❌ OCR Failed!";
            });
        });
    });
});
