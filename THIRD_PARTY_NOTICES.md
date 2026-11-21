# Third-party notices

## Background-removal model

The U2NetP ONNX weights are distributed by the [rembg project](https://github.com/danielgatis/rembg) from the [U-2-Net project](https://github.com/xuebinqin/U-2-Net). The U-2-Net project is licensed under Apache License 2.0; a copy is included at [licenses/U-2-Net-APACHE-2.0.txt](licenses/U-2-Net-APACHE-2.0.txt). Model source: <https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx>.

The rembg source library is licensed under MIT. ONNX Runtime is licensed under MIT. Each dependency's license is distributed with its installed package.

## Face detection

The face-blurring feature uses the OpenCV headless Python package and its bundled Haar cascade classifiers. OpenCV 4.5 and later are licensed under Apache License 2.0; the package license is distributed with the installed dependency.

## Searchable PDF OCR

OCR uses OCRmyPDF (MPL-2.0), Tesseract OCR (Apache-2.0), and the `eng` and `por` traineddata files (Apache-2.0). OCRmyPDF's Python dependencies and the Debian packages distribute their respective license texts with the installed packages.

## Local PDF translation

The `translate-pb_en-1_9` and `translate-en_pb-1_9` Argos model packages are derived from OPUS-MT (Jörg Tiedemann and Santhosh Thottingal, [2020 paper](https://aclanthology.org/2020.eamt-1.61/)) and are distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode). The model archives are downloaded from the [official Argos model directory](https://data.argosopentech.com/argospm/v1/) and SHA-256 verified during Docker build. CTranslate2 is MIT licensed; SentencePiece is Apache-2.0. The DejaVu Sans font is supplied by Debian's `fonts-dejavu-core` package under its included Bitstream Vera/DejaVu license.
