import pytest
from django.urls import reverse
from taiga.base.utils import json

from .. import factories as f


pytestmark = pytest.mark.django_db

from taiga.projects.history.models import CommentReaction

def test_add_and_list_reactions(client):
    """
    Testa se um usuário consegue:
    1. Adicionar uma reação (emoji) a um comentário de histórico (HistoryEntry).
    2. Listar as reações corretamente associadas ao comentário.

    Verifica:
    - Se a requisição de adição retorna 200.
    - Se a reação é persistida no banco.
    - Se a listagem retorna o emoji com a contagem e o ID do usuário que reagiu.
    """
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    issue = f.IssueFactory.create(project=project)
    comment = f.HistoryEntryFactory.create(
        project=project,
        user={"pk": user.pk},
        key=f"issues.Issue:{issue.pk}"
    )

    emoji = "👍"
    client.login(user)

    add_url = reverse("comment-reactions-add", kwargs={"comment_pk": comment.id})
    list_url = reverse("comment-reactions-list-reactions", kwargs={
        "comment_pk": comment.id,
    })

    # Add reaction
    response = client.post(add_url, json.dumps({"emoji": emoji}), content_type="application/json")
    assert response.status_code == 200
    assert CommentReaction.objects.count() == 1  # Consulta o model, não a factory

    # List reactions
    response = client.get(list_url)
    assert response.status_code == 200
    data = response.json()
    assert emoji in data
    assert data[emoji]["count"] == 1
    assert user.id in data[emoji]["users"]

def test_remove_reaction(client):
    """
    Testa se um usuário consegue remover uma reação (emoji) de um comentário de histórico (HistoryEntry).

    Verifica:
    - Se a reação foi criada corretamente para o comentário.
    - Se a remoção via endpoint retorna status 200.
    - Se a reação é de fato excluída do banco após a requisição.
    """
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    issue = f.IssueFactory.create(project=project)
    comment = f.HistoryEntryFactory.create(
        project=project,
        user={"pk": user.pk},
        key=f"issues.Issue:{issue.pk}"
    )
    emoji = "😂"
    f.MembershipFactory.create(project=project, user=user, is_admin=True)

    reaction = CommentReaction.objects.create(comment=comment, user=user, emoji=emoji)
    client.login(user)

    url = reverse("comment-reactions-remove", args=[comment.id])
    response = client.delete(url, json.dumps({"emoji": emoji}), content_type="application/json")
    assert response.status_code == 200
    assert CommentReaction.objects.count() == 0

def test_add_invalid_emoji_returns_400(client):
    """
    Testa se o endpoint rejeita emojis inválidos (palavras, letras, símbolos).

    Verifica:
    - Se a requisição com um valor inválido retorna status 400.
    - Se a mensagem de erro retornada é "invalid emoji".
    - Se nenhuma reação é criada no banco de dados.
    """
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    comment = f.HistoryEntryFactory.create(project=project, user={"pk": user.pk})
    client.login(user)

    url = reverse("comment-reactions-add", kwargs={"comment_pk": comment.id})
    response = client.post(url, json.dumps({"emoji": "banana"}), content_type="application/json")
    assert response.status_code == 400
    assert "invalid emoji" in response.json()["error"]

def test_add_reaction_missing_emoji_field(client):
    """
    Testa se o campo obrigatório 'emoji' está presente no payload da requisição.

    Verifica:
    - Se a ausência do campo 'emoji' no body gera status 400.
    - Se a mensagem de erro retornada é "emoji is required".
    - Se nenhuma reação é persistida no banco.
    """
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    comment = f.HistoryEntryFactory.create(project=project, user={"pk": user.pk})
    client.login(user)

    url = reverse("comment-reactions-add", kwargs={"comment_pk": comment.id})
    response = client.post(url, json.dumps({}), content_type="application/json")
    assert response.status_code == 400
    assert "emoji is required" in response.json()["error"]

def test_remove_invalid_emoji(client):
    """
    Testa se o endpoint de remoção trata emojis inválidos corretamente.

    Verifica:
    - Se a requisição com um emoji inválido retorna status 400.
    - Se a mensagem de erro retornada é "invalid emoji".
    - Se nenhuma reação é removida do banco (nem deve existir).
    """
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    comment = f.HistoryEntryFactory.create(project=project, user={"pk": user.pk})
    client.login(user)

    url = reverse("comment-reactions-remove", kwargs={"comment_pk": comment.id})
    response = client.delete(url, json.dumps({"emoji": "test123"}), content_type="application/json")
    assert response.status_code == 400
    assert "invalid emoji" in response.json()["error"]

def test_add_reaction_unauthenticated(client):
    """
    Testa se usuários não autenticados são impedidos de adicionar reações.

    Verifica:
    - Se a requisição feita sem autenticação retorna 401 ou 403.
    - Se nenhuma reação é criada no banco.
    """
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    issue = f.IssueFactory.create(project=project)
    comment = f.HistoryEntryFactory.create(
        project=project,
        user={"pk": user.pk},
        key=f"issues.Issue:{issue.pk}"
    )

    url = reverse("comment-reactions-add", kwargs={"comment_pk": comment.id})
    response = client.post(url, json.dumps({"emoji": "❤️"}), content_type="application/json")
    assert response.status_code in (401, 403)

import threading
import pytest
from django.test import Client
from django.db import transaction

@pytest.mark.django_db(transaction=True)
def test_concurrent_reactions():
    """
    Testa se múltiplas requisições concorrentes para adicionar a mesma reação não geram duplicatas.

    Verifica:
    - Se o endpoint trata condições de corrida corretamente.
    - Se apenas uma reação é persistida no banco, mesmo com várias requisições simultâneas.
    """
    with transaction.atomic():
        user = f.UserFactory.create(password="123123")
        project = f.ProjectFactory.create(owner=user)
        issue = f.IssueFactory.create(project=project)
        comment = f.HistoryEntryFactory.create(
            project=project,
            user={"pk": user.pk},
            key=f"issues.Issue:{issue.pk}"
        )

    url = reverse("comment-reactions-add", kwargs={"comment_pk": comment.id})
    data = json.dumps({"emoji": "👍"})

    def post_reaction():
        c = Client()
        c.force_login(user)
        c.post(url, data, content_type="application/json") #caso queira printar as threads, atribuir a uma variável response esta linha
        #print(f"Thread response: {response.status_code} — {response.content.decode()}")

    threads = [threading.Thread(target=post_reaction) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert CommentReaction.objects.count() == 1
