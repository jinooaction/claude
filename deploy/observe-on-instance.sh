#!/usr/bin/env bash
# Fixed observation commands for the auto-invest production instance.
#
# This helper is called by the forced-command SSH gateway. It intentionally
# exposes only read-only broker/account probes and paper-only forward track
# operations needed by GitHub Actions. It does not arm live trading, place live
# orders, change capital, or edit live configuration.

set -euo pipefail

REPO="${REPO:-/opt/auto-invest}"
APP_USER="${APP_USER:-auto-invest}"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_repo() {
    [[ -d "${REPO}/.git" ]] || die "missing repo: ${REPO}"
    cd "${REPO}"
}

run_cli() {
    sudo -u "${APP_USER}" -H /usr/local/bin/uv run auto-invest "$@"
}

validate_capital() {
    local capital="${1:-}"
    [[ "${capital}" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "invalid capital"
}

track_config() {
    local track="${1:-}"
    case "${track}" in
        trend)
            TRACK_PORTFOLIO="deploy/canary-portfolio.toml"
            TRACK_DB="data/forward_trend.db"
            TRACK_HALT="data/forward_trend.halt.flag"
            TRACK_CONSTRUCT_TOP_N="50"
            ;;
        notrend)
            TRACK_PORTFOLIO="deploy/canary-portfolio-notrend.toml"
            TRACK_DB="data/forward_notrend.db"
            TRACK_HALT="data/forward_notrend.halt.flag"
            TRACK_CONSTRUCT_TOP_N="50"
            ;;
        rmbeta)
            TRACK_PORTFOLIO="deploy/risk-managed-beta-portfolio.toml"
            TRACK_DB="data/forward_rmbeta.db"
            TRACK_HALT="data/forward_rmbeta.halt.flag"
            TRACK_CONSTRUCT_TOP_N=""
            ;;
        multiasset)
            TRACK_PORTFOLIO="deploy/multi-asset-trend-portfolio.toml"
            TRACK_DB="data/forward_multiasset.db"
            TRACK_HALT="data/forward_multiasset.halt.flag"
            TRACK_CONSTRUCT_TOP_N=""
            ;;
        global)
            TRACK_PORTFOLIO="deploy/global-trend-portfolio.toml"
            TRACK_DB="data/forward_global.db"
            TRACK_HALT="data/forward_global.halt.flag"
            TRACK_CONSTRUCT_TOP_N=""
            ;;
        globalfixed)
            TRACK_PORTFOLIO="deploy/global-trend-fixed-portfolio.toml"
            TRACK_DB="data/forward_globalfixed.db"
            TRACK_HALT="data/forward_globalfixed.halt.flag"
            TRACK_CONSTRUCT_TOP_N=""
            ;;
        wide)
            TRACK_PORTFOLIO="deploy/global-trend-wide-portfolio.toml"
            TRACK_DB="data/forward_wide.db"
            TRACK_HALT="data/forward_wide.halt.flag"
            TRACK_CONSTRUCT_TOP_N=""
            ;;
        *)
            die "unknown track: ${track}"
            ;;
    esac
}

candidate_history_config() {
    local dataset="${1:-}"
    case "${dataset}" in
        micro-gtaa)
            CANDIDATE_HISTORY_PORTFOLIO="deploy/micro-gtaa-live-portfolio.toml"
            CANDIDATE_HISTORY_DB="data/auto_invest.db"
            ;;
        global-trend-wide)
            CANDIDATE_HISTORY_PORTFOLIO="deploy/global-trend-wide-portfolio.toml"
            CANDIDATE_HISTORY_DB="data/forward_wide.db"
            ;;
        global-trend-fixed)
            CANDIDATE_HISTORY_PORTFOLIO="deploy/global-trend-fixed-portfolio.toml"
            CANDIDATE_HISTORY_DB="data/forward_globalfixed.db"
            ;;
        multi-asset-trend)
            CANDIDATE_HISTORY_PORTFOLIO="deploy/multi-asset-trend-portfolio.toml"
            CANDIDATE_HISTORY_DB="data/forward_multiasset.db"
            ;;
        *)
            die "candidate-history supports only micro-gtaa, global-trend-wide, global-trend-fixed, or multi-asset-trend"
            ;;
    esac
}

ensure_paper_track_storage() {
    local path
    [[ ! -L data ]] || die "unsafe data directory symlink"
    install -d -m 0750 -o "${APP_USER}" -g "${APP_USER}" data
    for path in "${TRACK_DB}" "${TRACK_DB}-wal" "${TRACK_DB}-shm" "${TRACK_HALT}"; do
        [[ -e "${path}" ]] || continue
        case "${path}" in
            data/forward_*.db|data/forward_*.db-wal|data/forward_*.db-shm|data/forward_*.halt.flag)
                ;;
            *)
                die "unsafe paper storage path: ${path}"
                ;;
        esac
        [[ ! -L "${path}" && -f "${path}" ]] || die "unsafe paper storage file type: ${path}"
        chown "${APP_USER}:${APP_USER}" "${path}"
        chmod u+rw,go-rwx "${path}"
    done
}

paper_track_run() {
    local track="${1:-}"
    local capital="${2:-}"
    validate_capital "${capital}"
    track_config "${track}"
    require_repo
    ensure_paper_track_storage

    run_cli backfill-bars \
        --portfolio "${TRACK_PORTFOLIO}" \
        --max-symbols 120 \
        --min-bars 1000 \
        --order deepen \
        --db "${TRACK_DB}" \
        --env-file .env \
        --json

    local rebalance_args=(
        rebalance-once
        --portfolio "${TRACK_PORTFOLIO}"
        --mode paper
        --capital "${capital}"
        --halt-path "${TRACK_HALT}"
        --db "${TRACK_DB}"
        --env-file .env
        --json
    )
    if [[ -n "${TRACK_CONSTRUCT_TOP_N}" ]]; then
        rebalance_args+=(--construct-universe-top-n "${TRACK_CONSTRUCT_TOP_N}")
    fi
    run_cli "${rebalance_args[@]}"

    run_cli nav-snapshot \
        --mode paper \
        --capital "${capital}" \
        --db "${TRACK_DB}" \
        --env-file .env \
        --snapshot \
        --format json
}

paper_track_verdict() {
    local track="${1:-}"
    track_config "${track}"
    require_repo
    run_cli forward-verdict \
        --mode paper \
        --portfolio "${TRACK_PORTFOLIO}" \
        --db "${TRACK_DB}" \
        --format json
}

halt_status() {
    require_repo
    local f
    for f in \
        data/halt.flag \
        data/forward_trend.halt.flag \
        data/forward_notrend.halt.flag \
        data/forward_rmbeta.halt.flag \
        data/forward_multiasset.halt.flag \
        data/forward_global.halt.flag \
        data/forward_globalfixed.halt.flag \
        data/forward_wide.halt.flag
    do
        echo "-- ${f}"
        cat "${f}" 2>/dev/null || echo "(none)"
    done
}

signal_ic_trend() {
    require_repo
    set +e
    echo "--- H=21 ---"
    run_cli signal-ic \
        --portfolio deploy/canary-portfolio.toml \
        --db data/forward_trend.db \
        --forward-horizon 21 2>/dev/null
    echo "--- H=63 ---"
    run_cli signal-ic \
        --portfolio deploy/canary-portfolio.toml \
        --db data/forward_trend.db \
        --forward-horizon 63 2>/dev/null
    exit 0
}

ladder_forward_verdict() {
    require_repo
    run_cli forward-verdict \
        --mode paper \
        --portfolio deploy/global-trend-fixed-portfolio.toml \
        --db data/forward_globalfixed.db \
        --format json
}

ladder_anchored_verdict() {
    require_repo
    local wrk="/tmp/autoarm_anchored_global"
    rm -rf "${wrk}"
    install -d -m 0750 -o "${APP_USER}" -g "${APP_USER}" "${wrk}"

    run_cli bars-export \
        --portfolio deploy/global-trend-fixed-portfolio.toml \
        --db data/forward_globalfixed.db \
        --out-dir "${wrk}/bars" \
        --json \
        > "${wrk}/bars-export.json"
    run_cli ingest-history \
        --from-dir "${wrk}/bars" \
        --out-dir "${wrk}/hist" \
        > "${wrk}/ingest.log"
    run_cli forward-verdict-anchored \
        --portfolio deploy/global-trend-fixed-portfolio.toml \
        --db data/forward_globalfixed.db \
        --history-root "${wrk}/hist" \
        --trailing-years 5 \
        --mode paper \
        --min-forward-obs 5 \
        --format json
}

exploration_canary() {
    require_repo
    run_cli canary-portfolio \
        --portfolio deploy/global-trend-fixed-portfolio.toml \
        --bars-db data/auto_invest.db \
        --bands-toml config/canary_bands_reassign.toml \
        --db data/canary_exploration.db \
        --halt-path data/canary_exploration.halt.flag \
        --format json
}

account_nav() {
    require_repo
    run_cli account-nav \
        --env-file .env \
        --db data/auto_invest.db \
        --json
}

live_growth() {
    local since="${1:-}"
    require_repo
    local args=(
        growth
        --mode live
        --db data/auto_invest.db
        --format json
    )
    if [[ -n "${since}" ]]; then
        [[ "${since}" =~ ^[0-9T:Z+_.-]+$ ]] || die "invalid since"
        args+=(--since "${since}")
    fi
    run_cli "${args[@]}"
}

live_canary_backfill() {
    require_repo
    run_cli backfill-bars \
        --portfolio deploy/canary-live-portfolio.toml \
        --min-bars 1000 \
        --db data/auto_invest.db \
        --env-file .env \
        --json
}

live_canary_preview() {
    local capital="${1:-}"
    validate_capital "${capital}"
    require_repo
    run_cli rebalance-once \
        --portfolio deploy/canary-live-portfolio.toml \
        --dry-run \
        --account-wide \
        --capital "${capital}" \
        --db data/auto_invest.db \
        --env-file .env \
        --json
}

live_canary_measure() {
    local capital="${1:-}"
    validate_capital "${capital}"
    require_repo
    run_cli nav-snapshot \
        --mode live \
        --capital "${capital}" \
        --db data/auto_invest.db \
        --env-file .env \
        --snapshot \
        --format json
    run_cli forward-verdict \
        --mode live \
        --portfolio deploy/canary-live-portfolio.toml \
        --db data/auto_invest.db \
        --format json
}

promote_readiness() {
    require_repo
    run_cli promote-check \
        --db data/auto_invest.db \
        --rules deploy/canary-live-rules.toml \
        --capital 12000 \
        --format json
}

refresh_regime_timeline() {
    local timeline="${1:-}"
    [[ -n "${timeline}" ]] || die "missing timeline path"
    require_repo

    if ! sudo -u "${APP_USER}" git -C "${REPO}" fetch --depth 1 origin \
        automation/public-data:refs/remotes/origin/automation/public-data --quiet; then
        echo "WARN: public-data sidecar fetch failed; using existing origin/automation/public-data" >&2
    fi

    local tmp_file
    tmp_file="$(mktemp)"
    if ! sudo -u "${APP_USER}" git -C "${REPO}" show \
        origin/automation/public-data:regime_timeline.csv > "${tmp_file}"; then
        rm -f "${tmp_file}"
        die "missing public-data regime_timeline.csv"
    fi
    [[ -s "${tmp_file}" ]] || {
        rm -f "${tmp_file}"
        die "empty public-data regime_timeline.csv"
    }
    install -m 0644 -o "${APP_USER}" -g "${APP_USER}" "${tmp_file}" "${timeline}"
    rm -f "${tmp_file}"
}

regime_stratify_track() {
    local track="${1:-}"
    case "${track}" in
        global|wide)
            ;;
        *)
            die "regime-stratify supports only global or wide"
            ;;
    esac

    track_config "${track}"
    require_repo

    local wrk="/tmp/stratify_${track}"
    local timeline="/tmp/regime_timeline.csv"
    local from_date
    local to_date
    from_date="$(date -u -d '3 years ago' +%Y-%m-%d)"
    to_date="$(date -u +%Y-%m-%d)"

    rm -rf "${wrk}"
    install -d -m 0750 -o "${APP_USER}" -g "${APP_USER}" "${wrk}"
    refresh_regime_timeline "${timeline}"

    run_cli bars-export \
        --portfolio "${TRACK_PORTFOLIO}" \
        --db "${TRACK_DB}" \
        --out-dir "${wrk}/bars" \
        --json \
        > "${wrk}/bars-export.json"
    run_cli ingest-history \
        --from-dir "${wrk}/bars" \
        --out-dir "${wrk}/hist" \
        > "${wrk}/ingest.log"
    run_cli backtest-portfolio \
        --portfolio "${TRACK_PORTFOLIO}" \
        --from "${from_date}" \
        --to "${to_date}" \
        --history-root "${wrk}/hist" \
        --db "${wrk}/audit.db" \
        --halt-path "${wrk}/halt.flag" \
        --capital 12000 \
        --equity-out "${wrk}/equity.csv" \
        --json
    run_cli regime-stratify \
        --returns-csv "${wrk}/equity.csv" \
        --timeline-csv "${timeline}" \
        --out "${wrk}/stratified.json"
    echo "--- stratified json ---"
    cat "${wrk}/stratified.json"
}

candidate_history_dataset() {
    local dataset="${1:-}"
    candidate_history_config "${dataset}"
    require_repo

    local wrk="/tmp/candidate_history_${dataset}"
    rm -rf "${wrk}"
    install -d -m 0750 -o "${APP_USER}" -g "${APP_USER}" \
        "${wrk}" "${wrk}/bars" "${wrk}/hist"

    echo "candidate history export: ${dataset} (${CANDIDATE_HISTORY_PORTFOLIO} <- ${CANDIDATE_HISTORY_DB})" >&2
    if ! run_cli bars-export \
        --portfolio "${CANDIDATE_HISTORY_PORTFOLIO}" \
        --db "${CANDIDATE_HISTORY_DB}" \
        --out-dir "${wrk}/bars" \
        --json \
        > "${wrk}/bars-export.json" \
        2> "${wrk}/bars-export.err"; then
        echo "candidate history bars-export failed: ${dataset}" >&2
        cat "${wrk}/bars-export.err" >&2 2>/dev/null || true
        return 1
    fi

    if ! run_cli ingest-history \
        --from-dir "${wrk}/bars" \
        --out-dir "${wrk}/hist" \
        > "${wrk}/ingest.log" \
        2>&1; then
        echo "candidate history ingest-history failed: ${dataset}" >&2
        cat "${wrk}/ingest.log" >&2 2>/dev/null || true
        return 1
    fi

    echo "candidate history ready: ${dataset}" >&2
    echo "CANDIDATE_HISTORY_ARCHIVE_BEGIN ${dataset}"
    tar -C "${wrk}" -czf - hist | base64 | tr -d '\n'
    echo
    echo "CANDIDATE_HISTORY_ARCHIVE_END ${dataset}"
}

main() {
    local cmd="${1:-}"
    shift || true
    case "${cmd}" in
        halt-status)
            [[ "$#" -eq 0 ]] || die "halt-status takes no args"
            halt_status
            ;;
        signal-ic)
            [[ "${1:-}" == "trend" && "$#" -eq 1 ]] || die "signal-ic requires track trend"
            signal_ic_trend
            ;;
        paper-track-run)
            [[ "$#" -eq 2 ]] || die "paper-track-run requires track and capital"
            paper_track_run "$1" "$2"
            ;;
        paper-track-verdict)
            [[ "$#" -eq 1 ]] || die "paper-track-verdict requires track"
            paper_track_verdict "$1"
            ;;
        ladder-forward-verdict)
            [[ "$#" -eq 0 ]] || die "ladder-forward-verdict takes no args"
            ladder_forward_verdict
            ;;
        ladder-anchored-verdict)
            [[ "$#" -eq 0 ]] || die "ladder-anchored-verdict takes no args"
            ladder_anchored_verdict
            ;;
        exploration-canary)
            [[ "$#" -eq 0 ]] || die "exploration-canary takes no args"
            exploration_canary
            ;;
        account-nav)
            [[ "$#" -eq 0 ]] || die "account-nav takes no args"
            account_nav
            ;;
        live-growth)
            [[ "$#" -le 1 ]] || die "live-growth takes at most one since arg"
            live_growth "${1:-}"
            ;;
        live-canary-backfill)
            [[ "$#" -eq 0 ]] || die "live-canary-backfill takes no args"
            live_canary_backfill
            ;;
        live-canary-preview)
            [[ "$#" -eq 1 ]] || die "live-canary-preview requires capital"
            live_canary_preview "$1"
            ;;
        live-canary-measure)
            [[ "$#" -eq 1 ]] || die "live-canary-measure requires capital"
            live_canary_measure "$1"
            ;;
        promote-readiness)
            [[ "$#" -eq 0 ]] || die "promote-readiness takes no args"
            promote_readiness
            ;;
        regime-stratify)
            [[ "$#" -eq 1 ]] || die "regime-stratify requires track"
            regime_stratify_track "$1"
            ;;
        candidate-history)
            [[ "$#" -eq 1 ]] || die "candidate-history requires dataset"
            candidate_history_dataset "$1"
            ;;
        *)
            die "unknown observe command: ${cmd:-missing}"
            ;;
    esac
}

main "$@"
