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

O I Love Open Converter reúne ferramentas para PDF e imagens no seu
computador, HomeLab ou NAS. Escolha uma ferramenta, envie o arquivo e baixe o
resultado.

## Ferramentas

- **Imagens:** converter, redimensionar, comprimir, recortar, girar, adicionar
  marca d'água, editar, criar memes, ampliar, remover fundos, desfocar rostos
  ou placas e converter arquivos SVG, PSD, HEIC e RAW localmente.
- **PDF:** mesclar, dividir, organizar, editar, ocultar conteúdo, assinar
  visualmente, proteger, desbloquear, reparar, comparar, aplicar OCR, traduzir,
  numerar páginas, converter para e de arquivos Office, imagens e HTML, além
  de exportar para Markdown ou planilhas.

A página inicial lista as ferramentas disponíveis. Algumas operações
opcionais, como a conversão para PDF/A, precisam de dependências locais extras.
Consulte o [roadmap do projeto](.specs/features/project-foundation/plan.md).

## Limites importantes

- O projeto oferece fluxos compatíveis para PDF e imagens; não converte
  qualquer tipo de arquivo para qualquer outro. Os formatos variam conforme a
  ferramenta.
- Assinaturas em PDF são marcas visuais, o preenchimento aceita campos já
  existentes e os resumos extraem frases de texto selecionável. Aplique OCR a
  documentos digitalizados antes.
- A tradução é local e funciona entre português brasileiro e inglês. A captura
  de HTML aceita conteúdo estático, sem JavaScript ou sessões autenticadas. A
  captura de URLs faz requisições limitadas a endereços HTTP(S) públicos pelo
  serviço web; o worker não tem acesso à rede.
- Por padrão, cada arquivo pode ter até 100 MB, cada requisição até 500 MB e
  cada job até 10 arquivos. Jobs e arquivos são removidos após 24 horas. Altere
  esses padrões em `.env`.

## Início rápido

Requisitos: Docker Engine e Docker Compose v2.

```sh
git clone https://github.com/paladini/i-love-open-converter.git
cd i-love-open-converter
cp .env.example .env
mkdir -p data
docker compose up -d
```

No Windows PowerShell, use `Copy-Item .env.example .env` e
`New-Item -ItemType Directory -Force data` no lugar de `cp` e `mkdir`. Abra
<http://localhost:8080>. O Compose inicia o aplicativo web e um worker
separado. Os dados ficam em `./data`; faça backup para preservar jobs e
resultados.

Altere `APP_PORT` em `.env` para mudar a porta. Consulte os demais ajustes em
[`.env.example`](.env.example). Use `docker compose logs -f web worker` para
ver logs, `docker compose pull && docker compose up -d` para atualizar e
`docker compose down` para parar os serviços.

## Privacidade e segurança

Os arquivos são processados no servidor que você controla. O aplicativo não
tem contas nem autenticação integrada; qualquer pessoa que alcance o serviço
pode enviar jobs. Mantenha-o em uma rede confiável ou use VPN ou proxy reverso
com autenticação. Não o exponha diretamente à internet pública.

A interface usa recursos locais e não carrega scripts, analytics ou
telemetria de terceiros. Confira PDFs com conteúdo ocultado e outros arquivos
sensíveis antes de compartilhá-los; a ocultação não remove metadados, anexos ou
o arquivo original armazenado.

## Desenvolvimento

Requisitos: Python 3.14 e [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-groups
uv run playwright install chromium
uv run uvicorn i_love_open_converter.main:app --app-dir src --reload
```

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para orientações de desenvolvimento
e pull requests.

## Licença

Licenciado sob a [GNU Affero General Public License v3.0](LICENSE).
