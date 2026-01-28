// Metricas CAPES - Aplicacao JavaScript

let revistas = [];
let conferencias = [];
let abaAtual = 'revistas';

// Estado de ordenacao por aba
const ordenacao = {
    revistas: { coluna: null, direcao: 'asc' },
    conferencias: { coluna: null, direcao: 'asc' }
};

// Inicializacao
document.addEventListener('DOMContentLoaded', async () => {
    inicializarTema();
    await carregarDados();
    configurarEventos();
    renderizar();
});

// Inicializar tema baseado na preferencia salva ou do sistema
function inicializarTema() {
    const temaSalvo = localStorage.getItem('theme');
    if (temaSalvo) {
        document.documentElement.setAttribute('data-theme', temaSalvo);
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
}

// Alternar tema
function alternarTema() {
    const temaAtual = document.documentElement.getAttribute('data-theme');
    const novoTema = temaAtual === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', novoTema);
    localStorage.setItem('theme', novoTema);
}

// Carregar dados dos JSONs
async function carregarDados() {
    try {
        const [revistasRes, conferenciasRes] = await Promise.all([
            fetch('data/revistas.json'),
            fetch('data/conferencias.json')
        ]);

        if (revistasRes.ok) {
            revistas = await revistasRes.json();
        }

        if (conferenciasRes.ok) {
            conferencias = await conferenciasRes.json();
        }

        // Atualizar data de coleta
        atualizarDataColeta();
    } catch (error) {
        console.error('Erro ao carregar dados:', error);
    }
}

// Atualizar data de coleta no rodape
function atualizarDataColeta() {
    const dados = abaAtual === 'revistas' ? revistas : conferencias;
    if (dados.length > 0 && dados[0].data_coleta) {
        const data = new Date(dados[0].data_coleta);
        document.getElementById('data-atualizacao').textContent =
            `Ultima atualizacao: ${data.toLocaleDateString('pt-BR')}`;
    }
}

// Configurar eventos
function configurarEventos() {
    // Theme toggle
    document.getElementById('theme-toggle').addEventListener('click', alternarTema);

    // Abas
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            tab.classList.add('active');
            abaAtual = tab.dataset.tab;
            document.getElementById(`${abaAtual}-section`).classList.add('active');

            atualizarDataColeta();
            renderizar();
        });
    });

    // Busca
    document.getElementById('busca').addEventListener('input', renderizar);

    // Filtro de estrato
    document.getElementById('filtro-estrato').addEventListener('change', renderizar);

    // Ordenacao - headers clicaveis
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const coluna = th.dataset.sort;
            const estado = ordenacao[abaAtual];

            // Alternar direcao se mesma coluna, senao resetar para asc
            if (estado.coluna === coluna) {
                estado.direcao = estado.direcao === 'asc' ? 'desc' : 'asc';
            } else {
                estado.coluna = coluna;
                estado.direcao = 'asc';
            }

            atualizarIndicadoresOrdenacao();
            renderizar();
        });
    });
}

// Atualizar indicadores visuais de ordenacao nos headers
function atualizarIndicadoresOrdenacao() {
    const tabela = abaAtual === 'revistas' ? '#tabela-revistas' : '#tabela-conferencias';
    const estado = ordenacao[abaAtual];

    // Remover indicadores de todas as colunas
    document.querySelectorAll(`${tabela} th[data-sort]`).forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
    });

    // Adicionar indicador na coluna ativa
    if (estado.coluna) {
        const thAtivo = document.querySelector(`${tabela} th[data-sort="${estado.coluna}"]`);
        if (thAtivo) {
            thAtivo.classList.add(estado.direcao === 'asc' ? 'sort-asc' : 'sort-desc');
        }
    }
}

// Filtrar dados
function filtrarDados(dados) {
    const buscaRaw = document.getElementById('busca').value.toLowerCase().trim();
    const estrato = document.getElementById('filtro-estrato').value;

    // Suporta multiplos termos separados por virgula
    const termos = buscaRaw
        .split(',')
        .map(t => t.trim())
        .filter(t => t.length > 0);

    return dados.filter(item => {
        // Filtro de busca (OR entre termos)
        const matchBusca = termos.length === 0 || termos.some(termo =>
            item.sigla.toLowerCase().includes(termo) ||
            (item.nome_completo && item.nome_completo.toLowerCase().includes(termo)) ||
            (item.nome_gsm && item.nome_gsm.toLowerCase().includes(termo)) ||
            (item.issn && item.issn.toLowerCase().includes(termo))
        );

        // Filtro de estrato
        const estratoItem = abaAtual === 'revistas' ? item.estrato_final : item.estrato_capes;
        const matchEstrato = !estrato || estratoItem === estrato;

        return matchBusca && matchEstrato;
    });
}

// Ordenar dados
function ordenarDados(dados) {
    const estado = ordenacao[abaAtual];
    if (!estado.coluna) return dados;

    const copia = [...dados];
    const multiplicador = estado.direcao === 'asc' ? 1 : -1;

    copia.sort((a, b) => {
        let valorA = a[estado.coluna];
        let valorB = b[estado.coluna];

        // Tratar valores nulos
        if (valorA === null || valorA === undefined) valorA = '';
        if (valorB === null || valorB === undefined) valorB = '';

        // Ordenacao numerica
        if (typeof valorA === 'number' && typeof valorB === 'number') {
            return (valorA - valorB) * multiplicador;
        }

        // Ordenacao de strings
        return String(valorA).localeCompare(String(valorB), 'pt-BR') * multiplicador;
    });

    return copia;
}

// Renderizar tabela
function renderizar() {
    const dados = abaAtual === 'revistas' ? revistas : conferencias;
    let dadosFiltrados = filtrarDados(dados);
    dadosFiltrados = ordenarDados(dadosFiltrados);

    // Atualizar contador
    document.getElementById('contador').textContent =
        `${dadosFiltrados.length} de ${dados.length} resultados`;

    if (abaAtual === 'revistas') {
        renderizarRevistas(dadosFiltrados);
    } else {
        renderizarConferencias(dadosFiltrados);
    }

    atualizarIndicadoresOrdenacao();
    configurarLinhasExpansiveis();
}

// Configurar clique nas linhas para expandir/colapsar
function configurarLinhasExpansiveis() {
    document.querySelectorAll('tr.expandable').forEach(tr => {
        tr.addEventListener('click', (e) => {
            // Ignorar cliques em links
            if (e.target.tagName === 'A') return;

            const detailsRow = tr.nextElementSibling;
            if (detailsRow && detailsRow.classList.contains('details-row')) {
                tr.classList.toggle('expanded');
                detailsRow.classList.toggle('visible');
            }
        });
    });
}

// Formatar data
function formatarData(dataISO) {
    if (!dataISO) return '-';
    const data = new Date(dataISO);
    return data.toLocaleDateString('pt-BR') + ' ' + data.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

// Renderizar tabela de revistas
function renderizarRevistas(dados) {
    const tbody = document.querySelector('#tabela-revistas tbody');

    if (dados.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="empty-state">Nenhuma revista encontrada</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = dados.map((r, index) => `
        <tr class="expandable" data-index="${index}">
            <td><span class="expand-icon">+</span> ${escapeHtml(r.nome_completo || r.nome_gsm || '-')} <strong>(${escapeHtml(r.sigla)})</strong></td>
            <td>${r.h5_index || '-'}</td>
            <td>${r.citescore ? r.citescore.toFixed(1) : '-'}</td>
            <td>${r.percentil ? r.percentil.toFixed(0) + '%' : '-'}</td>
            <td><span class="estrato estrato-${r.estrato_final}">${r.estrato_final || '-'}</span></td>
        </tr>
        <tr class="details-row">
            <td colspan="5">
                <div class="details-content">
                    <div class="details-grid">
                        <div class="detail-group">
                            <h4>Identificacao</h4>
                            <p><strong>ISSN:</strong> ${escapeHtml(r.issn || '-')}</p>
                            <p><strong>Nome GSM:</strong> ${escapeHtml(r.nome_gsm || '-')}</p>
                            <div class="detail-links">
                                ${r.url_gsm ? `<a href="${r.url_gsm}" target="_blank">Google Scholar</a>` : ''}
                                ${r.url_scopus ? `<a href="${r.url_scopus}" target="_blank">Scopus</a>` : ''}
                                ${r.url_wos ? `<a href="${r.url_wos}" target="_blank">Web of Science</a>` : ''}
                            </div>
                        </div>
                        <div class="detail-group">
                            <h4>Google Scholar</h4>
                            <p><strong>H5-Index:</strong> ${r.h5_index || '-'}</p>
                            <p><strong>H5-Median:</strong> ${r.h5_median || '-'}</p>
                            <p><strong>Estrato H5:</strong> ${r.estrato_h5 ? `<span class="estrato estrato-${r.estrato_h5}">${r.estrato_h5}</span>` : '-'}</p>
                        </div>
                        <div class="detail-group">
                            <h4>Scopus</h4>
                            <p><strong>CiteScore:</strong> ${r.citescore ? r.citescore.toFixed(1) : '-'}</p>
                            <p><strong>Percentil:</strong> ${r.percentil ? r.percentil.toFixed(1) + '%' : '-'}</p>
                            <p><strong>Area Tematica:</strong> ${r.area_tematica || '-'}</p>
                            <p><strong>Estrato Percentil:</strong> ${r.estrato_percentil ? `<span class="estrato estrato-${r.estrato_percentil}">${r.estrato_percentil}</span>` : '-'}</p>
                        </div>
                        <div class="detail-group">
                            <h4>Web of Science</h4>
                            <p><strong>JIF:</strong> ${r.jif ? r.jif.toFixed(3) : '-'}</p>
                            <p><strong>Percentil JIF:</strong> ${r.jif_percentil ? r.jif_percentil.toFixed(1) + '%' : '-'}</p>
                            <p><strong>Categoria:</strong> ${escapeHtml(r.categoria_wos || '-')}</p>
                            <p><strong>Estrato JIF:</strong> ${r.estrato_jif ? `<span class="estrato estrato-${r.estrato_jif}">${r.estrato_jif}</span>` : '-'}</p>
                        </div>
                        <div class="detail-group">
                            <h4>Qualis 2020</h4>
                            <p><strong>Estrato:</strong> ${r.qualis_2020 ? `<span class="estrato estrato-${r.qualis_2020}">${r.qualis_2020}</span>` : '-'}</p>
                            <p class="info-note">Classificacao do quadrienio 2017-2020</p>
                        </div>
                        <div class="detail-group">
                            <h4>Classificacao Final</h4>
                            <p><strong>Estrato Final:</strong> ${r.estrato_final ? `<span class="estrato estrato-${r.estrato_final}">${r.estrato_final}</span>` : '-'}</p>
                            <p class="formula">
                                <code>MAX(${r.estrato_h5 || '-'}, ${r.estrato_percentil || '-'}, ${r.estrato_jif || '-'}) = ${r.estrato_final || '-'}</code>
                            </p>
                            <p class="info-note">Melhor estrato entre H5, Scopus e WoS</p>
                            <p><strong>Data de Coleta:</strong> ${formatarData(r.data_coleta)}</p>
                            ${r.erro ? `<p class="error"><strong>Erro:</strong> ${escapeHtml(r.erro)}</p>` : ''}
                        </div>
                    </div>
                </div>
            </td>
        </tr>
    `).join('');
}

// Renderizar tabela de conferencias
function renderizarConferencias(dados) {
    const tbody = document.querySelector('#tabela-conferencias tbody');

    if (dados.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">Nenhuma conferencia encontrada</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = dados.map((c, index) => `
        <tr class="expandable" data-index="${index}">
            <td><span class="expand-icon">+</span> <strong>${escapeHtml(c.sigla)}</strong></td>
            <td>${escapeHtml(c.nome_completo || c.nome_gsm || '-')}</td>
            <td>${c.h5_index || '-'}</td>
            <td>${c.h5_median || '-'}</td>
            <td><span class="estrato estrato-${c.estrato_capes}">${c.estrato_capes || '-'}</span></td>
            <td class="links" onclick="event.stopPropagation()">
                ${c.url_fonte ? `<a href="${c.url_fonte}" target="_blank">Scholar</a>` : ''}
            </td>
        </tr>
        <tr class="details-row">
            <td colspan="6">
                <div class="details-content">
                    <div class="details-grid">
                        <div class="detail-group">
                            <h4>Google Scholar Metrics</h4>
                            <p><strong>Nome GSM:</strong> ${escapeHtml(c.nome_gsm || '-')}</p>
                            <p><strong>H5-Index:</strong> ${c.h5_index || '-'}</p>
                            <p><strong>H5-Median:</strong> ${c.h5_median || '-'}</p>
                        </div>
                        <div class="detail-group">
                            <h4>Classificacao CAPES</h4>
                            <p><strong>Estrato:</strong> ${c.estrato_capes ? `<span class="estrato estrato-${c.estrato_capes}">${c.estrato_capes}</span>` : '-'}</p>
                            <p><strong>Data de Coleta:</strong> ${formatarData(c.data_coleta)}</p>
                            ${c.erro ? `<p class="error"><strong>Erro:</strong> ${escapeHtml(c.erro)}</p>` : ''}
                        </div>
                    </div>
                </div>
            </td>
        </tr>
    `).join('');
}

// Escapar HTML para prevenir XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
