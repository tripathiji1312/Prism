'use strict';

const canvas = document.getElementById("fireflies");
const ctx = canvas.getContext("2d");

let w, h;
function resize() {
  w = canvas.width = window.innerWidth;
  h = canvas.height = window.innerHeight;
}
window.addEventListener("resize", resize);
resize();

/* ---------- Firefly Factory ---------- */
function createFirefly() {
  return {
    x: w * 0.3 + Math.random() * w * 0.4,   
    y: h * 0.25 + Math.random() * h * 0.45,
    r: Math.random() * 1.6 + 0.6,
    vx: (Math.random() - 0.5) * 0.12,
    vy: -Math.random() * 0.05,             
    phase: Math.random() * Math.PI * 2,
    life: Math.random() * 200 + 220,      
    age: 0
  };
}

/* ---------- Setup ---------- */
const FIREFLY_COUNT = 25;
const fireflies = Array.from(
  { length: FIREFLY_COUNT },
  createFirefly
);

/* ---------- Animation ---------- */
function animate() {
  ctx.clearRect(0, 0, w, h);

  for (let i = 0; i < fireflies.length; i++) {
    const f = fireflies[i];
    f.age++;
    f.phase += 0.001;

    // gentle wandering
    f.x += (f.vx + Math.sin(f.phase) * 0.05) * f.r;
    f.y += (f.vy + Math.cos(f.phase) * 0.04) * f.r;

    // fade in / out
    const fadeTime = 60;
    let alpha = 1;

    if (f.age < fadeTime) {
      alpha = f.age / fadeTime;
    } else if (f.age > f.life - fadeTime) {
      alpha = (f.life - f.age) / fadeTime;
    }

    // respawn
    if (f.age >= f.life) {
      fireflies[i] = createFirefly();
      continue;
    }

    const glow = (Math.sin(f.phase) + 1) / 2;

    const gradient = ctx.createRadialGradient(
      f.x, f.y, 0,
      f.x, f.y, f.r * 14
    );

    gradient.addColorStop(0,
      `rgba(120, 255, 230, ${0.6 * glow * alpha})`
    );
    gradient.addColorStop(0.4,
      `rgba(90, 200, 190, ${0.25 * glow * alpha})`
    );
    gradient.addColorStop(1, "rgba(90, 200, 190, 0)");

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(f.x, f.y, f.r * 14, 0, Math.PI * 2);
    ctx.fill();
  }

  requestAnimationFrame(animate);
}

animate();
