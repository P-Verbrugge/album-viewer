import { downloadZipBtn, lbDownloadBtn } from "./dom.js";
import { state } from "./state.js";
import { showToast } from "./toast.js";

async function triggerDownload(url, button) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = button === downloadZipBtn ? "Bezig met inpakken..." : button.textContent;
  try {
    const res = await fetch(url);
    if (!res.ok) {
      showToast("Downloaden mislukt.");
      return;
    }
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : "download";

    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(blobUrl);
  } catch {
    showToast("Downloaden mislukt.");
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

lbDownloadBtn.addEventListener("click", () => {
  const photo = state.currentPhotos[state.currentPhotoIndex];
  if (!photo) return;
  triggerDownload(`/api/download/photo?path=${encodeURIComponent(photo.path)}`, lbDownloadBtn);
});

downloadZipBtn.addEventListener("click", () => {
  triggerDownload(`/api/download/zip?path=${encodeURIComponent(state.currentBrowsePath)}`, downloadZipBtn);
});
