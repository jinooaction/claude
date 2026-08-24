# Quickstart: Independent Commodity Term Structure

```bash
uv run python scripts/commodity_term_structure_factory_probe.py \
  --prior-factory-json /tmp/fx_carry_factory.json \
  --calibration-json /tmp/edge_gate_calibration.json \
  --output /tmp/commodity_term_structure_factory.json \
  --markdown-output /tmp/commodity_term_structure_factory.md
```

The command is no-order. A nonzero exit means source or contract failure; a successful exit may still report
`NO_FACTORY_EDGE`.

