# Objective capability inventory

This inventory reconciles the capabilities named in the goal objective with the shipped application. It is a scope map, not an exhaustive list of every possible format.

## Current repository baseline

| Area | Present in the current source |
| --- | --- |
| Image | Static JPEG, PNG, GIF, WebP, BMP and TIFF conversion; SVG, PSD, HEIC/HEIF and camera RAW to raster; resize, compress, rotate, crop, watermark, photo editing and privacy tools; batch processing; image to PDF |
| PDF | Editing, merge, split, organize, security, OCR, summary, offline PT-BR/English translation, office conversion, HTML rendering and image workflows |
| App | Self-hosted Docker Compose web and worker, local SQLite queue and files, Portuguese (Brazil) and English UI, no external analytics |
| Document conversion | Local Office, PDF/A, PDF, HTML and image conversion pipelines; public URL rendering snapshots bounded static resources before the isolated offline worker; some features require local tools | 

## PDF capabilities named in the objective

| Capability | Current state |
| --- | --- |
| Merge PDFs | Implemented |
| Split by page/range | Implemented; selected ranges are returned as separate PDFs |
| Compress PDF | Implemented with local PyMuPDF optimization |
| Office documents to PDF (Word, PowerPoint, Excel) | Implemented with isolated local LibreOffice worker |
| PDF to Word, PowerPoint, Excel | Implemented with local conversion and extraction pipelines |
| Edit PDF (text, images, shapes, annotations) | Implemented |
| PDF to JPG / extract images | Implemented, including embedded image extraction |
| JPG/images to PDF | Implemented for supported raster images |
| Sign PDF | Implemented as a visual signature; it does not claim cryptographic validity |
| PDF watermark | Implemented |
| Rotate PDF | Implemented |
| HTML to PDF | Implemented for local HTML with embedded resources |
| Unlock / protect PDF | Implemented |
| Reorder, delete, insert PDF pages | Implemented |
| PDF/A conversion | Implemented as locally converted and independently validated PDF/A-2b when dependencies are available |
| Repair damaged PDF | Implemented as best-effort local repair |
| Add page numbers | Implemented |
| Scan capture to PDF | Implemented with mobile camera capture or image selection, page ordering, and rotation |
| OCR / searchable PDF | Implemented locally for Portuguese and English |
| Compare PDFs | Implemented as a visual page comparison |
| Redact PDF | Implemented with safeguards for tagged content |
| Fillable PDF forms | Implemented for existing fields |
| AI summary / translation | Local extractive PDF summary and offline PT-BR/English PDF text translation are implemented; scanned documents require OCR first |
| PDF to Markdown | Implemented |

## Image capabilities named in the objective

| Capability | Current state |
| --- | --- |
| Compress image | Implemented for supported static raster formats |
| Resize image | Implemented |
| Crop image | Implemented |
| Convert to JPG | Implemented for supported static raster inputs, including PNG, WebP, BMP and TIFF |
| Generic static raster conversion | JPEG, PNG, static GIF, WebP, BMP and TIFF inputs convert to JPEG, PNG, WebP or one-frame GIF outputs |
| Convert from JPG to PNG or GIF; create animated GIF | Implemented for PNG and animated GIF output from ordered JPEG files |
| Convert from SVG, PSD, HEIC/HEIF, and camera RAW | Implemented with local bounded converters; output formats and size limits are listed in the bilingual READMEs |
| Photo editor (text, effects, frames, stickers) | Implemented in stages: text, filters, and frames; stickers are also available as a separate editor stage |
| Image upscaling | Implemented locally without AI |
| Background removal | Implemented locally |
| Image watermark | Implemented |
| Meme generator | Implemented |
| Rotate image | Implemented |
| HTML page to image | Implemented for local HTML |
| Face/plate/object blur | Face and local OpenCV plate blur are implemented; arbitrary objects can be blurred with manually selected preview regions (up to 20) |

## Cross-cutting requirement

The objective asks for conversion from any file type to any other type. The named examples currently cover documents, PDFs and images; they do not define a safe or finite universal format matrix. The delivery plan must preserve that long-term direction while identifying concrete format support and staged capability boundaries for each milestone.
