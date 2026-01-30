from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from the_wall_api.wall.models import DailyLog
from the_wall_api.wall.models import WallProfile
from the_wall_api.wall.serializers import DailyIceSerializer
from the_wall_api.wall.serializers import GlobalOverviewSerializer
from the_wall_api.wall.serializers import ProfileOverviewSerializer


class WallViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WallProfile.objects.all()
    lookup_field = "profile_number"

    @method_decorator(cache_page(60 * 60))
    @method_decorator(vary_on_cookie)
    @action(detail=True, methods=["get"], url_path=r"days/(?P<day_number>\d+)")
    def daily_ice(self, request, profile_number=None, day_number=None):
        profile = self.get_object()
        log = profile.logs.filter(day_number=day_number).first()

        serializer = DailyIceSerializer(
            {
                "day": str(day_number),
                "ice_amount": str(log.ice_used if log else 0),
            },
        )
        return Response(serializer.data)

    @method_decorator(cache_page(60 * 60))
    @method_decorator(vary_on_cookie)
    @action(detail=True, methods=["get"], url_path=r"overview(?:/(?P<day_number>\d+))?")
    def profile_overview(self, request, profile_number=None, day_number=None):
        profile = self.get_object()
        ctx_day = int(day_number) if day_number is not None else None
        serializer = ProfileOverviewSerializer(
            profile,
            context={"day_number": ctx_day},
        )
        return Response(serializer.data)

    @method_decorator(cache_page(60 * 60))
    @method_decorator(vary_on_cookie)
    @action(
        detail=False,
        methods=["get"],
        url_path=r"overview(?:/(?P<day_number>\d+))?",
    )
    def overview(self, request, day_number=None):
        logs = DailyLog.objects.all()
        ctx_day = int(day_number) if day_number is not None else None
        serializer = GlobalOverviewSerializer(
            logs,
            context={"day_number": ctx_day},
        )
        return Response(serializer.data)
