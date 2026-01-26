# CAPES Metrics Collector

Ferramenta para coletar métricas de periódicos e conferências para avaliação CAPES.
**Procedimento 2 - Área de Computação 2025-2028**

## Estrutura

```
capes_metrics/
├── capes_metrics.py      # Script principal
├── requirements.txt      # Dependências Python
├── README.md            # Este arquivo
├── config/
│   ├── revistas.csv     # Lista de periódicos a consultar
│   └── conferencias.csv # Lista de conferências a consultar
└── output/              # Resultados gerados
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

### Apenas revistas (coleta H5-index + template Scopus)
```bash
# Apenas H5-index
python capes_metrics.py --revistas

# H5-index + JIF do Web of Science
python capes_metrics.py --revistas --wos
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
| Revistas | Scopus Preview | CiteScore + Percentil | ⚠️ Manual |

### Para revistas (workflow híbrido)

**Automático** (executado pelo script):
1. Coleta H5-index do Google Scholar Metrics
2. Calcula estrato inicial baseado em H5 (`estrato_h5`)
3. [Opcional com --wos] Coleta JIF do Web of Science Starter API
4. Calcula `estrato_jif` e `estrato_final` (melhor métrica)
5. Gera arquivo CSV com dados parciais

**Manual** (usuário deve fazer):
1. Abrir arquivo CSV gerado em `output/revistas_TIMESTAMP.csv`
2. Acessar: https://www.scopus.com/sources
3. Buscar pelo nome ou ISSN de cada revista
4. Anotar: **CiteScore**, **Percentile** e **Subject Area**
5. Preencher as colunas vazias: `citescore`, `percentil`, `area_tematica`, `url_scopus`
6. Comparar `estrato_final` com `estrato_percentil` e usar o melhor

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
- **Scopus Preview**: Requer JavaScript, não permite scraping direto
- **Web of Science**: Free tier limitado a 5000 req/mês (erro 429 se excedido)
- **Rankings SBC**: Não incluídos automaticamente (ajuste manual necessário)
- **Matching**: Primeira correspondência do Google Scholar pode não ser exata - validar coluna `nome_gsm`

## Segurança

- **Credenciais**: Armazene `WOS_API_KEY` em arquivo `.env` (não versionado)
- **API Keys**: Nunca commite `.env` no git (.gitignore já configurado)
- **Logs**: API keys são mascaradas automaticamente nos logs

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

**Nota**: As colunas `CiteScore` e `Percentil` devem ser preenchidas manualmente consultando o Scopus. A coluna `JIF` é preenchida automaticamente se usar `--wos`. Estrato Final mostra a melhor classificação entre H5, CiteScore e JIF.
