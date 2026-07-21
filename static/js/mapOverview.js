import { mapBtn, mapClose, mapContainerEl, mapEmptyEl, mapOverlay } from "./dom.js";
import { state } from "./state.js";
import { openLightbox } from "./lightbox.js";

function buildMapPopup(item, index, allItems) {
  const container = document.createElement("div");
  container.className = "map-popup";

  const img = document.createElement("img");
  img.alt = item.name;
  // No src here on purpose — see the popupopen handler below, where the
  // marker loading is wired up. Setting .src fires the request immediately
  // regardless of visibility, so doing it here for every marker at once
  // would blast out one request per geotagged photo the moment the map
  // opens.
  container.appendChild(img);

  const name = document.createElement("p");
  name.className = "map-popup-name";
  name.textContent = item.name;
  container.appendChild(name);

  const viewBtn = document.createElement("button");
  viewBtn.type = "button";
  viewBtn.textContent = "Bekijk foto";
  container.appendChild(viewBtn);

  const open = () => {
    closeMapOverview();
    state.savedGridPhotos = state.currentPhotos;
    state.currentPhotos = allItems;
    openLightbox(index);
  };
  img.addEventListener("click", open);
  viewBtn.addEventListener("click", open);

  return { container, img };
}

async function openMapOverview() {
  mapOverlay.hidden = false;
  mapEmptyEl.hidden = true;

  if (!state.mapInstance) {
    state.mapInstance = L.map(mapContainerEl);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(state.mapInstance);
  }

  if (state.markerClusterGroup) {
    state.mapInstance.removeLayer(state.markerClusterGroup);
  }
  state.markerClusterGroup = L.markerClusterGroup();

  try {
    const res = await fetch("/api/map/photos");
    const data = await res.json();

    if (!data.items || data.items.length === 0) {
      mapEmptyEl.hidden = false;
    } else {
      data.items.forEach((item, index) => {
        const marker = L.marker([item.lat, item.lon]);
        const { container, img } = buildMapPopup(item, index, data.items);
        marker.bindPopup(container);
        marker.on("popupopen", () => {
          if (!img.src) {
            img.src = `/api/thumbnail?path=${encodeURIComponent(item.path)}&size=200`;
          }
        });
        state.markerClusterGroup.addLayer(marker);
      });
      state.mapInstance.addLayer(state.markerClusterGroup);
      state.mapInstance.fitBounds(state.markerClusterGroup.getBounds(), { padding: [40, 40], maxZoom: 15 });
    }
  } catch {
    mapEmptyEl.hidden = false;
  }

  // The map container was hidden until just now, so Leaflet needs to
  // recalculate its size now that it's actually visible.
  setTimeout(() => state.mapInstance.invalidateSize(), 50);
}

export function closeMapOverview() {
  mapOverlay.hidden = true;
}

mapBtn.addEventListener("click", openMapOverview);
mapClose.addEventListener("click", closeMapOverview);
mapOverlay.addEventListener("click", (e) => {
  if (e.target === mapOverlay) closeMapOverview();
});
