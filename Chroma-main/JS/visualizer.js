'use strict';

const VIS_CONFIG = { radius: 130, barLen: 70, barCount: 80 };
const VIS_THEME = "#3BC1A8";

const visCanvas = document.getElementById("visualizer");
const visCtx = visCanvas.getContext("2d");

const video = document.getElementById("webcam");
const audio = document.getElementById("audio");
const overlay = document.getElementById("overlay");
const visContainer = document.querySelector('.visualizer-container');
const overlayText = document.querySelector('#overlay span');

let audioCtx, analyser, dataArray, source;
let isRunning = false;

// --- 1. SMART RESIZING LOGIC ---
function resizeVisualizer() {
    if (!visContainer || !overlayText) return; // Safety check

    const width = window.innerWidth;
    const height = window.innerHeight;
    
    // Base visualizer size including bars roughly (600px box covers it)
    const baseSize = 650; 
    
    // Available space (Subtract 150px for Header/Margins vertically)
    const availableHeight = height - 150; 
    
    // Calculate scale: Fit into Width OR Height, whichever is smaller
    // We cap it at 1 so it doesn't get pixelated on huge screens
    let scale = Math.min(width / baseSize, availableHeight / baseSize, 1);
    
    // Apply the scale
    visContainer.style.transform = `scale(${scale})`;
    
    // CHANGED: Increased padding values by 80px to move text upwards
    if (scale < 0.6) {
        overlayText.style.fontSize = "30px"; 
        overlay.style.paddingBottom = "160px"; // Was 80px
    } else {
        overlayText.style.fontSize = "50px"; 
        overlay.style.paddingBottom = "240px"; // Was 160px
    }
}

// Attach Resize Listeners
window.addEventListener('resize', resizeVisualizer);
// Run once on start
resizeVisualizer();

// --- 2. PRELOAD WEBCAM ---
if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => { video.srcObject = stream; })
        .catch(err => console.log("Camera Error: " + err));
}

// --- 3. CLICK TO START ---
if (overlay) {
    overlay.addEventListener("click", async () => {
        overlay.style.opacity = "0";
        setTimeout(() => { overlay.style.display = "none"; }, 500);

        visContainer.style.opacity = "1";
        
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!audioCtx) audioCtx = new AudioContext();
            await audioCtx.resume();
            await audio.play();

            if (!analyser) {
                analyser = audioCtx.createAnalyser();
                analyser.fftSize = 256; 
                const bufferLength = analyser.frequencyBinCount;
                dataArray = new Uint8Array(bufferLength);
            }

            if (!source) {
                // Try/Catch for CORS errors if running locally without server
                try {
                    source = audioCtx.createMediaElementSource(audio);
                    source.connect(analyser);
                    analyser.connect(audioCtx.destination);
                } catch (e) {
                    console.warn("Visualizer requires a local server (CORS restriction). Audio will still play.");
                }
            }
            
            if (!isRunning) {
                isRunning = true;
                draw();
            }
        } catch (error) {
            console.error("Audio Init Failed:", error);
        }
    });
}

function draw() {
    requestAnimationFrame(draw);
    if (!analyser) return;

    analyser.getByteFrequencyData(dataArray);
    
    visCtx.clearRect(0, 0, visCanvas.width, visCanvas.height);

    const cx = visCanvas.width / 2;
    const cy = visCanvas.height / 2;
    const angleStep = (Math.PI * 2) / VIS_CONFIG.barCount;

    for (let i = 0; i < VIS_CONFIG.barCount; i++) {
        let norm = i / (VIS_CONFIG.barCount / 2);
        if (norm > 1) norm = 2 - norm;
        
        const dataIdx = Math.floor(norm * 60) + 4; 
        const val = dataArray[dataIdx] || 0;
        const normalizedVal = val / 255;
        const len = Math.pow(normalizedVal, 3) * VIS_CONFIG.barLen;

        const angle = (i * angleStep) - (Math.PI / 2);
        const nx = Math.cos(angle);
        const ny = Math.sin(angle);

        const x1 = cx + nx * (VIS_CONFIG.radius + 2);
        const y1 = cy + ny * (VIS_CONFIG.radius + 2);
        const x2 = cx + nx * (VIS_CONFIG.radius + 2 + len);
        const y2 = cy + ny * (VIS_CONFIG.radius + 2 + len);

        visCtx.strokeStyle = VIS_THEME;
        visCtx.shadowBlur = normalizedVal * 15; 
        visCtx.shadowColor = VIS_THEME;
        visCtx.lineWidth = 8; 
        visCtx.lineCap = "butt"; 

        visCtx.beginPath();
        visCtx.moveTo(x1, y1);
        visCtx.lineTo(x2, y2);
        visCtx.stroke();
        visCtx.shadowBlur = 0;
    }

    visCtx.strokeStyle = "#1a2e33"; 
    visCtx.lineWidth = 0;
    visCtx.beginPath();
    visCtx.arc(cx, cy, VIS_CONFIG.radius, 0, Math.PI * 2);
    visCtx.stroke();
}