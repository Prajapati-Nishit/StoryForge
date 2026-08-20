from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from . import services, exporters
from .forms import StoryPromptForm, RegisterForm, SettingsForm
from .models import Story, Character, WorldDetail, Chapter, DialogueLine, SequelIdea, PromptHistory


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "stories/landing.html", {"form": StoryPromptForm()})


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f"Welcome to StoryForge, {user.username}.")
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
def dashboard(request):
    recent_stories = request.user.stories.all()[:6]
    favorites = request.user.stories.filter(is_favorite=True)[:4]
    recent_characters = Character.objects.filter(story__user=request.user).order_by("-id")[:6]
    recent_worlds = WorldDetail.objects.filter(story__user=request.user).order_by("-id")[:4]
    stats = {
        "story_count": request.user.stories.count(),
        "word_count": sum(s.word_count for s in request.user.stories.all()),
        "favorite_count": favorites.count(),
    }
    templates = [
        {"seed": "A boy finds a mysterious watch that runs backward.", "genre": "Fantasy"},
        {"seed": "A detective receives a phone call from the future.", "genre": "Sci-Fi"},
        {"seed": "A girl discovers a hidden kingdom beneath the ocean.", "genre": "Adventure"},
        {"seed": "A soldier wakes up with no memory of the war he just won.", "genre": "Thriller"},
    ]
    return render(request, "stories/dashboard.html", {
        "recent_stories": recent_stories,
        "favorites": favorites,
        "recent_characters": recent_characters,
        "recent_worlds": recent_worlds,
        "stats": stats,
        "templates": templates,
    })


@login_required
def new_story(request):
    if request.method == "POST":
        form = StoryPromptForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            data, ai_generated, warning = services.generate_story_data(
                cd["seed_prompt"], cd["genre"], cd["theme"], cd["tone"],
                cd["audience"], cd["style"], cd["length"], user=request.user,
            )
            story = _persist_story(request.user, cd, data, ai_generated)
            PromptHistory.objects.create(
                user=request.user, prompt_text=cd["seed_prompt"], genre=cd["genre"],
                tone=cd["tone"], audience=cd["audience"], resulting_story=story,
            )
            if warning:
                # Ollama was unreachable, timed out, or returned something
                # unusable — the user still gets a complete story (either
                # the offline generator or an outline-assembled story),
                # but we tell them what happened.
                messages.warning(request, warning)
            else:
                messages.success(request, "Story generated.")
            return redirect("story_detail", pk=story.pk)
        messages.error(request, "Enter a story seed to continue.")
    else:
        form = StoryPromptForm()
    return render(request, "stories/new_story.html", {"form": form})


def _persist_story(user, cd, data, ai_generated):
    import random as _r
    story = Story.objects.create(
        user=user,
        seed_prompt=cd["seed_prompt"],
        title=data.get("title", "Untitled Story")[:220],
        genre=cd["genre"],
        theme=data.get("theme", cd["theme"])[:60],
        tone=cd["tone"],
        audience=cd["audience"],
        style=cd["style"],
        length=cd["length"],
        tagline=data.get("tagline", "")[:240],

        summary=data.get("summary", ""),
        full_story=data.get("full_story", ""),

        structure_beginning=data.get("structure", {}).get("beginning", ""),
        structure_conflict=data.get("structure", {}).get("conflict", ""),
        structure_rising_action=data.get("structure", {}).get("rising_action", ""),
        structure_climax=data.get("structure", {}).get("climax", ""),
        structure_ending=data.get("structure", {}).get("ending", ""),
        plot_twist=data.get("plot_twist", ""),
        ending=data.get("ending", ""),
        cover_seed=str(_r.randint(1000, 9999)),
        generated_by_ai=ai_generated,
    )
    world = data.get("world", {})
    if world:
        WorldDetail.objects.create(
            story=story,
            name=world.get("name", "")[:120],
            description=world.get("description", ""),
            kingdoms_cities=world.get("kingdoms_cities", "")[:240],
            magic_or_technology=world.get("magic_or_technology", "")[:240],
            climate=world.get("climate", "")[:160],
            culture=world.get("culture", "")[:240],
            history=world.get("history", ""),
        )
    for c in data.get("characters", []):
        Character.objects.create(
            story=story,
            name=c.get("name", "Unnamed")[:120],
            age=str(c.get("age", ""))[:40],
            role=c.get("role", "")[:80],
            occupation=c.get("occupation", "")[:120],
            personality=c.get("personality", "")[:240],
            goal=c.get("goal", "")[:240],
            weakness=c.get("weakness", "")[:240],
            strength=c.get("strength", "")[:240],
            skills=c.get("skills", "")[:240],
            secrets=c.get("secrets", "")[:240],
            backstory=c.get("backstory", ""),
            avatar_seed=str(_r.randint(1000, 9999)),
        )
    for i, ch in enumerate(data.get("chapters", []), start=1):
        Chapter.objects.create(story=story, order=i, title=ch.get("title", f"Chapter {i}")[:200], summary=ch.get("summary", ""))
    for i, d in enumerate(data.get("dialogue", []), start=1):
        DialogueLine.objects.create(story=story, order=i, character_name=d.get("character", "")[:120], line=d.get("line", ""))
    for s in data.get("sequel_ideas", []):
        SequelIdea.objects.create(story=story, text=str(s)[:280])
    return story


@login_required
def story_detail(request, pk):
    story = get_object_or_404(Story, pk=pk, user=request.user)
    return render(request, "stories/story_detail.html", {"story": story})


@login_required
@require_POST
def toggle_favorite(request, pk):
    story = get_object_or_404(Story, pk=pk, user=request.user)
    story.is_favorite = not story.is_favorite
    story.save(update_fields=["is_favorite"])
    return redirect(request.META.get("HTTP_REFERER", "library"))


@login_required
@require_POST
def toggle_archive(request, pk):
    story = get_object_or_404(Story, pk=pk, user=request.user)
    story.is_archived = not story.is_archived
    story.save(update_fields=["is_archived"])
    return redirect(request.META.get("HTTP_REFERER", "library"))


@login_required
@require_POST
def delete_story(request, pk):
    story = get_object_or_404(Story, pk=pk, user=request.user)
    story.delete()
    messages.success(request, "Story deleted.")
    return redirect("library")


@login_required
@require_POST
def duplicate_story(request, pk):
    original = get_object_or_404(Story, pk=pk, user=request.user)
    story = Story.objects.create(
        user=request.user, seed_prompt=original.seed_prompt, title=f"{original.title} (Copy)",
        genre=original.genre, theme=original.theme, tone=original.tone, audience=original.audience,
        style=original.style, length=original.length, tagline=original.tagline, summary=original.summary,
        full_story=original.full_story,
        structure_beginning=original.structure_beginning, structure_conflict=original.structure_conflict,
        structure_rising_action=original.structure_rising_action, structure_climax=original.structure_climax,
        structure_ending=original.structure_ending, plot_twist=original.plot_twist, ending=original.ending,
        cover_seed=original.cover_seed, generated_by_ai=original.generated_by_ai,
    )
    if hasattr(original, "world"):
        w = original.world
        WorldDetail.objects.create(story=story, name=w.name, description=w.description,
                                     kingdoms_cities=w.kingdoms_cities, magic_or_technology=w.magic_or_technology,
                                     climate=w.climate, culture=w.culture, history=w.history)
    for c in original.characters.all():
        Character.objects.create(story=story, name=c.name, age=c.age, role=c.role, occupation=c.occupation,
                                   personality=c.personality, goal=c.goal, weakness=c.weakness, strength=c.strength,
                                   skills=c.skills, secrets=c.secrets, backstory=c.backstory,
                                   avatar_seed=c.avatar_seed, order=c.order)
    for ch in original.chapters.all():
        Chapter.objects.create(story=story, order=ch.order, title=ch.title, summary=ch.summary)
    for d in original.dialogue_lines.all():
        DialogueLine.objects.create(story=story, order=d.order, character_name=d.character_name, line=d.line)
    for s in original.sequel_ideas.all():
        SequelIdea.objects.create(story=story, text=s.text)
    messages.success(request, "Story duplicated.")
    return redirect("story_detail", pk=story.pk)


@login_required
@require_POST
def regenerate(request, pk, field):
    story = get_object_or_404(Story, pk=pk, user=request.user)
    if field not in {"twist", "ending", "continue"}:
        messages.error(request, "Unknown regeneration request.")
        return redirect("story_detail", pk=pk)

    result, ai_generated = services.regenerate_field(field, story, user=request.user)
    if field == "twist":
        story.plot_twist = result
        story.save(update_fields=["plot_twist"])
        messages.success(request, "New plot twist generated.")
    elif field == "ending":
        story.ending = result
        story.save(update_fields=["ending"])
        messages.success(request, "New ending generated.")
    elif field == "continue":
        next_order = story.chapters.count() + 1
        Chapter.objects.create(story=story, order=next_order, title=result.get("title", f"Chapter {next_order}"),
                                 summary=result.get("summary", ""))
        messages.success(request, "Story continued with a new chapter.")
    return redirect("story_detail", pk=pk)


@login_required
def download_story(request, pk, fmt):
    story = get_object_or_404(Story, pk=pk, user=request.user)
    if fmt == "pdf":
        return exporters.export_pdf(story)
    if fmt == "docx":
        return exporters.export_docx(story)
    if fmt == "md":
        return exporters.export_markdown(story)
    return exporters.export_txt(story)


@login_required
def library(request):
    stories = request.user.stories.filter(is_archived=False)
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "recent")
    only_favorites = request.GET.get("favorites") == "1"

    if q:
        stories = stories.filter(Q(title__icontains=q) | Q(genre__icontains=q) | Q(theme__icontains=q))
    if only_favorites:
        stories = stories.filter(is_favorite=True)
    if sort == "title":
        stories = stories.order_by("title")
    elif sort == "oldest":
        stories = stories.order_by("created_at")
    else:
        stories = stories.order_by("-updated_at")

    return render(request, "stories/library.html", {
        "stories": stories, "q": q, "sort": sort, "only_favorites": only_favorites,
    })


@login_required
def archive_view(request):
    stories = request.user.stories.filter(is_archived=True)
    return render(request, "stories/archive.html", {"stories": stories})


@login_required
def characters_view(request):
    characters = Character.objects.filter(story__user=request.user).select_related("story")
    return render(request, "stories/characters.html", {"characters": characters})


@login_required
def worlds_view(request):
    worlds = WorldDetail.objects.filter(story__user=request.user).select_related("story")
    return render(request, "stories/worlds.html", {"worlds": worlds})


@login_required
def prompt_history_view(request):
    history = request.user.prompt_history.all()[:50]
    return render(request, "stories/prompt_history.html", {"history": history})


@login_required
def templates_view(request):
    templates = [
        {"name": "Hidden Kingdom", "seed": "A girl discovers a hidden kingdom beneath the ocean.", "genre": "Adventure"},
        {"name": "Time-Turned Detective", "seed": "A detective receives a phone call from the future.", "genre": "Sci-Fi"},
        {"name": "The Backward Watch", "seed": "A boy finds a mysterious watch that runs backward.", "genre": "Fantasy"},
        {"name": "Amnesiac Soldier", "seed": "A soldier wakes up with no memory of the war he just won.", "genre": "Thriller"},
        {"name": "Last Signal", "seed": "An AI on a dying satellite sends one final message to Earth.", "genre": "Sci-Fi"},
        {"name": "The Uninvited Guest", "seed": "A wedding guest nobody remembers inviting knows everyone's secrets.", "genre": "Mystery"},
    ]
    return render(request, "stories/templates.html", {"templates": templates})


@login_required
def profile_view(request):
    stories = request.user.stories.all()
    genre_counts = stories.values("genre").annotate(n=Count("id")).order_by("-n")
    favorite_genre = genre_counts[0]["genre"] if genre_counts else "—"
    stats = {
        "story_count": stories.count(),
        "word_count": sum(s.word_count for s in stories),
        "favorite_genre": favorite_genre,
        "achievements": _achievements(stories.count()),
    }
    return render(request, "stories/profile.html", {"stats": stats})


def _achievements(story_count):
    badges = []
    if story_count >= 1:
        badges.append("First story forged")
    if story_count >= 5:
        badges.append("Prolific plotter")
    if story_count >= 10:
        badges.append("World builder")
    if story_count >= 25:
        badges.append("Master storyteller")
    return badges


@login_required
def settings_view(request):
    profile = request.user.profile
    if request.method == "POST":
        form = SettingsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved.")
            return redirect("settings")
    else:
        form = SettingsForm(instance=profile)
    return render(request, "stories/settings.html", {"form": form})


@login_required
def search_view(request):
    q = request.GET.get("q", "").strip()
    stories = characters = worlds = []
    if q:
        stories = request.user.stories.filter(Q(title__icontains=q) | Q(summary__icontains=q))[:20]
        characters = Character.objects.filter(story__user=request.user, name__icontains=q)[:20]
        worlds = WorldDetail.objects.filter(story__user=request.user, name__icontains=q)[:20]
    return render(request, "stories/search_results.html", {
        "q": q, "stories": stories, "characters": characters, "worlds": worlds,
    })
