const file = document.querySelector('#file');
const editor = document.querySelector('#editor');
const language = document.querySelector('#language');
const message = document.querySelector('#message');
const preview = document.querySelector('#preview');
const selection = document.querySelector('#crop-selection');
const download = document.querySelector('#download');
const pageLabel = document.querySelector('#page-label');
const submit = document.querySelector('#submit');
const ranges = document.querySelector('#ranges');
const controls = ['left','top','right','bottom'].map(id => document.querySelector(`#${id}`));
const aspectButtons = Array.from(document.querySelectorAll('.crop-aspect-btn'));
let lang = localStorage.getItem('i-love-open-converter-language') === 'pt-BR' ? 'pt-BR' : 'en';
let page = 1, count = 0, generation = 0, imageUrl = null, previewReady = false, pdfCropper = null, isSyncingCrop = false, activeAspectRatio = NaN;
const words = {'pt-BR':{loading:'Carregando prévia…',error:'Não foi possível processar o PDF. Confira o arquivo e as opções.',invalid:'A área deve ter largura e altura maiores que zero.',working:'Processando…',done:'Seu PDF está pronto.',page:'Página',of:'de',alt:'Prévia da página PDF'},en:{loading:'Loading preview…',error:'Could not process the PDF. Check the file and options.',invalid:'The area must have a positive width and height.',working:'Processing…',done:'Your PDF is ready.',page:'Page',of:'of',alt:'PDF page preview'}};
function translate() { document.documentElement.lang = lang; language.value = lang; document.querySelectorAll('[data-pt][data-en]').forEach(el => {el.textContent = lang === 'en' ? el.dataset.en : el.dataset.pt;}); preview.alt = words[lang].alt; showPageLabel(); }
function showPageLabel() { pageLabel.textContent = `${words[lang].page} ${page} ${words[lang].of} ${count}`; document.querySelector('#previous').disabled = page <= 1; document.querySelector('#next').disabled = page >= count; }
language.addEventListener('change', () => {lang = language.value; localStorage.setItem('i-love-open-converter-language',lang); translate();});
function rectangle() { return controls.map(input => Number(input.value)); }
function roundPct(value) { return Math.round(value * 10) / 10; }
function destroyCropper() { if (pdfCropper) { pdfCropper.destroy(); pdfCropper = null; } }
function draw() { const [left,top,right,bottom] = rectangle(); const valid = controls.every(el => el.validity.valid && el.value !== '') && left < right && top < bottom; selection.hidden = Boolean(pdfCropper) || !valid; if (valid && !pdfCropper) { selection.style.left = `${left}%`; selection.style.top = `${top}%`; selection.style.width = `${right-left}%`; selection.style.height = `${bottom-top}%`; } return valid; }
function syncInputsToCropper() {
  if (!pdfCropper) return;
  const [left, top, right, bottom] = rectangle();
  if (!controls.every(el => el.validity.valid && el.value !== '') || left >= right || top >= bottom) return;
  const imageData = pdfCropper.getImageData();
  if (!imageData?.naturalWidth || !imageData?.naturalHeight) return;
  isSyncingCrop = true;
  pdfCropper.setData({
    x: (left / 100) * imageData.naturalWidth,
    y: (top / 100) * imageData.naturalHeight,
    width: ((right - left) / 100) * imageData.naturalWidth,
    height: ((bottom - top) / 100) * imageData.naturalHeight,
  });
  isSyncingCrop = false;
}
function initCropper() {
  destroyCropper();
  if (typeof Cropper !== 'function') { draw(); return; }
  selection.hidden = true;
  pdfCropper = new Cropper(preview, {
    viewMode: 1,
    autoCropArea: 1,
    responsive: true,
    background: false,
    guides: true,
    movable: true,
    zoomable: false,
    scalable: false,
    rotatable: false,
    aspectRatio: activeAspectRatio,
    ready() { syncInputsToCropper(); },
    crop(event) {
      if (isSyncingCrop || !pdfCropper) return;
      const imageData = pdfCropper.getImageData();
      if (!imageData?.naturalWidth || !imageData?.naturalHeight) return;
      const l = Math.max(0, Math.min(99, roundPct((event.detail.x / imageData.naturalWidth) * 100)));
      const t = Math.max(0, Math.min(99, roundPct((event.detail.y / imageData.naturalHeight) * 100)));
      const r = Math.max(l + 0.1, Math.min(100, roundPct(((event.detail.x + event.detail.width) / imageData.naturalWidth) * 100)));
      const b = Math.max(t + 0.1, Math.min(100, roundPct(((event.detail.y + event.detail.height) / imageData.naturalHeight) * 100)));
      controls[0].value = String(l);
      controls[1].value = String(t);
      controls[2].value = String(r);
      controls[3].value = String(b);
      download.hidden = true;
    },
  });
}
controls.forEach(input => input.addEventListener('input', () => { if (pdfCropper) syncInputsToCropper(); else draw(); download.hidden = true; }));
aspectButtons.forEach(button => button.addEventListener('click', () => {
  const raw = button.dataset.cropAspect;
  activeAspectRatio = raw === 'free' ? NaN : Number(raw);
  aspectButtons.forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
  if (pdfCropper) pdfCropper.setAspectRatio(activeAspectRatio);
}));
ranges.addEventListener('input', () => {download.hidden = true;});
async function showPreview(current) {
  message.textContent = words[lang].loading; previewReady = false; submit.disabled = true; destroyCropper(); preview.parentElement.style.visibility = 'hidden';
  const body = new FormData(); body.append('files',file.files[0]); body.append('page',String(page));
  try { const response = await fetch('/api/pdf/preview',{method:'POST',body}); if (!response.ok) throw new Error(); const blob = await response.blob(); if (current !== generation) return; const nextUrl = URL.createObjectURL(blob); const nextImage = new Image(); nextImage.src = nextUrl; try {await nextImage.decode();} catch (error) {URL.revokeObjectURL(nextUrl); throw error;} if (current !== generation) {URL.revokeObjectURL(nextUrl); return;} if (imageUrl) URL.revokeObjectURL(imageUrl); imageUrl = nextUrl; preview.src = imageUrl; preview.parentElement.style.visibility = ''; previewReady = true; submit.disabled = false; message.textContent = ''; showPageLabel(); initCropper(); }
  catch { if (current === generation) message.textContent = words[lang].error; }
}
file.addEventListener('change', async () => {
  const current = ++generation; editor.hidden = true; download.hidden = true; count = 0; page = 1; destroyCropper();
  if (imageUrl) { URL.revokeObjectURL(imageUrl); imageUrl = null; preview.removeAttribute('src'); }
  if (!file.files.length) return;
  message.textContent = words[lang].loading; const body = new FormData(); body.append('files',file.files[0]);
  try { const response = await fetch('/api/pdf/pages',{method:'POST',body}); const data = await response.json(); if (!response.ok) throw new Error(); if (current !== generation) return; count = data.page_count; ranges.value = count === 1 ? '1' : `1-${count}`; document.querySelector('#filename').textContent = file.files[0].name; editor.hidden = false; draw(); await showPreview(current); }
  catch { if (current === generation) message.textContent = words[lang].error; }
});
for (const [id,delta] of [['previous',-1],['next',1]]) document.querySelector(`#${id}`).addEventListener('click', () => { page += delta; showPageLabel(); showPreview(++generation); });
editor.addEventListener('submit', async event => {
  event.preventDefault(); if (!previewReady || submit.disabled) return; if (!draw()) {message.textContent = words[lang].invalid; return;}
  const body = new FormData(); body.append('files',file.files[0]); body.append('operation','pdf.crop'); body.append('options',JSON.stringify({rectangle:rectangle().map(n => n/100),ranges:ranges.value}));
  const current = generation; submit.disabled = true; file.disabled = true; editor.querySelectorAll('input,button').forEach(el => {el.disabled = true;}); language.disabled = true; download.hidden = true; message.textContent = words[lang].working;
  try { const response = await fetch('/api/jobs',{method:'POST',body}); const job = await response.json(); if (!response.ok) throw new Error(); while (current === generation) { await new Promise(resolve => setTimeout(resolve,800)); const response = await fetch(job.status_url); const state = await response.json(); if (!response.ok || state.state === 'failed') throw new Error(); if (state.state === 'succeeded') {download.href = state.download_url; download.hidden = false; message.textContent = words[lang].done; break;} } }
  catch { message.textContent = words[lang].error; } finally { submit.disabled = false; file.disabled = false; language.disabled = false; editor.querySelectorAll('input,button').forEach(el => {el.disabled = false;}); showPageLabel(); }
});
translate();
