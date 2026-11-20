# Technology notes — document and web conversion

The cumulative roadmap remains the scope: Office documents to PDF; PDF to Word, PowerPoint and Excel; PDF to Markdown; extraction of embedded PDF images; and HTML or URL to PDF and image. Each supported input/output pair needs explicit disclosure. Processing and files remain local, subject to the project's existing privacy decisions.

## Initial findings

- LibreOffice exposes documented headless import/export filters for Office-to-PDF conversion, including separate Writer, Impress and Calc filters. A conversion process needs a private profile and a bounded lifetime. Its output must be inspected, not inferred solely from a successful process exit. [Official filter documentation](https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html?DbPAR=WRITER&System=LIN)
- Document macros and external resources are a separate security and privacy concern. Macro execution must be disabled, and network access from document conversion must be prevented rather than relying on document-provided settings. [LibreOffice security settings](https://help.libreoffice.org/latest/en-US/text/shared/optionen/01030300.html?DbPAR=SHARED)
- URL rendering requires a different network boundary: reject local, private and otherwise disallowed destinations, recheck every redirect and connection target, and prevent untrusted page subresources from bypassing the policy. The existing worker currently shares the Compose network, so this boundary must be designed and verified before exposing the URL tool.
- PDF-to-Office and PDF-to-Markdown have different fidelity limits; output must not promise preservation of arbitrary layouts, tables or embedded structures without verification. Select engines and publish a matrix before enabling the corresponding catalog entries.

## Next work

Develop the stage plan against the request, existing decisions and actual runtime; select and test isolation and conversion engines. Preserve all named stage capabilities in the cumulative roadmap.
