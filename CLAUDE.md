# CAPES Metrics Collector - Documentação Técnica

## Visão Geral

Sistema automatizado para coleta de métricas de periódicos científicos e conferências acadêmicas, desenvolvido para apoiar o processo de avaliação CAPES (Coordenação de Aperfeiçoamento de Pessoal de Nível Superior) conforme o **Procedimento 2 - Área de Computação 2025-2028**.

O projeto foi criado através de uma conversa com Claude.ai para automatizar a coleta de dados bibliométricos necessários para classificação de publicações científicas em estratos (A1-A8).

### O que o projeto faz automaticamente

✅ **Conferências**: Coleta H5-index do Google Scholar e calcula estrato inicial (Etapa 1)
❌ **Conferências**: Ajuste CE-SBC (Top10/Top20) requer consulta manual à SBC
✅ **Periódicos**: Coleta H5-index do Google Scholar e calcula estrato inicial
✅ **Periódicos**: Coleta JIF do Web of Science (opcional, via API com --wos)
✅ **Periódicos**: Coleta CiteScore do Scopus (opcional, via API com --scopus)

### Lista de Verificação para Uso Completo

- [x] Executar script para coletar H5-index de conferências e revistas
- [x] (Opcional) Configurar WOS_API_KEY em .env e usar --wos para coletar JIF
- [x] (Opcional) Configurar SCOPUS_API_KEY em .env e usar --scopus para coletar CiteScore
- [ ] Consultar rankings CE-SBC (eventos@sbc.org.br) e aplicar ajustes +1/+2 nas conferências
- [ ] Validar resultados manualmente (matching pode ser imperfeito)

## Contexto e Objetivo

### Propósito

A CAPES utiliza métricas bibliométricas para classificar periódicos e conferências em estratos de qualidade (A1 a A8). Este projeto automatiza a coleta dessas métricas de fontes públicas:

- **Conferências**: H5-index do Google Scholar Metrics (automático)
- **Periódicos**:
  - H5-index do Google Scholar Metrics (automático)
  - CiteScore (Scopus) - coleta automática via API (opcional com --scopus)
  - JIF (Web of Science) - coleta automática via API (opcional com --wos)
  - **Regra**: Usar o **MAIOR** percentil entre CiteScore e JIF

### Documentos de Referência CAPES

O sistema implementa as regras definidas nos seguintes documentos oficiais:

- `COMPUTACAO_DOCAREA_2025_2028.pdf` - Documento de Área da Computação
- `COMPUTACAO_FICHA_2025_2028.pdf` - Ficha de Avaliação
- `19052025_20250502_DocumentoReferencial_FICHA_pages_*.pdf` - Diretrizes Comuns
- `13052025_antoniogomes06maiodav.pdf` - Novas Diretrizes 2025

### Classificação CAPES

O sistema implementa as regras de estratificação definidas pela área de Computação:

#### Conferências (processo em 2 etapas)

**Etapa 1 - Classificação inicial por H5-index**:
```
A1: >= 35  |  A5: >= 12
A2: >= 25  |  A6: >= 9
A3: >= 20  |  A7: >= 6
A4: >= 15  |  A8: > 0
```

**Etapa 2 - Ajuste CE-SBC** (Comissão Especial da SBC):
- **Top10**: +2 níveis (saturação em A3)
- **Top20**: +1 nível (saturação em A3)
- **Relevante**: mantém estrato do H5-index
- Sem H5 mas **Top**: recebe A7
- Sem H5 mas **Relevante**: recebe A8

**Critério Tradição SBC**:
- 20+ anos de existência: pode ser classificado como A4
- 10+ anos de existência: pode ser classificado como A5

> **Nota**: O script atual implementa apenas a Etapa 1. O ajuste CE-SBC requer consulta manual aos rankings da SBC (ver seção "Contatos Úteis").

#### Periódicos (baseado no Percentil)
```
A1: >= 87.5%  |  A5: >= 37.5%
A2: >= 75.0%  |  A6: >= 25.0%
A3: >= 62.5%  |  A7: >= 12.5%
A4: >= 50.0%  |  A8: < 12.5%
```

**Métricas aceitas**:
- **CiteScore** (Scopus) - percentil na categoria
- **JIF** (Journal Impact Factor, Web of Science) - percentil na categoria
- **Regra**: Usar o **MAIOR** percentil entre as duas fontes

> **Nota**: O script suporta coleta automática de CiteScore (--scopus) e JIF (--wos). Ambos requerem API keys configuradas no arquivo .env.

## Estrutura do Projeto

```
coleta_capes/
│
├── capes_metrics.py          # Script principal (orquestração e CLI)
├── lib_aux.py                # Biblioteca auxiliar (dataclasses, funções de estrato)
├── lib_google.py             # Scraper Google Scholar Metrics (H5-index)
├── lib_scopus.py             # Cliente Scopus API (CiteScore)
├── lib_wos.py                # Cliente Web of Science API (JIF)
├── requirements.txt          # Dependências Python
├── README.md                 # Documentação de uso
├── CLAUDE.md                 # Esta documentação técnica
├── LICENSE                   # Licença do projeto
├── .gitignore               # Configuração Git
│
├── config/                   # Arquivos de configuração
│   ├── conferencias.csv     # Lista de conferências a consultar
│   └── revistas.csv         # Lista de periódicos a consultar
│
└── output/                   # Resultados gerados (não versionados)
    ├── conferencias_YYYYMMDD_HHMMSS.csv
    ├── conferencias_YYYYMMDD_HHMMSS.json
    ├── revistas_YYYYMMDD_HHMMSS.csv
    └── revistas_YYYYMMDD_HHMMSS.json
```

## Arquitetura e Componentes

O projeto foi refatorado em módulos para melhor organização e manutenibilidade:

### Módulos do Projeto

| Módulo | Arquivo | Responsabilidade |
|--------|---------|-----------------|
| Auxiliar | `lib_aux.py` | Dataclasses, funções de cálculo de estrato, constantes |
| Google Scholar | `lib_google.py` | Scraper para H5-index |
| Scopus | `lib_scopus.py` | Cliente API Scopus (CiteScore) |
| Web of Science | `lib_wos.py` | Cliente API WoS (JIF) |
| Principal | `capes_metrics.py` | CLI, orquestração, I/O |

### 1. Módulo Auxiliar (`lib_aux.py`)

Contém estruturas de dados e funções compartilhadas.

#### Constantes
```python
DELAY_MIN = 5   # Delay mínimo entre requisições (segundos)
DELAY_MAX = 10  # Delay máximo entre requisições (segundos)
HEADERS = {...}  # User-Agent e headers HTTP
```

#### `ConferenciaMetrics` (dataclass)
```python
@dataclass
class ConferenciaMetrics:
    sigla: str                      # Ex: "NeurIPS"
    nome_completo: Optional[str]    # Nome original da lista
    nome_gsm: Optional[str]         # Nome encontrado no GSM
    h5_index: Optional[int]         # Métrica H5-index
    h5_median: Optional[int]        # Métrica H5-median
    estrato_capes: Optional[str]    # A1-A8 calculado
    url_fonte: Optional[str]        # URL do Google Scholar
    erro: Optional[str]             # Mensagem de erro (se houver)
    data_coleta: Optional[str]      # Timestamp ISO
```

#### `RevistaMetrics` (dataclass)
```python
@dataclass
class RevistaMetrics:
    sigla: str                          # Ex: "TGRS"
    nome_completo: str                  # Nome completo
    issn: Optional[str]                 # ISSN (formato: XXXX-XXXX)
    nome_gsm: Optional[str]             # Nome encontrado no GSM
    h5_index: Optional[int]             # Métrica H5-index (GSM)
    h5_median: Optional[int]            # Métrica H5-median (GSM)
    estrato_h5: Optional[str]           # A1-A8 baseado em H5-index
    citescore: Optional[float]          # Métrica CiteScore (Scopus)
    percentil: Optional[float]          # Percentil (0-100, Scopus)
    area_tematica: Optional[str]        # Área do Scopus
    estrato_percentil: Optional[str]    # A1-A8 baseado em percentil
    jif: Optional[float]                # Journal Impact Factor (WoS)
    jif_percentil: Optional[float]      # Percentil JIF (0-100, WoS)
    categoria_wos: Optional[str]        # Categoria WoS
    estrato_jif: Optional[str]          # A1-A8 baseado em JIF
    estrato_final: Optional[str]        # Melhor estrato entre todos
    url_gsm: Optional[str]              # URL do Google Scholar
    url_scopus: Optional[str]           # URL do Scopus
    url_wos: Optional[str]              # URL do Web of Science
    erro: Optional[str]                 # Mensagem de erro
    data_coleta: Optional[str]          # Timestamp ISO
```

#### Funções de Cálculo de Estrato
```python
calcular_estrato_conferencia(h5_index: int) -> str
calcular_estrato_revista(percentil: float) -> str
calcular_estrato_final(estrato_h5, estrato_percentil, estrato_jif) -> str
```
Implementam as regras de estratificação CAPES com validação de entrada.

### 2. Módulo Google Scholar (`lib_google.py`)

#### `GoogleScholarMetricsScraper`
**Responsabilidade**: Coleta automática de H5-index de conferências e revistas

**Métodos**:
- `_delay()`: Implementa rate limiting randomizado
- `_buscar_venue_gsm(query)`: Método genérico de busca no GSM
- `buscar_conferencia(sigla, nome_completo)`: Busca métricas de conferência
- `buscar_revista(sigla, nome_completo, issn)`: Busca métricas de revista

**Fluxo**:
1. Aguarda delay aleatório (anti-bloqueio)
2. Monta query de busca (prioritiza nome completo)
3. Faz requisição GET ao Google Scholar Metrics
4. Detecta CAPTCHA/bloqueio
5. Parseia HTML com BeautifulSoup
6. Extrai primeira linha da tabela de resultados
7. Captura H5-index, H5-median e nome GSM
8. Calcula estrato CAPES
9. Retorna objeto `ConferenciaMetrics` ou `RevistaMetrics`

**Tratamento de Erros**:
- Bloqueio CAPTCHA
- Timeout de rede
- Ausência de resultados
- Parsing inválido

### 3. Módulo Scopus (`lib_scopus.py`)

#### `ScopusAPIClient`
**Responsabilidade**: Coleta de CiteScore e percentil via Scopus API (pybliometrics)

**Métodos**:
- `_delay()`: Rate limiting para API
- `_mask_api_key(key)`: Mascara chave para logs
- `buscar_revista_scopus(issn, nome)`: Busca métricas por ISSN

**Requisitos**:
- API key de https://dev.elsevier.com/myapikey.html
- Biblioteca `pybliometrics` instalada

**Retorno**: `(citescore, percentil, area_tematica, url_scopus, erro)`

### 4. Módulo Web of Science (`lib_wos.py`)

#### `WebOfScienceAPIClient`
**Responsabilidade**: Coleta de JIF e percentil via WoS Starter API

**Métodos**:
- `_delay()`: Rate limiting para API (5000 req/mês)
- `_mask_api_key(key)`: Mascara chave para logs
- `buscar_revista_wos(issn, nome)`: Busca JIF por ISSN

**Requisitos**:
- API key de https://developer.clarivate.com/portal
- Free tier: 5000 requisições/mês

**Retorno**: `(jif, jif_percentil, categoria_wos, url_wos, erro)`

### 5. Script Principal (`capes_metrics.py`)

#### Configuração Global
- **`BASE_DIR`**: Diretório raiz do projeto
- **`CONFIG_DIR`**: Pasta com listas de conferências/revistas
- **`OUTPUT_DIR`**: Pasta de saída dos resultados

#### Carregamento de Configuração
```python
carregar_conferencias(filepath: Path) -> List[Dict]
carregar_revistas(filepath: Path) -> List[Dict]
```
- Lê arquivos CSV com formato customizado
- Ignora linhas em branco e comentários (#)
- Valida formato esperado

#### Saída de Resultados
```python
salvar_csv(resultados, filepath, colunas)
salvar_json(resultados, filepath)
imprimir_tabela_conferencias(resultados)
imprimir_tabela_revistas(resultados)
```
- Cria diretórios automaticamente
- Formato CSV com headers
- JSON indentado (UTF-8)
- Tabelas formatadas no console

### 6. CLI (Command-Line Interface)

Implementado com `argparse`:

```bash
# Coleta tudo (conferências + revistas com H5-index)
python capes_metrics.py

# Apenas conferências
python capes_metrics.py --conferencias

# Apenas revistas (H5-index apenas)
python capes_metrics.py --revistas

# Revistas com JIF do Web of Science (requer WOS_API_KEY em .env)
python capes_metrics.py --revistas --wos

# Revistas com CiteScore do Scopus (requer SCOPUS_API_KEY em .env)
python capes_metrics.py --revistas --scopus

# Revistas com todas as métricas (H5 + JIF + CiteScore)
python capes_metrics.py --revistas --wos --scopus

# Customizar diretórios
python capes_metrics.py --output ./resultados --config ./minhas_listas
```

## Funcionamento Detalhado

### Fluxo de Execução

```
┌─────────────────────────────────────────┐
│ 1. Parse argumentos CLI                 │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┴──────────────┐
    │                           │
    ▼                           ▼
┌─────────────────┐    ┌─────────────────┐
│ 2a. Conferências│    │ 2b. Revistas    │
└────────┬────────┘    └────────┬────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│ 3. Carrega CSV  │    │ 3. Carrega CSV  │
└────────┬────────┘    └────────┬────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│ 4. Scrape GSM   │    │ 4. Gera Template│
│    (automático) │    │    (manual)     │
└────────┬────────┘    └────────┬────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│ 5. Calcula      │    │ 5. Instrui      │
│    Estrato      │    │    Usuário      │
└────────┬────────┘    └────────┬────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│ 6. Salva        │    │ 6. Salva        │
│    CSV + JSON   │    │    Template CSV │
└────────┬────────┘    └────────┬────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
          ┌─────────────────┐
          │ 7. Exibe Resumo │
          └─────────────────┘
```

### Coleta de Conferências (Automática)

1. **Preparação**
   - Carrega [config/conferencias.csv](config/conferencias.csv)
   - Inicializa sessão HTTP com headers customizados

2. **Para cada conferência**
   - Aguarda 5-10s (rate limiting)
   - Busca no Google Scholar Metrics
   - Extrai H5-index da primeira linha da tabela
   - Calcula estrato automaticamente
   - Loga progresso no console

3. **Finalização**
   - Salva [output/conferencias_TIMESTAMP.csv](output/)
   - Salva [output/conferencias_TIMESTAMP.json](output/)
   - Exibe tabela resumida

#### Fluxo Completo de Classificação de Conferências

```
Conferência → [Etapa 1] → [Etapa 2] → Estrato Final
                  ↓            ↓
            H5-index    Ranking CE-SBC
              (GSM)      (Manual)

Exemplo 1: ICSE
  H5-index: 42 → A1 (inicial)
  CE-SBC: Top10 → +2 níveis → A1 (saturado em A3, mas já é A1)
  Estrato Final: A1

Exemplo 2: SBES
  H5-index: 18 → A3 (inicial)
  CE-SBC: Relevante → mantém → A3
  Critério Tradição: 30+ anos → pode ser A4
  Estrato Final: A3 ou A4 (decisão da área)

Exemplo 3: Workshop Regional
  H5-index: 3 → A8 (inicial)
  CE-SBC: Não listado → mantém → A8
  Estrato Final: A8
```

> **Importante**: O script atual calcula apenas o estrato da **Etapa 1** (H5-index). A aplicação dos ajustes CE-SBC e critérios de tradição deve ser feita manualmente.

### Coleta de Periódicos (Automática)

**Coleta Automática**:
- H5-index do Google Scholar Metrics (sempre)
- CiteScore do Scopus (se flag --scopus ativada e SCOPUS_API_KEY configurada)
- JIF do Web of Science (se flag --wos ativada e WOS_API_KEY configurada)

**Workflow automatizado**:

1. **Configurar APIs (Opcional)**

   **Web of Science**:
   - Obter API key em: https://developer.clarivate.com/portal
   - Free tier: 5000 requisições/mês

   **Scopus**:
   - Obter API key em: https://dev.elsevier.com/myapikey.html
   - Requer conta institucional ou registro gratuito

   Criar arquivo `.env` na raiz do projeto:
   ```bash
   WOS_API_KEY=sua_chave_wos_aqui
   SCOPUS_API_KEY=sua_chave_scopus_aqui
   ```

2. **Executar Coleta Automática**
   ```bash
   # Apenas H5-index
   python capes_metrics.py --revistas

   # H5-index + JIF (requer WOS_API_KEY)
   python capes_metrics.py --revistas --wos

   # H5-index + CiteScore (requer SCOPUS_API_KEY)
   python capes_metrics.py --revistas --scopus

   # Todas as métricas (requer ambas as keys)
   python capes_metrics.py --revistas --wos --scopus
   ```

3. **Cálculo do Estrato Final**
   - Calcula automaticamente o melhor estrato entre H5, CiteScore e JIF
   - Exibe na coluna `estrato_final` do CSV/JSON
   - Usa a regra CAPES: maior percentil = melhor classificação

**Formato do CSV de Saída**:
```csv
sigla,nome_completo,issn,nome_gsm,h5_index,h5_median,estrato_h5,citescore,percentil,area_tematica,estrato_percentil,url_gsm,url_scopus,erro,data_coleta
TGRS,IEEE Trans...,0196-2892,IEEE Transactions...,85,105,A1,[PREENCHER],[PREENCHER],[PREENCHER],,[URL_GSM],[PREENCHER],,2026-01-26...
```

## Tecnologias Utilizadas

### Dependências Python

```python
requests>=2.28.0        # HTTP client
beautifulsoup4>=4.11.0  # HTML parsing
python-dotenv>=1.0.0    # Environment variables
pybliometrics>=3.5.0    # Scopus API client (para --scopus)
```

**Bibliotecas padrão**:
- `csv`: Leitura/escrita de CSVs
- `json`: Serialização JSON
- `argparse`: Interface CLI
- `pathlib`: Manipulação de caminhos
- `datetime`: Timestamps
- `dataclasses`: Estruturas de dados
- `typing`: Type hints
- `time`, `random`: Rate limiting

### Fontes de Dados

#### Fontes Utilizadas

| Fonte | URL Base | Métrica | Acesso |
|-------|----------|---------|--------|
| Google Scholar Metrics | https://scholar.google.com | H5-index | HTTP GET (HTML) |
| Scopus API | https://api.elsevier.com | CiteScore + Percentil | REST API (--scopus) |
| Web of Science Starter API | https://api.clarivate.com/api/wos-starter | JIF + Percentil | REST API (--wos) |
| CE-SBC Rankings | eventos@sbc.org.br | Top10/Top20/Relevante | Consulta por email |

#### Fontes Descartadas

- **OpenAlex** (https://openalex.org): Não fornece CiteScore nem JIF oficiais (apenas métricas proprietárias similares, não aceitas pela CAPES)

## Como Usar

### Instalação

```bash
# Clonar repositório
git clone <repo-url>
cd coleta_capes

# Instalar dependências
pip install -r requirements.txt
```

### Configuração

#### Adicionar Conferências

Editar [config/conferencias.csv](config/conferencias.csv):
```csv
# Formato: sigla,nome_completo
ICSE,International Conference on Software Engineering
FSE,Foundations of Software Engineering
```

#### Adicionar Periódicos

Editar [config/revistas.csv](config/revistas.csv):
```csv
# Formato: sigla,nome_completo,issn
TOSEM,ACM Transactions on Software Engineering and Methodology,1049-331X
JSS,Journal of Systems and Software,0164-1212
```

### Execução

```bash
# Coleta completa (H5-index apenas)
python capes_metrics.py

# Apenas conferências
python capes_metrics.py --conferencias

# Apenas periódicos (H5-index apenas)
python capes_metrics.py --revistas

# Periódicos com JIF do Web of Science (requer .env com WOS_API_KEY)
python capes_metrics.py --revistas --wos
```

### Fluxo de Trabalho Recomendado

#### Para Conferências

1. **Preparar lista** em [config/conferencias.csv](config/conferencias.csv)
2. **Executar coleta**:
   ```bash
   python capes_metrics.py --conferencias
   ```
3. **Validar resultados** em `output/conferencias_TIMESTAMP.csv`
   - Verificar se o nome encontrado (coluna `nome_gsm`) corresponde à conferência desejada
   - Anotar H5-index e estrato inicial (Etapa 1)

4. **Consultar CE-SBC**:
   - Enviar email para eventos@sbc.org.br solicitando rankings atuais
   - Identificar quais conferências são Top10/Top20/Relevante

5. **Aplicar ajustes manualmente**:
   - Top10: +2 níveis (máximo A3)
   - Top20: +1 nível (máximo A3)
   - Conferências com 20+ anos: considerar A4
   - Conferências com 10+ anos: considerar A5

6. **Documentar estrato final** em planilha própria

#### Para Periódicos

1. **Preparar lista** em [config/revistas.csv](config/revistas.csv) com ISSN

2. **(Opcional) Configurar Web of Science**:
   - Obter chave em https://developer.clarivate.com/portal
   - Criar `.env` com `WOS_API_KEY=sua_chave`

3. **Executar coleta automática**:
   ```bash
   # Apenas H5-index
   python capes_metrics.py --revistas

   # H5-index + JIF
   python capes_metrics.py --revistas --wos
   ```

4. **Validar resultados** em `output/revistas_TIMESTAMP.csv`
   - Verificar se o nome encontrado (coluna `nome_gsm`) corresponde à revista desejada
   - Anotar H5-index e estrato inicial (coluna `estrato_h5`)
   - Se usou --wos, verificar JIF coletado (coluna `jif`) e estrato WoS (coluna `estrato_wos`)

5. **Coletar CiteScore/Percentil manualmente**:
   - Abrir o arquivo CSV gerado (`output/revistas_TIMESTAMP.csv`)
   - Acessar https://www.scopus.com/sources
   - Para cada revista, buscar por nome ou ISSN
   - Anotar CiteScore, Percentil e Subject Area
   - Preencher as colunas: `citescore`, `percentil`, `area_tematica`, `url_scopus`

6. **Calcular estrato final**:
   - Comparar `estrato_h5`, `estrato_percentil` e `estrato_wos` (se disponível)
   - Usar o **melhor** estrato entre as três métricas

7. **Validar** contra documentos CAPES

### Interpretação dos Resultados

#### Arquivo CSV de Conferências
```csv
sigla,nome_completo,nome_gsm,h5_index,h5_median,estrato_capes,url_fonte,erro,data_coleta
NeurIPS,Conference on Neural Information Processing Systems,Neural Information Processing Systems,298,402,A1,https://scholar.google.com/...,null,2026-01-26T15:03:12
```

#### Arquivo JSON de Conferências
```json
[
  {
    "sigla": "NeurIPS",
    "nome_completo": "Conference on Neural Information Processing Systems",
    "nome_gsm": "Neural Information Processing Systems",
    "h5_index": 298,
    "h5_median": 402,
    "estrato_capes": "A1",
    "url_fonte": "https://scholar.google.com/...",
    "erro": null,
    "data_coleta": "2026-01-26T15:03:12"
  }
]
```

#### Arquivo CSV de Revistas
```csv
sigla,nome_completo,issn,nome_gsm,h5_index,h5_median,estrato_h5,citescore,percentil,area_tematica,estrato_percentil,url_gsm,url_scopus,erro,data_coleta
TGRS,IEEE Transactions on Geoscience and Remote Sensing,0196-2892,IEEE Transactions on Geoscience and Remote Sensing,85,105,A1,,,,,https://scholar.google.com/...,,,2026-01-26T15:03:12
```

#### Arquivo JSON de Revistas
```json
[
  {
    "sigla": "TGRS",
    "nome_completo": "IEEE Transactions on Geoscience and Remote Sensing",
    "issn": "0196-2892",
    "nome_gsm": "IEEE Transactions on Geoscience and Remote Sensing",
    "h5_index": 85,
    "h5_median": 105,
    "estrato_h5": "A1",
    "citescore": null,
    "percentil": null,
    "area_tematica": null,
    "estrato_percentil": null,
    "url_gsm": "https://scholar.google.com/...",
    "url_scopus": null,
    "erro": null,
    "data_coleta": "2026-01-26T15:03:12"
  }
]
```

## Limitações Conhecidas

### Técnicas

1. **Rate Limiting do Google Scholar**
   - Bloqueio CAPTCHA após ~20-30 requisições consecutivas
   - Solução: Delay de 5-10s entre requests + aguardar alguns minutos se bloqueado
   - **Importante**: Script foi desenvolvido em ambiente com restrições. Teste localmente antes de usar em produção!

2. **Matching Imperfeito**
   - Busca retorna primeira correspondência do Google Scholar
   - Pode não ser exatamente a conferência ou revista desejada
   - Solução: Validação manual dos resultados (verificar coluna `nome_gsm`)

3. **Scopus API**
   - Requer API key de https://dev.elsevier.com
   - Busca por ISSN (nome não suportado)
   - Alternativa: coleta manual via https://www.scopus.com/sources

4. **WoS API Free Tier**
   - Limite: 5000 requisições/mês
   - Erro 429 se excedido
   - Solução: Aguardar reset mensal ou adquirir plano pago

5. **Segurança de Credenciais**
   - API keys armazenadas em .env (não versionado)
   - Máscaramento em logs (mostra apenas últimos 4 caracteres)
   - Nunca commitar .env no git

6. **Sem Histórico de Métricas**
   - Coleta snapshot do momento atual
   - Não rastreia mudanças temporais
   - Google Scholar atualiza anualmente

### Documentação CAPES

7. **Ajustes CE-SBC**
   - Rankings Top10/Top20/Relevante não incluídos automaticamente
   - Requer consulta por email: eventos@sbc.org.br
   - Ajuste manual do estrato final (+1 ou +2 níveis)
   - Critério de tradição SBC (10+/20+ anos) também manual

8. **Critérios Qualitativos**
   - Sistema não considera critérios subjetivos
   - Avaliação humana ainda necessária

## Detalhes Técnicos

### Parsing HTML (Google Scholar)

**Seletores CSS utilizados**:
```python
tabela = soup.find("table", {"id": "gsc_mvt_table"})
linha = tabela.find("tr", {"class": "gsc_mvt_row"})
celula_nome = linha.find("td", {"class": "gsc_mvt_t"})
celula_h5 = linha.find("td", {"class": "gsc_mvt_n"})
```

**Estrutura esperada**:
```html
<table id="gsc_mvt_table">
  <tr class="gsc_mvt_row">
    <td class="gsc_mvt_t">
      <a href="/citations?...">Nome da Conferência</a>
    </td>
    <td class="gsc_mvt_n">
      <a>298</a> <!-- H5-index -->
      <a>402</a> <!-- H5-median -->
    </td>
  </tr>
</table>
```

### Anti-Bloqueio

**Estratégias implementadas**:
- User-Agent realista (Mozilla/5.0)
- Delay randomizado entre requests
- Detecção de CAPTCHA via palavras-chave
- Session reuse (mantém cookies)

**Não implementado** (possíveis melhorias):
- Proxy rotation
- Headless browser
- IP rotation via VPN

### Cálculo de Estrato

**Conferências** (lógica em cascata):
```python
if h5_index >= 35: return "A1"
elif h5_index >= 25: return "A2"
# ... (demais faixas)
elif h5_index > 0: return "A8"
else: return "N/C"  # Não classificado
```

**Periódicos** (baseado em percentil):
```python
if percentil >= 87.5: return "A1"
elif percentil >= 75.0: return "A2"
# ... (faixas de 12.5%)
```

## Próximos Passos e Pendências

### Curto Prazo

- [ ] Testar script localmente (Google Scholar pode estar bloqueado em alguns ambientes)
- [ ] Preencher template de revistas com dados do Scopus Preview
- [ ] Obter rankings CE-SBC (contatar eventos@sbc.org.br)
- [ ] Implementar leitura de templates de revistas preenchidos
- [ ] Validar formato de ISSN (regex: `\d{4}-\d{3}[\dX]`)
- [ ] Adicionar modo `--dry-run` (simulação sem requests)
- [ ] Exportar relatório consolidado PDF/Excel

### Médio Prazo

- [ ] Implementar cálculo de ajuste CE-SBC no script
- [x] Adicionar suporte a Scopus API (via pybliometrics)
- [ ] Cache local de resultados (SQLite/JSON)
- [ ] Comparação com coletas anteriores (diff)
- [ ] Interface web (Flask/FastAPI + dashboard)
- [x] Adicionar suporte a Web of Science (JIF)

### Longo Prazo

- [ ] Sistema de cadastro de artigos por usuário
- [ ] Cálculo de métricas agregadas do programa de pós-graduação
- [ ] Machine learning para validação de matching
- [ ] Sistema de notificações (mudanças em estratos)
- [ ] Multi-threading para coleta paralela
- [ ] Dockerfile para deploy containerizado
- [ ] Deploy online (GitHub Pages, Vercel, etc.)

## Histórico de Desenvolvimento

### Versão 1.3 (2026-01-27)

**Atualização**: Refatoração modular e integração com Scopus API

#### Melhorias Implementadas

- ✅ Refatoração do código em módulos separados para melhor organização
- ✅ Novo módulo `lib_aux.py` com dataclasses e funções de cálculo
- ✅ Novo módulo `lib_google.py` com scraper do Google Scholar
- ✅ Novo módulo `lib_scopus.py` com cliente Scopus API via pybliometrics
- ✅ Novo módulo `lib_wos.py` com cliente Web of Science API
- ✅ Coleta automática de CiteScore via Scopus API (opcional com --scopus)
- ✅ Headers de documentação em todos os arquivos Python
- ✅ Documentação atualizada (CLAUDE.md e README.md)

#### Nova Estrutura de Arquivos

```
capes_metrics.py    # Script principal (orquestração)
lib_aux.py          # Dataclasses e funções auxiliares
lib_google.py       # Scraper Google Scholar Metrics
lib_scopus.py       # Cliente Scopus API
lib_wos.py          # Cliente Web of Science API
```

#### Workflow Atualizado

Agora todas as métricas podem ser coletadas automaticamente:
1. H5-index automático (Google Scholar)
2. JIF automático (WoS API, opcional com --wos)
3. CiteScore automático (Scopus API, opcional com --scopus)
4. Estrato final calculado automaticamente (melhor entre três)

### Versão 1.2 (2026-01-26)

**Atualização**: Integração com Web of Science Starter API

#### Melhorias Implementadas

- ✅ Coleta automática de JIF via WoS Starter API (opcional com --wos)
- ✅ Suporte a variáveis de ambiente via python-dotenv (.env)
- ✅ Função `calcular_estrato_final()` para determinar melhor métrica
- ✅ Campos WoS adicionados ao dataclass `RevistaMetrics`
- ✅ Máscaramento de API keys em logs (segurança)
- ✅ Tratamento de erros 401, 429, 404 da API WoS
- ✅ Tabela de resultados expandida com JIF e estrato final
- ✅ Documentação completa para configuração .env

#### Workflow Atualizado

Antes: H5-index automático + template Scopus manual
Agora:
1. H5-index automático (Google Scholar)
2. JIF automático (WoS API, opcional)
3. CiteScore manual (Scopus)
4. Estrato final calculado automaticamente (melhor entre três)

### Versão 1.1 (2026-01-26)

**Atualização**: Coleta automática de H5-index para revistas

#### Melhorias Implementadas

- ✅ Coleta automática de H5-index para periódicos via Google Scholar Metrics
- ✅ Cálculo de estrato inicial para revistas baseado em H5-index (`estrato_h5`)
- ✅ Exportação CSV + JSON com ambas as métricas (H5 e CiteScore/Percentil)
- ✅ Tabela de resultados mostrando ambos os estratos (`estrato_h5` e `estrato_percentil`)
- ✅ Refatoração do scraper com método genérico `_buscar_venue_gsm()`
- ✅ Atualização da documentação (CLAUDE.md e README.md)

#### Workflow Atualizado para Revistas

Antes: Apenas gerava template vazio para preenchimento manual
Agora:
1. Coleta H5-index automaticamente
2. Calcula estrato baseado em H5
3. Gera CSV com dados parciais (H5 preenchido, Scopus vazio)
4. Usuário preenche colunas CiteScore/Percentil manualmente
5. Compara ambos os estratos para decisão final

### Versão 1.0 (2026-01-26)

Criado via Claude.ai com as seguintes funcionalidades:

#### ✅ Implementado

- Scraping de H5-index do Google Scholar Metrics para conferências
- Cálculo automático de estratos para conferências (Etapa 1 - H5-index)
- Geração de template para periódicos (apenas estrutura)
- Exportação CSV + JSON
- CLI com argparse
- Rate limiting básico
- Detecção de CAPTCHA
- Documentação completa (README + CLAUDE.md)

#### ❌ Não Implementado (Requer Trabalho Manual ou APIs Pagas)

- Ajuste CE-SBC (Etapa 2) para conferências
- Critério de tradição SBC (10+/20+ anos)
- Coleta automática de CiteScore do Scopus (requer JavaScript/Selenium)
- Coleta de JIF do Web of Science (requer assinatura)
- Leitura e processamento de templates preenchidos de revistas
- Cálculo automático de estrato final para revistas (requer comparação H5 vs Percentil)

## Contatos Úteis

### APIs e Serviços

- **Google Scholar Metrics**: https://scholar.google.com/citations?view_op=top_venues
- **Web of Science Starter API**: https://developer.clarivate.com/portal (free tier: 5000 req/mês)
- **Scopus API**: https://dev.elsevier.com (requer email institucional para acesso)
- **Scopus Preview** (gratuito): https://www.scopus.com/sources
- **OpenAlex API**: https://docs.openalex.org (não utilizado - métricas não oficiais)

### Sociedade Brasileira de Computação

- **Rankings CE-SBC**: eventos@sbc.org.br
- **Website SBC**: https://www.sbc.org.br/

### CAPES

- **Portal CAPES**: https://www.gov.br/capes
- **Documentos de Área**: https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-e-programas/avaliacao

## Regras de Desenvolvimento

### Linting e Formatação

**OBRIGATÓRIO**: Após QUALQUER modificação em arquivos Python (.py):

1. Execute `ruff check --fix .` para corrigir problemas automaticamente
2. Execute `ruff format .` para formatar o código
3. Se houver erros não corrigíveis automaticamente, corrija-os antes de finalizar

**Comando completo**:
```bash
ruff check --fix . && ruff format .
```

### Documentação de Código

**OBRIGATÓRIO**: Todo código Python deve seguir estas regras de docstrings:

1. **Formato**: Google Style (https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
2. **Obrigatoriedade**:
   - Todas as funções públicas devem ter docstrings
   - Todas as classes devem ter docstrings
   - Métodos públicos devem ter docstrings
3. **Estrutura mínima**:
   ```python
   def funcao_exemplo(param1: str, param2: int) -> bool:
       """Breve descrição em uma linha.

       Descrição mais detalhada se necessário, explicando o comportamento,
       casos especiais, etc.

       Args:
           param1: Descrição do parâmetro 1
           param2: Descrição do parâmetro 2

       Returns:
           Descrição do que a função retorna

       Raises:
           ValueError: Quando e por que essa exceção é levantada
       """
       pass
   ```

### Fluxo de Trabalho

Sempre que modificar código:
1. Faça as alterações necessárias
2. Execute ruff (check + format)
3. Adicione/atualize docstrings se necessário
4. Verifique se o código está funcionando
5. Confirme que todas as regras foram seguidas antes de finalizar

## Contribuindo

Este projeto foi gerado automaticamente. Para modificações:

1. Respeitar estrutura de dataclasses
2. Manter compatibilidade com formato CSV/JSON
3. Validar contra regras CAPES 2025-2028
4. Adicionar testes para novas features
5. Atualizar documentação
6. **Seguir as Regras de Desenvolvimento** (seção acima)

## Licença

Ver arquivo [LICENSE](LICENSE)

## Referências

### Documentação CAPES

- [Portal CAPES - Avaliação](https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-e-programas/avaliacao)
- [Documento de Área - Computação CAPES 2025-2028](https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-e-programas/avaliacao/sobre-a-avaliacao/areas-avaliacao/sobre-as-areas-de-avaliacao/colegio-de-ciencias-exatas-tecnologicas-e-multidisciplinar/ciencia-da-computacao)
- Documentos em PDF (obtidos durante desenvolvimento):
  - `COMPUTACAO_DOCAREA_2025_2028.pdf`
  - `COMPUTACAO_FICHA_2025_2028.pdf`
  - `19052025_20250502_DocumentoReferencial_FICHA_pages_*.pdf`
  - `13052025_antoniogomes06maiodav.pdf`

### Fontes de Métricas

- [Google Scholar Metrics](https://scholar.google.com/citations?view_op=top_venues) - H5-index gratuito
- [Scopus Preview](https://www.scopus.com/sources) - CiteScore gratuito (coleta manual)
- [Scopus API](https://dev.elsevier.com) - API oficial (requer credenciais)
- [Web of Science](https://www.webofscience.com) - JIF (requer assinatura)
- [OpenAlex](https://openalex.org) - Métricas abertas (não utilizadas - não oficiais)

### Organizações

- [Sociedade Brasileira de Computação - SBC](https://www.sbc.org.br/)
- Rankings CE-SBC: eventos@sbc.org.br

---

**Gerado por**: Claude.ai (Anthropic)
**Data**: 2026-01-26
**Conversa Original**: https://claude.ai/share/b4c1ea23-87f3-4552-94b7-84aecb4ab3cf
