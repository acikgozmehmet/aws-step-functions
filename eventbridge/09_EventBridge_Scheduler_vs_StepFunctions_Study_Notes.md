# EventBridge Scheduler vs. Step Functions Wait State: Study Notes

Source: [Step Functions vs EventBridge Scheduler for AWS Timers](https://www.youtube.com/watch?v=bK1_Bu_BR-E) (Be A Better Dev), about 18:44.

The video compares two ways to delay or schedule an action in AWS: a Step Functions **Wait state** (notes [`../tutorial/08`](../tutorial/08_AWS_Step_Functions_Wait_State_Study_Notes.md)) and **Amazon EventBridge Scheduler** — the feature [`../tutorial/20`](../tutorial/20_Amazon_EventBridge_Overview_Study_Notes.md) named as one of EventBridge's five features but didn't cover. The presenter ran their own informal timing experiments (~50 invocations each) to compare accuracy, and walks through cost, IAM setup, and feature differences.

What was checked:
- Step Functions Standard pricing (per-transition cost, free tier) against the [Step Functions pricing page](https://aws.amazon.com/step-functions/pricing/). The video's on-screen rate (transcribed as "$.00025 per state transition") is a caption/rounding artifact — the actual rate, and the video's own worked math, both reflect **$0.000025** per transition.
- EventBridge Scheduler pricing (free tier, per-invocation cost) against the [EventBridge pricing page](https://aws.amazon.com/eventbridge/pricing/).
- Flexible time windows and `ActionAfterCompletion` against the [EventBridge Scheduler User Guide](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-schedule-flexible-time-windows.html) and its [schedule-deletion page](https://docs.aws.amazon.com/scheduler/latest/UserGuide/managing-schedule-delete.html).
- The "1,000 schedules" quota the video cites is checked against the current [EventBridge Scheduler quotas page](https://docs.aws.amazon.com/scheduler/latest/UserGuide/scheduler-quotas.html) — it's badly out of date (see section 4).
- The video's own empirical accuracy numbers (±1s for Step Functions, ~30s drift for Scheduler) are **not independently re-tested here** — they're the presenter's informal experiment, not a documented AWS SLA, and are reported as such.

---

## 1. The two mechanisms

| | Step Functions Wait state | EventBridge Scheduler |
|---|---|---|
| What it is | A state inside an existing workflow that pauses it | A standalone AWS feature purpose-built for "invoke this target at this time" |
| Setup | Build/own a state machine with a Wait state, pass in a timestamp | One `CreateSchedule` API call with a target + timestamp/rate/cron |
| Launched | Part of Step Functions since its 2016 launch | re:Invent 2022, as a new feature of the existing EventBridge service |
| Needs a workflow around it? | Yes — it's one state in a larger state machine | No — it invokes a target (Lambda, SQS, Step Functions, 270+ services via API destinations) directly |

---

## 2. Accuracy and granularity

| | Step Functions Wait state | EventBridge Scheduler |
|---|---|---|
| Finest unit you can specify | Seconds (`Seconds`, `Timestamp`, `SecondsPath`, `TimestampPath` — notes [`../tutorial/08`](../tutorial/08_AWS_Step_Functions_Wait_State_Study_Notes.md#3-the-four-ways-to-wait)) | Minutes (cron/rate expressions are minute-granularity) |
| Presenter's own measured accuracy (~50 runs each, informal, not an AWS SLA) | ~1 second drift on average | ~30 seconds drift on average |

If an application genuinely needs "fire within a second or two of the requested time," that's a real reason to prefer a Wait state inside a state machine over Scheduler — this isn't something AWS documents as a hard guarantee for either service, so if it's load-bearing for your use case, measure it yourself rather than trusting either number here.

---

## 3. Cost

### Step Functions Standard (the mode the video prices)

Confirmed against AWS's pricing page: **$0.000025 per state transition** ($0.025 per 1,000), with **4,000 free transitions/month**. A trivial two-state Wait→Lambda workflow costs 4 transitions per execution (start → Wait → Lambda → end). At volume:

| Workflows/month | Transitions | Cost (after free tier) |
|---|---|---|
| 1,000,000 | 4,000,000 | ≈ $100 |
| 10,000,000 | 40,000,000 | ≈ $1,000 |
| 20,000,000 | 80,000,000 | ≈ $2,000 |

This matches the video's own numbers. **Express workflows** sidestep per-transition billing (charged by request count + GB-seconds instead), roughly halving cost for this pattern per the video — but Express executions cap at **5 minutes**, so they only work as a timer for short delays.

### EventBridge Scheduler

Confirmed: **14,000,000 invocations/month free**, then **$1.00 per million** beyond that. For almost any realistic volume this is far cheaper than Standard Step Functions transitions — the video's framing ("almost free") holds up.

---

## 4. What has changed since the video

| Then (video, ~2023-2024 era) | Now |
|---|---|
| "Only supports up to 1,000 timer instances" (soft limit) | Default quota is **10,000,000 schedules per Region** (adjustable to billions) — AWS raised this substantially; the video's stated limit and its "ask support for an increase" advice are both stale |
| "Confusing IAM setup" | Still true in substance — a schedule's target still needs an execution role that EventBridge Scheduler assumes, and the caller still needs `iam:PassRole` for that role. AWS has since added **universal targets** (`arn:aws:scheduler:::aws-sdk:*`) and templated targets to simplify common cases, but the role/trust-policy/PassRole mechanics the video complains about are unchanged. |
| "Just introduced" `ActionAfterCompletion` | Now a standard, documented option (`DELETE` or `NONE`) on any schedule — confirmed current, not new |

---

## 5. Feature differences that matter beyond timing

| Step Functions Wait state | EventBridge Scheduler |
|---|---|
| Full access to everything else Step Functions does in the same execution: Parallel, Map, Choice, Retry/Catch, 220+ direct service integrations (notes [`../tutorial/17`](../tutorial/17_AWS_Step_Functions_Introduction_Study_Notes.md)) | A single target per schedule; no branching, retries-with-backoff, or multi-step logic built in |
| Execution history ties the wait, the timestamp, and what ran afterward together automatically | **No built-in link** between a schedule firing and what its target did afterward — the video calls this out as a real auditability gap. Workaround: embed your own correlation ID in the schedule's `Input` and log it in the target. |
| One-shot per execution; recurring means starting a new execution each time | Native **recurring schedules** (rate/cron expressions) in addition to one-time ones, with no separate "restart the workflow" logic needed |
| No built-in anti-stampede mechanism — many executions hitting the same `Timestamp` all resume at once | **Flexible time windows** (confirmed): set `FlexibleTimeWindow: {Mode: FLEXIBLE, MaximumWindowInMinutes: N}` and EventBridge Scheduler spreads invocations across that window instead of firing them all at once — directly solves the "concert ticket notification stampede" example from the video |

### Flexible time window, verified syntax

```bash
aws scheduler update-schedule --name my-schedule \
  --schedule-expression 'rate(1 hour)' \
  --flexible-time-window '{"Mode": "FLEXIBLE", "MaximumWindowInMinutes": 15}' \
  --target file://target-configuration.json
```

This invokes the target *within* 15 minutes after the scheduled time, not exactly on it — the same tradeoff as the "~30 second drift" observation in section 2, just intentional and configurable here instead of incidental.

---

## 6. Decision table

| You need... | Pick |
|---|---|
| A delay or timer as one step inside a larger workflow that also does other things (save to DynamoDB, call a Lambda, branch on a condition) | **Wait state** — it's already in the same execution, same audit trail, no extra service to wire up |
| Second-level timing accuracy | **Wait state** (per the presenter's own testing; verify for your own use case if this is load-bearing) |
| "Run this one thing at a future time," with nothing else around it | **EventBridge Scheduler** — one API call, no workflow to build or own |
| A recurring job (nightly, hourly) that doesn't need branching/retries beyond what its single target does | **EventBridge Scheduler** with a cron/rate expression |
| Very high volume (millions of timers/month) where Standard Step Functions transition cost would be painful | **EventBridge Scheduler** (near-free) — or Express Step Functions if you also need workflow features and delays stay under 5 minutes |
| Many timers firing at the same moment, where a stampede on a downstream service is a risk | **EventBridge Scheduler** with a flexible time window |
| A clear built-in audit trail linking "this timer" to "this exact downstream action" | **Wait state** — Scheduler needs you to build that correlation yourself |

---

## 7. Gotchas

1. **The video's on-screen price (`$.00025`/transition) is garbled relative to its own math** — the real rate, consistent with the $100/$1,000/$2,000 figures it computes, is $0.000025/transition ($0.025 per 1,000).
2. **EventBridge Scheduler's "1,000 schedules" limit is stale.** Current default is 10,000,000 per Region. Don't design around the old number.
3. **Flexible time windows and minute-level granularity aren't the same gap.** Even with jitter off, Scheduler only accepts minute-granularity cron/rate expressions — there's no way to ask for second-level precision from Scheduler itself.
4. **Scheduler needs its own execution role, not your caller's permissions.** The role must trust the Scheduler service *and* allow the target action; the caller creating the schedule separately needs `iam:PassRole` on that role. Forgetting either half is the most common setup failure.
5. **Express workflows cap at 5 minutes**, so "cheaper Step Functions timer via Express" only works for short delays, not the heavier "wait two weeks for a reminder email" scenario the video opens with.
6. **No native request/response correlation in Scheduler.** If you need to prove "schedule X caused Lambda invocation Y," you must embed and log a correlation ID yourself — nothing ties these together automatically the way Step Functions' execution history does.

---

## 8. Cheat sheet

```
Step Functions Wait state         EventBridge Scheduler
---------------------------       ---------------------------
Inside a workflow                 Standalone, one target per schedule
Second-level granularity          Minute-level granularity
~1s drift (informal test)         ~30s drift (informal test)
$0.000025/transition, Standard    14M invocations/mo free, then $1/million
                                   (4,000/mo free; 4 transitions/trivial workflow)
No built-in stampede protection   FlexibleTimeWindow spreads invocations
No native recurring primitive     Native rate()/cron() recurring schedules
Full Step Functions feature set   Single target; no branching/retry built in
Audit trail built in              Must self-correlate (embed an ID in Input)
Needs a state machine + its role  Needs a schedule + a role IT assumes + caller's iam:PassRole
Quota: driven by Step Functions   Quota: 10,000,000 schedules/Region (was 1,000; raised since video)
   account limits
```

---

## 9. Review questions

<details>
<summary>1. The video's slide shows "$.00025 per state transition" for Standard Step Functions, but its own worked example ($100 for 1M workflows at 4 transitions each) only checks out at a different number. What's the real rate, and why does it reconcile the math?</summary>

$0.000025 per transition ($0.025 per 1,000). At that rate, 1,000,000 workflows × 4 transitions = 4,000,000 transitions, minus 4,000 free = 3,996,000 × $0.000025 ≈ $100 — matching the video's own stated result. The on-screen "$.00025" is off by a factor of 10 from what the video's math actually uses.
</details>

<details>
<summary>2. Why would you choose a Wait state over EventBridge Scheduler even though Scheduler is simpler to set up?</summary>

When the timer is one step inside a larger workflow that also does other things (parallel calls, retries, branching), or when you need second-level timing accuracy and a single built-in audit trail linking the timer to what happened afterward.
</details>

<details>
<summary>3. Why would you choose EventBridge Scheduler over a Step Functions Wait state even though it's less accurate?</summary>

When there's no surrounding workflow — you just need "invoke this target at this time" — and when volume is high enough that Standard Step Functions' per-transition cost would be significant. Scheduler's generous free tier (14M invocations/month) makes it close to free at most realistic scales.
</details>

<details>
<summary>4. What two IAM pieces does EventBridge Scheduler need that often trip people up?</summary>

An execution role that Scheduler itself assumes at invocation time (with a trust policy allowing the Scheduler service, plus permissions to invoke the actual target), and `iam:PassRole` permission for whoever calls `CreateSchedule`, so they're allowed to hand that role to the service.
</details>

<details>
<summary>5. The video says EventBridge Scheduler only supports 1,000 schedules per account. Is that still accurate?</summary>

No — it's stale. The current default quota is 10,000,000 schedules per Region (adjustable to billions). AWS raised this substantially since the video was made.
</details>

<details>
<summary>6. How does a "flexible time window" solve the concert-ticket-notification stampede problem from the video?</summary>

Instead of every schedule firing at exactly the same instant and potentially overwhelming a downstream service (e.g. exhausting database connections), a flexible time window (e.g. `MaximumWindowInMinutes: 15`) spreads the actual invocations across that window, so they land at slightly different times instead of all at once.
</details>

<details>
<summary>7. Why can't you simply use Express Step Functions workflows to get Scheduler-like low cost with Wait-state-like second-level accuracy for every use case?</summary>

Express workflows cap execution duration at 5 minutes, so they can't be used for delays longer than that (e.g. the video's two-week follow-up-email example) — only for short waits.
</details>

<details>
<summary>8. If you need to prove, after the fact, exactly which schedule invocation caused a specific Lambda execution, what do you have to do with each tool?</summary>

With a Step Functions Wait state, this is free — the execution history already ties the wait, its timestamp, and the following state together. With EventBridge Scheduler, there's no built-in link; you must embed your own correlation ID in the schedule's `Input` and have the target log it.
</details>
