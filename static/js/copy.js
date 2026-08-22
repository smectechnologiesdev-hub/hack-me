/* Copy-to-clipboard for [data-copy-btn] buttons.
   The button's data-copy-btn value is the id of the element to copy.
   Only the button's trailing text node is swapped, so an inline SVG icon
   inside the button is preserved. */
(function () {
  function setLabel(btn, text) {
    var last = btn.childNodes[btn.childNodes.length - 1];
    if (last && last.nodeType === 3) last.textContent = " " + text;
    else btn.appendChild(document.createTextNode(" " + text));
  }
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy-btn]");
    if (!btn) return;
    var el = document.getElementById(btn.getAttribute("data-copy-btn"));
    if (!el) return;
    var text = el.textContent.trim();
    var done = function () {
      setLabel(btn, "Copied");
      setTimeout(function () { setLabel(btn, "Copy"); }, 1200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(fallback);
    } else { fallback(); }
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch (err) {}
      document.body.removeChild(ta); done();
    }
  });
})();
