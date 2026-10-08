from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from .choices import RelationType, CardType, CARD_TYPE_MODEL_MAP
from taiga.projects.models import Project
from django.db.models import Q, UniqueConstraint, constraints


class CardRelation(models.Model):

    created_date = models.DateTimeField(
        verbose_name="created_date", 
        auto_now_add=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name="created_by", 
        null=True, 
        on_delete=models.SET_NULL,
        related_name="card_relations_created"
    )
    modified_date = models.DateTimeField(
        verbose_name="modified_date", 
        null=True,
        blank=True
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name="modified_by", 
        null=True,
        on_delete=models.SET_NULL,
        related_name="card_relations_modified"
    )
    project = models.ForeignKey(
        Project, 
        verbose_name=_("project"), 
        null=True,
        on_delete=models.SET_NULL, 
        related_name="card_relations"
    )
    source_type = models.CharField(
        max_length=20, 
        choices= CardType.choices,
        verbose_name=_("source_type"),
        null=True
    )
    source_id = models.PositiveIntegerField(
        verbose_name=_("source id"),
        null=True
    )
    target_type = models.CharField(
        max_length=20,
        choices=CardType.choices,
        verbose_name=_("target type"),
        null=True
    )
    target_id = models.PositiveIntegerField(
        verbose_name=_("target id"),
        null=True
    )
    relation_type = models.CharField(
        max_length= 10,
        choices= RelationType.choices,
        default=RelationType.RELATED_TO
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True
    )
    is_resolved = models.BooleanField(
        default=False,
        db_index=True
    )
    resolved_date = models.DateTimeField(
        verbose_name="resolved_date",
        null=True,
        blank=True
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name="resolved_by", 
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="card_relations_resolved"
    )
    class Meta:
        verbose_name = _("Card Relation")
        verbose_name_plural = _("Card Relations")
        constraints = [
            UniqueConstraint(
                fields=[
                    "project",
                    "source_type",
                    "source_id",
                    "target_type",
                    "target_id",
                    "relation_type"
                ],
                condition=Q(is_active=True),
                name="unique_active_card_relation"
            )
        ]
        
    def __str__(self):
        return f"{self.get_source_display()} {self.get_relation_type_display()} {self.get_target_display()}"

    def _get_model_for_type(self, card_type):
        return CARD_TYPE_MODEL_MAP.get(card_type)

    def get_source_object(self):
        Model = self._get_model_for_type(self.source_type)
        if Model is None:
            return None
        try:
            return Model.objects.get(pk=self.source_id)
        except Model.DoesNotExist:
            return None

    def get_target_object(self):
        Model = self._get_model_for_type(self.target_type)
        if Model is None:
            return None
        try:
            return Model.objects.get(pk=self.target_id)
        except Model.DoesNotExist:
            return None

    def get_source_display(self):
        obj = self.get_source_object()
        return getattr(obj, "ref", None) or str(obj) if obj else f"{self.source_type}:{self.source_id}"

    def get_target_display(self):
        obj = self.get_target_object()
        return getattr(obj, "ref", None) or str(obj) if obj else f"{self.target_type}:{self.target_id}"