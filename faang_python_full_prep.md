# FAANG Python Senior — Full 8-Week Prep Plan

Diagnostic score: 10/30 (33%) · 2 hours/day · Python 3.11 → 3.14 coverage · DSA + Project parallel tracks

**Jump to section:** [Scores](#diagnostic-scores) · [2hr daily schedule](#the-2-hour-daily-structure) · [Python 3.11→3.14](#python-311--314--what-changed-when-to-use-what) · [Week 1–2: DSA](#week-12--dsa-foundations) · [Week 3: Internals](#week-3--python-internals-depth) · [Week 4: Async](#week-4--async--concurrency-mastery) · [Week 5: Security](#week-5--web-security-hardening) · [Week 6–7: System design](#week-67--system-design) · [Week 8: Mocks](#week-8--mock-interviews--project-polish) · [Parallel tracks](#parallel-tracks--dsa--project-by-week) · [The project](#the-project--build-this-across-8-weeks)

---

## Diagnostic scores

| Area | Score | Verdict |
|---|---|---|
| Python internals | 2/5 | Surface level |
| Async / concurrency | 2/5 | Gaps in mechanics |
| Web security | 1/5 | Very thin |
| System design | 2/5 | Single-component thinking |
| DSA | 1/5 | Not practiced |
| Data engineering | 3/5 | Practical, shallow theory |

## The 2-hour daily structure

> **Rule** — The split changes by phase. Weeks 1–2 are DSA-heavy. From Week 3 the project gets equal time. The key: DSA and project always target the same concept that week — you see it twice in different contexts and it actually sticks.

| Phase | Block 1 · 45 min | Block 2 · 45 min | Block 3 · 30 min |
|---|---|---|---|
| **Wk 1–2** DSA focus | **DSA — 2 problems** — Attempt without hints for 20 min. Check solution after. Read top community solution. | **Project build** — That day's component (producer, consumer, dedup). Same concept as the DSA pattern. | **Review + notes** — Write the pattern in plain English. What was hard? What would you do differently? |
| **Wk 3–5** Concepts | **Concept deep dive** — GIL / async / security. Read then experiment in REPL. Prove each claim with code. | **Project — apply it** — Add what you learned to the project. JWT this week → auth layer in FastAPI today. | **1 DSA problem** — Keep the muscle warm. Medium difficulty, any pattern. |
| **Wk 6–7** Design | **System design** — Draw a full architecture from scratch. No notes. 5-layer framework every time. | **2 DSA problems** — Resume full DSA — weak patterns only. Trees, graphs, DP. | **Project polish** — README, diagrams, clean up one component per day. |
| **Wk 8** Mocks | **Mock interview** — Alternate: DSA timed mock one day, system design mock next day. Record yourself. | **Review + fix gaps** — Whatever the mock exposed — go fix it. Not new topics. | **Project demo prep** — Practice the 5-min "walk me through your project" answer out loud. |

**Switching rule:** If DSA is frying your brain → switch to project. If project is blocked → do 2 Leetcode problems. Never stay stuck. Friday = always finish something you can see working.

## Python 3.11 → 3.14 — what changed, when to use what

> **Interview reality** — Senior interviews ask "how would you handle this on 3.11 vs 3.12?" or "what version-specific features are you using and why?" You need to know the evolution, not just the latest. Real codebases are pinned — trading systems especially.

### Python 3.11 · Oct 2022

- **TaskGroup (asyncio)** — Structured concurrency — all tasks cancelled if any raises. Cleaner than gather() for scoped concurrent work.
- **Exception groups + except\*** — Handle multiple unrelated exceptions from concurrent tasks in one block. Essential with TaskGroup.
- **Fine-grained error locations** — Tracebacks now point to exact expression, not just the line. Faster debugging in production.
- **tomllib** — Built-in TOML parsing. No more toml third-party dependency for reading pyproject.toml.
- **~25% faster** — CPython adaptive interpreter — specializes bytecode per use pattern.

### Python 3.12 · Oct 2023

- **f-string improvements** — Multi-line f-strings, nested quotes, arbitrary expressions allowed. No more backslash restriction.
- **Type parameter syntax** — `class Stack[T]:` and `def first[T](lst: list[T]) -> T:` — no more TypeVar boilerplate.
- **@override decorator** — Explicit override marking in subclasses. mypy enforces it. Prevents silent drift in inheritance hierarchies.
- **Per-interpreter GIL (PEP 684)** — Each subinterpreter has its own GIL. Foundation for true multi-core Python — not user-facing yet.
- **Improved buffer protocol** — Faster zero-copy data sharing between C extensions.

### Python 3.13 · Oct 2024

- **Free-threaded mode (experimental)** — Run without GIL using `python3.13t`. True thread-level CPU parallelism. Third-party ecosystem not yet ready.
- **New interactive REPL** — Multi-line editing, history, coloured output. Replaces decades-old default.
- **Improved error messages** — NameError suggests similar names, ImportError gives install hints.
- **copy.replace()** — Immutable-style updates on dataclasses, namedtuples, and custom objects without deepcopy.
- **warnings.deprecated()** — Formal deprecation decorator — integrates with type checkers.

### Python 3.14 · Oct 2025

- **Free-threaded officially supported** — No-GIL build is now stable (PEP 779). Still separate binary — not default. Ecosystem catching up.
- **Deferred annotations (PEP 649)** — Annotations evaluated lazily by default. No more `from __future__ import annotations` needed for forward refs.
- **t-strings (PEP 750)** — `t"Hello {name}"` returns a Template object, not a string. Enables safe SQL/HTML templating without injection risk.
- **asyncio introspection CLI** — Inspect running async tasks from the command line — new debugging superpower for async production systems.
- **Subinterpreters in stdlib (PEP 734)** — `concurrent.futures.InterpreterPoolExecutor` — run CPU-bound work in isolated interpreters, true parallelism.
- **compression.zstd** — Zstandard compression built-in — faster than gzip, better ratio. Relevant for data pipeline compression.

### Feature availability matrix — what you can use where

| Feature | 3.11 | 3.12 | 3.13 | 3.14 | Interview relevance |
|---|---|---|---|---|---|
| asyncio.TaskGroup | ✓ | ✓ | ✓ | ✓ | Use over gather() for structured concurrency when 3.11+ |
| except* (exception groups) | ✓ | ✓ | ✓ | ✓ | Required pair for TaskGroup — know both or neither |
| class Stack[T] type params | ✗ | ✓ | ✓ | ✓ | Replaces TypeVar for new codebases on 3.12+ |
| @override decorator | ✗ | ✓ | ✓ | ✓ | Use in any OOP-heavy codebase on 3.12+ |
| Deferred annotations default | ✗ | ✗ | ✗ | ✓ | On 3.11–3.13 still need `from __future__ import annotations` |
| Free-threaded (no GIL) | ✗ | ✗ | Experimental | Stable | Know it exists, know the tradeoffs, don't use in prod yet |
| t-strings | ✗ | ✗ | ✗ | ✓ | 3.14 only — mention as safe templating alternative to f-strings |
| InterpreterPoolExecutor | ✗ | ✗ | ✗ | ✓ | True CPU parallelism alternative to multiprocessing on 3.14 |
| copy.replace() | ✗ | ✗ | ✓ | ✓ | Cleaner immutable updates — mention when discussing dataclasses |
| tomllib | ✓ | ✓ | ✓ | ✓ | Use over third-party toml everywhere |
| asyncio CLI inspector | ✗ | ✗ | ✗ | ✓ | Production debugging — know this exists for 3.14 async systems |
| compression.zstd | ✗ | ✗ | ✗ | ✓ | Data pipeline compression — faster than gzip, stdlib in 3.14 |

### How to answer version questions in interview

- **On concurrency:** "On 3.10 and below I'd use `asyncio.gather(return_exceptions=True)`. On 3.11+ I prefer TaskGroup with except* — it gives structured cancellation semantics. If we're on 3.14 and truly CPU-bound, InterpreterPoolExecutor is worth evaluating over multiprocessing because we get true parallelism without the inter-process serialization overhead."
- **On the GIL:** "The GIL is being phased out. 3.13 had an experimental free-threaded build. 3.14 makes it officially supported but it's still a separate binary — the default build still has the GIL. Third-party C extensions need to opt in, and not all have. For production today I'd still use multiprocessing for CPU-bound work, but I'm tracking the ecosystem readiness."
- **On type annotations:** "On 3.11–3.13 I add `from __future__ import annotations` at the top of every module for forward references and lazy evaluation. On 3.14+ it's the default — I'd remove that import in a 3.14-only codebase. For generic classes I use the new `class Stack[T]` syntax on 3.12+, TypeVar on 3.11."
- **On t-strings (3.14):** "t-strings return a Template object instead of a string. The key use case is safe SQL or HTML templating — the interpolated values are captured as structured data before rendering, so a library can sanitize them. It's a safer alternative to f-strings when user input is involved."

## Week 1–2 — DSA foundations

**Badge:** DSA

> **Why first** — FAANG DSA screens come before Python depth. You failed the streaming median question (said binary tree — answer is two heaps). That ends a phone screen. Fix this before anything else.

### Pattern order — do exactly this sequence

1. **Arrays + Hashmaps** — Two Sum, Group Anagrams, Top K Frequent. Foundation of 60% of problems.
2. **Two Pointers** — Container With Most Water, 3Sum. Sorted array problems.
3. **Sliding Window** — Longest Substring Without Repeating, Longest Repeating Char Replacement.
4. **Binary Search** — not just sorted arrays. Search in Rotated Array, Find Minimum in Rotated Array.
5. **Heaps** — Find Median from Data Stream (your Q6), K Closest Points, Task Scheduler. Know heapq negate trick for max-heap.
6. **Stack / Monotonic Stack** — Valid Parentheses, Daily Temperatures, Car Fleet.
7. **Linked List** — Reverse, Merge Two Sorted, Detect Cycle (Floyd's).
8. **Trees** — BFS level order, DFS inorder/preorder, LCA, Diameter.
9. **Graphs** — Number of Islands, Clone Graph, Course Schedule (topological sort).
10. **DP (intro only)** — Climbing Stairs, Coin Change, Longest Common Subsequence. Pattern recognition, not deep theory.

### Week 1 problems (patterns 1–5)

| Difficulty | Problem | Pattern |
|---|---|---|
| Easy | Two Sum | Hashmap |
| Easy | Valid Anagram | Hashmap |
| Med | Group Anagrams | Hashmap |
| Med | Top K Frequent Elements | Hashmap + Heap |
| Med | Container With Most Water | Two Pointers |
| Med | 3Sum | Two Pointers |
| Med | Longest Substring Without Repeating | Sliding Window |
| Med | Longest Repeating Character Replacement | Sliding Window |
| Med | Find Minimum in Rotated Sorted Array | Binary Search |
| Med | Search in Rotated Sorted Array | Binary Search |
| Med | Find Median from Data Stream | Two Heaps ← your Q6 answer |
| Med | K Closest Points to Origin | Heap |
| Med | Task Scheduler | Heap + Greedy |

### Week 2 problems (patterns 6–10)

| Difficulty | Problem | Pattern |
|---|---|---|
| Easy | Valid Parentheses | Stack |
| Med | Daily Temperatures | Monotonic Stack |
| Easy | Reverse Linked List | Linked List |
| Med | Merge Two Sorted Lists | Linked List |
| Med | Linked List Cycle II | Floyd's algorithm |
| Med | Level Order Traversal | Tree BFS |
| Med | Lowest Common Ancestor BST | Tree DFS |
| Med | Number of Islands | Graph BFS/DFS |
| Med | Course Schedule | Topological Sort |
| Easy | Climbing Stairs | DP |
| Med | Coin Change | DP |

### Two-heap pattern — your Q6 answer in code

```python
import heapq

class MedianFinder:
    def __init__(self):
        self.lo = []   # max-heap (negate values — heapq is min only)
        self.hi = []   # min-heap

    def addNum(self, num: int) -> None:
        heapq.heappush(self.lo, -num)
        # rebalance if max of lo > min of hi
        if self.lo and self.hi and -self.lo[0] > self.hi[0]:
            heapq.heappush(self.hi, -heapq.heappop(self.lo))
        # keep sizes balanced (lo can have 1 extra)
        if len(self.lo) > len(self.hi) + 1:
            heapq.heappush(self.hi, -heapq.heappop(self.lo))
        if len(self.hi) > len(self.lo):
            heapq.heappush(self.lo, -heapq.heappop(self.hi))

    def findMedian(self) -> float:
        if len(self.lo) > len(self.hi):
            return float(-self.lo[0])
        return (-self.lo[0] + self.hi[0]) / 2.0

# Time: O(log n) insert, O(1) median
# Space: O(n)
```

**Resources:** Neetcode.io — do in pattern order · Leetcode (free tier fine) · Neetcode YouTube — watch after attempting

## Week 3 — Python internals depth

**Badge:** Python

### Day by day

**Day 1 — GIL — and the 3.14 free-threaded story**
GIL is a mutex on interpreter state. Exists because CPython reference counting is not thread-safe. Released during I/O and C extensions that call `Py_BEGIN_ALLOW_THREADS`. 3.13 added experimental free-threaded build. 3.14 makes it officially supported — but it's a separate binary, not the default. Third-party extensions need to opt in. For today: write a CPU benchmark with threads vs processes and confirm threads give no speedup (GIL in standard build). Then run the same on a 3.14t free-threaded build if available and compare.

**Day 2 — Memory model + GC**
Reference counting via `ob_refcnt`. `sys.getrefcount()` always returns one extra (the call itself). Cyclic GC handles reference cycles — `gc.collect()` forces it. Small int cache: -5 to 256 are singletons. String interning: short strings without spaces are interned automatically. Use `id()` to prove it. Python 3.13+ improved error messages help debugging these cases — mention this.

**Day 3 — Descriptors + `__slots__`**
Descriptor protocol: `__get__`, `__set__`, `__delete__`. How `@property` works internally — it is a descriptor. How `@classmethod` and `@staticmethod` work — also descriptors. `__slots__` removes `__dict__`, saves memory, prevents dynamic attribute creation. Use in high-instance-count classes. Trade-off: harder to pickle, no `__dict__` introspection. Use `dis.dis()` to compare slot vs dict attribute access bytecode.

**Day 4 — Type system — 3.11 vs 3.12 vs 3.14**
3.11: TypeVar, Generic[T], `from __future__ import annotations` for forward refs. 3.12: `class Stack[T]` syntax — no TypeVar boilerplate. `@override` decorator — enforced by mypy. 3.14: annotations deferred by default — drop the future import. Protocol for structural subtyping. ParamSpec for decorator typing. Know which version supports what — this is a senior-level question.

**Day 5 — Metaclasses + dataclasses**
`type` is the metaclass of all classes. `class Foo:` is sugar for `type('Foo', (bases,), namespace)`. Django ORM uses metaclasses. Prefer `__init_subclass__` for lighter class customization. `@dataclass`: auto `__init__`, `__repr__`, `__eq__`. `frozen=True` for immutability. 3.13: `copy.replace()` works on dataclasses — cleaner than `replace()` from dataclasses module. Know `slots=True` on dataclass for memory optimization.

**Day 6 — Generators vs coroutines**
Generator: `yield`, produces values, driven by `next()`. Coroutine: `async def` + `await`, driven by event loop. They share bytecode machinery. Use `dis.dis()` on both — see `YIELD_VALUE` vs `GET_AWAITABLE` opcodes. Generator expressions for lazy pipelines: `(x*2 for x in range(10**9))` uses O(1) memory. Coroutines for I/O concurrency. Never use threads for I/O when asyncio is available.

### 3.12 type syntax — old vs new

```python
# 3.11 and below — TypeVar boilerplate
from typing import TypeVar, Generic
T = TypeVar('T')

class Stack(Generic[T]):
    def push(self, item: T) -> None: ...
    def pop(self) -> T: ...

# 3.12+ — clean type parameter syntax
class Stack[T]:
    def push(self, item: T) -> None: ...
    def pop(self) -> T: ...

# 3.12 @override
from typing import override

class Base:
    def process(self) -> str: return "base"

class Child(Base):
    @override
    def process(self) -> str: return "child"  # mypy enforces this exists in Base

# 3.14 — deferred annotations default (no import needed)
# On 3.11-3.13 you need this:
from __future__ import annotations

class Node:
    def next(self) -> Node: ...  # Forward ref — works on 3.11 with the import
                                  # Works natively on 3.14 without it
```

### Must-answer questions

- **Q: Why does CPython have a GIL and why is removal hard?** Reference counting is the memory management strategy — it's not thread-safe without a global lock. Removing the GIL requires rethinking the entire object lifecycle and breaks C extensions that assume it. PEP 703 (3.13) / PEP 779 (3.14) use a separate build to avoid breaking the existing ecosystem.
- **Q: What's new in 3.14 that affects concurrent Python?** Free-threaded build is now officially stable. InterpreterPoolExecutor in `concurrent.futures` runs CPU-bound work in isolated subinterpreters — each has its own GIL, so it achieves true parallelism. Different from multiprocessing in that objects can be shared via memoryview without pickling.
- **Q: How does @property actually work?** It's a descriptor. `property()` returns an object with `__get__`, `__set__`, `__delete__`. Python's attribute lookup finds the descriptor on the class and calls `__get__`. This is why you can't set a property without a setter — there's no `__set__` defined.

**Resources:** Fluent Python 2nd ed — chapters 1, 6, 9, 22, 23 · CPython Internals — Anthony Shaw · What's new in 3.12, 3.13, 3.14 — docs.python.org · dis module — use constantly

## Week 4 — Async + concurrency mastery

**Badge:** Python

### gather() vs wait() vs TaskGroup — when each

- **`asyncio.gather(*coros, return_exceptions=True)`** — fire all, collect all results in input order. One exception doesn't kill others when `return_exceptions=True`. Best for: batch API calls where you need all results and want to handle failures individually.
- **`asyncio.wait(tasks, return_when=...)`** — returns (done, pending) sets. `FIRST_COMPLETED` for race pattern. `FIRST_EXCEPTION` for fail-fast. `ALL_COMPLETED` equivalent to gather. Best for: when you need fine-grained control over what to do as each task completes.
- **`asyncio.TaskGroup` (3.11+)** — structured concurrency. All tasks cancelled if any raises. Scope-based — tasks live within the `async with` block. Best for: when all tasks must succeed or all must cancel. Cleaner than gather() for coordinated work. This is the modern preferred pattern on 3.11+.
- **`asyncio.wait_for(coro, timeout=N)`** — hard timeout on a coroutine. Raises TimeoutError. Critical distinction: timeout = max wall time. Backoff = delay between retries. You need both for production retry logic. Missing wait_for was the gap in your Q3 answer.

### Full production pattern — what Q3 wanted

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiohttp

# Per-provider retry — not on the gather itself
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((asyncio.TimeoutError, aiohttp.ClientError))
    # Note: 4xx errors are NOT retried — wrong to retry a bad request
)
async def call_provider(session: aiohttp.ClientSession, url: str) -> dict:
    async with asyncio.wait_for(session.get(url), timeout=2.0) as resp:
        return await resp.json()

async def get_merged_response(session: aiohttp.ClientSession) -> dict:
    urls = [URL_A, URL_B, URL_C]
    tasks = [call_provider(session, url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged = {}
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            # Graceful degradation — partial response, not 500
            merged[url] = {"data": None, "error": type(result).__name__}
        else:
            merged[url] = {"data": result, "error": None}
    return merged

# 3.11+ version — TaskGroup with except*
async def get_merged_taskgroup(session: aiohttp.ClientSession) -> dict:
    results = {}
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = {url: tg.create_task(call_provider(session, url)) for url in [URL_A, URL_B, URL_C]}
    except* asyncio.TimeoutError as eg:
        # Handle timeout group — other tasks already cancelled
        pass
    return {url: t.result() for url, t in tasks.items() if not t.cancelled()}
```

### Circuit breaker — the senior differentiator

```python
import time
from enum import Enum, auto

class State(Enum):
    CLOSED = auto()    # Normal — requests pass through
    OPEN = auto()      # Failing — reject immediately
    HALF_OPEN = auto() # Probing — allow one request through

class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=30):
        self.state = State.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0.0

    async def call(self, coro):
        if self.state == State.OPEN:
            if time.monotonic() - self.last_failure_time > self.recovery_timeout:
                self.state = State.HALF_OPEN
            else:
                raise RuntimeError("Circuit open — service unavailable")
        try:
            result = await coro
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        self.state = State.CLOSED

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = State.OPEN
```

**Resources:** Python Concurrency with asyncio — Matthew Fowler · asyncio docs — TaskGroup, wait_for, Semaphore · tenacity docs

## Week 5 — Web security hardening

**Badge:** Security

> **Your gap — what was missing from your Q4 answer** — You named JWT and rate limiting. Missing: security headers middleware, CORS config, input validation depth, 5 JWT attack vectors, error response sanitisation, audit logging, dependency scanning. One focused week moves you from 1/5 to 4/5.

### JWT attack vectors — memorise all 5

1. **alg:none attack** — Attacker strips signature, sets `"alg":"none"`. If server doesn't pin algorithm, accepts unsigned token. Fix: always pass `algorithms=["RS256"]` explicitly. Never trust the token header for algorithm selection.
2. **Algorithm confusion (RS256 → HS256)** — Server uses RS256. Attacker switches alg to HS256 and signs with the server's public key (which is public). If server uses public key as HS256 secret, it validates. Fix: pin algorithm, never derive it from token.
3. **Weak secret** — HS256 with short/guessable secret is brute-forceable offline. Fix: use RS256 in production, or 256-bit random secret for HS256.
4. **Missing expiry** — Token without `exp` lives forever. Fix: always set `exp`. Reject tokens missing exp claim.
5. **No revocation** — JWTs are stateless — can't invalidate without a blocklist. Fix: short-lived access tokens (15 min) + server-side refresh token store in Redis. Delete refresh token on logout.

### Full security middleware stack

```python
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
import structlog

app = FastAPI()
log = structlog.get_logger()

# 1. CORS — explicit origins only, never wildcard in production
app.add_middleware(CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=True)

# 2. Security headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 3. Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# 4. Audit logging middleware
class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/auth"):
            log.info("auth_event",
                path=request.url.path,
                method=request.method,
                status=response.status_code,
                ip=request.client.host,
                user_agent=request.headers.get("user-agent"))
        return response

# 5. Global error handler — never leak internals
from fastapi.responses import JSONResponse
@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", exc=str(exc), path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

### t-strings (3.14) for safe templating — mention this

```python
# 3.14 t-strings — Template object, not a string
# Enables safe SQL/HTML without injection risk
name = "O'Brien'; DROP TABLE users;--"

# f-string — injection risk
query_f = f"SELECT * FROM users WHERE name = '{name}'"  # DANGEROUS

# t-string (3.14) — Template captures parts before rendering
query_t = t"SELECT * FROM users WHERE name = '{name}'"
# type(query_t) is Template — not a string yet
# A safe library can sanitize interpolated values before rendering
# This is the 3.14 alternative to parameterized queries for templating layers

# In interviews: "On 3.14 I'd use t-strings for any template where user input
# flows into SQL or HTML — the Template object lets the rendering layer
# sanitize values before they become a string."
```

**Resources:** owasp.org/Top10 · portswigger.net/web-security/jwt (free labs) · PyJWT docs 2.x · slowapi · structlog

## Week 6–7 — System design

**Badge:** System design

> **Your gap from Q5** — You named Kafka and stopped. You missed: deduplication layer (the core ask), stream processor, query store, and the 5-second SLA mechanism. You think in tools, not data flows. Fix the thinking pattern first.

### The mandatory 5-layer framework — use on every design

- **Layer 1 — Ingestion:** How does data get in? Kafka, Kinesis, HTTP webhook. Write throughput? Delivery guarantee (at-least-once / exactly-once)?
- **Layer 2 — Processing:** What transforms raw data? Flink, Kafka Streams, Spark, custom Python consumer. Deduplication, enrichment, aggregation happen here.
- **Layer 3 — Storage:** Hot path (ClickHouse, DynamoDB, Redis) for recent queryable data. Cold path (S3 + Parquet) for archival. Choose based on query pattern.
- **Layer 4 — Query/Serve:** How do users read data? REST, GraphQL, gRPC. Caching layer. Pagination. p99 latency SLA.
- **Layer 5 — Monitoring:** Consumer lag, error rate, p99 per layer, DLQ size. Alerts on SLA breach. This separates senior from mid-level answers.

### Full Q5 model answer — trade event pipeline

```text
Brokers (N sources)
  ↓ Kafka — partitioned by broker_id, replication_factor=3, 50+ partitions
  ↓ Flink / Kafka Streams consumer group
        → Redis SET dedup: trade:{broker_id}:{trade_id} EX 300 (5-min TTL window)
           - SETNX returns 0 = duplicate → drop
           - SETNX returns 1 = new → process
        → normalize schema, validate, enrich instrument metadata
        → ClickHouse write (hot — queryable within 5s SLA, columnar, fast ingestion)
        → S3 + Parquet (cold — archival, Athena queries for analytics)
  ↓ FastAPI query service (reads ClickHouse, Redis cache for hot keys)
  ↓ Prometheus metrics:
        - consumer_lag_by_partition (alert if > 10k events)
        - dedup_hit_rate (duplicates / total — track broker health)
        - write_latency_p99 (alert if > 4s — leave 1s buffer on 5s SLA)
        - api_request_latency_p99

Failure modes:
  - Kafka broker down → consumer lag alert → DLQ fills → ops page
  - Redis down → fall back to DB dedup (slower, temporary) → alert
  - ClickHouse slow → query cache serves stale data → alert on staleness
  - Consumer crash → Kafka offset held, restart resumes from last commit (at-least-once)
```

### Systems to practice — one per day

- **URL Shortener:** Base62 encoding, DynamoDB for KV, CDN for redirects, async analytics counter via Kafka. Common trap: don't use DB sequence for IDs.
- **Real-time Leaderboard:** Redis Sorted Set — `ZADD` O(log n), `ZRANK` O(log n). Periodic flush to DB. Sharding for global scale.
- **Rate Limiter as a service:** Token bucket vs sliding window. Redis `INCR` + TTL. Lua script for atomic check-and-increment. Distributed nodes share Redis state.
- **Notification system:** Priority queues per channel (push/email/SMS). Per-user rate limiting. Retry with backoff. Idempotency key per notification. Delivery tracking.
- **Your MDM/EDM system:** The highest-value design to articulate. You built this. Draw it with all 5 layers. This is what gets you the "tell me about a system you designed" question answered perfectly.

**Resources:** github.com/donnemartin/system-design-primer · bytebytego.com · Designing Data-Intensive Apps — Kleppmann

## Week 8 — Mock interviews + project polish

**Badge:** Mocks

### Must-pass bar before applying

- **DSA:** Any Leetcode medium in practiced patterns within 25 min. Time + space complexity stated immediately after.
- **Python internals:** GIL mechanics, event loop, descriptor protocol, memory model — explained in plain English, no notes, under 90 seconds each.
- **Async:** gather vs wait vs TaskGroup — when each. Build retry + timeout + circuit breaker from memory.
- **Version awareness:** Can state what's available on 3.11 vs 3.12 vs 3.14 for any feature discussed. Can give a "how I'd handle this across versions" answer without hesitation.
- **Security:** Full FastAPI security checklist in 2 min. Name all 5 JWT attack vectors and fixes.
- **System design:** Complete 5-layer architecture for any practiced system in 30 min.
- **Project:** 5-min demo answer. Deep-dive on any design decision. Why Redis not DB for dedup. Why RS256 not HS256. Why ClickHouse not Postgres for hot data.

**Resources:** Pramp.com — free peer mocks · Interviewing.io — paid, realistic · Record yourself — watch it back

## Parallel tracks — DSA + project by week

> **Key principle** — DSA and project tackle the same concept each week. Week 1: heaps in DSA → Redis dedup in project (both are about the right data structure for a real-time problem). Week 4: asyncio patterns in DSA practice → circuit breaker in project. See it twice, remember it permanently.

### Week 1–2 · DSA track

- **Mon** — Hashmap pattern — Two Sum, Group Anagrams
- **Tue** — Two pointers — 3Sum, Container Water
- **Wed** — Sliding window — Longest substring problems
- **Thu** — Binary search — Rotated array variants
- **Fri** — Heaps — Streaming median, K closest
- **Sat** — Redo 5 hardest from the week, timed, no notes

### Week 1–2 · Project track

- **Mon — Docker Compose scaffold — Kafka, Redis, Postgres.** Create a `docker-compose.yml` file that spins up 4 containers with one command: Kafka (message queue for trade events), Zookeeper (required by Kafka), Redis (for deduplication), and Postgres (to store processed trades). You don't write any Python yet — just confirm `docker-compose up` starts all 4 services without errors. This is your local dev environment for the whole project.
- **Tue — Kafka producer — fake trade events, 5% dupes.** Write a Python script using `confluent-kafka` that generates fake trade events (fields: broker_id, trade_id, symbol, qty, price, timestamp) and sends them to a Kafka topic called `trades`. Intentionally re-send ~5% of events with the same trade_id to simulate duplicate messages from brokers. This is the data source the rest of the project reads from.
- **Wed — Consumer + Redis dedup (SETNX + TTL).** Write a Python Kafka consumer that reads from the `trades` topic. For each event, run `SETNX trade:{broker_id}:{trade_id} 1 EX 300` in Redis. SETNX means "set if not exists" — if it returns 0 the key already existed so it's a duplicate, drop it. If it returns 1 it's new, process it. The EX 300 auto-deletes the key after 5 minutes so Redis doesn't grow forever.
- **Thu — Postgres writer with manual Kafka offset commit.** After the dedup check passes, write the trade to Postgres using psycopg2 or SQLAlchemy. Only call `consumer.commit()` after the DB write succeeds — this is "manual offset commit". If the write fails, the offset isn't committed so Kafka will re-deliver the event on restart. This prevents data loss. Never auto-commit — you'd lose events on crash.
- **Fri — End-to-end smoke test — all containers running.** Run the full pipeline: `docker-compose up`, then start the producer, then the consumer. Check Postgres has rows. Check Redis has dedup keys. Send the same trade_id twice and confirm only one row lands in Postgres. This is your first proof the whole system works end-to-end.
- **Sat — Debug / clean up / write first README paragraph.** Fix anything that broke during the week. Then write one paragraph in README.md: what the project does and why. Example: "A real-time trade event pipeline that ingests events from multiple brokers via Kafka, deduplicates them using Redis, and stores them in Postgres — queryable via a FastAPI endpoint." This forces you to articulate the project clearly, which you'll need to do in interviews.

### Week 3 · Internals track

- **Mon–Tue** — GIL + 3.14 free-threaded — benchmark both builds
- **Wed** — Memory model — refcount, cyclic GC, interning
- **Thu** — Type system — 3.11 TypeVar vs 3.12 [T] syntax
- **Fri** — Descriptors, `__slots__`, metaclasses
- **Sat** — Generators vs coroutines — `dis.dis()` both

### Week 3 · Project track

- **Mon–Tue — Add JWT RS256 auth — keypair gen, Depends() guards.** Generate an RSA keypair: `openssl genrsa -out private.pem 2048` and `openssl rsa -in private.pem -pubout -out public.pem`. Write a `POST /auth/login` endpoint that returns a JWT signed with the private key, expiring in 15 minutes. Write a `get_current_user` FastAPI dependency that validates the JWT using the public key. Add `Depends(get_current_user)` to `GET /trades`. RS256 is asymmetric — the private key signs, the public key verifies.
- **Wed — Refresh token — Redis store, httpOnly cookie, rotate.** On login, also generate a random UUID refresh token. Store it in Redis with a 7-day TTL: `SET refresh:{uuid} {user_id} EX 604800`. Send it to the browser as an httpOnly cookie (JS can't read it — protects against XSS). Add `POST /auth/refresh`: reads the cookie, verifies the UUID exists in Redis, deletes it (single-use), stores a new UUID, returns a new access token. On logout: delete the Redis key.
- **Thu — Security headers middleware + CORS config.** Write a Starlette middleware class that adds 5 headers to every response: `X-Content-Type-Options: nosniff` (stops browser guessing file types), `X-Frame-Options: DENY` (prevents clickjacking), `Strict-Transport-Security` (forces HTTPS), `Content-Security-Policy: default-src 'self'` (blocks external scripts). Also configure CORSMiddleware with your frontend origin — never `["*"]`.
- **Fri — FastAPI query endpoint — GET /trades, async SA.** Refactor the Postgres queries to use async SQLAlchemy (`asyncpg` driver). Replace `session.execute()` with `await session.execute()`. This means the database query doesn't block the event loop — FastAPI can handle other requests while waiting for Postgres. Test that the auth guard works: requests without a valid JWT get 401.
- **Sat — Integration test — auth flow end to end.** Write a pytest test that: logs in, gets an access token, calls GET /trades with the token, asserts 200. Then calls GET /trades without a token, asserts 401. Then calls POST /auth/refresh with the cookie, asserts a new token is returned and the old refresh UUID is gone from Redis. This proves the whole auth flow works correctly.

### Week 4 · Async track

- **Mon–Tue** — gather vs wait vs TaskGroup — prove difference
- **Wed** — wait_for timeout — build flaky coroutine + fix it
- **Thu** — Semaphore — 100 concurrent calls, cap to 10
- **Fri** — Full async pattern — gather + retry + timeout
- **Sat** — 3.11 TaskGroup vs gather — write both versions

### Week 4 · Project track

- **Mon–Tue — Circuit breaker class — 3 states, failure counter.** Write a `CircuitBreaker` class with 3 states: CLOSED (normal, requests go through), OPEN (broken, reject immediately without calling the service), HALF_OPEN (testing — let one request through to check if service recovered). After 3 consecutive failures → OPEN. After 30 seconds in OPEN → HALF_OPEN. Successful probe → CLOSED. Failed probe → back to OPEN. This prevents your API from waiting on a dead enrichment service.
- **Wed — Wire circuit breaker into enrichment calls.** Create one CircuitBreaker instance per enrichment service (not shared). Wrap each `call_enrichment()` with `await circuit_breaker.call(coro)`. When the circuit is OPEN, the call raises immediately without any network request — your endpoint returns partial data (null for that enrichment field) instead of waiting for timeouts. Test it by making the mock service fail 3 times and confirming the 4th call is rejected instantly.
- **Thu — slowapi rate limiting — 100 req/min per IP.** Install `slowapi`. Add `@limiter.limit("100/minute")` to `GET /trades` and `"10/minute"` to auth endpoints (stricter for login to slow brute force). When the limit is exceeded, slowapi returns 429 Too Many Requests automatically. Test with a loop of 15 rapid login requests — confirm the 11th gets a 429.
- **Fri — Prometheus metrics endpoint — consumer lag, p99.** Add `prometheus-fastapi-instrumentator` to FastAPI. It auto-exposes a `/metrics` endpoint that Prometheus scrapes. Also add custom metrics: a counter for dedup hits vs misses, a histogram for DB write latency. These numbers answer "is the pipeline healthy?" without reading any logs.
- **Sat — Error handler — sanitised external, full internal log.** Add a global FastAPI exception handler using `@app.exception_handler(Exception)`. It should: log the full error internally with `structlog` (include stack trace, request path, user ID), but return only `{"detail": "Internal server error"}` to the client. Never expose DB errors, file paths, or stack traces externally — attackers use these to map your system.

### Week 5 · Security track

- **Mon–Tue** — OWASP Top 10 mapped to FastAPI code
- **Wed** — JWT attack vectors — implement alg:none exploit, fix it
- **Thu** — PortSwigger JWT labs — exploit in lab, understand why
- **Fri–Sat — pip-audit, audit logging, write 2-min security checklist.** Run `pip-audit` — it checks every dependency against the CVE database and flags known vulnerabilities. Fix any critical ones (usually just a version bump). Then write your 2-minute security checklist from memory: JWT pins RS256, exp checked, refresh in Redis, httpOnly cookie, CORS explicit, security headers, rate limiting, error sanitisation, audit log, pip-audit in CI. If you can recite it fluently you know it.

### Week 5 · Project track

- **Mon–Tue — Harden JWT — pin RS256, add exp check, add blocklist.** In your JWT validation: explicitly pass `algorithms=["RS256"]` to `jwt.decode()` — never let the token header decide the algorithm (that's the alg:none attack). Add a check that the `exp` claim exists and is not expired. Add a Redis blocklist: on logout, store the JWT's `jti` (unique token ID) in Redis until its expiry time. On every request, check the token isn't blocklisted.
- **Wed — Global error handler — zero internal detail externally.** Review every exception handler and every Pydantic validation error response. FastAPI by default returns detailed 422 validation errors that reveal your field names and types. Override the 422 handler to return just `{"detail": "Invalid request"}` externally. Internally log the full validation detail. Attackers use verbose error messages to probe your API structure.
- **Thu — Audit log middleware — structured JSON, all auth events.** Write a middleware that logs every request to `/auth/*` as a structured JSON line: `{"event": "login_attempt", "ip": "1.2.3.4", "user_agent": "...", "status": 200, "timestamp": "..."}`. Use `structlog` for this. These logs let you detect brute force attacks (many failed logins from one IP), token theft (same user logging in from 2 countries), and account takeover attempts.
- **Fri–Sat — Run pip-audit, fix vulns, final security review.** Run `pip-audit` on your requirements.txt — it checks every dependency against the CVE database and flags known vulnerabilities. Fix any that are critical or high severity (usually just bump the version). Then do a manual pass: read every route and ask "what happens if I send unexpected input here?" Add to your Makefile so this runs automatically in CI.

### Week 6–7 · System design track

- **Mon — Draw trade pipeline with all 5 layers — from memory.** Without looking at any notes, draw: Kafka (ingestion) → consumer + Redis dedup (processing) → Postgres + S3 (storage) → FastAPI (query) → Prometheus (monitoring). Label every arrow. Name every component. Then compare with your actual project. Any gaps? That's what you still need to build or document.
- **Wed — Design URL shortener — full 5-layer, failure modes.** Classic system design question. Spend 30 min designing it before reading any solution. Requirements: shorten a URL, redirect on access, handle 100M URLs, 10B reads/day. Key decisions: how to generate the short code (base62 of a counter vs random vs hash), where to store (DynamoDB for KV), how to make redirect fast (CDN caching), how to track click analytics (async Kafka, don't slow down the redirect).
- **Fri — Design real-time leaderboard — Redis sorted sets.** Design a leaderboard for a trading game — players earn points in real time. Key insight: Redis Sorted Set is the right data structure. `ZADD leaderboard {score} {player_id}` to update (O(log n)). `ZRANK` to get a player's rank (O(log n)). `ZRANGE leaderboard 0 9 WITHSCORES` to get top 10 (O(log n + k)). Discuss: how do you shard for 100M players? How do you persist scores across Redis restarts?
- **Mon W7 — Design rate limiter — token bucket vs sliding window.** Design a rate limiter as a standalone microservice (not just middleware). Token bucket: allow bursting up to N requests, refill at R per second — good for APIs that allow short bursts. Sliding window counter: divide time into 1-second buckets, count requests in last 60 — smoother. Implementation: Redis `INCR` + `EXPIRE` per key per window. Atomic with a Lua script. How do you share rate limit state across 10 API servers?
- **Wed W7 — Design notification system — priority queues, retry.** Design a system that sends push notifications, emails, and SMS to 10M users. Key decisions: separate queues per channel (email is slow, push is fast — don't mix them), priority queue so critical alerts go first, per-user rate limiting (don't spam), idempotency key per notification (retries don't send twice), delivery status tracking (sent/delivered/failed), dead letter queue for permanently failing deliveries.
- **Fri W7 — Draw your MDM/EDM system — your real production work.** Draw your actual production system using the 5-layer framework. This is your highest-value prep — real production experience beats any theoretical design. Know: why you chose each component, what broke in production and how you fixed it, what you'd change with unlimited time, what the scale numbers are (events/sec, latency, data volume). Interviewers love "I actually built this" more than "I would design it like this".

### Week 6–7 · Project track

- **Mon–Tue — Architecture diagram in README — ASCII/mermaid, 5 layers.** Draw the full system in README.md using either ASCII art or a Mermaid diagram (GitHub renders Mermaid natively). Show all 5 layers: Kafka producer → consumer with Redis dedup → Postgres → FastAPI → client. Label every arrow with what flows across it (trade events, SQL queries, JSON responses). This is the first thing an interviewer looks at — a clear diagram signals engineering maturity.
- **Wed–Thu — Add compression.zstd (3.14) for S3 archival writes.** Add a second write path in the consumer: every 1000 trades, batch them into a JSON file, compress with `compression.zstd` (Python 3.14 stdlib), and write to a local `archive/` folder (simulating S3). This demonstrates the cold storage layer from the system design. Measure: how much smaller is the zstd file vs uncompressed JSON? This gives you real numbers to quote ("zstd achieved 8x compression on trade event data").
- **Fri — Add version compat notes — what changes on 3.11 vs 3.14.** Add a "Python version notes" section to the README. List 3–4 things that would change if the project ran on 3.11 instead of 3.14: use `gather()` instead of `TaskGroup`, add `from __future__ import annotations`, use third-party `zstandard` instead of stdlib `compression.zstd`, use `TypeVar` instead of `[T]` syntax. This shows version awareness — a strong senior signal.
- **Mon–Fri W7 — Resume DSA — 2 mediums/day, weak patterns only.** Go back to Neetcode and pick 2 mediums per day from your weakest patterns — trees, graphs, and DP were the least practiced. Don't redo easy problems you already solved. Time yourself: 25 minutes max per problem. If you can't solve it in 25 min, look at the approach hint only, try again, then read the full solution. The goal is pattern recognition speed under pressure.
- **Sat W7 — Full project run — clean docker-compose up, smoke test.** `docker-compose down -v` (wipe all data), then `docker-compose up` (fresh start). Run the producer for 60 seconds. Check Postgres row count. Check Redis dedup hit rate. Hit GET /trades via curl with a valid JWT. Check /metrics endpoint. Everything should work from a clean state. If anything needs manual steps to work, document them in the README — a project that only works on your machine is not a portfolio piece.

## Week 8 — Mocks, demo prep, no new concepts

_(see [Week 8 — Mock interviews + project polish](#week-8--mock-interviews--project-polish) above)_

## The project — build this across 8 weeks

**Real-time trade event pipeline with secure query API**

Exactly what you were asked in Q5 — but built. Every component maps to a weak area. By Week 8 you can say "I designed and built this end-to-end" and go deep on any decision.

| Component | When | Details |
|---|---|---|
| Component 1 | Week 1 | **Kafka producer** — Simulates N broker feeds. Publishes trade events (broker_id, trade_id, instrument, price, qty, timestamp). Intentionally duplicates ~5% of events. Uses confluent-kafka-python. On 3.14: use compression.zstd for message compression. |
| Component 2 | Week 1 | **Consumer + Redis dedup** — `SETNX trade:{broker_id}:{trade_id} EX 300` — duplicate = drop, new = process. Manual offset commit only after successful write. Covers: Kafka offset semantics, Redis atomic ops, at-least-once delivery. |
| Component 3 | Week 2–3 | **FastAPI query layer** — `GET /trades` with filters. Full security stack: JWT RS256 via `Depends()`, security headers middleware, explicit CORS, slowapi rate limiting, Pydantic input validation, global error handler. Full async with asyncio throughout. |
| Component 4 | Week 4 | **Async enrichment** — Calls 3 mock enrichment services in parallel. gather() + return_exceptions=True + wait_for(timeout=2) per call + tenacity retry on TimeoutError only + circuit breaker after 3 failures. Graceful partial response on failure. |
| Component 5 | Week 4–5 | **Observability + security** — Prometheus /metrics: consumer lag, dedup hit rate, write latency p99, API p99. Audit log middleware. pip-audit in Makefile. JWT blocklist in Redis. Error sanitisation. |
| README | Week 6–7 | **Write it as a design doc** — Problem statement. Architecture diagram (5 layers). Why Kafka not RabbitMQ. Why Redis dedup not DB. Why RS256 not HS256. Why ClickHouse not Postgres for hot data. How to run. What you'd change at 10x scale. Python version notes: what changes if the project runs on 3.11 vs 3.14. |

## Three things to fix first

> **Biggest risk** — DSA. FAANG screens on it before Python depth. Weak DSA ends the process early — regardless of everything else. Start Week 1 here.

> **Thinking pattern to break** — You name the tool before drawing the flow. In system design: clarify → draw data flow → name components → justify each. Never lead with "I'd use Kafka."

> **Quick win** — Security. One focused week on OWASP + PortSwigger JWT labs moves you from 1/5 to 4/5. Much faster to learn than DSA or system design.

---

_FAANG Python Senior Prep · Python 3.11–3.14 · 8 weeks · 2hr/day · April 2026_
