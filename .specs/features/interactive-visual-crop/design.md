# Design: Interactive Visual Crop with Handles (`#65`)

## Architecture Overview

We use **Cropper.js v1.6.x** (`cropperjs`, MIT license), vendored locally under:
- `src/i_love_open_converter/static/vendor/cropper.min.js`
- `src/i_love_open_converter/static/vendor/cropper.min.css`

### 1. Image Crop (`index.html` + `app.js` + `app.css`)

- **DOM (`index.html`):**
  - In `.workspace-stage` (right after `#blur-region-editor`), add `<section class="image-crop-editor" id="image-crop-editor" hidden ...>` containing `<img id="image-crop-preview" alt="">`.
  - In `.operation-options` (right before/with `crop-left`), add an aspect-ratio preset group (`data-option="crop-aspect"`): buttons with `data-crop-aspect="free|1|1.7777777777777777|1.3333333333333333"` (`Free`, `1:1`, `16:9`, `4:3`).
  - Include `<link rel="stylesheet" href="/static/vendor/cropper.min.css">` and `<script defer src="/static/vendor/cropper.min.js"></script>` in `index.html`.
- **State & Lifecycle (`app.js`):**
  - `imageCropper` instance + `imageCropUrl` + `isSyncingCropInputs` guard flag to prevent infinite feedback loops between Cropper `crop` events and input `input` events.
  - `destroyImageCropper()` destroys `imageCropper` if present, revokes `imageCropUrl`, hides `#image-crop-editor`.
  - `loadImageCropPreview()` runs when `currentOperation === "image.crop"` and `currentFiles.length > 0` and `canRenderImagePreview(currentFiles[0])`. Loads `URL.createObjectURL(currentFiles[0])` into `#image-crop-preview`, initializes `new Cropper(img, { viewMode: 1, autoCropArea: 0.8, responsive: true, background: false, guides: true, movable: true, zoomable: false, scalable: false, rotatable: false, crop(event) { ... } })`.
  - On Cropper `crop` event (when not `isSyncingCropInputs`): round `detail.x`, `detail.y`, `detail.width`, `detail.height` to integers (clamped `>= 0` for x/y and `>= 1` for width/height) and write to `#crop-left`, `#crop-top`, `#crop-width`, `#crop-height`.
  - On input `input` event on `#crop-left`, `#crop-top`, `#crop-width`, `#crop-height`: set `isSyncingCropInputs = true`, call `imageCropper.setData({ x, y, width, height })`, reset flag.
  - On aspect ratio button click: set active class / `aria-pressed`, call `imageCropper.setAspectRatio(ratio)` (`NaN` for Free).

### 2. PDF Crop (`pdf-crop.html` + `pdf-crop.js` + `app.css`)

- **DOM (`pdf-crop.html`):**
  - Include `<link rel="stylesheet" href="/static/vendor/cropper.min.css">` and `<script defer src="/static/vendor/cropper.min.js"></script>`.
  - Keep `.crop-preview > img#preview`; remove or hide the old static `#crop-selection` div when Cropper is active.
  - Add aspect ratio preset buttons (`Free`, `1:1`, `16:9`, `4:3`) above/beside `.crop-inputs` with `data-pt` / `data-en` attributes.
- **State & Lifecycle (`pdf-crop.js`):**
  - `pdfCropper` instance + `isSyncing` guard flag + `activeAspectRatio = NaN`.
  - When `showPreview()` finishes decoding the page PNG and sets `preview.src`, destroy any previous `pdfCropper` and instantiate `new Cropper(preview, { viewMode: 1, autoCropArea: 1, responsive: true, background: false, guides: true, movable: true, zoomable: false, scalable: false, rotatable: false, ready() { applyInputsToCropper(); }, crop(event) { ... } })`.
  - Note: `ready()` applies the current `#left`, `#top`, `#right`, `#bottom` percentage values (default `0, 0, 100, 100`, or user-adjusted values when switching pages!) onto the Cropper using `imageData.naturalWidth` and `imageData.naturalHeight`.
  - On Cropper `crop` event: convert `detail.x`, `detail.y`, `detail.width`, `detail.height` into percentages of `naturalWidth` / `naturalHeight` (clamped `0..100`, rounded to 1 decimal or integer, ensuring `right > left` and `bottom > top`) and update `#left`, `#top`, `#right`, `#bottom`.
  - On input `input` event on `#left`, `#top`, `#right`, `#bottom`: if valid (`left < right`, `top < bottom`), convert percentages to natural pixels and call `pdfCropper.setData(...)`.
  - On aspect ratio button click: update active state and call `pdfCropper.setAspectRatio(ratio)`.

### 3. Styling (`app.css`)

- Style `.image-crop-editor`, `.crop-aspect-presets`, `.crop-aspect-btn`, and ensure `.crop-preview` works cleanly with Cropper.js's `.cropper-container` on both desktop and 360px mobile viewports (`touch-action: none` is handled by Cropper.js; ensure container doesn't overflow horizontally).
