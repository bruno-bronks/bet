"""
scripts/fetch_stats_incremental.py
Busca estatísticas reais (chutes, escanteios, cartões, faltas) via api-sports.io
de forma incremental: até 90 partidas por execução (plano gratuito = 100 req/dia).

Fluxo:
  1. Lista fixtures de cada temporada/liga e salva cache local
  2. A cada execução, busca stats de até 90 fixtures pendentes
  3. Quando tiver stats suficientes, mistura com o CSV de treinamento e retreina

Uso:
  python scripts/fetch_stats_incremental.py              # busca stats (modo padrão)
  python scripts/fetch_stats_incremental.py --list       # só lista fixtures, sem buscar stats
  python scripts/fetch_stats_incremental.py --status     # mostra progresso
  python scripts/fetch_stats_incremental.py --apply      # aplica cache ao CSV e retreina
  python scripts/fetch_stats_incremental.py --limit 50   # limita a 50 req nesta execução
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# ── Configuração ──────────────────────────────────────────────────────────────

_BASE = "https://v3.football.api-sports.io"
_KEY = settings.API_FOOTBALL_KEY

# Ligas + temporadas (api-sports.io usa season=2022, 2023, 2024 para plano gratuito)
_LEAGUES = {
    "brasileirao": {"id": 71,  "seasons": [2022, 2023, 2024]},
    "champions_league": {"id": 2, "seasons": [2022, 2023, 2024]},  # 2022 = 2022/23
}

# Cache local
_CACHE_PATH = settings.RAW_DATA_DIR / "api_sports_stats_cache.json"

# Rate limit: 10 req/min → 7s entre requests (margem de segurança)
# Plano gratuito: 100 req/dia → 90 stats + 6 listagens por execução
_DEFAULT_STATS_LIMIT = 90
_SLEEP_BETWEEN = 7.0  # segundos entre requests (10 req/min = 6s mínimo)


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict | None:
    url = f"{_BASE}/{path.lstrip('/')}"
    headers = {"x-apisports-key": _KEY}
    try:
        resp = httpx.get(url, headers=headers, params=params or {}, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        errors = data.get("errors", {})
        if errors:
            logger.warning(f"API error: {errors}")
            return None
        return data
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP {e.response.status_code} → {url}")
    except Exception as e:
        logger.error(f"Request error: {e}")
    return None


# ── Cache ─────────────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if _CACHE_PATH.exists():
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    return {"fixtures": {}, "stats": {}, "no_data": []}


def save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Normalização de times ─────────────────────────────────────────────────────

def _norm(name: str) -> str:
    """Normaliza nome do time para matching entre provedores."""
    return name.lower().strip().replace("  ", " ")


# ── Listagem de fixtures ──────────────────────────────────────────────────────

def list_fixtures(cache: dict) -> int:
    """Lista todos os fixtures de cada liga/temporada. Retorna quantos requests foram feitos."""
    req_count = 0
    for comp, conf in _LEAGUES.items():
        league_id = conf["id"]
        for season in conf["seasons"]:
            key = f"{comp}_{season}"
            if key in cache["fixtures"]:
                logger.info(f"  {key}: {len(cache['fixtures'][key])} fixtures já em cache")
                continue

            logger.info(f"  Listando {comp} {season}...")
            data = _get("fixtures", {"league": league_id, "season": season, "status": "FT"})
            req_count += 1
            time.sleep(_SLEEP_BETWEEN)

            if not data:
                cache["fixtures"][key] = []
                continue

            fixtures = []
            for f in data.get("response", []):
                fix = f.get("fixture", {})
                home = f.get("teams", {}).get("home", {})
                away = f.get("teams", {}).get("away", {})
                date_str = fix.get("date", "")[:10]
                fixtures.append({
                    "id": fix.get("id"),
                    "date": date_str,
                    "home": home.get("name", ""),
                    "away": away.get("name", ""),
                })
            cache["fixtures"][key] = fixtures
            logger.info(f"  {key}: {len(fixtures)} fixtures encontrados")

    save_cache(cache)
    return req_count


# ── Busca de estatísticas ─────────────────────────────────────────────────────

def _parse_team_stats(statistics: list[dict]) -> dict:
    """Converte lista de stats da API em dict com nossos nomes."""
    mapping = {
        "Shots on Goal":    "shots_on_target",
        "Shots off Goal":   "shots_off_target",
        "Total Shots":      "shots",
        "Corner Kicks":     "corners",
        "Fouls":            "fouls",
        "Yellow Cards":     "yellow_cards",
        "Red Cards":        "red_cards",
        "Ball Possession":  "possession",
        "Goalkeeper Saves": "saves",
    }
    result = {}
    for item in statistics:
        key = mapping.get(item.get("type", ""))
        if not key:
            continue
        val = item.get("value")
        if val is None:
            continue
        if isinstance(val, str) and val.endswith("%"):
            try:
                val = float(val.rstrip("%"))
            except ValueError:
                continue
        try:
            result[key] = float(val) if "." in str(val) else int(val)
        except (TypeError, ValueError):
            result[key] = 0
    return result


def fetch_stats(cache: dict, limit: int = _DEFAULT_STATS_LIMIT) -> int:
    """Busca estatísticas para fixtures ainda pendentes. Retorna quantos requests foram feitos."""
    no_data_set = set(cache.get("no_data", []))
    req_count = 0

    for comp, conf in _LEAGUES.items():
        for season in conf["seasons"]:
            key = f"{comp}_{season}"
            fixtures = cache["fixtures"].get(key, [])

            for f in fixtures:
                if req_count >= limit:
                    logger.info(f"Limite de {limit} requests atingido para esta execução.")
                    cache["no_data"] = list(no_data_set)
                    save_cache(cache)
                    return req_count

                fid = str(f["id"])
                if fid in cache["stats"] or fid in no_data_set:
                    continue  # já temos

                data = _get("fixtures/statistics", {"fixture": fid})
                req_count += 1
                time.sleep(_SLEEP_BETWEEN)

                if not data or not data.get("response"):
                    no_data_set.add(fid)
                    continue

                response = data["response"]
                if len(response) < 2:
                    no_data_set.add(fid)
                    continue

                # Identifica home/away pela ordem (time da casa sempre primeiro)
                home_stats = _parse_team_stats(response[0].get("statistics", []))
                away_stats = _parse_team_stats(response[1].get("statistics", []))

                cache["stats"][fid] = {
                    "home_shots":             home_stats.get("shots", 0),
                    "home_shots_on_target":   home_stats.get("shots_on_target", 0),
                    "home_corners":           home_stats.get("corners", 0),
                    "home_fouls":             home_stats.get("fouls", 0),
                    "home_yellow_cards":      home_stats.get("yellow_cards", 0),
                    "home_red_cards":         home_stats.get("red_cards", 0),
                    "home_possession":        home_stats.get("possession", 50.0),
                    "away_shots":             away_stats.get("shots", 0),
                    "away_shots_on_target":   away_stats.get("shots_on_target", 0),
                    "away_corners":           away_stats.get("corners", 0),
                    "away_fouls":             away_stats.get("fouls", 0),
                    "away_yellow_cards":      away_stats.get("yellow_cards", 0),
                    "away_red_cards":         away_stats.get("red_cards", 0),
                    "away_possession":        away_stats.get("possession", 50.0),
                    # lookup key para merge
                    "_date": f["date"],
                    "_home": _norm(f["home"]),
                    "_away": _norm(f["away"]),
                }

    cache["no_data"] = list(no_data_set)
    save_cache(cache)
    return req_count


# ── Status ────────────────────────────────────────────────────────────────────

def show_status(cache: dict) -> None:
    print("\n--- Status do cache de estatisticas -----------------------------------")
    total_fix = sum(len(v) for v in cache["fixtures"].values())
    total_stats = len(cache["stats"])
    no_data = len(cache.get("no_data", []))
    pending = total_fix - total_stats - no_data

    for key, fixtures in sorted(cache["fixtures"].items()):
        fids = {str(f["id"]) for f in fixtures}
        fetched = sum(1 for fid in fids if fid in cache["stats"])
        nd = sum(1 for fid in fids if fid in set(cache.get("no_data", [])))
        pend = len(fids) - fetched - nd
        pct = fetched / len(fids) * 100 if fids else 0
        print(f"  {key:35s}  {fetched:3d}/{len(fids):3d} ({pct:5.1f}%)  pendentes={pend}  sem_dados={nd}")

    print(f"\n  Total fixtures: {total_fix}")
    print(f"  Com stats reais: {total_stats} ({total_stats/total_fix*100:.1f}%)" if total_fix else "")
    print(f"  Pendentes: {pending}")
    print(f"  Sem dados: {no_data}")
    est_days = pending // _DEFAULT_STATS_LIMIT + 1 if pending > 0 else 0
    print(f"  Estimativa: ~{est_days} execuções para completar")
    print()


# ── Aplicar stats reais ao CSV de treinamento ─────────────────────────────────

def apply_stats(cache: dict) -> None:
    """Substitui stats sintéticas por reais no CSV de treinamento e retreina."""
    import pandas as pd
    from app.models.registry import ModelRegistry
    from app.training.trainer import ModelTrainer

    if not cache["stats"]:
        print("Nenhuma stat em cache ainda. Execute sem --apply primeiro.")
        return

    # Indexa stats por (date, home_norm, away_norm) para match rápido
    stats_index: dict[tuple, dict] = {}
    for fid, s in cache["stats"].items():
        key = (s.get("_date", ""), s.get("_home", ""), s.get("_away", ""))
        stats_index[key] = s

    processed_dir = settings.PROCESSED_DATA_DIR
    applied_total = 0

    for comp in _LEAGUES.keys():
        files = sorted(processed_dir.glob(f"{comp}_real_*.csv"))
        if not files:
            logger.warning(f"Nenhum CSV encontrado para {comp}. Execute fetch_and_train.py primeiro.")
            continue

        df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        original_len = len(df)
        applied = 0

        for idx, row in df.iterrows():
            key = (
                str(row["date"])[:10],
                _norm(str(row["home_team"])),
                _norm(str(row["away_team"])),
            )
            if key not in stats_index:
                continue

            s = stats_index[key]
            for col in ["home_shots", "home_shots_on_target", "home_corners", "home_fouls",
                        "home_yellow_cards", "home_red_cards", "home_possession",
                        "away_shots", "away_shots_on_target", "away_corners", "away_fouls",
                        "away_yellow_cards", "away_red_cards", "away_possession"]:
                if col in s:
                    df.at[idx, col] = s[col]
            applied += 1

        # Salva CSV com stats reais aplicadas
        out_path = processed_dir / f"{comp}_real_with_stats.csv"
        df.to_csv(out_path, index=False)
        applied_total += applied
        pct = applied / original_len * 100 if original_len else 0
        print(f"  {comp}: {applied}/{original_len} partidas com stats reais ({pct:.1f}%) → {out_path.name}")

    print(f"\nTotal aplicado: {applied_total} partidas")

    # Retreina modelos
    print("\nReiniciando treinamento com stats reais...")
    from app.data.preprocess import MatchPreprocessor
    from app.features.feature_pipeline import FeaturePipeline

    registry = ModelRegistry()
    for comp in _LEAGUES.keys():
        out_path = processed_dir / f"{comp}_real_with_stats.csv"
        if not out_path.exists():
            continue
        df = pd.read_csv(out_path, parse_dates=["date"]).sort_values("date")
        trainer = ModelTrainer(competition=comp, registry=registry)
        metrics = trainer.train_all(df)
        print(f"\n{'='*50}")
        print(f"  {comp}")
        print(f"{'='*50}")
        for m_name, m in metrics.items():
            print(f"  {m_name}: {m}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Busca incremental de stats via api-sports.io")
    parser.add_argument("--list",   action="store_true", help="Só lista fixtures (sem buscar stats)")
    parser.add_argument("--status", action="store_true", help="Mostra progresso do cache")
    parser.add_argument("--apply",  action="store_true", help="Aplica stats ao CSV e retreina")
    parser.add_argument("--limit",  type=int, default=_DEFAULT_STATS_LIMIT,
                        help=f"Máx de requests de stats nesta execução (padrão: {_DEFAULT_STATS_LIMIT})")
    args = parser.parse_args()

    if not _KEY:
        print("ERRO: API_FOOTBALL_KEY não configurada no .env")
        sys.exit(1)

    cache = load_cache()

    if args.status:
        if not cache["fixtures"]:
            print("Cache vazio. Execute sem flags para começar.")
        else:
            show_status(cache)
        return

    if args.apply:
        apply_stats(cache)
        return

    # Passo 1: garantir que fixtures estão listados
    print("Verificando lista de fixtures...")
    list_req = list_fixtures(cache)
    if list_req > 0:
        print(f"  {list_req} requests usados para listagem")

    if args.list:
        show_status(cache)
        return

    # Passo 2: buscar stats incrementalmente
    total_fix = sum(len(v) for v in cache["fixtures"].values())
    already = len(cache["stats"])
    pending = total_fix - already - len(cache.get("no_data", []))

    if pending == 0:
        print("Todas as stats já estão em cache! Use --apply para retreinar.")
        show_status(cache)
        return

    print(f"\nBuscando stats ({pending} pendentes, limite={args.limit} nesta execução)...")
    fetched = fetch_stats(cache, limit=args.limit)
    print(f"\n  {fetched} requests feitos nesta execução")
    show_status(cache)

    total_stats = len(cache["stats"])
    if total_stats > 0:
        pct = total_stats / total_fix * 100 if total_fix else 0
        print(f"Progresso: {total_stats}/{total_fix} ({pct:.1f}%) partidas com stats reais")
        print("Execute novamente amanhã para continuar. Use --apply quando tiver dados suficientes.")


if __name__ == "__main__":
    main()
