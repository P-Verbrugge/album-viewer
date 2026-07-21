import { themeBtn } from "./dom.js";

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("album-theme", theme);
  themeBtn.textContent = theme === "light" ? "☀" : "◐";
}

themeBtn.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme") || "dark";
  applyTheme(current === "light" ? "dark" : "light");
});

applyTheme(document.documentElement.getAttribute("data-theme") || "dark");
