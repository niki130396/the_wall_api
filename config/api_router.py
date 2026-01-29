from django.conf import settings
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from the_wall_api.users.api.views import UserViewSet
from the_wall_api.wall.views import WallViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)
router.register("profiles", WallViewSet, basename="profiles")

app_name = "api"
urlpatterns = router.urls
