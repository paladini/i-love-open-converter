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

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ORT_DISABLE_TELEMETRY=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ghostscript fonts-urw-base35 fonts-dejavu-core libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 default-jre-headless libreoffice-writer libreoffice-calc libreoffice-impress tesseract-ocr tesseract-ocr-eng tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*
COPY --from=verapdf-installer /opt/verapdf /opt/verapdf
COPY --from=verapdf-installer /opt/u2net /opt/u2net
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
