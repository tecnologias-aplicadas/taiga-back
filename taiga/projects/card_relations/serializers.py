from taiga.base.api import serializers
from taiga.projects.mixins.serializers import (
    OwnerExtraInfoSerializerMixin,
    ProjectExtraInfoSerializerMixin,
)
from taiga.base.fields import Field, MethodField
from taiga.base.neighbors import NeighborsSerializerMixin



class CardRelationListSerializer(ProjectExtraInfoSerializerMixin,serializers.LightSerializer):
    id = Field()
    project = Field(attr="project_id")

    source_type = Field()
    source_id = Field()
    source_ref = MethodField()

    target_type = Field()
    target_id = Field()
    target_ref = MethodField()

    relation_type = Field()
    relation_type_display = MethodField()

    created_date = Field()
    modified_date = Field()
    
    is_active = Field()
    is_resolved = Field()
    resolved_date = Field()

    def get_relation_type_display(self, obj):
        return obj.get_relation_type_display()

    def get_source_ref(self, obj):
        source = obj.get_source_object()
        return getattr(source, "ref", None) if source else None

    def get_target_ref(self, obj):
        target = obj.get_target_object()
        return getattr(target, "ref", None) if target else None


class CardRelationSerializer(ProjectExtraInfoSerializerMixin, serializers.LightSerializer):
    id = Field()
    project = Field(attr="project_id")

    source_type = Field()
    source_id = Field()
    source_ref = MethodField()

    target_type = Field()
    target_id = Field()
    target_ref = MethodField()

    relation_type = Field()
    relation_type_display = MethodField()

    created_date = Field()
    modified_date = Field()

    created_by = Field(attr="created_by_id")
    created_by_username = MethodField()

    modified_by = Field(attr="modified_by_id")
    modified_by_username = MethodField()
    
    is_active = Field()
    is_resolved = Field()
    resolved_date = Field()
    resolved_by = Field(attr="resolved_by_id")
    resolved_by_username = MethodField()

    def get_relation_type_display(self, obj):
        return obj.get_relation_type_display()

    def get_source_ref(self, obj):
        source = obj.get_source_object()
        return getattr(source, "ref", None) if source else None

    def get_target_ref(self, obj):
        target = obj.get_target_object()
        return getattr(target, "ref", None) if target else None

    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_modified_by_username(self, obj):
        return obj.modified_by.username if obj.modified_by else None
    
    def get_resolved_by_username(self, obj):
        return obj.resolved_by.username if obj.resolved_by else None


# class CardRelationNeighborsSerializer(NeighborsSerializerMixin, CardRelationListSerializer):
#     pass
