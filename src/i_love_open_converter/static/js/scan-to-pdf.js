const input = document.querySelector('#page-input');
const pagesElement = document.querySelector('#scan-pages');
const emptyState = document.querySelector('#empty-state');
const addButton = document.querySelector('#add-pages');
const submit = document.querySelector('#submit');
const message = document.querySelector('#message');
const download = document.querySelector('#download');
const language = document.querySelector('#language');
const strings = {
  'pt-BR': { page: 'Página', up: 'Subir página', down: 'Descer página', rotate: 'Girar página', remove: 'Remover página', empty: 'Adicione pelo menos uma página para criar o PDF.', queued: 'Na fila…', working: 'Criando seu PDF…', done: 'PDF pronto. Confira o resultado antes de usar.', error: 'Não foi possível criar o PDF. Confira as imagens e tente novamente.' },
  en: { page: 'Page', up: 'Move page up', down: 'Move page down', rotate: 'Rotate page', remove: 'Remove page', empty: 'Add at least one page to create a PDF.', queued: 'Queued…', working: 'Creating your PDF…', done: 'PDF ready. Review the result before using it.', error: 'Could not create the PDF. Check the images and try again.' },
};
let lang = localStorage.getItem('i-love-open-converter-language') === 'pt-BR' ? 'pt-BR' : 'en';
let pages = [];
let busy = false;

function localize() {
  language.value = lang;
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-pt][data-en]').forEach(element => {
    element.textContent = lang === 'en' ? element.dataset.en : element.dataset.pt;
  });
  pagesElement.setAttribute('aria-label', lang === 'en' ? 'Pages' : 'Páginas');
  render();
}

language.addEventListener('change', () => {
  lang = language.value;
  localStorage.setItem('i-love-open-converter-language', lang);
  localize();
});

input.addEventListener('change', () => {
  for (const file of input.files) pages.push({ file, rotation: 0, url: URL.createObjectURL(file) });
  input.value = '';
  invalidateResult();
  render();
});

addButton.addEventListener('click', () => input.click());

function render() {
  pagesElement.replaceChildren();
  pagesElement.hidden = pages.length === 0;
  emptyState.hidden = pages.length > 0;
  addButton.hidden = pages.length === 0;
  submit.disabled = busy || pages.length === 0;
  pages.forEach((page, index) => {
    const item = document.createElement('li');
    item.className = 'scan-page';
    const image = document.createElement('img');
    image.src = page.url;
    image.alt = `${strings[lang].page} ${index + 1}`;
    image.style.transform = `rotate(${page.rotation}deg)`;
    const info = document.createElement('span');
    info.className = 'scan-page-name';
    info.textContent = `${strings[lang].page} ${index + 1}: ${page.file.name}`;
    const controls = document.createElement('span');
    controls.className = 'scan-page-controls';
    const actions = [
      [strings[lang].up, '↑', () => move(index, -1), index === 0],
      [strings[lang].down, '↓', () => move(index, 1), index === pages.length - 1],
      [strings[lang].rotate, '↻', () => rotate(page), false],
      [strings[lang].remove, '×', () => remove(index), false],
    ];
    for (const [label, symbol, action, disabled] of actions) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = symbol;
      button.setAttribute('aria-label', label);
      button.title = label;
      button.disabled = busy || disabled;
      button.addEventListener('click', action);
      controls.append(button);
    }
    item.append(image, info, controls);
    pagesElement.append(item);
  });
}

function move(index, amount) {
  const target = index + amount;
  if (target < 0 || target >= pages.length) return;
  [pages[index], pages[target]] = [pages[target], pages[index]];
  invalidateResult();
  render();
}

function rotate(page) {
  page.rotation = (page.rotation + 90) % 360;
  invalidateResult();
  render();
}

function remove(index) {
  URL.revokeObjectURL(pages[index].url);
  pages.splice(index, 1);
  invalidateResult();
  render();
}

function invalidateResult() {
  message.textContent = '';
  download.hidden = true;
  download.removeAttribute('href');
}

submit.addEventListener('click', async () => {
  if (busy || pages.length === 0) {
    if (!pages.length) message.textContent = strings[lang].empty;
    return;
  }
  busy = true;
  language.disabled = true;
  input.disabled = true;
  addButton.disabled = true;
  download.hidden = true;
  render();
  const body = new FormData();
  body.append('operation', 'image.to_pdf');
  body.append('options', JSON.stringify({ rotations: pages.map(page => page.rotation) }));
  pages.forEach(page => body.append('files', page.file));
  try {
    const response = await fetch('/api/jobs', { method: 'POST', body });
    const job = await response.json();
    if (!response.ok) throw new Error();
    message.textContent = strings[lang].queued;
    while (true) {
      await new Promise(resolve => setTimeout(resolve, 900));
      const statusResponse = await fetch(job.status_url);
      const state = await statusResponse.json();
      if (!statusResponse.ok || state.state === 'failed') throw new Error();
      if (state.state === 'queued') message.textContent = strings[lang].queued;
      if (state.state === 'processing') message.textContent = strings[lang].working;
      if (state.state === 'succeeded') {
        download.href = state.download_url;
        download.hidden = false;
        message.textContent = strings[lang].done;
        break;
      }
    }
  } catch {
    message.textContent = strings[lang].error;
  } finally {
    busy = false;
    language.disabled = false;
    input.disabled = false;
    addButton.disabled = false;
    render();
  }
});

localize();
