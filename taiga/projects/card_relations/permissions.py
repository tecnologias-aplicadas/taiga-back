from taiga.base.api.permissions import TaigaResourcePermission, IsAuthenticated, IsProjectAdmin, HasProjectPerm, IsSuperUser, AllowAny
from taiga.permissions.permissions import CommentAndOrUpdatePerm

class CardRelationPermission(TaigaResourcePermission):
    enough_perms = IsProjectAdmin() | IsSuperUser()
    global_perms = None
    retrieve_perms = AllowAny()
    create_perms = IsAuthenticated()
    update_perms = IsAuthenticated()
    destroy_perms = IsAuthenticated()
    list_perms = AllowAny()
    filters_data_perms = AllowAny()