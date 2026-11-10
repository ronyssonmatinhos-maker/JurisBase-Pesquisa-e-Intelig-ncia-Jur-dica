(function (root) {
  const MIN_QUERY_LENGTH = 2;
  const MAX_QUERY_LENGTH = 100;

  function normalize(value) {
    return String(value)
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLocaleLowerCase('pt-BR')
      .trim();
  }

  function validateQuery(value) {
    const query = String(value ?? '').trim();

    if (!query) return { valid: false, message: 'Digite um termo para pesquisar.' };
    if (query.length < MIN_QUERY_LENGTH) return { valid: false, message: 'Digite pelo menos 2 caracteres.' };
    if (query.length > MAX_QUERY_LENGTH) return { valid: false, message: 'A busca deve ter no máximo 100 caracteres.' };
    return { valid: true, message: '' };
  }

  function searchDocuments(documents, query, filter = 'all') {
    const tokens = normalize(query).split(/\s+/).filter(Boolean);

    return documents.filter((document) => {
      if (filter !== 'all' && document.type !== filter) return false;
      const searchableText = normalize([
        document.title,
        document.summary,
        document.number,
        document.typeLabel,
        document.jurisdiction,
        document.category,
      ].join(' '));

      return tokens.every((token) => searchableText.includes(token));
    });
  }

  const api = { normalize, validateQuery, searchDocuments };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.JurisSearch = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);