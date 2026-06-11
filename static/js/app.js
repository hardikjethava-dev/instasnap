document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('downloader-form');
    const urlInput = document.getElementById('instagram-url-input');
    
    const loaderSection = document.getElementById('loader-section');
    const loaderTitle = document.getElementById('loader-title');
    const loaderSubtitle = document.getElementById('loader-subtitle');
    
    const errorSection = document.getElementById('error-section');
    const errorMessage = document.getElementById('error-message');
    
    const resultsSection = document.getElementById('results-section');
    const resultTitle = document.getElementById('result-title');
    const metaType = document.getElementById('meta-type');
    const metaDate = document.getElementById('meta-date');
    const metaDuration = document.getElementById('meta-duration');
    const metaResolution = document.getElementById('meta-resolution');
    const downloadContainer = document.getElementById('download-buttons-container');
    const zipContainer = document.getElementById('zip-download-container');
    const individualFilesSection = document.getElementById('individual-files-section');
    
    let pollInterval = null;

    // Theme Toggle Logic
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const themeIcon = document.getElementById('theme-icon');
    
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.body.classList.add('light-theme');
        themeIcon.className = 'bi bi-sun-fill fs-5';
    } else {
        document.body.classList.remove('light-theme');
        themeIcon.className = 'bi bi-moon-stars-fill fs-5';
    }
    
    themeToggleBtn.addEventListener('click', () => {
        if (document.body.classList.contains('light-theme')) {
            document.body.classList.remove('light-theme');
            themeIcon.className = 'bi bi-moon-stars-fill fs-5';
            localStorage.setItem('theme', 'dark');
        } else {
            document.body.classList.add('light-theme');
            themeIcon.className = 'bi bi-sun-fill fs-5';
            localStorage.setItem('theme', 'light');
        }
    });

    // Helper to get CSRF token
    const getCsrfToken = () => {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    };

    // Show/Hide Helpers
    const hideAllStates = () => {
        loaderSection.classList.add('d-none');
        errorSection.classList.add('d-none');
        resultsSection.classList.add('d-none');
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    };

    // Fetch logic
    const startFetch = async () => {
        hideAllStates();

        const url = urlInput.value.trim();
        if (!url) {
            showError("Please paste a valid Instagram URL.");
            return;
        }

        // Clear the URL input box for the next query
        urlInput.value = '';

        // Set Loading State
        loaderTitle.textContent = "Fetching post metadata...";
        loaderSubtitle.textContent = "Connecting to Instagram's server";
        loaderSection.classList.remove('d-none');

        const formData = new FormData();
        formData.append('url', url);

        try {
            const response = await fetch('/api/fetch/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken()
                },
                body: formData
            });

            const data = await response.json();

            if (!response.ok || data.status === 'error') {
                throw new Error(data.message || 'Failed to extract post details.');
            }

            // Populate metadata
            renderMetadata(data.metadata);
            resultsSection.classList.remove('d-none');

            // Start polling for download task completion
            startPolling(data.task_id);

        } catch (err) {
            hideAllStates();
            showError(err.message);
        }
    };

    // Handle Form Submission
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        startFetch();
    });

    // Automatically trigger fetch when url is pasted or dropped
    urlInput.addEventListener('paste', () => {
        setTimeout(startFetch, 100);
    });

    urlInput.addEventListener('drop', () => {
        setTimeout(startFetch, 100);
    });

    // Render extracted metadata values to UI
    const renderMetadata = (meta) => {
        resultTitle.textContent = meta.title;
        
        metaType.textContent = meta.media_type;
        metaDate.textContent = meta.upload_date;
        metaResolution.textContent = meta.resolution;

        const durationBadge = metaDuration.closest('.badge');
        if (meta.media_type === 'Photo' || meta.duration === 'N/A') {
            durationBadge.classList.add('d-none');
        } else {
            metaDuration.textContent = meta.duration;
            durationBadge.classList.remove('d-none');
        }
        
        // Clear previous download links
        downloadContainer.innerHTML = '';
        if (zipContainer) {
            zipContainer.innerHTML = '';
        }
        if (individualFilesSection) {
            individualFilesSection.classList.add('d-none');
        }
    };

    // Poll status of background download task
    const startPolling = (taskId) => {
        pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${taskId}/`);
                const data = await response.json();

                if (!response.ok || data.status === 'error') {
                    throw new Error(data.message || 'Task check failed.');
                }

                if (data.status === 'completed') {
                    hideLoadingState();
                    renderDownloadButtons(data.files, data.zip_file);
                } else if (data.status === 'failed') {
                    hideLoadingState();
                    showError(data.error || 'Downloading process failed on server.');
                }
                // If status is 'processing', do nothing and poll again

            } catch (err) {
                hideLoadingState();
                showError("Connection lost. Failed to fetch download status: " + err.message);
            }
        }, 2000);
    };

    const hideLoadingState = () => {
        loaderSection.classList.add('d-none');
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    };

    const showError = (msg) => {
        console.error("Downloader error details:", msg);
        errorMessage.textContent = "This media file cannot be processed at the moment. It might be private or the link could be invalid.";
        errorSection.classList.remove('d-none');
    };

    // Render individual download cards with separate previews and an optional ZIP Download All button
    const renderDownloadButtons = (files, zipFile) => {
        if (!files || files.length === 0) {
            downloadContainer.innerHTML = `<p class="text-danger small">No files available for download.</p>`;
            return;
        }

        // Render ZIP Download All button if present (indicating multiple files in a carousel)
        if (zipFile && zipContainer) {
            const zipDiv = document.createElement('div');
            zipDiv.className = "mb-2 fade-in";
            zipDiv.innerHTML = `
                <a href="${zipFile.url}" download="${zipFile.name}" class="btn btn-gradient btn-lg w-100 py-3 font-outfit d-flex align-items-center justify-content-center gap-2" style="box-shadow: 0 4px 15px rgba(255, 0, 122, 0.3);">
                    <i class="bi bi-file-earmark-zip-fill fs-4"></i>
                    <strong>Download All in One Click (ZIP)</strong>
                    <span class="badge bg-secondary-custom rounded-pill ms-1" style="font-size: 0.8rem; padding: 6px 12px;">${zipFile.size}</span>
                </a>
            `;
            zipContainer.appendChild(zipDiv);
        }

        // Show/hide Individual Files heading based on count
        if (individualFilesSection) {
            if (files.length > 1) {
                individualFilesSection.classList.remove('d-none');
            } else {
                individualFilesSection.classList.add('d-none');
            }
        }

        const cardsWrapper = document.createElement('div');
        cardsWrapper.className = "row g-3 pb-3";
        downloadContainer.appendChild(cardsWrapper);

        files.forEach((file, index) => {
            const col = document.createElement('div');
            col.className = "col-12 col-sm-6 col-md-4 fade-in";
            
            const isVideo = file.name.endsWith('.mp4') || file.name.endsWith('.mov') || file.name.endsWith('.webm');
            const previewMedia = isVideo 
                ? `<video src="${file.url}" controls muted class="w-100 h-100" style="object-fit: contain; background: #000;"></video>`
                : `<img src="${file.url}" alt="Preview" class="w-100 h-100" style="object-fit: contain; background: #000;" referrerpolicy="no-referrer">`;
                
            col.innerHTML = `
                <div class="media-preview-card rounded-4 p-3 border border-secondary-subtle h-100 d-flex flex-column justify-content-between" style="background: rgba(255, 255, 255, 0.02);">
                    <div class="preview-item-wrapper rounded-3 overflow-hidden shadow-sm mb-3" style="background: #000; display: flex; align-items: center; justify-content: center; aspect-ratio: 1/1; border: 1px solid rgba(255, 255, 255, 0.08);">
                        ${previewMedia}
                    </div>
                    <div class="text-center mt-auto">
                        <p class="text-muted mb-2 small">${file.size}</p>
                        <a href="${file.url}" download="${file.name}" class="btn btn-gradient btn-sm w-100 py-2 font-outfit" style="border-radius: 8px !important;">
                            <i class="bi bi-cloud-arrow-down-fill me-1"></i>
                            Download
                        </a>
                    </div>
                </div>
            `;
            cardsWrapper.appendChild(col);
        });
    };
});
