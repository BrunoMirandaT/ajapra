"""Módulo de previsão: número de animais novos cadastrados por mês.

Fluxo (conforme a arquitetura proposta):
  1. Coleta de dados históricos  -> contagem de cadastros por mês (build_series)
  2. Pré-processamento           -> meses sem cadastro viram 0; mês em curso (incompleto) é descartado
  3. Modelo preditivo            -> regressão linear com tendência + sazonalidade anual (Fourier)
  4. Geração de estimativas      -> estimativa pontual + intervalo de ~80% por mês futuro

O método se adapta à quantidade de histórico disponível:
  < 3 meses   : não há dados suficientes
  3 a 11      : média móvel dos últimos 3 meses
  12 a 23     : tendência + 1 harmônica sazonal
  >= 24       : tendência + 2 harmônicas sazonais

Um backtest (validação com os últimos meses conhecidos) compara o modelo com uma
referência ingênua (média móvel de 3 meses) para indicar se ele realmente ajuda.
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import date

import numpy as np

Z80 = 1.2816  # quantil normal para intervalo de 80%
RIDGE = 0.05  # regularização leve para estabilidade numérica


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def add_months(ym: str, k: int) -> str:
    idx = int(ym[:4]) * 12 + (int(ym[5:7]) - 1) + k
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def build_series(datas: list[str], hoje: date | None = None) -> tuple[list[str], list[int]]:
    """Converte datas de cadastro (AAAA-MM-DD) em série mensal contínua até o mês anterior ao atual."""
    hoje = hoje or date.today()
    atual = month_key(hoje)
    counts = Counter(d[:7] for d in datas if d and len(d) >= 7 and d[:7] < atual)
    if not counts:
        return [], []
    first, last = min(counts), add_months(atual, -1)
    labels, m = [], first
    while m <= last:
        labels.append(m)
        m = add_months(m, 1)
    return labels, [counts.get(m, 0) for m in labels]


def _features(labels: list[str], t0: int, harmonics: int) -> np.ndarray:
    rows = []
    for i, ym in enumerate(labels):
        theta = 2 * math.pi * (int(ym[5:7]) - 1) / 12
        row = [1.0, (t0 + i) / 12.0]
        for k in range(1, harmonics + 1):
            row += [math.sin(k * theta), math.cos(k * theta)]
        rows.append(row)
    return np.array(rows)


def _harmonics_for(n: int) -> int | None:
    if n < 3:
        return None
    if n < 12:
        return 0  # sinaliza média móvel
    return 1 if n < 24 else 2


def _predict(labels: list[str], values: list[int], horizon: int) -> tuple[list[dict], str]:
    n = len(values)
    h = _harmonics_for(n)
    if h is None:
        raise ValueError("Dados insuficientes: são necessários ao menos 3 meses completos de cadastros.")
    futuros = [add_months(labels[-1], i) for i in range(1, horizon + 1)]
    y = np.array(values, dtype=float)

    if h == 0:  # média móvel
        mu = float(y[-3:].mean())
        sigma = float(y.std(ddof=1)) if n > 1 else 0.0
        out = [(mu, sigma * Z80) for _ in futuros]
        metodo = "media_movel"
    else:
        X = _features(labels, 0, h)
        p = X.shape[1]
        pen = RIDGE * np.eye(p)
        pen[0, 0] = 0.0  # não penaliza o intercepto
        A = X.T @ X + pen
        A_inv = np.linalg.pinv(A)
        beta = A_inv @ X.T @ y
        resid = y - X @ beta
        sigma = math.sqrt(float(resid @ resid) / max(n - p, 1))
        Xf = _features(futuros, n, h)
        out = []
        for row in Xf:
            mu = float(row @ beta)
            se = sigma * math.sqrt(1.0 + float(row @ A_inv @ row))
            out.append((mu, se * Z80))
        metodo = "tendencia_sazonal"

    preds = []
    for ym, (mu, margem) in zip(futuros, out):
        est = max(mu, 0.0)
        preds.append({
            "mes": ym,
            "estimativa": round(est, 1),
            "inteiro": int(round(est)),
            "minimo": max(int(math.floor(mu - margem)), 0),
            "maximo": int(math.ceil(mu + margem)),
        })
    return preds, metodo


def backtest(labels: list[str], values: list[int], folds: int = 6) -> dict | None:
    """Validação rolling-origin de 1 passo à frente nos últimos meses conhecidos."""
    n = len(values)
    if n < 15:
        return None
    folds = min(folds, n - 12)
    err_model, err_base = [], []
    for i in range(n - folds, n):
        pred, _ = _predict(labels[:i], values[:i], 1)
        base = float(np.mean(values[max(0, i - 3):i]))
        err_model.append(abs(pred[0]["estimativa"] - values[i]))
        err_base.append(abs(base - values[i]))
    mae_m, mae_b = float(np.mean(err_model)), float(np.mean(err_base))
    return {
        "meses_testados": folds,
        "mae_modelo": round(mae_m, 2),
        "mae_referencia": round(mae_b, 2),
        "melhoria_pct": round((1 - mae_m / mae_b) * 100, 1) if mae_b > 0 else None,
    }


def forecast(datas_cadastro: list[str], meses: int = 6, hoje: date | None = None) -> dict:
    meses = max(1, min(int(meses), 12))
    labels, values = build_series(datas_cadastro, hoje)
    preds, metodo = _predict(labels, values, meses)  # lança ValueError se faltar histórico
    ultimos12 = values[-12:]
    aviso = None
    if metodo == "media_movel":
        aviso = ("Histórico curto (menos de 12 meses): a previsão usa a média dos últimos 3 meses "
                 "e não considera sazonalidade. Ela melhora conforme novos dados são cadastrados.")
    elif len(values) < 24:
        aviso = "Histórico entre 12 e 23 meses: a sazonalidade é estimada de forma simplificada."
    return {
        "metodo": metodo,
        "meses_historico": len(values),
        "historico": [{"mes": m, "valor": v} for m, v in zip(labels, values)],
        "previsao": preds,
        "total_previsto": sum(p["inteiro"] for p in preds),
        "media_historica_12m": round(float(np.mean(ultimos12)), 1),
        "media_prevista": round(float(np.mean([p["estimativa"] for p in preds])), 1),
        "pico": max(preds, key=lambda p: p["estimativa"]),
        "metricas": backtest(labels, values),
        "aviso": aviso,
        "intervalo_confianca": "80%",
    }
