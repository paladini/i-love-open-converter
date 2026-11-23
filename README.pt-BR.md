# I Love Open Converter

**Uma caixa de ferramentas privada e auto-hospedada para tarefas comuns com PDFs e imagens.**

Envie um arquivo, escolha uma ferramenta e baixe o resultado em uma interface
web simples. O processamento e os arquivos ficam no seu próprio servidor.

<p align="center">
  <img src="docs/screenshots/home.jpg" alt="Página inicial em inglês com o catálogo de ferramentas para PDF e imagens" width="100%">
</p>
<p align="center">
  <img src="docs/screenshots/image-compress-result.jpg" alt="Compressão de imagem concluída na interface em inglês" width="49%">
  <img src="docs/screenshots/pdf-page-numbers-result.jpg" alt="Numeração de páginas de PDF concluída na interface em inglês" width="49%">
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="https://github.com/paladini/i-love-open-converter/releases">Versões</a> ·
  <a href="https://github.com/paladini/i-love-open-converter/pkgs/container/i-love-open-converter">Imagem de contêiner</a> ·
  <a href="CONTRIBUTING.md">Como contribuir</a> ·
  <a href="SUPPORT.md">Suporte</a> ·
  <a href="SECURITY.md">Segurança</a> ·
  <a href="CHANGELOG.md">Histórico de alterações</a>
</p>

<p align="center">
  <a href="https://github.com/paladini/i-love-open-converter/releases/latest"><img alt="Última versão" src="https://img.shields.io/github/v/release/paladini/i-love-open-converter?display_name=tag"></a>
  <a href="LICENSE"><img alt="Licença AGPL-3.0" src="https://img.shields.io/github/license/paladini/i-love-open-converter"></a>
  <a href="https://github.com/paladini/i-love-open-converter/pkgs/container/i-love-open-converter"><img alt="Imagem de contêiner no GHCR" src="https://img.shields.io/badge/container-GHCR-2496ED?logo=github"></a>
</p>

O I Love Open Converter é um conjunto gratuito e self-hosted de ferramentas para PDF e imagens. Escolha uma ferramenta, envie um arquivo e baixe o resultado no seu próprio servidor.

## Recursos

- **PDF:** comprimir e girar vários arquivos, organizar, editar, mesclar, dividir, proteger, aplicar OCR, resumir, traduzir, comparar, ocultar conteúdo e converter PDFs.
- **Imagens:** converter, comprimir, redimensionar, recortar, editar, aplicar marca d’água, remover fundos, desfocar rostos ou placas e muito mais.
- **Documentos e web:** converter arquivos Office, renderizar páginas HTML e exportar PDFs para Markdown ou planilhas.

Os formatos dependem da ferramenta escolhida. O processamento fica no seu servidor; o modelo de resumo de PDF é executado localmente.

<details>
<summary>Formatos e limites disponíveis</summary>

### Formatos e limites

| Entrada | Operação | Saída |
| --- | --- | --- |
| JPEG, PNG, GIF estático, WebP, BMP, TIFF | Conversão genérica de imagens | JPEG, PNG, WebP ou GIF estático de um quadro por entrada |
| JPEG (`.jpg`, `.jpeg`) | Converter para PNG ou criar GIF animado com JPEGs na ordem escolhida | PNG ou GIF animado |
| SVG (`.svg`) | Converter SVG estático localmente | JPEG, PNG ou WebP |
| PSD (`.psd`) | Converter imagem achatada localmente | JPEG, PNG ou WebP |
| HEIC, HEIF, HIF | Converter uma imagem estática localmente | JPEG |
| RAW de câmera (.3fr, .ari, .arw, .bay, .cap, .cr2, .cr3, .crw, .dcr, .dcs, .dng, .drf, .eip, .erf, .fff, .gpr, .iiq, .k25, .kdc, .mdc, .mef, .mos, .mrw, .nef, .nrw, .orf, .pef, .ptx, .raf, .raw, .rw2, .rwl, .sr2, .srf, .srw) | Revelar localmente; suporte varia conforme a câmera | JPEG; até 100 MiB por arquivo |
| PDF sem criptografia | Mesclar, dividir, organizar, editar, proteger, aplicar OCR, traduzir, reparar, comparar e ocultar conteúdo | PDF |
| PDF com texto selecionável | Converter para documentos Office editáveis | DOCX, PPTX ou XLSX |
| PDF digitalizado (até 20 páginas) | OCR local opcional antes da exportação para Word ou Excel | DOCX ou XLSX; layout e precisão do OCR variam |
| PDF | Exportar para Markdown ou extrair imagens incorporadas | Arquivo ZIP |
| Word, PowerPoint, Excel | Converter para PDF | PDF |
| HTML (`.html`, `.htm`) ou URL pública | HTML para PDF | PDF |
| HTML (`.html`, `.htm`) ou URL pública | HTML para imagens | Arquivo ZIP |

Limites por job: 100 MB por arquivo, 500 MB por requisição, 10 arquivos e retenção por 24 horas.
</details>

## Início rápido com Docker

Requisitos: Docker Engine e Docker Compose v2.

```sh
git clone https://github.com/paladini/i-love-open-converter.git
cd i-love-open-converter
cp .env.example .env
mkdir -p data
docker compose up -d
```

Abra <http://localhost:8080>. O aplicativo web e o worker são serviços separados, e os dados ficam em `./data`. No PowerShell, use `Copy-Item .env.example .env` e `New-Item -ItemType Directory -Force data`.

## Limites e privacidade

- Padrões: 100 MB por arquivo, 500 MB por requisição, 10 arquivos por job e retenção de 24 horas. Altere em `.env`.
- A captura de URLs aceita recursos HTTP(S) públicos com limites; JavaScript e páginas autenticadas não são suportados. O worker processa arquivos offline.
- Assinaturas em PDF são visuais. Confira ocultações e resumos antes de compartilhar.
- O app não inclui contas, analytics ou telemetria. Mantenha-o em rede confiável ou atrás de um proxy autenticado.

Use `docker compose ps`, `docker compose logs -f web worker` e `docker compose down` para conferir, investigar e parar os serviços sem apagar os arquivos.

<details>
<summary>Padrões de configuração</summary>

| Configuração | Padrão |
| --- | --- |
| `APP_PORT` | `8080` |
| `IMAGE_TAG` | `latest` |
| `MAX_FILE_SIZE_MB` | `100` |
| `MAX_TOTAL_UPLOAD_MB` | `500` |
| `MAX_FILES_PER_JOB` | `10` |
| `JOB_RETENTION_HOURS` | `24` |
| `WORKER_POLL_SECONDS` | `1` |
| `PUID` | `1000` |
| `PGID` | `1000` |

Copie [`.env.example`](.env.example) para `.env` antes de alterar as opções.
</details>

## Desenvolvimento

Requisitos: Python 3.14 e [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-groups
uv run playwright install chromium
uv run uvicorn i_love_open_converter.main:app --app-dir src --reload
```

Consulte [CONTRIBUTING.md](CONTRIBUTING.md). Licenciado sob [AGPL-3.0](LICENSE).
