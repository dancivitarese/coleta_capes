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

import requests
from bs4 import BeautifulSoup
import csv
import json
import time
import random
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from urllib.parse import quote_plus

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
    url_gsm: Optional[str] = None
    url_scopus: Optional[str] = None
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
    print(f"\n{'=' * 95}")
    print(" REVISTAS - Métricas Google Scholar (H5) + Scopus (CiteScore/Percentil)")
    print(f"{'=' * 95}")
    print(
        f"{'Sigla':<8} {'Nome':<30} {'H5':>6} {'E-H5':>5} {'CiteScore':>10} {'Percentil':>10} {'E-Pct':>6}"
    )
    print(f"{'-' * 8} {'-' * 30} {'-' * 6} {'-' * 5} {'-' * 10} {'-' * 10} {'-' * 6}")

    for r in resultados:
        nome = (r.nome_gsm or r.nome_completo or r.sigla)[:30]
        h5 = str(r.h5_index) if r.h5_index else "N/A"
        estrato_h5 = r.estrato_h5 or "N/A"
        cs = f"{r.citescore:.1f}" if r.citescore else "N/A"
        pct = f"{r.percentil:.1f}%" if r.percentil else "N/A"
        estrato_pct = r.estrato_percentil or "N/A"
        erro = " ⚠️" if r.erro else ""
        print(
            f"{r.sigla:<8} {nome:<30} {h5:>6} {estrato_h5:>5} {cs:>10} {pct:>10} {estrato_pct:>6}{erro}"
        )

    print()


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================


def main():
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
                resultado = scraper.buscar_revista(
                    rev["sigla"], rev["nome_completo"], rev.get("issn")
                )
                resultados_rev.append(resultado)

                if resultado.erro:
                    print(f"    ⚠️  {resultado.erro}")
                else:
                    print(f"    ✓ H5={resultado.h5_index} → {resultado.estrato_h5}")

            # Salva resultados com H5-index
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
                    "url_gsm",
                    "url_scopus",
                    "erro",
                    "data_coleta",
                ],
            )
            salvar_json(resultados_rev, args.output / f"revistas_{timestamp}.json")

            imprimir_tabela_revistas(resultados_rev)

            # Gera também template Scopus para preenchimento manual
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
