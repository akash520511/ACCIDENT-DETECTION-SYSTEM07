
// ========================================
// Configuration & State
// ========================================
const CONFIG = {
    API_BASE: 'https://accident-detection-system07-3.onrender.com', 
    FRAME_INTERVAL: 500, 
    ALERT_SOUND_ENABLED: true
};

const state = {
    currentSection: 'home',
    cameraStream: null,
    websocket: null,
    isDetecting: false,
    frameCount: 0,
    lastFrameTime: 0
};

// ========================================
// DOM Elements
// ========================================
const elements = {
    navbar: document.getElementById('navbar'),
    mobileMenuBtn: document.getElementById('mobileMenuBtn'),
    mobileMenu: document.getElementById('mobileMenu'),
    sections: document.querySelectorAll('.section'),
    navLinks: document.querySelectorAll('.nav-link'),
    mobileNavLinks: document.querySelectorAll('.mobile-nav-link'),
    imageInput: document.getElementById('imageInput'),
    videoInput: document.getElementById('videoInput'),
    imageDropZone: document.getElementById('imageDropZone'),
    videoDropZone: document.getElementById('videoDropZone'),
    imagePreview: document.getElementById('imagePreview'),
    videoPreview: document.getElementById('videoPreview'),
    previewImage: document.getElementById('previewImage'),
    previewVideo: document.getElementById('previewVideo'),
    imagePlaceholder: document.getElementById('imagePlaceholder'),
    videoPlaceholder: document.getElementById('videoPlaceholder'),
    resultsPanel: document.getElementById('resultsPanel'),
    resultsContent: document.getElementById('resultsContent'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    loadingText: document.getElementById('loadingText'),
    progressFill: document.getElementById('progressFill'),
    alertModal: document.getElementById('alertModal'),
    alertSound: document.getElementById('alertSound'),
    webcamVideo: document.getElementById('webcamVideo'),
    cameraOverlay: document.getElementById('cameraOverlay'),
    detectionOverlay: document.getElementById('detectionOverlay'),
    detectionLabel: document.getElementById('detectionLabel'),
    cameraStatus: document.getElementById('cameraStatus'),
    liveStatus: document.getElementById('liveStatus'),
    liveConfidence: document.getElementById('liveConfidence'),
    liveFPS: document.getElementById('liveFPS'),
    startCameraBtn: document.getElementById('startCameraBtn'),
    stopCameraBtn: document.getElementById('stopCameraBtn'),
    historyTableBody: document.getElementById('historyTableBody'),
    historyEmpty: document.getElementById('historyEmpty'),
    totalDetections: document.getElementById('totalDetections'),
    accidentsDetected: document.getElementById('accidentsDetected'),
    safeDetections: document.getElementById('safeDetections'),
    avgConfidence: document.getElementById('avgConfidence')
};

// ========================================
// Initialize Application
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initFileUploads();
    loadStats();
    loadHistory();
});

// ========================================
// Navigation
// ========================================
function initNavigation() {
    // Scroll handling
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            elements.navbar.classList.add('scrolled');
        } else {
            elements.navbar.classList.remove('scrolled');
        }
    });

    // Nav links
    elements.navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const section = link.dataset.section;
            navigateTo(section);
        });
    });

    // Mobile nav links
    elements.mobileNavLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const section = link.dataset.section;
            navigateTo(section);
            elements.mobileMenu.classList.remove('show');
        });
    });

    // Mobile menu toggle
    elements.mobileMenuBtn.addEventListener('click', () => {
        elements.mobileMenu.classList.toggle('show');
    });
}

function navigateTo(section) {
    state.currentSection = section;
    
    // Update sections
    elements.sections.forEach(s => s.classList.remove('active'));
    document.getElementById(section).classList.add('active');
    
    // Update nav links
    elements.navLinks.forEach(link => {
        link.classList.toggle('active', link.dataset.section === section);
    });
    
    elements.mobileNavLinks.forEach(link => {
        link.classList.toggle('active', link.dataset.section === section);
    });
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    // Load section-specific data
    if (section === 'history') {
        loadHistory();
    } else if (section === 'upload') {
        loadStats();
    }
}

// ========================================
// File Uploads
// ========================================
function initFileUploads() {
    // Image upload
    setupDropZone(elements.imageDropZone, elements.imageInput, handleImageSelect);
    elements.imageDropZone.addEventListener('click', () => elements.imageInput.click());
    elements.imageInput.addEventListener('change', (e) => {
        if (e.target.files[0]) handleImageSelect(e.target.files[0]);
    });

    // Video upload
    setupDropZone(elements.videoDropZone, elements.videoInput, handleVideoSelect);
    elements.videoDropZone.addEventListener('click', () => elements.videoInput.click());
    elements.videoInput.addEventListener('change', (e) => {
        if (e.target.files[0]) handleVideoSelect(e.target.files[0]);
    });
}

function setupDropZone(zone, input, handler) {
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });
    
    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });
    
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handler(file);
    });
}

function handleImageSelect(file) {
    if (!file.type.startsWith('image/')) {
        showNotification('Please select an image file', 'error');
        return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
        elements.previewImage.src = e.target.result;
        elements.imagePreview.style.display = 'block';
        elements.imagePlaceholder.style.display = 'none';
    };
    reader.readAsDataURL(file);
}

function handleVideoSelect(file) {
    if (!file.type.startsWith('video/')) {
        showNotification('Please select a video file', 'error');
        return;
    }
    
    const url = URL.createObjectURL(file);
    elements.previewVideo.src = url;
    elements.videoPreview.style.display = 'block';
    elements.videoPlaceholder.style.display = 'none';
}

function clearImagePreview() {
    elements.previewImage.src = '';
    elements.imagePreview.style.display = 'none';
    elements.imagePlaceholder.style.display = 'block';
    elements.imageInput.value = '';
}

function clearVideoPreview() {
    elements.previewVideo.src = '';
    elements.videoPreview.style.display = 'none';
    elements.videoPlaceholder.style.display = 'block';
    elements.videoInput.value = '';
}

// ========================================
// Image Analysis
// ========================================
async function analyzeImage() {
    const file = elements.imageInput.files[0];
    if (!file) {
        showNotification('Please select an image first', 'error');
        return;
    }
    
    showLoading('Analyzing image...');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${CONFIG.API_BASE}/predict-image`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayResults(data, 'image');
            
            if (data.result === 'Accident') {
                showAlertModal(data);
            }
        } else {
            throw new Error(data.detail || 'Analysis failed');
        }
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        hideLoading();
        loadStats();
    }
}

// ========================================
// Video Analysis
// ========================================
async function analyzeVideo() {
    const file = elements.videoInput.files[0];
    if (!file) {
        showNotification('Please select a video first', 'error');
        return;
    }
    
    showLoading('Processing video frame-by-frame...', true);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        // Simulate progress for better UX
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 90) progress = 90;
            updateProgress(progress);
        }, 500);
        
        const response = await fetch(`${CONFIG.API_BASE}/predict-video`, {
            method: 'POST',
            body: formData
        });
        
        clearInterval(progressInterval);
        updateProgress(100);
        
        const data = await response.json();
        
        if (data.success) {
            displayResults(data, 'video');
            
            if (data.result === 'Accident') {
                showAlertModal(data);
            }
        } else {
            throw new Error(data.detail || 'Video analysis failed');
        }
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        hideLoading();
        loadStats();
    }
}

// ========================================
// Results Display
// ========================================
function displayResults(data, type) {
    const isAccident = data.result === 'Accident';
    
    let html = `
        <div class="result-main">
            <div class="result-badge ${isAccident ? 'accident' : 'safe'}">
                ${isAccident ? 'Accident Detected' : 'No Accident'}
            </div>
            <div class="confidence-display">
                <span class="confidence-value">${data.confidence.toFixed(1)}%</span>
                <span class="confidence-label">Confidence Score</span>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${data.confidence}%"></div>
                </div>
            </div>
        </div>
        <div class="result-details">
            <div class="detail-item">
                <span class="detail-label">Response Time</span>
                <span class="detail-value">${data.response_time.toFixed(2)}s</span>
            </div>
            <div class="detail-item">
                <span class="detail-label">Severity</span>
                <span class="detail-value severity-${data.severity?.toLowerCase() || 'none'}">${data.severity || 'N/A'}</span>
            </div>
            ${type === 'video' ? `
                <div class="detail-item">
                    <span class="detail-label">Total Frames</span>
                    <span class="detail-value">${data.frames_processed || data.total_frames}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Accident Frames</span>
                    <span class="detail-value">${data.accident_frames_count || 0}</span>
                </div>
            ` : ''}
        </div>
    `;
    
    // Show accident frame timestamps for video
    if (type === 'video' && data.accident_frames && data.accident_frames.length > 0) {
        html += `
            <div class="accident-frames-list">
                <h4>Accident Detected at Timestamps:</h4>
                <div class="frames-grid">
                    ${data.accident_frames.slice(0, 12).map(f => `
                        <div class="frame-item">
                            <span class="frame-time">${f.timestamp}s</span>
                            <span class="frame-confidence">${f.confidence.toFixed(1)}%</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    elements.resultsContent.innerHTML = html;
    elements.resultsPanel.style.display = 'block';
    elements.resultsPanel.scrollIntoView({ behavior: 'smooth' });
}

function closeResults() {
    elements.resultsPanel.style.display = 'none';
}

// ========================================
// Live Camera Detection
// ========================================
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 1280, height: 720, facingMode: 'environment' }
        });
        
        state.cameraStream = stream;
        elements.webcamVideo.srcObject = stream;
        
        elements.cameraOverlay.style.display = 'none';
        elements.startCameraBtn.style.display = 'none';
        elements.stopCameraBtn.style.display = 'inline-flex';
        
        updateCameraStatus(true, 'Camera Active');
        elements.liveStatus.textContent = 'Detecting';
        
        // Start WebSocket connection
        startWebSocket();
        
    } catch (error) {
        showNotification(`Camera error: ${error.message}`, 'error');
        updateCameraStatus(false, 'Camera Error');
    }
}

function stopCamera() {
    if (state.cameraStream) {
        state.cameraStream.getTracks().forEach(track => track.stop());
        state.cameraStream = null;
    }
    
    if (state.websocket) {
        state.websocket.close();
        state.websocket = null;
    }
    
    elements.webcamVideo.srcObject = null;
    elements.cameraOverlay.style.display = 'flex';
    elements.detectionOverlay.style.display = 'none';
    elements.startCameraBtn.style.display = 'inline-flex';
    elements.stopCameraBtn.style.display = 'none';
    
    updateCameraStatus(false, 'Camera Off');
    elements.liveStatus.textContent = 'Inactive';
    elements.liveConfidence.textContent = '--';
    elements.liveFPS.textContent = '--';
}

function startWebSocket() {
    const wsProtocol = CONFIG.API_BASE.startsWith('https') ? 'wss' : 'ws';
    const wsUrl = `${wsProtocol}://${CONFIG.API_BASE.replace(/^https?:\/\//, '')}/ws/live-detection`;
    
    state.websocket = new WebSocket(wsUrl);
    
    state.websocket.onopen = () => {
        console.log('WebSocket connected');
        startFrameCapture();
    };
    
    state.websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleDetectionResult(data);
    };
    
    state.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    state.websocket.onclose = () => {
        console.log('WebSocket disconnected');
    };
}

function startFrameCapture() {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    state.isDetecting = true;
    state.frameCount = 0;
    state.lastFrameTime = performance.now();
    
    function captureFrame() {
        if (!state.isDetecting || !state.websocket || state.websocket.readyState !== WebSocket.OPEN) {
            return;
        }
        
        const video = elements.webcamVideo;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        ctx.drawImage(video, 0, 0);
        canvas.toBlob((blob) => {
            if (blob && state.websocket && state.websocket.readyState === WebSocket.OPEN) {
                blob.arrayBuffer().then(buffer => {
                    state.websocket.send(buffer);
                });
            }
        }, 'image/jpeg', 0.8);
        
        // Update FPS
        const now = performance.now();
        const fps = Math.round(1000 / (now - state.lastFrameTime));
        state.lastFrameTime = now;
        elements.liveFPS.textContent = fps;
        
        state.frameCount++;
        setTimeout(captureFrame, CONFIG.FRAME_INTERVAL);
    }
    
    captureFrame();
}

function handleDetectionResult(data) {
    const isAccident = data.result === 'Accident';
    
    elements.liveConfidence.textContent = `${data.confidence.toFixed(1)}%`;
    
    // Update detection overlay
    elements.detectionOverlay.style.display = 'block';
    elements.detectionLabel.className = `detection-label ${isAccident ? 'accident' : ''}`;
    elements.detectionLabel.innerHTML = `
        <span class="result-text">${data.result}</span>
        <span class="confidence-text">${data.confidence.toFixed(1)}%</span>
    `;
    
    // Trigger alert for accident
    if (isAccident && CONFIG.ALERT_SOUND_ENABLED) {
        showAlertModal(data);
        playAlertSound();
    }
}

function updateCameraStatus(active, text) {
    const statusEl = elements.cameraStatus;
    statusEl.className = `status-indicator-live ${active ? 'active' : ''}`;
    statusEl.querySelector('.text').textContent = text;
}

// ========================================
// History
// ========================================
async function loadHistory() {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/history?limit=100`);
        const data = await response.json();
        
        if (data.success && data.history.length > 0) {
            renderHistory(data.history);
            elements.historyEmpty.style.display = 'none';
        } else {
            elements.historyEmpty.style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading history:', error);
        elements.historyEmpty.style.display = 'block';
    }
}

function renderHistory(history) {
    const html = history.map(item => {
        const isAccident = item.result === 'Accident';
        const timestamp = new Date(item.timestamp).toLocaleString();
        
        return `
            <tr>
                <td>#${item.id}</td>
                <td>${timestamp}</td>
                <td>
                    <span class="result-tag ${isAccident ? 'accident' : 'safe'}">
                        ${item.result}
                    </span>
                </td>
                <td>${item.confidence?.toFixed(1) || '--'}%</td>
                <td>${item.input_type || '--'}</td>
                <td>
                    <span class="severity-tag ${(item.severity || 'none').toLowerCase()}">
                        ${item.severity || 'N/A'}
                    </span>
                </td>
                <td>${item.response_time?.toFixed(2) || '--'}s</td>
            </tr>
        `;
    }).join('');
    
    elements.historyTableBody.innerHTML = html;
}

async function refreshHistory() {
    await loadHistory();
    showNotification('History refreshed', 'success');
}

async function clearAllHistory() {
    if (!confirm('Are you sure you want to clear all detection history?')) return;
    
    try {
        await fetch(`${CONFIG.API_BASE}/history`, { method: 'DELETE' });
        await loadHistory();
        await loadStats();
        showNotification('History cleared', 'success');
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    }
}

// ========================================
// Statistics
// ========================================
async function loadStats() {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/stats`);
        const data = await response.json();
        
        if (data.success) {
            const stats = data.stats;
            elements.totalDetections.textContent = stats.total_detections || 0;
            elements.accidentsDetected.textContent = stats.accidents_detected || 0;
            elements.safeDetections.textContent = stats.safe_detections || 0;
            elements.avgConfidence.textContent = `${stats.average_confidence || 0}%`;
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ========================================
// Alerts & Notifications
// ========================================
function showAlertModal(data) {
    document.getElementById('alertConfidence').textContent = `${data.confidence?.toFixed(1) || '--'}%`;
    document.getElementById('alertSeverity').textContent = data.severity || 'Detected';
    document.getElementById('alertTime').textContent = new Date().toLocaleTimeString();
    
    elements.alertModal.classList.add('show');
}

function closeAlertModal() {
    elements.alertModal.classList.remove('show');
}

function playAlertSound() {
    try {
        elements.alertSound.currentTime = 0;
        elements.alertSound.play().catch(() => {});
    } catch (e) {
        console.log('Could not play alert sound');
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        <span>${message}</span>
    `;
    
    // Style the notification
    Object.assign(notification.style, {
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        padding: '16px 24px',
        background: type === 'error' ? 'rgba(255, 71, 87, 0.95)' : type === 'success' ? 'rgba(0, 210, 106, 0.95)' : 'rgba(58, 175, 169, 0.95)',
        color: '#fff',
        borderRadius: '12px',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        fontSize: '14px',
        fontWeight: '500',
        boxShadow: '0 8px 30px rgba(0, 0, 0, 0.3)',
        zIndex: '9999',
        animation: 'slideInRight 0.3s ease'
    });
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease forwards';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

// ========================================
// Loading States
// ========================================
function showLoading(text = 'Processing...', showProgress = false) {
    elements.loadingText.textContent = text;
    elements.progressFill.style.width = '0%';
    elements.loadingOverlay.classList.add('show');
}

function hideLoading() {
    elements.loadingOverlay.classList.remove('show');
}

function updateProgress(percent) {
    elements.progressFill.style.width = `${Math.min(percent, 100)}%`;
}

// ========================================
// CSS Animations (injected)
// ========================================
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { opacity: 0; transform: translateX(100px); }
        to { opacity: 1; transform: translateX(0); }
    }
    @keyframes slideOutRight {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(100px); }
    }
`;
document.head.appendChild(style);
