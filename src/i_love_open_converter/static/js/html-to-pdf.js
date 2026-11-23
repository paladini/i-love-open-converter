const file = document.querySelector('#file'), form = document.querySelector('#form'), language = document.querySelector('#language');
const url = document.querySelector('#url'), fileMode = document.querySelector('#file-mode'), urlMode = document.querySelector('#url-mode');
const message = document.querySelector('#message'), download = document.querySelector('#download'), submit = document.querySelector('#submit');
let lang = localStorage.getItem('i-love-open-converter-language') === 'pt-BR' ? 'pt-BR' : 'en';
let statusKey = null;
const words = {
  'pt-BR': {
    capturing: 'Capturando a página pública…', queued: 'Na fila…', working: 'Convertendo HTML…', done: 'Seu PDF está pronto.',
    error: 'Não foi possível converter o HTML. Verifique o arquivo e os limites de processamento.',
    unavailable: 'A conversão exige um worker Linux com isolamento de rede e arquivos.',
    external: 'O HTML usa recursos externos. Incorpore imagens como data URI e tente novamente.'
  },
  en: {
    capturing: 'Capturing public page…', queued: 'Queued…', working: 'Converting HTML…', done: 'Your PDF is ready.',
    error: 'Could not convert the HTML. Check the file and processing limits.',
    unavailable: 'Conversion requires a Linux worker with network and filesystem isolation.',
    external: 'The HTML uses external resources. Embed images as data URIs and try again.'
  }
};
function setStatus(key) { statusKey = key; message.textContent = key ? words[lang][key] : ''; }
function translate() {
  document.documentElement.lang = lang;
  language.value = lang;
  document.querySelectorAll('[data-pt][data-en]').forEach(el => {
    el.textContent = lang === 'en' ? el.dataset.en : el.dataset.pt;
  });
  setStatus(statusKey);
}
language.addEventListener('change', () => {
  lang = language.value;
  localStorage.setItem('i-love-open-converter-language', lang);
  translate();
});
function selectedSource() { return document.querySelector('input[name="source-mode"]:checked').value; }
function updateSource() {
  const useUrl = selectedSource() === 'url';
  fileMode.hidden = useUrl;
  urlMode.hidden = !useUrl;
  file.required = !useUrl;
  url.required = useUrl;
  submit.disabled = useUrl ? !url.value.trim() : !file.files.length;
  setStatus(null);
  download.hidden = true;
}
document.querySelectorAll('input[name="source-mode"]').forEach(control => control.addEventListener('change', updateSource));
file.addEventListener('change', () => {
  document.querySelector('#filename').textContent = file.files[0]?.name || '';
  submit.disabled = selectedSource() === 'file' && !file.files.length;
  setStatus(null);
  download.hidden = true;
});
url.addEventListener('input', () => { if (selectedSource() === 'url') submit.disabled = !url.value.trim(); });
form.addEventListener('submit', async event => {
  event.preventDefault();
  const useUrl = selectedSource() === 'url';
  if ((useUrl ? !url.value.trim() : !file.files.length) || submit.disabled) return;
  const body = new FormData();
  if (useUrl) body.append('url', url.value.trim());
  else body.append('files', file.files[0]);
  body.append('operation', 'html.to_pdf');
  file.disabled = true;
  url.disabled = true;
  submit.disabled = true;
  download.hidden = true;
  setStatus(useUrl ? 'capturing' : 'queued');
  try {
    const response = await fetch('/api/jobs', {method: 'POST', body});
    const job = await response.json();
    if (!response.ok) throw new Error();
    while (true) {
      await new Promise(resolve => setTimeout(resolve, 800));
      const statusResponse = await fetch(job.status_url);
      const state = await statusResponse.json();
      if (!statusResponse.ok || state.state === 'failed') throw new Error(state.error?.code);
      if (state.state === 'queued') setStatus('queued');
      if (state.state === 'processing') setStatus('working');
      if (state.state === 'succeeded') {
        download.href = state.download_url;
        download.hidden = false;
        setStatus('done');
        break;
      }
    }
  } catch (error) {
    setStatus(error.message === 'html_unavailable' ? 'unavailable'
      : error.message === 'html_external_resource' ? 'external' : 'error');
  } finally {
    file.disabled = false;
    url.disabled = false;
    submit.disabled = selectedSource() === 'url' ? !url.value.trim() : !file.files.length;
  }
});
updateSource();
translate();
