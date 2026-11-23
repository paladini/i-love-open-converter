const file = document.querySelector('#file');
const form = document.querySelector('#form');
const language = document.querySelector('#language');
const ocr = document.querySelector('#ocr');
const ocrLanguage = document.querySelector('#ocr-language');
const ocrLanguageControl = document.querySelector('#ocr-language-control');
const message = document.querySelector('#message');
const download = document.querySelector('#download');
const submit = document.querySelector('#submit');
let lang = localStorage.getItem('i-love-open-converter-language') === 'pt-BR' ? 'pt-BR' : 'en';
let statusKey = null;

const words = {
  'pt-BR': {
    queued: 'Na fila…', working: 'Convertendo…', done: 'Seu documento Word está pronto.',
    error: 'Não foi possível converter o PDF. Confira o arquivo e os limites de processamento.',
    unavailable: 'A conversão exige um worker Linux isolado da rede.',
    ocrFailed: 'Não foi possível reconhecer o texto neste PDF. Confira a qualidade do arquivo.',
    pageLimit: 'O OCR aceita PDFs com até 20 páginas.',
  },
  en: {
    queued: 'Queued…', working: 'Converting…', done: 'Your Word document is ready.',
    error: 'Could not convert the PDF. Check the file and processing limits.',
    unavailable: 'Conversion requires a network-isolated Linux worker.',
    ocrFailed: 'Could not recognize text in this PDF. Check the file quality.',
    pageLimit: 'OCR supports PDFs with up to 20 pages.',
  },
};

function setStatus(key) {
  statusKey = key;
  message.textContent = key ? words[lang][key] : '';
}

function translate() {
  document.documentElement.lang = lang;
  language.value = lang;
  document.querySelectorAll('[data-pt][data-en]').forEach((element) => {
    element.textContent = lang === 'en' ? element.dataset.en : element.dataset.pt;
  });
  [...ocrLanguage.options].forEach((option, index) => {
    const labels = lang === 'en'
      ? ['English', 'Portuguese', 'Portuguese + English']
      : ['Inglês', 'Português', 'Português + inglês'];
    option.textContent = labels[index];
  });
  setStatus(statusKey);
}

function setBusy(busy) {
  file.disabled = busy;
  ocr.disabled = busy;
  ocrLanguage.disabled = busy;
  submit.disabled = busy || !file.files.length;
}

language.addEventListener('change', () => {
  lang = language.value;
  localStorage.setItem('i-love-open-converter-language', lang);
  translate();
});

ocr.addEventListener('change', () => {
  ocrLanguageControl.hidden = !ocr.checked;
});

file.addEventListener('change', () => {
  document.querySelector('#filename').textContent = file.files[0]?.name || '';
  submit.disabled = !file.files.length;
  setStatus(null);
  download.hidden = true;
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!file.files.length || submit.disabled) return;

  const body = new FormData();
  body.append('files', file.files[0]);
  body.append('operation', 'pdf.to_word');
  if (ocr.checked) {
    body.append('options', JSON.stringify({ ocr: true, language: ocrLanguage.value }));
  }

  setBusy(true);
  download.hidden = true;
  setStatus('queued');
  try {
    const response = await fetch('/api/jobs', { method: 'POST', body });
    const job = await response.json();
    if (!response.ok) {
      const code = job.detail?.error?.code || job.error?.code;
      throw new Error(code || 'request_failed');
    }
    while (true) {
      await new Promise((resolve) => setTimeout(resolve, 800));
      const response = await fetch(job.status_url);
      const state = await response.json();
      if (!response.ok || state.state === 'failed') {
        throw new Error(state.error?.code || 'conversion_failed');
      }
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
    const code = error.message;
    setStatus(code === 'word_unavailable' ? 'unavailable'
      : code === 'ocr_failed' ? 'ocrFailed'
        : code === 'page_limit_exceeded' ? 'pageLimit' : 'error');
  } finally {
    setBusy(false);
  }
});

translate();
