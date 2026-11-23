data "aws_caller_identity" "current" {}

locals {
  functions = {
    ProcessPurchase = "lambda_function.process_purchase"
    ProcessRefund   = "lambda_function.process_refund"
  }
}

# --- Lambda code: one file holds both handlers, zipped once ---

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/build/lambda.zip"
}

# --- Lambda execution role (assumed by Lambda when the function runs) ---

resource "aws_iam_role" "lambda_exec" {
  name = "TransactionProcessorLambdaRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Created up front so they get a retention period. Lambda's auto-created groups never expire.
resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = local.functions
  name              = "/aws/lambda/${each.key}"
  retention_in_days = 7
}

resource "aws_lambda_function" "fn" {
  for_each = local.functions

  function_name = each.key
  handler       = each.value
  runtime       = "python3.13"
  role          = aws_iam_role.lambda_exec.arn

  filename = data.archive_file.lambda.output_path
  # Changes when the code changes, which triggers a redeploy (the console's "Deploy" button).
  source_code_hash = data.archive_file.lambda.output_base64sha256

  depends_on = [
    aws_iam_role_policy_attachment.lambda_logs,
    aws_cloudwatch_log_group.lambda,
  ]
}

# --- State machine role (assumed by Step Functions when an execution runs) ---

resource "aws_iam_role" "sfn" {
  name = "TransactionProcessorStateMachineRole"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

resource "aws_iam_role_policy" "sfn_invoke_lambdas" {
  name = "InvokeTransactionLambdas"
  role = aws_iam_role.sfn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "lambda:InvokeFunction"
      Resource = flatten([
        for f in aws_lambda_function.fn : [f.arn, "${f.arn}:*"]
      ])
    }]
  })
}

# --- State machine ---

resource "aws_sfn_state_machine" "transaction_processor" {
  name     = "TransactionProcessorStateMachine"
  type     = "STANDARD"
  role_arn = aws_iam_role.sfn.arn

  definition = templatefile("${path.module}/statemachine.asl.json", {
    purchase_arn = aws_lambda_function.fn["ProcessPurchase"].arn
    refund_arn   = aws_lambda_function.fn["ProcessRefund"].arn
  })

  # The role must be able to invoke the Lambdas before the first execution.
  depends_on = [aws_iam_role_policy.sfn_invoke_lambdas]
}
