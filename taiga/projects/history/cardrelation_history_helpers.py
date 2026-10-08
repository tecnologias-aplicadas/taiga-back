from django.apps import apps

from taiga.projects.history.models import HistoryEntry
from taiga.projects.history.choices import HistoryType

"""
#187 Histórico de alteração de relacionamento

Arquivo responsável por criar activities de relacionamento para a timeline
dos cards afetados.

Quando uma CardRelation é criada, este arquivo ajuda a:
- descobrir quais cards foram impactados;
- montar a key de history correta para cada card;
- criar um HistoryEntry do tipo change para aparecer na aba Activities.

Agora também suporta:
- criação de relação
- alteração de tipo de relação
- resolução/remoção de relação

Gerando diffs corretos no formato:

criação
[None, relation]

alteração
[old_relation, new_relation]

remoção
[old_relation, None]
"""


# Chave do diff das entradas de relação. É a única chave que o front lê na aba
# Atividades e a que a reconstrução de snapshot do card precisa ignorar.
CARDRELATION_DIFF_KEY = "card_relation"

# Mapeia o tipo do card para o typename usado na key do history.
CARDRELATION_KEY_MAP = {
    "userstory": "userstories.userstory",
    "task": "tasks.task",
    "epic": "epics.epic",
    "issue": "issues.issue",
}

# Mapeia o tipo do card para o app/model do Django.
CARD_MODEL_MAP = {
    "issue": ("issues", "Issue"),
    "userstory": ("userstories", "UserStory"),
    "task": ("tasks", "Task"),
    "epic": ("epics", "Epic"),
}


# Retorna a classe do model Django com base no tipo do card.
def get_card_model(card_type):
    mapping = CARD_MODEL_MAP.get(card_type)
    if not mapping:
        return None

    app_label, model_name = mapping
    return apps.get_model(app_label, model_name)


# Busca o "ref" do card, que é o número exibido na interface.
def get_card_ref(card_type, card_id):
    Model = get_card_model(card_type)
    if not Model:
        return None

    obj = Model.objects.filter(id=card_id).only("ref").first()
    return obj.ref if obj else None


# Monta um rótulo amigável no formato TIPO-REF, como USERSTORY-57.
def get_card_ref_label(card_type, card_id):
    ref = get_card_ref(card_type, card_id)
    if ref is None:
        return None

    return f"{card_type.upper()}-{ref}"


# Monta a key de history usada para gravar a activity no card correto.
def build_history_key(card_type, card_id):
    typename = CARDRELATION_KEY_MAP.get(card_type)
    if not typename:
        return None

    return f"{typename}:{card_id}"


# Helper interno que permite acessar atributos tanto de dict quanto de objeto.
def _relation_value(obj, field, default=None):
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(field, default)

    return getattr(obj, field, default)


# Retorna o project_id independentemente se relation é dict ou model.
def get_relation_project_id(relation):
    return _relation_value(relation, "project_id") or _relation_value(relation, "project")


# Retorna os cards afetados por uma relação específica.
def get_affected_targets_from_relation(relation):
    if not relation:
        return []

    pairs = [
        (_relation_value(relation, "source_type"), _relation_value(relation, "source_id")),
        (_relation_value(relation, "target_type"), _relation_value(relation, "target_id")),
    ]

    result = []
    seen = set()

    for card_type, card_id in pairs:
        if not card_type or not card_id:
            continue

        item = (card_type, card_id)
        if item in seen:
            continue

        seen.add(item)

        key = build_history_key(card_type, card_id)
        if not key:
            continue

        result.append({
            "type": card_type,
            "id": card_id,
            "key": key,
        })

    return result


# Retorna todos os cards afetados considerando estado anterior e posterior.
def get_affected_targets(before_relation=None, after_relation=None):
    result = []
    seen = set()

    for relation in (before_relation, after_relation):
        for item in get_affected_targets_from_relation(relation):
            marker = (item["type"], item["id"])

            if marker in seen:
                continue

            seen.add(marker)
            result.append(item)

    return result


# Retorna o outro lado da relação com base no card atual da timeline.
def get_other_side(relation, current_type, current_id):
    source_type = _relation_value(relation, "source_type")
    source_id = _relation_value(relation, "source_id")
    target_type = _relation_value(relation, "target_type")
    target_id = _relation_value(relation, "target_id")

    if source_type == current_type and source_id == current_id:
        return target_type, target_id

    return source_type, source_id


# Monta um lado do diff preservando source e target reais da relação.
def build_relation_side(relation):
    if not relation:
        return None

    source_type = _relation_value(relation, "source_type")
    source_id = _relation_value(relation, "source_id")
    target_type = _relation_value(relation, "target_type")
    target_id = _relation_value(relation, "target_id")

    return {
        "relation_type": _relation_value(relation, "relation_type"),
        "source_type": source_type,
        "source_ref": get_card_ref(source_type, source_id),
        "target_type": target_type,
        "target_ref": get_card_ref(target_type, target_id),
    }


# Monta o diff estruturado da relação para o frontend renderizar.
def build_relation_diff(before_relation, after_relation, current_type=None, current_id=None, action=None):
    before = build_relation_side(before_relation)
    after = build_relation_side(after_relation)

    if before and action:
        before["action"] = action
    return {CARDRELATION_DIFF_KEY: [before, after]}


# Monta as informações básicas do usuário no formato salvo no history.
def get_user_info(user):
    if user is None:
        return {"pk": None, "name": ""}

    return {"pk": user.id, "name": user.get_full_name()}


# Cria uma entry de history do tipo change para aparecer na aba Activities.
def build_history_entry(*, user_info, project_id, key, diff,  history_type=HistoryType.change):
    return HistoryEntry.objects.create(
        user=user_info,
        project_id=project_id,
        key=key,
        type=history_type,
        diff=diff,
        values={"users": {}},
        values_diff_cache=diff,
        snapshot=None,
        comment="",
        comment_html="",
        is_hidden=False,
        is_snapshot=False,
    )


# Cria as activities de relacionamento para todos os cards afetados.
# Agora aceita BEFORE e AFTER para representar corretamente:
# criação, alteração ou resolução de relação.
def create_cardrelation_activity_entries(
    *,
    before_relation=None,
    after_relation=None,
    user=None,
    comment="",
    history_type=HistoryType.change,
    action=None,
):
    user_info = get_user_info(user)
    entries = []

    reference_relation = after_relation or before_relation
    project_id = get_relation_project_id(reference_relation)

    for target in get_affected_targets(before_relation, after_relation):

        diff = build_relation_diff(
            before_relation,
            after_relation,
            action=action,
        )

        entry = build_history_entry(
            user_info=user_info,
            project_id=project_id,
            key=target["key"],
            diff=diff,
            history_type=history_type,
        )

        entries.append(entry)

    return entries