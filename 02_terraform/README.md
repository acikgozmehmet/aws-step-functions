# Transaction processor (Terraform)

Terraform version of the console experiment in `../tutorial/02_AWS_Step_Functions_with_Lambda_Study_Notes.md`: two Python Lambdas and a Step Functions state machine whose Choice state routes on `$.TransactionType`.

Uses whatever `AWS_PROFILE` is set. Region defaults to `us-east-1`. Walkthrough: [Terraform_Study_Notes.md](Terraform_Study_Notes.md).

```sh
terraform init
terraform plan
terraform apply

# Run it (or use the console's "Start execution")
aws stepfunctions start-execution \
  --state-machine-arn "$(terraform output -raw state_machine_arn)" \
  --input '{"TransactionType": "REFUND"}'

terraform destroy
```

Edit `lambda/lambda_function.py` and run `terraform apply` again to redeploy the code.
