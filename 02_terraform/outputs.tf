output "lambda_arns" {
  value = { for name, f in aws_lambda_function.fn : name => f.arn }
}

output "state_machine_arn" {
  value = aws_sfn_state_machine.transaction_processor.arn
}

output "start_purchase_command" {
  value = "aws stepfunctions start-execution --state-machine-arn ${aws_sfn_state_machine.transaction_processor.arn} --input '{\"TransactionType\": \"PURCHASE\"}'"
}
