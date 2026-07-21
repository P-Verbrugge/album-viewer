import {
  backBtn,
  breadcrumbsEl,
  brand,
  emptyState,
  emptySub,
  emptyTitle,
  grid,
  gridToolbar,
  scrollSentinel,
  startSlideshowBtn,
} from "./dom.js";
import { FAVORITES_PATH, PAGE_SIZE, state } from "./state.js";
import { openLightbox } from "./lightbox.js";
import { toggleFavorite } from "./favorites.js";

export function pathFromLocation() {
  const params = new URLSearchParams(window.location.search);
  return params.get("path") || "";
}

export async function loadPath(path, pushState = true) {
  const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}&offset=0&limit=${PAGE_SIZE}`);
  if (!res.ok) {
    grid.innerHTML = "";
    teardownInfiniteScroll();
    showEmpty("Niets gevonden", "Deze locatie bestaat niet (meer).");
    return;
  }
  const data = await res.json();

  if (pushState) {
    const url = data.path ? `?path=${encodeURIComponent(data.path)}` : window.location.pathname;
    history.pushState({ path: data.path }, "", url);
  }

  renderBreadcrumbs(data.breadcrumbs, data.path === FAVORITES_PATH);
  updateBackButton(data);
  render(data);
}

function updateBackButton(data) {
  if (data.path === FAVORITES_PATH) {
    backBtn.hidden = false;
    backBtn.onclick = () => loadPath("");
    return;
  }
  if (!data.breadcrumbs || data.breadcrumbs.length === 0) {
    // We're already at the top-level overview, nothing to go back to.
    backBtn.hidden = true;
    backBtn.onclick = null;
    return;
  }
  const parentPath =
    data.breadcrumbs.length >= 2 ? data.breadcrumbs[data.breadcrumbs.length - 2].path : "";
  backBtn.hidden = false;
  backBtn.onclick = () => loadPath(parentPath);
}

function renderBreadcrumbs(crumbs, isFavorites) {
  breadcrumbsEl.innerHTML = "";
  crumbs.forEach((c, i) => {
    const sep = document.createElement("span");
    sep.className = "crumb-sep";
    sep.textContent = "•";
    breadcrumbsEl.appendChild(sep);

    const el = document.createElement("span");
    el.className = "crumb" + (i === crumbs.length - 1 ? " current" : "");
    el.textContent = c.name;
    if (!isFavorites) {
      el.addEventListener("click", () => loadPath(c.path));
    }
    breadcrumbsEl.appendChild(el);
  });
}

function showEmpty(title, sub) {
  emptyTitle.textContent = title;
  emptySub.textContent = sub;
  emptyState.hidden = false;
}

function render(data) {
  grid.innerHTML = "";
  emptyState.hidden = true;
  state.currentPhotos = [];
  teardownInfiniteScroll();
  gridToolbar.hidden = true;
  startSlideshowBtn.hidden = true;

  state.currentBrowsePath = data.path;
  state.currentOffset = data.items.length;
  state.hasMore = !!data.has_more;

  if (data.type === "folders") {
    // Backend only returns type "folders" when there is at least one
    // subfolder, so downloading the whole tree always makes sense here.
    gridToolbar.hidden = false;
    data.items.forEach((item) => grid.appendChild(folderTile(item)));
  } else if (data.type === "photos") {
    state.currentPhotos = data.items.slice();
    if (data.items.length === 0 && data.path === FAVORITES_PATH) {
      showEmpty("Nog geen favorieten", "Klik op het hartje bij een foto om 'm hier te laten verschijnen.");
    } else {
      gridToolbar.hidden = data.items.length === 0;
      startSlideshowBtn.hidden = data.items.length === 0;
      data.items.forEach((item, i) => grid.appendChild(photoTile(item, i)));
    }
  } else {
    showEmpty("Niets te zien hier", "Deze map bevat geen submappen of foto's.");
  }

  if (state.hasMore) {
    setupInfiniteScroll();
  }
}

function folderTile(item) {
  const tile = document.createElement("div");
  tile.className = "tile folder";
  tile.tabIndex = 0;

  if (item.cover) {
    const img = document.createElement("img");
    img.src = `/api/thumbnail?path=${encodeURIComponent(item.cover)}`;
    img.loading = "lazy";
    img.alt = item.name;
    tile.appendChild(img);
  } else {
    const placeholder = document.createElement("div");
    placeholder.className = "cover-placeholder";
    placeholder.textContent = "◍";
    tile.appendChild(placeholder);
  }

  const label = document.createElement("div");
  label.className = "label";
  label.textContent = item.name;
  tile.appendChild(label);

  const open = () => loadPath(item.path);
  tile.addEventListener("click", open);
  tile.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") open();
  });

  return tile;
}

function photoTile(item, index) {
  const tile = document.createElement("div");
  tile.className = "tile photo";
  tile.tabIndex = 0;
  tile.dataset.path = item.path;

  const img = document.createElement("img");
  img.src = `/api/thumbnail?path=${encodeURIComponent(item.path)}`;
  img.loading = "lazy";
  img.alt = item.name;
  tile.appendChild(img);

  if (item.kind === "video") {
    const badge = document.createElement("span");
    badge.className = "video-badge";
    badge.textContent = "▶";
    tile.appendChild(badge);
  }

  const favBtn = document.createElement("button");
  favBtn.className = "tile-fav-btn" + (item.favorite ? " active" : "");
  favBtn.textContent = item.favorite ? "♥" : "♡";
  favBtn.setAttribute("aria-label", "Favoriet");
  favBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleFavorite(item.path, favBtn);
  });
  tile.appendChild(favBtn);

  const open = () => openLightbox(index);
  tile.addEventListener("click", open);
  tile.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") open();
  });

  return tile;
}

// ---------------- Pagination / infinite scroll ----------------

const scrollObserver = new IntersectionObserver(
  (entries) => {
    if (entries.some((e) => e.isIntersecting)) {
      loadMoreItems();
    }
  },
  { rootMargin: "600px" } // start loading well before the user actually hits the bottom
);

function setupInfiniteScroll() {
  scrollSentinel.hidden = false;
  scrollObserver.observe(scrollSentinel);
}

function teardownInfiniteScroll() {
  scrollSentinel.hidden = true;
  scrollObserver.unobserve(scrollSentinel);
}

async function loadMoreItems() {
  if (state.isLoadingMore || !state.hasMore) return;
  state.isLoadingMore = true;
  try {
    const res = await fetch(
      `/api/browse?path=${encodeURIComponent(state.currentBrowsePath)}&offset=${state.currentOffset}&limit=${PAGE_SIZE}`
    );
    if (!res.ok) return;
    const data = await res.json();

    if (data.type === "folders") {
      data.items.forEach((item) => grid.appendChild(folderTile(item)));
    } else if (data.type === "photos") {
      const startIndex = state.currentPhotos.length;
      state.currentPhotos = state.currentPhotos.concat(data.items);
      data.items.forEach((item, i) => grid.appendChild(photoTile(item, startIndex + i)));
    }

    state.currentOffset += data.items.length;
    state.hasMore = !!data.has_more;
    if (!state.hasMore) teardownInfiniteScroll();
  } finally {
    state.isLoadingMore = false;
  }
}

// ---------------- Wiring ----------------

brand.addEventListener("click", () => loadPath(""));

window.addEventListener("popstate", (e) => {
  const path = (e.state && e.state.path) || "";
  loadPath(path, false);
});
