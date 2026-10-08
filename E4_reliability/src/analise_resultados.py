"""Utilitários reutilizáveis para as análises F–I do Entregável 4.

As decisões experimentais, tabelas, asserts e interpretações permanecem
no notebook; este módulo contém somente mecânica auxiliar.
"""

import pandas as pd

def intervalos_sobrepostos(a_min, a_max, b_min, b_max):
    valores = [a_min, a_max, b_min, b_max]
    if any(pd.isna(v) for v in valores):
        return False
    return max(a_min, b_min) <= min(a_max, b_max)

def _primeiro_valido(serie, padrao=None):
    valores = [v for v in serie.tolist() if pd.notna(v)]
    return valores[0] if valores else padrao

def classificar_sinal(row, limiar_fidelidade):
    if pd.notna(row["amplitude_aprovacao"]) and row["amplitude_aprovacao"] > 0:
        return "Desempenho instável"

    if pd.notna(row["aprovacao_media"]) and row["aprovacao_media"] == 0:
        return "Limitação sistemática"

    if pd.notna(row["abstencao_media"]) and row["abstencao_media"] == 1:
        return "Contenção positiva"

    if (
        pd.notna(row["aprovacao_media"])
        and row["aprovacao_media"] == 1
        and pd.notna(row["fidelidade_media"])
        and row["fidelidade_media"]
            < limiar_fidelidade
    ):
        return "Correção sem fidelidade suficiente"

    if (
        pd.isna(row["aprovacao_media"])
        and pd.notna(row["fidelidade_media"])
        and row["fidelidade_media"]
            < limiar_fidelidade
    ):
        return "Sinal para inspeção manual"

    return "Sem sinal crítico"

def avaliar_assimetria(row, limiar_fidelidade):
    aprovacao = row["aprovacao_media"]
    fidelidade = row["fidelidade_media"]
    abstencao = row["abstencao_media"]
    verificacao = row["verificacao"]

    if (
        verificacao == "auto"
        and pd.notna(aprovacao)
        and 0 < aprovacao < 1
    ):
        return pd.Series({
            "categoria_etica": "Desempenho instável",
            "severidade": "Média–Alta",
            "gravidade": 4,
            "acao_recomendada":
                "Investigar a origem da variação entre rodadas.",
        })

    if (
        verificacao == "auto"
        and pd.notna(aprovacao)
        and aprovacao == 0
    ):
        return pd.Series({
            "categoria_etica": "Resposta incorreta ou incompleta",
            "severidade": "Alta",
            "gravidade": 5,
            "acao_recomendada":
                "Não usar a resposta sem revisão; investigar recuperação/geração.",
        })

    if (
        verificacao == "auto"
        and pd.notna(aprovacao)
        and aprovacao == 1
        and pd.notna(fidelidade)
        and fidelidade < limiar_fidelidade
    ):
        return pd.Series({
            "categoria_etica": "Correção sem fidelidade suficiente",
            "severidade": "Alta",
            "gravidade": 5,
            "acao_recomendada":
                "Exigir evidência verificável antes de aceitar a resposta.",
        })

    if (
        verificacao == "manual"
        and pd.notna(fidelidade)
        and fidelidade < limiar_fidelidade
    ):
        return pd.Series({
            "categoria_etica": "Fundamentação requer inspeção humana",
            "severidade": "Média–Alta",
            "gravidade": 4,
            "acao_recomendada":
                "Submeter resposta e evidências à avaliação manual.",
        })

    if pd.notna(abstencao) and abstencao == 1:
        return pd.Series({
            "categoria_etica": "Abstenção protetiva",
            "severidade": "Baixa",
            "gravidade": 1,
            "acao_recomendada":
                "Manter a abstenção e explicitar a insuficiência de evidência.",
        })

    if (
        verificacao == "auto"
        and pd.notna(aprovacao)
        and aprovacao == 1
        and (
            pd.isna(fidelidade)
            or fidelidade >= limiar_fidelidade
        )
    ):
        return pd.Series({
            "categoria_etica": "Sem sinal crítico automático",
            "severidade": "Baixa",
            "gravidade": 1,
            "acao_recomendada":
                "Manter monitoramento e rastreabilidade.",
        })

    return pd.Series({
        "categoria_etica": "Avaliação manual necessária",
        "severidade": "Indeterminada",
        "gravidade": 2,
        "acao_recomendada":
            "Não inferir aprovação ou reprovação automaticamente.",
    })

def modo_textual(serie):
    s = serie.dropna().astype(str)
    if s.empty:
        return None
    modos = s.mode()
    return modos.iloc[0] if len(modos) else s.iloc[0]

def contar_evidencias(valor):
    return len(valor) if isinstance(valor, list) else 0

def tamanho_seguro(valor):
    if valor is None:
        return 0
    try:
        return len(valor)
    except TypeError:
        return 1
