#!/usr/bin/env python3
"""Atomic research state, hard budgets, and adaptive gap prioritization."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from io_utils import atomic_write_json, file_lock, utc_now

MODES = {
    'surface': {'max_rounds': 1, 'max_subtopics': 3, 'query_limit': 8, 'fetch_limit': 8, 'investigator_limit': 3, 'verification_retry_limit': 0},
    'moderate': {'max_rounds': 2, 'max_subtopics': 4, 'query_limit': 16, 'fetch_limit': 16, 'investigator_limit': 8, 'verification_retry_limit': 1},
    'exhaustive': {'max_rounds': 3, 'max_subtopics': 5, 'query_limit': 30, 'fetch_limit': 30, 'investigator_limit': 15, 'verification_retry_limit': 2},
    'maximum': {'max_rounds': 4, 'max_subtopics': 5, 'query_limit': 40, 'fetch_limit': 40, 'investigator_limit': 20, 'verification_retry_limit': 3},
}
RESOURCE_KEYS = {
    'query': ('query_calls', 'query_limit'),
    'fetch': ('fetch_calls', 'fetch_limit'),
    'investigator': ('investigator_calls', 'investigator_limit'),
    'verification_retry': ('verification_retries', 'verification_retry_limit'),
}
IMPORTANCE = {'low': 0.3, 'medium': 0.6, 'high': 1.0, 'critical': 1.0}


class BudgetExceeded(RuntimeError):
    pass


def init_state(path: Path, mode: str = 'moderate') -> dict:
    if mode not in MODES:
        raise ValueError(f'unknown mode: {mode}')
    limits = MODES[mode]
    budget = dict(limits)
    budget.update({'query_calls': 0, 'fetch_calls': 0, 'investigator_calls': 0, 'verification_retries': 0})
    state = {
        'version': 1,
        'mode': mode,
        'phase': 'brief',
        'round': 0,
        'budget': budget,
        'completed_subtopics': [],
        'findings_files': [],
        'agent_failures': [],
        'director_decisions': [],
        'created_at': utc_now(),
        'updated_at': utc_now(),
    }
    atomic_write_json(Path(path), state)
    return state


def load_state(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_state(path: Path, state: dict) -> None:
    state['updated_at'] = utc_now()
    atomic_write_json(Path(path), state)


def consume(path: Path, resource: str, amount: int = 1) -> dict:
    if amount < 0:
        raise ValueError('amount must be non-negative')
    if resource not in RESOURCE_KEYS:
        raise ValueError(f'unknown resource: {resource}')
    path = Path(path)
    with file_lock(path):
        state = load_state(path)
        counter, limit = RESOURCE_KEYS[resource]
        current = int(state['budget'][counter])
        maximum = int(state['budget'][limit])
        if current + amount > maximum:
            raise BudgetExceeded(f'{resource} budget exceeded: {current}+{amount}>{maximum}')
        state['budget'][counter] = current + amount
        save_state(path, state)
        return state


def remaining(path: Path) -> dict[str, int]:
    state = load_state(path)
    result: dict[str, int] = {}
    for resource, (counter, limit) in RESOURCE_KEYS.items():
        result[resource] = max(0, int(state['budget'][limit]) - int(state['budget'][counter]))
    return result


def _importance(value: object) -> float:
    if isinstance(value, str):
        return IMPORTANCE.get(value.lower(), 0.0)
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _unit(value: object) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def rank_gaps(gaps: list[dict]) -> list[dict]:
    ranked: list[dict] = []
    for gap in gaps:
        item = dict(gap)
        item['score'] = round(_importance(gap.get('importance')) * _unit(gap.get('uncertainty')) * _unit(gap.get('resolvability')), 6)
        ranked.append(item)
    return sorted(ranked, key=lambda item: item['score'], reverse=True)


def _research_budget_exhausted(state: dict) -> bool:
    budget = state['budget']
    return any(
        int(budget[counter]) >= int(budget[limit])
        for counter, limit in (
            ('query_calls', 'query_limit'),
            ('fetch_calls', 'fetch_limit'),
            ('investigator_calls', 'investigator_limit'),
        )
    )


SATURATION_THRESHOLD = 3  # >=3 high-credibility sources on ALL key aspects → saturated


def subtopic_saturated(state: dict, subtopic: str, high_cred_sources: int, key_aspects_covered: int, key_aspects_total: int) -> bool:
    """Per-subtopic adaptive depth (ecosystem candidate #5).

    A subtopic is saturated when it already has >=3 high-credibility sources
    and ALL its key aspects are covered (no open sub-questions). Saturated
    subtopics are skipped in the next round — global adaptive stop already
    exists (Phase 5, trigger 5); this is the per-subtopic complement: a single
    exhausted subtopic should not force the whole run to continue, and a
    saturated one should not be re-researched while others still need rounds.
    """
    record = state.setdefault('subtopic_saturation', {}).get(subtopic, {})
    if high_cred_sources >= SATURATION_THRESHOLD and key_aspects_covered >= key_aspects_total > 0:
        return True
    return bool(record.get('saturated'))


def mark_saturated(state: dict, subtopic: str) -> dict:
    state.setdefault('subtopic_saturation', {})[subtopic] = {
        'saturated': True,
        'marked_at': utc_now(),
    }
    return state


def decide_next(path: Path, gaps: list[dict], threshold: float = 0.25) -> dict:
    state = load_state(path)
    if _research_budget_exhausted(state):
        return {'decision': 'SYNTHESIZE', 'reason': 'budget_exhausted', 'gap': None}
    ranked = rank_gaps(gaps)
    if not ranked:
        return {'decision': 'SYNTHESIZE', 'reason': 'no_gaps', 'gap': None}
    best = ranked[0]
    if best['score'] < threshold:
        return {'decision': 'SYNTHESIZE', 'reason': 'low_expected_value', 'gap': best}
    return {'decision': 'CONTINUE', 'reason': 'high_value_gap', 'gap': best}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p_init = sub.add_parser('init'); p_init.add_argument('path', type=Path); p_init.add_argument('--mode', choices=MODES, default='moderate')
    p_consume = sub.add_parser('consume'); p_consume.add_argument('path', type=Path); p_consume.add_argument('resource', choices=RESOURCE_KEYS); p_consume.add_argument('--amount', type=int, default=1)
    p_remaining = sub.add_parser('remaining'); p_remaining.add_argument('path', type=Path)
    p_decide = sub.add_parser('decide'); p_decide.add_argument('path', type=Path); p_decide.add_argument('--gaps', required=True, type=Path); p_decide.add_argument('--threshold', type=float, default=0.25)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init': result = init_state(args.path, args.mode)
        elif args.command == 'consume': result = consume(args.path, args.resource, args.amount)
        elif args.command == 'remaining': result = remaining(args.path)
        else: result = decide_next(args.path, json.loads(args.gaps.read_text(encoding='utf-8')), args.threshold)
    except BudgetExceeded as exc:
        print(json.dumps({'error': str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
