#!/usr/bin/env python3
"""
Biblioteca Google Scholar - CAPES Metrics Collector
=====================================================
Scraper para coleta de H5-index do Google Scholar Metrics.

Este módulo contém:
- GoogleScholarMetricsScraper: classe para buscar métricas de conferências e revistas

Funcionalidades:
- Busca H5-index e H5-median de venues acadêmicos
- Rate limiting para evitar bloqueio por CAPTCHA
- Detecção de bloqueio e tratamento de erros

Fonte: https://scholar.google.com/citations?view_op=top_venues

Autor: Daniel (gerado com Claude.ai)
Data: 2026-01-26
"""

import random
import time
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from lib_aux import (
    DELAY_MAX,
    DELAY_MIN,
    HEADERS,
    ConferenciaMetrics,
    RevistaMetrics,
    calcular_estrato_conferencia,
)


class GoogleScholarMetricsScraper:
    """Scraper para H5-index do Google Scholar Metrics."""

    BASE_URL = "https://scholar.google.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def _delay(self):
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        print(f"    ⏳ Aguardando {delay:.1f}s...")
        time.sleep(delay)

    def _buscar_venue_gsm(self, query: str) -> tuple:
        """
        Busca genérica no Google Scholar Metrics.

        Args:
            query: Termo de busca (nome da conferência ou revista)

        Returns:
            Tupla (nome_gsm, h5_index, h5_median, url_fonte, erro)
        """
        try:
            self._delay()

            query_encoded = quote_plus(query)
            url = f"{self.BASE_URL}/citations?view_op=search_venues&vq={query_encoded}&hl=en"

            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Verifica bloqueio (CAPTCHA)
            if (
                "unusual traffic" in response.text.lower()
                or "captcha" in response.text.lower()
            ):
                return (
                    None,
                    None,
                    None,
                    None,
                    "BLOQUEADO (CAPTCHA) - aguarde alguns minutos",
                )

            soup = BeautifulSoup(response.text, "html.parser")

            # Encontra tabela de resultados
            tabela = soup.find("table", {"id": "gsc_mvt_table"})
            if not tabela:
                return None, None, None, None, "Nenhum resultado encontrado"

            # Pega todas as linhas e filtra as que têm células TD (ignora header com TH)
            linhas = tabela.find_all("tr")
            linhas_dados = [linha_tr for linha_tr in linhas if linha_tr.find("td")]

            if not linhas_dados:
                return None, None, None, None, "Nenhum resultado na tabela"

            # Pega primeira linha de dados (melhor match)
            linha = linhas_dados[0]

            # Nome do venue (texto direto na célula)
            nome_gsm = None
            celula_nome = linha.find("td", {"class": "gsc_mvt_t"})
            if celula_nome:
                nome_gsm = celula_nome.text.strip()

            # H5-index e H5-median (estão em células separadas, ambas com classe gsc_mvt_n)
            h5_index = None
            h5_median = None
            url_fonte = None
            celulas_metricas = linha.find_all("td", {"class": "gsc_mvt_n"})

            if len(celulas_metricas) >= 1:
                # Primeira célula: H5-index (geralmente em um link)
                link_h5 = celulas_metricas[0].find("a")
                if link_h5:
                    try:
                        h5_index = int(link_h5.text.strip())
                        href = link_h5.get("href", "")
                        if href:
                            url_fonte = self.BASE_URL + str(href)
                    except ValueError:
                        pass

            if len(celulas_metricas) >= 2:
                # Segunda célula: H5-median (pode estar em span ou direto)
                texto_median = celulas_metricas[1].text.strip()
                try:
                    h5_median = int(texto_median)
                except ValueError:
                    pass

            return nome_gsm, h5_index, h5_median, url_fonte, None

        except requests.RequestException as e:
            return None, None, None, None, f"Erro de conexão: {str(e)}"
        except Exception as e:
            return None, None, None, None, f"Erro: {str(e)}"

    def buscar_conferencia(
        self, sigla: str, nome_completo: Optional[str] = None
    ) -> ConferenciaMetrics:
        """Busca métricas de uma conferência no Google Scholar Metrics."""

        resultado = ConferenciaMetrics(
            sigla=sigla,
            nome_completo=nome_completo,
            data_coleta=datetime.now().isoformat(),
        )

        # Tenta buscar pelo nome completo, senão pela sigla
        query = nome_completo if nome_completo else sigla
        nome_gsm, h5_index, h5_median, url_fonte, erro = self._buscar_venue_gsm(query)

        resultado.nome_gsm = nome_gsm
        resultado.h5_index = h5_index
        resultado.h5_median = h5_median
        resultado.url_fonte = url_fonte
        resultado.erro = erro
        resultado.estrato_capes = calcular_estrato_conferencia(h5_index)

        return resultado

    def buscar_revista(
        self, sigla: str, nome_completo: str, issn: Optional[str] = None
    ) -> RevistaMetrics:
        """Busca métricas de uma revista no Google Scholar Metrics."""

        resultado = RevistaMetrics(
            sigla=sigla,
            nome_completo=nome_completo,
            issn=issn,
            data_coleta=datetime.now().isoformat(),
        )

        # Tenta buscar pelo nome completo
        nome_gsm, h5_index, h5_median, url_gsm, erro = self._buscar_venue_gsm(
            nome_completo
        )

        resultado.nome_gsm = nome_gsm
        resultado.h5_index = h5_index
        resultado.h5_median = h5_median
        resultado.url_gsm = url_gsm
        resultado.erro = erro
        resultado.estrato_h5 = calcular_estrato_conferencia(h5_index)

        return resultado
