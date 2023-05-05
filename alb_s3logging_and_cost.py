import boto3

#Cost Usage period. The start date is inclusive. For example, if start is 2017-01-01, Amazon Web Services retrieves cost and usage data starting at 2017-01-01 up to the end date. The start date must be equal to or no later than the current date to avoid a validation error.
#The end date is exclusive. For example, if end is 2017-05-01, Amazon Web Services retrieves cost and usage data from the start date up to, but NOT including, 2017-05-01
start_date = "2023-04-01"
end_date = "2023-05-01"

result = ""
accounts = ["Account IDs here"]

#Establish sesion:
for account in accounts:
    try:
        session = boto3.Session(profile_name=account, region_name="eu-west-1")
        #Get AWS account Id:      
        sts_session = session.client("sts")
        account_id = sts_session.get_caller_identity()["Account"]
        print(account_id)

        #Set boto3 proxy
        s3_resource = session.resource('s3')
        s3_client = session.client('s3')
        elbv2_client = session.client('elbv2')
        ce_client = session.client('ce')

        #get all bucket names
        buckets = [bucket.name for bucket in s3_resource.buckets.all()]

        #Loop through all ALBs:
        elbv2_response = elbv2_client.describe_load_balancers()
        for lb in elbv2_response["LoadBalancers"]:
            if lb["Type"] == 'application':
                s3bucket = "" 
                s3prefix = ""
                monitoring_is_enabled = ""
                
                #Get ALB attrs:
                elbv2_attrs_response = elbv2_client.describe_load_balancer_attributes(LoadBalancerArn=lb["LoadBalancerArn"])
                # The return of elbv2_attrs_response["Attributes"]:
                # [{'Key': 'access_logs.s3.enabled', 'Value': 'false'}, {'Key': 'access_logs.s3.bucket', 'Value': 'wvtemps3'}, {'Key': 'access_logs.s3.prefix', 'Value': ''}]
                for attr in elbv2_attrs_response["Attributes"]:
                    if attr["Key"] == "access_logs.s3.enabled":
                        monitoring_is_enabled = attr["Value"]
                    elif attr["Key"] == "access_logs.s3.bucket":
                        s3bucket = attr["Value"]
                    elif attr["Key"] == "access_logs.s3.prefix":
                        if len(attr["Value"]) >= 1:
                            s3prefix = attr["Value"]

                #Check if the S3 bucket that collects data from the ALB has Lifecycle policy:
                s3_full_name = s3prefix+s3bucket  
                bucket_rules = ""
                try:
                    if buckets:
                        for bucket in buckets:
                            if bucket == s3_full_name:  
                                response = s3_client.get_bucket_lifecycle_configuration(
                                Bucket=s3_full_name,) 
                                # for x in response["Rules"]:
                                #     bucket_rules += f'{x["ID"]} | '
                                bucket_rules += ' | '.join([x['ID'] for x in response['Rules']])
                except Exception as ex:
                    print(f" ### Bucket Error: {account_id}: {ex}")

                #Get ALB Tag name, to pass it to AWS CostManagement service to get monthly cost for the ALB.
                tag_name = None
                elb_tags = elbv2_client.describe_tags(ResourceArns=[lb["LoadBalancerArn"]])
                if elb_tags:
                    for tag in elb_tags["TagDescriptions"]:
                        if tag["Tags"]:
                            for _ in tag["Tags"]:
                                if _["Key"] == "Name":
                                    tag_name = _["Value"]

                #Get S3 bucket's Tag name, used by ALB to store data in it, to pass it to AWS CostManagement service to get the monthly cost.
                s3_tag_name = None
                try:
                    s3_tags = s3_client.get_bucket_tagging(Bucket=s3bucket)
                    if s3_tags:
                        for tag in s3_tags["TagSet"]:
                            if tag["Key"] == "Name":
                                s3_tag_name = tag["Value"]
                except Exception as ex:
                    print("No bucket")

                #Get the montly cost of PutObject API call made on the S3 bucket, used by ALB to store data in it, if the Name tag exists.
                s3_PutObject_cost = None
                try:
                    ce_response_s3_PutObject = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date,
                        'End': end_date
                    },
                    Granularity='MONTHLY', 
                    Filter={
                        'And': [
                            {'Dimensions': {
                                'Key': 'OPERATION',
                                'Values': ['PutObject'],
                            }},
                            {'Tags': {
                                'Key': 'Name',
                                'Values': [s3_tag_name,],
                                },}
                        ]
                    },
                    Metrics=['AmortizedCost',]
                    )

                    s3_PutObject_cost = f'{ce_response_s3_PutObject["ResultsByTime"][0]["Total"]["AmortizedCost"]["Amount"][0:6]}'
    
                except Exception as ex:
                    alb_cost = "Not available"
                    print(f" ### Cost not available: {account_id}: {ex}")

                #Get the montly cost the S3 bucket, used by ALB to store data in it, if the Name tag exists.
                s3_cost = None
                try:
                    ce_response_s3 = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date,
                        'End': end_date
                    },
                    Granularity='MONTHLY', 
                    Filter={
                        'And': [
                            {'Dimensions': {
                                'Key': 'SERVICE',
                                'Values': ['Amazon Simple Storage Service'],
                            }},
                            {'Tags': {
                                'Key': 'Name',
                                'Values': [s3_tag_name],
                                },}
                        ]
                    }, 
                    Metrics=['AmortizedCost',]
                    )
                    s3_cost = f'{ce_response_s3["ResultsByTime"][0]["Total"]["AmortizedCost"]["Amount"][0:6]}'
    
                except Exception as ex:
                    alb_cost = "Not available"
                    print(f" ### Cost not available: {account_id}: {ex}")

                #Get the montly cost for each ALB if the Name tag exists.
                alb_cost = None
                try:
                    ce_response = ce_client.get_cost_and_usage(
                    TimePeriod={
                        'Start': start_date,
                        'End': end_date
                    },
                    Granularity='MONTHLY', 
                    Filter={
                        'Tags': {
                            'Key': 'Name',
                            'Values': [tag_name,], 
                        },
                    },
                    Metrics=['AmortizedCost',]
                    )
                    alb_cost = f'{ce_response["ResultsByTime"][0]["Total"]["AmortizedCost"]["Amount"][0:5]}'
                    
    
                except Exception as ex:
                    alb_cost = "Not available"
                    print(f" ### Cost not available: {account_id}: {ex}")

                result += f'{account_id} ? {lb["LoadBalancerName"]} ? {alb_cost} ? {lb["LoadBalancerArn"]} ? {monitoring_is_enabled} ? {s3_full_name} ? {s3_cost} ? {s3_PutObject_cost} ? {bucket_rules} \n' 

                print(f'--- {lb["LoadBalancerName"]}')
    except Exception as ex:
        print(f" ### Can't access: {account_id}: {ex}")

with open('alb.txt', 'a') as file:
    file.write(result) 
