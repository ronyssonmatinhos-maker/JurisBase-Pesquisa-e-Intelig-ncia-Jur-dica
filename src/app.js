(function () {
  const form = document.querySelector('#search-form');
  const input = document.querySelector('#query');
  const error = document.querySelector('#search-error');
  const results = document.querySelector('#results');
  const count = document.querySelector('#result-count');
  const clearButton = document.querySelector('#clear-button');
  const filterButtons = Array.from(document.querySelectorAll('.filter-button'));
  let activeFilter = 'all';
  let activeQuery = '';

  function render(documents) {
    count.textContent = `${documents.length} ${documents.length === 1 ? 'fonte' : 'fontes'}`;

    if (documents.length === 0) {
      results.innerHTML = '<div class="empty-state"><span class="empty-mark" aria-hidden="true">⌕</span><h3>Nenhuma fonte encontrada</h3><p>Tente outros termos ou remova o filtro para ampliar a busca.</p></div>';
      return;
    }

    results.innerHTML = documents.map((document) => `
      <article class="result-item">
        <div class="result-type"><span class="type-marker" aria-hidden="true"></span>${escapeHTML(document.typeLabel)}</div>
        <div class="result-main">
          <p class="result-number">${escapeHTML(document.number)}</p>
          <h3>${escapeHTML(document.title)}</h3>
          <p class="result-summary">${escapeHTML(document.summary)}</p>
          <div class="result-meta"><span>${escapeHTML(document.category)}</span><span>${escapeHTML(document.jurisdiction)}</span></div>
        </div>
        <a class="source-link" href="${escapeAttribute(document.url)}" target="_blank" rel="noopener noreferrer" aria-label="Abrir ${escapeAttribute(document.title)} no ${escapeAttribute(document.source)}">Fonte oficial <span aria-hidden="true">↗</span></a>
      </article>
    `).join('');
  }

  function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[character]);
  }

  function escapeAttribute(value) {
    return escapeHTML(value);
  }

  function updateResults() {
    render(window.JurisSearch.searchDocuments(window.JURIS_DOCUMENTS, activeQuery, activeFilter));
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const validation = window.JurisSearch.validateQuery(input.value);

    if (!validation.valid) {
      error.textContent = validation.message;
      error.hidden = false;
      input.setAttribute('aria-invalid', 'true');
      input.focus();
      return;
    }

    error.hidden = true;
    input.removeAttribute('aria-invalid');
    activeQuery = input.value.trim();
    clearButton.hidden = false;
    updateResults();
  });

  input.addEventListener('input', () => {
    if (input.value.trim()) {
      error.hidden = true;
      input.removeAttribute('aria-invalid');
    }
  });

  clearButton.addEventListener('click', () => {
    input.value = '';
    activeQuery = '';
    clearButton.hidden = true;
    error.hidden = true;
    input.removeAttribute('aria-invalid');
    input.focus();
    updateResults();
  });

  filterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      activeFilter = button.dataset.filter;
      filterButtons.forEach((filterButton) => {
        const isActive = filterButton === button;
        filterButton.classList.toggle('is-active', isActive);
        filterButton.setAttribute('aria-pressed', String(isActive));
      });
      updateResults();
    });
  });

  updateResults();
})();