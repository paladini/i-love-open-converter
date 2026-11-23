# English UI default and concise documentation

**Approved**: 2026-11-23 - user asked for English as the default interface language, shorter direct READMEs, and preservation of the existing opening visual.
**Review:** pending.
**Fix pass:** pending.

## Problem

The screenshots in the English README show English, but the running application defaults to Brazilian Portuguese on first visits across the home page and dedicated tools. Both READMEs also contain long format matrices and repeated operating/configuration details that obscure the quick start.

New visitors should see the English interface and concise setup guidance by default, while users who chose Brazilian Portuguese should keep that preference.

## Shape

- Default the language selector and document language to English throughout the home page and all dedicated tool pages.
- Keep an explicit `pt-BR` choice in local storage and apply it across pages.
- Set page titles and language selectors to English-first defaults.
- Preserve both READMEs' existing opening layout, links, badges, and screenshots. Replace the long body with concise feature, startup, limits/privacy, and development sections in each language.
- No API, data model, job behavior, or conversion support changes.

**Changes underneath**

| Front | What changes |
| --- | --- |
| browser language | The shared home-page script and dedicated page scripts default to English and honor saved `pt-BR`. |
| templates | Set the initial document language, title, and language selector order to English. |
| documentation | Retain the visual introduction and condense the body in both languages. |
| stored data | None. The existing local storage language key is reused; no server data is added. |

Data: none - the change uses only the existing browser language preference and does not persist server-side records.

## Surface

| Route | In | Out | Status | Who |
| --- | --- | --- | --- | --- |
| `GET /` | No input | Localized home page | 200 | Anyone |
| `GET /tools/*` | No input | Localized dedicated tool page | 200 | Anyone |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| Browser preference key | Reuse `i-love-open-converter-language`; absent or invalid value resolves to English, explicit `pt-BR` remains Portuguese | A new preference key would discard existing user choices and require migration. |
| README opening | Keep current screenshots, links, and badges in the same order | Replacing the opening visual would disregard the user's explicit instruction. |

## Criteria

### S1: Default the UI to English

**Acceptance Criteria**

1. WHEN a visitor has no saved language preference THEN every page SHALL initialize in English, set `html[lang]` to `en`, and show English as the selected language.
2. WHEN a visitor selects Brazilian Portuguese THEN all pages SHALL continue to use the saved `pt-BR` preference.
3. WHEN a stored preference is neither `en` nor `pt-BR` THEN the UI SHALL fall back to English.
4. WHEN a page title is shown on first visit THEN its title SHALL be in English.

### S2: Keep the READMEs concise

**Acceptance Criteria**

1. WHEN a reader opens either README THEN its existing opening visual block, screenshots, links, and badges SHALL remain in the same order.
2. WHEN an English reader scans `README.md` THEN the body SHALL provide a concise feature overview, Docker quick start, key limits/privacy notes, and development command without repeating settings in a large matrix.
3. WHEN a Brazilian Portuguese reader scans `README.pt-BR.md` THEN it SHALL provide the matching concise information in Portuguese.
4. WHEN supported conversions and privacy are described THEN the READMEs SHALL not promise unsupported universal format conversions or imply hosted document processing.

## Out of scope

- Removing Brazilian Portuguese or changing an explicitly saved language preference.
- Changing the screenshot artwork or the visual layout at the top of either README.
- Changing application functionality, conversion coverage, or self-host requirements.

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Existing preference | Preserve saved `pt-BR`; use English when no valid preference exists | The user requested English by default while keeping the existing language option. | Yes - explicit user request |
| README scope | Condense both language versions and retain their current opening visual | The project publishes a bilingual README pair, and the requested edit concerns the shared documentation content. | Yes - explicit user request |

**Open questions:** none.

## Sources

- `.specs/features/readme-english-refresh/request.md` - prior request for English README screenshots and a concise README.
- `src/i_love_open_converter/static/js/app.js` and dedicated page scripts - current saved language behavior.
- `src/i_love_open_converter/templates/` - current page language and title defaults.
- `README.md` and `README.pt-BR.md` - current documentation structure and feature claims.

## Differences from the source

None. The requested first-visit language and documentation trim preserve the existing tool behavior and README opening visual.
