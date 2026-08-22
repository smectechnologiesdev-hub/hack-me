/* ==========================================================================
   Celebration: fires once, right after a successful sign-in (ACCESS GRANTED).
   Triggered by data-just-accessed="1" on #vault-root. Confetti is drawn on a
   canvas with no external libraries.
   ========================================================================== */
(function () {
  var overlay = document.getElementById("win-overlay");
  var root = document.getElementById("vault-root");
  if (!overlay || !root) return;
  if (root.getAttribute("data-just-accessed") !== "1") return;

  var canvas = document.getElementById("confetti");
  var ctx = canvas ? canvas.getContext("2d") : null;
  var closeBtn = document.getElementById("win-close");

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
    pieces = pieces.filter(function (p) { return p.y < canvas.height + 40; });
    if (running || pieces.length) rafId = requestAnimationFrame(tick);
  }

  function startConfetti() {
    if (!ctx) return;
    resize();
    running = true;
    spawn(160);
    setTimeout(function () { spawn(80); }, 400);
    setTimeout(function () { spawn(60); }, 900);
    setTimeout(function () { running = false; }, 2600);
    cancelAnimationFrame(rafId);
    tick();
  }

  function show() {
    overlay.hidden = false;
    void overlay.offsetWidth;
    overlay.classList.add("show");
    startConfetti();
  }

  function hide() {
    overlay.classList.remove("show");
    running = false;
    setTimeout(function () { overlay.hidden = true; }, 250);
  }

  window.addEventListener("resize", resize);
  if (closeBtn) closeBtn.addEventListener("click", hide);
  overlay.addEventListener("click", function (e) { if (e.target === overlay) hide(); });

  show();
})();
