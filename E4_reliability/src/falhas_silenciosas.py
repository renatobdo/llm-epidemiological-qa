import re
import unicodedata
from typing import Iterable, List


class FalhaSilenciosaDetectada(RuntimeError):
    """Sinaliza uma condição que o baseline trataria sem erro explícito."""


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    texto = texto.lower()
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def validar_classificacao_sem_fallback(
    dimensoes_brutas: Iterable[str],
    dimensoes_suportadas: Iterable[str],
) -> List[str]:
    """
    Valida a saída do classificador antes do fallback herdado.

    O baseline converte uma classificação vazia ou totalmente inválida
    em ["geral"]. A auditoria impede que essa substituição ocorra sem
    sinalização explícita.
    """
    suportadas = set(dimensoes_suportadas)
    dimensoes_brutas = list(dimensoes_brutas or [])

    validas = [
        dimensao
        for dimensao in dimensoes_brutas
        if dimensao in suportadas
    ]
    validas = list(dict.fromkeys(validas))

    if not validas:
        raise FalhaSilenciosaDetectada(
            "Classificação sem dimensão válida: o fallback herdado "
            "para ['geral'] ocultaria a incerteza do classificador."
        )

    return validas


def _padrao_elemento(esperado: str) -> re.Pattern:
    """
    Cria padrão com fronteiras alfanuméricas.

    Evita, por exemplo, aceitar '15' dentro de '215', preservando
    elementos compostos como '88,21%' e nomes como 'febre'.
    """
    esperado_norm = _normalizar(esperado)
    return re.compile(
        rf"(?<![a-z0-9]){re.escape(esperado_norm)}(?![a-z0-9])"
    )


def validar_benchmark_sem_substring(
    resposta: str,
    esperados: Iterable[str],
) -> bool:
    """
    Verifica elementos esperados com fronteiras explícitas.

    Lança exceção quando algum elemento não aparece como unidade
    independente na resposta, tornando ruidoso um possível falso
    positivo do verificador herdado baseado em substring.
    """
    resposta_norm = _normalizar(resposta)
    ausentes = []

    for esperado in esperados:
        if not _padrao_elemento(str(esperado)).search(resposta_norm):
            ausentes.append(str(esperado))

    if ausentes:
        raise FalhaSilenciosaDetectada(
            "Benchmark estrito rejeitou a resposta. "
            f"Elementos ausentes como unidades independentes: {ausentes}"
        )

    return True
