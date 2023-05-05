import boto3
import json

accounts = ["Your ACC IDs here"]
for account in accounts:
    account = f"{account}"
    print(f"\n   {account}")
    try:
        boto3.setup_default_session(profile_name=account)  

        config = boto3.client('config')
        s3 = boto3.client('s3')
        iam = boto3.client('iam')

        response_iam = iam.create_service_linked_role(
        AWSServiceName='config.amazonaws.com',)
        print(f"Role is created")

        response_s3_create = s3.create_bucket(
        Bucket=f"config-bucket-{account}",
        CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'},
        ObjectLockEnabledForBucket=False,
        ObjectOwnership='ObjectWriter')    #<- previous:'BucketOwnerEnforced'
        
        response_s3_policy = s3.put_bucket_policy(
        Bucket=f"config-bucket-{account}",
        Policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AWSConfigBucketPermissionsCheck",
                "Effect": "Allow",
                "Principal": {
                    "Service": "config.amazonaws.com"
                },
                "Action": "s3:GetBucketAcl",
                "Resource": f"arn:aws:s3:::config-bucket-{account}",
                "Condition": {
                    "StringEquals": {
                        "AWS:SourceAccount": f"{account}"
                    }
                }
            },
            {
                "Sid": "AWSConfigBucketExistenceCheck",
                "Effect": "Allow",
                "Principal": {
                    "Service": "config.amazonaws.com"
                },
                "Action": "s3:ListBucket",
                "Resource": f"arn:aws:s3:::config-bucket-{account}",
                "Condition": {
                    "StringEquals": {
                        "AWS:SourceAccount": f"{account}"
                    }
                }
            },
            {
                "Sid": "AWSConfigBucketDelivery",
                "Effect": "Allow",
                "Principal": {
                    "Service": "config.amazonaws.com"
                },
                "Action": "s3:PutObject",
                "Resource": f"arn:aws:s3:::config-bucket-{account}/AWSLogs/{account}/Config/*",
                "Condition": {
                    "StringEquals": {
                        "AWS:SourceAccount": f"{account}",
                        "s3:x-amz-acl": "bucket-owner-full-control"
                    }
                }
            }
            ]
            }),)
        print(f"S3 bucket is created")
        responsee_config_put_recorder = config.put_configuration_recorder(
            ConfigurationRecorder={
                'name': 'default',
                'roleARN': f'arn:aws:iam::{account}:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig',
                'recordingGroup': {
                    'allSupported': True,
                    'includeGlobalResourceTypes': True,}})

        response_config_channel = config.put_delivery_channel(
        DeliveryChannel={
            'name': 'default',
            's3BucketName': f"config-bucket-{account}",})

        response_config_start_recorder = config.start_configuration_recorder(
            ConfigurationRecorderName='default')

        print(f"Config is deployed and started")
    except:
        print(f"\n Something went wrong- {account}")
