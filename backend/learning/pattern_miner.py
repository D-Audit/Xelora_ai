"""
learning/pattern_miner.py
Workflow Learning & Pattern Recognition + Continuous Skill Learning.

Mines a user's ActionLog history for repeated sequences of actions
(e.g. "sort_range -> remove_duplicates -> create_chart" run together
three times) and stores them as WorkflowPattern rows. Once a pattern's
occurrence_count crosses PROMOTION_THRESHOLD, it's flagged as a
candidate to become a reusable named skill in the library - promotion
itself (generating the actual skill function/schema) is a deliberate,
reviewed step, not automatic, since a wrong auto-generated skill is
worse than none.
"""

import json
from collections import Counter
from sqlalchemy.orm import Session

from models import ActionLog, Task, WorkflowPattern

PROMOTION_THRESHOLD = 3   # times a sequence must repeat before flagging
SEQUENCE_WINDOW = 4        # how many consecutive actions define one "pattern"


def _get_user_action_sequences(db: Session, user_id: int):
    """Returns, per task, the ordered list of action_names that ran."""
    task_ids = [t.id for t in db.query(Task).filter_by(user_id=user_id).all()]
    sequences = []
    for task_id in task_ids:
        actions = (
            db.query(ActionLog)
            .filter_by(task_id=task_id, status="success")
            .order_by(ActionLog.created_at)
            .all()
        )
        sequences.append([a.action_name for a in actions])
    return sequences


def mine_patterns(db: Session, user_id: int) -> list:
    """
    Scans this user's task history for repeated sliding-window action
    sequences, upserts WorkflowPattern rows, and returns the list of
    patterns that just crossed the promotion threshold on this run.
    """
    sequences = _get_user_action_sequences(db, user_id)

    window_counts = Counter()
    for seq in sequences:
        for i in range(len(seq) - SEQUENCE_WINDOW + 1):
            window = tuple(seq[i:i + SEQUENCE_WINDOW])
            window_counts[window] += 1

    newly_promotable = []
    for window, count in window_counts.items():
        if count < 2:
            continue  # not worth persisting a one-off

        window_json = json.dumps(list(window))
        existing = (
            db.query(WorkflowPattern)
            .filter_by(user_id=user_id, action_sequence=window_json)
            .first()
        )
        if existing:
            existing.occurrence_count = count
            was_below = existing.occurrence_count < PROMOTION_THRESHOLD
        else:
            existing = WorkflowPattern(
                user_id=user_id, action_sequence=window_json, occurrence_count=count,
            )
            db.add(existing)
            was_below = True

        db.commit()
        db.refresh(existing)

        if count >= PROMOTION_THRESHOLD and not existing.promoted_to_skill:
            newly_promotable.append(existing)

    return newly_promotable


def promotable_patterns(db: Session, user_id: int) -> list:
    """Patterns already over threshold, awaiting a human/dev decision to
    turn them into a real named skill."""
    return (
        db.query(WorkflowPattern)
        .filter(
            WorkflowPattern.user_id == user_id,
            WorkflowPattern.occurrence_count >= PROMOTION_THRESHOLD,
            WorkflowPattern.promoted_to_skill.is_(False),
        )
        .all()
    )
