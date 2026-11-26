(() => {
  window.__ilovepdfDropzoneReady = true;
  document.querySelectorAll(".pdf-upload").forEach((zone) => {
    const input = zone.querySelector('input[type="file"]') || document.getElementById(zone.getAttribute("for") || "");
    if (!input) return;
    for (const eventName of ["dragenter", "dragover"]) {
      zone.addEventListener(eventName, (event) => {
        event.preventDefault();
        zone.classList.add("dragover");
      });
    }
    for (const eventName of ["dragleave", "drop"]) {
      zone.addEventListener(eventName, (event) => {
        event.preventDefault();
        zone.classList.remove("dragover");
      });
    }
    zone.addEventListener("drop", (event) => {
      const incoming = Array.from(event.dataTransfer?.files || []);
      if (!incoming.length || input.disabled) return;
      const transfer = new DataTransfer();
      const files = input.multiple ? incoming : [incoming[0]];
      files.forEach((file) => transfer.items.add(file));
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });
})();
