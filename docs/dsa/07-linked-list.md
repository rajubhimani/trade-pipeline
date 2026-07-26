# 7. Linked List

Key idea: most linked-list problems are really about carefully managing 2-3 pointers at once
(prev/curr/next) without losing a reference mid-rewrite. Floyd's cycle detection (slow/fast pointers)
is the classic "two pointers moving at different speeds" trick extended to a non-array structure.

```python
class ListNode:
    def __init__(self, val: int = 0, next: "ListNode | None" = None) -> None:
        self.val = val
        self.next = next


def reverse_list(head: ListNode | None) -> ListNode | None:
    prev = None
    while head:
        head.next, prev, head = prev, head, head.next
    return prev


def has_cycle(head: ListNode | None) -> bool:
    slow = fast = head
    while fast and fast.next:
        slow, fast = slow.next, fast.next.next
        if slow is fast:
            return True
    return False
```

## Problems

| Problem | Difficulty | Date | Hints needed? | What I'd do differently |
|---|---|---|---|---|
| Reverse Linked List | Easy | | | |
| Merge Two Sorted Lists | Med | | | |
| Linked List Cycle II | Med (Floyd's algorithm) | | | |

## Notes

(what actually tripped you up, in plain English — fill in after attempting)
