import { toast } from "./dom.js";
import { state } from "./state.js";

export function showToast(message, isFavorite) {
  clearTimeout(state.toastTimer);
  toast.innerHTML = "";
  if (isFavorite === true) {
    const heart = document.createElement("span");
    heart.className = "toast-heart";
    heart.textContent = "♥";
    toast.appendChild(heart);
  }
  toast.appendChild(document.createTextNode(message));
  toast.hidden = false;
  toast.classList.remove("hide");
  state.toastTimer = setTimeout(() => {
    toast.classList.add("hide");
    setTimeout(() => {
      toast.hidden = true;
    }, 250);
  }, 1800);
}
