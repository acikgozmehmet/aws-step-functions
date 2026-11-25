# Step Functions vs EventBridge vs SQS: Study Notes

Source: [Step Functions vs EventBridge vs SQS — When to Use What? (AWS Explained Simply)](https://www.youtube.com/watch?v=26_MS4H7qBA), channel Design Decode Camp, about 10 minutes.

A conceptual, slide-style comparison — no console lab, no code. It walks through what each of the three services is, its key features, where it shines, then gives a one-line rule of thumb and a combined order-processing example using all three together.

This repo already compares Step Functions against alternatives in [tutorial/17 section 11](../tutorial/17_AWS_Step_Functions_Introduction_Study_Notes.md#11-beyond-the-video-the-alternatives-today) ("Lambda durable functions, MWAA, EventBridge, SQS/SNS chains") and lists its disadvantages in [section 9](../tutorial/17_AWS_Step_Functions_Introduction_Study_Notes.md#9-disadvantages-and-when-not-to-use-it). That comparison lumps "SQS/SNS chains" into one row. This video's one genuinely useful addition is giving **SQS its own distinct role** next to Step Functions and EventBridge, rather than treating queues as an afterthought — so these notes focus on that three-way split and correct the places where the video oversimplifies, rather than repeating tutorial/17's table.

What was checked:
- SQS Standard vs FIFO processing/ordering guarantees against [FIFO queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues.html) in the Amazon SQS Developer Guide.
- Step Functions Standard/Express pricing against the [Step Functions pricing page](https://aws.amazon.com/step-functions/pricing/).
- SQS and EventBridge free-tier and per-event pricing against the [SQS pricing page](https://aws.amazon.com/sqs/pricing/) and [EventBridge pricing page](https://aws.amazon.com/eventbridge/pricing/).
- This is a conceptual video with no code or console steps to run, so there's nothing to validate with `TestState` or the CLI.

---

## 1. The video's three-way split

| Service | Video's one-liner | What it's actually for |
|---|---|---|
| **Step Functions** | "The brain" | Orchestration: a central definition coordinates an ordered (or parallel) sequence of steps, with built-in retries and a visual execution history |
| **EventBridge** | "The nervous system sending signals everywhere" | Choreography: a producer fires an event and doesn't know or care who reacts; a rule can fan one event out to several targets |
| **SQS** | "The workhorse" / "the safety net" | Buffering: a durable queue that absorbs bursty traffic between a producer and one or more workers, so the producer doesn't block on the consumer |

The video's closing summary is a reasonable, memorable compression of this: **"Step Functions = orchestration. EventBridge = event routing. SQS = queuing and background processing."**

### The combined example (closing minutes)

The video's own order-processing walkthrough is a good illustration of all three together:
1. Order placed → an `OrderCreated` event → **EventBridge** picks it up.
2. The EventBridge rule **starts a Step Functions execution** that runs validation, payment, inventory, and notification steps in order.
3. For work that doesn't need to block the workflow (e.g. sending a confirmation email), the state machine **pushes a message to SQS** for a background worker to pick up whenever it's free.

This is structurally the same pattern already built in this repo: [tutorial/19](../tutorial/19_AWS_Step_Functions_Trigger_from_SQS_Study_Notes.md) and [eventbridge/02](02_EventBridge_Integrating_With_Step_Functions_Study_Notes.md) cover EventBridge/SQS **starting** a workflow; [tutorial/03](../tutorial/03_AWS_Step_Functions_with_SQS_Study_Notes.md) covers a state machine **sending to** SQS from inside a Task.

---

## 2. Corrections to the video's oversimplifications

| Video says | More precisely |
|---|---|
| "SQS... case safe... if order matters like bank transactions, SQS guarantees exactly-once processing" (06:19-ish, garbled in captions) | This is true only of **FIFO** queues. A **Standard** SQS queue — the default, and what most of the video's other claims describe — gives **at-least-once delivery with best-effort ordering**, not exactly-once or strict order. If order and dedup matter, you must explicitly choose a FIFO queue (and set a message group ID); it isn't automatic. |
| "SQS can handle millions of messages per second" | True in spirit for Standard queues, which AWS describes as having very high, effectively unbounded throughput for unordered processing. It does **not** apply to FIFO queues, which trade throughput for ordering — FIFO throughput is meaningfully lower per queue (higher with batching, higher still with high-throughput mode) and is the wrong queue type to reach for if raw throughput is the goal. |
| "EventBridge... built-in scheduling, no need for a separate scheduler" | There are genuinely two different mechanisms: a plain EventBridge **rule with a schedule expression** (cron/rate, no incoming event) has existed for years, but **EventBridge Scheduler** is a separate, newer feature (launched Nov 2022) built for scheduling at much larger scale with per-schedule flexible time windows and retries. [eventbridge/09](09_EventBridge_Scheduler_vs_StepFunctions_Study_Notes.md) covers the distinction, and when a Step Functions `Wait` state (tutorial/08) is the better fit than either. |
| "Step Functions usually the most expensive since you pay per step" | Only true of **Standard** workflows, which bill **$0.000025 per state transition** (4,000 free per month). **Express** workflows bill differently — $1.00 per million requests plus duration × memory (GB-seconds) — which can be cheaper or more expensive than Standard depending on the shape of the workload (see [tutorial/09](../tutorial/09_AWS_Step_Functions_Standard_vs_Express_Study_Notes.md) for when to pick which). The video's "pay per step" framing only matches Standard. |
| Relative cost ranking: "Step Functions most expensive, EventBridge mid-range, SQS insanely cheap" | Directionally reasonable at low-to-moderate volume: EventBridge custom/partner events are **$1.00 per million**; SQS gives **1 million requests free per month**, after which it's priced per request at a small fraction of a cent each. The qualitative ranking (SQS cheapest, EventBridge next, Standard Step Functions most expensive per unit of work) holds, but exact numbers should be checked on each service's current pricing page rather than assumed from this video. |

---

## 3. Where this video usefully extends tutorial/17's comparison

[tutorial/17 section 11](../tutorial/17_AWS_Step_Functions_Introduction_Study_Notes.md#11-beyond-the-video-the-alternatives-today) frames the choice mainly as **orchestration (Step Functions) vs. choreography (EventBridge, SNS)**, with SQS mentioned only as part of a combined "SQS/SNS chains" row for "simple, linear handoffs with buffering." This video's contribution is making the case that SQS answers a **third, different question** from the other two — not "who decides the order of steps" (Step Functions) and not "who gets notified that something happened" (EventBridge), but **"what absorbs the gap in speed between a producer and a consumer."** A system can need orchestration, event routing, *and* buffering at once, as the combined example shows — they're not mutually exclusive alternatives to pick one of, the way tutorial/17's table (reasonably, for its purpose) presents Step Functions vs. its alternatives.

### A sharper decision table

| Question you're actually asking | Reach for |
|---|---|
| "What order do these steps need to happen in, and what do I do if one fails?" | **Step Functions** |
| "Something happened — who else needs to know, and I don't want to hard-code who?" | **EventBridge** |
| "I have more incoming work than I can process right now — where does it wait?" | **SQS** |
| "I need all three" (an event starts a workflow; the workflow offloads slow, non-blocking work to a queue) | Compose them, as in the video's closing example |

---

## 4. Gotchas

1. **"SQS guarantees exactly-once" is a FIFO-only property.** Standard queues (the default) are at-least-once with best-effort ordering — design consumers to be idempotent regardless of queue type, the same point already made in tutorial/19's gotchas about `messageId`-as-execution-name.
2. **"Millions of messages per second" doesn't apply to FIFO queues.** Don't choose FIFO for raw throughput; choose it specifically when ordering/dedup matter and you can live with its lower ceiling.
3. **A schedule expression on an EventBridge rule and EventBridge Scheduler are not the same feature**, despite both doing "run this on a timer" — see eventbridge/09 for the actual differences and quotas.
4. **Step Functions' "pay per step" framing is Standard-only.** Express pricing (requests + duration × memory) can make a short-lived, high-volume workflow cheaper than the same workflow running as Standard, or vice versa for a long-running, low-volume one.
5. **These three aren't a menu of alternatives you pick one from** — the video's own closing example uses all three in the same system. Treat the decision table in section 3 as "which question am I answering right now," not "which single service wins."

---

## 5. Cheat sheet

```
Step Functions : orchestration — ordered/parallel steps, built-in retry/catch, visual execution
                 history. Standard: $0.000025/state transition (4,000 free/mo).
                 Express: $1.00/million requests + duration x memory (GB-s).
EventBridge    : choreography/event routing — one event, zero-to-many targets, content filtering
                 via rules, SaaS partner sources, schema registry. $1.00/million custom/partner
                 events; AWS service management events on the default bus are free.
SQS            : buffering — durable queue between producer and worker(s).
                 Standard: at-least-once, best-effort order, very high throughput.
                 FIFO: exactly-once + strict order (per message group), lower throughput.
                 First 1M requests/month free.
Ask yourself   : "what order do steps run in" -> Step Functions
                 "who else should know this happened" -> EventBridge
                 "where does excess work wait" -> SQS
Together       : event -> EventBridge rule -> starts a Step Functions execution -> state machine
                 pushes slow/non-blocking work to SQS for a background worker
```

---

## 6. Review questions

<details>
<summary>1. The video says SQS "guarantees exactly-once processing" for cases like bank transactions. Is this true of any SQS queue, or only one type?</summary>

Only FIFO queues guarantee exactly-once processing and strict ordering (within a message group). Standard queues — the default — are at-least-once with best-effort ordering only.
</details>

<details>
<summary>2. The video claims SQS "can handle millions of messages per second." Does this apply equally to Standard and FIFO queues?</summary>

No. It describes Standard queues' very high, effectively unbounded throughput. FIFO queues trade throughput for ordering/dedup guarantees and have a meaningfully lower ceiling (higher with batching or high-throughput mode, but still not "millions per second" in the same sense).
</details>

<details>
<summary>3. Are "a scheduled EventBridge rule" and "EventBridge Scheduler" the same feature?</summary>

No. A rule with a schedule expression (cron/rate) on an event bus is the older, simpler mechanism. EventBridge Scheduler is a separate, newer feature built for scheduling at much larger scale with flexible time windows and per-schedule retry configuration.
</details>

<details>
<summary>4. Is Step Functions always the most expensive of the three, as the video implies?</summary>

Only its Standard workflow type bills strictly "per step" ($0.000025/state transition). Express workflows bill by request count plus duration × memory, which can make Express cheaper or more expensive than Standard depending on the workload shape — "pay per step" doesn't describe Express.
</details>

<details>
<summary>5. In the video's combined order-processing example, which service plays which role?</summary>

EventBridge catches the `OrderCreated` event and starts a Step Functions execution; the state machine runs the ordered business steps (validate, pay, check inventory, notify); for slow or non-blocking work like sending a confirmation email, the workflow pushes a task onto an SQS queue for a background worker to pick up later.
</details>

<details>
<summary>6. Is it accurate to treat Step Functions, EventBridge, and SQS as three alternatives you choose one of?</summary>

No — they answer different questions (ordering/error-handling, event routing/fan-out, and buffering/backpressure respectively) and commonly appear together in the same system, as the video's own closing example shows.
</details>

<details>
<summary>7. If you need a queue where message order and exactly-once processing both matter, what must you explicitly choose?</summary>

A FIFO queue with a message group ID — this isn't the default behavior of a Standard queue, which is at-least-once with best-effort ordering only.
</details>
