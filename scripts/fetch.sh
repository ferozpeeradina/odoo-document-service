#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p vendor
if [ ! -d vendor/sign/.git ]; then git clone --branch 19.0 --single-branch https://github.com/OCA/sign.git vendor/sign; fi
if [ ! -d vendor/dms/.git ]; then git clone --branch 19.0 --single-branch https://github.com/OCA/dms.git vendor/dms; fi
git -C vendor/sign checkout --detach 3b768318bc5eaccb79535337478f49d59d17d0b1
git -C vendor/dms checkout --detach 1a3098d1d6bbce6a38d06d9f361db319e7858fa3
python3 scripts/prepare.py
