// Tema (sistema / claro / oscuro) e idioma preferido. El estado inicial lo fija el script en <head>
// para evitar el parpadeo; este archivo solo conecta los controles. Sin JS la web sigue al sistema.
(function () {
  var root = document.documentElement;
  var mq = window.matchMedia("(prefers-color-scheme: dark)");

  function read(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function write(key, val) { try { localStorage.setItem(key, val); } catch (e) { /* modo privado: se ignora */ } }

  function apply(pref) {
    var dark = pref === "dark" || (pref === "system" && mq.matches);
    root.dataset.theme = dark ? "dark" : "light";
    root.dataset.themePref = pref;
    document.querySelectorAll("[data-theme-set]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.themeSet === pref));
    });
  }

  var switcher = document.querySelector("[data-theme-switch]");
  if (switcher) {
    switcher.hidden = false;
    switcher.addEventListener("click", function (e) {
      var b = e.target.closest("[data-theme-set]");
      if (!b) return;
      write("gecal-theme", b.dataset.themeSet);
      apply(b.dataset.themeSet);
    });
  }
  apply(root.dataset.themePref || "system");
  (mq.addEventListener ? mq.addEventListener.bind(mq, "change") : mq.addListener.bind(mq))(function () {
    if (root.dataset.themePref === "system") apply("system");
  });

  document.addEventListener("click", function (e) {
    var a = e.target.closest("a[data-lang]");
    if (a) write("gecal-lang", a.dataset.lang);
  });
})();
