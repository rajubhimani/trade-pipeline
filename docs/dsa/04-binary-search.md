# 4. Binary Search

Not just "sorted array, find target" — the real skill is spotting when a search space is monotonic
(some condition is false-false-false-true-true-true across it) even when the array itself looks
rotated/unsorted at a glance. Key idea: at each midpoint, figure out which half is *still sorted*,
then check if the target could be in that half.

```python
def search_rotated(nums: list[int], target: int) -> int:
    left, right = 0, len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            return mid
        if nums[left] <= nums[mid]:  # left half is sorted
            if nums[left] <= target < nums[mid]:
                right = mid - 1
            else:
                left = mid + 1
        else:  # right half is sorted
            if nums[mid] < target <= nums[right]:
                left = mid + 1
            else:
                right = mid - 1
    return -1
```

## Problems

| Problem | Difficulty | Date | Hints needed? | What I'd do differently |
|---|---|---|---|---|
| Find Minimum in Rotated Sorted Array | Med | | | |
| Search in Rotated Sorted Array | Med | | | |

## Notes

(what actually tripped you up, in plain English — fill in after attempting)
