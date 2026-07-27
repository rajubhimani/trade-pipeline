# 1. Arrays + Hashmaps

Foundation of ~60% of problems per the plan. Key idea: trade O(n) space for O(1) average lookup to
turn an O(n²) nested-loop scan into a single O(n) pass — "have I seen this value/complement before?"

```python
def two_sum(nums: list[int], target: int) -> list[int]:
    seen: dict[int, int] = {}  # value -> index
    for i, n in enumerate(nums):
        if (complement := target - n) in seen:
            return [seen[complement], i]
        seen[n] = i
    return []
```

## Problems

| Problem | Difficulty | Date | Hints needed? | What I'd do differently |
|---|---|---|---|---|
| Two Sum | Easy | | | |
| Group Anagrams | Med | | | |
| Top K Frequent Elements | Med (Hashmap + Heap) | | | |

## Notes

(what actually tripped you up, in plain English — fill in after attempting)
