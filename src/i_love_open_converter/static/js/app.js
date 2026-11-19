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
    resizeHint: "Defina largura e altura", compressImageTitle: "Comprimir imagem", compressHint: "Controle a qualidade final",
    rotateImageTitle: "Girar imagem", rotateHint: "90°, 180° ou 270°", mergeTitle: "Mesclar PDF",
    splitTitle: "Dividir PDF", rotatePdfTitle: "Girar PDF", compressPdfTitle: "Comprimir PDF",
    comingSoon: "Em breve", soon: "Em breve", selectedTool: "FERRAMENTA SELECIONADA",
    widthLabel: "Largura (px)", heightLabel: "Altura (px)", qualityLabel: "Qualidade", degreesLabel: "Rotação",
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
    resizeHint: "Set width and height", compressImageTitle: "Compress image", compressHint: "Control output quality",
    rotateImageTitle: "Rotate image", rotateHint: "90°, 180°, or 270°", mergeTitle: "Merge PDF",
    splitTitle: "Split PDF", rotatePdfTitle: "Rotate PDF", compressPdfTitle: "Compress PDF",
    comingSoon: "Coming soon", soon: "Soon", selectedTool: "SELECTED TOOL",
    widthLabel: "Width (px)", heightLabel: "Height (px)", qualityLabel: "Quality", degreesLabel: "Rotation",
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
const formatRow = document.querySelector("#format-row");
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
let currentFiles = [];
let currentOperation = "image.convert";
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
  if (operationTitles[currentOperation]) {
    const title = t(operationTitles[currentOperation]);
    document.querySelector("#converter-title").textContent = title;
    submitButton.querySelector("[data-i18n]").textContent = title;
  }
  updateFormatTarget();
}

function updateFormatTarget() {
  const format = outputFormat.value === "JPEG" ? "JPG" : outputFormat.value;
  formatTarget.textContent = format;
  formatTargetIcon.textContent = format;
}

const operationTitles = {
  "image.convert": "convertTitle",
  "image.resize": "resizeTitle",
  "image.compress": "compressImageTitle",
  "image.rotate": "rotateImageTitle",
};

function selectTool(operation) {
  currentOperation = operation;
  document.querySelectorAll("[data-tool]").forEach((tool) => {
    const selected = tool.dataset.tool === operation;
    tool.classList.toggle("active", selected);
    tool.setAttribute("aria-pressed", String(selected));
  });
  const title = t(operationTitles[operation]);
  document.querySelector("#converter-title").textContent = title;
  submitButton.querySelector("[data-i18n]").textContent = title;
  document.querySelector('[data-option="width"]').hidden = operation !== "image.resize";
  document.querySelector('[data-option="height"]').hidden = operation !== "image.resize";
  document.querySelector('[data-option="quality"]').hidden = operation !== "image.compress";
  document.querySelector('[data-option="degrees"]').hidden = operation !== "image.rotate";
  formatRow.hidden = operation === "image.rotate";
  fileInput.value = "";
  showFiles([]);
}

function formatBytes(size) {
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function showFiles(files) {
  currentFiles = Array.from(files || []);
  selectedFile.hidden = currentFiles.length === 0;
  dropZone.hidden = currentFiles.length > 0;
  if (currentFiles.length) {
    selectedName.textContent = currentFiles.map((file) => file.name).join(", ");
    const totalSize = currentFiles.reduce((sum, file) => sum + file.size, 0);
    selectedSize.textContent = `${currentFiles.length} · ${formatBytes(totalSize)}`;
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

fileInput.addEventListener("change", () => showFiles(fileInput.files));
document.querySelector("#remove-file").addEventListener("click", () => {
  fileInput.value = "";
  showFiles([]);
});
document.querySelectorAll("[data-tool]").forEach((tool) => {
  tool.addEventListener("click", () => selectTool(tool.dataset.tool));
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
dropZone.addEventListener("drop", (event) => showFiles(event.dataTransfer.files));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  if (!currentFiles.length) {
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
  const options = { format: outputFormat.value };
  if (currentOperation === "image.resize") {
    if (document.querySelector("#width").value) options.width = document.querySelector("#width").value;
    if (document.querySelector("#height").value) options.height = document.querySelector("#height").value;
  }
  if (currentOperation === "image.compress") options.quality = document.querySelector("#quality").value;
  if (currentOperation === "image.rotate") options.degrees = document.querySelector("#degrees").value;
  body.append("operation", currentOperation);
  body.append("options", JSON.stringify(options));
  currentFiles.forEach((file) => body.append("files", file, file.name));
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
  showFiles([]);
  jobStatus.hidden = true;
  jobResult.hidden = true;
  resetButton.hidden = true;
  jobSpinner.hidden = false;
  submitButton.disabled = false;
  clearError();
  updateFormatTarget();
  dropZone.scrollIntoView({ behavior: "smooth", block: "center" });
});

selectTool(currentOperation);
applyLanguage(currentLanguage);
