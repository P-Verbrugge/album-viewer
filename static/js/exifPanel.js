import { infoClose, infoFilename, infoList, infoMapEl, infoPanel } from "./dom.js";
import { state } from "./state.js";

const EXIF_LABELS = [
  ["camera", "Camera"],
  ["lens", "Lens"],
  ["date_taken", "Datum"],
  ["exposure", "Sluitertijd"],
  ["fnumber", "Diafragma"],
  ["iso", "ISO"],
  ["focal_length", "Brandpuntsafstand"],
];

export function addInfoRow(label, value) {
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  infoList.appendChild(dt);
  infoList.appendChild(dd);
}

export async function loadExifInto(path) {
  infoFilename.textContent = "Laden...";
  infoList.innerHTML = "";
  infoMapEl.hidden = true;

  const res = await fetch(`/api/exif?path=${encodeURIComponent(path)}`);
  if (!res.ok) {
    infoFilename.textContent = path.split("/").pop();
    return;
  }
  const data = await res.json();

  infoFilename.textContent = data.filename;

  if (data.width && data.height) {
    addInfoRow("Afmetingen", `${data.width} × ${data.height}px`);
  }
  EXIF_LABELS.forEach(([key, label]) => {
    if (data[key]) addInfoRow(label, data[key]);
  });
  if (!infoList.children.length) {
    addInfoRow("Metadata", "Geen EXIF-gegevens gevonden in dit bestand.");
  }

  if (data.gps && typeof data.gps.lat === "number") {
    infoMapEl.hidden = false;
    showOnMap(data.gps.lat, data.gps.lon);
  }
}

function showOnMap(lat, lon) {
  if (typeof L === "undefined") return;

  if (!state.leafletMap) {
    state.leafletMap = L.map(infoMapEl).setView([lat, lon], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(state.leafletMap);
    state.leafletMarker = L.marker([lat, lon]).addTo(state.leafletMap);
  } else {
    state.leafletMap.setView([lat, lon], 13);
    state.leafletMarker.setLatLng([lat, lon]);
  }
  // The map container was hidden until just now (display:none), so Leaflet
  // needs to recalculate its size now that it's visible.
  setTimeout(() => state.leafletMap.invalidateSize(), 50);
}

infoClose.addEventListener("click", () => {
  infoPanel.hidden = true;
});
