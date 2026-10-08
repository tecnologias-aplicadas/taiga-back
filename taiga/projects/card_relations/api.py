from taiga.base.api import ModelCrudViewSet
from taiga.base.api.mixins import BlockedByProjectMixin
from taiga.projects.history.mixins import HistoryResourceMixin
from taiga.base import response
from taiga.projects.models import Project
from taiga.base import exceptions as exc
from taiga.permissions.services import user_has_perm, is_project_admin
from django.utils.translation import ugettext as _
from django.utils import timezone
from taiga.base.decorators import list_route, detail_route
from django.db.models import Q
from .choices import RelationType
from .validators import CardRelationValidator
from taiga.projects.history import services as history_services
from taiga.projects.history.cardrelation_history_helpers import create_cardrelation_activity_entries
from taiga.projects.history.services import build_cardrelation_removed_comment
from taiga.projects.history.choices import HistoryType
from taiga.base.exceptions import ValidationError



from . import validators
from . import models
from . import permissions
from . import serializers

_CARD_TYPE_MODIFY_PERM = {
    "userstory": "modify_us",
    "task": "modify_task",
    "issue": "modify_issue",
    "epic": "modify_epic",
}


class CardRelationViewSet(ModelCrudViewSet,BlockedByProjectMixin,HistoryResourceMixin):
    validator_class = validators.CardRelationValidator
    queryset = models.CardRelation.objects.all()
    permission_classes = (permissions.CardRelationPermission,)

    def _check_card_type_perm(self, request, project, source_type, target_type):
        if is_project_admin(request.user, project):
            return None

        source_perm = _CARD_TYPE_MODIFY_PERM.get(source_type)
        target_perm = _CARD_TYPE_MODIFY_PERM.get(target_type)

        if not source_perm or not target_perm:
            return response.Forbidden({"_error_code": "NO_MODIFY_PERM"})

        if not user_has_perm(request.user, source_perm, project):
            return response.Forbidden({"_error_code": "NO_MODIFY_PERM"})

        if not user_has_perm(request.user, target_perm, project):
            return response.Forbidden({"_error_code": "NO_MODIFY_PERM"})

        return None

    def get_serializer_class(self):  
        if self.action == "list" or self.action == "active":
           return serializers.CardRelationListSerializer

        return serializers.CardRelationSerializer
    
     # CREATE (POST /card-relations)
    def create(self, request, **kwargs):
        
        validator = self.validator_class(data=request.DATA)
        if not validator.is_valid():
            return response.BadRequest(validator.errors)
        data = validator.data
        
        try:
            project = Project.objects.get(id=data["project_id"])
        except Project.DoesNotExist:
            return response.BadRequest({"project_id": [_("Projeto inválido.")]})

        self.check_permissions(request, "create", project)
        perm_error = self._check_card_type_perm(request, project, data["source_type"], data["target_type"])
        if perm_error:
            return perm_error

        if project.blocked_code is not None:
            raise exc.Blocked(_("Projeto bloqueado."))

        obj = validator.save()
        
        obj.created_by = request.user
        obj.is_active = True
        obj.resolved_by = None
        obj.resolved_date = None
        obj.modified_date = None
        obj.save(update_fields=["created_by", "is_active", "resolved_by", "resolved_date", "modified_date"])
        
        #187 Histórico de alteração de relacionamento
        relation_comment = history_services.build_cardrelation_comment(obj)
        
        # history_services.take_snapshot(
        #     obj,
        #     user=request.user,
        #     comment=relation_comment,
        # )  
        
        # Activities nas timelines dos cards afetados
        create_cardrelation_activity_entries(
        after_relation=obj,
        user=request.user,
        comment=relation_comment,
        history_type=HistoryType.change,
        )

        self.object = obj
        
        serializer = self.get_serializer(obj)
        
        
        return response.Ok(serializer.data)
    
    # LIST (GET /card-relations)
    def list(self, request, **kwargs):     
        qs = self.get_queryset()

        project_id = request.QUERY_PARAMS.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
            
        card_type = request.QUERY_PARAMS.get("card_type")
        card_id = request.QUERY_PARAMS.get("card_id")
        if card_type and card_id:
            qs = qs.filter(
                Q(source_type=card_type, source_id=card_id)
                | Q(target_type=card_type, target_id=card_id)
            )

        serializer = self.get_serializer(qs, many=True)
        return response.Ok(serializer.data)
    
    #GET /api/v1/card-relations/list_active
    @list_route(methods=["GET"])
    def list_active(self, request, **kwargs):
        qs = self.get_queryset().filter(is_active=True)

        project_id = request.QUERY_PARAMS.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)

        card_type = request.QUERY_PARAMS.get("card_type")
        card_id = request.QUERY_PARAMS.get("card_id")
        if card_type and card_id:
            qs = qs.filter(
                Q(source_type=card_type, source_id=card_id)
                | Q(target_type=card_type, target_id=card_id)
            )

        serializer = self.get_serializer(qs, many=True)
        return response.Ok(serializer.data)
    
    #GET /api/v1/card-relations/get_all_by_ref?project={project_id}&card_type={card_type}&card_ref={card_ref}
    @list_route(methods=["GET"])
    def get_all_by_ref(self, request, **kwargs):
        qs = self.get_queryset()

        project_id = request.QUERY_PARAMS.get("project")
        card_type = request.QUERY_PARAMS.get("card_type")
        card_ref = request.QUERY_PARAMS.get("card_ref")

        if not project_id:
            return response.BadRequest({"project": [_("Parâmetro 'project' é obrigatório.")]})
        if not card_type:
            return response.BadRequest({"card_type": [_("Parâmetro 'card_type' é obrigatório.")]})
        if not card_ref:
            return response.BadRequest({"card_ref": [_("Parâmetro 'card_ref' é obrigatório.")]})

        validate = validators.CardRelationValidator()

        try:
            card_obj, card_type_enum = validate.get_all_by_ref(project_id, card_type, card_ref)
        except ValidationError as e:
            return response.BadRequest({"detail": e.messages})

        qs = qs.filter(project_id=project_id).filter(
            Q(source_type=card_type_enum, source_id=card_obj.id) |
            Q(target_type=card_type_enum, target_id=card_obj.id)
        ).filter(is_active=True)

        serializer = self.get_serializer(qs, many=True)
        return response.Ok(serializer.data)

    
    # RETRIEVE (GET /card-relations/{id}) 
    def retrieve(self, request, **kwargs):
        obj = self.get_object()
        self.object = obj
        
        serializer = self.get_serializer(obj)
        
        return response.Ok(serializer.data)
    
    # UPDATE (PUT/PATCH /card-relations/{id})
    def update(self, request, **kwargs):
        instance = self.get_object()

        partial = request.method.lower() == "patch"

        if partial:
            readonly_fields = {"project_id", "source_type", "source_id", "target_type", "target_id"}
            forbidden = readonly_fields.intersection(request.DATA.keys())
            if forbidden:
                return response.BadRequest({
                    "_error_code": "PATCH_READONLY_FIELDS",
                    "fields": list(forbidden),
                })

        validator = self.validator_class(data=request.DATA, partial=partial)
        validator.current_instance = instance

        if not validator.is_valid():
            return response.BadRequest(validator.errors)

        cleaned = getattr(validator, "cleaned_attrs", {})

        project = instance.project
        
        #187 Histórico de alteração de relacionamento
        before = history_services.cardrelation_freezer(instance)
        # history_services.take_snapshot(instance)  

        if project is not None:
            self.check_permissions(request, "update", project)
            perm_error = self._check_card_type_perm(request, project, instance.source_type, instance.target_type)
            if perm_error:
                return perm_error
            if project.blocked_code is not None:
                raise exc.Blocked(_("Projeto bloqueado."))
        else:
            self.check_permissions(request, "update", None)

        blocking_types = (RelationType.BLOCKS, RelationType.BLOCKED_BY)
        old_relation_type = instance.relation_type
        new_relation_type = cleaned.get("relation_type", old_relation_type)

        instance.project = cleaned.get("project", instance.project)
        instance.source_type = cleaned.get("source_type", instance.source_type)
        instance.source_id = cleaned.get("source_id", instance.source_id)
        instance.target_type = cleaned.get("target_type", instance.target_type)
        instance.target_id = cleaned.get("target_id", instance.target_id)
        instance.relation_type = new_relation_type

        if "is_active" in cleaned:
            instance.is_active = cleaned["is_active"]

        instance.modified_date = timezone.now()
        instance.modified_by = request.user
        instance.save()

        # Se o tipo mudou DE um tipo bloqueador, verificar se o card bloqueado
        # deve ter is_blocked=False (caso não haja mais outras relações de bloqueio)
        if old_relation_type in blocking_types and new_relation_type not in blocking_types:
            validate = validators.CardRelationValidator()
            SourceModel, source_card_type = validate._get_model_for_type(instance.source_type)
            TargetModel, target_card_type = validate._get_model_for_type(instance.target_type)

            source_obj = SourceModel.objects.get(id=instance.source_id, project_id=project.id)
            target_obj = TargetModel.objects.get(id=instance.target_id, project_id=project.id)

            if old_relation_type == RelationType.BLOCKS:
                blocked_obj = target_obj
                blocked_card_type = target_card_type
            else:  # BLOCKED_BY
                blocked_obj = source_obj
                blocked_card_type = source_card_type

            still_blocked = models.CardRelation.objects.filter(
                project=project,
                is_active=True,
                is_resolved=False,
                relation_type__in=blocking_types,
            ).exclude(id=instance.id).filter(
                Q(source_type=blocked_card_type, source_id=blocked_obj.id)
                | Q(target_type=blocked_card_type, target_id=blocked_obj.id)
            )

            if not still_blocked.exists() and blocked_obj.is_blocked:
                blocked_obj.is_blocked = False
                blocked_obj.save(update_fields=["is_blocked"])
        
        relation_comment = history_services.build_cardrelation_update_comment(
            before,
            instance
        )
        
        # history_services.take_snapshot(
        #     instance,
        #     user=request.user,
        #     comment=relation_comment,
        # )
        
        create_cardrelation_activity_entries(
            before_relation=before,
            after_relation=instance,
            user=request.user,
            comment=relation_comment,
            history_type=HistoryType.change,
        )

        self.object = instance
        serializer = self.get_serializer(instance)
        return response.Ok(serializer.data)

    
    # RESOLVE (PATCH /card-relations/{id}/resolve) — mantém na lista com status resolvido
    @detail_route(methods=["patch"])
    def resolve(self, request, **kwargs):
        instance = self.get_object()
        project = instance.project

        if project is not None:
            self.check_permissions(request, "update", project)
            perm_error = self._check_card_type_perm(request, project, instance.source_type, instance.target_type)
            if perm_error:
                return perm_error
            if project.blocked_code is not None:
                raise exc.Blocked(_("Projeto bloqueado."))
        else:
            self.check_permissions(request, "update", None)

        if not instance.is_active:
            return response.BadRequest({"_error_code": "RELATION_ALREADY_DELETED"})

        if instance.is_resolved:
            return response.BadRequest({"_error_code": "RELATION_ALREADY_RESOLVED"})

        if instance.relation_type not in (RelationType.BLOCKS, RelationType.BLOCKED_BY):
            return response.BadRequest({"_error_code": "RESOLVE_ONLY_BLOCKING_RELATIONS"})

        validate = validators.CardRelationValidator()
        SourceModel, source_card_type = validate._get_model_for_type(instance.source_type)
        TargetModel, target_card_type = validate._get_model_for_type(instance.target_type)

        source_obj = SourceModel.objects.get(id=instance.source_id, project_id=project.id)
        target_obj = TargetModel.objects.get(id=instance.target_id, project_id=project.id)

        if instance.relation_type == RelationType.BLOCKS:
            blocked_obj = target_obj
            blocked_card_type = target_card_type
        else:
            blocked_obj = source_obj
            blocked_card_type = source_card_type

        before = history_services.cardrelation_freezer(instance)

        instance.is_resolved = True
        instance.resolved_by = request.user
        instance.resolved_date = timezone.now()
        instance.modified_by = request.user
        instance.modified_date = timezone.now()
        instance.save(update_fields=["is_resolved", "resolved_by", "resolved_date", "modified_by", "modified_date"])

        still_blocked = models.CardRelation.objects.filter(
            project=project,
            is_active=True,
            is_resolved=False,
            relation_type__in=(RelationType.BLOCKS, RelationType.BLOCKED_BY),
        ).filter(
            Q(source_type=blocked_card_type, source_id=blocked_obj.id)
            | Q(target_type=blocked_card_type, target_id=blocked_obj.id)
        )

        if not still_blocked.exists() and blocked_obj.is_blocked:
            blocked_obj.is_blocked = False
            blocked_obj.save(update_fields=["is_blocked"])

        create_cardrelation_activity_entries(
            before_relation=before,
            after_relation=None,
            user=request.user,
            history_type=HistoryType.change,
            action="resolved",
        )

        self.object = instance
        serializer = self.get_serializer(instance)
        return response.Ok(serializer.data)

    # DESTROY (SOFT DELETE (DEACTIVATE) /card-relations/{id}
    def destroy(self, request, **kwargs):
        instance = self.get_object()
        project = instance.project

        if project is not None:
            self.check_permissions(request, "destroy", project)
            perm_error = self._check_card_type_perm(request, project, instance.source_type, instance.target_type)
            if perm_error:
                return perm_error
            if project.blocked_code is not None:
                raise exc.Blocked(_("Projeto bloqueado."))
        else:
            self.check_permissions(request, "destroy", None)

        if not instance.is_active:
            return response.BadRequest({"_error_code": "RELATION_ALREADY_DELETED"})

        before = history_services.cardrelation_freezer(instance)

        if instance.relation_type in (RelationType.BLOCKS, RelationType.BLOCKED_BY):
            validate = validators.CardRelationValidator()

            SourceModel, source_card_type = validate._get_model_for_type(instance.source_type)
            TargetModel, target_card_type = validate._get_model_for_type(instance.target_type)

            source_obj = SourceModel.objects.get(
                id=instance.source_id, project_id=project.id
            )
            target_obj = TargetModel.objects.get(
                id=instance.target_id, project_id=project.id
            )

            if instance.relation_type == RelationType.BLOCKS:
                blocked_obj = target_obj
                blocked_card_type = target_card_type
            else:  # BLOCKED_BY
                blocked_obj = source_obj
                blocked_card_type = source_card_type

            instance.is_active = False
            instance.save(update_fields=["is_active", "modified_date", "modified_by"])

            still_blocked = models.CardRelation.objects.filter(
                project=project,
                is_active=True,
                is_resolved=False,
                relation_type__in=(RelationType.BLOCKS, RelationType.BLOCKED_BY),
            ).filter(
                Q(source_type=blocked_card_type, source_id=blocked_obj.id)
                | Q(target_type=blocked_card_type, target_id=blocked_obj.id)
            )

            if not still_blocked.exists() and blocked_obj.is_blocked:
                blocked_obj.is_blocked = False
                blocked_obj.save(update_fields=["is_blocked"])

        else:
            instance.is_active = False
            instance.save(update_fields=["is_active", "modified_date", "modified_by"])

        create_cardrelation_activity_entries(
            before_relation=before,
            after_relation=None,
            user=request.user,
            history_type=HistoryType.change,
            action="removed",
        )

        return response.NoContent()
