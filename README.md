<div align="center">

<img src="logo.png" alt="PRISM Protocol" width="200"/>

# PRISM Protocol

**Proof of Liveness**

The World's First Physics-Based Human Verification System

---

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB.svg)](https://python.org)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.x-363636.svg)](https://soliditylang.org)
[![Sepolia](https://img.shields.io/badge/Testnet-Sepolia-6B4EE6.svg)](https://sepolia.etherscan.io)

[Read the Whitepaper](WHITEPAPER.md) | [Technical Documentation](PRISM_PROTOCOL.md) | [Runbook](RUNBOOK.md)

---

</div>

## Why PRISM Exists

**The age of digital trust is over.**

In 2024, AI-based deepfake detection accuracy fell below 50%---statistically no better than a coin flip. The "AI vs. AI" arms race is lost. Every detector trained today is already obsolete against tomorrow's generators.

PRISM does not play this game. We built something fundamentally different.

> **PRISM is the first system to verify human identity by measuring the laws of physics---not by analyzing pixels.**

A deepfake can replicate how a face *looks*. It cannot replicate how light scatters through living skin, how blood pulses through capillaries, or how a curved, wet cornea reflects the world. These are not visual features. They are physical phenomena. And physics cannot be faked.

---

<div align="center">

## The Breakthrough

</div>

PRISM combines **four novel detection engines**, each grounded in peer-reviewed research, into a single verification pipeline. No other system in the world uses this approach.

| Engine | Scientific Basis | What We Measure | Why AI Cannot Fake It |
|:--|:--|:--|:--|
| **Corneal Specular Reflection** | Purkinje Image Analysis | Light reflections from the curved cornea | Deepfakes render eyes as 2D textures; reflections are geometrically impossible |
| **Subsurface Scattering Spectroscopy** | Radiative Transfer in Biological Tissue | Differential light absorption in skin (red vs. blue channels) | AI renders skin as opaque; real skin is translucent with wavelength-dependent scattering |
| **Remote Photoplethysmography (rPPG)** | Hemoglobin Light Absorption | Blood Volume Pulse signal extracted from facial video | Deepfakes have no circulatory system; no coherent cardiac signal exists |
| **Active Chroma Challenge** | Challenge-Response Temporal Binding | Real-time correlation of screen color to facial reflection | Pre-recorded video cannot react; real-time deepfakes exhibit detectable latency |

This is not incremental improvement. This is a category-defining innovation.

---

<div align="center">

## How It Works: The Science

</div>

### Engine 1: Corneal Specular Reflection

When light hits the human eye, it produces distinct reflections called **Purkinje images**, formed by the anterior and posterior surfaces of the cornea and lens. The position and behavior of these reflections are governed by the physical geometry of a curved, wet optical surface.

**The Detection Principle:**

When a user moves their head, the pupil moves with the eyeball. But the primary Purkinje reflection (the "glint") moves *independently*---its position is determined by the external light source (the screen), not the eye's muscles. This decoupling is a direct consequence of optical physics.

**Why Deepfakes Fail:**

Generative models render eyes as flat textures. Any "reflection" is baked into the texture and moves *with* the pupil, or is generated with physically impossible geometry. PRISM's algorithm detects the brightest pixel in the eye region and verifies that its movement is consistent with a 3D curved surface.

> **Research Foundation:** University of Hull (2024). *"Detecting AI-Generated Images via Corneal Reflection Analysis."*

---

### Engine 2: Subsurface Scattering Spectroscopy

Human skin is not a painted surface. It is a complex, translucent, layered medium. When light enters the skin, it penetrates 1-3mm before being absorbed or scattered by:

*   **Melanin:** Absorbs blue and UV wavelengths in the epidermis.
*   **Hemoglobin:** Absorbs green light in the vascular dermis.
*   **Collagen:** Backscatters light uniformly in the deep dermis.

Critically, **red light penetrates deeper than blue light** due to lower absorption coefficients. This causes characteristic differences in shadow sharpness between color channels.

**The Detection Principle:**

PRISM's "Chroma Challenge" illuminates the face with controlled R, G, B sequences. We then analyze the **Laplacian variance** (sharpness) of shadow edges in each color channel. In real skin, the red channel exhibits *blurrier* shadow boundaries than the blue channel due to deeper subsurface transport.

**Why Deepfakes Fail:**

AI models render skin as a Lambertian (matte, opaque) surface. They produce uniform sharpness across all wavelengths because they do not simulate radiative transfer. This is a fundamental physics violation that PRISM detects.

> **Research Foundation:** Jensen et al. (2001). *"A Practical Model for Subsurface Light Transport."* SIGGRAPH.

---

### Engine 3: Remote Photoplethysmography (rPPG)

With every heartbeat, oxygenated blood surges through the capillaries in the face. Hemoglobin in the blood absorbs green light. This causes an **imperceptible, rhythmic color fluctuation** in the skin---a signal invisible to the naked eye but recoverable through computational analysis.

**The Detection Principle:**

PRISM extracts the **Blood Volume Pulse (BVP)** waveform from facial video using signal processing techniques. The implementation uses multiple established rPPG methods:

*   **POS (Plane Orthogonal to Skin):** Projects RGB signals onto a plane orthogonal to the skin tone vector
*   **CHROM (Chrominance-based):** Uses chrominance signals to separate pulse from motion artifacts
*   **GREEN Channel Method:** Direct extraction from the green channel with bandpass filtering

From the BVP, we derive:
*   **Heart Rate (HR):** Must fall within 40-180 BPM (mammalian range)
*   **Signal Quality Index (SQI):** Validates the coherence of the extracted signal
*   **Spectral Peak Analysis:** Uses Welch's method for robust frequency estimation

**Why Deepfakes Fail:**

A synthetic face has no cardiovascular system. It cannot produce a physiologically coherent BVP signal. Any noise in the video will lack the characteristic frequency signature and temporal coherence of a living organism.

> **Research Foundation:** 
> - De Haan & Jeanne (2013). *"Robust Pulse Rate from Chrominance-Based rPPG."* IEEE TBME.
> - Wang et al. (2017). *"Algorithmic Principles of Remote PPG."* IEEE TBME.

---

### Engine 4: Active Chroma Challenge

The three engines above analyze passive physical properties. The Chroma Challenge adds an **active, temporal binding** layer that defeats two critical attack vectors: pre-recorded video injection and real-time deepfake streaming.

**The Detection Principle:**

1.  The PRISM frontend generates a **random color sequence** (e.g., `[RED, BLUE, WHITE, GREEN]`) and a timestamp.
2.  The screen flashes the sequence, illuminating the user's face.
3.  The backend verifies that the correct color reflection appears on the user's skin at each timestamp, within a strict latency window (50-100ms).

**Why Attacks Fail:**

| Attack Type | Why It Fails |
|:--|:--|
| **Pre-recorded Video** | The video was recorded before the challenge existed. The face shows no color change, or the wrong colors. |
| **Real-time Deepfake (e.g., via API)** | Network latency + GPU rendering time introduces a delay signature (typically 150-500ms) that exceeds the biological response window. |
| **Screen Replay Attack** | Moire pattern detection identifies screen-of-screen artifacts. |

---

<div align="center">

## On-Chain Identity: Soulbound Proof of Humanity

</div>

Upon successful verification, PRISM mints a **Soulbound Token (SBT)** to the user's wallet address.

**Token Properties:**

| Property | Value |
|:--|:--|
| **Standard** | ERC-5192 (Minimal Soulbound NFT) |
| **Transferability** | Non-transferable (locked) |
| **Expiration** | Configurable (default: 7 days) |
| **On-Chain Data** | `proofHash`, `timestamp`, `confidenceScore`, `expiresAt` |
| **Biometric Data** | None stored on-chain |

**Integration:**

Any smart contract can call `PRISMRegistry.isHuman(address)` to gate access to verified humans. This enables:

*   **Sybil-resistant DAO voting**
*   **Fair airdrop distribution**
*   **Human-only DeFi pools**
*   **Verified creator badges**

> **Reference:** [EIP-5192: Minimal Soulbound NFTs](https://eips.ethereum.org/EIPS/eip-5192)

---

<div align="center">

## System Architecture

</div>

```
====================================================================================
                                PRISM PROTOCOL
====================================================================================

    +---------------------------+          +----------------------------------+
    |      CLIENT (Browser)     |   HTTP   |       BACKEND (Python/FastAPI)   |
    +---------------------------+  ------> +----------------------------------+
    |                           |          |                                  |
    |  [1] WebRTC Camera Feed   |          |  [3] PHYSICS ENGINE              |
    |  [2] Chroma Challenge UI  |          |      - Corneal Reflection        |
    |      (Color Sequence)     |          |      - Subsurface Scattering     |
    |  [*] MediaPipe Face Mesh  |          |      - Moire Detection           |
    |      (468 Landmarks)      |          |                                  |
    |                           |          |  [4] BIOLOGY ENGINE              |
    +---------------------------+          |      - rPPG (POS/CHROM/GREEN)    |
                                           |      - HR / SQI Extraction       |
                                           |                                  |
                                           |  [5] FUSION MODEL                |
                                           |      - Multi-Modal Aggregation   |
                                           |      - Liveness Score Output     |
                                           +----------------------------------+
                                                          |
                                                          v
                                           +----------------------------------+
                                           |      SECURITY CORE (Java)        |
                                           +----------------------------------+
                                           |                                  |
                                           |  [6] Score Validation            |
                                           |  [7] EIP-712 Signature Auth      |
                                           |  [8] Blockchain Transaction      |
                                           |                                  |
                                           +----------------------------------+
                                                          |
                                                          v
                                           +----------------------------------+
                                           |      BLOCKCHAIN (Sepolia)        |
                                           +----------------------------------+
                                           |                                  |
                                           |  [9] PRISMRegistry.sol           |
                                           |      -> mintAttestation()        |
                                           |                                  |
                                           |  [10] Soulbound Token Minted     |
                                           |       (ERC-5192)                 |
                                           |                                  |
                                           +----------------------------------+

====================================================================================
```

---

<div align="center">

## Competitive Landscape

</div>

PRISM is architecturally distinct from existing solutions.

| | PRISM Protocol | WorldCoin | Humanity Protocol | AI Detectors | Traditional KYC |
|:--|:--|:--|:--|:--|:--|
| **Core Method** | Physics + Biology | Iris Biometrics | Palm Vein Scan | Neural Network Classifiers | Document + Face Match |
| **Hardware** | Any Webcam | Custom $300K Orb | Proprietary Scanner | Any Camera | Smartphone |
| **Scalability** | Instant, Global | Hardware-Constrained | Hardware-Constrained | Instant | Manual Review Bottleneck |
| **Deepfake Resistance** | Physics-Grade | High (Hardware Bound) | Medium | Low (Arms Race) | Very Low |
| **Verification Time** | ~10 Seconds | Travel to Orb Location | Travel to Scanner | Seconds | Minutes to Days |

**PRISM is the only webcam-based solution that uses physics to verify liveness rather than AI pattern matching.**

---

<div align="center">

## Technology Stack

</div>

| Layer | Technologies |
|:--|:--|
| **Frontend** | HTML/CSS/JS, WebRTC |
| **Vision Backend** | Python 3.11, FastAPI, OpenCV, MediaPipe, NumPy, SciPy |
| **Security Core** | Java, Spring Boot, Web3j |
| **Blockchain** | Solidity 0.8.x, Foundry, Sepolia Testnet |
| **Identity Standard** | ERC-5192 (Soulbound Tokens) |

---

<div align="center">

## Roadmap

</div>

| Phase | Status | Deliverables |
|:--|:--|:--|
| **Phase 1: Core Engine** | Complete | Physics Detection Engines (Corneal, SSS, Chroma), Classical rPPG Pipeline, Soulbound Token Contract, MVP Backend |
| **Phase 2: Enhancement** | In Progress | Neural Network rPPG (VidFormer), Improved Accuracy, Mobile Optimization, Testnet Deployment |
| **Phase 3: Privacy Layer** | Planned | Zero-Knowledge Proof Integration (EZKL), Client-Side Verification, On-Chain ZK Verifier |
| **Phase 4: Ecosystem** | Planned | Enterprise API, DAO Governance Module, Mainnet Launch, W3C DID Integration |

---

<div align="center">

## Getting Started

</div>

```bash
# Clone the repository
git clone https://github.com/your-org/prism-protocol.git
cd prism-protocol

# Install dependencies
pip install -r requirements.txt

# Start the backend
python app/server.py

# The API will be available at http://localhost:8000
```

See [RUNBOOK.md](RUNBOOK.md) for complete deployment and integration instructions.

---

<div align="center">

## Research References

</div>

1.  **Corneal Reflection Analysis:** University of Hull (2024). *"Detecting AI-Generated Images via Corneal Reflection Analysis."*
2.  **Subsurface Scattering:** Jensen, H. W., et al. (2001). *"A Practical Model for Subsurface Light Transport."* SIGGRAPH.
3.  **rPPG - CHROM Method:** De Haan, G. & Jeanne, V. (2013). *"Robust Pulse Rate from Chrominance-Based rPPG."* IEEE TBME.
4.  **rPPG - POS Method:** Wang, W., et al. (2017). *"Algorithmic Principles of Remote PPG."* IEEE TBME.
5.  **VidFormer (Planned):** VidFormer (2025). *"End-to-End Remote Photoplethysmography via Hybrid 3D-CNN Transformer."* Target architecture for Phase 2.
6.  **Zero-Knowledge ML (Planned):** EZKL. [https://docs.ezkl.xyz](https://docs.ezkl.xyz). Target framework for Phase 3.
7.  **Soulbound Tokens:** EIP-5192. [https://eips.ethereum.org/EIPS/eip-5192](https://eips.ethereum.org/EIPS/eip-5192)

---

<div align="center">

---

**PRISM Protocol**

*Physics Cannot Be Faked.*

---

[Whitepaper](WHITEPAPER.md) | [Technical Spec](PRISM_PROTOCOL.md) | [Runbook](RUNBOOK.md)

</div>
