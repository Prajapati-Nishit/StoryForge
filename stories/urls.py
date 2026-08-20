from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("new/", views.new_story, name="new_story"),
    path("story/<int:pk>/", views.story_detail, name="story_detail"),
    path("story/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("story/<int:pk>/archive/", views.toggle_archive, name="toggle_archive"),
    path("story/<int:pk>/delete/", views.delete_story, name="delete_story"),
    path("story/<int:pk>/duplicate/", views.duplicate_story, name="duplicate_story"),
    path("story/<int:pk>/regenerate/<str:field>/", views.regenerate, name="regenerate"),
    path("story/<int:pk>/download/<str:fmt>/", views.download_story, name="download_story"),
    path("library/", views.library, name="library"),
    path("archive/", views.archive_view, name="archive"),
    path("characters/", views.characters_view, name="characters"),
    path("worlds/", views.worlds_view, name="worlds"),
    path("prompt-history/", views.prompt_history_view, name="prompt_history"),
    path("templates/", views.templates_view, name="templates"),
    path("profile/", views.profile_view, name="profile"),
    path("settings/", views.settings_view, name="settings"),
    path("search/", views.search_view, name="search"),
]
