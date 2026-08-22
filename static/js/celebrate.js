/* ==========================================================================
   Celebration: fires when the student cracks the password.
   Triggered live via the "lab:success" event (from monitor.js), or immediately
   on load if the challenge is already completed. Confetti is drawn on a canvas
   with no external libraries.
   ========================================================================== */
(function () {
  var overlay = document.getElementById("win-overlay");
  if (!overlay) return;

  var canvas = document.getElementById("confetti");
  var ctx = canvas ? canvas.getContext("2d") : null;
  var pwEl = document.getElementById("win-password");
  var atEl = document.getElementById("win-attempts");
  var closeBtn = document.getElementById("win-close");
  var root = document.getElementById("monitor-root");

  var COLORS = ["#2fe0b0", "#38bdf8", "#7c6cff", "#f5b73d", "#ff6472", "#ffffff"];
  var pieces = [];
  var running = false;
  var rafId = null;

  function resize() {
    if (!canvas) return;
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function spawn(n) {
    for (var i = 0; i < n; i++) {
      pieces.push({
        x: Math.random() * canvas.width,
        y: -20 - Math.random() * canvas.height * 0.5,
        r: 4 + Math.random() * 6,
        c: COLORS[(i + pieces.length) % COLORS.length],
        vy: 2 + Math.random() * 4,
        vx: -1.5 + Math.random() * 3,
        rot: Math.random() * Math.PI,
        vr: -0.2 + Math.random() * 0.4,
      });
    }
  }

  function tick() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (var i = 0; i < pieces.length; i++) {
      var p = pieces[i];
      p.x += p.vx; p.y += p.vy; p.rot += p.vr; p.vy += 0.03;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.c;
      ctx.fillRect(-p.r / 2, -p.r / 2, p.r, p.r * 0.5);
      ctx.restore();
    }
    // Drop pieces that fell off-screen.
    pieces = pieces.filter(function (p) { return p.y < canvas.height + 40; });
    if (running || pieces.length) {
      rafId = requestAnimationFrame(tick);
    }
  }

  function startConfetti() {
    if (!ctx) return;
    resize();
    running = true;
    spawn(160);
    // A couple of extra bursts for effect.
    setTimeout(function () { spawn(80); }, 400);
    setTimeout(function () { spawn(60); }, 900);
    setTimeout(function () { running = false; }, 2600);
    cancelAnimationFrame(rafId);
    tick();
  }

  var shown = false;
  function showWin(password, attempts) {
    if (shown) return;
    shown = true;
    if (pwEl && password) pwEl.textContent = password;
    if (atEl && attempts != null) atEl.textContent = attempts;
    overlay.hidden = false;
    // force reflow then add class for CSS transition
    void overlay.offsetWidth;
    overlay.classList.add("show");
    startConfetti();
  }

  function hideWin() {
    overlay.classList.remove("show");
    running = false;
    setTimeout(function () { overlay.hidden = true; }, 250);
  }

  window.addEventListener("resize", resize);
  if (closeBtn) closeBtn.addEventListener("click", hideWin);
  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) hideWin();
  });

  // Live trigger from the WebSocket stream.
  window.addEventListener("lab:success", function (e) {
    var d = e.detail || {};
    showWin(d.cracked_password, d.attempt_number);
  });

  // Already completed when the page loaded? Celebrate right away.
  if (root && root.getAttribute("data-completed") === "1") {
    showWin(root.getAttribute("data-cracked"), root.getAttribute("data-attempts"));
  }
})();
