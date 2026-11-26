# Third-party notices

## Background-removal model

The U2NetP ONNX weights are distributed by the [rembg project](https://github.com/danielgatis/rembg) from the [U-2-Net project](https://github.com/xuebinqin/U-2-Net). The U-2-Net project is licensed under Apache License 2.0; a copy is included at [licenses/U-2-Net-APACHE-2.0.txt](licenses/U-2-Net-APACHE-2.0.txt). Model source: <https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx>.

The rembg source library is licensed under MIT. ONNX Runtime is licensed under MIT. Each dependency's license is distributed with its installed package.

## Face detection

The face-blurring feature uses the OpenCV headless Python package and its bundled Haar cascade classifiers. OpenCV 4.5 and later are licensed under Apache License 2.0; the package license is distributed with the installed dependency.

## PSD conversion

PSD parsing and compositing uses [psd-tools](https://github.com/psd-tools/psd-tools), copyright Kota Yamaguchi, licensed under MIT. The license is distributed with the installed package.

## HEIC/HEIF conversion

HEIC/HEIF decoding uses [libheif 1.23.7](https://github.com/strukturag/libheif/tree/v1.23.7), licensed under LGPL-3.0-or-later. Its example command-line programs `heif-info` and `heif-dec` are licensed under MIT. The build enables the `libde265` HEVC decoder (LGPL-3.0-or-later) and JPEG encoding through libjpeg-turbo. The Docker image includes libheif and example-program license texts at `/app/licenses/heif`; Debian package copyright notices for the runtime codec libraries remain under `/usr/share/doc/`.

## Camera RAW conversion

RAW decoding uses [rawpy 0.28.0](https://github.com/letmaik/rawpy/tree/v0.28.0), licensed under MIT, compiled against the shared [LibRaw 0.22.3](https://github.com/LibRaw/LibRaw/tree/0.22.3) library, which is dual-licensed under LGPL-2.1 or CDDL. The Docker image includes the rawpy MIT license and both LibRaw license texts and copyright notice at `/app/licenses/rawpy` and `/app/licenses/libraw`. OpenMP and LittleCMS support are disabled; the optional GPL demosaic packs are not included.

## Searchable PDF OCR

OCR uses OCRmyPDF (MPL-2.0), Tesseract OCR (Apache-2.0), and the `eng` and `por` traineddata files (Apache-2.0). OCRmyPDF's Python dependencies and the Debian packages distribute their respective license texts with the installed packages.

## Local PDF translation

The `translate-pb_en-1_9` and `translate-en_pb-1_9` Argos model packages are derived from OPUS-MT (Jörg Tiedemann and Santhosh Thottingal, [2020 paper](https://aclanthology.org/2020.eamt-1.61/)) and are distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode). The model archives are downloaded from the [official Argos model directory](https://data.argosopentech.com/argospm/v1/) and SHA-256 verified during Docker build. CTranslate2 is MIT licensed; SentencePiece is Apache-2.0. The DejaVu Sans font is supplied by Debian's `fonts-dejavu-core` package under its included Bitstream Vera/DejaVu license.

## Local PDF summarization

The Docker image includes the [Google FLAN-T5-small model](https://huggingface.co/google/flan-t5-small) at revision `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab`, converted to INT8 CTranslate2 format during the image build. The model is Apache License 2.0; a copy is included at [licenses/FLAN-T5-APACHE-2.0.txt](licenses/FLAN-T5-APACHE-2.0.txt). CTranslate2 is MIT licensed and SentencePiece is Apache-2.0; their license texts are distributed with the installed packages.

## Interactive visual crop

The browser-side interactive crop UI for images and PDFs uses [Cropper.js v1.6.2](https://github.com/fengyuanchen/cropperjs), vendored locally under `src/i_love_open_converter/static/vendor/` and licensed under the MIT License.
