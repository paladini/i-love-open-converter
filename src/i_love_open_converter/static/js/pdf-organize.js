const primary = document.querySelector('#primary');
const secondary = document.querySelector('#secondary');
const editor = document.querySelector('#editor');
const list = document.querySelector('#pages');
const message = document.querySelector('#message');
const download = document.querySelector('#download');
const submit = document.querySelector('#submit');
const language = document.querySelector('#language');
let lang = localStorage.getItem('i-love-open-converter-language') === 'en' ? 'en' : 'pt-BR';
let pages = [];
let files = [];
let revision = 0;
const words = { 'pt-BR': {page:'Página',up:'Subir',down:'Descer',remove:'Remover',loading:'Lendo PDF…',error:'Não foi possível ler ou processar o PDF. Confira os arquivos e tente novamente.',empty:'Mantenha pelo menos uma página.',queued:'Processando…',done:'Seu PDF está pronto.'}, en:{page:'Page',up:'Move up',down:'Move down',remove:'Remove',loading:'Reading PDF…',error:'Could not read or process the PDF. Check your files and try again.',empty:'Keep at least one page.',queued:'Processing…',done:'Your PDF is ready.'} };
function localize() {
  language.value = lang; document.documentElement.lang = lang;
  document.querySelectorAll('[data-pt][data-en]').forEach(el => { el.textContent = lang === 'en' ? el.dataset.en : el.dataset.pt; });
  render();
}
language.addEventListener('change', () => { lang = language.value; localStorage.setItem('i-love-open-converter-language', lang); localize(); });
function render() {
  list.replaceChildren();
  pages.forEach((page, index) => {
    const li = document.createElement('li');
    const label = document.createElement('span'); label.textContent = `${files[page[0]-1].name} — ${words[lang].page} ${page[1]} `; li.append(label);
    for (const [key, delta] of [['up',-1],['down',1],['remove',0]]) {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = words[lang][key];
      button.setAttribute('aria-label', `${words[lang][key]} ${label.textContent}`);
      button.disabled = (delta === -1 && index === 0) || (delta === 1 && index === pages.length - 1);
      button.addEventListener('click', () => {
        const nextIndex = delta ? index + delta : Math.min(index, pages.length - 2);
        if (delta) [pages[index],pages[nextIndex]] = [pages[nextIndex],pages[index]];
        else pages.splice(index,1);
        download.hidden = true; message.textContent = ''; render();
        const row = list.children[nextIndex];
        const nextButton = row?.querySelectorAll('button')[delta ? (delta < 0 ? 0 : 1) : 2];
        if (nextButton && !nextButton.disabled) nextButton.focus();
        else row?.querySelector('button:not(:disabled)')?.focus();
      });
      li.append(button);
    }
    list.append(li);
  });
}
async function addFile(file, isPrimary) {
  const current = ++revision;
  if (isPrimary) { files = []; pages = []; secondary.value = ''; editor.hidden = true; render(); }
  if (!file) return;
  message.textContent = words[lang].loading; submit.disabled = true; download.hidden = true;
  const body = new FormData(); body.append('files',file);
  try {
    const response = await fetch('/api/pdf/pages',{method:'POST',body}); const result = await response.json();
    if (!response.ok) throw new Error();
    if (current !== revision) return;
    if (!isPrimary) { pages = pages.filter(p => p[0] === 1); files = files.slice(0,1); }
    files.push(file); for (let n=1;n<=result.page_count;n++) pages.push([files.length,n]);
    editor.hidden = false; message.textContent = ''; render();
  } catch { if (current === revision) { message.textContent = words[lang].error; if (!isPrimary) secondary.value = ''; } }
  finally { if (current === revision) submit.disabled = false; }
}
primary.addEventListener('change', () => addFile(primary.files[0],true));
secondary.addEventListener('change', () => addFile(secondary.files[0],false));
submit.addEventListener('click', async () => {
  if (!pages.length) { message.textContent = words[lang].empty; return; }
  const body = new FormData(); body.append('operation','pdf.organize'); body.append('options',JSON.stringify({pages})); files.forEach(file => body.append('files',file));
  submit.disabled = true; primary.disabled = true; secondary.disabled = true; language.disabled = true;
  list.querySelectorAll('button').forEach(button => { button.disabled = true; });
  download.hidden = true; message.textContent = words[lang].queued;
  try {
    const response = await fetch('/api/jobs',{method:'POST',body}); const job = await response.json(); if (!response.ok) throw new Error();
    while (true) { await new Promise(resolve => setTimeout(resolve,800)); const result = await fetch(job.status_url); const state = await result.json(); if (!result.ok || state.state === 'failed') throw new Error(); if (state.state === 'succeeded') { download.href = state.download_url; download.hidden = false; message.textContent = words[lang].done; break; } }
  } catch { message.textContent = words[lang].error; } finally { submit.disabled = false; primary.disabled = false; secondary.disabled = false; language.disabled = false; render(); }
});
localize();
