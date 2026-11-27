# Amazon S3 multipart upload study notes

A standalone collection on S3 multipart upload and presigned URLs. Start with [note 00](00_S3_Multipart_Upload_Study_Notes.md), which the other notes build on. For a runnable Python version of its design, with end-to-end tests, see [`code/`](code/README.md).

Note 00 was note 21 of the [`tutorial/`](../tutorial/) series.

| # | Topic | Source | Depth |
|---|---|---|---|
| [00](00_S3_Multipart_Upload_Study_Notes.md) | **Resumable upload design with presigned URLs (start here)** | Rahul Saxena | Base note |
| [01](01_S3_Multipart_Comprehensive_Study_Notes.md) | **.NET SDK, presigned URLs, CORS and multipart end to end** | Milan Jovanović | **Full (pick)** |
| [02](02_S3_Multipart_Presigned_Upload_Study_Notes.md) | Express backend, size switch, parallel parts, App Runner | Chandan Maurya | Standard |
| [03](03_S3_Multipart_AWS_CLI_Study_Notes.md) | **Multipart upload by hand with the AWS CLI** | CloudYeti | **Full (pick)** |
| [04](04_S3_Multipart_Boto3_Python_Study_Notes.md) | boto3 managed transfers and `TransferConfig` | Saadi AWS | Standard |
| [05](05_S3_Multipart_Java_SDK_Study_Notes.md) | Java upload and multipart copy (**poor transcript**, see note) | Dev Problems | Standard |
| [06](06_S3_Multipart_Lifecycle_Cleanup_Study_Notes.md) | **Lifecycle rules and cleanup of incomplete uploads** | IAAS Academy | **Full (pick)** |
| [07](07_S3_Presigned_URLs_General_Study_Notes.md) | Presigned `PUT` and `GET`, when CORS matters | Milan Jovanović | Standard |
| [08](08_S3_Upload_Service_Resumable_Verified_Study_Notes.md) | **Upload service design with integrity checks** | GrowAsEngineers | **Full (pick)** |
| [09](09_Dropbox_File_Chunking_Resumable_Study_Notes.md) | Dropbox design: chunking and resume | Avantika's Notes | Standard |
| [10](10_Dropbox_GDrive_System_Design_Study_Notes.md) | Dropbox design: upload and chunking portion only | Hello Interview | Standard |

## The four picks

- **01** is the broadest single walkthrough, compared with note 00 topic by topic.
- **03** shows the CLI calls that note 00 only listed.
- **06** builds the abort rule that note 00 recommended.
- **08** covers whole-file verification, which note 00 left open.

## Corrections made to note 00

Found while writing these notes and since fixed there.

| Section | Said | Now says |
|---|---|---|
| 2 | A presigned URL is "single-use-scoped" | Reusable until it expires |
| 7 | `aws s3 presign`, then `PUT` to the URL | Signs `upload_part` with boto3, since the command makes `GET` URLs only ([note 03](03_S3_Multipart_AWS_CLI_Study_Notes.md#8-checking-note-00-section-7)) |
| 6, 10, 12 | Only full object checksums need consecutive part numbers | AWS states the requirement for composite checksums; number parts 1, 2, 3 ([note 01](01_S3_Multipart_Comprehensive_Study_Notes.md#9-cross-check-against-note-00)) |

## What was checked

- Technical claims were checked against AWS documentation, cited in each note.
- **Nothing was run against a real AWS account.**
- Python and JavaScript uploads in notes 01, 02, 04, 05, 07 and 08 ran against a local S3 mock (moto). The mock does not enforce checksums or sizes the way S3 does.
- The note 03 shell script ran with a stand-in `aws` command. Note 06's lifecycle JSON was validated against the SDK's request model.
- C# and Java snippets were not compiled.
