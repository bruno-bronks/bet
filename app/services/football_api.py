"""
app/services/football_api.py
Cliente HTTP para dados de futebol.

Suporta dois provedores (em ordem de prioridade):
  1. football-data.org  — plano gratuito com temporada ATUAL (UCL: CL, Brasileirão: BSA)
  2. api-sports.io      — plano gratuito limitado a 2022-2024

O provedor é selecionado automaticamente pela chave configurada no .env:
  FOOTBALL_DATA_KEY=...   → usa football-data.org (recomendado)
  API_FOOTBALL_KEY=...    → usa api-sports.io (fallback)
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# ── Normalização de nomes ──────────────────────────────────────────────────────

# Mapeamento: nome da API externa → nome raw do football-data.org (padrão do CSV).
# REGRA: football-data.org retorna nomes corretos — NÃO remapear.
#        Apenas api-sports.io e variantes precisam de mapeamento.
TEAM_NAME_MAP: Dict[str, str] = {
    # ── Brasileirão: api-sports.io → football-data.org raw ────────────────────
    "Athletico Paranaense": "CA Paranaense",
    "Atletico Paranaense": "CA Paranaense",
    "Atletico Mineiro": "CA Mineiro",
    "Atlético Mineiro": "CA Mineiro",
    "Atletico-MG": "CA Mineiro",
    "Atlético-MG": "CA Mineiro",
    "Atletico Goianiense": "AC Goianiense",
    "Atlético Goianiense": "AC Goianiense",
    "Atlético GO": "AC Goianiense",
    "America Mineiro": "América FC",
    "América Mineiro": "América FC",
    "América-MG": "América FC",
    "Bahia": "EC Bahia",
    "Esporte Clube Bahia": "EC Bahia",
    "Sport Recife": "SC Recife",
    "Sport Club Recife": "SC Recife",
    "Sport": "SC Recife",
    "Vasco DA Gama": "CR Vasco da Gama",
    "Vasco da Gama": "CR Vasco da Gama",
    "Vasco": "CR Vasco da Gama",
    "Red Bull Bragantino": "RB Bragantino",
    "Rb Bragantino": "RB Bragantino",
    "Bragantino": "RB Bragantino",
    "Fluminense": "Fluminense FC",
    "Corinthians": "SC Corinthians Paulista",
    "Sport Club Corinthians Paulista": "SC Corinthians Paulista",
    "Flamengo": "CR Flamengo",
    "Clube de Regatas do Flamengo": "CR Flamengo",
    "Palmeiras": "SE Palmeiras",
    "Sociedade Esportiva Palmeiras": "SE Palmeiras",
    "Cruzeiro": "Cruzeiro EC",
    "Santos": "Santos FC",
    "Gremio": "Grêmio FBPA",
    "Grêmio": "Grêmio FBPA",
    "Internacional": "SC Internacional",
    "São Paulo": "São Paulo FC",
    "Sao Paulo": "São Paulo FC",
    "Vitoria": "EC Vitória",
    "Vitória": "EC Vitória",
    "Fortaleza": "Fortaleza EC",
    "Juventude": "EC Juventude",
    "Cuiabá": "Cuiabá EC",
    "Cuiaba": "Cuiabá EC",
    "Goias": "Goiás EC",
    "Goiás": "Goiás EC",
    "Ceara": "Ceará SC",
    "Ceará": "Ceará SC",
    "Criciuma": "Criciúma EC",
    "Criciúma": "Criciúma EC",
    "Coritiba": "Coritiba FBC",
    "Mirassol": "Mirassol FC",

    # ── Champions League: api-sports.io → football-data.org raw ───────────────
    "Bayern Munich": "Bayern München",
    "Bayern Munchen": "Bayern München",
    "Paris Saint Germain": "Paris Saint-Germain",
    "PSG": "Paris Saint-Germain",
    "Dortmund": "Borussia Dortmund",
    "Inter": "FC Internazionale Milano",
    "Inter Milan": "FC Internazionale Milano",
    "FC Internazionale": "FC Internazionale Milano",
    "Atletico Madrid": "Club Atlético de Madrid",
    "Atlético Madrid": "Club Atlético de Madrid",
    "Atlético de Madrid": "Club Atlético de Madrid",
    "Rb Leipzig": "RB Leipzig",
    "RasenBallsport Leipzig": "RB Leipzig",
    "Manchester City": "Manchester City FC",
    "Real Madrid": "Real Madrid CF",
    "Barcelona": "FC Barcelona",
    "Arsenal": "Arsenal FC",
    "Chelsea": "Chelsea FC",
    "Liverpool": "Liverpool FC",
    "Juventus": "Juventus FC",
    "Benfica": "Sport Lisboa e Benfica",
    "SL Benfica": "Sport Lisboa e Benfica",
    "Porto": "FC Porto",
    "Ajax": "AFC Ajax",
    "Napoli": "SSC Napoli",
    # Nomes raw football-data.org → padrão interno do CSV with_stats
    "Bayern München": "FC Bayern München",
    "LOSC Lille": "Lille OSC",
    "Feyenoord": "Feyenoord Rotterdam",
    "Sporting CP": "Sporting Clube de Portugal",
}


def _normalize_team(name: str) -> str:
    return TEAM_NAME_MAP.get(name, name)


def _parse_round(round_str: str) -> int | None:
    """Extrai número de strings como 'Regular Season - 8' ou '8'."""
    import re
    m = re.search(r"\d+", str(round_str))
    return int(m.group()) if m else None


# ── Cache TTL ─────────────────────────────────────────────────────────────────

class _TTLCache:
    def __init__(self) -> None:
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str, ttl_seconds: int) -> Optional[Any]:
        if key not in self._store:
            return None
        ts, value = self._store[key]
        if time.monotonic() - ts > ttl_seconds:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)


_cache = _TTLCache()

TTL_FIXTURES  = 3600    # 1 hora
TTL_STANDINGS = 21600   # 6 horas
TTL_RECENT    = 1800    # 30 minutos


# ══════════════════════════════════════════════════════════════════════════════
# PROVEDOR 1: football-data.org (recomendado — temporada atual grátis)
# ══════════════════════════════════════════════════════════════════════════════

# Códigos das competições em football-data.org
_FD_LEAGUE_CODES: Dict[str, str] = {
    "brasileirao": "BSA",
    "champions_league": "CL",
}

# Status de partidas em football-data.org
_FD_STATUS_UPCOMING  = "SCHEDULED,TIMED,POSTPONED"
_FD_STATUS_FINISHED  = "FINISHED"


class FootballDataClient:
    """
    Cliente para api.football-data.org (v4).
    Plano gratuito: 10 req/min, temporada atual incluída.
    Registro em: https://www.football-data.org/client/register
    """

    def __init__(self) -> None:
        self._base = settings.FOOTBALL_DATA_BASE_URL.rstrip("/")

    @property
    def available(self) -> bool:
        return bool(settings.FOOTBALL_DATA_KEY)

    def _headers(self) -> Dict[str, str]:
        return {
            "X-Auth-Token": settings.FOOTBALL_DATA_KEY,
            "Accept": "application/json",
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        url = f"{self._base}/{path.lstrip('/')}"
        try:
            resp = httpx.get(url, headers=self._headers(), params=params or {}, timeout=12.0)
            if resp.status_code == 429:
                logger.warning("football-data.org rate limit atingido")
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"football-data.org HTTP {e.response.status_code} → {url}: {e.response.text[:200]}")
        except Exception as e:
            logger.error(f"football-data.org request error: {e}")
        return None

    def get_fixtures(self, competition: str, days_ahead: int = 21) -> List[Dict[str, Any]]:
        code = _FD_LEAGUE_CODES.get(competition)
        if not code:
            return []

        cache_key = f"fd_fixtures:{competition}:{days_ahead}"
        cached = _cache.get(cache_key, TTL_FIXTURES)
        if cached is not None:
            return cached

        today = date.today()
        to_date = today + timedelta(days=days_ahead)
        data = self._get(f"competitions/{code}/matches", {
            "status": _FD_STATUS_UPCOMING,
            "dateFrom": today.isoformat(),
            "dateTo": to_date.isoformat(),
        })

        result = self._parse_matches(data)
        _cache.set(cache_key, result)
        return result

    def get_recent(self, competition: str, limit: int = 15) -> List[Dict[str, Any]]:
        code = _FD_LEAGUE_CODES.get(competition)
        if not code:
            return []

        cache_key = f"fd_recent:{competition}:{limit}"
        cached = _cache.get(cache_key, TTL_RECENT)
        if cached is not None:
            return cached

        today = date.today()
        from_date = today - timedelta(days=45)
        data = self._get(f"competitions/{code}/matches", {
            "status": _FD_STATUS_FINISHED,
            "dateFrom": from_date.isoformat(),
            "dateTo": today.isoformat(),
        })

        result = self._parse_matches(data)
        result = sorted(result, key=lambda x: x["date"], reverse=True)[:limit]
        _cache.set(cache_key, result)
        return result

    def get_standings(self, competition: str) -> Dict[str, Any]:
        code = _FD_LEAGUE_CODES.get(competition)
        if not code:
            return {"standings": [], "season": 0}

        cache_key = f"fd_standings:{competition}"
        cached = _cache.get(cache_key, TTL_STANDINGS)
        if cached is not None:
            return cached

        data = self._get(f"competitions/{code}/standings")
        result = self._parse_standings(data)
        _cache.set(cache_key, result)
        return result

    def _parse_matches(self, data: Optional[Dict]) -> List[Dict[str, Any]]:
        if not data:
            return []
        result = []
        for m in data.get("matches", []):
            try:
                # Data e hora (UTC → exibir como está)
                utc_date: str = m.get("utcDate", "")
                date_part = utc_date[:10] if utc_date else ""
                time_part = utc_date[11:16] if len(utc_date) > 16 else "00:00"

                status_raw = m.get("status", "")
                # Mapear status football-data.org → nosso padrão
                status = {
                    "SCHEDULED": "NS", "TIMED": "NS", "POSTPONED": "PST",
                    "CANCELLED": "CANC", "SUSPENDED": "SUSP",
                    "IN_PLAY": "LIVE", "PAUSED": "HT",
                    "FINISHED": "FT", "AWARDED": "AW",
                }.get(status_raw, status_raw)

                score = m.get("score", {})
                ft = score.get("fullTime", {})

                venue_info = m.get("venue") or ""

                # Árbitro principal (football-data.org retorna lista de árbitros)
                referees = m.get("referees", [])
                referee_name = next(
                    (r.get("name", "") for r in referees if r.get("type") == "REFEREE"),
                    referees[0].get("name", "") if referees else "",
                )

                result.append({
                    "fixture_id": m.get("id", 0),
                    "home_team": _normalize_team(m.get("homeTeam", {}).get("name", "")),
                    "away_team": _normalize_team(m.get("awayTeam", {}).get("name", "")),
                    "home_team_logo": m.get("homeTeam", {}).get("crest", ""),
                    "away_team_logo": m.get("awayTeam", {}).get("crest", ""),
                    "date": date_part,
                    "time": time_part,
                    "matchday": m.get("matchday"),
                    "stage": m.get("stage", ""),
                    "venue": venue_info,
                    "status": status,
                    "home_score": ft.get("home"),
                    "away_score": ft.get("away"),
                    "referee": referee_name or None,
                })
            except Exception as e:
                logger.debug(f"Match parse error: {e}")
        return result

    def _parse_standings(self, data: Optional[Dict]) -> Dict[str, Any]:
        if not data:
            return {"standings": [], "season": 0}
        try:
            season_year = data.get("season", {}).get("startDate", "0000")[:4]
            season = int(season_year) if season_year.isdigit() else 0

            # Pegar tabela total (type=TOTAL)
            tables = data.get("standings", [])
            total_table = next(
                (t["table"] for t in tables if t.get("type") == "TOTAL"),
                tables[0]["table"] if tables else []
            )

            standings = []
            for entry in total_table:
                team = entry.get("team", {})
                form_raw = entry.get("form") or ""
                # football-data.org usa W/D/L
                form = form_raw.replace(",", "").replace("W", "W").replace("D", "D").replace("L", "L")
                standings.append({
                    "position": entry.get("position", 0),
                    "team": _normalize_team(team.get("name", "")),
                    "team_logo": team.get("crest", ""),
                    "played": entry.get("playedGames", 0),
                    "won": entry.get("won", 0),
                    "drawn": entry.get("draw", 0),
                    "lost": entry.get("lost", 0),
                    "goals_for": entry.get("goalsFor", 0),
                    "goals_against": entry.get("goalsAgainst", 0),
                    "goal_diff": entry.get("goalDifference", 0),
                    "points": entry.get("points", 0),
                    "form": form,
                    "description": entry.get("description") or "",
                })
            return {"standings": standings, "season": season}
        except Exception as e:
            logger.error(f"football-data.org standings parse error: {e}")
            return {"standings": [], "season": 0}


# ══════════════════════════════════════════════════════════════════════════════
# PROVEDOR 2: api-sports.io (fallback — plano gratuito até 2024)
# ══════════════════════════════════════════════════════════════════════════════

_AS_LEAGUE_IDS: Dict[str, int] = {
    "brasileirao": 71,
    "champions_league": 2,
}

def _current_season_apisports(competition: str) -> int:
    today = date.today()
    if competition == "brasileirao":
        return today.year
    else:
        # UCL: temporada começa em julho (ex: 2025/26 = season 2025)
        return today.year if today.month >= 7 else today.year - 1


class ApiSportsClient:
    """Fallback: api-sports.io (apenas dados até 2024 no plano gratuito)."""

    def __init__(self) -> None:
        self._base = settings.API_FOOTBALL_BASE_URL.rstrip("/")

    @property
    def available(self) -> bool:
        return bool(settings.API_FOOTBALL_KEY)

    def _headers(self) -> Dict[str, str]:
        return {
            "x-apisports-key": settings.API_FOOTBALL_KEY,
            "Accept": "application/json",
        }

    def _get(self, path: str, params: Dict[str, Any]) -> Optional[Dict]:
        url = f"{self._base}/{path.lstrip('/')}"
        try:
            resp = httpx.get(url, headers=self._headers(), params=params, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            errors = data.get("errors", {})
            if errors:
                logger.error(f"api-sports.io error: {errors}")
                return None
            return data
        except Exception as e:
            logger.error(f"api-sports.io request failed: {e}")
        return None

    def _parse_fixtures(self, data: Optional[Dict]) -> List[Dict[str, Any]]:
        if not data:
            return []
        result = []
        for item in data.get("response", []):
            try:
                f = item.get("fixture", {})
                home = item.get("teams", {}).get("home", {})
                away = item.get("teams", {}).get("away", {})
                goals = item.get("goals", {})
                league = item.get("league", {})
                dt_str: str = f.get("date", "")
                if "T" in dt_str:
                    date_part, time_part = dt_str.split("T")
                    time_part = time_part[:5]
                else:
                    date_part = dt_str[:10]
                    time_part = "00:00"
                # api-sports.io retorna "Nome, Nacionalidade" ou apenas o nome
                referee_raw = f.get("referee") or ""
                referee_name = referee_raw.split(",")[0].strip() if referee_raw else None

                result.append({
                    "fixture_id": f.get("id", 0),
                    "home_team": _normalize_team(home.get("name", "")),
                    "away_team": _normalize_team(away.get("name", "")),
                    "home_team_logo": home.get("logo", ""),
                    "away_team_logo": away.get("logo", ""),
                    "date": date_part,
                    "time": time_part,
                    "matchday": _parse_round(league.get("round", "")),
                    "stage": league.get("round", ""),
                    "venue": f.get("venue", {}).get("name", ""),
                    "status": f.get("status", {}).get("short", "NS"),
                    "home_score": goals.get("home"),
                    "away_score": goals.get("away"),
                    "referee": referee_name or None,
                })
            except Exception as e:
                logger.debug(f"api-sports.io fixture parse error: {e}")
        return result

    def _parse_standings(self, data: Optional[Dict], season: int) -> Dict[str, Any]:
        if not data:
            return {"standings": [], "season": season}
        try:
            leagues = data.get("response", [])
            if not leagues:
                return {"standings": [], "season": season}
            standings_raw = leagues[0].get("league", {}).get("standings", [[]])[0]
            standings = []
            for entry in standings_raw:
                team = entry.get("team", {})
                all_s = entry.get("all", {})
                goals = all_s.get("goals", {})
                standings.append({
                    "position": entry.get("rank", 0),
                    "team": _normalize_team(team.get("name", "")),
                    "team_logo": team.get("logo", ""),
                    "played": all_s.get("played", 0),
                    "won": all_s.get("win", 0),
                    "drawn": all_s.get("draw", 0),
                    "lost": all_s.get("lose", 0),
                    "goals_for": goals.get("for", 0),
                    "goals_against": goals.get("against", 0),
                    "goal_diff": entry.get("goalsDiff", 0),
                    "points": entry.get("points", 0),
                    "form": entry.get("form", ""),
                    "description": entry.get("description", ""),
                })
            return {"standings": standings, "season": season}
        except Exception as e:
            logger.error(f"api-sports.io standings parse error: {e}")
            return {"standings": [], "season": season}

    def get_fixtures(self, competition: str, days_ahead: int = 21) -> List[Dict[str, Any]]:
        league_id = _AS_LEAGUE_IDS.get(competition)
        if not league_id:
            return []
        today = date.today()
        season = _current_season_apisports(competition)
        is_historical = season < today.year
        cache_key = f"as_fixtures:{competition}:{season}"
        cached = _cache.get(cache_key, TTL_FIXTURES)
        if cached is not None:
            return cached
        if is_historical:
            if competition == "brasileirao":
                from_date, to_date = date(season, 11, 1), date(season, 12, 31)
            else:
                from_date, to_date = date(season, 3, 1), date(season, 5, 31)
            status = "FT-AET-PEN"
        else:
            from_date, to_date = today, today + timedelta(days=days_ahead)
            status = "NS-TBD-PST"
        data = self._get("fixtures", {
            "league": league_id, "season": season,
            "from": from_date.isoformat(), "to": to_date.isoformat(),
            "status": status, "timezone": "America/Sao_Paulo",
        })
        result = self._parse_fixtures(data)
        if is_historical:
            result = sorted(result, key=lambda x: x["date"], reverse=True)
        _cache.set(cache_key, result)
        return result

    def get_recent(self, competition: str, limit: int = 15) -> List[Dict[str, Any]]:
        league_id = _AS_LEAGUE_IDS.get(competition)
        if not league_id:
            return []
        season = _current_season_apisports(competition)
        cache_key = f"as_recent:{competition}:{season}"
        cached = _cache.get(cache_key, TTL_RECENT)
        if cached is not None:
            return cached
        today = date.today()
        from_date = today - timedelta(days=60)
        data = self._get("fixtures", {
            "league": league_id, "season": season,
            "from": from_date.isoformat(), "to": today.isoformat(),
            "status": "FT-AET-PEN", "timezone": "America/Sao_Paulo",
        })
        result = self._parse_fixtures(data)
        result = sorted(result, key=lambda x: x["date"], reverse=True)[:limit]
        _cache.set(cache_key, result)
        return result

    def get_referee_stats(
        self,
        referee: str,
        competition: str,
        home_team: str,
        away_team: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Busca estatísticas de cartões para um árbitro via api-sports.io.
        Retorna médias gerais e por time (quando o time jogou com este árbitro).
        Faz no máximo 1 + 3 chamadas à API; resultado cacheado 24h por árbitro+competição.
        """
        if not self.available:
            return None

        league_id = _AS_LEAGUE_IDS.get(competition)
        if not league_id:
            return None

        season = _current_season_apisports(competition)
        referee_clean = referee.split(",")[0].strip()

        cache_key = f"as_referee:{referee_clean.lower()}:{competition}:{home_team}:{away_team}"
        cached = _cache.get(cache_key, 86400)  # 24h
        if cached is not None:
            return cached

        # 1) Busca partidas recentes com este árbitro na competição
        data = self._get("fixtures", {
            "referee": referee_clean,
            "league": league_id,
            "season": season,
            "status": "FT-AET-PEN",
            "last": 20,
        })
        fixtures = (data or {}).get("response", [])
        if not fixtures:
            _cache.set(cache_key, None)
            return None

        fixture_ids = [f["fixture"]["id"] for f in fixtures]
        matches_total = len(fixture_ids)

        # 2) Busca estatísticas de até 3 partidas mais recentes (economiza créditos)
        total_yellow: list[float] = []
        total_red: list[float] = []
        home_cards: list[float] = []
        away_cards: list[float] = []

        for fid in fixture_ids[:3]:
            stats_data = self._get("fixtures/statistics", {"fixture": fid})
            if not stats_data:
                continue

            game_yellow = 0.0
            game_red = 0.0
            for team_stats in (stats_data or {}).get("response", []):
                team_name = _normalize_team(team_stats.get("team", {}).get("name", ""))
                statistics = team_stats.get("statistics", [])
                yc = next((s.get("value") or 0 for s in statistics if s.get("type") == "Yellow Cards"), 0)
                rc = next((s.get("value") or 0 for s in statistics if s.get("type") == "Red Cards"), 0)
                game_yellow += yc
                game_red += rc
                if team_name == home_team:
                    home_cards.append(yc + rc)
                elif team_name == away_team:
                    away_cards.append(yc + rc)

            total_yellow.append(game_yellow)
            total_red.append(game_red)

        if not total_yellow:
            _cache.set(cache_key, None)
            return None

        n = len(total_yellow)
        result: Dict[str, Any] = {
            "name": referee,
            "matches_analyzed": matches_total,
            "avg_yellow_per_game": round(sum(total_yellow) / n, 2),
            "avg_red_per_game": round(sum(total_red) / n, 2),
            "avg_cards_per_game": round((sum(total_yellow) + sum(total_red)) / n, 2),
            "avg_cards_home_team": round(sum(home_cards) / len(home_cards), 2) if home_cards else None,
            "avg_cards_away_team": round(sum(away_cards) / len(away_cards), 2) if away_cards else None,
            "home_team_matches": len(home_cards),
            "away_team_matches": len(away_cards),
        }
        _cache.set(cache_key, result)
        return result

    def get_standings(self, competition: str) -> Dict[str, Any]:
        league_id = _AS_LEAGUE_IDS.get(competition)
        if not league_id:
            return {"standings": [], "season": 0}
        season = _current_season_apisports(competition)
        cache_key = f"as_standings:{competition}:{season}"
        cached = _cache.get(cache_key, TTL_STANDINGS)
        if cached is not None:
            return cached
        data = self._get("standings", {"league": league_id, "season": season})
        result = self._parse_standings(data, season)
        _cache.set(cache_key, result)
        return result


# ══════════════════════════════════════════════════════════════════════════════
# Facade: seleciona automaticamente o provedor disponível
# ══════════════════════════════════════════════════════════════════════════════

class FootballAPIClient:
    """
    Fachada unificada. Tenta os dois provedores e usa o que retornar dados:
      1. football-data.org (FOOTBALL_DATA_KEY) — temporada atual, grátis
      2. api-sports.io    (API_FOOTBALL_KEY)   — temporada atual, 100 req/dia
    Se o primário retornar vazio, tenta o secundário automaticamente.
    """

    def __init__(self) -> None:
        self._fd  = FootballDataClient()
        self._as  = ApiSportsClient()

    def get_fixtures(self, competition: str, days_ahead: int = 21) -> List[Dict[str, Any]]:
        if self._fd.available:
            result = self._fd.get_fixtures(competition, days_ahead)
            if result:
                return result
        if self._as.available:
            logger.info(f"football-data.org sem fixtures para {competition} — tentando api-sports.io")
            return self._as.get_fixtures(competition, days_ahead)
        logger.warning("Nenhuma chave de API configurada")
        return []

    def get_recent(self, competition: str, limit: int = 15) -> List[Dict[str, Any]]:
        if self._fd.available:
            result = self._fd.get_recent(competition, limit)
            if result:
                return result
        if self._as.available:
            return self._as.get_recent(competition, limit)
        return []

    def get_standings(self, competition: str) -> Dict[str, Any]:
        if self._fd.available:
            result = self._fd.get_standings(competition)
            if result.get("standings"):
                return result
        if self._as.available:
            return self._as.get_standings(competition)
        return {"standings": [], "season": 0}

    def get_referee_stats(
        self,
        referee: str,
        competition: str,
        home_team: str,
        away_team: str,
    ) -> Optional[Dict[str, Any]]:
        """Estatísticas do árbitro via api-sports.io (requer API_FOOTBALL_KEY)."""
        if self._as.available:
            return self._as.get_referee_stats(referee, competition, home_team, away_team)
        return None


# Singleton
football_api = FootballAPIClient()
