#!/usr/bin/env bash
# Collect -> export -> publish, once per hour at minute :17 UTC, until the time budget
# runs out. The workflow then dispatches its own successor, so collection does not
# depend on GitHub's cron scheduler (which can be delayed or skip runs).
set -uo pipefail
BUDGET=${LOOP_SECONDS:-10500}          # ~2h55m per job; keeps code changes picked up within 3h
MINUTE=${COLLECT_MINUTE:-17}
START=$(date +%s); END=$((START + BUDGET)); i=0
publish() {
  ( cd store
    git config user.name "paraca-collector[bot]"
    git config user.email "actions@users.noreply.github.com"
    git checkout -q --orphan "snap-$(date +%s)"
    git add -A
    git commit -qm "data: run ${GITHUB_RUN_ID:-local}.$1 ($(date -u +%FT%TZ))"
    for t in 1 2 3; do git push -q --force origin HEAD:data && return 0; sleep 15; done
    echo "::error::could not push to data branch"; return 1 )
}
while :; do
  i=$((i + 1))
  echo "::group::iteration $i $(date -u +%FT%TZ)"
  python -m paraca.cli collect --db store/paraca.sqlite || echo "::warning::portal collection partial"
  python -m paraca.cli owned   --db store/paraca.sqlite --every-hours 24 || echo "::warning::owned releases failed"
  python -m paraca.cli osm     --db store/paraca.sqlite --every-hours 168 || echo "::warning::osm failed"
  python -m paraca.cli export  --db store/paraca.sqlite --out store
  publish "$i"
  echo "::endgroup::"
  now=$(date +%s)
  next=$(python - "$MINUTE" <<'PY'
import sys, time
m = int(sys.argv[1]); t = time.time()
nxt = (t // 3600) * 3600 + m * 60
while nxt <= t + 60: nxt += 3600
print(int(nxt - t))
PY
)
  # restart the chain on new code: if main moved since this job started, stop now
  if [ -n "${GITHUB_SHA:-}" ] && git fetch -q --depth=1 origin main 2>/dev/null \
     && [ "$(git rev-parse FETCH_HEAD)" != "$GITHUB_SHA" ]; then
    echo "main changed; ending this job so the next one runs the new code"; break
  fi
  # stop if the next iteration would not finish inside the budget (collection takes ~4 min)
  if [ $((now + next + 600)) -gt "$END" ] || [ "${ONE_SHOT:-0}" = 1 ]; then break; fi
  echo "sleeping ${next}s until next :$MINUTE"
  sleep "$next"
done
