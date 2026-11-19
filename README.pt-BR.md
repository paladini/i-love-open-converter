# I Love Open Converter

Uma caixa de ferramentas gratuita e self-hosted para conversões comuns de imagens e PDFs. Envie arquivos pelo navegador, processe tudo no seu próprio servidor e baixe o resultado. Os arquivos ficam no seu HomeLab; o aplicativo não tem anúncios, contas, armazenamento em nuvem nem telemetria externa.

O projeto está em desenvolvimento ativo. A primeira versão foca em operações comuns com imagens estáticas e ferramentas essenciais para PDF.

## Início rápido

Requisitos: Docker Engine e Docker Compose v2.

```sh
cp .env.example .env
mkdir -p data
docker compose up -d --build
```

Abra <http://localhost:8080>. Se a porta já estiver em uso, altere `APP_PORT` em `.env` e reinicie o Compose.

Para parar a aplicação:

```sh
docker compose down
```

O banco e os arquivos ficam em `./data`. Faça backup desse diretório se quiser preservar jobs pendentes ou resultados ao trocar de máquina.

## Recursos disponíveis

- Converter, redimensionar, comprimir e girar imagens estáticas JPEG, PNG, WebP, BMP ou TIFF; processe até 10 arquivos por job e baixe lotes em ZIP.
- Mesclar, dividir por intervalos de páginas, girar e otimizar PDFs sem senha; renderizar páginas de PDF para JPG ou transformar imagens em PDFs A4.
- Interface em português do Brasil e inglês.
- Processamento local por serviço web, fila SQLite e worker.

Cada arquivo enviado pode ter até 100 MB por padrão. Cada job pode processar até 10 arquivos. Imagens animadas e conversões avançadas de documentos (Office, OCR, PDF/A e IA) ficam fora da versão inicial. Os formatos de entrada são validados pelo conteúdo antes do processamento.

## Configuração

Copie `.env.example` para `.env`. O Compose lê essas configurações ao iniciar os containers:

| Configuração | Padrão | Finalidade |
| --- | --- | --- |
| `APP_PORT` | `8080` | Porta no host para a interface e a API |
| `MAX_FILE_SIZE_MB` | `100` | Tamanho máximo de cada arquivo enviado |
| `MAX_TOTAL_UPLOAD_MB` | `500` | Total máximo enviado em uma requisição |
| `MAX_FILES_PER_JOB` | `10` | Quantidade máxima de arquivos por job |
| `JOB_RETENTION_HOURS` | `24` | Tempo até remover o job e os arquivos locais |
| `WORKER_POLL_SECONDS` | `1` | Intervalo entre consultas do worker à fila |
| `PUID`, `PGID` | `1000` | IDs de usuário e grupo donos dos arquivos no volume |

O worker e o processo web precisam de acesso de leitura e gravação em `./data`. No Linux, configure `PUID` e `PGID` com os IDs da conta dona desse diretório.

## Privacidade

Todo processamento e armazenamento acontecem na máquina em que a aplicação foi instalada. A interface usa arquivos estáticos locais e não carrega analytics, fontes ou scripts de terceiros. Qualquer pessoa que consiga acessar o serviço pode usá-lo. Os links de job usam IDs imprevisíveis, mas não são contas nem uma fronteira de controle de acesso. Disponibilize o serviço apenas em uma rede que você controla.

## Contribuição

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para configurar o ambiente de desenvolvimento, executar testes e seguir as instruções de contribuição.

## Licença

Este projeto está sob a GNU Affero General Public License v3.0. Consulte [LICENSE](LICENSE).
