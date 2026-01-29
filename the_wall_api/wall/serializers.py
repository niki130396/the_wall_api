from rest_framework import serializers
from django.db.models import Sum

from the_wall_api.wall.models import WallProfile

COST_PER_CUBIC_YARD = 1900


class DailyIceSerializer(serializers.Serializer):
    day = serializers.CharField()
    ice_amount = serializers.CharField()


class ProfileOverviewSerializer(serializers.ModelSerializer):
    day = serializers.SerializerMethodField()
    cost = serializers.SerializerMethodField()

    class Meta:
        model = WallProfile
        fields = ['day', 'cost']

    def get_day(self, obj):
        return str(self.context.get('day_number') or "None")

    def get_cost(self, obj):
        day_number = self.context.get('day_number')
        logs = obj.logs.all()
        if day_number:
            logs = logs.filter(day_number__lte=day_number)

        total_ice = logs.aggregate(total=Sum('ice_used'))['total'] or 0
        return f"{total_ice * COST_PER_CUBIC_YARD:,}"


class GlobalOverviewSerializer(serializers.Serializer):
    day = serializers.CharField()
    cost = serializers.SerializerMethodField()

    def get_cost(self, obj):
        # In this case, 'obj' is the QuerySet of DailyLogs passed from the view
        day_number = self.context.get('day_number')
        logs = obj
        if day_number:
            logs = logs.filter(day_number__lte=day_number)

        total_ice = logs.aggregate(total=Sum('ice_used'))['total'] or 0
        return f"{total_ice * COST_PER_CUBIC_YARD:,}"
