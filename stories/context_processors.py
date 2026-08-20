def theme(request):
    """Expose dark-mode / font-size preference to every template."""
    dark_mode = True
    font_size = "md"
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile:
            dark_mode = profile.dark_mode
            font_size = profile.font_size
    return {"dark_mode": dark_mode, "font_size": font_size}
