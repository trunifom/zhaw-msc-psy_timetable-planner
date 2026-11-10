"""
ZHAW MSc Psychology - Timetable Planner (Conflict Logic Layer)
Description: Pure, Streamlit-independent conflict detection over validated
`ZHAWModule` objects:
  - find_time_conflicts(): pairwise overlap detection (same date, or same
    weekday if undated).
  - find_critical_first_session_conflicts(): Passerelle-specific narrowing
    to conflicts hitting a course's first/second session.
Imported by src/app.py; covered by tests/test_scheduler.py.

(An earlier standalone Streamlit prototype that used to live below these
functions was removed - it was never imported by anything.)
"""

from datetime import time
from typing import Callable, Iterable

from models import ZHAWModule

# ==========================================
# 0. ACTIVE CONFLICT-DETECTION LOGIC
# (imported by src/app.py - this is the part of the file that is actually used)
# ==========================================


def _weekday_key(module: ZHAWModule) -> str:
    """Return a normalized weekday key (e.g. "montag") for robust comparison."""
    # `module.wochentag` is a `Weekday` enum member; `.value` gives the
    # plain string. The getattr fallback also tolerates being handed a
    # raw string directly (defensive, in case this is ever called with
    # something other than a full ZHAWModule).
    value = getattr(module.wochentag, "value", module.wochentag)
    return str(value).strip().lower()


def _to_minutes(value: time) -> int:
    """Convert a time object to minutes since midnight (e.g. 08:15 -> 495)."""
    return value.hour * 60 + value.minute


def _same_occurrence(left: ZHAWModule, right: ZHAWModule) -> bool:
    """
    Return True when two rows refer to the same schedulable occurrence,
    i.e. they *could* conflict at all before we even look at the times.

    If both rows carry a real `datum`, "same occurrence" means the exact
    same calendar date - a Monday 08:00 lecture on 2026-09-14 does not
    conflict with a different Monday 08:00 lecture on 2026-09-21, even
    though both are "Monday mornings". Only when a date is missing on
    either side do we fall back to comparing weekdays, which is a looser
    check (assumes the module recurs on that weekday every week).
    """
    left_date = getattr(left, "datum", None)
    right_date = getattr(right, "datum", None)
    if left_date is not None and right_date is not None:
        return left_date == right_date
    return _weekday_key(left) == _weekday_key(right)


def _semantic_signature(module: ZHAWModule) -> tuple:
    """
    Stable signature to suppress exact duplicate rows in conflict results.

    Some source exports contain the literal same session twice (e.g. once
    per "SG"/study-program variant). Two rows with an identical signature
    describe the same real-world event, not two different modules that
    happen to clash - so they must never be reported as a "conflict" with
    each other (see the `left_signature == right_signature` skip below).
    """
    return (
        getattr(module, "datum", None),
        _weekday_key(module),
        _to_minutes(module.startzeit),
        _to_minutes(module.endzeit),
        str(getattr(module, "modul_nr", "") or "").strip(),
        str(getattr(module, "kurs_nr", "") or "").strip(),
        str(getattr(module, "modulname", "") or "").strip(),
        str(getattr(module, "raum", "") or "").strip(),
    )


def is_same_course(left: ZHAWModule, right: ZHAWModule) -> bool:
    """
    True when two rows belong to the SAME course (same Kurs-Nr within the
    same Modul-Nr and the same upload origin) - e.g. "Gruppe A" and
    "Gruppe B" of one course running at the same time, or two sessions of
    the same course.

    Such rows are alternatives/parts of ONE course and never count as a
    conflict with each other: a student attends only one group, or - while
    the group is still undecided - the groups are not competing with
    themselves. They can of course still conflict with OTHER courses.

    Deliberately conservative: without a Kurs-Nr nothing can be said, so
    this returns False (the pair is then judged purely by time as before).
    An exam row vs. a non-exam row of the same course is also not treated
    as "same course" - an exam overlapping a regular session is a data
    oddity worth flagging.
    """
    left_kurs = str(getattr(left, "kurs_nr", "") or "").strip()
    right_kurs = str(getattr(right, "kurs_nr", "") or "").strip()
    if not left_kurs or left_kurs != right_kurs:
        return False
    if str(getattr(left, "modul_nr", "") or "").strip() != str(getattr(right, "modul_nr", "") or "").strip():
        return False
    if bool(getattr(left, "ist_zusatzmodul", False)) != bool(getattr(right, "ist_zusatzmodul", False)):
        return False
    return bool(getattr(left, "ist_pruefung", False)) == bool(getattr(right, "ist_pruefung", False))


def find_time_conflicts(modules: Iterable[ZHAWModule]) -> list[tuple[ZHAWModule, ZHAWModule]]:
    """
    Detect overlapping modules (same date, or same weekday if undated).
    Rows of the SAME course (see is_same_course) are never paired.

    This is an O(n^2) pairwise comparison - deliberately simple, since a
    student's selected schedule is at most a few hundred rows, so the
    quadratic cost is negligible and clarity/correctness matters far more
    here than algorithmic cleverness.

    Returns:
        list[tuple[ZHAWModule, ZHAWModule]]: Pairs of conflicting modules,
        each pair reported at most once (see `seen_pairs` below).
    """
    module_list = list(modules or [])
    conflicts: list[tuple[ZHAWModule, ZHAWModule]] = []
    # Tracks (sorted) signature pairs already reported, so that if the same
    # logical clash is reachable via more than one (i, j) index combination
    # it still only ends up once in the result.
    seen_pairs: set[tuple[tuple, tuple]] = set()

    for i, left in enumerate(module_list):
        left_start = _to_minutes(left.startzeit)
        left_end = _to_minutes(left.endzeit)
        left_signature = _semantic_signature(left)

        # Only compare against modules *after* this one in the list - every
        # (left, right) pair is thus considered exactly once, and a module
        # never gets checked against itself.
        for right in module_list[i + 1 :]:
            if not _same_occurrence(left, right):
                continue
            if is_same_course(left, right):
                continue  # groups/sessions of one course never conflict with each other

            right_signature = _semantic_signature(right)
            if left_signature == right_signature:
                continue  # identical row (duplicate data), not a real conflict

            right_start = _to_minutes(right.startzeit)
            right_end = _to_minutes(right.endzeit)

            # Half-open interval overlap test: [a,b) and [c,d) overlap iff
            # a < d and c < b. Using half-open intervals means a module
            # ending exactly when another starts (e.g. 10:00-12:00 and
            # 12:00-14:00) is correctly NOT flagged as a conflict.
            if left_start < right_end and right_start < left_end:
                pair_key = tuple(sorted((left_signature, right_signature)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                conflicts.append((left, right))

    return conflicts


def find_critical_first_session_conflicts(
    modules: Iterable[ZHAWModule],
    family_key: Callable[[ZHAWModule], str],
    protected_sessions: int = 2,
) -> list[dict]:
    """
    Passerelle-specific narrowing of find_time_conflicts(): flag only the
    conflicts a Passerelle student most needs to act on.

    Background: a Passerelle student's schedule combines Master modules
    with Bachelor "Zusatzmodule" (see ZHAWModule.ist_zusatzmodul), and the
    two catalogs collide far more often than two Master modules normally
    would. Not every collision is avoidable - but a collision landing on a
    course's FIRST or SECOND session is much higher-stakes than a later
    one: ZHAW courses conventionally use those early sessions to cover
    assessment requirements ("Leistungsnachweise"), exam format, group
    assignment ("Gruppenbildung"), the course structure ("Ablauf") and the
    reading list - information a student can't easily recover later
    (unlike catching up on regular course content).

    This is deliberately a pure function over a plain `ZHAWModule` list
    (like find_time_conflicts itself), NOT tied to any Streamlit
    session_state - so unlike almost everything else this app's UI layer
    (src/app.py) surfaces, it can be (and is, see tests/test_scheduler.py)
    covered by ordinary pytest unit tests.

    Args:
        modules: the schedule to check (typically a student's current
            selection) - passed through to find_time_conflicts() as-is.
        family_key: groups `modules` into "one course component" for the
            purpose of counting "1st/2nd session" - the caller supplies
            this (src/app.py's `_module_course_family_key`, which prefers
            Kurs-Nr and falls back to a parsed base title) rather than
            this module reimplementing that grouping/variant-parsing
            logic, keeping scheduler.py decoupled from app.py's course-
            title parsing rules.
        protected_sessions: how many of a family's earliest dated,
            non-exam sessions count as "critical" (default 2, matching
            "the first 1-2 sessions" from the feature request - both
            positions are treated as equally critical, no severity
            distinction between 1st and 2nd).

    A family's own exam rows (`ist_pruefung=True`) and undated rows
    (`datum is None`) are excluded before counting "1st"/"2nd" - an exam
    slot doesn't carry the intro information described above, and an
    undated row has no reliable chronological position to assign.

    Returns:
        One dict per flagged conflict pair: `{"left": ZHAWModule, "right":
        ZHAWModule, "left_session_position": int | None,
        "right_session_position": int | None}` - the 1-based position
        within its own family for whichever side(s) are protected (`None`
        for a side that isn't). A pair is only included when AT LEAST ONE
        side is a Zusatzmodul (i.e. not a pure Master-vs-Master conflict -
        that's what the regular conflict analysis already covers) AND AT
        LEAST ONE side is protected.
    """
    module_list = list(modules or [])

    families: dict[str, list[ZHAWModule]] = {}
    for module in module_list:
        if getattr(module, "ist_pruefung", False):
            continue
        if getattr(module, "datum", None) is None:
            continue
        families.setdefault(family_key(module), []).append(module)

    session_position: dict[int, int] = {}
    for items in families.values():
        for position, module in enumerate(sorted(items, key=lambda m: m.datum), start=1):
            if position > protected_sessions:
                break
            session_position[id(module)] = position

    results: list[dict] = []
    for left, right in find_time_conflicts(module_list):
        if not (getattr(left, "ist_zusatzmodul", False) or getattr(right, "ist_zusatzmodul", False)):
            continue  # pure Master-vs-Master - not this feature's concern

        left_position = session_position.get(id(left))
        right_position = session_position.get(id(right))
        if left_position is None and right_position is None:
            continue

        results.append(
            {
                "left": left,
                "right": right,
                "left_session_position": left_position,
                "right_session_position": right_position,
            }
        )

    return results
