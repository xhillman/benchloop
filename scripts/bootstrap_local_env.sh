#!/usr/bin/env sh
set -eu

copy_if_missing() {
  source_path="$1"
  target_path="$2"

  if [ -f "$target_path" ]; then
    printf 'Keeping existing %s\n' "$target_path"
    return
  fi

  cp "$source_path" "$target_path"
  printf 'Created %s from %s\n' "$target_path" "$source_path"
}

copy_if_missing ".env.example" ".env"
copy_if_missing "apps/api/.env.example" "apps/api/.env"
copy_if_missing "apps/web/.env.example" "apps/web/.env.local"

printf '\nReview the placeholder secrets before using the app runtime.\n'
