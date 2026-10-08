from django.db import models
from django.utils.translation import gettext_lazy as _
from taiga.projects.issues.models import Issue
from taiga.projects.userstories.models import UserStory
from taiga.projects.tasks.models import Task
from taiga.projects.epics.models import Epic

class RelationType(models.TextChoices):
        RELATED_TO= "RT", _("RELATED TO")
        BLOCKS = "BK", _("BLOCKS")
        BLOCKED_BY = "BKBY", _("BLOCKED BY")
        DEPENDS_ON = "DPON", _("DEPENDS ON")
        DEPENDS_ME = "DPME", _("DEPENDS ME")
        DUPLICATED_BY = "DUBY", _("DUPLICATED BY")
        DUPLICATED_FROM = "DUFROM",_("DUPLICATED_FROM")
        DISCOVERD_WHILE_TESTING = "DWT", _("DISCOVERED WHILE TESTING")
        LED_TO_DISCOVER_DURING_TESTING = "LTDWT", _("LED TO DISCOVERED DURING TESTING")

        
class CardType (models.TextChoices):
        ISSUE = "issue", _("Issue")
        USERSTORY = "userstory", _("User story")
        TASK = "task", _("Task")
        EPIC = "epic", _("Epic")
        

CARD_TYPE_MODEL_MAP = {
    CardType.ISSUE: Issue,
    CardType.USERSTORY: UserStory,
    CardType.TASK: Task,
    CardType.EPIC: Epic,
}