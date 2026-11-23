const form = document.querySelector('#office-form'), file = document.querySelector('#office-file');
const submit = document.querySelector('#office-submit'), message = document.querySelector('#office-message');
const download = document.querySelector('#office-download'), language = document.querySelector('#language');
let lang = localStorage.getItem('i-love-open-converter-language') === 'pt-BR' ? 'pt-BR' : 'en';
let statusKey = null;
const words = {
  'pt-BR': {queued:'Na fila…', working:'Convertendo…', done:'Seu PDF está pronto.', failed:'Não foi possível converter o documento. Confira se ele é válido e não está protegido por senha.', unavailable:'Conversor indisponível. Confira o LibreOffice, o isolamento de rede e o suporte ao Landlock no worker.'},
  en: {queued:'Queued…', working:'Converting…', done:'Your PDF is ready.', failed:'Could not convert the document. Check that it is valid and not password-protected.', unavailable:'Converter unavailable. Check LibreOffice, network isolation and Landlock support in the worker.'},
};
function setStatus(key) { statusKey = key; message.textContent = key ? words[lang][key] : ''; }
function translate() {
  document.documentElement.lang = lang; language.value = lang;
  document.querySelectorAll('[data-pt][data-en]').forEach(el => { el.textContent = lang === 'en' ? el.dataset.en : el.dataset.pt; });
  setStatus(statusKey);
}
language.addEventListener('change', () => { lang = language.value; localStorage.setItem('i-love-open-converter-language',lang); translate(); });
file.addEventListener('change', () => { document.querySelector('#office-filename').textContent = file.files[0]?.name || ''; submit.disabled = !file.files.length; download.hidden = true; setStatus(null); });
form.addEventListener('submit', async event => {
  event.preventDefault(); if (!file.files.length || submit.disabled) return;
  const body = new FormData(); body.append('files',file.files[0]); body.append('operation',`office.${form.dataset.family}_to_pdf`);
  file.disabled = true; submit.disabled = true; download.hidden = true; setStatus('queued');
  try {
    const response = await fetch('/api/jobs',{method:'POST',body}); const job = await response.json();
    if (!response.ok) throw new Error('failed');
    while (true) {
      await new Promise(resolve => setTimeout(resolve,800));
      const response = await fetch(job.status_url); const state = await response.json();
      if (!response.ok || state.state === 'failed') throw new Error(state.error?.code || 'failed');
      if (state.state === 'queued') setStatus('queued');
      if (state.state === 'processing') setStatus('working');
      if (state.state === 'succeeded') { download.href = state.download_url; download.hidden = false; setStatus('done'); break; }
    }
  } catch (error) { setStatus(error.message === 'office_unavailable' ? 'unavailable' : 'failed'); }
  finally { file.disabled = false; submit.disabled = false; }
});
translate();
