// Shared mutable state. Since ES module bindings can't be reassigned by an
// importing module, every module that needs to mutate this state imports
// the `state` object and sets properties on it (state.foo = ...) rather
// than importing individual `let` variables.

export const FAVORITES_PATH = "__favorites__";
export const PAGE_SIZE = 300;

export const state = {
  currentPhotos: [],
  currentPhotoIndex: 0,

  currentBrowsePath: "",
  currentOffset: 0,
  hasMore: false,
  isLoadingMore: false,

  savedGridPhotos: null, // stashes the grid's photo list while a map popup uses the lightbox

  slideshowPlaying: false,
  slideshowTimer: null,
  controlsHideTimer: null,

  leafletMap: null,
  leafletMarker: null,

  mapInstance: null,
  markerClusterGroup: null,

  toastTimer: null,
};
