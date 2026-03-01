const videoElement = document.getElementById('input_video');
const canvasElement = document.getElementById('output_canvas');
const canvasCtx = canvasElement.getContext('2d');
const gestureIndicator = document.getElementById('gesture-indicator');
const gestureHintEl = document.getElementById('gesture-hint');
const statusText = document.getElementById('status-text');

let isWriting = false;
let isPenDown = false;
let pathPoints = []; // Stores {x, y, t} normalized coordinates with timestamps
let lastPoint = null;
let showingFeedback = false;
let feedbackErrors = null;
let strokeStartTime = null; // Timestamp when stroke started
let currentStrokeQuality = 'low'; // 'good', 'fair', 'low' — updated by live scoring

// ── GESTURE STATE (camera mode) ──
let currentGesture = 'NEUTRAL';
let gestureHoldFrames = 0;
const GESTURE_HOLD_REQUIRED = 4; // must hold gesture for 4 frames (~133ms) to trigger

// ── EMA STROKE SMOOTHER ──
let smoothX = null;
let smoothY = null;
const EMA_ALPHA = 0.35; // lower = smoother but more lag; 0.35 is good for children

// ----------------------
// Drawing Mode: 'camera' (MediaPipe) or 'draw' (mouse/touch)
// ----------------------
let currentMode = 'camera';
let cameraReady = false;
let mouseDown = false;

function switchMode(mode) {
    currentMode = mode;

    const videoSection = document.getElementById('video-section');
    const cameraModeBtn = document.getElementById('mode-camera');
    const drawModeBtn = document.getElementById('mode-draw');
    const headerLabel = document.getElementById('header-mode-label');
    const hint = document.getElementById('gesture-hint');

    // Update buttons
    cameraModeBtn.classList.toggle('active', mode === 'camera');
    drawModeBtn.classList.toggle('active', mode === 'draw');

    if (mode === 'draw') {
        videoSection.classList.add('draw-mode');
        if (headerLabel) headerLabel.innerHTML = '<i class="fas fa-pencil-alt"></i> Draw Mode';
        if (hint) {
            hint.innerHTML = '<i class="fas fa-mouse-pointer"></i> <span>Click and drag to draw!</span>';
            hint.classList.remove('active');
        }
        // Hide video, show canvas background
        videoElement.style.display = 'none';
        canvasElement.style.background = '#1a1a2e';
        // Size canvas properly for draw mode
        ensureCanvasSize();
    } else {
        videoSection.classList.remove('draw-mode');
        if (headerLabel) headerLabel.innerHTML = '<i class="fas fa-video"></i> Camera Mode';
        if (hint) {
            hint.innerHTML = '<i class="fas fa-hand-paper"></i> <span>Open hand: Start, Index finger: Draw, Fist: Submit!</span>';
            hint.classList.remove('active');
        }
        videoElement.style.display = 'block';
        canvasElement.style.background = 'transparent';
    }
}

function ensureCanvasSize() {
    // Make sure canvas has proper dimensions
    const rect = canvasElement.parentElement.getBoundingClientRect();
    if (canvasElement.width < 100 || canvasElement.height < 100) {
        canvasElement.width = rect.width || 640;
        canvasElement.height = rect.height || 480;
    }
}

// MediaPipe Setup
// ── GESTURE CLASSIFIER ──────────────────────────────────────────────────
function classifyHandGesture(landmarks) {
    // landmarks is the array of 21 hand landmark objects {x, y, z}
    const tips = [4, 8, 12, 16, 20];  // thumb, index, middle, ring, pinky tips
    const middle = [3, 6, 10, 14, 18];  // middle joints

    // Individual finger extensions (tip above middle joint)
    const indexExtended = landmarks[8].y < landmarks[6].y;
    const middleExtended = landmarks[12].y < landmarks[10].y;
    const ringExtended = landmarks[16].y < landmarks[14].y;
    const pinkyExtended = landmarks[20].y < landmarks[18].y;
    const thumbExtended = Math.abs(landmarks[4].x - landmarks[0].x) > Math.abs(landmarks[3].x - landmarks[0].x);

    const extendedCount = (thumbExtended ? 1 : 0) + (indexExtended ? 1 : 0) + (middleExtended ? 1 : 0) + (ringExtended ? 1 : 0) + (pinkyExtended ? 1 : 0);

    if (extendedCount >= 4) return 'OPEN';
    if (!indexExtended && !middleExtended && !ringExtended && !pinkyExtended) return 'FIST'; // fist
    if (indexExtended && !middleExtended && !ringExtended && !pinkyExtended) return 'POINT'; // pointing with index

    return 'NEUTRAL';
}

// ── GESTURE STATE MACHINE ────────────────────────────────────────────────
function handleGestureChange(newGesture) {
    if (newGesture === currentGesture) {
        gestureHoldFrames++;
    } else {
        gestureHoldFrames = 0;
        currentGesture = newGesture;
        return;
    }

    if (gestureHoldFrames === GESTURE_HOLD_REQUIRED) {
        if (currentGesture === 'OPEN' && !isWriting) {
            // START drawing session
            isWriting = true;
            // Clear current path
            pathPoints = [];
            canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
            strokeStartTime = null;
            showGestureIndicator('✋ Ready! Point to draw', 'green');
        } else if (currentGesture === 'FIST' && isWriting) {
            // STOP drawing + auto-submit
            isWriting = false;
            isPenDown = false;
            lastPoint = null;
            showGestureIndicator('✊ Done! Submitting...', 'blue');
            setTimeout(() => autoSubmitStroke(), 500); // small delay so child sees feedback
        }
    }
}

function startNewStroke() {
    smoothX = null;
    smoothY = null;
    if (strokeStartTime === null) {
        strokeStartTime = performance.now();
    }
}

function getSmoothedPoint(rawX, rawY) {
    if (smoothX === null) {
        smoothX = rawX;
        smoothY = rawY;
    } else {
        smoothX = EMA_ALPHA * rawX + (1 - EMA_ALPHA) * smoothX;
        smoothY = EMA_ALPHA * rawY + (1 - EMA_ALPHA) * smoothY;
    }
    return { x: smoothX, y: smoothY };
}

function showGestureIndicator(text, color) {
    const el = document.getElementById('gesture-indicator');
    if (!el) return;
    el.textContent = text;
    el.style.backgroundColor = color === 'green' ? '#22c55e' :
        color === 'blue' ? '#3b82f6' : '#6b7280';
    el.style.opacity = '1';
    setTimeout(() => { el.style.opacity = '0'; }, 1500);
}

function autoSubmitStroke() {
    if (pathPoints.length >= 10) {
        stopLiveScoring();
        submitAttempt();
    }
}

function onResults(results) {
    canvasCtx.save();
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);

    // 1. Check for hands
    if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
        const landmarks = results.multiHandLandmarks[0];
        const indexTip = landmarks[8];

        // Classify gesture (OPEN / FIST / POINT / NEUTRAL)
        const gesture = classifyHandGesture(landmarks);
        handleGestureChange(gesture);

        // Draw cursor on index fingertip
        drawCursor(indexTip, isWriting && gesture === 'POINT');

        // Writing: capture EMA-smoothed points only if session is active AND pointing
        if (isWriting && gesture === 'POINT') {
            if (!isPenDown) {
                isPenDown = true;
                startNewStroke(); // reset smoother
            }
            const smoothed = getSmoothedPoint(indexTip.x, indexTip.y);
            const t = strokeStartTime !== null ? Math.round(performance.now() - strokeStartTime) : 0;
            pathPoints.push({ x: smoothed.x, y: smoothed.y, t: t });

            const w = canvasElement.width;
            const h = canvasElement.height;
            const px = { x: smoothed.x * w, y: smoothed.y * h };
            if (lastPoint) {
                drawMagicalStroke(lastPoint, px);
            }
            lastPoint = px;
        } else {
            // Pen lifted
            if (isPenDown) {
                isPenDown = false;
                lastPoint = null;
            }
        }

    } else {
        // No hand detected
        if (isPenDown) {
            isPenDown = false;
            lastPoint = null;
        }
    }

    // Redraw the persistent path every frame (because we clearRect above)
    drawFullTrail();

    canvasCtx.restore();
}

// ----------------------
// Drawing Functions
// ----------------------

function drawCursor(point, active) {
    const x = point.x * canvasElement.width;
    const y = point.y * canvasElement.height;

    canvasCtx.beginPath();
    canvasCtx.arc(x, y, active ? 10 : 5, 0, 2 * Math.PI);
    canvasCtx.fillStyle = active ? '#ffd700' : '#ffffff';
    canvasCtx.shadowColor = active ? '#ffd700' : '#000';
    canvasCtx.shadowBlur = active ? 20 : 0;
    canvasCtx.fill();
    canvasCtx.closePath();
}

// Get quality-based stroke colors (green/amber/red)
function getQualityColors() {
    if (currentStrokeQuality === 'good') {
        return { c1: '#22c55e', c2: '#16a34a', shadow: '#22c55e' };
    } else if (currentStrokeQuality === 'fair') {
        return { c1: '#f59e0b', c2: '#d97706', shadow: '#f59e0b' };
    }
    return { c1: '#ef4444', c2: '#dc2626', shadow: '#ef4444' };
}

function drawFullTrail() {
    if (pathPoints.length < 2) return;

    canvasCtx.lineWidth = 8;
    canvasCtx.lineCap = 'round';
    canvasCtx.lineJoin = 'round';

    // Color based on current quality from live scoring (Part 3C)
    let color1, color2, shadowClr;
    if (currentStrokeQuality === 'good') {
        color1 = '#22c55e'; color2 = '#16a34a'; shadowClr = '#22c55e';  // green — good
    } else if (currentStrokeQuality === 'fair') {
        color1 = '#f59e0b'; color2 = '#d97706'; shadowClr = '#f59e0b';  // amber — fair
    } else {
        color1 = '#ef4444'; color2 = '#dc2626'; shadowClr = '#ef4444';  // red — needs improvement
    }

    const gradient = canvasCtx.createLinearGradient(0, 0, canvasElement.width, canvasElement.height);
    gradient.addColorStop(0, color1);
    gradient.addColorStop(1, color2);
    canvasCtx.strokeStyle = gradient;
    canvasCtx.shadowBlur = 10;
    canvasCtx.shadowColor = shadowClr;

    canvasCtx.beginPath();
    const w = canvasElement.width;
    const h = canvasElement.height;

    // Start
    canvasCtx.moveTo(pathPoints[0].x * w, pathPoints[0].y * h);

    for (let i = 1; i < pathPoints.length; i++) {
        canvasCtx.lineTo(pathPoints[i].x * w, pathPoints[i].y * h);
    }
    canvasCtx.stroke();
}

function drawMagicalStroke(p1, p2) {
    // This function acts more for particle generation in a full engine,
    // but here we just rely on drawFullTrail redrawing everything.
    // If we wanted particles, we'd spawn them here.
}


// ----------------------
// Initialization
// ----------------------

// Set canvas size immediately
ensureCanvasSize();

// Initialize MediaPipe with error handling
let hands = null;
let camera = null;

function initMediaPipe() {
    try {
        if (typeof Hands === 'undefined') {
            throw new Error('MediaPipe Hands library not loaded');
        }

        hands = new Hands({
            locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/${file}`;
            }
        });

        hands.setOptions({
            maxNumHands: 1,
            modelComplexity: 1,
            minDetectionConfidence: 0.7,
            minTrackingConfidence: 0.7
        });

        hands.onResults(onResults);

        // Camera
        if (typeof Camera === 'undefined') {
            throw new Error('Camera utils library not loaded');
        }

        camera = new Camera(videoElement, {
            onFrame: async () => {
                if (currentMode === 'camera' && hands) {
                    try {
                        await hands.send({ image: videoElement });
                    } catch (e) {
                        console.error('MediaPipe frame error:', e);
                    }
                }
            },
            width: 640,
            height: 480
        });

        camera.start().then(() => {
            cameraReady = true;
            console.log('Camera started successfully');
        }).catch((err) => {
            console.error('Camera start failed:', err);
            showCameraError();
        });

    } catch (err) {
        console.error('MediaPipe init failed:', err);
        showCameraError();
    }
}

function showCameraError() {
    const errorBanner = document.getElementById('camera-error');
    if (errorBanner) errorBanner.classList.remove('hidden');
    // Show popup error
    showErrorPopup('Camera Not Available', 'Could not access camera or load hand tracking. You can still draw with your mouse or touchscreen!');
    // Auto-switch to draw mode
    switchMode('draw');
}

// Resize Canvas to match Video
videoElement.addEventListener('loadeddata', () => {
    canvasElement.width = videoElement.videoWidth || 640;
    canvasElement.height = videoElement.videoHeight || 480;
});

// Also resize on window resize
window.addEventListener('resize', () => {
    if (currentMode === 'draw') {
        ensureCanvasSize();
    }
});

// ----------------------
// Mouse & Touch Drawing (Draw Mode)
// ----------------------

function getCanvasCoords(e) {
    const rect = canvasElement.getBoundingClientRect();
    let clientX, clientY;

    if (e.touches && e.touches.length > 0) {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
    } else {
        clientX = e.clientX;
        clientY = e.clientY;
    }

    // Return normalized coordinates [0, 1]
    return {
        x: (clientX - rect.left) / rect.width,
        y: (clientY - rect.top) / rect.height
    };
}

canvasElement.addEventListener('mousedown', (e) => {
    if (currentMode !== 'draw') return;
    e.preventDefault();
    mouseDown = true;
    isWriting = true;

    if (strokeStartTime === null) {
        strokeStartTime = performance.now();
    }

    const coords = getCanvasCoords(e);
    const t = Math.round(performance.now() - strokeStartTime);
    pathPoints.push({ x: coords.x, y: coords.y, t: t });
    lastPoint = { x: coords.x * canvasElement.width, y: coords.y * canvasElement.height };

    if (gestureIndicator) {
        gestureIndicator.innerHTML = '<i class="fas fa-pen-fancy"></i> <span>Drawing!</span>';
        gestureIndicator.classList.add('active');
    }
});

canvasElement.addEventListener('mousemove', (e) => {
    if (currentMode !== 'draw' || !mouseDown) return;
    e.preventDefault();

    const coords = getCanvasCoords(e);
    const t = Math.round(performance.now() - strokeStartTime);
    pathPoints.push({ x: coords.x, y: coords.y, t: t });

    // Draw on canvas
    const px = { x: coords.x * canvasElement.width, y: coords.y * canvasElement.height };
    if (lastPoint) {
        canvasCtx.lineWidth = 8;
        canvasCtx.lineCap = 'round';
        canvasCtx.lineJoin = 'round';
        const qc = getQualityColors();
        const gradient = canvasCtx.createLinearGradient(0, 0, canvasElement.width, canvasElement.height);
        gradient.addColorStop(0, qc.c1);
        gradient.addColorStop(1, qc.c2);
        canvasCtx.strokeStyle = gradient;
        canvasCtx.shadowBlur = 10;
        canvasCtx.shadowColor = qc.shadow;
        canvasCtx.beginPath();
        canvasCtx.moveTo(lastPoint.x, lastPoint.y);
        canvasCtx.lineTo(px.x, px.y);
        canvasCtx.stroke();
    }
    lastPoint = px;
});

canvasElement.addEventListener('mouseup', (e) => {
    if (currentMode !== 'draw') return;
    mouseDown = false;
    isWriting = false;
    lastPoint = null;
    if (gestureIndicator) {
        gestureIndicator.innerHTML = '<i class="fas fa-mouse-pointer"></i> <span>Click and drag to draw!</span>';
        gestureIndicator.classList.remove('active');
    }
});

canvasElement.addEventListener('mouseleave', (e) => {
    if (currentMode !== 'draw') return;
    mouseDown = false;
    isWriting = false;
    lastPoint = null;
});

// Touch support
canvasElement.addEventListener('touchstart', (e) => {
    if (currentMode !== 'draw') return;
    e.preventDefault();
    mouseDown = true;
    isWriting = true;

    if (strokeStartTime === null) {
        strokeStartTime = performance.now();
    }

    const coords = getCanvasCoords(e);
    const t = Math.round(performance.now() - strokeStartTime);
    pathPoints.push({ x: coords.x, y: coords.y, t: t });
    lastPoint = { x: coords.x * canvasElement.width, y: coords.y * canvasElement.height };

    if (gestureIndicator) {
        gestureIndicator.innerHTML = '<i class="fas fa-pen-fancy"></i> <span>Drawing!</span>';
        gestureIndicator.classList.add('active');
    }
}, { passive: false });

canvasElement.addEventListener('touchmove', (e) => {
    if (currentMode !== 'draw' || !mouseDown) return;
    e.preventDefault();

    const coords = getCanvasCoords(e);
    const t = Math.round(performance.now() - strokeStartTime);
    pathPoints.push({ x: coords.x, y: coords.y, t: t });

    const px = { x: coords.x * canvasElement.width, y: coords.y * canvasElement.height };
    if (lastPoint) {
        canvasCtx.lineWidth = 8;
        canvasCtx.lineCap = 'round';
        canvasCtx.lineJoin = 'round';
        const qc = getQualityColors();
        const gradient = canvasCtx.createLinearGradient(0, 0, canvasElement.width, canvasElement.height);
        gradient.addColorStop(0, qc.c1);
        gradient.addColorStop(1, qc.c2);
        canvasCtx.strokeStyle = gradient;
        canvasCtx.shadowBlur = 10;
        canvasCtx.shadowColor = qc.shadow;
        canvasCtx.beginPath();
        canvasCtx.moveTo(lastPoint.x, lastPoint.y);
        canvasCtx.lineTo(px.x, px.y);
        canvasCtx.stroke();
    }
    lastPoint = px;
}, { passive: false });

canvasElement.addEventListener('touchend', (e) => {
    if (currentMode !== 'draw') return;
    mouseDown = false;
    isWriting = false;
    lastPoint = null;
    if (gestureIndicator) {
        gestureIndicator.innerHTML = '<i class="fas fa-mouse-pointer"></i> <span>Click and drag to draw!</span>';
        gestureIndicator.classList.remove('active');
    }
});

// Start MediaPipe initialization (non-blocking)
initMediaPipe();


// ----------------------
// Interactions
// ----------------------

document.getElementById('clear-btn').addEventListener('click', () => {
    showingFeedback = false;
    feedbackErrors = null;
    pathPoints = [];
    strokeStartTime = null;
    mouseDown = false;
    lastPoint = null;
    currentStrokeQuality = 'low';
    // Reset EMA smoother and gesture state
    smoothX = null;
    smoothY = null;
    currentGesture = 'NEUTRAL';
    gestureHoldFrames = 0;
    isWriting = false;
    isPenDown = false;
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);

    // Reset score display
    const liveScore = document.getElementById('live-score');
    const accuracyBar = document.getElementById('accuracy-bar');
    const statusText = document.getElementById('status-text');
    if (liveScore) liveScore.innerText = '0%';
    if (accuracyBar) { accuracyBar.style.width = '0%'; accuracyBar.style.background = '#db2777'; }
    if (statusText) statusText.innerText = 'Start writing...';

    // In draw mode, repaint background
    if (currentMode === 'draw') {
        canvasElement.style.background = '#1a1a2e';
    }
});

document.getElementById('submit-btn').addEventListener('click', () => {
    if (pathPoints.length < 10) {
        showErrorPopup('Not Enough Input', 'Please write the letter first! Draw more strokes before submitting.');
        return;
    }
    stopLiveScoring();
    submitAttempt();
});

// ──────────────────────────────────────────────────────────────
// PATH NORMALIZATION — match recognition test coordinate space
// ──────────────────────────────────────────────────────────────
function preparePathForServer(points) {
    if (!points || points.length === 0) return points;

    let prepared = points.map(p => ({ x: p.x, y: p.y, t: p.t }));

    // 1. Camera mode: mirror x-coordinates.
    //    MediaPipe coordinates are in camera space, but the display is
    //    mirrored (CSS scaleX(-1)). The user sees the letter correctly,
    //    but stored coordinates are horizontally flipped.
    //    Fix: flip x so the data matches what the user actually intended.
    if (currentMode === 'camera') {
        prepared = prepared.map(p => ({ x: 1.0 - p.x, y: p.y, t: p.t }));
    }

    // 2. Adjust for canvas aspect ratio → square-normalized space.
    //    The recognition test uses a square 400×400 canvas (1:1 proportions).
    //    The air-writing canvas may be rectangular (e.g. 640×480 from video).
    //    Without correction, letters get distorted when stroke_to_image()
    //    maps [0,1]×[0,1] onto a square image.
    const rect = canvasElement.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;

    if (w > 0 && h > 0 && Math.abs(w - h) > 2) {
        const maxDim = Math.max(w, h);
        const xScale = w / maxDim;
        const yScale = h / maxDim;
        const xOffset = (1 - xScale) / 2;
        const yOffset = (1 - yScale) / 2;

        prepared = prepared.map(p => ({
            x: p.x * xScale + xOffset,
            y: p.y * yScale + yOffset,
            t: p.t
        }));
    }

    return prepared;
}

async function submitAttempt() {
    const statusDiv = document.getElementById('status-text');
    statusDiv.innerText = "Checking your magic... ✨";

    try {
        const serverPath = preparePathForServer(pathPoints);
        const response = await fetch('/api/submit_attempt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                letter_id: typeof CURRENT_LETTER_ID !== 'undefined' ? CURRENT_LETTER_ID : 1,
                path: serverPath,
                input_mode: currentMode  // 'camera' or 'draw'
            })
        });

        if (!response.ok) {
            throw new Error('Server returned status ' + response.status);
        }

        const result = await response.json();

        if (!result.success && !result.blocked) {
            showErrorPopup('Submission Failed', result.message || result.error || 'An unexpected error occurred. Please try again.');
            statusDiv.innerText = "Error. Try again.";
            return;
        }

        // CHECK: AI Evaluation Agent blocked the attempt
        if (result.blocked) {
            const cls = result.classification || 'SCRIBBLE_OR_INVALID';
            if (cls === 'SCRIBBLE_OR_INVALID') {
                statusDiv.innerText = "That wasn't a letter shape — try again! 🖊️";
            } else if (cls === 'WRONG_LETTER') {
                statusDiv.innerText = "Different letter detected — let's practise the right one! 🔄";
            } else {
                statusDiv.innerText = "Try again! You can do it! 🐝";
            }
            showBlockedModal(result);
            return;
        }

        showResultModal(result.score, result.stars, result.feedback_level, result.breakdown, result.guidance || [], result.cnn_confidence, result.scoring_method, result.child_message);

        // Update live score display
        const liveScore = document.getElementById('live-score');
        const accuracyBar = document.getElementById('accuracy-bar');
        if (liveScore) liveScore.innerText = result.score.toFixed(1) + '%';
        if (accuracyBar) accuracyBar.style.width = result.score + '%';

        // Draw Feedback Path with error classification
        if (result.error_indices || result.error_types) {
            showingFeedback = true;
            feedbackErrors = result.error_indices;

            const feedbackCanvas = document.getElementById('feedback_canvas');
            if (feedbackCanvas) {
                feedbackCanvas.width = feedbackCanvas.offsetWidth;
                feedbackCanvas.height = feedbackCanvas.offsetHeight;
                const fCtx = feedbackCanvas.getContext('2d');
                const feedbackPath = preparePathForServer(pathPoints);
                drawFeedbackPath(
                    feedbackPath, feedbackErrors, fCtx,
                    feedbackCanvas.width, feedbackCanvas.height,
                    result.error_types || {}
                );
            }
        }

    } catch (error) {
        showErrorPopup('Connection Error', 'Could not reach the server. Please check your connection and try again.');
        statusDiv.innerText = "Connection error. Try again.";
    }
}

function showBlockedModal(result) {
    const modal = document.getElementById('success-modal');
    const starsContainer = document.getElementById('modal-stars');
    const scoreText = document.getElementById('modal-score');
    const title = document.getElementById('modal-title');
    const resultMessage = document.getElementById('result-message');
    const letterComparison = document.getElementById('letter-comparison');

    modal.classList.remove('hidden');

    const cls = result.classification || 'SCRIBBLE_OR_INVALID';

    // No stars for blocked attempts (give_stars=false)
    starsContainer.innerHTML = '';
    if (!result.give_stars) {
        for (let i = 0; i < 5; i++) {
            const star = document.createElement('i');
            star.classList.add('fas', 'fa-star');
            starsContainer.appendChild(star);
        }
    }

    // Classification-aware title
    if (cls === 'WRONG_LETTER') {
        title.innerText = "Oops! Different Letter 🔄";
    } else {
        // SCRIBBLE_OR_INVALID (covers scribble + unrecognizable)
        title.innerText = "Let's try again! ✏️";
    }

    // Child-friendly message from backend
    if (resultMessage) {
        resultMessage.textContent = result.child_message || result.message || 'Try again with the correct letter!';
    }

    // Show letter comparison ONLY for WRONG_LETTER classification
    if (letterComparison && cls === 'WRONG_LETTER') {
        const writtenEl = document.getElementById('written-letter');
        const targetEl = document.getElementById('target-letter-display');
        if (writtenEl) writtenEl.textContent = result.predicted_letter || '?';
        if (targetEl) targetEl.textContent = result.target_letter || '?';
        letterComparison.style.display = 'flex';
    } else if (letterComparison) {
        letterComparison.style.display = 'none';
    }

    // Show feedback canvas with child's drawing for SCRIBBLE_OR_INVALID (so they see what they drew)
    if (cls === 'SCRIBBLE_OR_INVALID') {
        const feedbackCanvas = document.getElementById('feedback_canvas');
        if (feedbackCanvas && pathPoints.length > 1) {
            feedbackCanvas.width = feedbackCanvas.offsetWidth;
            feedbackCanvas.height = feedbackCanvas.offsetHeight;
            const fCtx = feedbackCanvas.getContext('2d');
            const correctedPath = preparePathForServer(pathPoints);
            // Draw their path in red to show it wasn't recognized
            fCtx.clearRect(0, 0, feedbackCanvas.width, feedbackCanvas.height);
            fCtx.strokeStyle = '#ef4444';
            fCtx.lineWidth = 6;
            fCtx.lineCap = 'round';
            fCtx.lineJoin = 'round';
            fCtx.beginPath();
            for (let i = 0; i < correctedPath.length; i++) {
                const px = correctedPath[i].x * feedbackCanvas.width;
                const py = correctedPath[i].y * feedbackCanvas.height;
                if (i === 0) fCtx.moveTo(px, py);
                else fCtx.lineTo(px, py);
            }
            fCtx.stroke();
            // Draw label
            fCtx.font = 'bold 14px Fredoka, sans-serif';
            fCtx.fillStyle = '#ef4444';
            fCtx.textAlign = 'center';
            fCtx.fillText('Let\'s try to draw the letter shape!', feedbackCanvas.width / 2, feedbackCanvas.height - 10);
        }
    }

    // Hide score / breakdown for blocked attempts
    if (scoreText) scoreText.style.display = 'none';
    const breakdownDetails = document.getElementById('score-breakdown-details');
    if (breakdownDetails) breakdownDetails.style.display = 'none';

    // Show guidance based on AI classification
    const guidanceContainer = document.getElementById('correction-guidance');
    const guidanceList = document.getElementById('guidance-list');
    if (cls === 'SCRIBBLE_OR_INVALID') {
        if (guidanceContainer && guidanceList) {
            guidanceList.innerHTML = '';
            const tips = [
                "📍 Look at the letter on the right side carefully",
                "✏️ Try to trace the same shape slowly",
                "🐝 Take your time — slow drawing is better!"
            ];
            tips.forEach(tip => {
                const li = document.createElement('li');
                li.style.marginBottom = '4px';
                li.textContent = tip;
                guidanceList.appendChild(li);
            });
            guidanceContainer.style.background = '#fef2f2';
            guidanceContainer.style.borderLeftColor = '#ef4444';
            guidanceContainer.style.display = 'block';
        }
    } else if (cls === 'WRONG_LETTER') {
        if (guidanceContainer && guidanceList) {
            guidanceList.innerHTML = '';
            const tips = [
                "👀 Look carefully at the letter you need to write",
                `✍️ The letter '${result.target_letter || ''}' is different from '${result.predicted_letter || ''}'`,
                "💪 You recognised a letter — just the wrong one! Try again!"
            ];
            tips.forEach(tip => {
                const li = document.createElement('li');
                li.style.marginBottom = '4px';
                li.textContent = tip;
                guidanceList.appendChild(li);
            });
            guidanceContainer.style.background = '#fffbeb';
            guidanceContainer.style.borderLeftColor = '#f59e0b';
            guidanceContainer.style.display = 'block';
        }
    } else {
        if (guidanceContainer) guidanceContainer.style.display = 'none';
    }
}

function showResultModal(score, stars, feedbackLevel, breakdown, guidance, cnnConfidence, scoringMethod, childMessage) {
    const modal = document.getElementById('success-modal');
    const starsContainer = document.getElementById('modal-stars');
    const scoreText = document.getElementById('modal-score');
    const title = document.getElementById('modal-title');
    const resultMessage = document.getElementById('result-message');
    const letterComparison = document.getElementById('letter-comparison');

    modal.classList.remove('hidden');

    // Hide letter comparison for normal results
    if (letterComparison) letterComparison.style.display = 'none';

    // Explicit score display
    scoreText.innerText = `Score: ${score.toFixed(1)}%`;
    scoreText.style.display = 'block';

    // Show child-friendly message from backend
    if (resultMessage) {
        resultMessage.textContent = childMessage || '';
    }

    // Use stars from backend (ML-first classification)
    if (typeof stars === 'undefined' || stars === null) {
        // Fallback star calculation matching backend thresholds
        if (score >= 90) stars = 5;
        else if (score >= 75) stars = 4;
        else if (score >= 60) stars = 3;
        else if (score >= 40) stars = 2;
        else stars = 1;
    }

    // Render Stars (Out of 5)
    starsContainer.innerHTML = '';
    for (let i = 0; i < 5; i++) {
        const star = document.createElement('i');
        star.classList.add('fas', 'fa-star');
        if (i < stars) star.classList.add('active');
        starsContainer.appendChild(star);
    }

    // Feedback title based on level
    if (feedbackLevel === 'excellent' || stars === 5) {
        title.innerText = "Superstar! 🌟✨";
    } else if (feedbackLevel === 'good' || stars >= 3) {
        title.innerText = "Great Job! 🎉";
    } else if (feedbackLevel === 'fair' || stars >= 2) {
        title.innerText = "Good Try! 👍";
    } else {
        title.innerText = "Keep Practicing! 💪";
    }

    // Show correction guidance
    const guidanceContainer = document.getElementById('correction-guidance');
    const guidanceList = document.getElementById('guidance-list');
    if (guidanceContainer && guidanceList && guidance && guidance.length > 0) {
        guidanceList.innerHTML = '';
        guidance.forEach(g => {
            const li = document.createElement('li');
            li.style.marginBottom = '4px';
            li.textContent = g;
            guidanceList.appendChild(li);
        });
        // Color guidance based on score
        if (score >= 88) {
            guidanceContainer.style.background = '#f0fdf4';
            guidanceContainer.style.borderLeftColor = '#22c55e';
        } else if (score >= 55) {
            guidanceContainer.style.background = '#fffbeb';
            guidanceContainer.style.borderLeftColor = '#f59e0b';
        } else {
            guidanceContainer.style.background = '#fef2f2';
            guidanceContainer.style.borderLeftColor = '#ef4444';
        }
        guidanceContainer.style.display = 'block';
    } else if (guidanceContainer) {
        guidanceContainer.style.display = 'none';
    }

    // Show algorithm breakdown if container exists
    const breakdownDetails = document.getElementById('score-breakdown-details');
    if (breakdownDetails) breakdownDetails.style.display = 'block';
    const breakdownContainer = document.getElementById('score-breakdown');
    if (breakdownContainer && breakdown) {
        let breakdownHTML = `
            <div class="breakdown-grid">
                <div class="breakdown-item">
                    <span class="breakdown-label">Alignment</span>
                    <span class="breakdown-value">${(breakdown.procrustes || 0).toFixed(3)}</span>
                </div>
                <div class="breakdown-item">
                    <span class="breakdown-label">Worst Error</span>
                    <span class="breakdown-value">${(breakdown.hausdorff || 0).toFixed(3)}</span>
                </div>
                <div class="breakdown-item">
                    <span class="breakdown-label">Shape</span>
                    <span class="breakdown-value">${(breakdown.chamfer || 0).toFixed(3)}</span>
                </div>
                <div class="breakdown-item">
                    <span class="breakdown-label">Timing</span>
                    <span class="breakdown-value">${(breakdown.dtw || 0).toFixed(3)}</span>
                </div>
                <div class="breakdown-item">
                    <span class="breakdown-label">Coverage</span>
                    <span class="breakdown-value">${(breakdown.coverage || 0).toFixed(1)}%</span>
                </div>`;

        // Show CNN confidence row for blended scoring
        if (cnnConfidence !== null && cnnConfidence !== undefined) {
            breakdownHTML += `
                <div class="breakdown-item">
                    <span class="breakdown-label">CNN Match</span>
                    <span class="breakdown-value">${cnnConfidence.toFixed(1)}%</span>
                </div>`;
        }

        // Show scoring method badge
        if (scoringMethod) {
            const methodLabel = scoringMethod === 'blended' ? 'Blended (Geo+CNN)'
                : scoringMethod === 'blended_penalised' ? 'Blended (Penalised)'
                    : 'Geometric Only';
            breakdownHTML += `
                <div class="breakdown-item" style="grid-column: 1 / -1; text-align:center; opacity:0.7;">
                    <span class="breakdown-label">Method</span>
                    <span class="breakdown-value" style="font-size:0.85em">${methodLabel}</span>
                </div>`;
        }

        breakdownHTML += `</div>`;
        breakdownContainer.innerHTML = breakdownHTML;
        breakdownContainer.style.display = 'block';
    }
}

function drawFeedbackPath(points, errorIndices, targetCtx, width, height, errorTypes) {
    if (!points || points.length < 2) return;

    const ctx = targetCtx || canvasCtx;
    const w = width || canvasElement.width;
    const h = height || canvasElement.height;

    // Clear canvas for feedback redraw
    ctx.clearRect(0, 0, w, h);

    // Build error classification lookup
    const errorSet = new Set(errorIndices || []);
    const wrongStartSet = new Set((errorTypes && errorTypes.wrong_start) || []);
    const missingSet = new Set((errorTypes && errorTypes.missing_stroke) || []);
    const extraSet = new Set((errorTypes && errorTypes.extra_stroke) || []);
    const directionSet = new Set((errorTypes && errorTypes.wrong_direction) || []);

    ctx.lineWidth = 8;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    // Draw segment by segment with classified colors
    for (let i = 0; i < points.length - 1; i++) {
        ctx.beginPath();
        ctx.moveTo(points[i].x * w, points[i].y * h);
        ctx.lineTo(points[i + 1].x * w, points[i + 1].y * h);

        // Color by error type (priority order)
        if (wrongStartSet.has(i) || wrongStartSet.has(i + 1)) {
            // Wrong start point — magenta
            ctx.strokeStyle = '#ff00ff';
            ctx.shadowColor = '#ff44ff';
            ctx.shadowBlur = 8;
        } else if (directionSet.has(i) || directionSet.has(i + 1)) {
            // Wrong direction — yellow/amber
            ctx.strokeStyle = '#ffaa00';
            ctx.shadowColor = '#ffcc44';
            ctx.shadowBlur = 8;
        } else if (missingSet.has(i) || missingSet.has(i + 1)) {
            // Missing stroke area — red
            ctx.strokeStyle = '#ff0000';
            ctx.shadowColor = '#ff4444';
            ctx.shadowBlur = 5;
        } else if (extraSet.has(i) || extraSet.has(i + 1)) {
            // Extra unwanted stroke — orange
            ctx.strokeStyle = '#ff6600';
            ctx.shadowColor = '#ff8844';
            ctx.shadowBlur = 5;
        } else if (errorSet.has(i) || errorSet.has(i + 1)) {
            // General error (poor shape) — red
            ctx.strokeStyle = '#ff0000';
            ctx.shadowColor = '#ff4444';
            ctx.shadowBlur = 5;
        } else {
            // Correct — green
            ctx.strokeStyle = '#00ff00';
            ctx.shadowColor = '#44ff44';
            ctx.shadowBlur = 5;
        }

        ctx.stroke();
    }

    // Draw start point indicator if wrong start detected
    if (wrongStartSet.size > 0) {
        ctx.beginPath();
        ctx.arc(points[0].x * w, points[0].y * h, 12, 0, 2 * Math.PI);
        ctx.fillStyle = 'rgba(255, 0, 255, 0.5)';
        ctx.fill();
        ctx.strokeStyle = '#ff00ff';
        ctx.lineWidth = 2;
        ctx.shadowBlur = 0;
        ctx.stroke();

        // "Start Here" text
        ctx.font = '12px Fredoka, sans-serif';
        ctx.fillStyle = '#ff00ff';
        ctx.fillText('Start Here ↗', points[0].x * w + 15, points[0].y * h - 5);
    }
}

function resetGame() {
    document.getElementById('success-modal').classList.add('hidden');
    showingFeedback = false;
    feedbackErrors = null;
    pathPoints = [];
    strokeStartTime = null; // Reset timestamp
    currentStrokeQuality = 'low';
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);

    // Clear Feedback Canvas
    const feedbackCanvas = document.getElementById('feedback_canvas');
    if (feedbackCanvas) {
        const fCtx = feedbackCanvas.getContext('2d');
        fCtx.clearRect(0, 0, feedbackCanvas.width, feedbackCanvas.height);
    }

    // Clear breakdown
    const breakdownContainer = document.getElementById('score-breakdown');
    if (breakdownContainer) {
        breakdownContainer.innerHTML = '';
        breakdownContainer.style.display = 'none';
    }

    // Clear guidance
    const guidanceContainer = document.getElementById('correction-guidance');
    if (guidanceContainer) {
        guidanceContainer.style.display = 'none';
    }

    document.getElementById('status-text').innerText = "Start writing...";
    document.getElementById('live-score').innerText = "0%";
    document.getElementById('accuracy-bar').style.width = "0%";

    // Restart live scoring
    startLiveScoring();
}


// ----------------------
// Error Popup System
// ----------------------

function showErrorPopup(title, message) {
    const modal = document.getElementById('error-modal');
    const titleEl = document.getElementById('error-modal-title');
    const msgEl = document.getElementById('error-modal-message');
    if (modal && titleEl && msgEl) {
        titleEl.innerText = '⚠️ ' + title;
        msgEl.innerText = message;
        modal.classList.remove('hidden');
    } else {
        // Fallback if error modal not present on this page
        alert(title + ': ' + message);
    }
}


// ----------------------
// Real-Time Live Scoring
// ----------------------

let liveScoreTimer = null;
const LIVE_SCORE_INTERVAL = 2000; // ms between live score requests
const MIN_POINTS_FOR_LIVE = 15;   // minimum points before scoring

function startLiveScoring() {
    stopLiveScoring();
    liveScoreTimer = setInterval(async () => {
        if (pathPoints.length >= MIN_POINTS_FOR_LIVE && !showingFeedback) {
            try {
                const liveServerPath = preparePathForServer(pathPoints);
                const response = await fetch('/api/live-score', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        letter_id: typeof CURRENT_LETTER_ID !== 'undefined' ? CURRENT_LETTER_ID : 1,
                        path: liveServerPath
                    })
                });
                const data = await response.json();
                if (data.success && data.score !== undefined) {
                    const liveScore = document.getElementById('live-score');
                    const accuracyBar = document.getElementById('accuracy-bar');
                    const statusText = document.getElementById('status-text');

                    if (liveScore) liveScore.innerText = data.score.toFixed(1) + '%';
                    if (accuracyBar) {
                        accuracyBar.style.width = data.score + '%';
                        // Color the progress bar based on quality
                        if (data.quality === 'good') {
                            accuracyBar.style.background = '#22c55e';
                        } else if (data.quality === 'fair') {
                            accuracyBar.style.background = '#f59e0b';
                        } else {
                            accuracyBar.style.background = '#db2777';
                        }
                    }
                    if (statusText) {
                        if (data.quality === 'good') {
                            statusText.innerText = "Looking good! Keep going... ✨";
                        } else if (data.quality === 'fair') {
                            statusText.innerText = "Getting there... keep writing!";
                        } else {
                            statusText.innerText = "Writing detected... continue!";
                        }
                    }
                    // Update stroke quality for real-time color
                    currentStrokeQuality = data.quality || 'low';
                }
            } catch (e) {
                // Silent failure for live scoring — don't interrupt user
            }
        }
    }, LIVE_SCORE_INTERVAL);
}

function stopLiveScoring() {
    if (liveScoreTimer) {
        clearInterval(liveScoreTimer);
        liveScoreTimer = null;
    }
}

// Start live scoring on page load
startLiveScoring();
