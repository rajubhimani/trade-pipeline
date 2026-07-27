"""Old-way vs new-way, side by side, for every version-gated feature this
project touches. Unlike the rest of the codebase (which just writes the 3.14
way with a one-line fallback comment, per docs/PYTHON_VERSION_NOTES.md), this
module exists purely to teach the contrast — both versions are real, both are
tested (see tests/common/test_version_compat_demo.py), so you can run either
side and see it actually behave the same way.

Read top to bottom; each section is one feature, oldest Python first.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Generic, TypeVar

# ---------------------------------------------------------------------------
# 1. Generics: TypeVar (3.11 and earlier) vs class Foo[T] (3.12+)
# ---------------------------------------------------------------------------

# --- 3.11 way: TypeVar + Generic base class boilerplate ---
_T = TypeVar("_T")


class StackOld(Generic[_T]):
    def __init__(self) -> None:
        self._items: list[_T] = []

    def push(self, item: _T) -> None:
        self._items.append(item)

    def pop(self) -> _T:
        return self._items.pop()


# --- 3.12+ way: type parameter syntax, no TypeVar/Generic needed ---
# NOTE: this class body uses 3.12 syntax and will raise SyntaxError on 3.11.
# It's exec'd conditionally below so this module still imports on 3.11-3.13.
_STACK_NEW_SRC = """
class StackNew[T]:
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()
"""

if sys.version_info >= (3, 12):
    _ns: dict[str, object] = {}
    exec(_STACK_NEW_SRC, _ns)
    StackNew = _ns["StackNew"]
else:
    StackNew = None  # not available before 3.12


# ---------------------------------------------------------------------------
# 2. Structured concurrency: gather() (any version) vs TaskGroup (3.11+)
# ---------------------------------------------------------------------------


async def fan_out_gather(urls: list[str], fetch) -> list[object]:
    """Pre-3.11 idiom. One failing coroutine doesn't cancel the others when
    return_exceptions=True, but there's no structured cancellation — a task
    that's still running when another fails just keeps running unsupervised.
    """
    return await asyncio.gather(*(fetch(u) for u in urls), return_exceptions=True)


async def fan_out_taskgroup(urls: list[str], fetch) -> dict[str, object]:
    """3.11+ idiom. If any task raises, all sibling tasks are cancelled
    automatically (structured concurrency) and the exception(s) surface via
    except* as an ExceptionGroup — no manual bookkeeping needed.
    """
    results: dict[str, object] = {}
    tasks = {}
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = {url: tg.create_task(fetch(url)) for url in urls}
    except* Exception:
        pass  # sibling tasks are already cancelled by TaskGroup at this point
    for url, task in tasks.items():
        if not task.cancelled() and task.exception() is None:
            results[url] = task.result()
    return results


# ---------------------------------------------------------------------------
# 3. Immutable updates: dataclasses.replace() (always available) vs
#    copy.replace() (3.13+, works on more than just dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


def move_old_way(point: Point, dx: int) -> Point:
    import dataclasses

    return dataclasses.replace(point, x=point.x + dx)


def move_new_way(point: Point, dx: int) -> Point:
    import copy  # copy.replace is 3.13+

    return copy.replace(point, x=point.x + dx)


# ---------------------------------------------------------------------------
# 4. Forward references: from __future__ import annotations (3.11-3.13
#    requirement) vs deferred-by-default annotations (3.14, PEP 649)
# ---------------------------------------------------------------------------

# This whole module has `from __future__ import annotations` at the top,
# which is exactly what a 3.11-3.13 codebase needs to write self-referencing
# type hints like the one below without quoting them:


class Node:
    def next(self) -> Node:  # forward reference to the still-being-defined class
        return self

    # 3.14 fallback note: on 3.14, annotations are deferred by default (PEP 649)
    # so the `from __future__ import annotations` line at the top of this file
    # would be unnecessary — it's kept here because this module also needs to
    # run on 3.11-3.13 for the comparison to mean anything.
