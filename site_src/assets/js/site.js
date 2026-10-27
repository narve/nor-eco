/* Site chrome only: theme toggle, hamburger panel, "I denne siden" list, sticky-on-scroll-up top bar.
   No framework. Storage access is wrapped because it can be unavailable. */
(function () {
  "use strict";
  var root = document.documentElement;

  // Theme toggle: cycles dark/light, remembers the choice when possible.
  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var current = root.dataset.theme ||
        (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
      var next = current === "light" ? "dark" : "light";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }

  // Hamburger panel: close on link click and Escape.
  var menu = document.getElementById("menu");
  if (menu) {
    menu.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest(".menu-panel a")) menu.open = false;
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && menu.open) { menu.open = false; menu.querySelector("summary").focus(); }
    });
  }

  // "I denne siden": built from the page's h2 headings that have ids.
  var toc = document.querySelector(".toc");
  if (toc) {
    var heads = document.querySelectorAll("main h2[id], main section[id] > h2");
    var list = toc.querySelector("ul");
    heads.forEach(function (h) {
      var id = h.id || (h.parentElement && h.parentElement.id);
      if (!id) return;
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#" + id;
      a.textContent = h.textContent;
      li.appendChild(a);
      list.appendChild(li);
    });
    toc.hidden = !list.children.length;
  }

  // Top bar hides on scroll down and returns on scroll up, so charts get the height.
  var bar = document.getElementById("topbar");
  if (bar) {
    var last = window.scrollY;
    window.addEventListener("scroll", function () {
      var y = window.scrollY;
      var open = menu && menu.open;
      bar.classList.toggle("hidden", !open && y > last && y > 80);
      last = y;
    }, { passive: true });
  }
})();
