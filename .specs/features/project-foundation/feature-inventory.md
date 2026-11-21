# Objective capability inventory

This inventory preserves the capabilities named in the goal objective while the delivery plan is being shaped. It is a scope map, not an implementation commitment or an exhaustive list of every possible format.

## Current repository baseline

| Area | Present in the current source |
| --- | --- |
| Image | Static JPEG, PNG, WebP, BMP, TIFF: convert, resize, compress, rotate; batch processing; image to PDF |
| PDF | Merge, split by page ranges, compress, rotate, PDF pages to JPG |
| App | Self-hosted Docker Compose web and worker, local SQLite queue and files, Portuguese (Brazil) and English UI, no external analytics |
| Document conversion | No Office document conversion, OCR, PDF/A, PDF editing, or HTML rendering |

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
| AI summary / translation | Deferred; no remote AI service is part of the local-first scope |
| PDF to Markdown | Implemented |

## Image capabilities named in the objective

| Capability | Current state |
| --- | --- |
| Compress image | Implemented for supported static raster formats |
| Resize image | Implemented |
| Crop image | Implemented |
| Convert to JPG | Implemented for supported static raster inputs, including PNG, WebP, BMP and TIFF |
| Convert from JPG to PNG or GIF; create animated GIF | Implemented for PNG and animated GIF output |
| Photo editor (text, effects, frames, stickers) | Implemented in stages: text, filters, and frames; stickers are also available as a separate editor stage |
| Image upscaling | Implemented locally without AI |
| Background removal | Implemented locally |
| Image watermark | Implemented |
| Meme generator | Implemented |
| Rotate image | Implemented |
| HTML page to image | Implemented for local HTML |
| Face/plate/object blur | Face blur is implemented; plate and arbitrary-object blur are deferred |

## Cross-cutting requirement

The objective asks for conversion from any file type to any other type. The named examples currently cover documents, PDFs and images; they do not define a safe or finite universal format matrix. The delivery plan must preserve that long-term direction while identifying concrete format support and staged capability boundaries for each milestone.
