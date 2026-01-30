from django.db.models import Sum
from rest_framework import serializers

from the_wall_api.wall.constants import COST_PER_CUBIC_YARD
from the_wall_api.wall.models import WallProfile


class DailyIceSerializer(serializers.Serializer):
    day = serializers.CharField()
    ice_amount = serializers.CharField()


class ProfileOverviewSerializer(serializers.ModelSerializer):
    day = serializers.SerializerMethodField()
    cost = serializers.SerializerMethodField()

    class Meta:
        model = WallProfile
        fields = ["day", "cost"]

    def get_day(self, obj):
        return str(self.context.get("day_number") or "None")

    def get_cost(self, obj):
        day_number = self.context.get("day_number")
        logs = obj.logs.all()
        if day_number is not None:
            logs = logs.filter(day_number__lte=day_number)

        total_ice = logs.aggregate(total=Sum("ice_used"))["total"] or 0
        return f"{total_ice * COST_PER_CUBIC_YARD:,}"


class GlobalOverviewSerializer(serializers.Serializer):
    day = serializers.SerializerMethodField()
    cost = serializers.SerializerMethodField()

    def get_day(self, obj):
        day = self.context.get("day_number")
        return str(day) if day is not None else "None"

    def get_cost(self, obj):
        day_number = self.context.get("day_number")
        logs = obj  # This is DailyLog.objects.all() from the view

        if day_number is not None:
            # Now that day_number is an int, __lte will work perfectly
            logs = logs.filter(day_number__lte=day_number)

        total_ice = logs.aggregate(total=Sum("ice_used"))["total"] or 0
        return f"{total_ice * COST_PER_CUBIC_YARD:,}"
