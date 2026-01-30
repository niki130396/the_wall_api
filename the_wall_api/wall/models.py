from django.db import models
from django.db.models import Sum

from the_wall_api.wall.constants import COST_PER_CUBIC_YARD


class WallProfile(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    profile_number = models.PositiveIntegerField(unique=True, db_index=True)

    def __str__(self):
        return self.name

    def total_cost(self, day=None):
        """Calculates cost up to a specific day or total if day is None"""
        logs = self.logs.all()
        if day is not None:
            logs = logs.filter(day_number__lte=day)

        total_ice = logs.aggregate(total=Sum("ice_used"))["total"] or 0
        return total_ice * COST_PER_CUBIC_YARD


class WallSection(models.Model):
    profile = models.ForeignKey(
        WallProfile,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    section_index = models.PositiveIntegerField()
    # Adding an index here is crucial for performance with large config files
    height = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        unique_together = ("profile", "section_index")
        ordering = ["profile", "section_index"]

    def __str__(self):
        return f"{self.profile.name} - Section {self.section_index} ({self.height}ft)"


class DailyLog(models.Model):
    profile = models.ForeignKey(
        WallProfile,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    day_number = models.PositiveIntegerField(db_index=True)
    ice_used = models.PositiveIntegerField()

    class Meta:
        unique_together = ("profile", "day_number")
        ordering = ["day_number"]

    def __str__(self):
        return f"Day {self.day_number} - {self.profile.name}"
