# Triggering a Step Function from an EC2 Stop Event: Study Notes

Source: [Trigger Step Function with an event from EventBridge](https://www.youtube.com/watch?v=hwMcqzpKBOg), channel Unus AWS, 4:01.

This is a short, console-only hands-on: an EventBridge rule matches EC2 "stopping" state-change events and targets a pre-built Step Functions state machine directly, no Lambda in between. It covers the same core pairing — EventBridge rule → Step Functions target — as [`02_EventBridge_Integrating_With_Step_Functions_Study_Notes.md`](02_EventBridge_Integrating_With_Step_Functions_Study_Notes.md) in this folder, which is the fuller, official (Serverless Land) treatment of that integration. **If you've read note 02, the only new things here are:** a live console walkthrough with a concrete EC2-stop trigger, explicit confirmation that targeting a state machine needs a console-created **IAM role** (not a resource-based policy — verified in section 3), and the video's suggested real-world extension (auto-restarting the stopped instance). Skip to section 3 if you just want that.

What was checked:
- The EC2 state-change event pattern and valid state values were checked against the [EC2 event patterns for rules](https://docs.aws.amazon.com/eventbridge/latest/userguide/ec2-event-patterns-for-rules.html) page.
- The permission model for a Step Functions target (IAM role vs. resource-based policy) was checked against the [`PutTargets` API reference](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutTargets.html), which states this explicitly and gives a worked example.
- Standard/Express `StartExecution` semantics referenced in the gotchas come from this repo's own [notes 09](../tutorial/09_AWS_Step_Functions_Standard_vs_Express_Study_Notes.md) and [notes 19](../tutorial/19_AWS_Step_Functions_Trigger_from_SQS_Study_Notes.md#10-beyond-the-video-a-better-handler), already validated there.
- Nothing was run against a live AWS account for this note.

---

## 1. What the video builds

```mermaid
flowchart LR
    EC2[EC2 instance] -->|stop instance| EV[EC2 Instance<br/>State-change Notification]
    EV --> B[(Default event bus)]
    B --> R{Rule: EC2 stop event<br/>state = stopping}
    R -->|match| SF[Step Functions:<br/>"trigger SF through event bridge"]
    SF --> P[Pass/Wait state:<br/>print hello world, wait 5s]
```

| Piece | What the video does |
|---|---|
| State machine | Pre-built, trivial: prints a message, waits 5 seconds. Exists only to prove the trigger works — no real task. |
| Rule | Default event bus, "rule with an event pattern" (not the schedule rule type). Event source: AWS services → EC2 → **EC2 Instance State-change Notification**. |
| State filter | "Specific states" → **`stopping`** (not `stopped`) — chosen because it fires sooner in the EC2 stop sequence (`running → stopping → stopped`) |
| Target | AWS service → **Step Functions state machine** → the pre-built state machine |
| Permission | Console offers to **create a new role**, granting EventBridge permission to start this execution |

The resulting event pattern matches what's already documented and verified in this repo (notes on EventBridge/EC2 patterns):

```json
{
  "source": ["aws.ec2"],
  "detail-type": ["EC2 Instance State-change Notification"],
  "detail": { "state": ["stopping"] }
}
```

---

## 2. Verifying the result (what the video actually demonstrates)

The video doesn't just create the rule and assume it works — it proves it:

1. Open the state machine's **Executions** tab, and narrow the time window to "last 5 minutes" to get an empty list (a deliberate control, so the next execution is unambiguous).
2. Stop the EC2 instance from the EC2 console.
3. Refresh the executions list: a new execution appears, running, then completes within the few seconds it takes the Pass/Wait demo to finish.

This is a reasonable, repeatable way to confirm an EventBridge-to-Step-Functions wire-up works before building real logic into the state machine — worth reusing for your own rules.

---

## 3. The permission model (the one fact this video confirms that's easy to get wrong)

The console's "create a new role" step isn't incidental — it reflects a real, documented asymmetry in how EventBridge authorizes different target types. AWS's own `PutTargets` API reference states it plainly:

> "For AWS Lambda and Amazon SNS resources, EventBridge relies on resource-based policies. For EC2 instances, Kinesis Data Streams, **AWS Step Functions state machines** and API Gateway APIs, EventBridge relies on **IAM roles that you specify in the `RoleARN` argument** in `PutTargets`."

So unlike the SNS targets built in [notes 19](../tutorial/19_AWS_Step_Functions_Trigger_from_SQS_Study_Notes.md) and [notes 20](../tutorial/20_Amazon_EventBridge_Overview_Study_Notes.md) — where the target gets a resource-based policy statement naming the rule's ARN — a Step Functions target needs an **execution role** that EventBridge itself assumes. AWS's documented example for exactly this:

```json
{
  "Rule": "testrule",
  "Targets": [{
    "RoleArn": "arn:aws:iam::123456789012:role/MyRoleToAccessStepFunctions",
    "Arn": "arn:aws:states:us-east-1:123456789012:stateMachine:HelloWorld",
    "Input": "Hello World!"
  }]
}
```

The role the console creates on your behalf has, at minimum:

**Trust policy** (lets EventBridge assume the role):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "events.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
```

**Permissions policy** (least privilege: scoped to this one state machine):
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "states:StartExecution",
    "Resource": "arn:aws:states:us-east-1:123456789012:stateMachine:HelloWorld"
  }]
}
```

If you build this with the CLI instead of the console, you must create this role (and pass its ARN as `RoleArn`) yourself — there's no resource-based-policy shortcut available for this target type, unlike SNS.

---

## 4. The video's own suggested extension

At the end (03:38), the presenter notes the obvious next step: since the trigger is "EC2 instance stopping," the state machine could do something useful with that fact — e.g., invoke a Lambda Task that calls `ec2:StartInstances` to restart it (an auto-remediation / self-healing pattern). This is a one-Task state machine away from the demo shown, and is the same shape of idea this repo's [notes 12](../tutorial/12_AWS_Step_Functions_Serverless_Order_Workflow_Study_Notes.md) and [notes 20 §9](../tutorial/20_Amazon_EventBridge_Overview_Study_Notes.md#9-beyond-the-video-step-functions-as-the-target-instead-of-sns) build out in more depth for GuardDuty-driven remediation.

---

## 5. Gotchas

1. **The target is asynchronous.** A rule targeting a state machine calls `StartExecution` and moves on; EventBridge doesn't wait for (or expose) the execution's result. The video confirms this by checking the Executions tab manually rather than seeing any result in EventBridge itself.
2. **Step Functions targets need an IAM role, not a resource-based policy.** Easy to assume it works like the SNS/Lambda case (notes 19/20) — it doesn't (section 3).
3. **`stopping` fires before `stopped`.** Picking `stopping` makes for a faster demo, but if your real use case cares about the instance actually being stopped (not just stopping), filter on `stopped` instead.
4. **No idempotency built in.** Nothing here names the execution (e.g. after an idempotency key), so a redelivered or duplicate EC2 event would start a second, independent execution. Compare with the `name=messageId` pattern in [notes 19 §10](../tutorial/19_AWS_Step_Functions_Trigger_from_SQS_Study_Notes.md#10-beyond-the-video-a-better-handler) for why that matters once the state machine does something non-idempotent (like actually restarting the instance).
5. **This target type is `ASYNC` only.** You can't use a rule target to run a Standard workflow's `.sync`/callback patterns and get a response back through EventBridge — you'd need to call `StartExecution`/`StartSyncExecution` yourself (e.g. from Lambda, as in [notes 06](../tutorial/06_AWS_Step_Functions_Start_Execution_from_Lambda_Study_Notes.md)) if you need that.

---

## 6. Cheat sheet

```
Pattern   : source "aws.ec2", detail-type "EC2 Instance State-change Notification",
            detail.state one of pending|running|shutting-down|stopping|stopped|terminated
Target    : AWS service -> Step Functions state machine -> StartExecution (ASYNC)
Perm      : IAM execution role (RoleArn in PutTargets), trust events.amazonaws.com,
            states:StartExecution scoped to the state machine -- NOT a resource-based policy
Console   : offers to auto-create this role when you pick a state machine target
Verify    : filter Executions to a short time window before triggering, so the next
            execution is unambiguous
```

---

## 7. Review questions

<details>
<summary>1. Why does the rule filter on "stopping" rather than "stopped"?</summary>

Purely to make the demo faster — `stopping` fires earlier in the EC2 stop sequence (`running → stopping → stopped`). If the use case needs the instance to actually be stopped, filter on `stopped`.
</details>

<details>
<summary>2. How does EventBridge get permission to start an execution of this state machine?</summary>

Through an IAM execution role specified in the target's `RoleArn`, which EventBridge assumes (trust policy for `events.amazonaws.com`) and which grants `states:StartExecution` on that state machine — not a resource-based policy, unlike Lambda or SNS targets.
</details>

<details>
<summary>3. If you build this rule with the AWS CLI instead of the console, what do you need to create yourself that the console would otherwise handle?</summary>

The IAM role (trust policy + `states:StartExecution` permission) and pass its ARN as `RoleArn` in the `PutTargets` call — the console creates this role automatically when you pick a Step Functions target, but the CLI does not.
</details>

<details>
<summary>4. Does EventBridge wait for the state machine's execution to finish, or get its result back?</summary>

No — targeting a state machine from a rule is asynchronous (`StartExecution`, fire-and-forget). You have to check the Step Functions console or API separately to see the execution's progress or result, exactly as the video does.
</details>

<details>
<summary>5. What real-world action does the video suggest building on top of this exact trigger?</summary>

Using the EC2-stop event to automatically restart the instance — e.g., a Task state in the state machine that invokes a Lambda function calling `ec2:StartInstances` — a simple self-healing/auto-remediation pattern.
</details>

<details>
<summary>6. What happens if the same EC2 stop event is somehow delivered twice, given how this state machine is started?</summary>

Two independent executions start, since nothing here gives the execution a deterministic name tied to the event. Compare with naming the execution after a stable idempotency key (e.g. `messageId` in an SQS-driven trigger, notes 19 §10) to collapse duplicates into one execution on a Standard workflow.
</details>
