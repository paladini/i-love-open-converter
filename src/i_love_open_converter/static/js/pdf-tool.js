const root = document.querySelector(".pdf-tool");
const tool = root.dataset.tool;
const isWatermark = tool === "watermark";
const form = document.querySelector("#pdf-tool-form");
const pdfInput = document.querySelector("#pdf-file");
const imageInput = document.querySelector("#watermark-image");
const uploadStep = document.querySelector("#upload-step");
const optionsStep = document.querySelector("#options-step");
const continueButton = document.querySelector("#continue-button");
const fileName = document.querySelector("#pdf-file-name");
const selectedPdf = document.querySelector("#selected-pdf");
const status = document.querySelector("#job-status");
const statusMessage = document.querySelector("#job-message");
const downloadLink = document.querySelector("#download-link");
const error = document.querySelector("#form-error");
const language = document.querySelector("#language");
let kind = "text";
let timer;
const strings = {
  "pt-BR": {continue:"Continuar",upload:"Selecionar arquivo PDF",drag:"ou arraste o arquivo PDF até aqui",text:"Texto",image:"Imagem",change:"Trocar arquivo",submitWatermark:"Adicionar marca d’água",submitNumbers:"Numerar páginas",queued:"Na fila…",processing:"Processando seu PDF…",done:"Seu PDF está pronto.",download:"Baixar PDF",selectImage:"Selecione uma imagem para a marca d’água.",invalid:"Não foi possível processar o arquivo.",failed:"O processamento falhou. Confira o arquivo e tente novamente.",fileType:"PDF · até {size} MB",mode:"Tipo de marca d’água",imageName:"Imagem selecionada: {name}",language:"Idioma",local:"Seus arquivos são processados no servidor que você controla.",allTools:"Todas as ferramentas",pageFormat:"Página 1 de total", bottomCenter:"Inferior central",bottomLeft:"Inferior esquerdo",bottomRight:"Inferior direito",topLeft:"Superior esquerdo",topCenter:"Superior central",topRight:"Superior direito",center:"Centro",centerLeft:"Centro esquerdo",centerRight:"Centro direito",top:"Superior",bottom:"Inferior",left:"esquerdo",right:"direito",centerPos:"central",opacity:"Opacidade",position:"Posição",format:"Formato",start:"Número inicial",font:"Fonte",size:"Tamanho",color:"Cor",watermarkText:"Texto da marca d’água",watermarkImage:"Imagem da marca d’água (PNG, JPG ou WebP)"},
  en: {continue:"Continue",upload:"Select PDF file",drag:"or drop the PDF file here",text:"Text",image:"Image",change:"Change file",submitWatermark:"Add watermark",submitNumbers:"Add page numbers",queued:"Queued…",processing:"Processing your PDF…",done:"Your PDF is ready.",download:"Download PDF",selectImage:"Choose an image for the watermark.",invalid:"The file could not be processed.",failed:"Processing failed. Check the file and try again.",fileType:"PDF · up to {size} MB",mode:"Watermark type",imageName:"Selected image: {name}",language:"Language",local:"Your files are processed on the server you control.",allTools:"All tools",pageFormat:"Page 1 of total",bottomCenter:"Bottom center",bottomLeft:"Bottom left",bottomRight:"Bottom right",topLeft:"Top left",topCenter:"Top center",topRight:"Top right",center:"Center",centerLeft:"Center left",centerRight:"Center right",top:"Top",bottom:"Bottom",left:"left",right:"right",centerPos:"center",opacity:"Opacity",position:"Position",format:"Format",start:"Starting number",font:"Font",size:"Size",color:"Color",watermarkText:"Watermark text",watermarkImage:"Watermark image (PNG, JPG, or WebP)"},
};
let lang = localStorage.getItem("i-love-open-converter-language") === "en" ? "en" : "pt-BR";
function t(key) { return strings[lang][key] || key; }
function localize() {
  document.documentElement.lang = lang;
  language.value = lang;
  document.querySelectorAll("[data-pt][data-en]").forEach((el) => { el.textContent = lang === "en" ? el.dataset.en : el.dataset.pt; });
  const suffix = lang === "en" ? "en" : "pt";
  const toolKey = tool === "page-numbers" ? "pageNumbers" : "watermark";
  document.querySelector("#tool-title").textContent = document.querySelector("#tool-title").dataset[`${toolKey}${suffix === "en" ? "En" : "Pt"}`];
  document.querySelector("#tool-description").textContent = document.querySelector("#tool-description").dataset[`${toolKey}${suffix === "en" ? "En" : "Pt"}`];
  document.querySelector("#upload-title").textContent = t("upload");
  document.querySelector("#upload-note").textContent = t("drag");
  document.querySelector("#continue-button").textContent = t("continue");
  document.querySelector("#back-button").textContent = t("change");
  document.querySelector("#submit-button").textContent = isWatermark ? t("submitWatermark") : t("submitNumbers");
  document.querySelector(".local-note").textContent = t("local");
  document.querySelector(".breadcrumbs a").textContent = t("allTools");
  if (isWatermark) {
    document.querySelectorAll(".mode-button").forEach((button) => button.textContent = button.dataset.kind === "text" ? t("text") : t("image"));
    document.querySelector(".mode-switch").setAttribute("aria-label", t("mode"));
  }
  document.querySelectorAll(".pdf-options label > span").forEach((el) => { const key = lang === "en" ? "en" : "pt"; if (el.dataset[key]) el.textContent = el.dataset[key]; });
  for (const option of document.querySelectorAll("#position option")) {
    const key = option.value.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
    option.textContent = t(key) || option.textContent;
  }
  const pageFormat = document.querySelector('#number-format option[value="page_number_total"]');
  if (pageFormat) pageFormat.textContent = lang === "en" ? "Page 1 of total" : "Página 1 de total";
  if (downloadLink.href && !downloadLink.hidden) downloadLink.textContent = t("download");
}
language.value = lang;
language.addEventListener("change", () => { lang = language.value; localStorage.setItem("i-love-open-converter-language", lang); localize(); });
localize();
pdfInput.addEventListener("change", () => {
  const file = pdfInput.files[0];
  continueButton.disabled = !file;
  fileName.hidden = !file;
  fileName.textContent = file ? file.name : "";
});
const pdfDropZone = document.querySelector(".pdf-upload");
for (const name of ["dragenter", "dragover"]) pdfDropZone.addEventListener(name, (event) => {
  event.preventDefault();
  pdfDropZone.classList.add("dragover");
});
for (const name of ["dragleave", "drop"]) pdfDropZone.addEventListener(name, (event) => {
  event.preventDefault();
  pdfDropZone.classList.remove("dragover");
});
pdfDropZone.addEventListener("drop", (event) => {
  const pdf = Array.from(event.dataTransfer.files).find((file) => file.name.toLowerCase().endsWith(".pdf"));
  if (!pdf) return;
  const transfer = new DataTransfer();
  transfer.items.add(pdf);
  pdfInput.files = transfer.files;
  pdfInput.dispatchEvent(new Event("change", {bubbles:true}));
});
continueButton.addEventListener("click", () => {
  if (!pdfInput.files.length) return;
  selectedPdf.textContent = pdfInput.files[0].name;
  uploadStep.hidden = true;
  optionsStep.hidden = false;
});
document.querySelector("#back-button").addEventListener("click", () => {
  uploadStep.hidden = false;
  optionsStep.hidden = true;
  status.hidden = true;
  clearInterval(timer);
});
if (isWatermark) {
  document.querySelectorAll(".mode-button").forEach((button) => button.addEventListener("click", () => {
    kind = button.dataset.kind;
    document.querySelectorAll(".mode-button").forEach((item) => item.classList.toggle("active", item === button));
    document.querySelector("#text-options").hidden = kind !== "text";
    document.querySelector("#watermark-image-field").hidden = kind !== "image";
    document.querySelector("#image-picked").hidden = !imageInput.files.length || kind !== "image";
    document.querySelector("#watermark-text").required = kind === "text";
    document.querySelector("#watermark-image").required = kind === "image";
  }));
  imageInput.addEventListener("change", () => {
    const image = imageInput.files[0];
    document.querySelector("#image-picked").hidden = !image;
    document.querySelector("#image-picked-name").textContent = image ? image.name : "";
  });
  document.querySelector("#remove-watermark-image").addEventListener("click", () => {
    imageInput.value = "";
    document.querySelector("#image-picked").hidden = true;
  });
  document.querySelector("#opacity").addEventListener("input", (event) => document.querySelector("#opacity-value").value = `${Math.round(Number(event.target.value) * 100)}%`);
}
function makeOptions() {
  if (isWatermark) {
    const options = { kind, position: document.querySelector("#position").value, opacity: Number(document.querySelector("#opacity").value) };
    if (kind === "text") Object.assign(options, {text:document.querySelector("#watermark-text").value,font:document.querySelector("#font").value,font_size:Number(document.querySelector("#font-size").value),color:document.querySelector("#color").value});
    return options;
  }
  return {position:document.querySelector("#position").value,format:document.querySelector("#number-format").value,start:Number(document.querySelector("#start").value),font:document.querySelector("#font").value,font_size:Number(document.querySelector("#font-size").value),color:document.querySelector("#color").value,language:lang};
}
async function poll(url) {
  try {
    const response = await fetch(url);
    const job = await response.json();
    if (!response.ok || job.state === "failed") throw new Error(job.error?.code || "failed");
    if (job.state === "queued") statusMessage.textContent = t("queued");
    else if (job.state === "processing") statusMessage.textContent = t("processing");
    else if (job.state === "succeeded") {
      clearInterval(timer);
      statusMessage.textContent = t("done");
      downloadLink.href = job.download_url;
      downloadLink.textContent = t("download");
      downloadLink.hidden = false;
    }
  } catch (e) {
    clearInterval(timer);
    statusMessage.textContent = e.message === "invalid_file" ? t("invalid") : t("failed");
  }
}
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.hidden = true;
  if (isWatermark && kind === "image" && !imageInput.files.length) { error.textContent = t("selectImage"); error.hidden = false; return; }
  const body = new FormData();
  body.append("operation", isWatermark ? "pdf.watermark" : "pdf.page_numbers");
  body.append("options", JSON.stringify(makeOptions()));
  body.append("files", pdfInput.files[0], pdfInput.files[0].name);
  if (isWatermark && kind === "image") body.append("files", imageInput.files[0], imageInput.files[0].name);
  status.hidden = false;
  statusMessage.textContent = t("queued");
  downloadLink.hidden = true;
  document.querySelector("#submit-button").disabled = true;
  try {
    const response = await fetch("/api/jobs", {method:"POST",body});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error?.code || "failed");
    await poll(payload.status_url);
    timer = setInterval(() => poll(payload.status_url), 800);
  } catch {
    statusMessage.textContent = t("failed");
  } finally {
    document.querySelector("#submit-button").disabled = false;
  }
});
