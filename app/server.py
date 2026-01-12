# File: app/server.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel
import uvicorn
import json
import os
import cv2
import numpy as np
import base64
import shutil
import uuid

# Import your ML Logic
from main import PrismEngine

app = FastAPI()

# --- 1. SETUP FACE DETECTION (OpenCV) ---
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def get_face_data(image):
    if image is None: return False, None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) == 0: return False, None
    x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
    return True, (int(x), int(y), int(w), int(h))

def decode_image(b64_string):
    try:
        if ',' in b64_string:
            b64_string = b64_string.split(',')[1]
        img_bytes = base64.b64decode(b64_string)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    except:
        return None

def process_engine_logic(frames_data, wallet):
    """
    Shared logic to run ML and generate DETAILED SCORES for Blockchain.
    """
    engine = PrismEngine()
    valid_frames = 0
    
    # Accumulators for detailed breakdown
    acc = {
        "pulse": 0.0,
        "skin": 0.0,
        "flash": 0.0,
        "eye": 0.0,
        "total": 0.0
    }
    
    print(f"   👤 Processing {len(frames_data)} frames for {wallet}...")

    for i, data in enumerate(frames_data):
        # Handle different data sources (JSON B64 vs Direct Image)
        if isinstance(data['image'], str):
            img = decode_image(data['image'])
        else:
            img = data['image'] # Already a numpy array

        if img is None: continue
        
        has_face, roi = get_face_data(img)
        
        if has_face:
            x, y, w, h = roi
            fh_h = int(h * 0.3)
            forehead = img[y:y+fh_h, x:x+w]
            
            # RUN THE ENGINE
            result = engine.process_frame(
                forehead_roi=forehead,
                face_img=img,
                screen_color=data.get('screenColor', 'WHITE')
            )
            
            # Extract Detailed Metrics if we got a result
            if result.confidence > 0:
                valid_frames += 1
                acc["total"] += result.confidence
                
                # 1. Pulse Score (Signal Quality is 0.0-1.0)
                acc["pulse"] += result.signal_quality
                
                # 2. Skin Score (SSS Ratio normalized approx)
                # SSS usually 0.8-1.2. We clamp to 0-1 for the contract.
                sss = result.details.get('sss_ratio', 0.0)
                acc["skin"] += min(max(sss / 1.2, 0.0), 1.0)
                
                # 3. Flash Score (Chroma Pass)
                # If passed = 1.0, else 0.0
                chroma = 1.0 if result.details.get('chroma_passed', False) else 0.0
                acc["flash"] += chroma
                
                # 4. Eye Score (Moire/Texture inverse)
                # Moire score high = bad. So Eye Score = 1.0 - Moire
                moire = result.details.get('moire_score', 0.0)
                acc["eye"] += max(0.0, 1.0 - (moire * 5)) # Scale moire up to penalize

    # Calculate Averages
    if valid_frames > 0:
        final_scores = {k: v / valid_frames for k, v in acc.items()}
    else:
        final_scores = {"pulse": 0, "skin": 0, "flash": 0, "eye": 0, "total": 0}

    # Generate Session ID
    session_id = f"sess_{uuid.uuid4()}"
    
    # Verdict Logic (Threshold > 40%)
    is_human = final_scores["total"] > 40.0

    print(f"📊 RESULT: Human={is_human} | Score={final_scores['total']:.2f}")

    # --- FINAL RETURN FORMAT (Matches Java Blockchain Requirement) ---
    return {
        "status": "verified" if is_human else "failed",
        "wallet": wallet,
        "sessionId": session_id,
        "confidenceScore": round(final_scores["total"] / 100.0, 2), # Normalize 0-1
        # Detailed Component Scores (0.0 - 1.0)
        "eyeScore": round(final_scores["eye"], 2),
        "skinScore": round(final_scores["skin"], 2),
        "pulseScore": round(final_scores["pulse"], 2),
        "flashScore": round(final_scores["flash"], 2)
    }

# --- 2. ENDPOINTS ---

class FileTrigger(BaseModel):
    json_path: str 

print("🚀 PRISM ANALYZER: READY ON PORT 8000")

# METHOD A: The "Clean" Way (JSON Path)
@app.post("/process-file")
async def process_file(trigger: FileTrigger):
    print(f"📥 [JSON METHOD] Signal received: {trigger.json_path}")
    
    target_filename = os.path.basename(trigger.json_path)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    security_core_dir = os.path.join(project_root, "security-core")
    
    # Simple Finder
    full_path = None
    for root, dirs, files in os.walk(project_root):
        if target_filename in files:
            full_path = os.path.join(root, target_filename)
            break
            
    if not full_path:
        print("❌ File not found on disk")
        raise HTTPException(status_code=404, detail="JSON file not found")

    print(f"   ✅ Found JSON: {full_path}")
    
    try:
        with open(full_path, 'r') as f:
            frames_data = json.load(f)
    except:
        raise HTTPException(status_code=500, detail="JSON Corrupted")
        
    wallet = "UNKNOWN"
    if len(frames_data) > 0:
        wallet = frames_data[0].get('wallet', 'UNKNOWN')

    return process_engine_logic(frames_data, wallet)


# METHOD B: The "Zombie Java" Way (Direct Video Upload)
@app.post("/process-video")
async def process_video_fallback(
    request: Request,
    video: UploadFile = File(None),
    file: UploadFile = File(None),
    wallet: str = Form("UNKNOWN"),
    screenColor: str = Form("RED")
):
    print(f"⚠️ [FALLBACK METHOD] Java is sending a raw video file!")
    
    actual_file = video or file
    if not actual_file:
        return {"status": "error", "message": "No file"}

    temp_filename = f"temp_{uuid.uuid4()}.mp4"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(actual_file.file, buffer)
    
    frames_data = []
    cap = cv2.VideoCapture(temp_filename)
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        frames_data.append({
            'image': frame, 
            'screenColor': screenColor
        })
    cap.release()
    
    if os.path.exists(temp_filename):
        os.remove(temp_filename)

    return process_engine_logic(frames_data, wallet)

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)