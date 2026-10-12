"""Nightly: (re)explain the last day's daily and hourly moves for every stock with Claude.

Production would submit these through the Message Batches API (half price, async). This
implementation uses sequential calls when a key is configured, rules otherwise.
"""
from celery import shared_task

from apps.assistant import llm
from apps.market.bars import bars_for_range
from apps.market.models import Stock

from . import service


@shared_task
def explain_recent_moves():
    for stock in Stock.objects.filter(is_active=True):
        for rng in ("1D", "1M"):
            tf, bars = bars_for_range(stock, rng)
            mvs = service.build_moves(stock, tf, bars)
            service.ensure_explained(stock, mvs)
            if not llm.enabled():
                continue
            # Only significant stock-specific moves are worth an LLM call.
            for mv in mvs:
                if mv.pk and mv.direction != "flat" and abs(mv.residual_pct or 0) >= 1.0:
                    service.save_explanation(mv, service.explain(stock, mv, use_llm=True))
