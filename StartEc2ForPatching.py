import boto3


ACCOUNT = boto3.client('sts').get_caller_identity()['Account']

ec2_resource = boto3.resource('ec2')
ec2_client = boto3.client('ec2')
s3_resource = boto3.resource('s3')
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    """Start the Stopped instances with tag ApplyPatching = True,
    and change tag EC2UPTIME to TempEC2UPTIME"""
    instances = ec2_resource.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['stopped', 'running']}])
    buckets = [bucket.name for bucket in s3_resource.buckets.all()] 
    list_of_instances = ""
    list_of_tags = ""
    d_customer_config = None
    
    """Iterate through all of the instances, then through all of the tags to check if 'ApplyPatching' is set to 'True'"""
    for instance in instances:
        if instance.tags:   
            for tag in instance.tags:
                if tag['Key'] == "ApplyPatching":
                    if tag['Value'] == "True":  
                        for tag in instance.tags:
                            if tag['Key'] == "EC2UPTIME":
                                list_of_tags += f"{instance.id}+TEMPEC2UPTIME+{tag['Value']};"
                                key_to_delete = tag['Key']                      
                                value_to_use = tag['Value']                                       
                                ec2_client.create_tags(Resources=[instance.id], Tags=[{'Key':"TEMPEC2UPTIME",'Value':value_to_use}])
                                ec2_client.delete_tags(Resources=[instance.id], Tags=[{'Key':key_to_delete}])
                                print(f"On {instance.id} - Tag name:'{tag['Key']}' is changed to 'TEMPEC2UPTIME'.")
                                
                            elif tag['Key'] == "AutoScheduler":  
                                list_of_tags += f"{instance.id}+TEMPAutoScheduler+{tag['Value']};"
                                key_to_delete = tag['Key']     
                                value_to_use = tag['Value']                 
                                ec2_client.create_tags(Resources=[instance.id], Tags=[{'Key':"TEMPAutoScheduler",'Value':value_to_use}])
                                ec2_client.delete_tags(Resources=[instance.id], Tags=[{'Key':key_to_delete}])
                                print(f"On {instance.id} - Tag name:'{tag['Key']}' is changed to 'TEMPAutoScheduler'.")        
                                
        if instance.state['Name'] == "stopped":
            if instance.tags:
                for tag in instance.tags:
                    if tag['Key'] == "ApplyPatching":  
                        if tag['Value'] == "True":
                            """Start the Stopped EC2 instance with tag 'ApplyPatching'='True'"""  
                            list_of_instances += instance.id +':'  
                            print(f"Starting EC2 instance: '{instance.id}'")
                            ec2_client.start_instances(InstanceIds=[instance.id])
    
    """Create a file with the result from list_of_instances in S3 bucket - OBE"""
    """We overwrite the data every time, so we can guarantee that the data is the latest"""
    if len(list_of_tags) == 0:
        print(f"There are no instances with tag 'EC2UPTIME' or 'AutoScheduler'.")
    if len(list_of_instances) == 0:
        print(f"There are no instances with tag 'ApplyPatching'.")
    
    
    for bucket in buckets:
        if f"customer.config-{ACCOUNT}" in bucket:
            d_customer_config = bucket
            break
    
    object_instances = s3_resource.Object(d_customer_config, 'ForPatching_ListOfInstances/list_of_started_ec2.txt') 
    object_instances.put(Body=list_of_instances)
    
    object_tags = s3_resource.Object(d_customer_config, 'ForPatching_ListOfInstances/Tags.txt') 
    object_tags.put(Body=list_of_tags)
    return list_of_instances
