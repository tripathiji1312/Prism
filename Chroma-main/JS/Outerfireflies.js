/* JS/scary-fireflies.js */

const canvasScary = document.getElementById("scary-fireflies");
const ctxScary = canvasScary.getContext("2d");

let wScary, hScary;

function resizeScary() {
  wScary = canvasScary.width = window.innerWidth;
  hScary = canvasScary.height = window.innerHeight;
}
window.addEventListener("resize", resizeScary);
resizeScary();

/* --- Configuration --- */
const SCARY_COUNT = 50; 

function createScaryFly() {
  // 1. ZONING: Left (0-25%) or Right (75-100%)
  const isLeft = Math.random() > 0.5;
  const zoneWidth = wScary * 0.25; 
  
  const x = isLeft 
    ? Math.random() * zoneWidth 
    : (wScary - zoneWidth) + Math.random() * zoneWidth;

  return {
    x: x,
    y: hScary * 0.3 + Math.random() * hScary * 0.7, 
    
    // --- SIZE CHANGE HERE ---
    // Previously: Math.random() * 0.8 + 0.2
    // Now: Bigger range (0.6 to 2.1)
    r: Math.random() * 1.5 + 0.6,
    
    // MOVEMENT: Jittery/Nervous
    vx: (Math.random() - 0.5) * 0.3, 
    vy: (Math.random() - 0.5) * 0.2, 
    
    phase: Math.random() * Math.PI * 2,
    life: Math.random() * 150 + 100, 
    age: 0
  };
}

const scaryFlies = Array.from({ length: SCARY_COUNT }, createScaryFly);

function animateScary() {
  ctxScary.clearRect(0, 0, wScary, hScary);

  for (let i = 0; i < scaryFlies.length; i++) {
    const f = scaryFlies[i];
    f.age++;
    f.phase += 0.02; 

    // Erratic movement
    f.x += (f.vx + Math.sin(f.phase) * 0.1) * f.r;
    f.y += (f.vy + Math.cos(f.phase) * 0.1) * f.r;

    // Fade logic
    const fadeTime = 90;
    let alpha = 1;
    if (f.age < fadeTime) alpha = f.age / fadeTime;
    else if (f.age > f.life - fadeTime) alpha = (f.life - f.age) / fadeTime;

    // Respawn
    if (f.age >= f.life) {
      scaryFlies[i] = createScaryFly();
      continue;
    }

    const glow = (Math.sin(f.phase) + 1) / 2;

    // DRAWING
    // Multiplier is still 4x, but since base 'r' is bigger, the glow is bigger too
    const gradient = ctxScary.createRadialGradient(
      f.x, f.y, 0,
      f.x, f.y, f.r * 6 
    );

    gradient.addColorStop(0,   `rgba(100, 160, 120, ${0.6 * glow * alpha})`);
    gradient.addColorStop(0.5, `rgba(40, 70, 50, ${0.3 * glow * alpha})`);
    gradient.addColorStop(1,   "rgba(0, 0, 0, 0)");

    ctxScary.fillStyle = gradient;
    ctxScary.beginPath();
    ctxScary.arc(f.x, f.y, f.r * 6, 0, Math.PI * 2);
    ctxScary.fill();
  }

  requestAnimationFrame(animateScary);
}

animateScary();