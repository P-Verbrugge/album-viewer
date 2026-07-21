// This is the module map for the whole frontend:
//
//   dom.js          - all DOM element references
//   state.js        - shared mutable state + constants
//   toast.js        - toast notifications
//   theme.js        - light/dark theme toggle
//   browse.js       - navigation, breadcrumbs, pagination, tile rendering
//   favorites.js    - favorite toggling
//   exifPanel.js    - EXIF info panel + per-photo mini map
//   lightbox.js     - the photo/video viewer
//   slideshow.js    - play/pause/interval/fullscreen/auto-hide-controls
//   downloads.js    - single-file and zip downloads
//   settings.js     - settings modal + bulk-cache job
//   mapOverview.js  - the map overview with clustered markers
//
// lightbox.js and slideshow.js intentionally import from each other (the
// lightbox needs to restart the slideshow timer on every photo change, and
// the slideshow needs to advance the lightbox) — that's fine with ES
// modules as long as nothing calls the other module's functions until
// after the whole graph has loaded, which is the case here (everything
// only runs from later event-handler callbacks). Likewise for browse.js
// and favorites.js.

import { infoPanel, lightbox, mapOverlay, settingsModal } from "./dom.js";
import { state } from "./state.js";
import { loadPath, pathFromLocation } from "./browse.js";
import { closeLightbox, showNext, showPrev } from "./lightbox.js";
import { startSlideshow, stopSlideshow } from "./slideshow.js";
import { closeSettings } from "./settings.js";
import { closeMapOverview } from "./mapOverview.js";

import "./theme.js";
import "./favorites.js";
import "./exifPanel.js";
import "./downloads.js";

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !settingsModal.hidden) {
    closeSettings();
    return;
  }
  if (e.key === "Escape" && !mapOverlay.hidden) {
    closeMapOverview();
    return;
  }
  if (lightbox.hidden) return;
  if (e.key === "Escape") {
    if (!infoPanel.hidden) {
      infoPanel.hidden = true;
    } else {
      closeLightbox();
    }
  }
  if (e.key === "ArrowRight") showNext();
  if (e.key === "ArrowLeft") showPrev();
  if (e.key === " " && !["SELECT", "INPUT", "BUTTON", "TEXTAREA"].includes(e.target.tagName)) {
    e.preventDefault(); // don't let the page scroll
    if (state.slideshowPlaying) stopSlideshow();
    else startSlideshow();
  }
});

loadPath(pathFromLocation(), false);
