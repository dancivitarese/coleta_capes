#!/usr/bin/env python3
"""
Biblioteca Auxiliar - CAPES Metrics Collector
==============================================
Estruturas de dados e funções auxiliares para coleta de métricas CAPES.

Este módulo contém:
- Dataclasses para métricas de conferências e revistas
- Funções de cálculo de estrato CAPES
- Constantes de configuração compartilhadas

Autor: Daniel (gerado com Claude.ai)
Data: 2026-01-26
"""

from dataclasses import dataclass
from typing import Optional


DELAY_MIN = 5
DELAY_MAX = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# =============================================================================
# ESTRUTURAS DE DADOS
# =============================================================================


@dataclass
class ConferenciaMetrics:
    sigla: str
    nome_completo: Optional[str] = None
    nome_gsm: Optional[str] = None
    h5_index: Optional[int] = None
    h5_median: Optional[int] = None
    estrato_capes: Optional[str] = None
    url_fonte: Optional[str] = None
    erro: Optional[str] = None
    data_coleta: Optional[str] = None


@dataclass
class RevistaMetrics:
    sigla: str
    nome_completo: str
    issn: Optional[str] = None
    nome_gsm: Optional[str] = None
    h5_index: Optional[int] = None
    h5_median: Optional[int] = None
    estrato_h5: Optional[str] = None
    citescore: Optional[float] = None
    percentil: Optional[float] = None
    area_tematica: Optional[str] = None
    estrato_percentil: Optional[str] = None
    jif: Optional[float] = None
    jif_percentil: Optional[float] = None
    categoria_wos: Optional[str] = None
    estrato_jif: Optional[str] = None
    estrato_final: Optional[str] = None
    url_gsm: Optional[str] = None
    url_scopus: Optional[str] = None
    url_wos: Optional[str] = None
    erro: Optional[str] = None
    data_coleta: Optional[str] = None


# =============================================================================
# CÁLCULO DO ESTRATO CAPES
# =============================================================================


def calcular_estrato_conferencia(h5_index: Optional[int]) -> str:
    """
    Calcula estrato CAPES para conferências baseado no H5-index.
    Documento de Área de Computação 2025-2028 (Procedimento 2, Etapa 1).

    NOTA: Este é o estrato INICIAL, antes dos ajustes CE-SBC.
    """
    if h5_index is None:
        return "N/A"

    if h5_index >= 35:
        return "A1"
    elif h5_index >= 25:
        return "A2"
    elif h5_index >= 20:
        return "A3"
    elif h5_index >= 15:
        return "A4"
    elif h5_index >= 12:
        return "A5"
    elif h5_index >= 9:
        return "A6"
    elif h5_index >= 6:
        return "A7"
    elif h5_index > 0:
        return "A8"
    else:
        return "N/C"


def calcular_estrato_revista(percentil: Optional[float]) -> str:
    """
    Calcula estrato CAPES para periódicos baseado no percentil CiteScore.
    Documento de Área de Computação 2025-2028 (Procedimento 2).

    Faixas de 12.5%:
    A1: >= 87.5, A2: >= 75, A3: >= 62.5, A4: >= 50,
    A5: >= 37.5, A6: >= 25, A7: >= 12.5, A8: < 12.5
    """
    if percentil is None:
        return "N/A"

    if percentil >= 87.5:
        return "A1"
    elif percentil >= 75.0:
        return "A2"
    elif percentil >= 62.5:
        return "A3"
    elif percentil >= 50.0:
        return "A4"
    elif percentil >= 37.5:
        return "A5"
    elif percentil >= 25.0:
        return "A6"
    elif percentil >= 12.5:
        return "A7"
    else:
        return "A8"


def calcular_estrato_final(
    estrato_h5: Optional[str],
    estrato_percentil: Optional[str],
    estrato_jif: Optional[str],
) -> str:
    """
    Calcula o estrato final de uma revista usando a MELHOR métrica disponível.

    Regra CAPES: Considerar o maior percentil entre CiteScore e JIF.
    Para implementação: A1 > A2 > ... > A8 (menor valor = melhor estrato).

    Args:
        estrato_h5: Estrato baseado em H5-index (ex: "A1", "A2", "N/A")
        estrato_percentil: Estrato baseado em CiteScore percentil
        estrato_jif: Estrato baseado em JIF percentil

    Returns:
        Melhor estrato entre as três métricas, ou "N/A" se nenhuma disponível

    Examples:
        >>> calcular_estrato_final("A2", "A1", "A3")
        "A1"
        >>> calcular_estrato_final("A5", None, None)
        "A5"
        >>> calcular_estrato_final(None, None, None)
        "N/A"
    """
    # Mapear estratos para valores numéricos (menor = melhor)
    estrato_map = {
        "A1": 1,
        "A2": 2,
        "A3": 3,
        "A4": 4,
        "A5": 5,
        "A6": 6,
        "A7": 7,
        "A8": 8,
        "N/A": 999,
        "N/C": 999,
        None: 999,
    }

    # Converter estratos para números
    valores = [
        (estrato_h5, estrato_map.get(estrato_h5, 999)),
        (estrato_percentil, estrato_map.get(estrato_percentil, 999)),
        (estrato_jif, estrato_map.get(estrato_jif, 999)),
    ]

    # Filtrar valores válidos e pegar o melhor (menor número)
    valores_validos = [(e, v) for e, v in valores if v < 999]

    if not valores_validos:
        return "N/A"

    # Retorna o estrato com menor valor numérico (melhor)
    melhor_estrato, _ = min(valores_validos, key=lambda x: x[1])
    return melhor_estrato
