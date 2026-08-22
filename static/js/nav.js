/* Add a subtle border/background to the marketing header once scrolled. */
(function () {
  var header = document.getElementById("siteHeader");
  if (!header) return;
  var onScroll = function () {
    if (window.scrollY > 8) header.classList.add("scrolled");
    else header.classList.remove("scrolled");
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
})();
