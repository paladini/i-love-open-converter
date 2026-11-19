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
| Merge PDFs | Present |
| Split by page/range | Present; current split returns selected ranges as separate PDFs |
| Compress PDF | Present; current implementation uses PyMuPDF garbage collection and deflate |
| Office documents to PDF (Word, PowerPoint, Excel) | Missing |
| PDF to Word, PowerPoint, Excel | Missing |
| Edit PDF (text, images, shapes, annotations) | Missing |
| PDF to JPG / extract images | PDF pages to JPG present; embedded image extraction missing |
| JPG/images to PDF | Present for supported static raster images |
| Sign PDF | Missing |
| PDF watermark | Missing |
| Rotate PDF | Present |
| HTML to PDF | Missing |
| Unlock / protect PDF | Missing |
| Reorder, delete, insert PDF pages | Missing |
| PDF/A conversion | Missing |
| Repair damaged PDF | Missing |
| Add page numbers | Missing |
| Scan capture to PDF | Missing |
| OCR / searchable PDF | Missing |
| Compare PDFs | Missing |
| Redact PDF | Missing |
| Fillable PDF forms | Missing |
| AI summary / translation | Missing |
| PDF to Markdown | Missing |

## Image capabilities named in the objective

| Capability | Current state |
| --- | --- |
| Compress image | Present for supported static raster formats |
| Resize image | Present |
| Crop image | Missing |
| Convert to JPG | Present for supported static raster inputs, including PNG, WebP, BMP and TIFF |
| Convert from JPG to PNG or GIF; create animated GIF | PNG output present; GIF output and animation missing |
| Photo editor (text, effects, frames, stickers) | Missing |
| Image upscaling | Missing |
| Background removal | Missing |
| Image watermark | Missing |
| Meme generator | Missing |
| Rotate image | Present |
| HTML page to image | Missing |
| Face/plate/object blur | Missing |

## Cross-cutting requirement

The objective asks for conversion from any file type to any other type. The named examples currently cover documents, PDFs and images; they do not define a safe or finite universal format matrix. The delivery plan must preserve that long-term direction while identifying concrete format support and staged capability boundaries for each milestone.
