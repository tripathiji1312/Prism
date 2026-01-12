// --- MENU LOGIC ---
document.addEventListener("DOMContentLoaded", () => {
  const menuTrigger = document.getElementById("menuTrigger");
  const menuOverlay = document.getElementById("menuOverlay");
  const closeMenuBtn = document.getElementById("closeMenuBtn");
  const overlay = document.getElementById("overlay");
  const visualizerContainer = document.getElementById("visualizerContainer");
  const controlsContainer = document.getElementById("controlsContainer");

  // Menu Toggle
  menuTrigger.addEventListener("click", () =>
    menuOverlay.classList.add("active")
  );
  closeMenuBtn.addEventListener("click", () =>
    menuOverlay.classList.remove("active")
  );
  menuOverlay.addEventListener("click", (e) => {
    if (e.target === menuOverlay) menuOverlay.classList.remove("active");
  });

  // "Start" Overlay Interaction
  if (overlay) {
    overlay.addEventListener("click", () => {
      overlay.style.opacity = "0";
      setTimeout(() => (overlay.style.display = "none"), 500);

      // Show visualizer and recording controls
      visualizerContainer.style.opacity = "1";
      controlsContainer.style.opacity = "1";

      // Try to play audio if present
      const audio = document.getElementById("audio");
      if (audio)
        audio.play().catch((e) => console.log("Audio play blocked", e));
    });
  }
});

// --- UPLOAD & RECORDING LOGIC ---
document.addEventListener("DOMContentLoaded", () => {
  const uploadLink = document.getElementById("uploadLink");
  const videoInput = document.getElementById("videoInput");
  const statusText = document.getElementById("uploadStatus"); // For menu upload status
  const recStatus = document.getElementById("recStatus"); // For recording status

  // 1. Menu Upload Logic
  if (uploadLink) {
    uploadLink.addEventListener("click", (e) => {
      e.preventDefault();
      const menuOverlay = document.getElementById("menuOverlay");
      if (menuOverlay) menuOverlay.classList.remove("active");
      videoInput.click();
    });
  }

  if (videoInput) {
    videoInput.addEventListener("change", function () {
      if (this.files && this.files[0]) {
        validateAndUpload(this.files[0]);
      }
    });
  }

  function validateAndUpload(file) {
    const videoElement = document.createElement("video");
    videoElement.preload = "metadata";
    videoElement.onloadedmetadata = function () {
      window.URL.revokeObjectURL(videoElement.src);
      if (videoElement.duration > 9) {
        alert(`Video too long (${videoElement.duration.toFixed(1)}s). Max 9s.`);
        videoInput.value = "";
        return;
      }
      uploadToBackend(file);
    };
    videoElement.src = URL.createObjectURL(file);
  }

  // --- NEW RECORDING LOGIC ---
  const startRecBtn = document.getElementById("startRecBtn");
  const stopRecBtn = document.getElementById("stopRecBtn");
  const webcamVideo = document.getElementById("webcam");

  let mediaRecorder;
  let recordedChunks = [];
  let autoStopTimer;

  startRecBtn.addEventListener("click", () => {
    // Check stream
    if (!webcamVideo.srcObject) {
      alert("Webcam not active.");
      return;
    }

    const stream = webcamVideo.srcObject;
    mediaRecorder = new MediaRecorder(stream);
    recordedChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      // 1. Create File
      const blob = new Blob(recordedChunks, { type: "video/webm" });
      // Convert Blob to File object so we can reuse your upload function
      const file = new File([blob], "webcam_record.webm", {
        type: "video/webm",
      });

      // 2. Upload
      recStatus.innerText = "Processing & Uploading...";
      uploadToBackend(file, true); // Pass 'true' to indicate this is from live record
    };

    // Start Recording
    mediaRecorder.start();
    recStatus.innerText = "Recording... (9s left)";
    startRecBtn.disabled = true;
    stopRecBtn.disabled = false;

    // Auto-stop after 9 seconds
    autoStopTimer = setTimeout(() => {
      if (mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        resetControls();
        recStatus.innerText = "Auto-stopped. Uploading...";
      }
    }, 9000);
  });

  stopRecBtn.addEventListener("click", () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      clearTimeout(autoStopTimer); // Cancel the 9s timer
      mediaRecorder.stop();
      resetControls();
      recStatus.innerText = "Stopped. Uploading...";
    }
  });

  function resetControls() {
    startRecBtn.disabled = false;
    stopRecBtn.disabled = true;
  }

  // 4. Send Video + Wallet + Color to Backend (Shared Function)
  async function uploadToBackend(file, isLive = false) {
    // Use the correct status text depending on where the upload came from
    const currentStatus = isLive ? recStatus : statusText;

    currentStatus.innerText = "Uploading...";

    const userWallet =
      localStorage.getItem("walletAddress") || "0xUNKNOWN_WALLET";
    const screenColor = "RED";

    const formData = new FormData();
    formData.append("video", file);
    formData.append("wallet", userWallet);
    formData.append("screenColor", screenColor);

    try {
      const response = await fetch("http://localhost:8080/api/video/upload", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const result = await response.text();
        currentStatus.innerText = "Success! Uploaded.";
        console.log("Server response:", result);
        if (!isLive) alert("Video Uploaded Successfully!");
      } else {
        currentStatus.innerText = "Upload failed.";
        console.error("Server Error:", await response.text());
      }
    } catch (error) {
      console.error("Network Error:", error);
      currentStatus.innerText = "Error connecting to server.";
    }
  }
});
