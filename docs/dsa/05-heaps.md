# 5. Heaps

Q6 from the diagnostic — streaming median was answered "binary tree" when the actual answer is two
heaps. Key idea: whenever you need "the k largest/smallest so far" or "the running median" from a
*stream* (can't re-sort every time), a heap gives O(log n) insert while keeping the extreme(s)
accessible in O(1) — a sorted structure would cost O(n) per insert to stay sorted.

`heapq` is min-heap only — negate values for a max-heap (the "heapq negate trick" the plan calls out).

```python
import heapq


class MedianFinder:
    """Two heaps: a max-heap for the lower half, a min-heap for the upper
    half, kept balanced in size so the median is always at one/both tops."""

    def __init__(self) -> None:
        self._lo: list[int] = []  # max-heap, stored negated
        self._hi: list[int] = []  # min-heap

    def add_num(self, num: int) -> None:
        heapq.heappush(self._lo, -num)
        heapq.heappush(self._hi, -heapq.heappop(self._lo))
        if len(self._hi) > len(self._lo):
            heapq.heappush(self._lo, -heapq.heappop(self._hi))

    def find_median(self) -> float:
        if len(self._lo) > len(self._hi):
            return -self._lo[0]
        return (-self._lo[0] + self._hi[0]) / 2
```

## Problems

| Problem | Difficulty | Date | Hints needed? | What I'd do differently |
|---|---|---|---|---|
| Find Median from Data Stream | Med (your Q6 answer) | | | |
| K Closest Points to Origin | Med | | | |
| Task Scheduler | Med (Heap + Greedy) | | | |

## Notes

(what actually tripped you up, in plain English — fill in after attempting)
