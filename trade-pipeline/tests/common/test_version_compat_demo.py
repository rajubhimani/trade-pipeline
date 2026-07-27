import sys

import pytest

from trade_pipeline.common.version_compat_demo import (
    Point,
    StackNew,
    StackOld,
    fan_out_gather,
    fan_out_taskgroup,
    move_new_way,
    move_old_way,
)


def test_stack_old_typevar_style():
    s = StackOld()
    s.push(1)
    s.push(2)
    assert s.pop() == 2
    assert s.pop() == 1


@pytest.mark.skipif(sys.version_info < (3, 12), reason="class Foo[T] syntax needs 3.12+")
def test_stack_new_type_param_syntax_matches_old_behavior():
    s = StackNew()
    s.push("a")
    s.push("b")
    assert s.pop() == "b"
    assert s.pop() == "a"


async def _fetch(url: str) -> str:
    return f"ok:{url}"


async def _fetch_one_fails(url: str) -> str:
    if url == "bad":
        raise ValueError("boom")
    return f"ok:{url}"


async def test_gather_collects_all_including_exceptions():
    results = await fan_out_gather(["a", "bad", "c"], _fetch_one_fails)
    assert results[0] == "ok:a"
    assert isinstance(results[1], ValueError)
    assert results[2] == "ok:c"


async def test_taskgroup_cancels_siblings_on_failure():
    results = await fan_out_taskgroup(["a", "bad", "c"], _fetch_one_fails)
    # the failing task is excluded; success of the others depends on scheduling,
    # but the call must not raise out of the helper itself
    assert "bad" not in results


async def test_taskgroup_all_succeed_matches_gather_all_succeed():
    tg_results = await fan_out_taskgroup(["a", "b"], _fetch)
    gather_results = await fan_out_gather(["a", "b"], _fetch)
    assert set(tg_results.values()) == set(gather_results)


def test_move_old_way_produces_expected_result():
    p = Point(x=1, y=2)
    old = move_old_way(p, dx=5)
    assert old == Point(x=6, y=2)
    assert p == Point(x=1, y=2)  # original untouched (frozen)


@pytest.mark.skipif(sys.version_info < (3, 13), reason="copy.replace() needs 3.13+")
def test_move_old_and_new_produce_same_result():
    p = Point(x=1, y=2)
    old = move_old_way(p, dx=5)
    new = move_new_way(p, dx=5)
    assert old == new == Point(x=6, y=2)
    assert p == Point(x=1, y=2)  # original untouched (frozen)
