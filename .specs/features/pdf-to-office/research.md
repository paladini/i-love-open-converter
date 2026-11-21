# PDF to Office research

The cumulative roadmap explicitly requires PDF to Word, PowerPoint and Excel. Conversion must be local and output fidelity must be disclosed. Evaluate each destination and retain all three in the roadmap; Word is the first vertical slice.

The upstream [pdf2docx repository](https://github.com/ArtifexSoftware/pdf2docx) states that Artifex no longer actively maintains it and that the project has been relicensed under MIT. The current published `pdf2docx==0.5.13` declares MIT and depends on PyMuPDF, python-docx, NumPy, OpenCV and fontTools. Verify compatibility with this project's pinned PyMuPDF 2.1 and both supported Linux architectures, and run the converter in a resource-bounded subprocess before considering it for the product. The [conversion documentation](https://github.com/ArtifexSoftware/pdf2docx/blob/master/docs/quickstart.convert.rst) describes its PDF-to-DOCX interface. It reconstructs document structure and is not expected to preserve all layouts.

PDF to PowerPoint and Excel require independent engine and fidelity decisions. Preserve the original requirement and investigate editable output, table extraction, image-only and scanned PDFs, and safe degradation before enabling either tool.
