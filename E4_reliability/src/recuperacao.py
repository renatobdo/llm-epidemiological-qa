from pathlib import Path
from typing import Dict, List
import re
import unicodedata

# ============================================================
# CONFIGURAÇÃO DA RECUPERAÇÃO
# ============================================================
TOP_SECOES_POR_DOCUMENTO = 2
MAX_CARACTERES_POR_SECAO = 1800

def ler_documento_semantico(caminho: Path) -> str:
    """Carrega um documento semântico Markdown."""

    if not caminho.exists():
        raise FileNotFoundError(
            f"Documento não encontrado: {caminho}"
        )

    conteudo = caminho.read_text(
        encoding="utf-8"
    ).strip()

    if not conteudo:
        raise ValueError(
            f"Documento vazio: {caminho}"
        )

    return conteudo

def normalizar_texto(texto: str) -> str:
    """
    Normaliza texto para comparações lexicais determinísticas.
    """
    texto = str(texto).lower().strip()

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    return texto
# ============================================================
# RECUPERAÇÃO DETERMINÍSTICA HERDADA DO E3
# ============================================================

STOPWORDS_RECUPERACAO = {
    "a", "ao", "aos", "as",
    "com", "como",
    "da", "das", "de", "do", "dos",
    "e", "em", "entre",
    "foi",
    "no", "nos", "na", "nas",
    "o", "os",
    "para", "por",
    "qual", "quais", "que",
    "um", "uma",
    "resuma", "mostre",
    "brasil", "dengue", "2026",
}


def extrair_termos_consulta(pergunta: str) -> List[str]:
    pergunta_norm = normalizar_texto(pergunta)

    termos = re.findall(
        r"\b[a-z0-9_-]{3,}\b",
        pergunta_norm
    )

    termos = [
        termo
        for termo in termos
        if termo not in STOPWORDS_RECUPERACAO
    ]

    return list(dict.fromkeys(termos))

TERMOS_DIMENSAO = {
    "geral": [
        "geral",
        "total",
        "notificacoes",
        "panorama",
        "situacao",
    ],

    "temporal": [
        "temporal",
        "semana",
        "semanal",
        "periodo",
        "pico",
        "tendencia",
        "notificacoes",
    ],

    "geografica": [
        "geografica",
        "uf",
        "estado",
        "municipio",
        "incidencia",
        "residencia",
        "localizacao",
    ],

    "clinica": [
        "clinica",
        "sinal",
        "sinais",
        "sintoma",
        "sintomas",
        "doenca",
        "preexistente",
        "febre",
        "hipertensao",
    ],

    "virologica": [
        "virologica",
        "sorotipo",
        "sorotipos",
        "denv",
        "informado",
    ],

    "desfechos": [
        "desfecho",
        "desfechos",
        "hospitalizacao",
        "hospitalizado",
        "evolucao",
        "cura",
        "obito",
        "obitos",
    ],
}

def dividir_markdown_em_secoes(conteudo: str) -> List[Dict]:
    """Divide um documento Markdown utilizando cabeçalhos como limites."""

    linhas = conteudo.splitlines()

    secoes = []
    titulo_atual = "Introdução"
    nivel_atual = 0
    linhas_secao = []

    def salvar_secao():
        if not linhas_secao:
            return

        texto = "\n".join(linhas_secao).strip()

        if texto:
            secoes.append({
                "titulo": titulo_atual,
                "nivel": nivel_atual,
                "conteudo": texto,
            })

    for linha in linhas:
        match = re.match(
            r"^(#{1,6})\s+(.+?)\s*$",
            linha
        )

        if match:
            salvar_secao()

            titulo_atual = match.group(2).strip()
            nivel_atual = len(match.group(1))
            linhas_secao = []

        else:
            linhas_secao.append(linha)

    salvar_secao()

    return secoes

def pontuar_secao(
    secao: Dict,
    pergunta: str,
    dimensao: str
    ) -> float:

    titulo = normalizar_texto(secao["titulo"])
    conteudo = normalizar_texto(secao["conteudo"])

    termos_pergunta = extrair_termos_consulta(pergunta)
    termos_dimensao = TERMOS_DIMENSAO.get(dimensao, [])

    score = 0.0

    # Termos explícitos da pergunta
    for termo in termos_pergunta:
        if termo in titulo:
            score += 4.0
        elif termo in conteudo:
            score += 1.5

    # Vocabulário relacionado à dimensão
    for termo in termos_dimensao:
        termo_norm = normalizar_texto(termo)

        if termo_norm in titulo:
            score += 1.5
        elif termo_norm in conteudo:
            score += 0.25

    # Priorização de seções de síntese/panorama
    titulo_norm = normalizar_texto(secao["titulo"])
    pergunta_norm = normalizar_texto(pergunta)

    eh_consulta_panorama = any(
        termo in pergunta_norm
        for termo in [
            "panorama",
            "resuma",
            "resumo",
            "sintese",
            "geral",
        ]
    )

    if eh_consulta_panorama:
        if titulo_norm == "indicadores":
            score += 4.0

        elif titulo_norm == "interpretacao dos resultados":
            score += 3.5

        elif titulo_norm == "sintese epidemiologica":
            score += 3.0

        elif titulo_norm == "observacoes sobre os dados":
            score -= 2.0

    return score


def compactar_secao(
    secao: Dict,
    dimensao: str,
    limite_caracteres: int = 1800,
) -> str:

    conteudo = secao["conteudo"].strip()

    if len(conteudo) <= limite_caracteres:
        return conteudo

    linhas = [
        linha.strip()
        for linha in conteudo.splitlines()
        if linha.strip()
    ]

    # Caso especial: série temporal
    if (
        dimensao == "temporal"
        and any(
            "semana epidemiologica" in normalizar_texto(linha)
            for linha in linhas
        )
    ):
        registros = []

        for linha in linhas:
            match_semana = re.search(
                r"semana epidemiologica:\**\s*(\d+)",
                normalizar_texto(linha)
            )

            match_total = re.search(
                r"total registros:\**\s*([\d\.]+)",
                normalizar_texto(linha)
            )

            if match_semana and match_total:
                semana = int(match_semana.group(1))

                total = int(
                    match_total.group(1).replace(".", "")
                )

                registros.append({
                    "semana": semana,
                    "total": total,
                    "linha": linha,
                })

        if registros:
            pico = max(
                registros,
                key=lambda item: item["total"]
            )

            inicio = registros[:3]
            fim = registros[-3:]

            linhas_selecionadas = [
                "**Resumo compacto da série temporal**",
                "",
                "**Início da série:**",
            ]

            for item in inicio:
                linhas_selecionadas.append(item["linha"])

            linhas_selecionadas.extend([
                "",
                "**Pico da série:**",
                pico["linha"],
                "",
                "**Final da série:**",
            ])

            for item in fim:
                linhas_selecionadas.append(item["linha"])

            return "\n".join(linhas_selecionadas)

    # Fallback: preserva início e final
    metade = limite_caracteres // 2

    inicio = conteudo[:metade]
    fim = conteudo[-metade:]

    return (
        f"{inicio}\n\n"
        "[... trecho intermediário omitido ...]\n\n"
        f"{fim}"
    )


def selecionar_secoes_relevantes(
    conteudo: str,
    pergunta: str,
    dimensao: str,
    top_k: int = TOP_SECOES_POR_DOCUMENTO,
) -> List[Dict]:

    secoes = dividir_markdown_em_secoes(conteudo)

    secoes_pontuadas = []

    for secao in secoes:
        score = pontuar_secao(
            secao=secao,
            pergunta=pergunta,
            dimensao=dimensao,
        )

        secoes_pontuadas.append({
            **secao,
            "score": score,
        })

    secoes_pontuadas.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    # Mantém inicialmente apenas seções com relevância > 0
    selecionadas = [
        secao
        for secao in secoes_pontuadas
        if secao["score"] > 0
    ][:top_k]

    # Fallback herdado:
    # se nenhuma seção pontuar, utiliza as primeiras seções.
    if not selecionadas:
        selecionadas = secoes_pontuadas[:top_k]

    resultado = []

    for secao in selecionadas:
        texto = compactar_secao(
            secao=secao,
            dimensao=dimensao,
            limite_caracteres=MAX_CARACTERES_POR_SECAO,
        )

        resultado.append({
            "titulo": secao["titulo"],
            "score": secao["score"],
            "conteudo": texto,
        })

    return resultado


def construir_documentos_semanticos(base_docs: Path) -> Dict[str, List[Path]]:
    """Constrói o mapa da coleção a partir do diretório-base."""
    base_docs = Path(base_docs)
    return {
        "geral": [base_docs / "panorama_geral" / "sinan_dengue_2026_panorama_geral.md"],
        "temporal": [base_docs / "temporais" / "panorama_temporal" / "sinan_dengue_2026_temporal_brasil.md"],
        "geografica": [base_docs / "geograficos" / "panorama_geografico" / "sinan_dengue_2026_geografico_brasil.md"],
        "clinica": [base_docs / "clinicas" / "panorama_clinico" / "sinan_dengue_2026_clinico_brasil.md"],
        "virologica": [base_docs / "virologicas" / "panorama_sorotipos" / "sinan_dengue_2026_sorotipos_brasil.md"],
        "desfechos": [
            base_docs / "desfechos" / "panorama_desfechos" / "sinan_dengue_2026_desfechos_brasil.md",
            base_docs / "desfechos" / "panorama_obitos" / "sinan_dengue_2026_obitos_brasil.md",
        ],
    }


def recuperar_documentos_semanticos_compacto(
    pergunta: str,
    dimensoes: List[str],
    base_docs: Path,
) -> List[Dict]:
    """Recupera e compacta as seções mais relevantes por dimensão."""
    documentos_semanticos = construir_documentos_semanticos(base_docs)
    documentos_recuperados = []

    for dimensao in dimensoes:
        caminhos = documentos_semanticos.get(dimensao, [])

        for caminho in caminhos:
            if not caminho.exists():
                continue

            conteudo_completo = ler_documento_semantico(caminho)
            secoes = selecionar_secoes_relevantes(
                conteudo=conteudo_completo,
                pergunta=pergunta,
                dimensao=dimensao,
            )

            blocos = [
                f"## {secao['titulo']}\n\n{secao['conteudo']}"
                for secao in secoes
            ]
            conteudo_compacto = "\n\n".join(blocos)

            documentos_recuperados.append({
                "dimensao": dimensao,
                "document_id": caminho.stem,
                "arquivo": caminho.name,
                "caminho": str(caminho),
                "conteudo": conteudo_compacto,
                "secoes_selecionadas": [secao["titulo"] for secao in secoes],
                "caracteres_original": len(conteudo_completo),
                "caracteres_recuperados": len(conteudo_compacto),
            })

    return documentos_recuperados
