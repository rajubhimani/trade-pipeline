# 2. Two Pointers

For sorted-array problems. Key idea: instead of checking every pair (O(n²)), start pointers at both
ends and move the one that can't possibly improve the answer — each move eliminates a whole class of
pairs at once, giving O(n).

```python
def max_area(height: list[int]) -> int:
    left, right = 0, len(height) - 1
    best = 0
    while left < right:
        width = right - left
        best = max(best, width * min(height[left], height[right]))
        # the shorter wall is always the bottleneck — moving the taller one
        # can only shrink width without ever raising the limiting height.
        if height[left] < height[right]:
            left += 1
        else:
            right -= 1
    return best
```

## Problems

| Problem | Difficulty | Date | Hints needed? | What I'd do differently |
|---|---|---|---|---|
| Container With Most Water | Med | | | |
| 3Sum | Med | | | |

## Notes

(what actually tripped you up, in plain English — fill in after attempting)
