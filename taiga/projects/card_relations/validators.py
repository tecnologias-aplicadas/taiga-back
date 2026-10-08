from .choices import *
from taiga.base.api import validators
from taiga.base.api import serializers
from . import models
from taiga.base.exceptions import ValidationError
from django.utils.translation import gettext as _
from taiga.projects.models import Project
from django.db.models import Q



SYMMETRIC_TYPES = (
    RelationType.RELATED_TO,
    RelationType.DUPLICATED_BY,
    RelationType.DUPLICATED_FROM,
)

class CardRelationValidator(validators.ModelValidator):
    project_id = serializers.IntegerField(required=True)

    source_type = serializers.CharField(required=True)
    source_id = serializers.IntegerField(required=True)

    target_type = serializers.CharField(required=True)
    target_id = serializers.IntegerField(required=True)

    relation_type = serializers.CharField(required=True)
    

    class Meta:
        model = models.CardRelation
        read_only_fields = (
            "id",
            "created_date",
            "modified_date",
            "created_by",
            "modified_by",
            "resolved_date",
            "resolved_by",
            "is_resolved",
        )

    def _get_model_for_type(self, card_type):
        try:
            cardType = CardType(card_type)
        except ValueError:
            raise ValidationError({"code": "invalid_card_type"})

        Model = CARD_TYPE_MODEL_MAP.get(cardType)
        if Model is None:
            raise ValidationError({"code": "unsupported_card_type"})

        return Model, cardType

    def _get_card_for_type_and_id(self, card_type, card_id, project_id):
        Model, cardType = self._get_model_for_type(card_type)

        try:
            obj = Model.objects.only("id", "project_id").get(
                id=card_id,
                project_id=project_id,
            )
        except Model.DoesNotExist:
            raise ValidationError({"code": "card_not_found"})

        return obj, cardType

    #294 Erro 500 ao inserir valores inválidos no endpoint de histórico de alteração de relacionamentos
    def get_all_by_ref(self, project_id, card_type, card_ref):
        Model, cardType = self._get_model_for_type(card_type)

        try:
            project_id = int(project_id)
        except (ValueError, TypeError):
            raise ValidationError({"code": "invalid_project_param"})

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ValidationError({"code": "project_not_found"})

        try:
            card_ref = int(card_ref)
        except (ValueError, TypeError):
            raise ValidationError({"code": "invalid_card_ref_param"})

        try:
            card_obj = Model.objects.only("id").get(project_id=project_id, ref=card_ref)
        except Model.DoesNotExist:
            raise ValidationError({"code": "card_not_found"})
            
        return card_obj, cardType
    
    
    def _block_apply(self, project, source_obj, target_obj, source_card_type, target_card_type, rel_type, instance=None, attrs=None):
        
        if rel_type not in (RelationType.BLOCKS, RelationType.BLOCKED_BY):
            return

        if instance is not None:
            old_is_active = instance.is_active
        else:
            old_is_active = True  # create sempre gera relação ativa

        attrs = attrs or {}
        new_is_active = attrs.get("is_active", old_is_active)

        if rel_type == RelationType.BLOCKS:
            blocked_obj = target_obj
            blocked_card_type = target_card_type
        else:
            blocked_obj = source_obj
            blocked_card_type = source_card_type

        if not hasattr(blocked_obj, "is_blocked"):
            return 
 
        if new_is_active:
            if not blocked_obj.is_blocked:
                blocked_obj.is_blocked = True
                blocked_obj.save(update_fields=["is_blocked"])
            return

        still_blocked = models.CardRelation.objects.filter(
            project=project,
            is_active=True,
            is_resolved=False,
            relation_type__in=(RelationType.BLOCKS, RelationType.BLOCKED_BY),
        ).filter(
            Q(source_type=blocked_card_type, source_id=blocked_obj.id) |
            Q(target_type=blocked_card_type, target_id=blocked_obj.id)
        )

        if instance is not None and instance.pk is not None:
            still_blocked = still_blocked.exclude(pk=instance.pk)

        if not still_blocked.exists() and blocked_obj.is_blocked:
            blocked_obj.is_blocked = False
            blocked_obj.save(update_fields=["is_blocked"])
            
            

    def validate(self, attrs):
        instance = getattr(self, "current_instance", None)

        if instance is not None and not instance.is_active:
            raise ValidationError({"code": "cannot_edit_deleted_relation"})

        if instance is not None and instance.is_resolved:
            if "is_active" in attrs and not attrs["is_active"]:
                pass  # allow deactivating resolved relations
            else:
                raise ValidationError({"code": "cannot_edit_resolved_relation"})
        
        # Em PATCH, preenche campos ausentes com os valores da instância existente
        if instance is not None:
            if "project_id" not in attrs:
                attrs["project_id"] = instance.project_id
            if "source_type" not in attrs:
                attrs["source_type"] = instance.source_type
            if "source_id" not in attrs:
                attrs["source_id"] = instance.source_id
            if "target_type" not in attrs:
                attrs["target_type"] = instance.target_type
            if "target_id" not in attrs:
                attrs["target_id"] = instance.target_id
            if "relation_type" not in attrs:
                attrs["relation_type"] = instance.relation_type

        project_id = attrs.get("project_id")
        source_type = attrs.get("source_type")
        source_id = attrs.get("source_id")
        target_type = attrs.get("target_type")
        target_id = attrs.get("target_id")
        rel_type = attrs.get("relation_type")

        if None in (project_id, source_type, source_id, target_type, target_id, rel_type):
            raise ValidationError({"code": "missing_relation_fields"})

        if rel_type not in RelationType.values:
            raise ValidationError({"code": "invalid_relation_type"})

        if source_type == target_type and source_id == target_id:
            raise ValidationError({"code": "self_relation_not_allowed"})

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise ValidationError({"code": "project_not_found"})

        source_obj, source_card_type = self._get_card_for_type_and_id(
            source_type,
            source_id,
            project.id,
        )
        target_obj, target_card_type = self._get_card_for_type_and_id(
            target_type,
            target_id,
            project.id,
        )

        if source_obj.project_id != project.id or target_obj.project_id != project.id:
            raise ValidationError({"code": "card_not_in_project"})

        if source_obj.project_id != target_obj.project_id:
            raise ValidationError({"code": "cards_different_projects"})

        qs_any = models.CardRelation.objects.filter(
            project=project,
            is_active=True,
        ).filter(
            Q(source_type=source_card_type, source_id=source_obj.id, target_type=target_card_type, target_id=target_obj.id) |
            Q(source_type=target_card_type, source_id=target_obj.id, target_type=source_card_type, target_id=source_obj.id)
        )

        if instance is not None and instance.pk is not None:
            qs_any = qs_any.exclude(pk=instance.pk)

        if qs_any.exists():
            raise ValidationError({"code": "cards_already_related"})

        qs = models.CardRelation.objects.filter(
            project=project,
            source_type=source_card_type,
            source_id=source_obj.id,
            target_type=target_card_type,
            target_id=target_obj.id,
            relation_type=rel_type,
            is_active=True
        )

        if instance is not None and instance.pk is not None:
            qs = qs.exclude(pk=instance.pk)

        if qs.exists():
            raise ValidationError({"code": "relation_already_exists"})

        if rel_type in SYMMETRIC_TYPES:
            qs_symmetric = models.CardRelation.objects.filter(
                project=project,
                source_type=target_card_type,
                source_id=target_obj.id,
                target_type=source_card_type,
                target_id=source_obj.id,
                relation_type=rel_type,
                is_active=True
            )

            if instance is not None and instance.pk is not None:
                qs_symmetric = qs_symmetric.exclude(pk=instance.pk)

            if qs_symmetric.exists():
                raise ValidationError({"code": "symmetric_relation_exists"})

        attrs["project"] = project
        attrs["source_type"] = source_card_type
        attrs["source_id"] = source_obj.id
        attrs["target_type"] = target_card_type
        attrs["target_id"] = target_obj.id
        attrs["relation_type"] = rel_type
        
        self.cleaned_attrs = attrs 
        
        self._block_apply(
        
        project=project,
        source_obj=source_obj,
        target_obj=target_obj,
        source_card_type=source_card_type,
        target_card_type=target_card_type,
        rel_type=rel_type,
        instance=instance,
        attrs=attrs,
    )


        return attrs
