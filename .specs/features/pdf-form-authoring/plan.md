# PDF Form Authoring

**Approved**: 2026-11-22 - user: “É pra seguir, e ir criando PRs de tudo, mergeando, até finalizar completamente a implementação do nosso plano original!”
**Settled mid-build:** Keep detection and document processing local; suggestions must be reviewed before they become fields.
**Review:** completed - independent review in `review.md` found three issues; all three were addressed.
**Fix pass:** complete - choices are sent only for choice widgets, tool labels switch with the selected language, and OCR suggestions run in one bounded child process with a 90-second timeout.

## Problem

The PDF Forms tool only lists and fills text fields and checkboxes that already exist. The original request also asks users to create interactive forms and detect fields automatically. People with flat PDFs must currently recreate form fields by hand in another application.

When this ships, a visitor can fill an existing form, create text and choice fields on a PDF, or review locally detected field suggestions before saving an interactive PDF.

## Shape

Reuse the existing `/tools/pdf-forms` page, `/api/pdf/fields` inspection endpoint, `pdf.forms` job, PyMuPDF widget support, and isolated worker. Validate requested field types, names, page bounds, and rectangles in the existing API layer before creating a job; construct widgets in the worker where PDF transformations already run.

1. The PDF Forms page uploads one unencrypted PDF and displays existing fields, page count, and a bounded page preview.
2. The page lets a visitor fill existing fields or place text, checkbox, radio, combo-box, and list-box fields over the preview; the visitor can move, resize, edit, or remove new fields.
3. The page can request local field suggestions from OCR text and page geometry; it presents suggestions for review and editing before save.
4. `POST /api/jobs` validates existing updates and new widget descriptions, creates a `pdf.forms` job, and the network-isolated worker writes interactive widgets and returns the completed PDF.

```mermaid
sequenceDiagram
    participant U as PDF Forms UI
    participant A as FastAPI
    participant P as Local PDF/OCR tools
    participant Q as SQLite job queue
    participant W as Isolated worker
    U->>A: 1. Upload PDF; inspect fields and request preview
    A->>P: 2. Render requested page or suggest fields locally
    P-->>U: 2. Return bounded preview and editable suggestions
    U->>A: 3. Submit reviewed fields and existing values
    A->>Q: 4. Validate and create pdf.forms job
    W->>Q: 5. Claim job and write widgets
    W-->>U: 6. Publish completed interactive PDF
```

**Changes underneath**

| Front | What changes |
| --- | --- |
| domain | `pdf.forms` accepts optional `create` widget descriptions alongside existing `updates`; existing fill behavior keeps its meaning |
| API | Existing form inspection returns page count and one bounded preview; a local suggestion action returns editable candidate fields |
| worker | `pdf.forms` creates validated PyMuPDF widgets before saving the output |
| stored data | Existing `options_json` contains field descriptions; no database migration |
| readers | The form page exposes fill, manual authoring, and reviewable detection modes |

New: no persisted entities. One-way constraint: the additive `create` shape in `pdf.forms` job options is consumed by the API and worker (door 1).
Data: none - uploads remain temporary job files and field descriptions stay in existing job options.

## Surface

| Route | In | Out | Status | Who |
| --- | --- | --- | --- | --- |
| `POST /api/pdf/fields` (existing) | one unencrypted PDF and page number | fields, page count, bounded PNG preview | 200; 422 invalid PDF/page | anyone |
| `POST /api/pdf/form-fields/suggest` (new) | one PDF up to 20 pages | reviewable text/choice suggestions with page rectangles | 200; 422 invalid PDF or limits | anyone |
| `POST /api/jobs` (existing) | PDF, `pdf.forms`, updates, and optional new widget descriptions | accepted job and status URL | 202; 422 unsupported or invalid options | anyone |
| `GET /tools/pdf-forms` (existing) | language preference and one PDF | fill, create, review, and download workflow | 200 | anyone |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| Existing `pdf.forms` job options consumed by both API and worker | Keep `updates` as the current array and add optional `create` entries `{type,name,page,rect,choices}`; old jobs without `create` retain existing fill behavior | A separate operation and queue contract would duplicate the current PDF form workflow and split one output task across different handlers |

- Nothing else in this change is hard to reverse

## Criteria

### S1: Create interactive form fields (P1)

A visitor can author an interactive form over an existing PDF and fill existing fields in the same tool.

**Acceptance Criteria**

1. WHEN a visitor uploads an unencrypted PDF THEN the system SHALL show its existing text and checkbox fields, page count, and a page preview with the current filled values preserved.
2. WHEN a visitor selects a field type and drags on the page preview THEN the system SHALL place a field rectangle mapped to the displayed PDF page, allow it to be moved, resized, edited, or removed, and support text, checkbox, radio, combo-box, and list-box fields.
3. WHEN a visitor saves a form THEN the system SHALL preserve unchanged existing fields, apply changed values, add each reviewed field once, and return one interactive PDF.
4. IF a created field has a duplicate/invalid name, invalid choice list, unsupported type, out-of-range page, or rectangle outside that page THEN the API SHALL reject the request with 422 `invalid_options` and SHALL NOT create a job.
5. WHEN a visitor switches between English and Brazilian Portuguese THEN the form controls, status, errors, and preview instructions SHALL display in the selected language.

### S2: Suggest fields locally (P1)

A visitor can have likely fields detected on a flat or scanned PDF and review every suggestion before saving.

**Acceptance Criteria**

1. WHEN a visitor requests field detection THEN the system SHALL use only local OCR and document geometry, with a limit of 20 pages and a bounded preview render; no file or text SHALL be sent to a hosted model or third-party service.
2. WHEN local detection finds labeled fields, blank lines, or square checkboxes THEN the system SHALL return text-field and checkbox suggestions with page and rectangle data for the visitor to inspect and edit. Choice groups remain available through manual authoring.
3. IF detection finds no candidates or cannot read the PDF THEN the system SHALL show a localized no-result or safe error state and SHALL NOT change the uploaded PDF.
4. WHEN a visitor accepts suggestions THEN only the suggestions still present in the editor SHALL be added to the saved PDF.

## Out of scope

| Excluded | Why |
| --- | --- |
| Hosted AI, cloud OCR, file uploads to third parties | Violates the approved local-processing and no-telemetry project constraints |
| PDF digital signature or certificate issuance | A form signature widget is not a cryptographic signing workflow |
| General form templates or a multi-document workflow builder | Separate product capabilities not needed to create or fill a PDF form |
| Automatic acceptance without visitor review | Incorrect suggestions could create unusable fields in the resulting document |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Field placement | Drag on a rendered page preview | Gives visible coordinates without requiring knowledge of PDF points |
| Detection | Local OCR plus geometric heuristics; every candidate remains editable | Keeps documents local and makes uncertain recognition reviewable |
| Choice fields | Support radio groups, combo boxes, and list boxes with explicit choices | Maps the original “múltipla escolha e listas” requirement to standard PDF widgets |
| Existing form behavior | Retain current text and checkbox fill support | This feature extends the existing tool without removing its current use |

**Open questions:** none - the user delegated completion of the original plan in stages.

## Differences from the source

None - the original request requires form creation, detection, and filling; this feature provides those actions locally and makes uncertain detections reviewable.

## Sources

- `.specs/features/initial-project/request.md` - binding - PDF form detection, creation, supported field types, and manual filling.
- [PyMuPDF Widget documentation](https://pymupdf.readthedocs.io/en/latest/widget.html) - primary API for supported widgets and their field behavior.
- [PyMuPDF grounding](https://pymupdf.readthedocs.io/en/latest/grounding.html) - primary coordinate mapping for page previews and widget rectangles.
- Existing `.specs/features/project-foundation/plan.md` - approved local processing and staged capability direction.
