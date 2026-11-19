const messages = {
  "pt-BR": {
    localBadge: "100% local", languageLabel: "Idioma", brandHome: "I Love Open Converter — início",
    removeFile: "Remover arquivo", heroEyebrow: "SEUS ARQUIVOS, SUAS REGRAS",
    heroTitle: 'Converta do seu jeito.<br><span>Fica tudo com você.</span>',
    heroDescription: "Ferramentas práticas para seus arquivos, executadas no seu próprio servidor. Sem anúncios. Sem enviar seus documentos para a nuvem.",
    metaOpen: "Open-source", metaPrivate: "Arquivos permanecem locais", metaFree: "Gratuito para self-host",
    toolsEyebrow: "A CAIXA DE FERRAMENTAS", toolsTitle: "O que vamos transformar?", toolsNote: "Escolha uma ferramenta para começar",
    imageGroup: "Imagens", imageCount: "01 disponível", pdfGroup: "PDF", pdfCount: "Em preparação",
    convertTitle: "Converter imagem", convertHint: "PNG, JPG, WebP e mais", resizeTitle: "Redimensionar imagem",
    compressImageTitle: "Comprimir imagem", rotateImageTitle: "Girar imagem", mergeTitle: "Mesclar PDF",
    splitTitle: "Dividir PDF", rotatePdfTitle: "Girar PDF", compressPdfTitle: "Comprimir PDF",
    comingSoon: "Em breve", soon: "Em breve", selectedTool: "FERRAMENTA SELECIONADA",
    dropTitle: "Solte sua imagem aqui", dropOr: "ou", browse: "escolha um arquivo",
    fileTypes: "JPG, PNG, WEBP, BMP, TIFF · até {maxFileMb} MB", outputLabel: "Converter para",
    resultFormat: "Formato de saída", localNote: "Seu arquivo é processado no servidor que você controla.",
    convertButton: "Converter imagem", downloadButton: "Baixar arquivo", startAgain: "Converter outro arquivo",
    trustLocalTitle: "Hospedado por você", trustLocalBody: "Seus arquivos ficam no seu HomeLab",
    trustNoAdsTitle: "Sem anúncios ou rastreadores", trustNoAdsBody: "Sem conexões com serviços externos",
    trustOpenTitle: "Feito para ser aberto", trustOpenBody: "Código aberto, gratuito e seu",
    footerText: "Seu espaço. Seus arquivos. Sem complicação.",
    queued: "Na fila. Vamos começar assim que o worker estiver disponível.",
    processing: "Convertendo sua imagem...", succeeded: "Sua imagem está pronta.",
    selectFile: "Escolha uma imagem antes de converter.", uploadError: "Não foi possível enviar o arquivo. Tente novamente.",
    invalidFile: "O arquivo não é uma imagem válida.", unsupportedFormat: "Formato não suportado. Use JPG, PNG, WebP, BMP ou TIFF.",
    fileTooLarge: "O arquivo excede o limite configurado.", requestTooLarge: "O envio excede o limite total.",
    processingFailed: "Não foi possível processar este arquivo.", genericError: "Algo deu errado. Tente novamente.",
    tooManyFiles: "A quantidade de arquivos excede o limite.", invalidOptions: "As opções selecionadas não são válidas.",
    conversionFailed: "A conversão falhou. Verifique o arquivo e tente novamente.",
  },
  en: {
    localBadge: "100% local", languageLabel: "Language", brandHome: "I Love Open Converter — home",
    removeFile: "Remove file", heroEyebrow: "YOUR FILES, YOUR RULES",
    heroTitle: 'Convert your way.<br><span>It all stays with you.</span>',
    heroDescription: "Practical tools for your files, running on your own server. No ads. No sending documents to the cloud.",
    metaOpen: "Open source", metaPrivate: "Files stay on your server", metaFree: "Free to self-host",
    toolsEyebrow: "THE TOOLBOX", toolsTitle: "What shall we transform?", toolsNote: "Choose a tool to get started",
    imageGroup: "Images", imageCount: "01 available", pdfGroup: "PDF", pdfCount: "Coming together",
    convertTitle: "Convert image", convertHint: "PNG, JPG, WebP and more", resizeTitle: "Resize image",
    compressImageTitle: "Compress image", rotateImageTitle: "Rotate image", mergeTitle: "Merge PDF",
    splitTitle: "Split PDF", rotatePdfTitle: "Rotate PDF", compressPdfTitle: "Compress PDF",
    comingSoon: "Coming soon", soon: "Soon", selectedTool: "SELECTED TOOL",
    dropTitle: "Drop your image here", dropOr: "or", browse: "choose a file",
    fileTypes: "JPG, PNG, WEBP, BMP, TIFF · up to {maxFileMb} MB", outputLabel: "Convert to",
    resultFormat: "Output format", localNote: "Your file is processed on the server you control.",
    convertButton: "Convert image", downloadButton: "Download file", startAgain: "Convert another file",
    trustLocalTitle: "Hosted by you", trustLocalBody: "Your files stay on your HomeLab",
    trustNoAdsTitle: "No ads or trackers", trustNoAdsBody: "No external service connections",
    trustOpenTitle: "Made to stay open", trustOpenBody: "Open source, free, and yours",
    footerText: "Your space. Your files. No fuss.",
    queued: "Queued. We’ll start as soon as the worker is available.",
    processing: "Converting your image...", succeeded: "Your image is ready.",
    selectFile: "Choose an image before converting.", uploadError: "The file could not be uploaded. Try again.",
    invalidFile: "This file is not a valid image.", unsupportedFormat: "Unsupported format. Use JPG, PNG, WebP, BMP, or TIFF.",
    fileTooLarge: "The file is over the configured size limit.", requestTooLarge: "The upload is over the total size limit.",
    processingFailed: "This file could not be processed.", genericError: "Something went wrong. Try again.",
    tooManyFiles: "The number of files is over the limit.", invalidOptions: "The selected options are not valid.",
    conversionFailed: "Conversion failed. Check the file and try again.",
  },
};

const form = document.querySelector("#convert-form");
const fileInput = document.querySelector("#file-input");
const selectedFile = document.querySelector("#selected-file");
const selectedName = document.querySelector("#selected-file-name");
const selectedSize = document.querySelector("#selected-file-size");
const outputFormat = document.querySelector("#output-format");
const formatTarget = document.querySelector("#format-target-label");
const formatTargetIcon = document.querySelector("#format-target-icon");
const dropZone = document.querySelector("#drop-zone");
const formError = document.querySelector("#form-error");
const jobStatus = document.querySelector("#job-status");
const jobStatusText = document.querySelector("#job-status-text");
const jobSpinner = document.querySelector("#job-spinner");
const jobResult = document.querySelector("#job-result");
const resultName = document.querySelector("#result-name");
const downloadButton = document.querySelector("#download-button");
const resetButton = document.querySelector("#reset-button");
const submitButton = document.querySelector("#submit-button");
const languageSelect = document.querySelector("#language");
let currentFile = null;
let currentLanguage = localStorage.getItem("i-love-open-converter-language") || "pt-BR";
let pollTimer = null;

function t(key) { return messages[currentLanguage][key] || messages["pt-BR"][key] || key; }

function applyLanguage(language) {
  currentLanguage = language === "en" ? "en" : "pt-BR";
  document.documentElement.lang = currentLanguage;
  languageSelect.value = currentLanguage;
  localStorage.setItem("i-love-open-converter-language", currentLanguage);
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    let value = messages[currentLanguage][element.dataset.i18n];
    if (value === undefined) return;
    if (element.id === "file-types") value = value.replace("{maxFileMb}", element.dataset.maxFileMb);
    if (element.id === "hero-title") element.innerHTML = value;
    else element.textContent = value;
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAria));
  });
  updateFormatTarget();
}

function updateFormatTarget() {
  const format = outputFormat.value === "JPEG" ? "JPG" : outputFormat.value;
  formatTarget.textContent = format;
  formatTargetIcon.textContent = format;
}

function formatBytes(size) {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function showFile(file) {
  currentFile = file || null;
  selectedFile.hidden = !currentFile;
  dropZone.hidden = Boolean(currentFile);
  if (currentFile) {
    selectedName.textContent = currentFile.name;
    selectedSize.textContent = formatBytes(currentFile.size);
  }
  clearError();
}

function clearError() {
  formError.hidden = true;
  formError.textContent = "";
}

function showError(message) {
  clearInterval(pollTimer);
  jobSpinner.hidden = true;
  jobStatus.hidden = false;
  jobStatusText.textContent = message;
  jobResult.hidden = true;
  resetButton.hidden = false;
  formError.hidden = true;
  submitButton.disabled = false;
}

function apiErrorMessage(code) {
  const codes = {
    invalid_file: "invalidFile", unsupported_format: "unsupportedFormat", file_too_large: "fileTooLarge",
    request_too_large: "requestTooLarge", processing_failed: "processingFailed", invalid_options: "invalidOptions",
    too_many_files: "tooManyFiles",
  };
  return t(codes[code] || "genericError");
}

async function pollJob(statusUrl) {
  try {
    const response = await fetch(statusUrl, { headers: { Accept: "application/json" } });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error?.code || "genericError");
    if (payload.state === "queued") {
      jobStatusText.textContent = t("queued");
      return;
    }
    if (payload.state === "processing") {
      jobStatusText.textContent = t("processing");
      return;
    }
    if (payload.state === "failed") {
      showError(apiErrorMessage(payload.error?.code));
      return;
    }
    if (payload.state === "succeeded") {
      clearInterval(pollTimer);
      jobSpinner.hidden = true;
      jobStatusText.textContent = t("succeeded");
      const file = payload.files?.[0];
      resultName.textContent = file?.name || "";
      downloadButton.href = payload.download_url;
      jobResult.hidden = false;
      resetButton.hidden = false;
      submitButton.disabled = false;
    }
  } catch (error) {
    showError(error.message === "job_not_found" ? t("genericError") : t("conversionFailed"));
  }
}

fileInput.addEventListener("change", () => showFile(fileInput.files?.[0]));
document.querySelector("#remove-file").addEventListener("click", () => {
  fileInput.value = "";
  showFile(null);
});
outputFormat.addEventListener("change", updateFormatTarget);
languageSelect.addEventListener("change", () => applyLanguage(languageSelect.value));
document.querySelector("#year").textContent = new Date().getFullYear();

for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragover");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragover");
  });
}
dropZone.addEventListener("drop", (event) => showFile(event.dataTransfer.files?.[0]));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  if (!currentFile) {
    formError.textContent = t("selectFile");
    formError.hidden = false;
    fileInput.focus();
    return;
  }
  clearInterval(pollTimer);
  jobResult.hidden = true;
  resetButton.hidden = true;
  jobStatus.hidden = false;
  jobSpinner.hidden = false;
  jobStatusText.textContent = t("queued");
  submitButton.disabled = true;
  const body = new FormData();
  body.append("operation", "image.convert");
  body.append("options", JSON.stringify({ format: outputFormat.value }));
  body.append("files", currentFile, currentFile.name);
  try {
    const response = await fetch("/api/jobs", { method: "POST", body });
    const payload = await response.json();
    if (!response.ok) {
      const error = new Error(payload.error?.code || "genericError");
      throw error;
    }
    pollTimer = setInterval(() => pollJob(payload.status_url), 1000);
    await pollJob(payload.status_url);
  } catch (error) {
    showError(apiErrorMessage(error.message));
  }
});

resetButton.addEventListener("click", () => {
  clearInterval(pollTimer);
  form.reset();
  fileInput.value = "";
  showFile(null);
  jobStatus.hidden = true;
  jobResult.hidden = true;
  resetButton.hidden = true;
  jobSpinner.hidden = false;
  submitButton.disabled = false;
  clearError();
  updateFormatTarget();
  dropZone.scrollIntoView({ behavior: "smooth", block: "center" });
});

applyLanguage(currentLanguage);
