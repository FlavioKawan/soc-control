URL_NAME_PREFIXES = (
    ("usecase", "usecases"),
    ("clientusecase", "usecases"),
    ("logsource", "logsources"),
    ("clientlogsource", "logsources"),
    ("template", "templates"),
    ("framework", "frameworks"),
)


def active_nav(request):
    """
    Drives the sidebar's "current section" highlight and the Configurações
    submenu auto-expand, from the resolved URL rather than from a value
    every view would otherwise have to remember to set.
    """
    match = getattr(request, "resolver_match", None)
    if not match or not match.url_name:
        return {}

    app_name = match.app_name
    url_name = match.url_name

    if app_name == "clients":
        section = "clients"
    elif app_name == "detections":
        section = "rules"
    elif app_name == "gaps":
        section = "gaps"
    elif app_name == "audit":
        section = "audit"
    elif app_name == "search":
        section = "search"
    elif url_name == "dashboard":
        section = "dashboard"
    elif url_name in {"user_list", "user_create", "user_update", "user_password_reset", "user_delete"}:
        section = "users"
    elif app_name == "catalog":
        section = next((v for k, v in URL_NAME_PREFIXES if url_name.startswith(k)), None)
    elif app_name == "taxonomy":
        section = next((v for k, v in URL_NAME_PREFIXES if url_name.startswith(k)), "config")
    else:
        section = None

    return {"active_nav": section}
