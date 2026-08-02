DEVICES = [
    # Group A — A12 chip, no ProRes
    {"slug": "iphone-xs",          "name": "iPhone XS",          "chip": "A12",      "group": "a", "image": "/static/images/phones/xs.jpg"},
    {"slug": "iphone-xs-max",      "name": "iPhone XS Max",      "chip": "A12",      "group": "a", "image": "/static/images/phones/xs-max.jpg"},
    {"slug": "iphone-xr",          "name": "iPhone XR",          "chip": "A12",      "group": "a", "image": "/static/images/phones/xr.jpg"},

    # Group B — A13
    {"slug": "iphone-11",          "name": "iPhone 11",          "chip": "A13",      "group": "b", "image": "/static/images/phones/11.jpg"},
    {"slug": "iphone-11-pro",      "name": "iPhone 11 Pro",      "chip": "A13",      "group": "b", "image": "/static/images/phones/11-pro.jpg"},
    {"slug": "iphone-11-pro-max",  "name": "iPhone 11 Pro Max",  "chip": "A13",      "group": "b", "image": "/static/images/phones/11-pro-max.jpg"},

    # Group C — A14, Dolby Vision
    {"slug": "iphone-12-mini",     "name": "iPhone 12 mini",     "chip": "A14",      "group": "c", "image": "/static/images/phones/12-mini.jpg"},
    {"slug": "iphone-12",          "name": "iPhone 12",          "chip": "A14",      "group": "c", "image": "/static/images/phones/12.jpg"},
    {"slug": "iphone-12-pro",      "name": "iPhone 12 Pro",      "chip": "A14",      "group": "c", "image": "/static/images/phones/12-pro.jpg"},
    {"slug": "iphone-12-pro-max",  "name": "iPhone 12 Pro Max",  "chip": "A14",      "group": "c", "image": "/static/images/phones/12-pro-max.jpg"},

    # Group D — A15, Cinematic mode
    {"slug": "iphone-13-mini",     "name": "iPhone 13 mini",     "chip": "A15",      "group": "d", "image": "/static/images/phones/13-mini.jpg"},
    {"slug": "iphone-13",          "name": "iPhone 13",          "chip": "A15",      "group": "d", "image": "/static/images/phones/13.jpg"},
    {"slug": "iphone-13-pro",      "name": "iPhone 13 Pro",      "chip": "A15",      "group": "d", "image": "/static/images/phones/13-pro.jpg"},
    {"slug": "iphone-13-pro-max",  "name": "iPhone 13 Pro Max",  "chip": "A15",      "group": "d", "image": "/static/images/phones/13-pro-max.jpg"},

    # Group E — A15/A16
    {"slug": "iphone-14",          "name": "iPhone 14",          "chip": "A15",      "group": "e", "image": "/static/images/phones/14.jpg"},
    {"slug": "iphone-14-plus",     "name": "iPhone 14 Plus",     "chip": "A15",      "group": "e", "image": "/static/images/phones/14-plus.jpg"},
    {"slug": "iphone-14-pro",      "name": "iPhone 14 Pro",      "chip": "A16",      "group": "e", "image": "/static/images/phones/14-pro.jpg"},
    {"slug": "iphone-14-pro-max",  "name": "iPhone 14 Pro Max",  "chip": "A16",      "group": "e", "image": "/static/images/phones/14-pro-max.jpg"},

    # Group F — A16/A17, ProRes Log
    {"slug": "iphone-15",          "name": "iPhone 15",          "chip": "A16",      "group": "f", "image": "/static/images/phones/15.jpg"},
    {"slug": "iphone-15-plus",     "name": "iPhone 15 Plus",     "chip": "A16",      "group": "f", "image": "/static/images/phones/15-plus.jpg"},
    {"slug": "iphone-15-pro",      "name": "iPhone 15 Pro",      "chip": "A17 Pro",  "group": "f", "image": "/static/images/phones/15-pro.jpg"},
    {"slug": "iphone-15-pro-max",  "name": "iPhone 15 Pro Max",  "chip": "A17 Pro",  "group": "f", "image": "/static/images/phones/15-pro-max.jpg"},

    # Group G — A18, Camera Control
    {"slug": "iphone-16",          "name": "iPhone 16",          "chip": "A18",      "group": "g", "image": "/static/images/phones/16.jpg"},
    {"slug": "iphone-16-plus",     "name": "iPhone 16 Plus",     "chip": "A18",      "group": "g", "image": "/static/images/phones/16-plus.jpg"},
    {"slug": "iphone-16-pro",      "name": "iPhone 16 Pro",      "chip": "A18 Pro",  "group": "g", "image": "/static/images/phones/16-pro.jpg"},
    {"slug": "iphone-16-pro-max",  "name": "iPhone 16 Pro Max",  "chip": "A18 Pro",  "group": "g", "image": "/static/images/phones/16-pro-max.jpg"},

    # Group H — A19, latest
    {"slug": "iphone-17",          "name": "iPhone 17",          "chip": "A19",      "group": "h", "image": "/static/images/phones/17.jpg"},
    {"slug": "iphone-17-air",      "name": "iPhone 17 Air",      "chip": "A19",      "group": "h", "image": "/static/images/phones/17-air.jpg"},
    {"slug": "iphone-17-pro",      "name": "iPhone 17 Pro",      "chip": "A19 Pro",  "group": "h", "image": "/static/images/phones/17-pro.jpg"},
    {"slug": "iphone-17-pro-max",  "name": "iPhone 17 Pro Max",  "chip": "A19 Pro",  "group": "h", "image": "/static/images/phones/17-pro-max.jpg"},
]

DEVICE_MAP = {d["slug"]: d for d in DEVICES}


def get_device(slug: str):
    return DEVICE_MAP.get(slug)


def group_template(slug: str) -> str:
    """Return the content template filename for a given device slug."""
    device = DEVICE_MAP.get(slug)
    if not device:
        return None
    return f"content/group-{device['group']}.html"