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

paper_track_run() {
    local track="${1:-}"
    local capital="${2:-}"
    validate_capital "${capital}"
    track_config "${track}"
    require_repo

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
        --portfolio deploy/global-trend-portfolio.toml \
        --db data/forward_global.db \
        --format json
}

ladder_anchored_verdict() {
    require_repo
    local wrk="/tmp/autoarm_anchored_global"
    rm -rf "${wrk}"
    install -d -m 0750 -o "${APP_USER}" -g "${APP_USER}" "${wrk}"

    run_cli bars-export \
        --portfolio deploy/global-trend-portfolio.toml \
        --db data/forward_global.db \
        --out-dir "${wrk}/bars" \
        --json \
        > "${wrk}/bars-export.json"
    run_cli ingest-history \
        --from-dir "${wrk}/bars" \
        --out-dir "${wrk}/hist" \
        > "${wrk}/ingest.log"
    run_cli forward-verdict-anchored \
        --portfolio deploy/global-trend-portfolio.toml \
        --db data/forward_global.db \
        --history-root "${wrk}/hist" \
        --trailing-years 5 \
        --mode paper \
        --min-forward-obs 5 \
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

promote_readiness() {
    require_repo
    run_cli promote-check \
        --db data/auto_invest.db \
        --rules deploy/canary-live-rules.toml \
        --capital 12000 \
        --format json
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
        account-nav)
            [[ "$#" -eq 0 ]] || die "account-nav takes no args"
            account_nav
            ;;
        live-growth)
            [[ "$#" -le 1 ]] || die "live-growth takes at most one since arg"
            live_growth "${1:-}"
            ;;
        promote-readiness)
            [[ "$#" -eq 0 ]] || die "promote-readiness takes no args"
            promote_readiness
            ;;
        *)
            die "unknown observe command: ${cmd:-missing}"
            ;;
    esac
}

main "$@"
