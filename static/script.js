document.addEventListener('DOMContentLoaded', function () {
    const inputElement = document.getElementById('fileInput');
    const previewImage = document.getElementById('preview');
    const processButton = document.getElementById('processButton');
    const resultContainer = document.getElementById('resultContainer');
    const copyButton = document.getElementById('copyButton');
    const liveOCR = document.getElementById('liveOCR');
    const progressContainer = document.getElementById("progressContainer");
    const progressBar = document.getElementById("progressBar");
    const toggleNepaliButton = document.getElementById("toggleNepali"); // Toggle Button
    const extractedTextArea = document.getElementById("extractedText");

    let isProcessing = false;
    let originalImage = null;
    let cropper;
    let progressInterval;
    let isNepaliEnabled = false; // Track language mode
    let nepalifyInstance = null; // To store Nepalify instance

    // Initialize FilePond for better file upload handling
    const pond = FilePond.create(inputElement, {
        acceptedFileTypes: ['image/png', 'image/jpeg'],
        allowFileSizeValidation: true,
        maxFileSize: '5MB',
    });
    fileInput.addEventListener("change", function (event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = function (e) {
            originalImage = new Image();
            originalImage.src = e.target.result;
            originalImage.onload = function () {
                previewImage.src = originalImage.src;
                previewImage.style.display = "block";
                
                // Apply real-time enhancements
                setTimeout(enhanceImageInBrowser, 500);
            };
        };
        reader.readAsDataURL(file);
    });
    function enhanceImageInBrowser() {
        if (!originalImage) return;

        // Create a canvas to draw the processed image
        const canvas = document.createElement("canvas");
        const ctx = canvas.getContext("2d");

        canvas.width = originalImage.width;
        canvas.height = originalImage.height;
        ctx.drawImage(originalImage, 0, 0, canvas.width, canvas.height);

        // Convert to grayscale
        let imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        let data = imgData.data;
        for (let i = 0; i < data.length; i += 4) {
            let avg = (data[i] + data[i + 1] + data[i + 2]) / 3;
            data[i] = avg;  // Red
            data[i + 1] = avg;  // Green
            data[i + 2] = avg;  // Blue
        }

        // Apply contrast enhancement (CLAHE alternative)
        let contrastFactor = 2.5;
        for (let i = 0; i < data.length; i += 4) {
            data[i] = Math.min(255, data[i] * contrastFactor);
            data[i + 1] = Math.min(255, data[i + 1] * contrastFactor);
            data[i + 2] = Math.min(255, data[i + 2] * contrastFactor);
        }

        ctx.putImageData(imgData, 0, 0);

        // Show enhanced image in the preview
        previewImage.src = canvas.toDataURL();
        previewImage.style.display = "block";

        // Allow user to send enhanced image for OCR
        processButton.style.display = "inline-block";
        processButton.addEventListener("click", function () {
            uploadEnhancedImage(canvas);
        });
    }
    function uploadEnhancedImage(canvas) {
        canvas.toBlob((blob) => {
            const formData = new FormData();
            formData.append("image", blob, "enhanced.png");

            fetch("/crop_ocr", {
                method: "POST",
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById("result").innerHTML = `<p>✅ <b>Extracted Text:</b></p><pre>${data.text}</pre>`;
            })
            .catch(error => {
                console.error("❌ OCR Extraction Failed:", error);
                document.getElementById("result").innerHTML = "❌ OCR Failed!";
            });
        });
    }

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
                    extractedTextArea.value = data.text; // Display OCR result in textarea

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

    function initializeNepalify() {
        if (!nepalifyInstance) {
            nepalifyInstance = nepalify.interceptElementById("extractedText", { layout: "romanized" });
        }
    }

    toggleNepaliButton.addEventListener("click", function () {
        const currentText = extractedTextArea.value;

        if (isNepaliEnabled) {
            if (nepalifyInstance) {
                nepalifyInstance.disable();
            }
            toggleNepaliButton.innerText = "Switch to Nepali 🏳";
            extractedTextArea.style.backgroundColor = "white";
            isNepaliEnabled = false;
        } else {
            initializeNepalify();
            nepalifyInstance.enable();
            toggleNepaliButton.innerText = "Switch to English 🇬🇧";
            extractedTextArea.style.backgroundColor = "#ffdddd";
            isNepaliEnabled = true;
        }

        extractedTextArea.value = currentText; // Preserve text
    });

    // Copy Button Functionality
    copyButton.addEventListener("click", function () {
        navigator.clipboard.writeText(extractedTextArea.value)
            .then(() => alert('✅ Text Copied to Clipboard!'))
            .catch(err => console.error('❌ Copy failed:', err));
    });
    
});
