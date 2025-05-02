# tweets/admin.py
from django.contrib import admin

from .models import Note
from .models import TwitterCredentials


@admin.register(Note)
class TweetAdmin(admin.ModelAdmin):
    list_display = ("content", "status", "scheduled_time", "created_at", "published_at")
    list_filter = ("status", "created_at", "published_at")
    search_fields = ("content",)
    readonly_fields = ("published_at", "tweet_id")
    actions = ["mark_as_pending"]

    @admin.action(
        description="Marcar tweets seleccionados como pendientes",
    )
    def mark_as_pending(self, request, queryset):
        queryset.update(status="pending", published_at=None, tweet_id=None)


@admin.register(TwitterCredentials)
class TwitterCredentialsAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "updated_at")
    search_fields = ("user__username",)
    readonly_fields = ("created_at", "updated_at")
