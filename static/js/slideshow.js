import {
  lbFullscreenBtn,
  lbIntervalSelect,
  lbPlayBtn,
  lightbox,
  startSlideshowBtn,
} from "./dom.js";
import { state } from "./state.js";
import { openLightbox, showCurrentPhoto } from "./lightbox.js";

// Restore the viewer's last-chosen interval (a personal browser preference,
// not something that needs to be shared between visitors).
const savedInterval = localStorage.getItem("album-slideshow-interval");
if (savedInterval) lbIntervalSelect.value = savedInterval;

function currentIntervalMs() {
  return parseInt(lbIntervalSelect.value, 10) || 5000;
}

export function restartSlideshowTimer() {
  clearTimeout(state.slideshowTimer);
  state.slideshowTimer = setTimeout(() => {
    state.currentPhotoIndex = (state.currentPhotoIndex + 1) % state.currentPhotos.length;
    showCurrentPhoto();
  }, currentIntervalMs());
}

export function startSlideshow() {
  if (state.currentPhotos.length === 0) return;
  state.slideshowPlaying = true;
  lbPlayBtn.textContent = "⏸";
  lbPlayBtn.setAttribute("aria-label", "Pauzeren");
  restartSlideshowTimer();
  scheduleHideControls();
}

export function stopSlideshow() {
  state.slideshowPlaying = false;
  lbPlayBtn.textContent = "▶";
  lbPlayBtn.setAttribute("aria-label", "Diavoorstelling starten");
  clearTimeout(state.slideshowTimer);
  showControls();
}

function showControls() {
  lightbox.classList.remove("controls-hidden");
  clearTimeout(state.controlsHideTimer);
  if (state.slideshowPlaying) scheduleHideControls();
}

function scheduleHideControls() {
  clearTimeout(state.controlsHideTimer);
  state.controlsHideTimer = setTimeout(() => {
    lightbox.classList.add("controls-hidden");
  }, 3000);
}

lbIntervalSelect.addEventListener("change", () => {
  localStorage.setItem("album-slideshow-interval", lbIntervalSelect.value);
  if (state.slideshowPlaying) restartSlideshowTimer();
});
// Prevent a click on the dropdown from bubbling up to the backdrop-click handler.
lbIntervalSelect.addEventListener("click", (e) => e.stopPropagation());

lbPlayBtn.addEventListener("click", () => {
  if (state.slideshowPlaying) stopSlideshow();
  else startSlideshow();
});

lbFullscreenBtn.addEventListener("click", () => {
  if (!document.fullscreenElement) {
    lightbox.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
});

// Reveal controls again on movement/touch — like a video player.
lightbox.addEventListener("mousemove", () => {
  if (!lightbox.hidden) showControls();
});
lightbox.addEventListener("touchstart", () => {
  if (!lightbox.hidden) showControls();
});

startSlideshowBtn.addEventListener("click", () => {
  if (state.currentPhotos.length === 0) return;
  openLightbox(0);
  startSlideshow();
});
