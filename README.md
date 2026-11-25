# Airport Runway Scheduler — DSA2-P028

Schedules landing and takeoff requests on up to 10 runways. Emergencies go first, then priority, then requested time. Two flights never use the same runway at the same time.

**Run it:** open `index.html` in any browser. No installation needed.
**Tests:** `node tests/scheduler.test.js`

### Python implementation

The browser demo remains JavaScript, but its scheduling core is also available in
dependency-free Python at `python/airport_scheduler.py`. Run its checks with:

```bash
python3 -m unittest tests/test_scheduler.py
```

Use it from Python with `from airport_scheduler import RunwayScheduler` after
adding the `python/` directory to your module path.

---

## 1. Problem → data structure

| Requirement | Data structure | Why |
|---|---|---|
| Always pick the most important waiting flight | **Binary min-heap** (priority queue) | Gets the top flight in O(log n). Sorting again after every insert would cost O(n log n). |
| Change a flight's priority / declare an emergency while it waits | **Indexed heap** = heap + **hash map** `id → index` | Finds the flight in O(1), then moves it up or down in O(log n). |
| Look up a flight by ID, reject duplicate IDs | **Hash map** (`Map`) | O(1) lookup |
| Each runway's bookings, which must never overlap | **Sorted array of intervals** for each runway + **binary search** | Finds the first booking that could clash in O(log k) |
| Re-plan everything after a change | **Bottom-up heapify** | Builds the heap in O(n) instead of n inserts at O(n log n) |

### Priority rule (deterministic)

`compareFlights(a, b)` in [js/scheduler.js](js/scheduler.js) gives a **total order**:

1. Emergency flights first
2. Lower priority number first (1 = highest, 5 = lowest)
3. Earlier requested time first
4. Flight ID alphabetically

Flight IDs are unique, so no two flights ever tie. The same input always gives the same schedule.

---

## 2. Algorithm

```
for each flight, taken from the heap in priority order:      // extractMin  O(log n)
    for each runway that allows this operation:               // at most 10 runways
        slot = earliest free gap >= requested time            // binary search + walk
    choose the runway with the earliest slot (tie → first runway)
    book it (sorted insert)
    delay = slot start − requested time
```

**Finding a free slot on one runway** ([js/runwayTimeline.js](js/runwayTimeline.js)):
1. Go through the runway's open windows in order.
2. Binary-search for the first booking that ends after the candidate start.
3. If that booking overlaps the candidate slot, move the start to the booking's end and check the next booking.
4. If the slot still fits before the window closes, it's the answer. Otherwise try the next window.

**Conflicts.** When a flight's requested slot is taken, it is pushed later. The schedule table explains why: *"Conflict — waited for UK811"* or *"Runway closed until 06:40"*. A flight with no slot left in any open window is marked **unscheduled**.

---

## 3. Complexity (n = flights ≤ 500, R = runways ≤ 10, k = bookings on a runway)

| Operation | Time |
|---|---|
| Add flight (heap insert) | O(log n) |
| Update priority / emergency | O(log n) |
| Remove waiting flight | O(log n) |
| Peek next flight | O(1) |
| Schedule next flight | O(log n + R · (log k + g)), where g = bookings skipped |
| Schedule all | O(n log n + n · R · log n) for normal input |
| Re-plan (heapify) | O(n) to rebuild the heap |
| Space | O(n + R) |

---

## 4. Constraints handled

| Constraint | Where |
|---|---|
| Max 500 flights, 10 runways | `LIMITS` in `scheduler.js` |
| Time intervals must be valid (start < end, inside the day, no overlap) | `validateWindows()` |
| Runway assignments cannot overlap | `findEarliestSlot()`, plus a safety check in `book()` |
| Emergency priority is deterministic | `compareFlights()` |
| Dynamic priority updates with heap visualization | `MinHeap.update()` + `MinHeap.trace` → animated in the UI |

---

## 5. Files

```
index.html              page layout
css/style.css           theme and layout
js/time.js              "HH:MM" <-> minutes
js/minHeap.js           indexed binary min-heap   ← DSA core
js/runwayTimeline.js    one runway's sorted bookings + binary search   ← DSA core
js/scheduler.js         flights map, priority rule, scheduling algorithm   ← DSA core
js/sampleData.js        demo runways and flights
js/heapView.js          draws the heap as a tree and an array
js/timelineView.js      draws the runway Gantt chart
js/app.js               buttons → scheduler → animation → render
tests/scheduler.test.js checks no overlaps, emergency first, determinism, validation
```

The three core files contain **no UI code**, so the logic can be explained (and tested) on its own.

---

## 6. Demo walkthrough (about 3 minutes)

1. **Open the page.** 20 sample requests are already in the heap. Root = `AI2020` (an emergency) even though other flights asked for earlier times.
2. **Click "Schedule next"** a few times. Watch extract-min: the root is removed, the last item moves to the top, and it sifts down. Each flight's slot appears on the timeline.
3. **Change a waiting flight's priority** in the "Waiting" list (P1–P5), or press **EMG**. The node sifts up in the animation. This is the dynamic priority update.
4. **Click "Schedule all"**, then open the **Delayed** filter in the table to see each conflict and the flight it waited for.
5. **Runway 09R** is closed 06:20–06:40 (hatched area). Flights wait for it to reopen.
6. **Runway 27** is departures-only, so it never receives an arrival.
7. Change a runway or an occupancy time → **Re-plan** rebuilds the heap with heapify in O(n) and schedules again.
