#!/bin/sh
# Прод-деплой на Fly (з 2026-11-20; раніше Vercel). Дату деплою пишемо в build_info.json:
# з неї sitemap бере чесний <lastmod>, якщо дати файлів у контейнері недостовірні.
set -e
cd "$(dirname "$0")/.."
printf '{"date": "%s"}\n' "$(date -u +%Y-%m-%d)" > build_info.json
fly deploy --ha=false
