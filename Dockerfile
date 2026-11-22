FROM eclipse-temurin:17-jre AS verapdf-installer
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates && rm -rf /var/lib/apt/lists/*
COPY docker/verapdf-install.xml /tmp/verapdf-install.xml
RUN curl -fsSL -o /tmp/verapdf.zip https://software.verapdf.org/releases/1.30/verapdf-greenfield-1.30.3-installer.zip \
    && echo "b512bf24945503a33fc10738ecffc1f2dccaaf8593a448e94ee9ac86a9559a59  /tmp/verapdf.zip" | sha256sum -c - \
    && unzip -q /tmp/verapdf.zip -d /tmp \
    && java -jar /tmp/verapdf-greenfield-1.30.3/verapdf-izpack-installer-1.30.3.jar /tmp/verapdf-install.xml
RUN mkdir -p /opt/u2net \
    && curl -fsSL -o /opt/u2net/u2netp.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx \
    && echo "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8  /opt/u2net/u2netp.onnx" | sha256sum -c -

FROM python:3.14-slim AS heif-builder
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates cmake curl libde265-dev libjpeg62-turbo-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/libheif-build
RUN curl -fsSL -o libheif.tar.gz https://github.com/strukturag/libheif/releases/download/v1.23.7/libheif-1.23.7.tar.gz \
    && echo "f7483e818503ea6224c8863e4a56ac02c7089021a98472c811c12aa19faf2475  libheif.tar.gz" | sha256sum -c - \
    && tar -xzf libheif.tar.gz --strip-components=1 \
    && cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DCMAKE_INSTALL_LIBDIR=lib \
        -DENABLE_PLUGIN_LOADING=OFF \
        -DWITH_LIBDE265=ON \
        -DWITH_LIBDE265_PLUGIN=OFF \
        -DWITH_X265=OFF \
        -DWITH_X265_PLUGIN=OFF \
        -DWITH_AOM_DECODER=OFF \
        -DWITH_AOM_DECODER_PLUGIN=OFF \
        -DWITH_AOM_ENCODER=OFF \
        -DWITH_AOM_ENCODER_PLUGIN=OFF \
        -DWITH_DAV1D=OFF \
        -DWITH_DAV1D_PLUGIN=OFF \
        -DWITH_OpenH264_DECODER=OFF \
        -DWITH_OpenH264_DECODER_PLUGIN=OFF \
        -DWITH_OpenH264_ENCODER=OFF \
        -DWITH_OPENJPH_DECODER=OFF \
        -DWITH_OPENJPH_ENCODER=OFF \
        -DWITH_JPEG_DECODER=OFF \
        -DWITH_JPEG_ENCODER=ON \
        -DWITH_JPEG_ENCODER_PLUGIN=OFF \
        -DWITH_EXAMPLES=ON \
        -DWITH_EXAMPLE_HEIF_THUMB=OFF \
        -DWITH_EXAMPLE_HEIF_VIEW=OFF \
        -DWITH_GDK_PIXBUF=OFF \
        -DBUILD_TESTING=OFF \
        -DBUILD_DOCUMENTATION=OFF \
    && cmake --build build --parallel 2 --target heif-info heif-dec heif-enc \
    && cmake --install build \
    && mkdir -p /usr/local/share/licenses/libheif \
    && cp COPYING /usr/local/share/licenses/libheif/COPYING \
    && cp examples/COPYING /usr/local/share/licenses/libheif/COPYING.examples \
    && cp /usr/share/doc/libde265-0/copyright /usr/local/share/licenses/libheif/libde265-copyright

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ORT_DISABLE_TELEMETRY=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ghostscript fonts-urw-base35 fonts-dejavu-core libde265-0 libjpeg62-turbo libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 default-jre-headless libreoffice-writer libreoffice-calc libreoffice-impress tesseract-ocr tesseract-ocr-eng tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*
COPY --from=verapdf-installer /opt/verapdf /opt/verapdf
COPY --from=verapdf-installer /opt/u2net /opt/u2net
COPY --from=heif-builder /usr/local/bin/heif-info /usr/local/bin/heif-dec /usr/local/bin/
COPY --from=heif-builder /usr/local/lib/libheif.so* /usr/local/lib/
COPY --from=heif-builder /usr/local/share/licenses/libheif /app/licenses/heif
RUN ldconfig
ENV VERAPDF_BIN=/opt/verapdf/verapdf \
    U2NET_HOME=/opt/u2net

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md README.pt-BR.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY licenses ./licenses
COPY docker/install_translation_models.py /tmp/install_translation_models.py
RUN python /tmp/install_translation_models.py && rm /tmp/install_translation_models.py
ENV TRANSLATION_MODEL_DIR=/opt/translation-models
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev
COPY docker/ocr-smoke.py /tmp/ocr-smoke.py
COPY docker/translation-smoke.py /tmp/translation-smoke.py
RUN /app/.venv/bin/python /tmp/ocr-smoke.py && /app/.venv/bin/python /tmp/translation-smoke.py && rm /tmp/ocr-smoke.py /tmp/translation-smoke.py

EXPOSE 8080
CMD ["/app/.venv/bin/uvicorn", "i_love_open_converter.main:app", "--host", "0.0.0.0", "--port", "8080"]
