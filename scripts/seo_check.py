#!/usr/bin/env python3
"""Post-deploy SEO smoke test.

Every check here exists because the thing it checks was actually broken in
production at some point: /robots.txt 404'd, BASE_URL carried a trailing newline
that invalidated all 96 sitemap URLs, the og:image was never committed, and the
30 guide pages had no inbound link anywhere on the site.

Usage:
    python3 scripts/seo_check.py                       # checks production
    python3 scripts/seo_check.py http://localhost:5001 # checks a local server
"""
import json
import re
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "https://blackmagiccam.fly.dev"
TIMEOUT = 30
UA = "bmc-seo-check/1.0"

failures: list[str] = []
warnings: list[str] = []


def fetch(base, path):
    req = urllib.request.Request(base + path, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.headers  # HTTPMessage: заголовки без урахування регістру (Fly шле їх малими)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.headers


def head_status(base, path):
    req = urllib.request.Request(base + path, headers={"User-Agent": UA}, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def check(ok, label, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def warn(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'WARN'}  {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        warnings.append(label)


def main(base):
    base = base.rstrip("/")
    print(f"\nSEO check — {base}\n")

    print("robots.txt")
    st, robots, _ = fetch(base, "/robots.txt")
    check(st == 200, "/robots.txt returns 200", f"got {st}")
    sitemap_lines = [l for l in robots.splitlines() if l.lower().startswith("sitemap:")]
    check(bool(sitemap_lines), "robots.txt declares a sitemap")
    robots_sitemap_host = ""
    if sitemap_lines:
        url = sitemap_lines[0].split(":", 1)[1].strip()
        check(url.startswith("https://") and url.endswith("/sitemap.xml"),
              "robots.txt sitemap URL is absolute", url)
        robots_sitemap_host = url.split("/")[2] if "//" in url else ""

    print("\nsitemap.xml")
    st, sitemap, _ = fetch(base, "/sitemap.xml")
    check(st == 200, "/sitemap.xml returns 200", f"got {st}")
    locs = re.findall(r"<loc>(.*?)</loc>", sitemap, re.S)
    check(bool(locs), "sitemap has URLs", f"{len(locs)} found")
    check(not any(c in l for l in locs for c in "\n\r\t "),
          "no whitespace inside <loc> (BASE_URL is clean)")
    check(sitemap.count("<lastmod>") == len(locs), "every URL has <lastmod>")
    guide_locs = [l for l in locs if "/guide/" in l]
    check(all("/ru/guide/" not in l and "/ar/guide/" not in l for l in guide_locs),
          "no non-English guide URLs in sitemap")

    hosts = {l.split("/")[2] for l in locs if "//" in l}
    check(len(hosts) == 1, "all sitemap URLs share one host", str(sorted(hosts)))
    sitemap_host = next(iter(hosts)) if len(hosts) == 1 else ""
    if robots_sitemap_host and sitemap_host:
        check(robots_sitemap_host == sitemap_host,
              "robots.txt and sitemap agree on the host",
              f"robots={robots_sitemap_host} sitemap={sitemap_host}")
    # Compare by path, not absolute URL: running this against localhost is normal,
    # and the sitemap must still carry the canonical production host.
    tested_host = base.split("//", 1)[-1]
    warn(sitemap_host == tested_host, "sitemap host matches the host under test",
         f"sitemap={sitemap_host} tested={tested_host} (expected when testing locally)")
    for loc in locs[:3] + guide_locs[:1]:
        path = "/" + loc.split("/", 3)[3] if loc.count("/") >= 3 else "/"
        st = head_status(base, path)
        check(st == 200, f"sitemap URL resolves: {path}", f"got {st}")

    print("\nindexable pages")
    for path in ["/", "/ru/", "/ar/", "/select", "/guide/iphone-15-pro"]:
        st, html, _ = fetch(base, path)
        title = re.search(r"<title>(.*?)</title>", html, re.S)
        title = title.group(1).strip() if title else ""
        desc = re.search(r'<meta name="description" content="(.*?)"', html, re.S)
        robots_meta = re.findall(r'<meta name="robots" content="([^"]+)"', html)
        canonical = re.findall(r'<link rel="canonical" href="([^"]+)"', html)
        h1s = len(re.findall(r"<h1[\s>]", html))
        check(st == 200, f"{path} returns 200", f"got {st}")
        check(not robots_meta, f"{path} is indexable", f"robots={robots_meta}")
        check(len(canonical) == 1, f"{path} has exactly one canonical", str(canonical))
        check(bool(canonical) and canonical[0].startswith(base),
              f"{path} canonical is on this host")
        check(h1s == 1, f"{path} has exactly one <h1>", f"found {h1s}")
        check(bool(title), f"{path} has a title")
        warn(len(title) <= 70, f"{path} title <= 70 chars", f"{len(title)} chars")
        check(bool(desc), f"{path} has a meta description")
        if desc:
            warn(120 <= len(desc.group(1)) <= 165,
                 f"{path} description length sane", f"{len(desc.group(1))} chars")
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                json.loads(block)
            except Exception as e:
                check(False, f"{path} JSON-LD parses", str(e))
                break
        else:
            check(True, f"{path} JSON-LD parses")
        check("aggregateRating" not in html,
              f"{path} has no unbacked aggregateRating")

    print("\ninternal linking")
    st, home, _ = fetch(base, "/")
    guide_links = set(re.findall(r'href="(/guide/[a-z0-9-]+)"', home))
    check(len(guide_links) >= 30, "homepage links every guide page",
          f"{len(guide_links)} distinct guide links")
    st, ru_home, _ = fetch(base, "/ru/")
    ru_links = set(re.findall(r'href="(/ru/guide/[a-z0-9-]+)"', ru_home))
    check(len(ru_links) >= 30, "/ru/ links the localized guide URLs", f"{len(ru_links)} links")

    print("\nnon-English guides are not indexed")
    for path in ["/ru/guide/iphone-15-pro", "/ar/guide/iphone-15-pro"]:
        st, html, _ = fetch(base, path)
        robots_meta = re.findall(r'<meta name="robots" content="([^"]+)"', html)
        check(any("noindex" in r for r in robots_meta), f"{path} is noindex", str(robots_meta))
        check(not re.findall(r'<link rel="canonical"', html), f"{path} has no canonical")

    print("\nsoft-404s")
    st, html, _ = fetch(base, "/guide/iphone-does-not-exist")
    robots_meta = re.findall(r'<meta name="robots" content="([^"]+)"', html)
    check(st == 404, "unknown guide slug returns 404", f"got {st}")
    check(any("noindex" in r for r in robots_meta), "unknown guide slug is noindex", str(robots_meta))
    check(not re.findall(r'<link rel="canonical"', html), "unknown guide slug has no canonical")

    print("\nsocial / assets")
    st, home, _ = fetch(base, "/")
    og_image = re.findall(r'<meta property="og:image" content="([^"]+)"', home)
    check(bool(og_image), "og:image is declared")
    if og_image:
        code = head_status(base, og_image[0].replace(base, ""))
        check(code == 200, "og:image resolves", f"got {code}")
    og_url = re.findall(r'<meta property="og:url" content="([^"]+)"', home)
    check(bool(og_url) and "?" not in og_url[0], "og:url carries no query string", str(og_url))

    print("\ncaching")
    st, _, hdr = fetch(base, "/")
    vary = hdr.get("Vary", "")
    check("accept-language" in vary.lower(), "/ sends Vary: Accept-Language", vary or "(none)")

    print()
    if failures:
        print(f"{len(failures)} FAILED: " + "; ".join(failures))
    if warnings:
        print(f"{len(warnings)} warning(s): " + "; ".join(warnings))
    if not failures:
        print("All checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE))
