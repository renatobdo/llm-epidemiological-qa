from typing import Any, Callable, Dict, Iterable, List

import pandas as pd


def executar_rodadas_confiabilidade(
    casos: Iterable[Dict[str, Any]],
    executar_caso_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    n_rodadas: int = 3,
) -> pd.DataFrame:
    """Executa o conjunto congelado sem alterar casos entre rodadas."""
    registros: List[Dict[str, Any]] = []
    casos = list(casos)

    for rodada in range(1, n_rodadas + 1):
        print(f"\n=== RODADA {rodada}/{n_rodadas} ===")

        for indice, caso in enumerate(casos, start=1):
            print(
                f"[{indice:02d}/{len(casos)}] {caso['id']}",
                end=" ... ",
            )

            resultado = executar_caso_fn(caso)
            resultado = dict(resultado)
            resultado["rodada"] = rodada
            registros.append(resultado)

            status = resultado.get("aprovado")
            erro = resultado.get("erro")
            print(f"aprovado={status} | erro={erro}")

    return pd.DataFrame(registros)


def resumir_rodadas(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula métricas observáveis por rodada sem imputar casos manuais."""
    linhas = []

    for rodada, grupo in df.groupby("rodada", sort=True):
        automaticos = grupo[grupo["aprovado"].notna()].copy()
        coberturas = grupo["cobertura"].dropna()
        fidelidades = grupo["fidelidade_evidencias"].dropna()
        abstencoes = grupo["abstencao_correta"].dropna()

        linhas.append({
            "rodada": int(rodada),
            "casos_total": int(len(grupo)),
            "casos_avaliacao_automatica": int(len(automaticos)),
            "correcao_automatica": (
                float(automaticos["aprovado"].astype(float).mean())
                if len(automaticos) else None
            ),
            "cobertura_media": (
                float(coberturas.mean()) if len(coberturas) else None
            ),
            "fidelidade_media": (
                float(fidelidades.mean()) if len(fidelidades) else None
            ),
            "abstencao_correta": (
                float(abstencoes.astype(float).mean())
                if len(abstencoes) else None
            ),
            "latencia_media_s": float(grupo["latencia_s"].mean()),
            "chamadas_llm": int(grupo["chamadas_llm"].sum()),
            "chamadas_ferramentas": int(grupo["chamadas_ferramentas"].sum()),
            "erros": int(grupo["erro"].notna().sum()),
        })

    return pd.DataFrame(linhas)


def resumir_estabilidade_por_caso(df: pd.DataFrame) -> pd.DataFrame:
    """Resume repetibilidade observável de cada caso nas rodadas."""
    linhas = []

    for caso_id, grupo in df.groupby("id", sort=True):
        aprovados_obs = grupo["aprovado"].dropna()
        coberturas = grupo["cobertura"].dropna()
        fidelidades = grupo["fidelidade_evidencias"].dropna()
        abstencoes = grupo["abstencao_correta"].dropna()

        respostas_unicas = grupo["resposta"].fillna("<ERRO>").nunique()
        dimensoes_unicas = grupo["dimensoes_detectadas"].apply(
            lambda x: tuple(x) if isinstance(x, list) else tuple()
        ).nunique()

        if len(aprovados_obs):
            aprovacoes = int(aprovados_obs.astype(bool).sum())
            execucoes_auto = int(len(aprovados_obs))
            estabilidade_aprovacao = aprovados_obs.nunique() == 1
        else:
            aprovacoes = None
            execucoes_auto = 0
            estabilidade_aprovacao = None

        linhas.append({
            "id": caso_id,
            "tipo": grupo["tipo"].iloc[0],
            "verificacao": grupo["verificacao"].iloc[0],
            "aprovacoes": aprovacoes,
            "execucoes_auto": execucoes_auto,
            "estabilidade_aprovacao": estabilidade_aprovacao,
            "cobertura_min": float(coberturas.min()) if len(coberturas) else None,
            "cobertura_max": float(coberturas.max()) if len(coberturas) else None,
            "fidelidade_min": float(fidelidades.min()) if len(fidelidades) else None,
            "fidelidade_max": float(fidelidades.max()) if len(fidelidades) else None,
            "abstencao_min": float(abstencoes.astype(float).min()) if len(abstencoes) else None,
            "abstencao_max": float(abstencoes.astype(float).max()) if len(abstencoes) else None,
            "respostas_unicas": int(respostas_unicas),
            "classificacoes_unicas": int(dimensoes_unicas),
            "latencia_min_s": float(grupo["latencia_s"].min()),
            "latencia_max_s": float(grupo["latencia_s"].max()),
            "erros": int(grupo["erro"].notna().sum()),
        })

    return pd.DataFrame(linhas)


def identificar_casos_instaveis(df_estabilidade: pd.DataFrame) -> pd.DataFrame:
    """Seleciona sinais de instabilidade sem exigir igualdade textual das respostas."""
    mascara = (
        (df_estabilidade["estabilidade_aprovacao"] == False)
        | (df_estabilidade["classificacoes_unicas"] > 1)
        | (df_estabilidade["erros"] > 0)
    )
    return df_estabilidade[mascara].copy()
