import datetime


def process_purchase(message, context):
    # 1. Log the input from Step Functions
    print("Received message from Step Functions:")
    print(message)

    # 2. Build the response
    response = {}
    response["TransactionType"] = message["TransactionType"]
    response["Timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response["Message"] = "Hello from lambda land inside the ProcessPurchase function"

    # 3. Return it to the state machine
    return response


def process_refund(message, context):
    print("Received message from Step Functions:")
    print(message)

    response = {}
    response["TransactionType"] = message["TransactionType"]
    response["Timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response["Message"] = "Hello from lambda land inside the ProcessRefund function"

    return response
