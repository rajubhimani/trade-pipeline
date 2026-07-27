# 3. Sliding Window

Key idea: a "two pointers, same direction" variant for contiguous-subarray/substring problems —
grow the window on the right, shrink from the left only when a constraint is violated, so each
element is added and removed from the window at most once (O(n) instead of re-scanning every
subarray).

```python
def length_of_longest_substring(s: str) -> int:
    last_seen: dict[str, int] = {}
    left = 0
    best = 0
    for right, ch in enumerate(s):
        if ch in last_seen and last_seen[ch] >= left:
            left = last_seen[ch] + 1  # jump left past the earlier duplicate
        last_seen[ch] = right
        best = max(best, right - left + 1)
    return best
```

## Problems

| Problem | Difficulty | Date | Hints needed? | What I'd do differently |
|---|---|---|---|---|
| Longest Substring Without Repeating Characters | Med | | | |
| Longest Repeating Character Replacement | Med | | | |

## Notes

(what actually tripped you up, in plain English — fill in after attempting)
