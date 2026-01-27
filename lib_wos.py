#!/usr/bin/env python3
"""
Biblioteca Web of Science - CAPES Metrics Collector
=====================================================
Cliente para Web of Science Starter API.

Este módulo contém:
- WebOfScienceAPIClient: classe para buscar JIF e percentil de revistas

Funcionalidades:
- Busca Journal Impact Factor (JIF) por ISSN
- Coleta percentil e categoria WoS
- Rate limiting (free tier: 5000 req/mês)
- Tratamento de erros HTTP (401, 429, 404)

Requisitos:
- API key de https://developer.clarivate.com/portal

Documentação API: https://developer.clarivate.com/apis/wos-starter

Autor: Daniel (gerado com Claude.ai)
Data: 2026-01-26
"""

import random
import time
from typing import Optional

import requests

from lib_aux import DELAY_MAX, DELAY_MIN


class WebOfScienceAPIClient:
    """
    Cliente para Web of Science Starter API.

    Coleta Journal Impact Factor (JIF) e percentil de categorias.
    API Gratuita: 5000 requisições/mês
    Documentação: https://developer.clarivate.com/apis/wos-starter

    Attributes:
        api_key: Chave de API WoS
        base_url: URL base da API
        session: Sessão HTTP reutilizável
    """

    BASE_URL = "https://api.clarivate.com/apis/wos-starter/v1"

    def __init__(self, api_key: str, timeout: int = 30):
        """
        Inicializa o cliente WoS API.

        Args:
            api_key: Chave de API obtida em developer.clarivate.com
            timeout: Timeout em segundos para requisições (padrão: 30s)

        Raises:
            ValueError: Se api_key estiver vazio
        """
        if not api_key or not api_key.strip():
            raise ValueError("WoS API key não pode estar vazia")

        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-ApiKey": self.api_key,
                "Accept": "application/json",
                "User-Agent": "CAPES-Metrics-Collector/1.2",
            }
        )

    def _delay(self):
        """
        Implementa rate limiting para respeitar limites da API.

        Free tier: 5000 req/mês ≈ 6.9 req/hora se usado uniformemente.
        Delay conservador para evitar rate limit 429.
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

    def buscar_revista_wos(self, issn: Optional[str], nome: str) -> tuple:
        """
        Busca métricas de revista no Web of Science.

        Ordem de busca:
        1. Por ISSN (mais preciso)
        2. Por nome (fallback se ISSN não fornecido)

        Args:
            issn: ISSN da revista (formato: XXXX-XXXX)
            nome: Nome completo da revista (usado se ISSN ausente)

        Returns:
            Tupla (jif, jif_percentil, categoria_wos, url_wos, erro)
            onde:
                jif: Journal Impact Factor (float)
                jif_percentil: Percentil na categoria (0-100)
                categoria_wos: Nome da categoria WoS
                url_wos: URL da fonte no WoS
                erro: Mensagem de erro (None se sucesso)

        Examples:
            >>> client = WebOfScienceAPIClient("abc123")
            >>> jif, pct, cat, url, err = client.buscar_revista_wos(
            ...     "0028-0836", "Nature"
            ... )
        """
        try:
            self._delay()

            # API WoS Starter só aceita busca por ISSN
            if not issn or not issn.strip():
                return (
                    None,
                    None,
                    None,
                    None,
                    f"ISSN obrigatório para busca WoS (revista: {nome})",
                )

            issn_clean = issn.strip()

            # Endpoint: /journals (parâmetro: issn)
            url = f"{self.BASE_URL}/journals"
            params = {"issn": issn_clean}

            response = self.session.get(url, params=params, timeout=self.timeout)

            # Tratamento de erros HTTP
            if response.status_code == 401:
                masked = self._mask_api_key(self.api_key)
                return (
                    None,
                    None,
                    None,
                    None,
                    f"Autenticação falhou (chave: {masked}). Verifique WOS_API_KEY",
                )
            elif response.status_code == 429:
                return (
                    None,
                    None,
                    None,
                    None,
                    "Rate limit excedido (5000 req/mês). Aguarde reset mensal",
                )
            elif response.status_code == 404:
                return (
                    None,
                    None,
                    None,
                    None,
                    f"Revista não encontrada no WoS (ISSN: {issn_clean})",
                )

            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            # Estrutura esperada: {"data": [{"id": "...", "metrics": {...}}]}
            if not data.get("data") or len(data["data"]) == 0:
                return (
                    None,
                    None,
                    None,
                    None,
                    f"Nenhum resultado no WoS (ISSN: {issn_clean})",
                )

            journal = data["data"][0]
            metrics = journal.get("metrics", {})

            # Extrai métricas
            jif = metrics.get("jif")  # Journal Impact Factor
            jif_percentil = metrics.get("jif_percentile")
            categoria_wos = metrics.get("category")  # Categoria principal
            journal_id = journal.get("id")

            # Monta URL do WoS
            url_wos = None
            if journal_id:
                url_wos = f"https://jcr.clarivate.com/jcr/journal-profile?journal={journal_id}"

            # Validação básica
            if jif is None and jif_percentil is None:
                return (
                    None,
                    None,
                    categoria_wos,
                    url_wos,
                    "Revista encontrada mas sem métricas JIF disponíveis",
                )

            return (jif, jif_percentil, categoria_wos, url_wos, None)

        except requests.Timeout:
            return (
                None,
                None,
                None,
                None,
                f"Timeout após {self.timeout}s ao consultar WoS API",
            )
        except requests.RequestException as e:
            return (None, None, None, None, f"Erro de conexão WoS API: {str(e)}")
        except (KeyError, ValueError, TypeError) as e:
            return (None, None, None, None, f"Erro ao parsear resposta WoS: {str(e)}")
        except Exception as e:
            return (None, None, None, None, f"Erro inesperado WoS: {str(e)}")
