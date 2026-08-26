# Specification Quality Checklist: Calibrated Research Entry

**Purpose**: Validate the specification before implementation  
**Created**: 2026-08-26  
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] User value and root cause are stated without hiding behind implementation terms
- [x] Request, non-goals, risks, and completion criteria are separated
- [x] Current option evidence cannot benefit from outcome-fitted thresholds
- [x] Every numeric threshold has a preregistered rationale

## Requirement Completeness

- [x] Requirements are testable and unambiguous
- [x] Success criteria include type-I and type-II calibration
- [x] Raw candidates and research families are explicitly distinguished
- [x] Producer claims are independently recomputed
- [x] Legacy migration behavior is explicit
- [x] Missing and malformed evidence fails closed
- [x] Current production evidence has a required regression result

## Safety and Operations

- [x] Change is classified as grade 4
- [x] 10% research cap and every 20%+ gate remain unchanged
- [x] Orders, capital movement, and sentinel mutation are excluded
- [x] Rollback is documented
- [x] Constitution and K-meta impact are identified

## Notes

- Frozen before implementation on 2026-08-26.
- Primary research references and exact simulation assumptions are in `research.md`.
