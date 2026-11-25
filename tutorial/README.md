# AWS Step Functions study notes

Notes for the [AWS Simplified Step Functions playlist](https://www.youtube.com/playlist?list=PL9nWRykSBSFgQrO66TmO1vHFP6yuPF5G-), one file per video, in playlist order.

| # | Topic |
|---|---|
| [01](01_AWS_Step_Functions_Overview_Study_Notes.md) | Overview: what Step Functions is, benefits, pricing, a credit card example |
| [02](02_AWS_Step_Functions_with_Lambda_Study_Notes.md) | Choice state + two Lambda functions (Terraform version in [`../02_terraform`](../02_terraform)) |
| [03](03_AWS_Step_Functions_with_SQS_Study_Notes.md) | Send a message to SQS |
| [04](04_AWS_Step_Functions_with_SNS_Study_Notes.md) | Publish to SNS |
| [05](05_AWS_Step_Functions_with_DynamoDB_Study_Notes.md) | Write to DynamoDB, retries, ResultPath |
| [06](06_AWS_Step_Functions_Start_Execution_from_Lambda_Study_Notes.md) | Start an execution from Lambda |
| [07](07_AWS_Step_Functions_Map_State_Study_Notes.md) | Map state (inline) |
| [08](08_AWS_Step_Functions_Wait_State_Study_Notes.md) | Wait state, polling loops |
| [09](09_AWS_Step_Functions_Standard_vs_Express_Study_Notes.md) | Standard vs Express |
| [10](10_AWS_Step_Functions_Workflow_Studio_Study_Notes.md) | Workflow Studio |
| [11](11_AWS_Step_Functions_Data_Flow_Simulator_Study_Notes.md) | Data flow: InputPath to OutputPath, JSONata (simulator retired) |
| [12](12_AWS_Step_Functions_Serverless_Order_Workflow_Study_Notes.md) | Order workflow with DynamoDB, Lambda and compensation (saga) |
| [13](13_AWS_Step_Functions_Lambda_Workflow_Studio_Study_Notes.md) | Lambda workflow in Workflow Studio, passing results between functions |
| [14](14_AWS_Step_Functions_Nested_Workflows_Study_Notes.md) | Parent and child workflows |
| [15](15_AWS_Step_Functions_Distributed_Map_S3_Study_Notes.md) | Distributed Map over a CSV file in S3 |
| [16](16_AWS_Step_Functions_Callback_with_Lambda_Study_Notes.md) | Callbacks with task tokens |
| [17](17_AWS_Step_Functions_Introduction_Study_Notes.md) | Course introduction: use cases, disadvantages, alternatives |
| [18](18_AWS_Step_Functions_Redrive_Study_Notes.md) | Redrive a failed execution |

Extra videos, from other channels:

| # | Channel | Topic |
|---|---|---|
| [19](19_AWS_Step_Functions_Trigger_from_SQS_Study_Notes.md) | DataEng Uncomplicated | Start an execution for each SQS message: Lambda trigger, or EventBridge Pipes with no code |
| [20](20_Amazon_EventBridge_Overview_Study_Notes.md) | AWS Certified Security – Specialty (SCS-C03) course | Amazon EventBridge basics and a console lab: GuardDuty finding to an SNS email via an input transformer — documents Step Functions as a supported GuardDuty/EventBridge target |
| [21](21_S3_Multipart_Upload_Study_Notes.md) | Rahul Saxena | S3 multipart upload and presigned URLs for resumable browser uploads — general system design, not Step Functions; includes a sketch of orchestrating the missing post-upload scan step with a state machine |
