from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    Story, GENRE_CHOICES, THEME_CHOICES, TONE_CHOICES,
    AUDIENCE_CHOICES, STYLE_CHOICES, LENGTH_CHOICES, UserProfile,
)


class StoryPromptForm(forms.Form):
    seed_prompt = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "A detective receives a phone call from the future...",
            "class": "prompt-textarea",
        }),
        max_length=600,
        label="",
    )
    genre = forms.ChoiceField(choices=GENRE_CHOICES, initial="Fantasy")
    theme = forms.ChoiceField(choices=THEME_CHOICES, initial="Magic")
    tone = forms.ChoiceField(choices=TONE_CHOICES, initial="Epic")
    audience = forms.ChoiceField(choices=AUDIENCE_CHOICES, initial="Teen")
    style = forms.ChoiceField(choices=STYLE_CHOICES, initial="Novel")
    length = forms.ChoiceField(choices=LENGTH_CHOICES, initial="1000")


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class SettingsForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["default_genre", "dark_mode", "font_size", "language", "anthropic_api_key"]
        widgets = {
            "anthropic_api_key": forms.PasswordInput(render_value=True, attrs={
                "placeholder": "sk-ant-... (optional, enables real AI generation)"
            }),
        }
