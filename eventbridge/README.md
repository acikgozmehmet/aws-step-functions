# Amazon EventBridge study notes

A standalone collection of EventBridge-focused study notes, separate from the numbered [`tutorial/`](../tutorial/) Step Functions series. These exist because EventBridge is one of the ways to start (and react to) a Step Functions execution — [`tutorial/19`](../tutorial/19_AWS_Step_Functions_Trigger_from_SQS_Study_Notes.md), [`tutorial/20`](../tutorial/20_Amazon_EventBridge_Overview_Study_Notes.md), and [`tutorial/21`](../tutorial/21_S3_Multipart_Upload_Study_Notes.md) all touch EventBridge but don't cover it end to end. Those three notes stay in `tutorial/` since they're already numbered and cross-linked into that series; this folder is additive, not a reorg.

| # | Topic | Source | Depth |
|---|---|---|---|
| [01](01_EventBridge_Rules_Deep_Dive_Study_Notes.md) | Event patterns and content filtering (numeric, prefix, anything-but, etc.) | Serverless Land | Standard |
| [02](02_EventBridge_Integrating_With_Step_Functions_Study_Notes.md) | **Rule → Step Functions target, and `events:PutEvents` from a state machine, both directions built** | Serverless Land | **Full — pick** |
| [03](03_EventBridge_Trigger_Step_Function_Event_Study_Notes.md) | A second, shorter rule→state-machine lab (EC2 stop event); scoped to avoid repeating note 02 | Unus AWS | Standard |
| [04](04_EventBridge_Step_Functions_Hands_On_Study_Notes.md) | **End-to-end lab: S3 upload → EventBridge → Step Functions → DynamoDB/SQS branching** | Cumulus Cycles | **Full — pick** |
| [05](05_EventBridge_Pipes_SQS_StepFunctions_CDK_Study_Notes.md) | **EventBridge Pipes (SQS → Step Functions) built with the AWS CDK**, batch size 5 vs. tutorial/19's CLI build at batch size 1 | James Eastham (AWS) | **Full — pick** |
| [06](06_EventBridge_Pipes_Explained_Study_Notes.md) | Pipes mechanics beyond tutorial/19 and note 05: sources, enrichment, filtering cost, failure handling | System Design Lab | Standard |
| [07](07_EventBridge_S3_Event_Notifications_Study_Notes.md) | S3 → EventBridge → SNS, including the encrypted-topic KMS permission; fills in the event shape tutorial/21 §8 only sketched | DataEng Uncomplicated | Standard |
| [08](08_EventBridge_vs_StepFunctions_vs_SQS_Study_Notes.md) | Decision table: orchestration vs. event routing vs. buffering, with corrected pricing/throughput claims | Design Decode Camp | Standard |
| [09](09_EventBridge_Scheduler_vs_StepFunctions_Study_Notes.md) | EventBridge Scheduler vs. a Step Functions Wait state, for timers | Be A Better Dev | Standard |
| [10](10_EventBridge_GuardDuty_Automated_Remediation_Study_Notes.md) | **GuardDuty/Security Hub → EventBridge → Lambda/Step Functions remediation — the sequel to tutorial/20** | Cybr | **Full — pick** |

## The four picks

- **02** and **04** close the one gap the `tutorial/` series left open: an EventBridge rule actually targeting a Step Functions state machine, built and verified rather than just named as a capability.
- **05** extends the Pipes→Step Functions pattern from `tutorial/19` with the AWS CDK, from a credible source (an AWS Developer Advocate), and surfaces a real difference (batch size > 1 forcing a Map state).
- **10** is the direct sequel to `tutorial/20`: same course, same GuardDuty setup, moving from "notify a human" to "automatically remediate."

## What was checked

Every note in this folder follows the same discipline as `tutorial/19`-`21`: technical claims from the video are checked against current AWS documentation (cited inline), not taken at face value. Several notes caught real corrections — stale quota figures, incorrect payload-size limits, pricing that only applies to one mode of a service, an overly broad `Catch` clause masking failures, and more. Each note's own "what was checked" section lists its specific sources.
