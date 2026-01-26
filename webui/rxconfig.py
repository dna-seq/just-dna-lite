import reflex as rx

config = rx.Config(
    app_name="webui",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    # Fomantic UI styling
    stylesheets=[
        "https://cdn.jsdelivr.net/npm/fomantic-ui@2.9.4/dist/semantic.min.css",
    ],
    # jQuery and Fomantic UI JS for interactive components
    head_components=[
        rx.script(src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"),
        rx.script(src="https://cdn.jsdelivr.net/npm/fomantic-ui@2.9.4/dist/semantic.min.js"),
    ],
    # Tailwind is disabled
    tailwind=None,
)
