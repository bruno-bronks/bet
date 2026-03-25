# Football Probabilistic Analysis Platform

Plataforma de análise probabilística para partidas de futebol.
Limitada às competições: **Brasileirão** e **UEFA Champions League**.

> **AVISO IMPORTANTE**: Todas as saídas são estimativas probabilísticas baseadas em padrões históricos.
> Não constituem previsão garantida. Incerteza estatística é inerente ao sistema.

---

## Visão do Projeto

Sistema de inteligência esportiva capaz de:
- Ingerir e processar dados históricos de partidas
- Gerar features estatísticas e temporais
- Treinar modelos probabilísticos para múltiplos eventos
- Expor previsões via API REST
- Explicar as previsões com feature importance e linguagem natural

---

## Arquitetura

```
data/ (raw CSVs)
  └─► MatchPreprocessor (data/preprocess.py)
        └─► FeaturePipeline (features/)
              └─► ModelTrainer (training/trainer.py)
                    ├── OutcomeModel (1X2)
                    ├── GoalsModel (Poisson)
                    ├── CornersModel
                    ├── CardsModel
                    └── TimeWindowEnsemble
                          └─► ModelRegistry (models_artifacts/)
                                └─► FootballPredictor (inference/predictor.py)
                                      └─► FastAPI (api/)
```

---

## Estrutura de Pastas

```
bet/
├── app/
│   ├── api/            ← FastAPI: main.py, rotas, schemas
│   ├── core/           ← config, logger, constants, utils
│   ├── data/           ← ingestão, pré-processamento, repositório
│   ├── features/       ← ELO, rolling, temporal, H2H, pipeline
│   ├── models/         ← outcome, goals, corners, cards, calibração
│   ├── training/       ← trainer, splitters, avaliação, backtest
│   ├── inference/      ← predictor, explicabilidade, serializer
│   ├── live/           ← base para inferência in-play
│   ├── db/             ← SQLAlchemy: models, session
│   └── tests/          ← pytest
├── data/
│   ├── raw/            ← CSVs brutos
│   ├── processed/      ← CSVs processados
│   └── samples/        ← dados sintéticos de exemplo
├── models_artifacts/   ← modelos treinados (.joblib)
├── scripts/
│   ├── create_sample_data.py
│   ├── train_all.py
│   └── run_inference.py
├── requirements.txt
└── .env.example
```

---

## Instalação

```bash
# Clone ou acesse o diretório do projeto
cd bet

# Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# Instale as dependências
pip install -r requirements.txt
```

---

## Execução Rápida (End-to-End)

### 1. Gerar dados de exemplo

```bash
python scripts/create_sample_data.py
```

Cria CSVs sintéticos realistas em `data/samples/` e `data/processed/`.

### 2. Treinar os modelos

```bash
# Treinar para todas as competições
python scripts/train_all.py

# Treinar apenas Brasileirão
python scripts/train_all.py --competition brasileirao
```

### 3. Executar inferência via linha de comando

```bash
python scripts/run_inference.py \
  --competition brasileirao \
  --home "Flamengo" \
  --away "Palmeiras" \
  --date 2024-06-15
```

### 4. Iniciar a API

```bash
uvicorn app.api.main:app --reload --port 8000
```

Acesse a documentação interativa: http://localhost:8000/docs

---

## API

### GET /health
Verifica se a API está operacional.

### POST /api/v1/predict
Gera análise probabilística para uma partida.

**Request body:**
```json
{
  "competition": "brasileirao",
  "home_team": "Flamengo",
  "away_team": "Palmeiras",
  "match_date": "2024-06-15",
  "include_explanation": false
}
```

**Response:** Probabilidades de resultado, gols, escanteios, cartões e janelas temporais.

### POST /api/v1/train
Treina (ou re-treina) todos os modelos para uma competição.

### GET /api/v1/models
Lista todos os modelos registrados.

---

## Eventos Estimados

| Evento | Modelo |
|---|---|
| Vitória mandante / Empate / Vitória visitante | LightGBM multiclasse calibrado |
| Gols esperados (mandante/visitante) | Poisson Regression |
| Over/Under 0.5, 1.5, 2.5, 3.5, 4.5 | Derivado do Poisson |
| Ambas as equipes marcam | Derivado do Poisson |
| Placares mais prováveis | Poisson bivariado |
| Escanteios | Poisson Regression |
| Cartões | Poisson Regression |
| Gol nos primeiros 15 min | LightGBM binário calibrado |
| Gol nos últimos 15 min | LightGBM binário calibrado |
| Gol no 1º / 2º tempo | LightGBM binário calibrado |

---

## Features Principais

- **ELO Rating** dinâmico por time (calculado sem data leakage)
- **Médias móveis** (janelas 3, 5, 10 partidas): gols, escanteios, cartões, xG
- **Forma recente** ponderada (3pts vitória, 1pt empate)
- **Confrontos diretos** (H2H): taxa de vitória/empate nos últimos N jogos
- **Força ofensiva/defensiva** relativa à média da competição
- **Features temporais**: dias de descanso, rodada, fase, progresso da temporada
- **Features específicas por competição**: fases UCL, rodadas Brasileirão

---

## Avaliação de Modelos

| Métrica | Uso |
|---|---|
| Brier Score | Qualidade de calibração probabilística |
| Log-Loss | Sharpness das probabilidades |
| ECE (Expected Calibration Error) | Desvio de calibração |
| Accuracy | Acerto de classe modal |
| MAE / RMSE | Modelos de regressão (gols, escanteios) |
| ROC-AUC | Modelos binários (janelas temporais) |

---

## Backtesting

O sistema usa **walk-forward validation** (janela expansível):
- Treino sempre precede validação cronologicamente
- Sem data leakage futuro
- Métricas agregadas por fold

```bash
# Exemplo no código:
from app.training.backtest import Backtester
backtester = Backtester("brasileirao", n_splits=5)
results_df = backtester.run(df)
```

---

## Limitações

1. **Dados sintéticos** — Os dados de exemplo não representam resultados reais
2. **Pequena amostra** — Times com poucos jogos têm estimativas menos confiáveis
3. **Sem dados em tempo real** — O módulo `live/` é uma base para futura implementação
4. **Independência de Poisson** — O modelo bivariado assume gols independentes (sem correção Dixon-Coles)
5. **Features estáticas** — Lesões, suspensões e mudanças táticas não são capturadas automaticamente
6. **Derive temporal** — Modelos ficam desatualizados sem re-treino periódico

---

## Próximos Passos

- [ ] Integrar fonte de dados real (football-data.org, Sofascore, Opta)
- [ ] Implementar modelo Dixon-Coles para placares baixos
- [ ] Adicionar modelo live/in-play com estado completo
- [ ] Pipeline de re-treino automatizado (scheduler)
- [ ] Dashboard de monitoramento de calibração
- [ ] Suporte a PostgreSQL em produção
- [ ] Dockerização da aplicação
- [ ] CI/CD com testes automáticos

---

## Testes

```bash
# Executar todos os testes
pytest app/tests/ -v

# Com cobertura
pytest app/tests/ --cov=app --cov-report=term-missing
```
