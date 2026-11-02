#!/usr/bin/env bash
# Builds the made-up sample record used for the showcase demo.
# Fictional project: a small recipe website. No real people, projects or data.
# Run from the root of a throwaway git repository that already has the ledger at tools/ledger
# and has run:  python3 tools/ledger/ledger.py init --owner "Owner"
set -euo pipefail
L="python3 tools/ledger/ledger.py"

$L add goal "A fast, simple recipe website for home cooks" \
  --quote "I want a recipe site that loads instantly on a phone, even on a bad connection" \
  --basis owner-words --tags recipes,website,phone,fast,speed --created "2026-10-05 10:02" --quiet
$L add rule "No tracking or analytics" \
  --quote "no tracking, no analytics, no cookie banners. Ever." \
  --basis owner-words --tags tracking,tracker,analytics,cookies,privacy --created "2026-10-05 10:05" --quiet
$L add rule "Metric units only" \
  --quote "metric only: grams and millilitres, no cups" \
  --basis owner-words --tags metric,units,grams,cups,ounces,imperial,measurements --created "2026-10-06 09:15" --quiet
$L add rule "Every change ships with a test" \
  --quote "nothing ships without a test" \
  --basis owner-words --tags tests,testing,ship,release --created "2026-10-06 09:20" --quiet
$L add decision "Plain HTML and CSS, no framework" \
  --quote "plain HTML it is, no framework" --source "picked option B of three" \
  --basis owner-picked-rec --tags framework,react,vue,svelte,html,css,javascript --created "2026-10-07 14:40" --quiet
$L add decision "Each recipe is a Markdown file in the repository" \
  --quote "keep each recipe as its own markdown file, no database" \
  --basis owner-words --tags recipes,markdown,files,database,cms,wordpress --created "2026-10-07 14:55" --quiet
$L add decision "Use the system font stack" \
  --basis my-call --tags fonts,typography --created "2026-10-08 11:00" --quiet
$L add question "How big should the photos on recipe cards be?" \
  --owner owner --tags photos,images,size,cards,hero --created "2026-10-09 16:30" --quiet
$L add task "Build the recipe page template" --serves G1 --tags template,recipes,page \
  --status in-progress --created "2026-10-09 16:45" --quiet
$L focus T1 --quote "let's get one recipe page looking right first"
