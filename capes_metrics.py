#!/usr/bin/env python3
"""
CAPES Metrics Collector
=======================
Coleta métricas de periódicos e conferências para avaliação CAPES.
Procedimento 2 - Área de Computação 2025-2028.

Fontes:
- Conferências: Google Scholar Metrics (H5-index) - automático
- Periódicos: Google Scholar Metrics (H5-index) - automático
             + Scopus Preview (CiteScore + Percentil) - automático

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
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

from lib_aux import (
    ConferenciaMetrics,
    RevistaMetrics,
    calcular_estrato_final,
    calcular_estrato_revista,
)
from lib_google import GoogleScholarMetricsScraper
from lib_scopus import ScopusAPIClient
from lib_wos import WebOfScienceAPIClient

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "output"


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
