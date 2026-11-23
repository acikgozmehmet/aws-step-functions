# AWS Step Functions study notes

Study notes and hands-on labs for AWS Step Functions, following the 18-video [AWS Simplified Step Functions playlist](https://www.youtube.com/playlist?list=PL9nWRykSBSFgQrO66TmO1vHFP6yuPF5G-).

| Folder | Contents |
|---|---|
| [`tutorial/`](tutorial/) | One study note per video, in playlist order. Start with the [index](tutorial/README.md). |
| [`02_terraform/`](02_terraform/) | The Lambda lab from note 02 rebuilt with Terraform: two Lambda functions and a state machine. |

## Topics

- **Basics:** overview, Standard vs Express, Workflow Studio, data flow, course intro (01, 09, 10, 11, 17)
- **Service integrations:** Lambda, SQS, SNS, DynamoDB (02 to 05, 13)
- **Flow control:** Map, Distributed Map over S3, Wait, nested workflows, callbacks (07, 08, 14, 15, 16)
- **Errors and recovery:** retries, compensation (saga), redrive (05, 12, 18)
- **Starting workflows from code:** Lambda and boto3 (06)

## What each note contains

- The video's steps, with the state machine definitions rebuilt
- AWS CLI commands for the same setup, ending with cleanup
- Corrections where the video is wrong or out of date, plus gotchas
- A cheat sheet and review questions with hidden answers

The state machine definitions pass AWS's `ValidateStateMachineDefinition`. Their behavior was checked with the `TestState` API, using mocked service responses, and the Lambda code was run locally.

## Before you run a lab

- The labs create real AWS resources: state machines, Lambda functions, DynamoDB tables, SQS queues, SNS topics, S3 buckets. Run the cleanup at the end of each CLI section.
- Account IDs in the notes are the placeholder `123456789012`. No credentials are stored here; the commands use your own AWS CLI profile.
- Python scripts run with [uv](https://docs.astral.sh/uv/): `uv run script.py`.

Not affiliated with AWS or the AWS Simplified channel.
