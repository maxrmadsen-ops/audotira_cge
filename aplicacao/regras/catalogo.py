import hashlib
import json
from pathlib import Path

from django.db import transaction

from aplicacao.regras.classificacao import CLASSIFICACAO
from aplicacao.regras.models import RegraAnalise, RegraDependencia

ARQUIVO_MATRIZ = Path(__file__).resolve().parent / "dados" / "matriz_regras_cge.json"
FONTE_FUNCIONAL = "Matriz_Tecnica_Regras_Analise_IA_2022TR929.xlsx"

COLUNAS = {
    "ID": "codigo",
    "Categoria": "categoria",
    "Regra de análise": "titulo",
    "Fonte normativa indicada nas diretrizes": "fonte_normativa_original",
    "Aplicabilidade": "aplicabilidade_original",
    "Entradas necessárias": "entradas_necessarias",
    "Dados a extrair": "dados_extrair",
    "Lógica de verificação": "logica_verificacao",
    "Resultado possível": "resultados_possiveis",
    "Evidência obrigatória": "evidencia_obrigatoria",
    "Limitação/observação": "limitacao_observacao",
    "Tratamento/Ação para o analista": "tratamento_analista",
}


class DependenciaCircular(Exception):
    pass


def carregar_matriz() -> dict:
    return json.loads(ARQUIVO_MATRIZ.read_text(encoding="utf-8"))


def hash_catalogo() -> str:
    conteudo = json.dumps(carregar_matriz(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


def validar_grafo(dependencias: dict[str, list[str]]) -> None:
    visitando: set[str] = set()
    visitados: set[str] = set()

    def visitar(codigo: str) -> None:
        if codigo in visitados:
            return
        if codigo in visitando:
            raise DependenciaCircular(f"Dependência circular envolvendo {codigo}.")
        visitando.add(codigo)
        for requisito in dependencias.get(codigo, []):
            visitar(requisito)
        visitando.remove(codigo)
        visitados.add(codigo)

    for codigo in dependencias:
        visitar(codigo)


def _assinatura(regra: RegraAnalise) -> tuple:
    return (
        regra.conteudo_original,
        regra.tipo_execucao,
        regra.capacidade,
        regra.executor,
        regra.configuracao,
        [(item.codigo_requisito, item.tipo, item.parametro) for item in regra.dependencias.all()],
    )


def _assinatura_desejada(item: dict, meta: dict) -> tuple:
    dependencias = [(dep["codigo"], dep["tipo"], dep.get("parametro") or {}) for dep in meta["dependencias"]]
    return (item, meta["tipo_execucao"], meta["capacidade"], meta["executor"], meta["configuracao"], dependencias)


@transaction.atomic
def sincronizar_catalogo() -> dict:
    matriz = carregar_matriz()
    regras = matriz["regras"]
    codigos = [item["ID"] for item in regras]
    if len(codigos) != len(set(codigos)):
        raise ValueError("A matriz contém identificadores duplicados.")
    ausentes = sorted(set(codigos) - set(CLASSIFICACAO))
    extras = sorted(set(CLASSIFICACAO) - set(codigos))
    if ausentes or extras:
        raise ValueError(f"Classificação técnica divergente da matriz. Ausentes={ausentes} extras={extras}")
    grafo = {codigo: [dep["codigo"] for dep in CLASSIFICACAO[codigo]["dependencias"]] for codigo in codigos}
    validar_grafo(grafo)

    criadas = 0
    mantidas = 0
    for ordem, item in enumerate(regras, start=1):
        meta = CLASSIFICACAO[item["ID"]]
        atual = RegraAnalise.objects.filter(codigo=item["ID"], ativa=True).prefetch_related("dependencias").first()
        desejada = _assinatura_desejada(item, meta)
        if atual is not None and _assinatura(atual) == desejada:
            if atual.ordem != ordem:
                atual.ordem = ordem
                atual.save(update_fields=["ordem", "atualizado_em"])
            mantidas += 1
            continue
        versao = 1 if atual is None else atual.versao + 1
        if atual is not None:
            atual.ativa = False
            atual.save(update_fields=["ativa", "atualizado_em"])
        regra = RegraAnalise.objects.create(
            codigo=item["ID"],
            versao=versao,
            categoria=item["Categoria"],
            titulo=item["Regra de análise"],
            descricao_original=item["Regra de análise"],
            fonte_normativa_original=item["Fonte normativa indicada nas diretrizes"],
            aplicabilidade_original=item["Aplicabilidade"],
            entradas_necessarias=item["Entradas necessárias"],
            dados_extrair=item["Dados a extrair"],
            logica_verificacao=item["Lógica de verificação"],
            resultados_possiveis=item["Resultado possível"],
            evidencia_obrigatoria=item["Evidência obrigatória"],
            limitacao_observacao=item["Limitação/observação"],
            tratamento_analista=item["Tratamento/Ação para o analista"],
            tipo_execucao=meta["tipo_execucao"],
            capacidade=meta["capacidade"],
            executor=meta["executor"],
            configuracao=meta["configuracao"],
            conteudo_original=item,
            ativa=True,
            ordem=ordem,
        )
        for dependencia in meta["dependencias"]:
            RegraDependencia.objects.create(
                regra=regra,
                codigo_requisito=dependencia["codigo"],
                tipo=dependencia["tipo"],
                parametro=dependencia.get("parametro") or {},
            )
        criadas += 1
    return {"criadas": criadas, "mantidas": mantidas, "total": len(regras)}
