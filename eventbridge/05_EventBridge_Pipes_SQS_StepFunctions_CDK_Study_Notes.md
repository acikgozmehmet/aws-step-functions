# EventBridge Pipes with the AWS CDK: SQS to Step Functions: Study Notes

Source: [Integrate SQS & StepFunctions with EventBridge Pipes & the AWS CDK](https://www.youtube.com/watch?v=xFa8Y_9GQ6I), James Eastham (AWS Senior Developer Advocate), about 21 minutes, published shortly after EventBridge Pipes launched at re:Invent 2022.

This builds the exact same pattern as [tutorial/19 section 12](../tutorial/19_AWS_Step_Functions_Trigger_from_SQS_Study_Notes.md#12-beyond-the-video-no-lambda-with-eventbridge-pipes) — an SQS queue feeding a Step Functions state machine through a pipe, no Lambda in between — but two things differ: this video builds it with the **AWS CDK** (C#) instead of the AWS CLI, and it uses a **batch size of 5** instead of 1, which forces the state machine to handle an *array* of messages with a Map state rather than reading a single message at `$[0]`. That difference is the most useful thing this video adds to this repo (section 5).

What was checked:
- The `CfnPipe` L1 construct's properties (`roleArn`, `source`, `sourceParameters`, `target`, `targetParameters`, `enrichment`, `enrichmentParameters`) were checked against the current [CDK API reference for `CfnPipe`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_pipes.CfnPipe.html).
- The `InvocationType` values for a Step Functions target (`FIRE_AND_FORGET`, `REQUEST_RESPONSE`, and that `REQUEST_RESPONSE` is unsupported for Standard workflows) were checked against [`PipeTargetStateMachineParametersProperty`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_pipes.CfnPipe.PipeTargetStateMachineParametersProperty.html).
- The IAM principal for a pipe's execution role (`pipes.amazonaws.com`, distinct from a rule's `events.amazonaws.com`) and the exact SQS source permissions required were checked against [Event source permissions for EventBridge Pipes](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-pipes-permissions.html).
- Whether an L2 (higher-level) CDK construct exists today, since the video states only an L1 construct was available at the time, was checked against the [`@aws-cdk/aws-pipes-alpha` module README](https://raw.githubusercontent.com/aws/aws-cdk/main/packages/%40aws-cdk/aws-pipes-alpha/README.md) (section 7).
- Nothing was deployed; no CDK app was synthesized or run here.

---

## Contents

1. [What EventBridge Pipes adds, per the video](#1-what-eventbridge-pipes-adds-per-the-video)
2. [The four things you configure on a pipe](#2-the-four-things-you-configure-on-a-pipe)
3. [The CDK build, piece by piece](#3-the-cdk-build-piece-by-piece)
4. [The state machine: handling a batch, not a single message](#4-the-state-machine-handling-a-batch-not-a-single-message)
5. [How this differs from tutorial/19's version of the same pattern](#5-how-this-differs-from-tutorial19s-version-of-the-same-pattern)
6. [IAM, verified](#6-iam-verified)
7. [What has changed since the video](#7-what-has-changed-since-the-video)
8. [Gotchas](#8-gotchas)
9. [Cheat sheet](#9-cheat-sheet)
10. [Review questions](#10-review-questions)

---

## 1. What EventBridge Pipes adds, per the video

The video's framing (00:52): before Pipes, connecting "SQS to Step Functions" needed a Lambda function purely to pull messages off the queue and call `StartExecution` — pure "glue code" with no business logic of its own. A pipe replaces that Lambda entirely: EventBridge polls the source and calls the target's API directly, with **no code to deploy or maintain**.

This matches tutorial/19's own framing of the same trade-off (its section 10 "better handler" vs. section 12 "no Lambda, with EventBridge Pipes").

---

## 2. The four things you configure on a pipe

The video's mental model (01:05 onward), which matches `CfnPipe`'s actual shape:

| Piece | Video's description | Optional? |
|---|---|---|
| **Source** | Where events come from: SQS, DynamoDB Streams, Kinesis, Kafka (self-managed or MSK), Amazon MQ, RabbitMQ, ActiveMQ | Required, exactly one |
| **Filter** | Same event-pattern syntax as EventBridge rules; drop events that don't match before they cost you anything downstream | Optional |
| **Enrichment** | Call out (Lambda, a synchronous Step Functions execution, an API destination, API Gateway) to add data to the event before it reaches the target — the video's example: look up a customer's delivery address before the order reaches the target | Optional |
| **Target** | Where the (possibly filtered, possibly enriched) event ends up: Step Functions, another queue, EventBridge itself, a Lambda function, an HTTP endpoint, a Batch job, and more | Required, exactly one |

The video's own example (01:54) threads all four together: an order event comes off SQS (source), passes a filter, gets enriched with the customer's delivery address via an API or Step Functions call, and lands on a Step Functions target that kicks off order processing. This build only uses source + target — no filter, no enrichment — which is a smaller, no-code CDK equivalent of what tutorial/19's CLI build (source + target only) already covers.

---

## 3. The CDK build, piece by piece

Reconstructed from the video's live coding (C#, `cdk init app --language csharp`), verified against current `CfnPipe` docs:

```csharp
// Source: a plain SQS queue
var sourceQueue = new Queue(this, "SourceQueue");

// Target: a plain (empty, for now) Standard state machine
var targetStateMachine = new StateMachine(this, "TargetStateMachine");

// IAM: let the pipe receive/delete from the source queue
var sourcePolicy = new PolicyStatement(new PolicyStatementProps {
    Effect = Effect.ALLOW,
    Resources = new[] { sourceQueue.QueueArn },
    Actions = new[] { "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes" }
});

// IAM: let the pipe start an execution of the target state machine
var targetPolicy = new PolicyStatement(new PolicyStatementProps {
    Effect = Effect.ALLOW,
    Resources = new[] { targetStateMachine.StateMachineArn },
    Actions = new[] { "states:StartExecution" }
});

// The role the pipe itself assumes -- note the principal is pipes.amazonaws.com, not events.amazonaws.com
var pipeRole = new Role(this, "PipeRole", new RoleProps {
    AssumedBy = new ServicePrincipal("pipes.amazonaws.com")
});
pipeRole.AddToPolicy(sourcePolicy);
pipeRole.AddToPolicy(targetPolicy);

// The pipe itself -- today, only an L1 (CfnPipe) construct exists (section 7)
var pipe = new CfnPipe(this, "MyNewPipe", new CfnPipeProps {
    RoleArn = pipeRole.RoleArn,
    Source = sourceQueue.QueueArn,
    SourceParameters = new CfnPipe.PipeSourceParametersProperty {
        SqsQueueParameters = new CfnPipe.PipeSourceSqsQueueParametersProperty {
            BatchSize = 5,
            MaximumBatchingWindowInSeconds = 10
        }
    },
    Target = targetStateMachine.StateMachineArn,
    TargetParameters = new CfnPipe.PipeTargetParametersProperty {
        StepFunctionStateMachineParameters = new CfnPipe.PipeTargetStateMachineParametersProperty {
            InvocationType = "FIRE_AND_FORGET"
        }
    }
});
```

Every `SourceParameters`/`TargetParameters` field is typed per-source and per-target (`PipeSourceParametersProperty` has one slot for each supported source — SQS, Kinesis, DynamoDB, Kafka, Amazon MQ, RabbitMQ, self-managed Kafka — and `PipeTargetParametersProperty` has one slot per supported target), which is what the video calls out as the CDK's main ergonomic win over hand-writing the equivalent CloudFormation/CLI JSON: autocomplete and compile-time checking of exactly which parameters a given source or target accepts, instead of a loosely-typed JSON blob.

---

## 4. The state machine: handling a batch, not a single message

Because the pipe's `BatchSize` is 5, a single pipe invocation can hand the target **an array of up to 5 SQS messages**, not one message at a time. The video's state machine handles this with a `Map` state whose items path is the entire input:

```json
{
  "Comment": "Handles a batch of SQS messages delivered by an EventBridge pipe",
  "StartAt": "ForEachMessage",
  "States": {
    "ForEachMessage": {
      "Type": "Map",
      "ItemsPath": "$",
      "ItemProcessor": {
        "ProcessorConfig": { "Mode": "INLINE" },
        "StartAt": "FiveSecondWait",
        "States": {
          "FiveSecondWait": {
            "Type": "Wait",
            "Seconds": 5,
            "End": true
          }
        }
      },
      "End": true
    }
  }
}
```

`ItemsPath: "$"` is the .NET CDK's `JsonPath.ENTIRE_PAYLOAD` — "use the whole input as the array to iterate over." Inside the `Map`, the five-second `Wait` stands in for real per-message work ("you might make a call off to another step function to actually start your order processing workflow," 13:51) — a placeholder, not a real processing step.

### What the console execution showed (11:08-19:51 in the video)

- Sending **one** message to the source queue produced an execution whose top-level input was a **one-element JSON array** — `[ { ...one SQS message... } ]` — confirming the batch shape even when the batch happens to contain only one message.
- The execution history showed exactly one `Map` iteration and one `Wait` state entered, each lasting about five seconds, matching the single queued message.

---

## 5. How this differs from tutorial/19's version of the same pattern

[Tutorial/19 section 12](../tutorial/19_AWS_Step_Functions_Trigger_from_SQS_Study_Notes.md#12-beyond-the-video-no-lambda-with-eventbridge-pipes) builds the identical SQS-to-Step-Functions pipe with the AWS CLI, but with `BatchSize: 1`, and its state machine reads a single message directly with a `Pass` state at `$[0].messageId` / `$[0].body`. That note's own text even predicts this video's design:

> "For batches larger than 1, use a Map state over `$` instead of reading `$[0]`."

This video is a real-world confirmation of exactly that advice, built independently with batch size 5. Side by side:

| | tutorial/19 (CLI, batch size 1) | This video (CDK, batch size 5) |
|---|---|---|
| Source parameters | `BatchSize: 1` | `BatchSize: 5`, `MaximumBatchingWindowInSeconds: 10` |
| State machine's first state | `Pass` reading `$[0].messageId`, `$[0].body` | `Map` over `$` (the whole array) |
| Why it works | With batch size 1, the array always has exactly one element, so `$[0]` is safe | With batch size > 1, `$[0]` would silently process only the first message and ignore the rest — the same failure mode tutorial/19's own gotcha #2 warns about for the *Lambda-trigger* version of this pattern |
| Filter / enrichment | Neither used | Neither used (though the video explains both, 01:30-02:47) |
| Target invocation type | `FIRE_AND_FORGET` | `FIRE_AND_FORGET` |
| Tooling | Raw CLI JSON, fully inspectable | CDK's typed `CfnPipe` properties, less JSON to hand-write, same underlying CloudFormation resource |

Neither build uses a filter or enrichment step — both are the minimal "source plus target" pipe. The video explains filter/enrichment conceptually (section 2 above) but doesn't build either into its own demo.

---

## 6. IAM, verified

The video's spoken description of the IAM setup (04:42-06:21) is accurate; here's what each permission is actually for, confirmed against AWS's current docs:

| Permission | On | Why |
|---|---|---|
| `sqs:ReceiveMessage`, `sqs:DeleteMessage` | Source queue ARN | What the video says: "receive and delete from our SQS queue" |
| `sqs:GetQueueAttributes` | Source queue ARN | **Not mentioned in the video's narration**, but AWS's documented required permission set for an SQS pipe source includes it alongside the two above — the pipe needs it to check queue attributes like visibility timeout |
| `states:StartExecution` | Target state machine ARN | Lets the pipe start an execution — same action as every other way of starting a Standard execution in this repo (notes 06, 19) |
| Trust policy principal: `pipes.amazonaws.com` | The pipe's own execution role | Confirmed distinct from a **rule's** target principal, `events.amazonaws.com` — the video calls this out explicitly ("although it's part of EventBridge, it uses a different service principal") and AWS's docs confirm it: enrichment and target calls from a pipe use the IAM principal `pipes.amazonaws.com` |

---

## 7. What has changed since the video

| Then (this video, ~Dec 2022) | Now |
|---|---|
| "Currently in the CDK there's only actually an L1 construct" (`CfnPipe`) | An **L2 construct module**, `@aws-cdk/aws-pipes-alpha` (plus companion `aws-pipes-sources-alpha` / `aws-pipes-targets-alpha` packages), now exists with a `Pipe` class, typed `ISource`/`ITarget`/`IEnrichment` interfaces, a `FilterPattern` helper, and `InputTransformation` — still marked experimental/alpha, "subject to non-backward compatible changes," but a real step up from hand-building `CfnPipe` properties |
| Sources shown: SQS, DynamoDB, Kinesis, Kafka, Amazon MQ, RabbitMQ, self-managed Kafka | Same list is still current for `CfnPipe`'s `PipeSourceParametersProperty` |
| Targets shown: HTTP, Batch, Lambda, EventBridge, another queue, Step Functions | Still current; `PipeTargetStateMachineParametersProperty`'s `InvocationType` is `REQUEST_RESPONSE` (synchronous, `StartSyncExecution` — **Standard workflows don't support this**) or `FIRE_AND_FORGET` (async, `StartExecution`) — this build correctly uses `FIRE_AND_FORGET` for its Standard-type target |

---

## 8. Gotchas

1. **`InvocationType: REQUEST_RESPONSE` doesn't work on a Standard state machine.** It maps to `StartSyncExecution`, which only Express workflows support. This build's target is a (default) Standard state machine, so `FIRE_AND_FORGET` is the only valid choice here — the video picks correctly, but doesn't explain why the other option would fail.
2. **A batch size above 1 means your state machine receives an array, always** — even a batch that happens to contain just one message still arrives as a one-element array (confirmed in section 4's console walkthrough). Design the state machine for the array shape from the start, as this video does with its `Map` state, rather than special-casing "batch of one."
3. **`sqs:GetQueueAttributes` is a required pipe permission the video doesn't mention out loud** — a hand-rolled IAM policy that only grants `ReceiveMessage`/`DeleteMessage` (what the video says verbally) would be missing it; the CDK code shown on screen does include it implicitly if you copy AWS's own sample policy, but don't rely on the narration alone.
4. **The pipe's own role trusts `pipes.amazonaws.com`, not `events.amazonaws.com`.** Reusing an EventBridge *rule's* target role/trust policy for a *pipe* won't work — they're different service principals even though both are "part of EventBridge."
5. **The L1 `CfnPipe` construct takes source/target ARNs as plain strings**, with no compile-time check that the ARN actually matches the resource type you configured in `SourceParameters`/`TargetParameters`. Getting the ARN right is still on you.

---

## 9. Cheat sheet

```
Why Pipes       : replaces the "Lambda just to move messages" glue code with a managed integration
Four parts      : source (required) -> filter (optional) -> enrichment (optional) -> target (required)
CDK construct   : CfnPipe (L1, stable) -- roleArn, source, sourceParameters, target, targetParameters,
                  enrichment, enrichmentParameters
L2 construct    : @aws-cdk/aws-pipes-alpha -- Pipe, ISource/ITarget/IEnrichment, FilterPattern,
                  InputTransformation -- still experimental, added after this video
SQS source perms: sqs:ReceiveMessage, sqs:DeleteMessage, sqs:GetQueueAttributes (all three, even
                  though the video only narrates the first two)
SF target perms : states:StartExecution on the target state machine's ARN
Pipe role trust : principal pipes.amazonaws.com (NOT events.amazonaws.com -- that's for rules)
Invocation type : FIRE_AND_FORGET = StartExecution (works for Standard); REQUEST_RESPONSE =
                  StartSyncExecution (Express only)
Batch size > 1  : state machine input is always an array -- use Map over "$", never assume "$[0]"
                  is the only message (confirms tutorial/19's own guidance, built independently)
```

---

## 10. Review questions

<details>
<summary>1. What problem did EventBridge Pipes remove, per the video's SQS-to-Step-Functions example?</summary>

Before Pipes, you needed a Lambda function purely to pull messages off the queue and call `StartExecution` -- pure glue code with no business logic. A pipe does that integration directly, with no code to write or deploy.
</details>

<details>
<summary>2. Name the four configurable parts of a pipe, and which two are required.</summary>

Source, filter, enrichment, target. Source and target are required (exactly one each); filter and enrichment are optional.
</details>

<details>
<summary>3. In the video's enrichment example (an order-processing pipe), what does enrichment do that filtering can't?</summary>

Enrichment calls out to another service (an API, or a synchronous Step Functions execution) to fetch additional data -- like a customer's delivery address -- and adds it to the event before it reaches the target. Filtering only decides whether an event passes through; it can't add new data to it.
</details>

<details>
<summary>4. What CDK construct does this build use for the pipe itself, and what's its CloudFormation-level equivalent?</summary>

`CfnPipe`, the L1 (CloudFormation-level) construct, which maps directly onto `AWS::Pipes::Pipe`. At the time of this video, no higher-level (L2) construct existed yet.
</details>

<details>
<summary>5. The pipe's source has `BatchSize: 5`. What shape does the Step Functions execution's input take, even if only one message is in the queue?</summary>

A JSON array -- one element per message in the batch the pipe delivered, even if that array happens to contain only one element. The video's own test (sending a single message) confirmed the execution's input was a one-element array, not a bare object.
</details>

<details>
<summary>6. Why does this state machine use a Map state instead of reading `$[0]` directly, unlike tutorial/19's CLI-built version of the same pattern?</summary>

Because this pipe's batch size is 5, not 1 -- reading only `$[0]` would process the first message and silently ignore the other four. Tutorial/19's version is safe to read `$[0]` only because its batch size is 1, so the array always has exactly one element.
</details>

<details>
<summary>7. What IAM principal does a pipe's execution role trust, and how does that differ from an EventBridge rule's target role?</summary>

`pipes.amazonaws.com`. A rule's target role (for example, one letting a rule invoke Lambda or publish to SNS) trusts `events.amazonaws.com` instead -- they are different principals even though both are part of the broader EventBridge service.
</details>

<details>
<summary>8. The video's narration says the source IAM policy needs "receive and delete" permissions for SQS. What third permission does AWS's own documentation require that isn't mentioned out loud?</summary>

`sqs:GetQueueAttributes`, alongside `sqs:ReceiveMessage` and `sqs:DeleteMessage`.
</details>

<details>
<summary>9. Could this pipe's target use `InvocationType: REQUEST_RESPONSE`? Why or why not?</summary>

No. `REQUEST_RESPONSE` maps to `StartSyncExecution`, which is only supported for Express state machines. This build's target state machine is a (default) Standard workflow, so `FIRE_AND_FORGET` (asynchronous `StartExecution`) is the only valid invocation type.
</details>

<details>
<summary>10. What has AWS added to the CDK for Pipes since this video was published, and what's its stability status?</summary>

An L2 construct module, `@aws-cdk/aws-pipes-alpha` (with companion sources/targets alpha packages), providing a `Pipe` class and typed source/target/enrichment interfaces plus filtering and input transformation helpers. It's still marked experimental/alpha and subject to breaking changes.
</details>

<details>
<summary>11. Why might you choose the L1 `CfnPipe` construct even today, despite the newer L2 module existing?</summary>

The L2 module is still experimental/alpha and explicitly subject to non-backward-compatible changes, which is a real risk for production infrastructure code. `CfnPipe` is the stable, CloudFormation-backed construct and will keep working even as the L2 API evolves.
</details>
