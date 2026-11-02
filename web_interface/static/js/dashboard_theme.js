/* Préférence purement visuelle : chargée avant le CSS pour éviter un flash du mauvais thème. */
(() => {
  "use strict";
  const preferenceKey = "soc-dashboard-theme";
  const root = document.documentElement;
  let storageUnavailable = false;
  let theme = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";

  try {
    const savedTheme = localStorage.getItem(preferenceKey);
    if (savedTheme === "light" || savedTheme === "dark") theme = savedTheme;
  } catch (error) {
    storageUnavailable = true;
    console.warn("Lecture de la préférence de thème impossible.", error);
  }
  root.dataset.dashboardTheme = theme;

  document.addEventListener("DOMContentLoaded", () => {
    const controls = document.querySelector(".theme-switch");
    const choices = controls.querySelectorAll("[data-theme-choice]");
    const notice = document.querySelector(".theme-storage-notice");

    function showStorageNotice() {
      notice.hidden = false;
      notice.textContent = "Le thème reste utilisable, mais ce navigateur ne permet pas de mémoriser votre choix.";
    }

    function updatePressedStates() {
      choices.forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.themeChoice === root.dataset.dashboardTheme));
      });
      document.querySelector('meta[name="theme-color"]').content =
        root.dataset.dashboardTheme === "light" ? "#f5f6f8" : "#101113";
    }

    choices.forEach((button) => {
      button.addEventListener("click", () => {
        root.dataset.dashboardTheme = button.dataset.themeChoice;
        updatePressedStates();
        try {
          localStorage.setItem(preferenceKey, root.dataset.dashboardTheme);
        } catch (error) {
          console.warn("Enregistrement de la préférence de thème impossible.", error);
          showStorageNotice();
        }
      });
    });
    controls.hidden = false;
    updatePressedStates();
    if (storageUnavailable) showStorageNotice();
  });
})();
