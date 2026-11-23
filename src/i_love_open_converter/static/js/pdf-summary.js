const file = document.querySelector('#file');
const form = document.querySelector('#form');
const language = document.querySelector('#language');
const submit = document.querySelector('#submit');
const message = document.querySelector('#message');
const download = document.querySelector('#download');
const filename = document.querySelector('#filename');
let lang = localStorage.getItem('i-love-open-converter-language') === 'pt-BR' ? 'pt-BR' : 'en';
const words = {
  'pt-BR': { queued: 'Na fila…', working: 'Gerando resumo com o modelo local…', done: 'Resumo pronto. Confira os detalhes no PDF original.', noText: 'Este PDF não tem texto selecionável. Use OCR PDF e tente novamente.', tooLarge: 'Este PDF excede o limite do resumo local.', error: 'Não foi possível gerar o resumo. Confira o arquivo e tente novamente.' },
  en: { queued: 'Queued…', working: 'Generating a summary with the local model…', done: 'Summary ready. Verify details against the source PDF.', noText: 'This PDF has no selectable text. Run PDF OCR and try again.', tooLarge: 'This PDF exceeds the local summary limit.', error: 'Could not create the summary. Check the file and try again.' },
};

function translate() {
  language.value = lang;
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-pt][data-en]').forEach(element => {
    element.textContent = lang === 'en' ? element.dataset.en : element.dataset.pt;
  });
}

language.addEventListener('change', () => {
  lang = language.value;
  localStorage.setItem('i-love-open-converter-language', lang);
  translate();
});

file.addEventListener('change', () => {
  filename.textContent = file.files[0]?.name || '';
  submit.disabled = !file.files.length;
  message.textContent = '';
  download.hidden = true;
  download.removeAttribute('href');
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!file.files.length || submit.disabled) return;
  const body = new FormData();
  body.append('files', file.files[0]);
  body.append('operation', 'pdf.summary');
  body.append('options', '{}');
  file.disabled = true;
  language.disabled = true;
  submit.disabled = true;
  download.hidden = true;
  message.textContent = words[lang].working;
  try {
    const response = await fetch('/api/jobs', { method: 'POST', body });
    const job = await response.json();
    if (!response.ok) {
      const code = job.error?.code || job.detail?.error?.code;
      if (code === 'summary_too_large') throw new Error('tooLarge');
      throw new Error();
    }
    message.textContent = words[lang].queued;
    while (true) {
      await new Promise(resolve => setTimeout(resolve, 900));
      const statusResponse = await fetch(job.status_url);
      const state = await statusResponse.json();
      if (!statusResponse.ok || state.state === 'failed') {
        if (state.error?.code === 'summary_no_text') throw new Error('noText');
        if (state.error?.code === 'summary_too_large') throw new Error('tooLarge');
        throw new Error();
      }
      if (state.state === 'queued') message.textContent = words[lang].queued;
      if (state.state === 'processing') message.textContent = words[lang].working;
      if (state.state === 'succeeded') {
        download.href = state.download_url;
        download.hidden = false;
        message.textContent = words[lang].done;
        break;
      }
    }
  } catch (error) {
    message.textContent = words[lang][error.message] || words[lang].error;
  } finally {
    file.disabled = false;
    language.disabled = false;
    submit.disabled = !file.files.length;
  }
});

translate();
