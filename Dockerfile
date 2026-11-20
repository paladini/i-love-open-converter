FROM eclipse-temurin:17-jre AS verapdf-installer
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates && rm -rf /var/lib/apt/lists/*
COPY docker/verapdf-install.xml /tmp/verapdf-install.xml
RUN curl -fsSL -o /tmp/verapdf.zip https://software.verapdf.org/releases/1.30/verapdf-greenfield-1.30.3-installer.zip \
    && echo "b512bf24945503a33fc10738ecffc1f2dccaaf8593a448e94ee9ac86a9559a59  /tmp/verapdf.zip" | sha256sum -c - \
    && unzip -q /tmp/verapdf.zip -d /tmp \
    && java -jar /tmp/verapdf-greenfield-1.30.3/verapdf-izpack-installer-1.30.3.jar /tmp/verapdf-install.xml

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ghostscript fonts-urw-base35 default-jre-headless libreoffice-writer libreoffice-calc libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*
COPY --from=verapdf-installer /opt/verapdf /opt/verapdf
ENV VERAPDF_BIN=/opt/verapdf/verapdf

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8080
CMD ["/app/.venv/bin/uvicorn", "i_love_open_converter.main:app", "--host", "0.0.0.0", "--port", "8080"]
