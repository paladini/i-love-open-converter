# Translation model research

Verified against the official Argos package directory on 2026-11-21 by downloading each exact archive, checking its metadata and embedded README, measuring its compressed and expanded sizes, and computing SHA-256.

| Package | Direction | Compressed bytes | Expanded bytes | SHA-256 |
| --- | --- | ---: | ---: | --- |
| `translate-pb_en-1_9.argosmodel` | Portuguese (Brazil) → English | 69,447,841 | 82,857,048 | `578e9c504595ac85f8e8e0b31e4f53c84e38e7638db8c3c8df384d05eac2671b` |
| `translate-en_pb-1_9.argosmodel` | English → Portuguese (Brazil) | 66,179,201 | 82,958,472 | `1d1cd5e9540c6b38c258bed002a42d3b311b8a189acb74feaa311ef30d175c5b` |

Combined archives total 135,627,042 bytes (about 130 MiB); extracted model files total 165,815,520 bytes (about 158 MiB). The lightweight runtime pins CTranslate2 and SentencePiece and avoids loading Stanza or PyTorch. A dry run of the official PyPI Argos Translate 1.11.0 dependency graph resolved `stanza==1.10.1`; its PyTorch wheel alone is about 539 MB on Linux x86_64, so this feature uses the same official model files through CTranslate2 directly to honor the user's approximately 200 MB image-growth choice.

Both package `metadata.json` files declare Argos package version 1.9 and the expected source and target codes. Their embedded READMEs cite Jörg Tiedemann and Santhosh Thottingal's 2020 OPUS-MT paper and state that the derived models are licensed CC-BY 4.0. The Argos maintainers' model license audit lists `pb_en-1_9` and `en_pb-1_9` under OPUS-MT (CC-BY 4.0). Preserve that attribution and license link in the third-party notices.

Sources:

- [Official Argos model directory](https://data.argosopentech.com/argospm/v1/)
- [Argos package index](https://github.com/argosopentech/argospm-index/blob/main/index.json)
- [Argos model license audit](https://community.libretranslate.com/t/model-licenses-for-argos-translate/2442)
- [OPUS-MT paper, ACL Anthology](https://aclanthology.org/2020.eamt-1.61/)
- [CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode)
- [Argos Translate 1.11.0 metadata](https://pypi.org/pypi/argostranslate/1.11.0/json) - lists Stanza as a runtime dependency.
- [CTranslate2 on PyPI](https://pypi.org/project/ctranslate2/) - CPython 3.14 wheels are available for Linux x86_64 and ARM64.
- [PyTorch 2.15.0 on PyPI](https://pypi.org/project/torch/2.15.0/) - Linux x86_64 wheel size documents the cost avoided by direct CTranslate2 use.
