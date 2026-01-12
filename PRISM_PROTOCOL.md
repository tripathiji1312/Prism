# PRISM PROTOCOL

## MAIN FEATURES:

**1. The Eye Check (Corneal Reflection / Purkinje)**

**Goal:** Prove the eye is a curved lens, not a flat texture.

**The Logic:** When the eye rotates, the Pupil moves fast, but the Reflection (Glint) moves slow
(or stays still) because it depends on the light source (screen), not the eye muscles.

**Builder Task:**

Þ Use MediaPipe to find the Pupil Center.
Þ Use OpenCV (minMaxLoc) to find the Brightest Pixel (The Glint) in the eye box.
Þ _Pass Condition: As the user looks left/right, the distance between the Pupil and Glint
must change._
Þ _Fail Condition: If the Glint "sticks" to the Pupil and moves with it exactly, it’s a Deepfake._

**2. The Skin Check (Subsurface Scattering)**

**Goal:** Prove it is real flesh, not an LED screen or plastic mask.

**The Logic:** Real skin scatters light internally. Red light penetrates deep and blurs; Blue light
reflects off the surface and stays sharp.

**Builder Task:**

Þ Flash the screen White.
Þ Split the video frame into Red and Blue channels (cv2.split).
Þ Measure the "sharpness" (Laplacian variance) of the shadow edges (side of nose).
Þ _Pass Condition: The Red channel must be blurrier than the Blue channel._
Þ _Fail Condition: If Red and Blue have equal sharpness, it is a flat screen recording._

**3. The Heart Check (rPPG)**

**Goal:** Detect the pulse.

**The Logic:** Blood absorbs Green light. When the heart beats, the face gets slightly less green
for a fraction of a second.

**Builder Task:**

Þ Crop the Forehead ROI (Region of Interest).
Þ Calculate the Mean Green Value for that region.
Þ Store this value in an array for 100 frames (~3 seconds).
Þ Run a Fourier Transform (FFT) on the array.
Þ _Pass Condition: A clear frequency peak exists between 1.0Hz and 1.6Hz (60-100 BPM)._


**4. The Flash Check (Active Chroma)**

**Goal:** Defeat pre-recorded videos and laggy Deepfake APIs.

**The Logic:** The reflection on the skin must match the screen color instantly.

**Builder Task:**

Þ Frontend sends: {"color": "RED", "timestamp": 1000}.
Þ Backend looks at video frame at timestamp 1050 (allowing 50ms latency).
Þ _Pass Condition: The average Red intensity of the face pixels is significantly higher than
the previous frame._
Þ _Fail Condition: No color change (pre-recorded) OR color change happens too late
(Deepfake rendering lag)._

TECH-STACK:

- Frontend: React (Next.js)
- Vision Backend: Python (FastAPI + OpenCV)
- Core Backend: Java(Springboot + Web3j)
- Blockchain: Polygon Testnet (Solidity)

DETAILED WORK:

**1. The Frontend (Client)**

**Task:** Make the screen flash colors and stream the webcam.

**How it works:**

- The Flash: You know how a phone screen lights up your face in the dark? We do that.
- Code a loop that changes the <div> background color: Red (200ms) -> Blue (200ms) ->
    White (200ms).
- The Stream: Don't try to send a video file. That's too hard. Just take a screenshot of the
    <Webcam /> component every 30 milliseconds.
- Send that screenshot string (Base64) to the backend using socket.io.
- _Crucial: Send the current screen color along with the image._ socket.emit('frame', {
    image: imgData, screenColor: 'RED', timestamp: 12345 })

**Libraries to use:** react-webcam, socket.io-client.

**2. The Python Brain (Backend)**

**Task:** Analyze the images to see if the user is 3D and alive.

- **Part A:** The "Avatar" Check (Face Detection)

```
The Logic: We need to know where the head is.
The Tool: Use MediaPipe Face Mesh. It gives you 468 dots on the face.
The Code:
```

```
import mediapipe as mp
# This gives you the coordinates of the forehead, eyes, and nose.
face_mesh = mp.solutions.face_mesh.FaceMesh()
results = face_mesh.process(image)
```
- **Part B:** The "Vampire" Check (Reflections / Physics)

```
The Logic: If the screen turns RED, the user's face must turn slightly red. Deepfakes
generated in a server don't know your screen is red.
The Algorithm:
o Crop the Forehead pixels.
o Calculate the average Red, Green, and Blue values.
o Check: When frontend_screen_color == 'RED', does the forehead_red_value go up?
o If yes -> Real Physics. If no -> Fake Video.
```
- **Part C:** The "Terminator" Check (The Eye Glint)

```
The Logic: Real eyes are wet curves. Screens/Deepfakes are flat.
The Algorithm:
o Use MediaPipe to find the Left Eye.
o Use OpenCV (cv2.minMaxLoc) to find the brightest pixel in the eye. That's the
reflection of the screen (the "Glint").
o The Test: When the user moves their head slightly, the Glint should move differently
than the pupil.
o Hackathon Shortcut: Just check if the Glint turns RED when the screen is Red.
```
- **Part D:** The "Zombie" Check (Pulse/rPPG)

```
The Logic: Blood pumps through your face. It makes your skin slightly greener (cameras
see green best) every time your heart beats.
The Algorithm:
o Collect 100 frames (about 3 seconds).
o Take the average Green value of the cheeks for each frame.
o You now have a list of 100 numbers: [120, 121, 123, 120, 119...].
o Run a Fourier Transform (FFT) (use scipy.fft) on this list.
o Is there a strong wave pattern? That's the heartbeat.
```
**3. The Security Core (Java Backend)**

**Task:** This is the secure "Hands" of the system. Python sees the face; Java holds the wallet.

**How it works:**

- When Python determines is_human = True, it sends a secure HTTP POST request to the
    Java Service.
- Java's Job:


```
o Receive the request: { "wallet": "0xUser...", "secret": "API_KEY" }.
o Verify the Secret: Ensure the request came from our Python server, not a hacker.
o Execute Transaction: Java uses the Web3j library to load the Admin Private Key.
o Mint: Java calls the Smart Contract function mintBadge(UserAddress).
o Return: Java sends the Transaction Hash back to Python/Frontend.
```
**4. Blockchain (The Receipt)**

**Task:** Give them a badge that proves they passed.

**How it works:**

- Write a simple Smart Contract (Solidity).
- Function mintBadge(signature):
- It checks the signature. "Did the Python Server sign this?"
- If yes -> Give the user an NFT.
- _Crucial: Make the NFT "Soulbound". Just delete the transfer function so they can't sell it_
    _to a bot._


## FINAL ARCHITECTURE:


