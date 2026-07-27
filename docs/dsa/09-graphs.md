# 9. Graphs

Key idea: same BFS/DFS traversal skills as trees, generalized to structures with cycles and multiple
paths to the same node — which means a `visited` set is no longer optional (a tree traversal never
needs one; a graph traversal without one can loop forever). Topological sort (Course Schedule) is DFS
plus one extra idea: a cycle in the dependency graph means no valid ordering exists at all.

```python
def num_islands(grid: list[list[str]]) -> int:
    rows, cols = len(grid), len(grid[0])
    visited: set[tuple[int, int]] = set()

    def dfs(r: int, c: int) -> None:
        if (
            r < 0 or r >= rows or c < 0 or c >= cols
            or (r, c) in visited or grid[r][c] == "0"
        ):
            return
        visited.add((r, c))
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            dfs(r + dr, c + dc)

    count = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == "1" and (r, c) not in visited:
                dfs(r, c)
                count += 1
    return count


def can_finish(num_courses: int, prerequisites: list[list[int]]) -> bool:
    """Course Schedule — cycle detection via DFS with a 3-state visited set
    (unvisited / in current path / fully done) to distinguish a real cycle
    from just revisiting a node already fully explored via another path."""
    graph: dict[int, list[int]] = {i: [] for i in range(num_courses)}
    for course, prereq in prerequisites:
        graph[course].append(prereq)

    state = {}  # course -> "visiting" | "done"

    def dfs(course: int) -> bool:
        if state.get(course) == "visiting":
            return False  # back edge — cycle
        if state.get(course) == "done":
            return True
        state[course] = "visiting"
        for prereq in graph[course]:
            if not dfs(prereq):
                return False
        state[course] = "done"
        return True

    return all(dfs(c) for c in range(num_courses))
```

## Problems

| Problem | Difficulty | Date | Hints needed? | What I'd do differently |
|---|---|---|---|---|
| Number of Islands | Med (Graph BFS/DFS) | | | |
| Clone Graph | Med | | | |
| Course Schedule | Med (topological sort) | | | |

## Notes

(what actually tripped you up, in plain English — fill in after attempting)
