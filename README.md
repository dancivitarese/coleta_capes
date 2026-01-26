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

### Apenas revistas (gera template para preenchimento manual)
```bash
python capes_metrics.py --revistas
```

## Configuração

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
| Revistas | Scopus Preview | CiteScore + Percentil | ❌ Manual |

### Para revistas (coleta manual)

1. Acesse: https://www.scopus.com/sources
2. Busque pelo nome ou ISSN da revista
3. Anote: **CiteScore** e **Percentile**
4. Preencha o template CSV gerado em `output/`

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

## Limitações

- **Google Scholar Metrics**: Pode bloquear após muitas requisições (CAPTCHA)
- **Scopus Preview**: Requer JavaScript, não permite scraping direto
- **Rankings SBC**: Não incluídos automaticamente (ajuste manual necessário)

## Exemplo de Saída

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
