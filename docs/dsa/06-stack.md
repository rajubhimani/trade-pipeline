# 6. Stack / Monotonic Stack

Key idea: a stack is the natural fit whenever "the most recent unmatched thing" matters (parentheses,
nested structure). A *monotonic* stack (kept increasing or decreasing) additionally answers "what's
the next element to my right that's bigger/smaller than me" in O(n) total, instead of O(n²) rescanning.

```python
def daily_temperatures(temps: list[int]) -> list[int]:
    answer = [0] * len(temps)
    stack: list[int] = []  # indices, decreasing temperature
    for i, t in enumerate(temps):
        while stack and temps[stack[-1]] < t:
            prev = stack.pop()
            answer[prev] = i - prev
        stack.append(i)
    return answer
```

## Problems

| Problem | Difficulty | Date | Hints needed? | What I'd do differently |
|---|---|---|---|---|
| Valid Parentheses | Easy | | | |
| Daily Temperatures | Med (Monotonic Stack) | | | |
| Car Fleet | Med | | | |

## Notes

(what actually tripped you up, in plain English — fill in after attempting)
