#!/bin/sh
# Прод-деплой. Vercel віддає файли з фальшивою датою 2018-10-20, тож дату деплою
# пишемо в build_info.json: з неї sitemap бере чесний <lastmod>.
set -e
cd "$(dirname "$0")/.."
printf '{"date": "%s"}\n' "$(date -u +%Y-%m-%d)" > build_info.json
vercel --prod --yes
