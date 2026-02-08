const videoElement = document.getElementById('input_video');
const canvasElement = document.getElementById('output_canvas');
const canvasCtx = canvasElement.getContext('2d');
const gestureIndicator = document.getElementById('gesture-indicator');
const statusText = document.getElementById('status-text');

let isWriting = false;
let pathPoints = []; // Stores {x, y} normalized coordinates
let lastPoint = null;

// MediaPipe Setup
function onResults(results) {
    canvasCtx.save();
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);

    // Draw the camera frame first (optional visual style, maybe we want it clean)
    // For debugging, it helps to see the video. 
    // We can overlay a semi-transparent layer for "Magical" feel if needed in CSS.
    // Actually, let's NOT draw the image to the canvas, we rely on the <video> tag behind it 
    // to show the feed. The canvas is just for the trail.
    // Wait, if we don't draw the image, the landmarks will float on transparency. That's good.

    // 1. Check for hands
    if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
        // Only track the first hand
        const landmarks = results.multiHandLandmarks[0];

        // 2. Extract Key Landmarks
        const indexTip = landmarks[8];
        const thumbTip = landmarks[4];

        // 3. Draw Hand Skeleton (Optional, maybe just the finger tip?)
        // Let's draw a cute cursor on the index tip
        drawCursor(indexTip, isWriting);

        // 4. Calculate Pinch Distance (Euclidean)
        // Note: Landmarks are normalized [0.0, 1.0]. We need pixel coords for distance check, 
        // or just check normalized distance with aspect ratio correction.
        // Let's use simple normalized distance for now, assuming aspect ratio isn't too wild.
        // Actually, converting to pixel coords is safer for "30px" threshold logic.
        const width = canvasElement.width;
        const height = canvasElement.height;

        const idxPx = { x: indexTip.x * width, y: indexTip.y * height };
        const thbPx = { x: thumbTip.x * width, y: thumbTip.y * height };

        const distance = Math.sqrt(
            Math.pow(idxPx.x - thbPx.x, 2) + Math.pow(idxPx.y - thbPx.y, 2)
        );

        // Threshold: e.g., 40px (tunable)
        const PINCH_THRESHOLD = 50;

        if (distance < PINCH_THRESHOLD) {
            if (!isWriting) {
                isWriting = true;
                gestureIndicator.innerHTML = '<i class="fas fa-pen-fancy"></i> <span>Writing!</span>';
                gestureIndicator.classList.add('active');
            }
        } else {
            if (isWriting) {
                isWriting = false;
                gestureIndicator.innerHTML = '<i class="fas fa-hand-paper"></i> <span>Hovering</span>';
                gestureIndicator.classList.remove('active');
                lastPoint = null; // Break the line
            }
        }

        // 5. Writing Screen Logic
        if (isWriting) {
            // Add point to path
            // Invert X because the canvas is mirrored visually via CSS "transform: scaleX(-1)"
            // BUT MediaPipe coordinates are already matched to the source image.
            // If we draw at (x,y), and the canvas is flipped, it will look correct to the user 
            // acting as a mirror.
            // We store NORMALIZED coordinates [0, 1].

            pathPoints.push({ x: indexTip.x, y: indexTip.y });

            // Draw Line
            if (lastPoint) {
                drawMagicalStroke(lastPoint, idxPx);
            }
            lastPoint = idxPx;
        }

    } else {
        isWriting = false;
    }

    // Draw the accumulated path
    // (We need to redraw the persistent path every frame because we clearRect above)
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

function drawFullTrail() {
    if (pathPoints.length < 2) return;

    canvasCtx.lineWidth = 8;
    canvasCtx.lineCap = 'round';
    canvasCtx.lineJoin = 'round';
    // Gradient stroke
    const gradient = canvasCtx.createLinearGradient(0, 0, canvasElement.width, canvasElement.height);
    gradient.addColorStop(0, '#6a11cb');
    gradient.addColorStop(1, '#2575fc');
    canvasCtx.strokeStyle = gradient;
    canvasCtx.shadowBlur = 10;
    canvasCtx.shadowColor = '#2575fc';

    canvasCtx.beginPath();
    const w = canvasElement.width;
    const h = canvasElement.height;

    // Start
    canvasCtx.moveTo(pathPoints[0].x * w, pathPoints[0].y * h);

    for (let i = 1; i < pathPoints.length; i++) {
        // Basic smoothing could be added here (quadratic bezier)
        // For now, straight lines
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

const hands = new Hands({
    locateFile: (file) => {
        return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
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
const camera = new Camera(videoElement, {
    onFrame: async () => {
        await hands.send({ image: videoElement });
    },
    width: 640,
    height: 480
});

// Start
camera.start();

// Resize Canvas to match Video
videoElement.addEventListener('loadeddata', () => {
    canvasElement.width = videoElement.videoWidth;
    canvasElement.height = videoElement.videoHeight;
});


// ----------------------
// Interactions
// ----------------------

document.getElementById('clear-btn').addEventListener('click', () => {
    pathPoints = [];
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
});

document.getElementById('submit-btn').addEventListener('click', () => {
    if (pathPoints.length < 10) {
        alert("Please write something first!");
        return;
    }
    submitAttempt();
});

async function submitAttempt() {
    const statusDiv = document.getElementById('status-text');
    statusDiv.innerText = "Checking your magic... ✨";

    try {
        const response = await fetch('/api/submit_attempt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                letter_id: typeof CURRENT_LETTER_ID !== 'undefined' ? CURRENT_LETTER_ID : 1, // Global var from HTML
                path: pathPoints
            })
        });

        const result = await response.json();

        console.log("Score:", result.score);
        showResultModal(result.score);

    } catch (error) {
        console.error("Error submitting path:", error);
        statusDiv.innerText = "Oops! The magic fizzled out.";
    }
}

function showResultModal(score) {
    const modal = document.getElementById('success-modal');
    const starsContainer = document.getElementById('modal-stars');
    const scoreText = document.getElementById('modal-score');
    const title = document.getElementById('modal-title');

    modal.classList.remove('hidden');
    scoreText.innerText = `Accuracy: ${score.toFixed(1)}%`;

    // Calculate Stars (Aligned with backend app.py)
    let stars = 0;
    if (score >= 85) stars = 3;
    else if (score >= 60) stars = 2;
    else if (score >= 30) stars = 1;

    // Render Stars
    starsContainer.innerHTML = '';
    for (let i = 0; i < 3; i++) {
        const star = document.createElement('i');
        star.classList.add('fas', 'fa-star');
        if (i < stars) star.classList.add('active');
        starsContainer.appendChild(star);
    }

    // Text
    if (stars === 3) title.innerText = "Perfect! 🌟";
    else if (stars === 2) title.innerText = "Great Job! 🎉";
    else if (stars === 1) title.innerText = "Good Try! 👍";
    else title.innerText = "Keep Practicing! 💪";
}
