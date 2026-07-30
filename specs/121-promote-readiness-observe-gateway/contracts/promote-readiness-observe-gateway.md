# Contract: Promote Readiness Observe Gateway

## Workflow SSH Command

The promotion readiness workflow must send exactly:

```text
observe promote-readiness
```

It must not send:

```text
cd /opt/auto-invest && /usr/local/bin/uv run auto-invest promote-check ...
bash -s
```

## Gateway Allowlist

The forced-command gateway must accept this exact command:

```text
observe promote-readiness
```

Expected behavior:

- Invoke `/usr/local/sbin/auto-invest-observe promote-readiness`.
- Accept no user-provided arguments.
- Preserve existing refusal behavior for unknown commands and invalid variants.
- Return 126 for refused commands.

## Helper Behavior

The observation helper must run the equivalent of:

```text
auto-invest promote-check --db data/auto_invest.db --rules deploy/canary-live-rules.toml --capital 12000 --format json
```

Expected behavior:

- Exit 0 when the VI readiness gate is ready.
- Exit 1 when the VI readiness gate is not ready.
- Exit non-0/non-1 for setup or execution errors.
- Emit JSON on stdout when the readiness command can evaluate.
- Emit diagnostics on stderr when evaluation fails.

## Safety Contract

This command must never:

- submit live or paper orders,
- arm live trading,
- promote to full live,
- change capital,
- change whitelist or caps,
- change `.env` or secrets,
- mutate audit logs,
- start, stop, or restart system services,
- evaluate caller-provided shell.
