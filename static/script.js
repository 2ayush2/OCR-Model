document.addEventListener('DOMContentLoaded', function () {
    const inputElement = document.getElementById('fileInput');
    const previewImage = document.getElementById('preview');
    const processButton = document.getElementById('processButton');
    const resultContainer = document.getElementById('resultContainer');
    const copyButton = document.getElementById('copyButton');
    const liveOCR = document.getElementById('liveOCR');
    let isProcessing=false;

    // Progress Bar
    const progressContainer = document.getElementById("progressContainer");
    const progressBar = document.getElementById("progressBar");

    let cropper;
    let progressInterval;

    // Initialize FilePond for better file upload handling
    const pond = FilePond.create(inputElement, {
        acceptedFileTypes: ['image/png', 'image/jpeg'],
        allowFileSizeValidation: true,
        maxFileSize: '5MB',
    });

    pond.on('addfile', (error, file) => {
        if (error) {
            console.error('[ERROR] File upload failed:', error);
            liveOCR.innerHTML = "❌ File upload error!";
            return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
            previewImage.src = e.target.result;
            previewImage.classList.remove('hidden');

            if (cropper) {
                cropper.destroy();
            }

            cropper = new Cropper(previewImage, {
                viewMode: 2,
                autoCropArea: 1,
                scalable: true,
                zoomable: true,
                movable: true,
                cropBoxResizable: true,
                background: false,
            });

            processButton.classList.remove('hidden');
            processButton.disabled = false;
        };
        reader.readAsDataURL(file.file);
    });

    // Initialize Quill Editor
    var quill = new Quill('#editor', {
        theme: 'snow'
    });

    function startProgressPolling() {
        const liveOCR = document.getElementById("liveOCR");
        const progressBar = document.getElementById("progressBar");
    
        let progressInterval = setInterval(() => {
            fetch("/ocr_progress")
                .then(response => response.json())
                .then(data => {
                    liveOCR.innerText = `📤 ${data.status}`;
                    progressBar.style.width = `${data.progress}%`;
                    progressBar.innerText = `${data.progress}%`;
    
                    if (data.progress >= 100) {
                        clearInterval(progressInterval);
                    }
                })
                .catch(error => console.error("❌ Progress update failed:", error));
        }, 1000);
    }
    

    function stopProgressPolling() {
        clearInterval(progressInterval);
    }

    processButton.addEventListener("click", () => {
        if (!cropper) {
            alert("❌ Please select and crop an image first.");
            return;
        }
        if (isProcessing) {
            alert("❗ OCR is already in progress. Please wait...");
            return;
        }
        isProcessing = true;  // Set processing flag
        processButton.disabled = true;
        processButton.innerText = "⏳ Extracting..."; // Change button text
        const croppedCanvas = cropper.getCroppedCanvas();
        if (!croppedCanvas) {
            alert("❌ Failed to generate cropped image.");
            return;
        }

        processButton.disabled = true;
        liveOCR.innerHTML = "📤 Extracting Text...";

        // Show progress bar
        progressContainer.classList.remove("hidden");
        progressBar.style.width = "0%";
        progressBar.innerHTML = "0%";

        croppedCanvas.toBlob((blob) => {
            const formData = new FormData();
            formData.append("image", blob, "cropped.png");

            startProgressPolling(); // Start live progress updates

            fetch("/crop_ocr", {
                method: "POST",
                body: formData,
            })
            .then(response => response.json())
            .then(data => {
                stopProgressPolling(); // Stop progress updates

                if (data.text) {
                    quill.root.innerHTML = data.text;
                    resultContainer.classList.remove("hidden");
                    liveOCR.innerHTML = "✅ OCR Completed!";
                } else {
                    liveOCR.innerHTML = "⚠️ No text detected!";
                }
            })
            .catch(error => {
                console.error("[ERROR] OCR extraction failed:", error);
                liveOCR.innerHTML = "❌ OCR Failed!";
            })
            .finally(() => {
                isProcessing = false;  // Allow new requests
                processButton.disabled = false;
                processButton.innerText = "🔍 Extract Text";
            });
        });
    });

    copyButton.addEventListener('click', function () {
        navigator.clipboard.writeText(quill.root.innerText)
            .then(() => alert('✅ Text Copied to Clipboard!'))
            .catch(err => console.error('❌ Copy failed:', err));
    });
});
