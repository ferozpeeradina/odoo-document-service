#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p vendor
for module in sign dms; do
  case "$module" in
    sign) repo=https://github.com/ferozpeeradina/odoo-community-sign.git; pin=3b768318bc5eaccb79535337478f49d59d17d0b1;;
    dms) repo=https://github.com/ferozpeeradina/odoo-community-dms.git; pin=1a3098d1d6bbce6a38d06d9f361db319e7858fa3;;
  esac
  if [ ! -d "vendor/$module/.git" ]; then git clone -q "$repo" "vendor/$module"; git -C "vendor/$module" checkout -q --detach "$pin"; fi
  # Preserve forks/worktrees with user modifications; never reset or change remote.
  if [ -n "$(git -C "vendor/$module" status --porcelain)" ]; then
    echo "Refusing to alter modified vendor checkout: $module" >&2; exit 1
  fi
  if [ "$(git -C "vendor/$module" rev-parse HEAD)" != "$pin" ]; then
    echo "Vendor checkout differs from required pin: $module; preserve it and supply pinned source separately." >&2; exit 1
  fi
  echo "Verified pinned $module source"
done
