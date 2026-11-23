const $ = selector => document.querySelector(selector);
const file = $('#file'), editor = $('#editor'), language = $('#language'), message = $('#message');
const preview = $('#preview'), selection = $('#edit-selection'), image = $('#image'), download = $('#download');
const controls = ['left','top','right','bottom'].map(id => $(`#${id}`));
const isSign = $('.pdf-tool').dataset.sign === 'true';
const canvas = $('#signature');
let lang = localStorage.getItem('i-love-open-converter-language') === 'pt-BR' ? 'pt-BR' : 'en';
let page = 1, count = 0, generation = 0, imageUrl = null, overlayUrl = null, drawn = false, previewReady = false;
const words = {'pt-BR':{loading:'Carregando prévia…',error:'Não foi possível processar o PDF. Confira o arquivo, a área e as opções.',invalid:'Preencha os campos e escolha uma área com largura e altura maiores que zero.',working:'Processando…',done:'Seu PDF está pronto.',page:'Página',of:'de',alt:'Prévia da página PDF',note:'Anotação'},en:{loading:'Loading preview…',error:'Could not process the PDF. Check the file, area and options.',invalid:'Complete the fields and choose an area with positive width and height.',working:'Processing…',done:'Your PDF is ready.',page:'Page',of:'of',alt:'PDF page preview',note:'Note'}};
function translate() { document.documentElement.lang = lang; language.value = lang; document.querySelectorAll('[data-pt][data-en]').forEach(el => {el.textContent = lang === 'en' ? el.dataset.en : el.dataset.pt;}); for (const [value,name] of Object.entries({helv:'DejaVu Sans',tiro:'DejaVu Serif',cour:'DejaVu Sans Mono'})) $(`#font option[value="${value}"]`).textContent = name; if (isSign) $('#submit').textContent = lang === 'en' ? 'Apply signature' : 'Aplicar assinatura'; preview.alt = words[lang].alt; showPage(); draw(); }
function showPage() { $('#page-label').textContent = `${words[lang].page} ${page} ${words[lang].of} ${count}`; $('#previous').disabled = page <= 1; $('#next').disabled = page >= count; }
language.addEventListener('change', () => {lang = language.value; localStorage.setItem('i-love-open-converter-language',lang); translate();});
function rectangle() { return controls.map(input => Number(input.value)); }
function draw() {
  const [left,top,right,bottom] = rectangle(), kind = $('#kind').value, color = $('#color').value;
  const valid = controls.every(el => el.validity.valid && el.value !== '') && left < right && top < bottom;
  selection.hidden = !valid; if (!valid) return false;
  Object.assign(selection.style,{left:`${left}%`,top:`${top}%`,width:`${right-left}%`,height:`${bottom-top}%`,borderColor:color,borderRadius:kind === 'shape' && $('#shape').value === 'ellipse' ? '50%' : '0',color});
  const text = $('#edit-preview-text'); text.textContent = ['text','note'].includes(kind) ? $('#text').value : '';
  text.style.fontFamily = {helv:'Converter Sans',tiro:'Converter Serif',cour:'Converter Mono'}[$('#font').value];
  text.style.fontSize = `${$('#font-size').value}px`;
  $('#edit-preview-image').hidden = kind !== 'image' || !overlayUrl;
  return true;
}
function mode() { const kind = $('#kind').value; $('#text-field').hidden = !['text','note'].includes(kind); $('#image-field').hidden = kind !== 'image'; $('#shape-field').hidden = kind !== 'shape'; $('#font-field').hidden = kind !== 'text'; $('#size-field').hidden = kind !== 'text'; draw(); }
editor.addEventListener('input', () => {download.hidden = true; mode();});
image.addEventListener('change', () => {if (overlayUrl) URL.revokeObjectURL(overlayUrl); if (canvas) {canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height); drawn = false;} overlayUrl = image.files.length ? URL.createObjectURL(image.files[0]) : null; $('#edit-preview-image').src = overlayUrl || ''; mode();});
if (canvas) {
  const context = canvas.getContext('2d'); context.strokeStyle = '#151515'; context.lineWidth = 3; context.lineCap = 'round';
  const point = event => {const bounds = canvas.getBoundingClientRect(); return [(event.clientX-bounds.left)*canvas.width/bounds.width,(event.clientY-bounds.top)*canvas.height/bounds.height];};
  canvas.addEventListener('pointerdown', event => {if (file.disabled) return; event.preventDefault(); download.hidden = true; image.value = ''; canvas.setPointerCapture(event.pointerId); const [x,y] = point(event); context.beginPath(); context.moveTo(x,y); context.lineTo(x+0.01,y); context.stroke(); drawn = true; overlayUrl = canvas.toDataURL('image/png'); $('#edit-preview-image').src = overlayUrl; mode();});
  canvas.addEventListener('pointermove', event => {if (!canvas.hasPointerCapture(event.pointerId)) return; const [x,y] = point(event); context.lineTo(x,y); context.stroke(); overlayUrl = canvas.toDataURL('image/png'); $('#edit-preview-image').src = overlayUrl; mode();});
  $('#clear-signature').addEventListener('click', () => {download.hidden = true; context.clearRect(0,0,canvas.width,canvas.height); drawn = false; overlayUrl = image.files.length ? URL.createObjectURL(image.files[0]) : null; $('#edit-preview-image').src = overlayUrl || ''; mode();});
}
async function showPreview(current) { message.textContent = words[lang].loading; previewReady = false; $('#submit').disabled = true; preview.parentElement.style.visibility = 'hidden'; const body = new FormData(); body.append('files',file.files[0]); body.append('page',String(page)); try {const response = await fetch('/api/pdf/preview',{method:'POST',body}); if (!response.ok) throw new Error(); const blob = await response.blob(); if (current !== generation) return; const nextUrl = URL.createObjectURL(blob); const nextImage = new Image(); nextImage.src = nextUrl; try {await nextImage.decode();} catch (error) {URL.revokeObjectURL(nextUrl); throw error;} if (current !== generation) {URL.revokeObjectURL(nextUrl); return;} if (imageUrl) URL.revokeObjectURL(imageUrl); imageUrl = nextUrl; preview.src = imageUrl; preview.parentElement.style.visibility = ''; previewReady = true; $('#submit').disabled = false; message.textContent = ''; showPage();} catch {if (current === generation) message.textContent = words[lang].error;} }
file.addEventListener('change', async () => {const current = ++generation; editor.hidden = true; download.hidden = true; page = 1; count = 0; if (imageUrl) {URL.revokeObjectURL(imageUrl); imageUrl = null; preview.removeAttribute('src');} if (!file.files.length) return; message.textContent = words[lang].loading; const body = new FormData(); body.append('files',file.files[0]); try {const response = await fetch('/api/pdf/pages',{method:'POST',body}); const data = await response.json(); if (!response.ok) throw new Error(); if (current !== generation) return; count = data.page_count; $('#filename').textContent = file.files[0].name; editor.hidden = false; mode(); await showPreview(current);} catch {if (current === generation) message.textContent = words[lang].error;} });
for (const [id,delta] of [['previous',-1],['next',1]]) $(`#${id}`).addEventListener('click', () => {download.hidden = true; page += delta; showPage(); showPreview(++generation);});
editor.addEventListener('submit', async event => {
  event.preventDefault(); if (!previewReady || file.disabled || $('#submit').disabled) return; const kind = $('#kind').value;
  if (!draw() || (['text','note'].includes(kind) && !$('#text').value.trim()) || (kind === 'image' && !image.files.length && !drawn) || (kind === 'text' && !$('#font-size').validity.valid)) {message.textContent = words[lang].invalid; return;}
  const options = {kind,page,rectangle:rectangle().map(n => n/100),color:$('#color').value,text:$('#text').value,font:$('#font').value,font_size:Number($('#font-size').value),shape:$('#shape').value};
  $('#submit').disabled = true;
  const body = new FormData(); body.append('files',file.files[0]); if (kind === 'image') {const signature = drawn ? await new Promise(resolve => canvas.toBlob(resolve,'image/png')) : image.files[0]; if (!signature) {message.textContent = words[lang].error; $('#submit').disabled = false; return;} body.append('files',signature,drawn ? 'signature.png' : signature.name);} body.append('operation',isSign ? 'pdf.sign' : 'pdf.edit'); body.append('options',JSON.stringify(options));
  file.disabled = true; language.disabled = true; editor.querySelectorAll('input,select,button').forEach(el => {el.disabled = true;}); download.hidden = true; message.textContent = words[lang].working;
  try {const response = await fetch('/api/jobs',{method:'POST',body}); const job = await response.json(); if (!response.ok) throw new Error(); while (true) {await new Promise(resolve => setTimeout(resolve,800)); const response = await fetch(job.status_url); const state = await response.json(); if (!response.ok || state.state === 'failed') throw new Error(); if (state.state === 'succeeded') {download.href = state.download_url; download.hidden = false; message.textContent = words[lang].done; break;}}} catch {message.textContent = words[lang].error;} finally {file.disabled = false; language.disabled = false; editor.querySelectorAll('input,select,button').forEach(el => {el.disabled = false;}); showPage();}
});
translate(); mode();
