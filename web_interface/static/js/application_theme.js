// Apparence locale uniquement : applique le choix avant le rendu et le conserve entre les pages.
(function () {
  "use strict";

  const STORAGE_KEY = "fAnalyzerInterfaceTheme";

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    const isDark = theme === "dark";
    const button = document.getElementById("application-theme-toggle");
    if (button) {
      button.hidden = false;
      button.setAttribute("aria-pressed", String(isDark));
      button.setAttribute("aria-label", isDark ? "Activer le mode clair" : "Activer le mode sombre");
      button.querySelector("[data-theme-label]").textContent = isDark ? "Mode clair" : "Mode sombre";
    }
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
      themeColor.content = isDark ? "#142019" : "#f4f7f2";
    }
  }

  function readSavedTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
    } catch (storageError) {
      console.warn("Le choix clair/sombre ne peut pas être lu dans ce navigateur.", storageError);
      return "light";
    }
  }

  applyTheme(readSavedTheme());
  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(document.documentElement.dataset.theme);
    const button = document.getElementById("application-theme-toggle");
    if (!button) {
      return;
    }
    button.addEventListener("click", () => {
      const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(theme);
      try {
        localStorage.setItem(STORAGE_KEY, theme);
        button.removeAttribute("title");
      } catch (storageError) {
        button.title = "Choix appliqué, mais non mémorisé : le stockage du navigateur est indisponible.";
        console.warn(button.title, storageError);
      }
    });
  });
  window.addEventListener("storage", event => {
    if (event.key === STORAGE_KEY || event.key === null) {
      applyTheme(readSavedTheme());
    }
  });
})();
