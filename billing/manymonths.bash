#!/usr/bin/env bash
set -euo pipefail

# Config
start=202301
end=202509

# Build month list
months=()
for y in {2023..2025}; do
  for m in {01..12}; do
    ym="${y}${m}"
    (( ym < start )) && continue
    if (( ym > end )); then
      break 2
    fi
    months+=("$ym")
  done
done

# Process in batches of 5
batch_size=5
total=${#months[@]}
for ((i=0; i<total; i+=batch_size)); do
  batch=("${months[@]:i:batch_size}")

  printf "%s\n" "${batch[@]}" \
  | parallel --jobs "$batch_size" '
      ym={}
      tmp="durations-${ym}.txt.tmp"
      out="durations-${ym}.txt"
      echo "Running uv run duration.py ${ym}"
      if uv run duration.py "${ym}" > "${tmp}"; then
        mv -f "${tmp}" "${out}"
      else
        rm -f "${tmp}"
        exit 1
      fi
    '
done

# Concatenate in chronological order
: > durations.txt
for ym in "${months[@]}"; do
  cat "durations-${ym}.txt" >> durations.txt
done

echo "Wrote combined output to durations.txt"
