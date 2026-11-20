const file = document.querySelector('#file'), password = document.querySelector('#password'), form = document.querySelector('#form');
const options = document.querySelector('#options'), message = document.querySelector('#message'), download = document.querySelector('#download'), language = document.querySelector('#language');
const action = document.querySelector('.pdf-tool').dataset.action;
let lang = localStorage.getItem('i-love-open-converter-language') === 'en' ? 'en' : 'pt-BR';
const words = {'pt-BR':{protect:'Proteger PDF',unlock:'Desbloquear PDF',invalid:'Informe uma senha de 1 a 40 bytes.',error:'Não foi possível processar o PDF. Confira o arquivo e a senha.',working:'Processando…',done:'Seu PDF está pronto.'},en:{protect:'Protect PDF',unlock:'Unlock PDF',invalid:'Enter a password of 1 to 40 bytes.',error:'Could not process the PDF. Check the file and password.',working:'Processing…',done:'Your PDF is ready.'}};
function translate() {document.documentElement.lang = lang; language.value = lang; document.querySelectorAll('[data-pt][data-en]').forEach(el => {el.textContent = lang === 'en' ? el.dataset.en : el.dataset.pt;}); document.querySelector('#submit').textContent = words[lang][action];}
language.addEventListener('change', () => {lang = language.value; localStorage.setItem('i-love-open-converter-language',lang); translate();});
file.addEventListener('change', () => {options.hidden = !file.files.length; document.querySelector('#filename').textContent = file.files[0]?.name || ''; password.value = ''; message.textContent = ''; download.hidden = true;});
password.addEventListener('input', () => {download.hidden = true;});
form.addEventListener('submit', async event => {
  event.preventDefault(); const bytes = new TextEncoder().encode(password.value).length; if (bytes < 1 || bytes > 40 || password.value.includes('\0')) {message.textContent = words[lang].invalid; return;}
  const body = new FormData(); body.append('files',file.files[0]); body.append('operation',`pdf.${action}`); body.append('password',password.value); password.value = '';
  file.disabled = true; password.disabled = true; language.disabled = true; document.querySelector('#submit').disabled = true; download.hidden = true; message.textContent = words[lang].working;
  try {const response = await fetch('/api/jobs',{method:'POST',body}); const job = await response.json(); if (!response.ok) throw new Error(); while (true) {await new Promise(resolve => setTimeout(resolve,800)); const response = await fetch(job.status_url); const state = await response.json(); if (!response.ok || state.state === 'failed') throw new Error(); if (state.state === 'succeeded') {download.href = state.download_url; download.hidden = false; message.textContent = words[lang].done; break;}}} catch {message.textContent = words[lang].error;} finally {file.disabled = false; password.disabled = false; language.disabled = false; document.querySelector('#submit').disabled = false;}
});
translate();
