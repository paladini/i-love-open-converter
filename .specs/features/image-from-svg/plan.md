# Convert SVG to raster images

**Approved**: 2026-11-21 - user: “Pode seguir nas implementações dde acordo com o [$tlc-spec-lean](<C:\Users\Fernando Paladini\.codex\skills\tlc-spec-lean\SKILL.md>) até o final. Vá abrindo PRs conforme precisar e vá seguindo tudo da implementação”
**Settled mid-build:** none
**Review:** pending.
**Fix pass:** pending.

## Problem

The image catalog still marks SVG conversion as coming soon, leaving a common vector input unsupported. People need to rasterize a local SVG into a practical image format without uploading it to a hosted converter.

When this ships, visitors can select one SVG, choose PNG, JPEG, or WebP, and download one locally rendered image.

## Shape

1. The visitor chooses “Converter de SVG”, selects one `.svg` file, and chooses PNG, JPEG, or WebP in the existing image form (`static/js/app.js` exists).
2. `main.py` (exists) validates the operation, extension, actual SVG root, file size, output format, and bounded raster dimensions before it creates a job.
3. `worker.py` (exists) calls a dedicated local SVG conversion wrapper. The wrapper runs the existing HTML renderer in its isolated, resource-bounded child with a restrictive resource fetcher; scripts, animation, foreign content, and external resources are rejected. It writes one output image, preserving SVG transparency for PNG/WebP and flattening JPEG on white.
4. Existing job status and download routes (exist) report the result; failures remove partial output.

```mermaid
flowchart LR
    A[1 Existing image form] --> B[2 main.py - validate SVG and options]
    B --> C[3 Existing local job queue]
    C --> D[4 worker.py (exists)]
    D --> E[4 html_worker.py (exists)]
    E --> F[4 Existing image output artifact]
    F --> G[5 Existing status and download]
```

Data: none - reuse conversion jobs and artifacts; temporary renderer inputs are removed after processing.

### Changes underneath

| Existing element | Change | Readers and consequence |
| --- | --- | --- |
| Image operations in `main.py` and `worker.py` | Add `image.from_svg` as a single-file raster conversion operation | The existing upload, job status, and download routes handle the operation. |
| SVG validation and renderer | Validate a bounded static SVG and render in a local child process with network/filesystem restrictions | The renderer can read only the temporary job input and required application assets. |
| Image catalog and upload form | Enable the existing SVG card, single-file input, format selection, and bilingual labels | Visitors can use the tool in PT-BR or English. |
| Existing job and file store | No schema change | Normal expiry and output cleanup continue to apply. |

## Surface

| Route | Input | Output | Status | Who |
| --- | --- | --- | --- | --- |
| `POST /api/jobs` (existing; new `image.from_svg`) | One SVG file up to 10 MiB and one of PNG/JPEG/WebP | Existing queued job response | `202`; `400` invalid multipart, `415` unsupported format, `422` invalid SVG/options or output over 40 MP | anyone |
| `GET /api/jobs/{job_id}` (existing) | Job id | Existing job state | `200`, `404` unknown job | anyone |
| `GET /api/jobs/{job_id}/download` (existing) | Successful job id | One raster image | `200`, `404` unknown job, `409` failed or pending job | anyone |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| SVG rendering | Reuse the existing isolated WeasyPrint child; render only local sanitized SVG content and map its declared dimensions to bounded pixels | Adding another renderer duplicates system dependencies; rendering SVG in the web process would expose the service to untrusted XML/CSS parsing. |
| Input safety | One static SVG up to 10 MiB; reject scripts, animation elements, `foreignObject`, event attributes, and non-fragment external resource references; never access network or host files | Executing SVG scripts or fetching referenced resources could run content or disclose local/network data. |
| Raster outputs | PNG, JPEG, or WebP up to 40 MP; preserve alpha for PNG/WebP and flatten JPEG onto white | Keeping only vector output would not satisfy the catalog's SVG-to-image conversion path. |
| Sizing | Use positive `width`/`height` or `viewBox` dimensions; use a documented default of 300 × 150 CSS pixels when dimensions are absent; scale down only when needed to stay within 40 MP | Unbounded or inferred dimensions can consume excessive memory or fail unpredictably. |

## Criteria

### S1: Convert one SVG to a bounded raster image locally (P1)

**Acceptance Criteria**

1. WHEN a visitor selects “Converter de SVG” THEN the page SHALL show a single-file SVG input, PNG/JPEG/WebP output choice, the 40 MP limit, and local-processing notice in PT-BR and English.
2. WHEN a visitor submits one supported static SVG and valid output format THEN the API SHALL create one `image.from_svg` job and the worker SHALL produce one local raster image at the requested format and bounded dimensions.
3. WHEN the SVG has no explicit dimensions THEN the renderer SHALL use a 300 × 150 CSS-pixel default; WHEN it has valid `width`/`height` or `viewBox` dimensions THEN the output SHALL preserve the aspect ratio and SHALL not exceed 40 MP.
4. WHEN a PNG or WebP output is selected THEN transparency SHALL be preserved; WHEN JPEG is selected THEN transparent areas SHALL be flattened onto white.
5. IF the file is missing, multiple files are submitted, the extension/content is unsupported, output format is invalid, output dimensions exceed 40 MP after bounded scaling, or file exceeds 10 MiB THEN the API SHALL reject the request before creating a job.
6. IF the SVG contains script, animation, `foreignObject`, event handlers, or external resource references THEN the API/worker SHALL fail closed, expose no download, and remove partial output.
7. WHILE rendering THEN the worker SHALL make no network request and SHALL not access files outside the temporary sandbox and its required runtime assets.
8. WHEN the visitor selects the tool and downloads the result at a 360 CSS-pixel viewport THEN all controls, statuses, and errors SHALL be usable and localized without horizontal page overflow.

## Assumptions

| Decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| SVG output formats | PNG, JPEG, WebP | Matches the existing image form and local raster formats | y - the user delegated the complete staged project; no reply arrived to the optional format confirmation before work continued |
| Renderer | Existing isolated WeasyPrint worker | Avoids a new renderer and preserves the project's untrusted-document isolation boundary | y - repository architecture and user-authorized local processing |
| SVG dimension fallback | 300 × 150 CSS pixels | Common, predictable fallback when SVG has neither usable size nor viewBox | y - implementation default within delegated scope |
| Unsupported SVG behavior | Fail closed without output | Scripts, animation, external references, and HTML foreign content are outside static image conversion | y - user selected local conversion and the project has no-network invariants |

**Open questions:** none - the project owner delegated full roadmap sequencing and implementation; the recommended scope was used after the optional confirmation window elapsed.

## Differences from the source

No binding screenshot or source UI was supplied. Reuse the existing catalog card and image form.

## Out of scope

- SVG editing, SVG output from raster images, animated SVG, remote resource fetching, font downloads, external CSS, and converting SVG documents to PDF.
- PSD, HEIC, RAW, or batch SVG processing.
- Claiming conversion of malformed or unsupported SVG features.

## Sources

- `.specs/features/project-foundation/plan.md` - approved staged roadmap and local processing constraints.
- `src/i_love_open_converter/html_ops.py` and `html_worker.py` - existing renderer wrapper, temporary sandbox, local-resource rules, and output bounds.
- WeasyPrint 70.0 official documentation - SVG images are supported and use the configured URL fetcher; untrusted SVG requires the same security restrictions as HTML/CSS: https://doc.courtbouillon.org/weasyprint/stable/api_reference.html and https://doc.courtbouillon.org/weasyprint/stable/first_steps.html.
