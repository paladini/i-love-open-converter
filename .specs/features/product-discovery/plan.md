# Product discovery assets and repository metadata

**Approved:** 2026-11-22 - user authorized continuing planned work and PRs; issue #38 is a focused presentation task, not application refactoring.
**Settled mid-build:** none.
**Review:** sent at 571b613.
**Fix pass:** done - no changes needed.

## Build record

- Captured three 1440x980 screenshots from the running application using synthetic demo inputs in an isolated temporary data directory; optimized JPEG sizes are 111,153, 89,288, and 64,366 bytes.
- Rendered `docs/social-preview.svg` to `docs/social-preview.png`; confirmed 1280x640 dimensions, 255,679 bytes, and all three embedded screenshots loaded.
- Checked both README embeds and localized alt text; verified all referenced image paths exist.
- Confirmed repository About description and topics before update; current description is generic and topics are empty. GitHub settings update remains after reviewable PR creation.
- `validate_plan.py product-discovery`: 0 errors, 0 warnings.

## Problem

The bilingual README pages describe the product but show no current application screens. GitHub About metadata is generic and has no topics or social preview. This makes it harder to discover the self-hosted PDF and image tools.

When this ships, visitors see genuine current product screens and a repository description, topics, and social preview aligned with shipped functionality.

## Shape

Capture the real self-hosted web app at desktop size using an isolated temporary data directory and synthetic demo inputs. Store optimized captures under `docs/screenshots/`, embed the same three screenshots in both READMEs with localized alt text, and make a 1280x640 social preview from the actual screenshots. Update GitHub About metadata in a separate settings action after the reviewable PR is ready.

Data: none - only static screenshots generated from synthetic PDFs/images and repository metadata change.
New: nothing - no application or data model entities are introduced.

**Changes underneath**

| Front | What changes |
| --- | --- |
| Documentation | Add home catalog, image compression result, and PDF page-number result captures; embed in English and PT-BR READMEs. |
| Social preview | Add a maintainable SVG source and a GitHub-compatible PNG rendered from the SVG. |
| GitHub settings | Set an accurate product description, relevant topics, and the social preview image. |
| Application | No runtime changes. |

## Surface

| Route | In | Out | Status | Who |
| --- | --- | --- | --- | --- |
| `README.md` | Markdown | Home, image, and PDF screenshots with English alt text | `200` | anyone |
| `README.pt-BR.md` | Markdown | Same screenshots with Portuguese alt text | `200` | anyone |
| `docs/screenshots/` | Real app screens with synthetic input | Optimized JPEG captures without personal data | `200` | anyone |
| GitHub About metadata | Description and lowercase topic list | Accurate repository description and searchable topics | `200` | anyone |
| GitHub Settings / Social preview | 1280x640 PNG under 1 MiB | Repository social preview that remains readable in light/dark embeds | `200` | anyone |

## Landing

| Decision | Chosen behavior | Alternative |
| --- | --- | --- |
| Screenshot inputs | Synthetic landscape PNG and synthetic one-page PDF; use the real application and real conversion jobs. | Screenshots of invented UI or private/user files. |
| Metadata | `Free, open-source, self-hosted PDF and image tools with local processing.` Topics: `self-hosted`, `file-converter`, `pdf`, `image-converter`, `docker`, `privacy`, `open-source`, `fastapi`. | Product claims for music, signatures, unsupported formats, or an empty topic list. |
| Social preview | Solid background, product name, current application screenshots, 1280x640 PNG below 1 MiB. | Transparency-dependent or illegible artwork. |

## Assumptions

| Assumption | Default | Rationale |
| --- | --- | --- |
| Screenshot locale | PT-BR default | The same authentic screens appear in both READMEs; alt text is localized separately. |
| Screenshot size | 1440x980 CSS pixels, JPEG quality 86 | Captures the desktop app clearly and keeps assets optimized. |
| Public URL conversion claim | Metadata stays broad and does not imply all files convert to all formats. | The published capability matrix remains the source of specific supported pairs. |

**Open questions:** none - the issue proposes the product description and topic list; GitHub topic limits are validated against current documentation.

## Criteria

### S1: Show genuine product examples (P1)

**Acceptance Criteria**

1. WHEN a visitor opens either README THEN they SHALL see the current home catalog and clear examples of the image and PDF families near the project overview.
2. WHEN screenshots are captured THEN they SHALL come from the running application and synthetic input data, with no private documents, personal names, secrets, or misleading coming-soon state.
3. WHEN an image appears in either README THEN its path SHALL exist in the default branch and its alt text SHALL be in that README's language.
4. WHEN a visitor views the README and social preview THEN both SHALL remain readable in light and dark contexts and SHALL match the current shipped app.
5. WHEN GitHub About metadata is updated THEN the description SHALL describe shipped PDF/image scope and topics SHALL use valid lowercase names without unsupported product names.
6. WHEN a visitor uploads the social preview THEN its format SHALL be PNG/JPG/GIF, its dimensions SHALL be 1280x640, and its size SHALL be below 1 MiB.
7. WHEN the README pages are compared THEN both SHALL use the same screenshots and links while keeping language-specific alt text and surrounding copy aligned.

## Out of scope

- Do not claim unsupported formats or features, change tool behavior, or publish synthetic output as a real user file.
- Do not include any private document, personal name, credential, or sensitive account data in screenshots.
- Do not implement issues that ask to refactor or modularize the application.

## Sources

- GitHub issue #38 - screenshot, README, metadata, and social preview requirements.
- [GitHub social preview requirements](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview) - 1280x640 recommended and PNG/JPG/GIF under 1 MiB.
- [GitHub topics guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics) - lowercase letters, numbers, hyphens, up to 50 characters, and no more than 20 topics.
- README and current app routes at `main` branch - verified current product wording and available operations.
