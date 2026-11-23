# Independent review: English UI default and concise README

## Verdict

Approved. No material findings.

## Reviewed

- All 23 templates declare `lang="en"`. The 22 dedicated language selectors are English-first; the home page selector is also English-first in its multiline markup.
- The shared home-page script and all dedicated page scripts now use English when storage is empty or invalid, and retain a saved `pt-BR` choice. Each page runs its localization function during initialization.
- All page titles are English. The bilingual `data-pt` and `data-en` strings remain available for language switching.
- Both README visual openings are untouched: the existing screenshot, link, and badge blocks remain in their original order. Both bodies are substantially shorter and keep the requested quick-start, privacy/limits, and development information.
- The simplified capability descriptions remain bounded to supported PDF, image, Office, HTML, and Markdown workflows. They describe local summarization, public URL capture limits, and visual PDF signatures accurately.

## Limits of this review

Static review only. No tests, build, or browser session was run as part of this review.

## CI fix pass

The subsequent GitHub CI run found that existing documentation checks depend on the detailed format matrix, exact Compose defaults, and a specific Compose shutdown phrase being present in both READMEs. Those checks were written before this review and were not visible to static content review. The values and supported-path rows are retained in collapsible sections, the shutdown phrase is restored, and the main reading flow stays concise. CI is being rerun against this fix.
