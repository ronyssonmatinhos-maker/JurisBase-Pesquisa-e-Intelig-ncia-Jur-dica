const test = require('node:test');
const assert = require('node:assert/strict');
const { normalize, validateQuery, searchDocuments } = require('../src/search.js');

const documents = [
  { title: 'Lei Geral de Proteção de Dados', summary: 'Tratamento de dados pessoais', number: '13.709/2018', type: 'legislacao', typeLabel: 'Lei federal', jurisdiction: 'Federal', category: 'Privacidade' },
  { title: 'Código de Processo Civil', summary: 'Processo civil brasileiro', number: '13.105/2015', type: 'legislacao', typeLabel: 'Lei federal', jurisdiction: 'Federal', category: 'Processo' },
];

test('normaliza acentos e diferenças de caixa', () => {
  assert.equal(normalize(' PROTEÇÃO de DADOS '), 'protecao de dados');
});

test('valida busca vazia, tamanho mínimo, máximo e entrada válida', () => {
  assert.equal(validateQuery('').valid, false);
  assert.match(validateQuery('a').message, /2 caracteres/);
  assert.match(validateQuery('x'.repeat(101)).message, /100 caracteres/);
  assert.equal(validateQuery('LGPD').valid, true);
});

test('busca sem diferenciar acentos e caixa, exigindo todos os termos', () => {
  assert.deepEqual(searchDocuments(documents, 'protecao dados').map((item) => item.number), ['13.709/2018']);
  assert.deepEqual(searchDocuments(documents, 'CÓDIGO PENAL'), []);
});

test('aplica filtro por tipo', () => {
  assert.deepEqual(searchDocuments(documents, 'processo', 'legislacao').map((item) => item.number), ['13.105/2015']);
  assert.deepEqual(searchDocuments(documents, 'processo', 'julgado'), []);
});