import boto3
import uuid
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    try:
        results = []
        secret_name = "patch_reporting"
        region_name = "eu-west-1"
        # Create a Secrets Manager client session
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=region_name)

        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
            # Use 'eval' to convert string-dict to dictionary
            ssm_as_dict = eval(get_secret_value_response["SecretString"])
        except ClientError as e:
            raise e

        arn_list = ssm_as_dict["ARN_LIST"].split(",")

        for arn in arn_list:
            arn.strip()
            client = boto3.client("sts")
            response = client.assume_role(
                RoleArn=arn, RoleSessionName="{}-s3".format(str(uuid.uuid4())[:5])
            )
            session = boto3.Session(
                aws_access_key_id=response["Credentials"]["AccessKeyId"],
                aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
                aws_session_token=response["Credentials"]["SessionToken"],
                region_name=region_name,
            )
            ec2_resource = session.resource('ec2')
            instances = ec2_resource.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['stopped', 'running']}])

            for ec2 in instances['Reservations']:
                for name in ec2['Instances']:
                    for el in ec2.describe_instances(InstanceIds=[name["InstanceId"]])["Reservations"]:
                        try:
                            for x in el["Instances"]:
                                result = f'{x["IamInstanceProfile"]["Arn"]} - {name["InstanceId"]}'
                                results.append(result)
                        except:
                            result = f'*** No Role is presented ***{name["InstanceId"]}'
                            results.append(result)
                            
    except:
        print(f"Something went wrong")