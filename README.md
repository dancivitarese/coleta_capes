# CAPES Metrics Collector

Ferramenta para coletar métricas de periódicos e conferências para avaliação CAPES.
**Procedimento 2 - Área de Computação 2025-2028**

## Estrutura

```
coleta_capes/
├── capes_metrics.py      # Script principal (orquestração e CLI)
├── lib_aux.py            # Biblioteca auxiliar (dataclasses, funções)
├── lib_google.py         # Scraper Google Scholar Metrics
├── lib_scopus.py         # Cliente Scopus API (CiteScore)
├── lib_wos.py            # Cliente Web of Science API (JIF)
├── requirements.txt      # Dependências Python
├── README.md             # Este arquivo
├── CLAUDE.md             # Documentação técnica detalhada
├── config/
│   ├── revistas.csv      # Lista de periódicos a consultar
│   └── conferencias.csv  # Lista de conferências a consultar
└── output/               # Resultados gerados
```

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

### Coletar tudo (conferências + template de revistas)
```bash
python capes_metrics.py
```

### Apenas conferências
```bash
python capes_metrics.py --conferencias
```

### Apenas revistas (coleta H5-index + APIs opcionais)
```bash
# Apenas H5-index
python capes_metrics.py --revistas

# H5-index + JIF do Web of Science
python capes_metrics.py --revistas --wos

# H5-index + CiteScore do Scopus
python capes_metrics.py --revistas --scopus

# Todas as métricas (H5 + JIF + CiteScore)
python capes_metrics.py --revistas --wos --scopus
```

## Configuração

### Web of Science (Opcional)

Para habilitar coleta automática de JIF:

1. Obtenha chave API gratuita em: https://developer.clarivate.com/portal
2. Crie arquivo `.env` na raiz do projeto:
   ```bash
   WOS_API_KEY=sua_chave_api_aqui
   ```
3. Execute com flag `--wos`:
   ```bash
   python capes_metrics.py --revistas --wos
   ```

**Nota**: Free tier permite 5000 requisições/mês.

### Scopus (Opcional)

Para habilitar coleta automática de CiteScore:

1. Obtenha chave API em: https://dev.elsevier.com/myapikey.html
2. Adicione ao arquivo `.env`:
   ```bash
   SCOPUS_API_KEY=sua_chave_api_aqui
   ```
3. Execute com flag `--scopus`:
   ```bash
   python capes_metrics.py --revistas --scopus
   ```

**Nota**: Requer biblioteca `pybliometrics` (incluída em requirements.txt).

### Adicionar conferências

Edite `config/conferencias.csv`:
```csv
# Formato: sigla,nome_completo
NeurIPS,Conference on Neural Information Processing Systems
CVPR,Conference on Computer Vision and Pattern Recognition
```

### Adicionar revistas

Edite `config/revistas.csv`:
```csv
# Formato: sigla,nome_completo,issn
TGRS,IEEE Transactions on Geoscience and Remote Sensing,0196-2892
NATURE,Nature,0028-0836
```

## Fontes de Dados

| Tipo | Fonte | Métrica | Automático |
|------|-------|---------|------------|
| Conferências | Google Scholar Metrics | H5-index | ✅ Sim |
| Revistas | Google Scholar Metrics | H5-index | ✅ Sim |
| Revistas | Web of Science API | JIF + Percentil | ✅ Opcional (--wos) |
| Revistas | Scopus API | CiteScore + Percentil | ✅ Opcional (--scopus) |

### Para revistas (workflow automatizado)

**Automático** (executado pelo script):
1. Coleta H5-index do Google Scholar Metrics
2. Calcula estrato inicial baseado em H5 (`estrato_h5`)
3. [Opcional com --wos] Coleta JIF do Web of Science Starter API
4. [Opcional com --scopus] Coleta CiteScore do Scopus API
5. Calcula `estrato_final` automaticamente (melhor entre H5, CiteScore e JIF)
6. Gera arquivo CSV/JSON com todos os dados

**Uso completo** (todas as métricas):
```bash
python capes_metrics.py --revistas --wos --scopus
```

## Cálculo do Estrato CAPES

### Conferências (H5-index)
| Estrato | H5-index |
|---------|----------|
| A1 | >= 35 |
| A2 | >= 25 |
| A3 | >= 20 |
| A4 | >= 15 |
| A5 | >= 12 |
| A6 | >= 9 |
| A7 | >= 6 |
| A8 | > 0 |

**Ajuste CE-SBC:** Top10 (+2), Top20 (+1), saturação em A3.

### Revistas (Percentil CiteScore)
| Estrato | Percentil |
|---------|-----------|
| A1 | >= 87.5% |
| A2 | >= 75.0% |
| A3 | >= 62.5% |
| A4 | >= 50.0% |
| A5 | >= 37.5% |
| A6 | >= 25.0% |
| A7 | >= 12.5% |
| A8 | < 12.5% |

## Arquivos Gerados

### Conferências
- `output/conferencias_YYYYMMDD_HHMMSS.csv` - Dados em formato CSV
- `output/conferencias_YYYYMMDD_HHMMSS.json` - Dados em formato JSON

### Revistas
- `output/revistas_YYYYMMDD_HHMMSS.csv` - Dados em formato CSV (H5 preenchido, Scopus vazio)
- `output/revistas_YYYYMMDD_HHMMSS.json` - Dados em formato JSON

## Limitações

- **Google Scholar Metrics**: Pode bloquear após muitas requisições (CAPTCHA)
- **Scopus API**: Requer API key e busca por ISSN (busca por nome não suportada)
- **Web of Science**: Free tier limitado a 5000 req/mês (erro 429 se excedido)
- **Rankings SBC**: Não incluídos automaticamente (ajuste manual necessário)
- **Matching**: Primeira correspondência do Google Scholar pode não ser exata - validar coluna `nome_gsm`

## Segurança

- **Credenciais**: Armazene `WOS_API_KEY` e `SCOPUS_API_KEY` em arquivo `.env` (não versionado)
- **API Keys**: Nunca commite `.env` no git (.gitignore já configurado)
- **Logs**: API keys são mascaradas automaticamente nos logs (mostra apenas últimos 4 caracteres)

## Exemplo de Saída

### Conferências
```
CONFERÊNCIAS - Métricas Google Scholar
===========================================================================
Sigla      Nome                                     H5     Estrato
---------- ---------------------------------------- ------ --------
NeurIPS    Neural Information Processing Systems      298       A1
AAAI       AAAI Conference on Artificial Intelli      112       A1
ICML       International Conference on Machine L      224       A1
ICLR       International Conference on Learning       217       A1
IJCNN      International Joint Conference on Neu       47       A1
```

### Revistas
```
REVISTAS - Métricas: Google Scholar (H5) + Scopus (CiteScore) + WoS (JIF)
========================================================================================================================
Sigla    Nome                      H5     E-H5  CS     E-CS  JIF    E-JIF  Final
-------- ------------------------- ------ ----- ------ ----- ------ ------ ------
TGRS     IEEE Transactions on ...     85    A1   95.2%   A1   92.3%    A1    A1
SPE      SPE Journal                  42    A1   80.5%   A2   N/A     N/A    A1
GRSL     IEEE Geoscience and...      58    A1   N/A    N/A   88.1%    A1    A1
```

**Legenda**: E-H5 (estrato H5), E-CS (estrato CiteScore), E-JIF (estrato JIF), Final (melhor estrato)

**Nota**: Todas as métricas podem ser coletadas automaticamente usando `--wos` (JIF) e `--scopus` (CiteScore). Estrato Final mostra a melhor classificação entre H5, CiteScore e JIF.
