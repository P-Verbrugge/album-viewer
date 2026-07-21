// All DOM element lookups live here, so every other module just imports
// the refs it needs instead of re-querying the document.

export const grid = document.getElementById("grid");
export const emptyState = document.getElementById("empty-state");
export const emptyTitle = document.getElementById("empty-title");
export const emptySub = document.getElementById("empty-sub");
export const breadcrumbsEl = document.getElementById("breadcrumbs");
export const brand = document.querySelector(".brand");
export const backBtn = document.getElementById("back-btn");
export const toast = document.getElementById("toast");

export const themeBtn = document.getElementById("theme-btn");
export const favoritesBtn = document.getElementById("favorites-btn");
export const settingsBtn = document.getElementById("settings-btn");
export const mapBtn = document.getElementById("map-btn");

export const gridToolbar = document.getElementById("grid-toolbar");
export const startSlideshowBtn = document.getElementById("start-slideshow-btn");
export const downloadZipBtn = document.getElementById("download-zip-btn");
export const scrollSentinel = document.getElementById("scroll-sentinel");

export const lightbox = document.getElementById("lightbox");
export const lbImage = document.getElementById("lb-image");
export const lbVideo = document.getElementById("lb-video");
export const lbCounter = document.getElementById("lb-counter");
export const lbClose = document.getElementById("lb-close");
export const lbPrev = document.getElementById("lb-prev");
export const lbNext = document.getElementById("lb-next");
export const lbFavBtn = document.getElementById("lb-fav-btn");
export const lbInfoBtn = document.getElementById("lb-info-btn");
export const lbPlayBtn = document.getElementById("lb-play-btn");
export const lbFullscreenBtn = document.getElementById("lb-fullscreen-btn");
export const lbDownloadBtn = document.getElementById("lb-download-btn");
export const lbIntervalSelect = document.getElementById("lb-interval-select");

export const infoPanel = document.getElementById("info-panel");
export const infoClose = document.getElementById("info-close");
export const infoFilename = document.getElementById("info-filename");
export const infoList = document.getElementById("info-list");
export const infoMapEl = document.getElementById("info-map");

export const settingsModal = document.getElementById("settings-modal");
export const settingsClose = document.getElementById("settings-close");
export const cacheInfoText = document.getElementById("cache-info-text");
export const cacheProgressWrap = document.getElementById("cache-progress-wrap");
export const cacheProgressFill = document.getElementById("cache-progress-fill");
export const cacheProgressLabel = document.getElementById("cache-progress-label");
export const cacheBuildBtn = document.getElementById("cache-build-btn");
export const cacheClearBtn = document.getElementById("cache-clear-btn");

export const mapOverlay = document.getElementById("map-overlay");
export const mapClose = document.getElementById("map-close");
export const mapContainerEl = document.getElementById("map-container");
export const mapEmptyEl = document.getElementById("map-empty");
