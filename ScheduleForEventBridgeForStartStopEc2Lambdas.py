import boto3

ssm_client = boto3.client('ssm')
event_client = boto3.client('events')

def lambda_handler(event, context):
    try:
        next_execution = None
        response = ssm_client.describe_maintenance_windows()
        maintenance_windows = response['WindowIdentities']
        if maintenance_windows:
            for window in maintenance_windows:

                if window['Name'] == 'RunPatchBaseline-NonProd':
                    next_execution = window['NextExecutionTime']   
    
        """Convert NextExecutionTime to Cron Expression"""
        if next_execution:
            next_execution = next_execution.split('T') 
            year, month, day = next_execution[0].split("-")
        cron_exp_start = f"cron(40 16 {day} {month} ? {year})"
        cron_exp_stop = f"cron(40 21 {day} {month} ? {year})"
    except:
        print("No 'Maintenance windows' available.")
    
    try:
        eventbridge = event_client.list_rules()
        if eventbridge:
            for rule in eventbridge['Rules']:
                if rule['Name'] == 'Trigger-Lambda-start-EC2-for-Patching':
                    """Adding the monthly CRON expression to the EventBridge Rule"""
                    lambda_rule = event_client.list_targets_by_rule(Rule=rule['Name'])
                    lambda_targets = lambda_rule['Targets']
                    lambda_id = None   
                    lambda_arn = None  
    
                    for element in lambda_targets:
                        lambda_id = element['Id']
                        lambda_arn = element['Arn']
    
                    response = event_client.put_rule(
                        Name=rule['Name'],
                        ScheduleExpression=cron_exp_start, 
                        State='ENABLED',
                        EventBusName='default'
                    ) 
                    print(f"On Eventbridge rule: '{rule['Name']}' editing the cron expression to be '{cron_exp_start}' for this month.")
    
                    """Adding the Target-Lambda 'StartEc2ForPatching' to be triggered """
                    response = event_client.put_targets(
                        Rule=rule['Name'],
                        EventBusName='default',
                        Targets=[
                            {
                            'Id': lambda_id,
                            'Arn': lambda_arn,
                            }
                        ]
                    )   
                    print(f"On Eventbridge rule: '{rule['Name']}' adding target lambda - '{lambda_arn}'.\n")
    
                elif rule['Name'] == 'Trigger-Lambda-stop-EC2-for-Patching':
                    """Adding the monthly CRON expression to the EventBridge Rule"""
                    lambda_rule = event_client.list_targets_by_rule(Rule=rule['Name'])
                    lambda_targets = lambda_rule['Targets']
                    lambda_id = None                
                    lambda_arn = None  
    
                    for element in lambda_targets:
                        lambda_id = element['Id']    
                        lambda_arn = element['Arn']                     

                    response = event_client.put_rule(
                        Name=rule['Name'],
                        ScheduleExpression=cron_exp_stop,
                        State='ENABLED',
                        EventBusName='default'
                    ) 
                    print(f"On Eventbridge rule: '{rule['Name']}' editing the cron expression to be '{cron_exp_stop}' for this month.")
                    
                    """Adding the Target-Lambda 'StopEC2FromPatching' to be triggered """
                    response = event_client.put_targets(
                        Rule=rule['Name'],
                        EventBusName='default',
                        Targets=[
                            {
                            'Id': lambda_id,
                            'Arn': lambda_arn,
                            }
                        ]
                    )
                    print(f"On Eventbridge rule: '{rule['Name']}' adding target lambda - '{lambda_arn}'.\n")
    except:
        print("Something went wrong!")