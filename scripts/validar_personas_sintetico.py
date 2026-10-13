"""Validação sintética por persona. Não imprime senha."""

from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from aplicacao.prestacoes_contas.models import PrestacaoContas

Usuario = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
def run():
    admin = Usuario.objects.filter(username="adm_cedro").first()
    auditor = Usuario.objects.filter(username="aud_ipe").first()
    analista = Usuario.objects.filter(username="ana_araucaria").first()
    outro = Usuario.objects.filter(username="ana_sintetico_b").first()
    if not all([admin, auditor, analista]):
        print("FALHA: usuários de homologação ausentes")
        return 1
    if outro is None:
        outro = Usuario.objects.create_user(
            username="ana_sintetico_b",
            password="Isolada-apenas-no-teste",
            perfil=Usuario.Perfil.ANALISTA,
        )
    proc_a, _ = PrestacaoContas.objects.get_or_create(
        numero_processo="TESTE-SINT-ANA-A",
        defaults={"analista_responsavel": analista, "criado_por": admin, "demonstracao": True},
    )
    if proc_a.analista_responsavel_id != analista.pk:
        proc_a.analista_responsavel = analista
        proc_a.save(update_fields=["analista_responsavel"])
    proc_b, _ = PrestacaoContas.objects.get_or_create(
        numero_processo="TESTE-SINT-ANA-B",
        defaults={"analista_responsavel": outro, "criado_por": admin, "demonstracao": True},
    )
    if proc_b.analista_responsavel_id != outro.pk:
        proc_b.analista_responsavel = outro
        proc_b.save(update_fields=["analista_responsavel"])

    resultados = []

    def checar(nome, ok):
        resultados.append((nome, ok))
        print(("OK" if ok else "FALHA"), nome)

    c = Client()
    c.force_login(analista)
    checar("analista vê próprio", c.get(reverse("prestacoes_contas:detalhe", args=[proc_a.pk])).status_code == 200)
    checar("analista bloqueado no alheio", c.get(reverse("prestacoes_contas:detalhe", args=[proc_b.pk])).status_code == 403)
    painel = c.get(reverse("painel:inicio"))
    checar("analista painel 200", painel.status_code == 200)
    checar("analista painel sem processo B", "TESTE-SINT-ANA-B" not in painel.content.decode())
    checar(
        "analista não redistribui",
        c.post(reverse("prestacoes_contas:atribuir", args=[proc_a.pk]), {"analista": outro.pk}).status_code == 403,
    )
    checar("analista não admin", c.get(reverse("painel:administracao")).status_code == 403)
    checar("analista abre diligência form", c.get(reverse("diligencias:nova", args=[proc_a.pk])).status_code == 200)
    checar("analista abre parecer", c.get(reverse("pareceres:parecer_final", args=[proc_a.pk])).status_code == 200)

    c.force_login(auditor)
    checar("auditor vê A", c.get(reverse("prestacoes_contas:detalhe", args=[proc_a.pk])).status_code == 200)
    checar("auditor vê B", c.get(reverse("prestacoes_contas:detalhe", args=[proc_b.pk])).status_code == 200)
    checar("auditor painel 200", c.get(reverse("painel:inicio")).status_code == 200)
    checar("auditor não usuários", c.get(reverse("usuarios:lista")).status_code == 403)

    c.force_login(admin)
    checar("admin usuários", c.get(reverse("usuarios:lista")).status_code == 200)
    checar("admin saúde", c.get(reverse("painel:saude")).status_code == 200)
    checar("admin vê A e B", c.get(reverse("prestacoes_contas:lista")).status_code == 200)

    falhas = [n for n, ok in resultados if not ok]
    print(f"Total {len(resultados)} checagens, falhas={len(falhas)}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(run())
