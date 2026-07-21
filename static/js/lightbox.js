import {
  infoFilename,
  infoList as infoListEl,
  infoMapEl,
  infoPanel,
  lbClose,
  lbCounter,
  lbFavBtn,
  lbImage,
  lbInfoBtn,
  lbNext,
  lbPrev,
  lbVideo,
  lightbox,
} from "./dom.js";
import { state } from "./state.js";
import { addInfoRow, loadExifInto } from "./exifPanel.js";
import { toggleFavorite } from "./favorites.js";
import { restartSlideshowTimer, stopSlideshow } from "./slideshow.js";

export function openLightbox(index) {
  state.currentPhotoIndex = index;
  showCurrentPhoto();
  lightbox.hidden = false;
}

export function showCurrentPhoto() {
  const photo = state.currentPhotos[state.currentPhotoIndex];
  const isVideo = photo.kind === "video";

  // Always stop and detach any previously playing video first.
  lbVideo.pause();
  lbVideo.removeAttribute("src");
  lbVideo.load();

  if (isVideo) {
    lbImage.hidden = true;
    lbVideo.hidden = false;
    lbVideo.src = `/api/video?path=${encodeURIComponent(photo.path)}`;
    // During a slideshow the video just plays muted as a moving preview
    // for its slot; outside a slideshow you get full manual controls.
    lbVideo.muted = state.slideshowPlaying;
    lbVideo.controls = !state.slideshowPlaying;
    if (state.slideshowPlaying) {
      lbVideo.play().catch(() => {});
    }
  } else {
    lbVideo.hidden = true;
    lbImage.hidden = false;
    lbImage.src = `/api/image?path=${encodeURIComponent(photo.path)}`;
    lbImage.alt = photo.name;
  }

  lbCounter.textContent = `${state.currentPhotoIndex + 1} / ${state.currentPhotos.length}`;
  lbFavBtn.classList.toggle("active", !!photo.favorite);

  if (!infoPanel.hidden) {
    if (isVideo) {
      showVideoInfo(photo);
    } else {
      loadExifInto(photo.path);
    }
  }

  if (state.slideshowPlaying) {
    restartSlideshowTimer();
  }
}

function showVideoInfo(photo) {
  infoFilename.textContent = photo.name;
  infoListEl.innerHTML = "";
  addInfoRow("Type", "Video");
  infoMapEl.hidden = true;
}

export function closeLightbox() {
  lightbox.hidden = true;
  lbImage.src = "";
  lbVideo.pause();
  lbVideo.removeAttribute("src");
  lbVideo.load();
  infoPanel.hidden = true;
  stopSlideshow();
  lightbox.classList.remove("controls-hidden");
  if (document.fullscreenElement) {
    document.exitFullscreen().catch(() => {});
  }
  if (state.savedGridPhotos !== null) {
    state.currentPhotos = state.savedGridPhotos;
    state.savedGridPhotos = null;
  }
}

export function showNext() {
  state.currentPhotoIndex = (state.currentPhotoIndex + 1) % state.currentPhotos.length;
  showCurrentPhoto();
}

export function showPrev() {
  state.currentPhotoIndex =
    (state.currentPhotoIndex - 1 + state.currentPhotos.length) % state.currentPhotos.length;
  showCurrentPhoto();
}

lbClose.addEventListener("click", closeLightbox);
lbNext.addEventListener("click", showNext);
lbPrev.addEventListener("click", showPrev);
lightbox.addEventListener("click", (e) => {
  if (e.target === lightbox) closeLightbox();
});

lbFavBtn.addEventListener("click", () => {
  const photo = state.currentPhotos[state.currentPhotoIndex];
  if (photo) toggleFavorite(photo.path, null);
});

lbInfoBtn.addEventListener("click", () => {
  const photo = state.currentPhotos[state.currentPhotoIndex];
  if (!photo) return;
  if (infoPanel.hidden) {
    infoPanel.hidden = false;
    if (photo.kind === "video") {
      showVideoInfo(photo);
    } else {
      loadExifInto(photo.path);
    }
  } else {
    infoPanel.hidden = true;
  }
});
