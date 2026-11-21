const file = document.querySelector('#file'), form = document.querySelector('#form');
const language = document.querySelector('#language'), ocrLanguage = document.querySelector('#ocr-language');
const message = document.querySelector('#message'), download = document.querySelector('#download'), submit = document.querySelector('#submit');
let lang = localStorage.getItem('i-love-open-converter-language') === 'en' ? 'en' : 'pt-BR';
const words = {
  'pt-BR': {queued:'Na fila…',working:'Reconhecendo texto localmente…',done:'PDF pesquisável pronto. Revise o texto reconhecido.',noText:'Nenhum texto foi reconhecido. Confira a qualidade do documento.',error:'Não foi possível criar o PDF pesquisável. Confira o arquivo e tente novamente.'},
  en: {queued:'Queued…',working:'Recognizing text locally…',done:'Searchable PDF ready. Review the recognized text.',noText:'No text was recognized. Check the document quality.',error:'Could not create the searchable PDF. Check the file and try again.'}
};
function translate() {
  document.documentElement.lang = lang;
  language.value = lang;
  document.querySelectorAll('[data-pt][data-en]').forEach(el => {el.textContent = lang === 'en' ? el.dataset.en : el.dataset.pt;});
  for (const option of ocrLanguage.options) option.textContent = lang === 'en' ? option.dataset.en : option.dataset.pt;
}
language.addEventListener('change', () => {lang = language.value; localStorage.setItem('i-love-open-converter-language',lang); translate();});
file.addEventListener('change', () => {document.querySelector('#filename').textContent = file.files[0]?.name || ''; submit.disabled = !file.files.length; message.textContent = ''; download.hidden = true;});
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!file.files.length || submit.disabled) return;
  const body = new FormData();
  body.append('files', file.files[0]);
  body.append('operation', 'pdf.ocr');
  body.append('options', JSON.stringify({language: ocrLanguage.value}));
  file.disabled = true; language.disabled = true; ocrLanguage.disabled = true; submit.disabled = true;
  download.hidden = true; message.textContent = words[lang].working;
  try {
    const response = await fetch('/api/jobs', {method:'POST', body});
    const job = await response.json();
    if (!response.ok) throw new Error();
    message.textContent = words[lang].queued;
    while (true) {
      await new Promise(resolve => setTimeout(resolve, 900));
      const response = await fetch(job.status_url);
      const state = await response.json();
      if (!response.ok || state.state === 'failed') {
        if (state.error?.code === 'ocr_no_text') message.textContent = words[lang].noText;
        else message.textContent = words[lang].error;
        break;
      }
      if (state.state === 'queued') message.textContent = words[lang].queued;
      if (state.state === 'processing') message.textContent = words[lang].working;
      if (state.state === 'succeeded') {download.href = state.download_url; download.hidden = false; message.textContent = words[lang].done; break;}
    }
  } catch {message.textContent = words[lang].error;}
  finally {file.disabled = false; language.disabled = false; ocrLanguage.disabled = false; submit.disabled = !file.files.length;}
});
translate();
