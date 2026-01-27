#!/usr/bin/env python3
"""
CAPES Metrics Collector
=======================
Coleta métricas de periódicos e conferências para avaliação CAPES.
Procedimento 2 - Área de Computação 2025-2028.

Fontes:
- Conferências: Google Scholar Metrics (H5-index) - automático
- Periódicos: Google Scholar Metrics (H5-index) - automático
             + Scopus Preview (CiteScore + Percentil) - manual

Uso:
    python capes_metrics.py                    # Coleta tudo
    python capes_metrics.py --conferencias     # Apenas conferências
    python capes_metrics.py --revistas         # Apenas revistas (H5 + template Scopus)

Configuração:
    config/revistas.csv     - Lista de periódicos
    config/conferencias.csv - Lista de conferências
"""

import argparse
import csv
import json
import os
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Scopus API (pybliometrics)
import pybliometrics
from pybliometrics.scopus import SerialTitleISSN

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"

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


# =============================================================================
# CARREGAMENTO DE CONFIGURAÇÃO
# =============================================================================


def carregar_conferencias(filepath: Path) -> List[Dict]:
    """Carrega lista de conferências do arquivo CSV."""
    conferencias = []

    if not filepath.exists():
        print(f"⚠️  Arquivo não encontrado: {filepath}")
        return conferencias

    with open(filepath, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue

            partes = linha.split(",", 1)
            sigla = partes[0].strip()
            nome = partes[1].strip() if len(partes) > 1 else None

            conferencias.append({"sigla": sigla, "nome_completo": nome})

    return conferencias


def carregar_revistas(filepath: Path) -> List[Dict]:
    """Carrega lista de revistas do arquivo CSV."""
    revistas = []

    if not filepath.exists():
        print(f"⚠️  Arquivo não encontrado: {filepath}")
        return revistas

    with open(filepath, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#"):
                continue

            partes = linha.split(",")
            sigla = partes[0].strip()
            nome = partes[1].strip() if len(partes) > 1 else sigla
            issn = partes[2].strip() if len(partes) > 2 else None

            revistas.append({"sigla": sigla, "nome_completo": nome, "issn": issn})

    return revistas


# =============================================================================
# SCRAPER GOOGLE SCHOLAR METRICS
# =============================================================================


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


# =============================================================================
# WEB OF SCIENCE STARTER API CLIENT
# =============================================================================


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

    BASE_URL = "https://api.clarivate.com/api/wos-starter"

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

            # Monta query (prioriza ISSN)
            if issn and issn.strip():
                query_param = issn.strip()
                search_type = "issn"
            else:
                query_param = nome
                search_type = "title"

            # Endpoint: /journals
            url = f"{self.BASE_URL}/journals"
            params = {"q": query_param, "limit": 1}  # Pega apenas primeiro resultado

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
                    f"Revista não encontrada no WoS ({search_type}: {query_param})",
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
                    f"Nenhum resultado no WoS para {search_type}: {query_param}",
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


# =============================================================================
# SCOPUS API CLIENT (PYBLIOMETRICS)
# =============================================================================


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


# =============================================================================
# SAÍDA DE RESULTADOS
# =============================================================================


def salvar_csv(resultados: List, filepath: Path, colunas: List[str]):
    """Salva resultados em CSV."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=colunas)
        writer.writeheader()
        for r in resultados:
            writer.writerow(asdict(r))

    print(f"✅ Salvo: {filepath}")


def salvar_json(resultados: List, filepath: Path):
    """Salva resultados em JSON."""
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in resultados], f, indent=2, ensure_ascii=False)

    print(f"✅ Salvo: {filepath}")


def imprimir_tabela_conferencias(resultados: List[ConferenciaMetrics]):
    """Imprime resultados de conferências em tabela."""
    print(f"\n{'=' * 75}")
    print(" CONFERÊNCIAS - Métricas Google Scholar")
    print(f"{'=' * 75}")
    print(f"{'Sigla':<10} {'Nome':<40} {'H5':>6} {'Estrato':>8}")
    print(f"{'-' * 10} {'-' * 40} {'-' * 6} {'-' * 8}")

    for r in resultados:
        nome = (r.nome_gsm or r.nome_completo or r.sigla)[:40]
        h5 = str(r.h5_index) if r.h5_index else "N/A"
        estrato = r.estrato_capes or "N/A"
        erro = " ⚠️" if r.erro else ""
        print(f"{r.sigla:<10} {nome:<40} {h5:>6} {estrato:>8}{erro}")

    print()


def imprimir_tabela_revistas(resultados: List[RevistaMetrics]):
    """Imprime resultados de revistas em tabela."""
    print(f"\n{'=' * 120}")
    print(" REVISTAS - Métricas: Google Scholar (H5) + Scopus (CiteScore) + WoS (JIF)")
    print(f"{'=' * 120}")
    print(
        f"{'Sigla':<8} {'Nome':<25} {'H5':>6} {'E-H5':>5} {'CS':>6} {'E-CS':>5} {'JIF':>6} {'E-JIF':>6} {'Final':>6}"
    )
    print(
        f"{'-' * 8} {'-' * 25} {'-' * 6} {'-' * 5} {'-' * 6} {'-' * 5} {'-' * 6} {'-' * 6} {'-' * 6}"
    )

    for r in resultados:
        nome = (r.nome_gsm or r.nome_completo or r.sigla)[:25]
        h5 = str(r.h5_index) if r.h5_index else "N/A"
        estrato_h5 = r.estrato_h5 or "N/A"

        # CiteScore (Scopus)
        cs = f"{r.percentil:.1f}%" if r.percentil else "N/A"
        estrato_cs = r.estrato_percentil or "N/A"

        # JIF (Web of Science)
        jif_display = f"{r.jif_percentil:.1f}%" if r.jif_percentil else "N/A"
        estrato_jif = r.estrato_jif or "N/A"

        # Final (melhor entre todos)
        estrato_final = r.estrato_final or "N/A"

        erro = " ⚠️" if r.erro else ""
        print(
            f"{r.sigla:<8} {nome:<25} {h5:>6} {estrato_h5:>5} "
            f"{cs:>6} {estrato_cs:>5} {jif_display:>6} {estrato_jif:>6} {estrato_final:>6}{erro}"
        )

    print()

    # Add legend
    print(
        "Legenda: E-H5 (estrato H5), E-CS (estrato CiteScore), E-JIF (estrato JIF), Final (melhor estrato)"
    )


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================


def main():
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Coleta métricas CAPES de periódicos e conferências"
    )
    parser.add_argument(
        "--conferencias", action="store_true", help="Coleta apenas conferências"
    )
    parser.add_argument(
        "--revistas",
        action="store_true",
        help="Coleta apenas revistas (H5-index + template Scopus)",
    )
    parser.add_argument(
        "--wos",
        action="store_true",
        help="Inclui coleta de JIF do Web of Science (requer WOS_API_KEY em .env)",
    )
    parser.add_argument(
        "--scopus",
        action="store_true",
        help="Inclui coleta de CiteScore do Scopus (requer SCOPUS_API_KEY em .env)",
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT_DIR, help="Diretório de saída"
    )
    parser.add_argument(
        "--config", type=Path, default=CONFIG_DIR, help="Diretório de configuração"
    )

    args = parser.parse_args()

    print("=" * 75)
    print(" CAPES Metrics Collector")
    print(" Procedimento 2 - Computação 2025-2028")
    print("=" * 75)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    coletar_tudo = not args.conferencias and not args.revistas

    # -------------------------------------------------------------------------
    # WEB OF SCIENCE SETUP (OPTIONAL)
    # -------------------------------------------------------------------------
    wos_client = None
    if args.wos:
        wos_api_key = os.getenv("WOS_API_KEY")
        if wos_api_key:
            try:
                wos_client = WebOfScienceAPIClient(wos_api_key)
                print("✅ Web of Science API ativado")
            except ValueError as e:
                print(f"⚠️  Erro ao inicializar WoS client: {e}")
                print("   Continuando sem coleta de JIF...")
        else:
            print("⚠️  Flag --wos ativada mas WOS_API_KEY não encontrada em .env")
            print("   Continuando sem coleta de JIF...")
            print("   Configure WOS_API_KEY no arquivo .env para habilitar WoS")

    # -------------------------------------------------------------------------
    # SCOPUS SETUP (OPTIONAL)
    # -------------------------------------------------------------------------
    scopus_client = None
    if args.scopus:
        scopus_api_key = os.getenv("SCOPUS_API_KEY")
        if scopus_api_key:
            try:
                scopus_client = ScopusAPIClient(scopus_api_key)
                print("✅ Scopus API ativado")
            except ValueError as e:
                print(f"⚠️  Erro ao inicializar Scopus client: {e}")
                print("   Continuando sem coleta de CiteScore...")
        else:
            print("⚠️  Flag --scopus ativada mas SCOPUS_API_KEY não encontrada em .env")
            print("   Continuando sem coleta de CiteScore...")
            print("   Configure SCOPUS_API_KEY no arquivo .env para habilitar Scopus")

    # -------------------------------------------------------------------------
    # CONFERÊNCIAS
    # -------------------------------------------------------------------------
    if coletar_tudo or args.conferencias:
        print("\n📚 Carregando conferências...")
        conferencias = carregar_conferencias(args.config / "conferencias.csv")
        print(f"   → {len(conferencias)} conferências encontradas")

        if conferencias:
            print("\n🔍 Buscando H5-index no Google Scholar Metrics...")
            scraper = GoogleScholarMetricsScraper()
            resultados_conf = []

            for i, conf in enumerate(conferencias, 1):
                print(f"\n[{i}/{len(conferencias)}] {conf['sigla']}")
                resultado = scraper.buscar_conferencia(
                    conf["sigla"], conf.get("nome_completo")
                )
                resultados_conf.append(resultado)

                if resultado.erro:
                    print(f"    ⚠️  {resultado.erro}")
                else:
                    print(f"    ✓ H5={resultado.h5_index} → {resultado.estrato_capes}")

            # Salva resultados
            salvar_csv(
                resultados_conf,
                args.output / f"conferencias_{timestamp}.csv",
                [
                    "sigla",
                    "nome_completo",
                    "nome_gsm",
                    "h5_index",
                    "h5_median",
                    "estrato_capes",
                    "url_fonte",
                    "erro",
                    "data_coleta",
                ],
            )
            salvar_json(resultados_conf, args.output / f"conferencias_{timestamp}.json")

            imprimir_tabela_conferencias(resultados_conf)

    # -------------------------------------------------------------------------
    # REVISTAS
    # -------------------------------------------------------------------------
    if coletar_tudo or args.revistas:
        print("\n📚 Carregando revistas...")
        revistas = carregar_revistas(args.config / "revistas.csv")
        print(f"   → {len(revistas)} revistas encontradas")

        if revistas:
            print("\n🔍 Buscando H5-index no Google Scholar Metrics...")
            scraper = GoogleScholarMetricsScraper()
            resultados_rev = []

            for i, rev in enumerate(revistas, 1):
                print(f"\n[{i}/{len(revistas)}] {rev['sigla']}")

                # 1. Coleta H5-index (Google Scholar)
                resultado = scraper.buscar_revista(
                    rev["sigla"], rev["nome_completo"], rev.get("issn")
                )

                if resultado.erro:
                    print(f"    ⚠️  GSM: {resultado.erro}")
                else:
                    print(
                        f"    ✓ GSM: H5={resultado.h5_index} → {resultado.estrato_h5}"
                    )

                # 2. Coleta JIF (Web of Science) se --wos ativado
                if wos_client:
                    print("    🔍 Consultando WoS para JIF...")
                    jif, jif_pct, cat_wos, url_wos, erro_wos = (
                        wos_client.buscar_revista_wos(
                            resultado.issn, resultado.nome_completo
                        )
                    )

                    resultado.jif = jif
                    resultado.jif_percentil = jif_pct
                    resultado.categoria_wos = cat_wos
                    resultado.url_wos = url_wos
                    resultado.estrato_jif = (
                        calcular_estrato_revista(jif_pct)
                        if jif_pct is not None
                        else None
                    )

                    if erro_wos:
                        print(f"    ⚠️  WoS: {erro_wos}")
                    else:
                        print(
                            f"    ✓ WoS: JIF={jif} (Pct={jif_pct}%) → {resultado.estrato_jif}"
                        )

                # 3. Coleta CiteScore (Scopus) se --scopus ativado
                if scopus_client:
                    print("    🔍 Consultando Scopus para CiteScore...")
                    cs, pct, area, url_scopus, erro_scopus = (
                        scopus_client.buscar_revista_scopus(
                            resultado.issn, resultado.nome_completo
                        )
                    )

                    resultado.citescore = cs
                    resultado.percentil = pct
                    resultado.area_tematica = area
                    resultado.url_scopus = url_scopus
                    resultado.estrato_percentil = (
                        calcular_estrato_revista(pct) if pct is not None else None
                    )

                    if erro_scopus:
                        print(f"    ⚠️  Scopus: {erro_scopus}")
                    else:
                        print(
                            f"    ✓ Scopus: CS={cs} (Pct={pct}%) → {resultado.estrato_percentil}"
                        )

                # 4. Calcula estrato final (melhor entre H5, CiteScore, JIF)
                resultado.estrato_final = calcular_estrato_final(
                    resultado.estrato_h5,
                    resultado.estrato_percentil,
                    resultado.estrato_jif,
                )

                resultados_rev.append(resultado)

            # Salva resultados com H5-index e JIF (se disponível)
            salvar_csv(
                resultados_rev,
                args.output / f"revistas_{timestamp}.csv",
                [
                    "sigla",
                    "nome_completo",
                    "issn",
                    "nome_gsm",
                    "h5_index",
                    "h5_median",
                    "estrato_h5",
                    "citescore",
                    "percentil",
                    "area_tematica",
                    "estrato_percentil",
                    "jif",
                    "jif_percentil",
                    "categoria_wos",
                    "estrato_jif",
                    "estrato_final",
                    "url_gsm",
                    "url_scopus",
                    "url_wos",
                    "erro",
                    "data_coleta",
                ],
            )
            salvar_json(resultados_rev, args.output / f"revistas_{timestamp}.json")

            imprimir_tabela_revistas(resultados_rev)

            # Mostra instruções de coleta manual do Scopus apenas se --scopus não foi usado
            if not scopus_client:
                print("\n" + "=" * 75)
                print(" SCOPUS - Coleta Manual Necessária")
                print("=" * 75)
                print("""
⚠️  O Scopus Preview requer JavaScript e não permite scraping direto.

Para obter CiteScore e Percentil das revistas:

1. Acesse: https://www.scopus.com/sources
2. Busque cada revista pelo nome ou ISSN
3. Anote: CiteScore, Percentile, Subject Area
4. Preencha as colunas no arquivo CSV gerado acima

💡 DICA: Use --scopus para coleta automática via API (requer SCOPUS_API_KEY em .env)

Revistas para consultar:
""")
                for r in revistas:
                    issn_info = f" (ISSN: {r['issn']})" if r.get("issn") else ""
                    print(f"   • {r['nome_completo']}{issn_info}")

                print(
                    f"\n📝 Arquivo para preencher: {args.output / f'revistas_{timestamp}.csv'}"
                )
                print(
                    "   Preencha as colunas 'citescore', 'percentil' e 'area_tematica' com dados do Scopus."
                )
                print(
                    "   A coluna 'estrato_percentil' será calculada automaticamente após preencher."
                )

    # -------------------------------------------------------------------------
    # RESUMO
    # -------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print(" CÁLCULO DO ESTRATO (Referência)")
    print("=" * 75)
    print("""
CONFERÊNCIAS (H5-index):          REVISTAS (Percentil):
┌─────────┬───────────┐           ┌─────────┬─────────────┐
│ Estrato │ H5-index  │           │ Estrato │ Percentil   │
├─────────┼───────────┤           ├─────────┼─────────────┤
│ A1      │ >= 35     │           │ A1      │ >= 87.5%    │
│ A2      │ >= 25     │           │ A2      │ >= 75.0%    │
│ A3      │ >= 20     │           │ A3      │ >= 62.5%    │
│ A4      │ >= 15     │           │ A4      │ >= 50.0%    │
│ A5      │ >= 12     │           │ A5      │ >= 37.5%    │
│ A6      │ >= 9      │           │ A6      │ >= 25.0%    │
│ A7      │ >= 6      │           │ A7      │ >= 12.5%    │
│ A8      │ > 0       │           │ A8      │ < 12.5%     │
└─────────┴───────────┘           └─────────┴─────────────┘

NOTA: Conferências podem receber ajuste de +1 ou +2 níveis 
      conforme ranking CE-SBC (Top20/Top10), com saturação em A3.
""")

    print(f"📁 Arquivos salvos em: {args.output.absolute()}")
    print()


if __name__ == "__main__":
    main()
