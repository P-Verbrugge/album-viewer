import { favoritesBtn, lbFavBtn } from "./dom.js";
import { FAVORITES_PATH, state } from "./state.js";
import { showToast } from "./toast.js";
import { loadPath, pathFromLocation } from "./browse.js";

export async function toggleFavorite(path, buttonEl) {
  const res = await fetch("/api/favorites/toggle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) {
    showToast("Kon favoriet niet opslaan — probeer opnieuw.");
    return;
  }
  const data = await res.json();

  // Update every button that refers to this photo (grid + optionally the lightbox)
  document.querySelectorAll(`[data-path="${CSS.escape(path)}"] .tile-fav-btn`).forEach((btn) => {
    setFavButtonState(btn, data.favorite);
  });
  if (buttonEl) setFavButtonState(buttonEl, data.favorite);
  setFavButtonState(
    lbFavBtn,
    state.currentPhotos[state.currentPhotoIndex] && state.currentPhotos[state.currentPhotoIndex].path === path
      ? data.favorite
      : lbFavBtn.classList.contains("active")
  );

  const item = state.currentPhotos.find((p) => p.path === path);
  if (item) item.favorite = data.favorite;

  showToast(data.favorite ? "Toegevoegd aan favorieten" : "Verwijderd uit favorieten", data.favorite);

  // If we're in the favorites overview and a photo gets "unfavorited",
  // make it disappear immediately.
  if (!data.favorite && pathFromLocation() === FAVORITES_PATH) {
    loadPath(FAVORITES_PATH, false);
  }
}

export function setFavButtonState(btn, isFavorite) {
  if (!btn) return;
  btn.classList.toggle("active", isFavorite);
  // Only the heart on the tiles swaps between the ♡/♥ glyphs; the button in
  // the viewer (lb-fav) always keeps the same glyph and only changes color.
  if (btn.classList.contains("tile-fav-btn")) {
    btn.textContent = isFavorite ? "♥" : "♡";
  }
  btn.classList.remove("pulse");
  // Force a reflow so the animation still plays on rapid repeated clicks.
  void btn.offsetWidth;
  btn.classList.add("pulse");
}

favoritesBtn.addEventListener("click", () => loadPath(FAVORITES_PATH));
