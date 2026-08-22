/* ==========================================================================
   Live lab monitor.
   1. Loads the current attempt history + lab state from the REST API.
   2. Opens a WebSocket to /ws/labs/<token>/ for real-time updates.
   Each socket only ever receives events for the lab it subscribed to; the
   server authorises the subscription against the logged-in user.
   ========================================================================== */
(function () {
  var root = document.getElementById("monitor-root");
  if (!root) return;
  var token = root.getAttribute("data-lab-token");

  var els = {
    status: document.getElementById("stat-status"),
    count: document.getElementById("stat-count"),
    max: document.getElementById("stat-max"),
    result: document.getElementById("stat-result"),
    latest: document.getElementById("latest-pw"),
    rows: document.getElementById("attempt-rows"),
    empty: document.getElementById("empty-row"),
    wsStatus: document.getElementById("ws-status"),
    wsText: document.getElementById("ws-status-text"),
  };

  function fmtTime(iso) {
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleTimeString();
  }

  function removeEmptyRow() {
    if (els.empty && els.empty.parentNode) {
      els.empty.parentNode.removeChild(els.empty);
      els.empty = null;
    }
  }

  function addAttemptRow(a, prepend) {
    removeEmptyRow();
    var tr = document.createElement("tr");
    tr.className = a.success ? "result-flash" : "result-flash-fail";
    var resultBadge = a.success
      ? '<span class="badge badge-success">SUCCESS</span>'
      : '<span class="badge badge-failed">FAILED</span>';
    tr.innerHTML =
      '<td class="mono">#' + a.attempt_number + "</td>" +
      "<td class=\"mono\">" + escapeHtml(a.username || a.username_attempted || "") + "</td>" +
      '<td class="mono">' + escapeHtml(a.password) + "</td>" +
      "<td>" + resultBadge + "</td>" +
      '<td class="faint mono">' + fmtTime(a.timestamp || a.created_at) + "</td>";
    if (prepend && els.rows.firstChild) {
      els.rows.insertBefore(tr, els.rows.firstChild);
    } else {
      els.rows.appendChild(tr);
    }
    els.latest.textContent = a.password || "—";
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function setStatus(status) {
    if (status) els.status.textContent = status;
    if (status === "COMPLETED") {
      els.result.innerHTML = '<span class="badge badge-completed">Unlocked</span>';
    }
  }

  function applyEvent(evt) {
    // Live counters
    if (els.count && evt.attempt_count != null) els.count.textContent = evt.attempt_count;
    if (els.max && evt.max_attempts != null) els.max.textContent = evt.max_attempts;
    setStatus(evt.lab_status);
    addAttemptRow(evt, true);
    if (evt.success) {
      if (els.result) els.result.innerHTML = '<span class="badge badge-completed">Unlocked</span>';
      // Let the celebration (if present on this page) react in real time.
      window.dispatchEvent(new CustomEvent("lab:success", { detail: evt }));
    }
  }

  // --- 1. Initial load via REST API ---------------------------------------
  fetch("/api/labs/" + token + "/attempts/", { credentials: "same-origin" })
    .then(function (r) { return r.ok ? r.json() : []; })
    .then(function (attempts) {
      // API returns oldest-first; render newest at top.
      (attempts || []).slice().reverse().forEach(function (a) {
        addAttemptRow(a, false);
      });
    })
    .catch(function () { /* non-fatal: live events will still arrive */ });

  // --- 2. Live WebSocket ---------------------------------------------------
  var scheme = window.location.protocol === "https:" ? "wss" : "ws";
  var wsUrl = scheme + "://" + window.location.host + "/ws/labs/" + token + "/";
  var socket;
  var retry = 0;

  function connect() {
    socket = new WebSocket(wsUrl);

    socket.onopen = function () {
      retry = 0;
      els.wsStatus.className = "ws-status online";
      els.wsText.textContent = "live";
    };
    socket.onmessage = function (e) {
      var data;
      try { data = JSON.parse(e.data); } catch (err) { return; }
      if (data.type === "attempt") applyEvent(data);
    };
    socket.onclose = function () {
      els.wsStatus.className = "ws-status offline";
      els.wsText.textContent = "reconnecting…";
      // Exponential-ish backoff, capped.
      retry = Math.min(retry + 1, 6);
      setTimeout(connect, 500 * retry);
    };
    socket.onerror = function () { socket.close(); };
  }

  connect();
})();
