from django.contrib import admin

from .models import (
    Story, Character, WorldDetail, Chapter, DialogueLine,
    SequelIdea, PromptHistory, UserProfile,
)


class CharacterInline(admin.TabularInline):
    model = Character
    extra = 0


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0


class SequelIdeaInline(admin.TabularInline):
    model = SequelIdea
    extra = 0


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "genre", "tone", "is_favorite", "generated_by_ai", "created_at")
    list_filter = ("genre", "tone", "audience", "is_favorite", "is_archived", "generated_by_ai")
    search_fields = ("title", "seed_prompt", "summary")
    inlines = [CharacterInline, ChapterInline, SequelIdeaInline]


@admin.register(WorldDetail)
class WorldDetailAdmin(admin.ModelAdmin):
    list_display = ("name", "story")


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "story", "role", "age")


@admin.register(DialogueLine)
class DialogueLineAdmin(admin.ModelAdmin):
    list_display = ("story", "character_name", "order")


@admin.register(PromptHistory)
class PromptHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "prompt_text", "genre", "created_at")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "default_genre", "dark_mode")
