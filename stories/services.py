"""
AI story generation service.

StoryForge generates a complete story plot from a short seed prompt using
a local Ollama server (https://ollama.com). If Ollama is not running, the
configured model isn't pulled, or the call fails for any reason, it
automatically falls back to a deterministic-but-randomized offline
generator so the app keeps working with zero external dependencies.
"""
import json
import random
import re

import requests
from django.conf import settings

OLLAMA_GENERATE_URL = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"

SYSTEM_PROMPT = """You are a story architect for an app called StoryForge AI.
Output ONLY raw JSON, no markdown fences, no commentary, no preamble.
Match this exact schema:
{
"title": "evocative title, under 8 words",
"theme": "under 5 words",
"tagline": "under 14 words",
"summary": "2-3 sentences, under 60 words",
"characters": [
  {"name":"string","age":"string","role":"Protagonist/Antagonist/Mentor/Companion/Side Character","occupation":"string","personality":"under 10 words","goal":"under 14 words","weakness":"under 10 words","strength":"under 10 words","skills":"under 10 words","secrets":"under 12 words","backstory":"under 30 words"}
],
"world": {"name":"string","description":"under 30 words","kingdoms_cities":"under 20 words","magic_or_technology":"under 20 words","climate":"under 12 words","culture":"under 20 words","history":"under 30 words"},
"structure": {"beginning":"under 20 words","conflict":"under 20 words","rising_action":"under 20 words","climax":"under 20 words","ending":"under 20 words"},
"chapters": [
  {"title":"under 7 words","summary":"under 28 words"}
],
"dialogue": [
  {"character":"string","line":"under 16 words"}
],
"plot_twist": "under 30 words",
"ending": "under 35 words",
"sequel_ideas": ["under 16 words", "under 16 words", "under 16 words"]
}
Rules: 3 to 4 items in characters, 5 items in chapters, 6 items in dialogue
alternating between two characters, exactly 3 sequel_ideas. Never exceed
word limits. Never add fields not listed. Tailor content precisely to the
requested genre, theme, tone, audience and writing style."""


FULL_STORY_SYSTEM_PROMPT = """
You are an award-winning novelist.

Write a complete story using the provided outline.

Rules:
- Return ONLY the story.
- Do not return JSON.
- Do not use markdown.
- Do not explain anything.
- Use proper paragraphs.
- Follow the outline exactly.
- Keep characters consistent.
- Keep the world consistent.
- Use dialogue naturally.
- Build suspense.
- Write a satisfying ending.
"""

class StoryGenerationError(Exception):
    pass


def _ollama_available():
    """Quick, cheap check that a local Ollama server is reachable."""
    try:
        resp = requests.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=2)
        return resp.ok
    except Exception:
        return False


def generate_story_data(seed, genre, theme, tone, audience, style, length, user=None):
    """Generate a full story blueprint (title, characters, world, chapters,
    the complete prose `full_story`, etc).

    Returns a 3-tuple: ``(data, ai_generated, warning)``.

    * ``data`` always matches the schema above and always includes a
      non-empty ``full_story`` key, so the caller/template never has to
      special-case a missing story.
    * ``ai_generated`` is True when the story outline came from Ollama.
    * ``warning`` is ``None`` on a fully successful AI generation, or a
      short, user-facing message explaining what went wrong and that a
      fallback was used.
    """
    if _ollama_available():
        try:
            data = _call_ollama(seed, genre, theme, tone, audience, style, length)
        except Exception as e:
            # Ollama is up, but the outline call failed (bad/empty
            # response, invalid JSON, timeout, etc). Fall back to the
            # offline generator so the user still gets a complete story.
            print("STORY OUTLINE ERROR:", e)
            data = _offline_generate(seed, genre, theme, tone, audience, style)
            return data, False, (
                "Ollama didn't return a usable story outline "
                f"({e}). Showing an offline-generated story instead."
            )

        try:
            data["full_story"] = _generate_full_story(
                seed, data, genre, theme, tone, audience, style, length,
            )
            return data, True, None
        except Exception as e:
            # Outline succeeded but the (much longer) full-story call
            # failed. Keep the AI-generated outline and assemble a
            # readable full story from it, rather than losing everything
            # or crashing the request.
            print("FULL STORY ERROR:", e)
            data["full_story"] = _offline_full_story(data)
            return data, True, (
                "The AI couldn't finish writing the full story text "
                f"({e}). Showing a story assembled from the generated "
                "outline instead."
            )

    data = _offline_generate(seed, genre, theme, tone, audience, style)
    return data, False, None


def regenerate_field(field, story, user=None):
    """Regenerate a single aspect of an existing story: 'twist', 'ending',
    'characters', 'world', or 'continue' (adds the next chapter)."""
    context = (f"Existing story titled '{story.title}' in genre {story.genre}, "
               f"theme {story.theme}, tone {story.tone}. Summary: {story.summary}")

    if _ollama_available():
        try:
            return _call_ollama_field(field, context, story), True
        except Exception:
            pass
    return _offline_regenerate_field(field, story), False


# ---------------------------------------------------------------------
# Ollama integration (local LLM, no API key required)
# ---------------------------------------------------------------------

def _call_ollama_raw(prompt, system, max_tokens=2000, timeout=120):
    """Low-level call to a local Ollama /api/generate endpoint.

    Raises StoryGenerationError with a clear, user-facing message on any
    failure: Ollama not running, request timeout, an HTTP error from
    Ollama, a non-JSON response, or an empty generated response.
    """
    payload = {
        "model": settings.OLLAMA_MODEL,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.9,
            "top_p": 0.95,
            "seed": random.randint(0, 2_147_483_647),
            "num_predict": max_tokens,
        },
    }

    try:
        resp = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError as e:
        raise StoryGenerationError(
            "Could not connect to Ollama. Make sure it is running "
            f"(`ollama serve`) and reachable at {settings.OLLAMA_BASE_URL}."
        ) from e
    except requests.exceptions.Timeout as e:
        raise StoryGenerationError(
            f"Ollama did not respond within {timeout}s. The model may be "
            "loading for the first time, or the request may be too large."
        ) from e
    except requests.exceptions.RequestException as e:
        raise StoryGenerationError(f"Request to Ollama failed: {e}") from e

    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise StoryGenerationError(
            f"Ollama returned an error (HTTP {resp.status_code}): {e}"
        ) from e

    try:
        body = resp.json()
    except ValueError as e:
        raise StoryGenerationError("Ollama returned an invalid (non-JSON) response.") from e

    text = (body.get("response") or "").strip()
    if not text:
        raise StoryGenerationError("Ollama returned an empty response.")
    return text


def _call_ollama(seed, genre, theme, tone, audience, style, length):
    user_prompt = (
        f'Story seed: "{seed}"\n'
        f"Genre: {genre}\n"
        f"Theme: {theme}\n"
        f"Tone: {tone}\n"
        f"Audience: {audience}\n"
        f"Writing style: {style}\n"
        f"Target length: {length}\n"
        "Build a complete story plot from this seed."
    )

    text = _call_ollama_raw(
        user_prompt,
        SYSTEM_PROMPT,
        max_tokens=2000,
        timeout=getattr(settings, "OLLAMA_OUTLINE_TIMEOUT", 120),
    )

    print("\n========== OLLAMA RAW OUTPUT ==========\n")
    print(text)
    print("\n=======================================\n")

    try:
        return _parse_json(text)
    except (json.JSONDecodeError, AttributeError) as e:
        raise StoryGenerationError(
            "Ollama's response wasn't valid JSON for the story outline."
        ) from e

def _generate_full_story(seed, blueprint, genre, theme, tone, audience, style, length):
    prompt = f"""
Story Seed:
{seed}

Genre:
{genre}

Theme:
{theme}

Tone:
{tone}

Audience:
{audience}

Writing Style:
{style}

Write approximately {length} words.
Do not stop early.
Do not summarize.
Write the complete story from beginning to end.
Story Outline:

Title:
{blueprint.get("title")}

Summary:
{blueprint.get("summary")}

Characters:
{json.dumps(blueprint.get("characters", []), indent=2)}

World:
{json.dumps(blueprint.get("world", {}), indent=2)}

Story Structure:
{json.dumps(blueprint.get("structure", {}), indent=2)}

Chapters:
{json.dumps(blueprint.get("chapters", []), indent=2)}

Plot Twist:
{blueprint.get("plot_twist")}

Ending:
{blueprint.get("ending")}
"""

    return _call_ollama_raw(
        prompt,
        FULL_STORY_SYSTEM_PROMPT,
        max_tokens=8000,
        timeout=getattr(settings, "OLLAMA_STORY_TIMEOUT", 300),
    )

def _call_ollama_field(field, context, story):
    prompts = {
        "twist": f"{context}\nWrite ONE new, surprising plot twist. Reply with plain text only, under 35 words.",
        "ending": f"{context}\nWrite a new ending. Reply with plain text only, under 40 words.",
        "continue": f"{context}\nWrite the next chapter. Reply with raw JSON only: {{\"title\": \"under 7 words\", \"summary\": \"under 30 words\"}}",
    }
    prompt = prompts.get(field, prompts["twist"])
    text = _call_ollama_raw(
        prompt,
        "You are a story writer. Follow the instruction exactly and output nothing else.",
        max_tokens=300,
    ).strip()
    if field == "continue":
        return _parse_json(text)
    return text


def _parse_json(raw):
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Local models sometimes add a stray sentence before/after the
        # JSON object. Fall back to grabbing the outermost {...} block.
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


# ---------------------------------------------------------------------
# Offline fallback generator (no external API required)
# ---------------------------------------------------------------------

_FIRST_NAMES = ["Aria", "Kael", "Nova", "Theo", "Sable", "Rowan", "Isolde", "Jax",
                "Wren", "Corvin", "Lyra", "Dashiell", "Mira", "Osric", "Zeph", "Thalia"]
_LAST_NAMES = ["Ashford", "Blackwood", "Voss", "Marrow", "Ferrers", "Quill",
               "Halloway", "Sterling", "Nightshade", "Cross", "Vane", "Emberly"]
_ROLES = ["Protagonist", "Antagonist", "Mentor", "Companion"]
_PERSONALITIES = ["stubborn but loyal", "quietly observant", "reckless and bold",
                   "guarded, slow to trust", "sharp-tongued and clever", "gentle but resolute"]
_GOALS = ["uncover the truth before it's too late", "protect the people they love",
          "reclaim what was stolen from them", "find a way home", "break a curse they carry"]
_WEAKNESSES = ["haunted by an old failure", "trusts too easily", "fears losing control",
               "carries a debt they can't repay", "cannot let go of the past"]
_STRENGTHS = ["unshakable resolve", "a gift for reading people", "tactical brilliance",
              "raw physical courage", "an uncanny memory for detail"]
_SKILLS = ["blade work", "old magic", "lockpicking and stealth", "strategy and command",
           "reading ancient scripts", "piloting"]
_SECRETS = ["is not who they claim to be", "made a bargain they regret",
            "once served the enemy", "is the last of a forgotten line"]

_WORLD_NAMES = ["Veyrath", "Osmere", "Thallow", "Kaelspire", "Duskmere", "Ashenreach"]
_KINGDOMS = ["the twin cities of Marrow and Cael", "a scattered archipelago of floating isles",
             "the walled capital and its outlying farm-villages", "seven rival city-states"]
_SYSTEMS = ["magic drawn from memory and cost", "salvaged pre-collapse technology",
            "a bloodline-bound elemental magic", "networked minds and rented bodies"]
_CLIMATES = ["perpetual twilight and cold winds", "storm-wracked coastlines", "arid dust plains",
             "dense rain-forest canopy"]
_CULTURES = ["a rigid caste of guilds and oaths", "nomadic clans bound by story-debt",
             "a faith built around a vanished god", "traders who worship precise contracts"]

_TWISTS = [
    "the mentor was working for the enemy all along",
    "the missing person was never missing, only hiding in plain sight",
    "the villain and the hero share the same blood",
    "the artifact everyone is chasing is cursed to destroy its bearer",
    "the world they're trying to save is not the real one",
]
_ENDINGS = [
    "the hero wins, but the cost reshapes who they are forever",
    "peace is bought with a sacrifice no one saw coming",
    "the war ends, but a quieter, more personal battle is only beginning",
    "they choose to walk away from everything they fought for",
]
_SEQUELS = [
    "a new threat rises from the ashes of the old one",
    "a secondary character inherits the burden left behind",
    "the sacrifice made in the finale was not permanent after all",
]


def _rand_seed():
    return str(random.randint(1000, 9999))


def _title_from_seed(seed, genre):
    words = re.findall(r"[A-Za-z']+", seed)
    keyword = next((w for w in words if len(w) > 4), None) or (genre)
    templates = [
        f"The {keyword.capitalize()} Chronicles",
        f"Shadows of {keyword.capitalize()}",
        f"The Last {keyword.capitalize()}",
        f"{keyword.capitalize()} and the Broken Vow",
    ]
    return random.choice(templates)


def _offline_generate(seed, genre, theme, tone, audience, style):
    title = _title_from_seed(seed, genre)
    world_name = random.choice(_WORLD_NAMES)

    characters = []
    for i in range(3):
        characters.append({
            "name": f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}",
            "age": str(random.randint(16, 45)),
            "role": _ROLES[i % len(_ROLES)],
            "occupation": random.choice(["wanderer", "scholar", "soldier", "smuggler", "healer"]),
            "personality": random.choice(_PERSONALITIES),
            "goal": random.choice(_GOALS),
            "weakness": random.choice(_WEAKNESSES),
            "strength": random.choice(_STRENGTHS),
            "skills": random.choice(_SKILLS),
            "secrets": random.choice(_SECRETS),
            "backstory": f"Grew up on the edges of {world_name}, shaped by a loss they rarely speak of.",
        })

    chapters = []
    chapter_titles = ["The Spark", "A Door Opens", "Cracks in the Plan",
                       "The Point of No Return", "What Remains"]
    for i, ct in enumerate(chapter_titles, start=1):
        chapters.append({
            "title": ct,
            "summary": f"Chapter {i} pushes {characters[0]['name'].split()[0]} deeper into {theme.lower() if theme else genre.lower()} and closer to the truth.",
        })

    dialogue = []
    a, b = characters[0]["name"].split()[0], characters[1]["name"].split()[0] if len(characters) > 1 else "A stranger"
    lines = [
        f"We don't have time for doubt now.",
        f"Doubt is the only thing keeping us alive.",
        f"Then we do this together, or not at all.",
        f"Together. Like always.",
        f"If this goes wrong, it was worth trying.",
        f"It was always going to be worth it.",
    ]
    for i, line in enumerate(lines):
        dialogue.append({"character": a if i % 2 == 0 else b, "line": line})

    data = {
        "title": title,
        "theme": theme or random.choice(["Loyalty", "Sacrifice", "Discovery"]),
        "tagline": f"One choice. One world. No going back.",
        "summary": (f"When {characters[0]['name'].split()[0]} stumbles into a secret tied to {seed.strip().rstrip('.').lower()}, "
                     f"they're pulled into a {tone.lower()} {genre.lower()} story that will test everything they believe."),
        "characters": characters,
        "world": {
            "name": world_name,
            "description": f"A {genre.lower()} realm built around {random.choice(_SYSTEMS)}.",
            "kingdoms_cities": random.choice(_KINGDOMS),
            "magic_or_technology": random.choice(_SYSTEMS),
            "climate": random.choice(_CLIMATES),
            "culture": random.choice(_CULTURES),
            "history": f"{world_name} was reshaped generations ago by a war few now remember clearly.",
        },
        "structure": {
            "beginning": f"{characters[0]['name'].split()[0]} discovers the seed of the story: {seed.strip()}",
            "conflict": f"A force tied to {theme.lower() if theme else genre.lower()} threatens everything they know.",
            "rising_action": "Alliances form and fracture as the stakes climb.",
            "climax": "A confrontation forces an irreversible choice.",
            "ending": random.choice(_ENDINGS),
        },
        "chapters": chapters,
        "dialogue": dialogue,
        "plot_twist": random.choice(_TWISTS),
        "ending": random.choice(_ENDINGS),
        "sequel_ideas": random.sample(_SEQUELS, 2) + [random.choice(_SEQUELS)],
    }
    data["full_story"] = _offline_full_story(data)
    return data


def _offline_full_story(data):
    """Assemble a readable, complete prose story out of a structured
    blueprint dict (as produced by either the Ollama outline call or the
    offline generator).

    Used in two situations:
    1. Fully offline mode (Ollama unavailable) — this is the only story
       text the user will see, so it must be a real, readable narrative.
    2. Ollama produced a valid outline but the separate "write the full
       story" call failed — this turns the outline into flowing prose
       instead of losing the story entirely.
    """
    paragraphs = []

    summary = data.get("summary")
    if summary:
        paragraphs.append(summary)

    world = data.get("world") or {}
    if world.get("description"):
        world_name = world.get("name", "").strip()
        prefix = f"In {world_name}, " if world_name else ""
        paragraphs.append(f"{prefix}{world.get('description')}")

    structure = data.get("structure") or {}
    for key in ("beginning", "conflict", "rising_action", "climax"):
        val = structure.get(key)
        if val:
            paragraphs.append(val)

    for ch in data.get("chapters", []):
        ch_title = (ch.get("title") or "").strip()
        ch_summary = (ch.get("summary") or "").strip()
        if ch_summary:
            paragraphs.append(f"{ch_title + ': ' if ch_title else ''}{ch_summary}")

    dialogue = data.get("dialogue") or []
    if dialogue:
        lines = [
            f'{d.get("character", "").strip()}: "{d.get("line", "").strip()}"'
            for d in dialogue if d.get("line")
        ]
        if lines:
            paragraphs.append("\n".join(lines))

    plot_twist = data.get("plot_twist")
    if plot_twist:
        paragraphs.append(f"Just when it seemed settled, everything changed: {plot_twist}")

    ending = data.get("ending") or structure.get("ending")
    if ending:
        paragraphs.append(ending)

    return "\n\n".join(p for p in paragraphs if p)


def _offline_regenerate_field(field, story):
    if field == "twist":
        return random.choice(_TWISTS)
    if field == "ending":
        return random.choice(_ENDINGS)
    if field == "continue":
        n = story.chapters.count() + 1
        return {"title": f"Chapter {n}", "summary": f"The story pushes forward as new consequences of the twist unfold."}
    return random.choice(_TWISTS)
