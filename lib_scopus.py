#!/usr/bin/env python3
"""
Biblioteca Scopus - CAPES Metrics Collector
=============================================
Cliente para Scopus API via pybliometrics.

Este módulo contém:
- ScopusAPIClient: classe para buscar CiteScore e percentil de revistas

Funcionalidades:
- Busca CiteScore e percentil por ISSN
- Identifica melhor categoria (maior percentil)
- Rate limiting e tratamento de erros

Requisitos:
- API key de https://dev.elsevier.com/myapikey.html
- Biblioteca pybliometrics configurada

Fonte: https://www.scopus.com/sources

Autor: Daniel (gerado com Claude.ai)
Data: 2026-01-26
"""

import random
import time
from typing import Optional

import pybliometrics
from pybliometrics.scopus import SerialTitleISSN

from lib_aux import DELAY_MAX, DELAY_MIN


class ScopusAPIClient:
    """
    Cliente para Scopus API usando biblioteca pybliometrics.

    Busca CiteScore e percentil de periódicos por ISSN.
    Requer API key de https://dev.elsevier.com/myapikey.html

    Attributes:
        api_key: Chave de API Scopus
    """

    def __init__(self, api_key: str, timeout: int = 30):
        """
        Inicializa o cliente Scopus API.

        Args:
            api_key: Chave de API obtida em dev.elsevier.com
            timeout: Timeout em segundos para requisições (padrão: 30s)

        Raises:
            ValueError: Se api_key estiver vazio
        """
        if not api_key or not api_key.strip():
            raise ValueError("Scopus API key não pode estar vazia")

        self.api_key = api_key
        self.timeout = timeout

        # Initialize pybliometrics with API key
        pybliometrics.init(keys=[api_key])

    def _delay(self):
        """
        Implementa rate limiting para respeitar limites da API.

        Scopus API tem limites generosos mas delay conservador evita problemas.
        """
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        print(f"    ⏳ Aguardando {delay:.1f}s...")
        time.sleep(delay)

    def _mask_api_key(self, key: str) -> str:
        """
        Mascara chave API para logs (mostra apenas últimos 4 caracteres).

        Args:
            key: Chave API completa

        Returns:
            Chave mascarada (ex: "****abc123")
        """
        if len(key) <= 8:
            return "****"
        return "*" * (len(key) - 4) + key[-4:]

    def buscar_revista_scopus(self, issn: Optional[str], nome: str) -> tuple:
        """
        Busca métricas de revista no Scopus (CiteScore e percentil).

        Args:
            issn: ISSN da revista (formato: XXXX-XXXX)
            nome: Nome completo da revista (usado para mensagens de erro)

        Returns:
            Tupla (citescore, percentil, area_tematica, url_scopus, erro)
            onde:
                citescore: CiteScore atual (float)
                percentil: Percentil na melhor categoria (0-100)
                area_tematica: Código ASJC da área temática
                url_scopus: URL da fonte no Scopus
                erro: Mensagem de erro (None se sucesso)
        """
        try:
            self._delay()

            if not issn or not issn.strip():
                return (
                    None,
                    None,
                    None,
                    None,
                    f"ISSN não fornecido para '{nome}'. Scopus API requer ISSN.",
                )

            issn_clean = issn.strip()

            # Get journal data with CITESCORE view
            serial = SerialTitleISSN(issn_clean, view="CITESCORE")

            # Get CiteScore year info
            cs_info = serial.citescoreyearinfolist
            if not cs_info:
                return (
                    None,
                    None,
                    None,
                    None,
                    f"Nenhum dado CiteScore disponível para ISSN: {issn_clean}",
                )

            # Get most recent year's data (last entry)
            latest = cs_info[-1]
            citescore = float(latest.citescore) if latest.citescore else None

            # Extract percentile from rank (best category)
            percentile = None
            area = None
            if latest.rank:
                # rank is list of namedtuples (subjectcode, rank, percentile)
                # Get highest percentile across all categories
                best_rank = max(
                    latest.rank,
                    key=lambda r: float(r.percentile) if r.percentile else 0,
                )
                percentile = (
                    float(best_rank.percentile) if best_rank.percentile else None
                )
                area = best_rank.subjectcode

            # Build Scopus URL
            url_scopus = None
            if hasattr(serial, "source_id") and serial.source_id:
                url_scopus = f"https://www.scopus.com/sourceid/{serial.source_id}"

            return (citescore, percentile, area, url_scopus, None)

        except Exception as e:
            error_msg = str(e)
            # Check for common error patterns
            if "401" in error_msg or "Unauthorized" in error_msg:
                masked = self._mask_api_key(self.api_key)
                return (
                    None,
                    None,
                    None,
                    None,
                    f"Autenticação falhou (chave: {masked}). Verifique SCOPUS_API_KEY",
                )
            elif "404" in error_msg or "not found" in error_msg.lower():
                return (
                    None,
                    None,
                    None,
                    None,
                    f"Revista não encontrada no Scopus (ISSN: {issn})",
                )
            elif "429" in error_msg or "rate" in error_msg.lower():
                return (
                    None,
                    None,
                    None,
                    None,
                    "Rate limit excedido. Aguarde alguns minutos",
                )
            return (None, None, None, None, f"Erro Scopus: {error_msg}")
