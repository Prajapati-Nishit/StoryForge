from django.conf import settings
from django.db import models
from django.urls import reverse


GENRE_CHOICES = [(g, g) for g in [
    "Fantasy", "Sci-Fi", "Horror", "Mystery", "Romance", "Adventure",
    "Thriller", "Comedy", "Action", "Historical", "Crime", "Superhero",
    "Cyberpunk", "Steampunk", "Zombie", "Survival", "Magic", "Anime",
]]

THEME_CHOICES = [(t, t) for t in [
    "Love", "War", "Friendship", "AI", "Revenge", "Space", "Time Travel",
    "Magic", "Politics", "School", "Pirates", "Dreams",
]]

TONE_CHOICES = [(t, t) for t in [
    "Funny", "Dark", "Serious", "Emotional", "Epic", "Inspirational",
]]

AUDIENCE_CHOICES = [("Kids", "Kids"), ("Teen", "Teen"), ("Adult", "Adult")]

STYLE_CHOICES = [(s, s) for s in [
    "Simple", "Professional", "Poetic", "Novel", "Movie Script", "Comic",
]]

LENGTH_CHOICES = [
    ("500", "500 words"), ("1000", "1000 words"), ("3000", "3000 words"),
    ("10000", "10000 words"), ("novel", "Novel"),
]


class Story(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stories",
        null=True, blank=True,
    )
    seed_prompt = models.TextField()
    title = models.CharField(max_length=220)
    genre = models.CharField(max_length=40, choices=GENRE_CHOICES, default="Fantasy")
    theme = models.CharField(max_length=60, blank=True)
    tone = models.CharField(max_length=40, choices=TONE_CHOICES, default="Epic")
    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default="Teen")
    style = models.CharField(max_length=40, choices=STYLE_CHOICES, default="Novel")
    length = models.CharField(max_length=10, choices=LENGTH_CHOICES, default="1000")
    tagline = models.CharField(max_length=240, blank=True)
    summary = models.TextField(blank=True)
    # Complete generated story (500/1000/3000 words)
    full_story = models.TextField(blank=True)
    structure_beginning = models.TextField(blank=True)
    structure_conflict = models.TextField(blank=True)
    structure_rising_action = models.TextField(blank=True)
    structure_climax = models.TextField(blank=True)
    structure_ending = models.TextField(blank=True)
    plot_twist = models.TextField(blank=True)
    ending = models.TextField(blank=True)
    cover_seed = models.CharField(max_length=20, blank=True)
    is_favorite = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    generated_by_ai = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("story_detail", args=[self.pk])

    @property
    def word_count(self):
        parts = [self.summary, self.plot_twist, self.ending,
                  self.structure_beginning, self.structure_conflict,
                  self.structure_rising_action, self.structure_climax]
        parts += [c.summary for c in self.chapters.all()]
        parts += [d.line for d in self.dialogue_lines.all()]
        return sum(len(p.split()) for p in parts if p)

    @property
    def reading_time_minutes(self):
        return max(1, round(self.word_count / 200))


class WorldDetail(models.Model):
    story = models.OneToOneField(Story, on_delete=models.CASCADE, related_name="world")
    name = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    kingdoms_cities = models.CharField(max_length=240, blank=True)
    magic_or_technology = models.CharField(max_length=240, blank=True)
    climate = models.CharField(max_length=160, blank=True)
    culture = models.CharField(max_length=240, blank=True)
    history = models.TextField(blank=True)

    def __str__(self):
        return self.name or f"World of {self.story.title}"


class Character(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="characters")
    name = models.CharField(max_length=120)
    age = models.CharField(max_length=40, blank=True)
    role = models.CharField(max_length=80, blank=True)
    occupation = models.CharField(max_length=120, blank=True)
    personality = models.CharField(max_length=240, blank=True)
    goal = models.CharField(max_length=240, blank=True)
    weakness = models.CharField(max_length=240, blank=True)
    strength = models.CharField(max_length=240, blank=True)
    skills = models.CharField(max_length=240, blank=True)
    secrets = models.CharField(max_length=240, blank=True)
    backstory = models.TextField(blank=True)
    avatar_seed = models.CharField(max_length=20, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Chapter(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="chapters")
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Ch.{self.order}: {self.title}"


class DialogueLine(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="dialogue_lines")
    order = models.PositiveIntegerField(default=0)
    character_name = models.CharField(max_length=120)
    line = models.TextField()

    class Meta:
        ordering = ["order", "id"]


class SequelIdea(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="sequel_ideas")
    text = models.CharField(max_length=280)


class PromptHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="prompt_history",
        null=True, blank=True,
    )
    prompt_text = models.TextField()
    genre = models.CharField(max_length=40, blank=True)
    tone = models.CharField(max_length=40, blank=True)
    audience = models.CharField(max_length=10, blank=True)
    resulting_story = models.ForeignKey(
        Story, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Prompt history"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    default_genre = models.CharField(max_length=40, choices=GENRE_CHOICES, default="Fantasy")
    dark_mode = models.BooleanField(default=True)
    font_size = models.CharField(
        max_length=10,
        choices=[("sm", "Small"), ("md", "Medium"), ("lg", "Large")],
        default="md",
    )
    language = models.CharField(max_length=10, default="en")
    anthropic_api_key = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"
