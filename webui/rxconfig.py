import reflex as rx

config = rx.Config(
    app_name="webui",
    disable_plugins=["reflex.plugins.sitemap.SitemapPlugin"],
    tailwind={
        "plugins": [
            "@tailwindcss/typography",
            "daisyui",
        ],
        "daisyui": {
            "themes": ["light", "dark", "cupcake"],
        },
    },
)
