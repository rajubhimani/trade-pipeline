# 8. Trees

Key idea: two traversal families cover almost everything — BFS (level by level, via a queue) for
"shortest"/"level"-shaped questions, and DFS (recursive, via the call stack) for "path"/"ancestor"
questions. LCA and diameter are both DFS problems in disguise: each recursive call needs to return
*two* things to its parent (e.g., "found it here?" and "height so far") rather than just one.

```python
from collections import deque


class TreeNode:
    def __init__(self, val: int = 0, left=None, right=None) -> None:
        self.val, self.left, self.right = val, left, right


def level_order(root: TreeNode | None) -> list[list[int]]:
    if root is None:
        return []
    result, queue = [], deque([root])
    while queue:
        level = []
        for _ in range(len(queue)):
            node = queue.popleft()
            level.append(node.val)
            if node.left:
                queue.append(node.left)
            if node.right:
                queue.append(node.right)
        result.append(level)
    return result


def lowest_common_ancestor(root: TreeNode, p: TreeNode, q: TreeNode) -> TreeNode:
    # BST-specific: both values sorted relative to root tells you which
    # subtree (or that root itself) is the split point — no need to search
    # both subtrees like a general (non-BST) tree's LCA would.
    node = root
    while node:
        if p.val < node.val and q.val < node.val:
            node = node.left
        elif p.val > node.val and q.val > node.val:
            node = node.right
        else:
            return node
    raise ValueError("p/q not found in tree")
```

## Problems

| Problem | Difficulty | Date | Hints needed? | What I'd do differently |
|---|---|---|---|---|
| Level Order Traversal | Med (Tree BFS) | | | |
| Lowest Common Ancestor of a BST | Med (Tree DFS) | | | |

## Notes

(what actually tripped you up, in plain English — fill in after attempting)
