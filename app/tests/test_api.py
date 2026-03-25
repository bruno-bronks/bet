"""
app/tests/test_api.py
Testes de integração da API FastAPI usando TestClient.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


class TestHealth:
    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "supported_competitions" in data

    def test_root_redirect(self):
        r = client.get("/")
        assert r.status_code == 200


class TestPredictValidation:
    def test_missing_competition(self):
        r = client.post("/api/v1/predict", json={
            "home_team": "Flamengo",
            "away_team": "Palmeiras",
            "match_date": "2024-06-15",
        })
        assert r.status_code == 422  # Validation error

    def test_invalid_competition(self):
        r = client.post("/api/v1/predict", json={
            "competition": "la_liga",
            "home_team": "Real Madrid",
            "away_team": "Barcelona",
            "match_date": "2024-06-15",
        })
        assert r.status_code == 422

    def test_invalid_date_format(self):
        r = client.post("/api/v1/predict", json={
            "competition": "brasileirao",
            "home_team": "Flamengo",
            "away_team": "Palmeiras",
            "match_date": "15-06-2024",  # Wrong format
        })
        assert r.status_code == 422

    def test_same_team_names_accepted_at_api_level(self):
        """API aceita (validação de negócio é no predictor, não no schema)."""
        r = client.post("/api/v1/predict", json={
            "competition": "brasileirao",
            "home_team": "Flamengo",
            "away_team": "Flamengo",
            "match_date": "2024-06-15",
        })
        # Pode retornar 404 (sem dados) ou 500 (predictor error), mas não 422
        assert r.status_code != 422


class TestModels:
    def test_models_endpoint(self):
        r = client.get("/api/v1/models")
        assert r.status_code == 200
        data = r.json()
        assert "models" in data
        assert "total" in data
        assert isinstance(data["models"], list)
