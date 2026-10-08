import pytest
from taiga.projects.card_relations.validators import CardRelationValidator
from taiga.projects.card_relations.models import CardRelation
from taiga.projects.card_relations.choices import CardType, RelationType
from .. import factories as f
import unittest as u
from unittest.mock import Mock


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def project():
    return f.ProjectFactory.create()

@pytest.fixture
def issue(project):
    return f.IssueFactory.create(project=project)

@pytest.fixture
def another_issue(project):
    return f.IssueFactory.create(project=project)


def test_cannot_relate_with_itself(project, issue):
    validator=CardRelationValidator(data={
        "project_id": project.id,
        "source_type": CardType.ISSUE,
        "source_id": issue.id,
        "target_type": CardType.ISSUE,
        "target_id": issue.id,
        "relation_type": RelationType.RELATED_TO,
    })
    
    assert not validator.is_valid()
    

def test_valid_relationship(project, issue, another_issue):
    validator = CardRelationValidator(data={
        "project_id": project.id,
        "source_type": CardType.ISSUE,
        "source_id": issue.id,
        "target_type": CardType.ISSUE,
        "target_id": another_issue.id,
        "relation_type": RelationType.RELATED_TO,
    })

    assert validator.is_valid()

def test_not_supported_relation_type(project, issue, another_issue):
    validator = CardRelationValidator(data={
        "project_id": project.id,
        "source_type": CardType.ISSUE,
        "source_id": issue.id,
        "target_type": CardType.ISSUE,
        "target_id": another_issue.id,
        "relation_type": "abobrinha",
    })
    
    assert not validator.is_valid()
    
def test_not_supported_activity_type(project, issue, another_issue):
    validator = CardRelationValidator(data={
        "project_id": project.id,
        "source_type": "abobrinha",
        "source_id": issue.id,
        "target_type": CardType.ISSUE,
        "target_id": another_issue.id,
        "relation_type": RelationType.RELATED_TO,
    })
    
    assert not validator.is_valid()
    
def test_cannot_relate_items_from_different_projects(project, issue):
    other_project = f.ProjectFactory.create()
    issue_from_other_project = f.IssueFactory.create(project=other_project)
    
    validator = CardRelationValidator(data={
        "project_id": project.id,
        "source_type": CardType.ISSUE,
        "source_id": issue.id,
        "target_type": CardType.ISSUE,
        "target_id": issue_from_other_project.id,
        "relation_type": RelationType.RELATED_TO,
    })

    assert not validator.is_valid()
    
def test_cannot_create_duplicate_relation(project, issue, another_issue):
    # Cria a relação original no banco
    CardRelation.objects.create(
        project=project,
        source_type=CardType.ISSUE,
        source_id=issue.id,
        target_type=CardType.ISSUE,
        target_id=another_issue.id,
        relation_type=RelationType.RELATED_TO
    )

    # Tenta validar a criação da mesma relação novamente
    validator = CardRelationValidator(data={
        "project_id": project.id,
        "source_type": CardType.ISSUE,
        "source_id": issue.id,
        "target_type": CardType.ISSUE,
        "target_id": another_issue.id,
        "relation_type": RelationType.RELATED_TO,
    })

    assert not validator.is_valid()
    assert validator.errors == {"code": ["cards_already_related"]}

def test_cannot_create_reverse_symmetric_relation(project, issue, another_issue):
   
    CardRelation.objects.create(
        project=project,
        source_type=CardType.ISSUE,
        source_id=issue.id,
        target_type=CardType.ISSUE,
        target_id=another_issue.id,
        relation_type=RelationType.RELATED_TO 
    )

    # EXECUÇÃO: Tentamos validar a criação inversa B -> A
    validator = CardRelationValidator(data={
        "project_id": project.id,
        "source_type": CardType.ISSUE,
        "source_id": another_issue.id, # Invertido
        "target_type": CardType.ISSUE,
        "target_id": issue.id,         # Invertido
        "relation_type": RelationType.RELATED_TO,
    })

    assert not validator.is_valid()
    assert validator.errors == {"code": ["cards_already_related"]}