import boto3

account_names = ["Put your Acc IDs Here"]
text = ""
for account in account_names:
    session = boto3.Session(profile_name=account, region_name="eu-west-1")
    sts_session = session.client("sts")
    ec2_resource = session.resource('ec2')
    ec2_client = session.client('ec2')
    iam_client = session.client('iam')

    account_id = sts_session.get_caller_identity()["Account"]
    instances = ec2_resource.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['stopped', 'running']}])
    print(account_id)

    for ec2 in instances:


        for el in ec2_client.describe_instances(InstanceIds=[ec2.id])["Reservations"]:
            
            name = "NoName"
            application_name = "NoName"
            iam_role_arn = "NoName"
            for x in el["Instances"]:
                if ec2.tags:
                    for tag in x['Tags']:
                        if tag['Key'] == "Name":
                            name = tag['Value']
                        if tag['Key'] == "ApplicationNumber":
                            application_name = tag['Value']
            try:
                result = f'{account_id} ? {name} ? {x["InstanceId"]} ? {x["PrivateIpAddress"]} ? {application_name}\n'
                text += result
 
            except:
                name = 'NoName'
                iam_role_arn = "NoName"
                application_name = "NoName"
                result = f'{account_id} ? {name} ? {x["InstanceId"]} ? {x["PrivateIpAddress"]} ? {application_name}\n'
                text += result

with open('ec2_instance_role.txt', 'a') as file:
    file.write(text)      