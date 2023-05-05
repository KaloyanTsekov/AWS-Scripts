import boto3


ACCOUNT = boto3.client('sts').get_caller_identity()['Account']
s3_resource = boto3.resource('s3')
ec2_client = boto3.client('ec2')

def lambda_handler(event, context):
    d_customer_config = None
    is_true_tags = True
    is_true_ec2 = True
    
    buckets = [bucket.name for bucket in s3_resource.buckets.all()]
    for bucket in buckets:
        if f"customer.config-{ACCOUNT}" in bucket:
            d_customer_config = bucket
            break
    
    """List the data in list_of_started_ec2.txt """
    """Stop the previously started EC2 instances.""" 
    new_data_ec2 = None
    new_data_tags = None
    bucket = s3_resource.Bucket(d_customer_config)
    
    for obj in bucket.objects.all():
        if obj.key == 'ForPatching_ListOfInstances/list_of_started_ec2.txt':  
            body = obj.get()['Body'].read() 
            new_data_ec2 = body
            if not len(new_data_ec2) >= 1:
                is_true_tags = False
                print(f"No EC2 instances to stop.")
            break
    if new_data_ec2 == None:   
        is_true_tags = False
        print("File 'List_of_started_ec2.txt' does not exist.")
    
    if is_true_tags == True:
        try:
            new_data_ec2 = new_data_ec2.decode('utf8') 
            new_data_ec2 = new_data_ec2[:-1].split(":") 
            for ec2 in new_data_ec2:
                try:
                    ec2_client.stop_instances(InstanceIds=[ec2])
                    print(f"{ec2} will be stopped.")
                except:
                    print(f"{ec2} is not available - check if it's terminated")
        except:
            print("Something went wrong - EC2.")
    
    
    """List the data in Tags.txt """
    """Change the tag name with the original names."""
    for obj in bucket.objects.all():
        if obj.key == 'ForPatching_ListOfInstances/Tags.txt':  # ForPatchingListOfInstances/Tags.txt
            body = obj.get()['Body'].read()
            new_data_tags = body
            
            if not len(new_data_tags) >= 1:
                is_true_ec2 = False
                print(f"No EC2 Tags to be changed.")
            break
    if new_data_tags == None:   
        is_true_ec2 = False
        print("File 'Tags.txt' does not exist.")
    
    if is_true_ec2 == True:
        try:
            new_data_tags = new_data_tags.decode('utf8')
            new_data_tags = new_data_tags[:-1].split(";")
            for element in new_data_tags: 
                try:
                    id, key_to_delete, value_to_use = element.split("+")
 
                    """InstanceID, TagName, TagValue """
                    if key_to_delete == "TEMPEC2UPTIME":
                        ec2_client.create_tags(Resources=[id], Tags=[{'Key':"EC2UPTIME",'Value':value_to_use}])
                        ec2_client.delete_tags(Resources=[id], Tags=[{'Key':key_to_delete}])
                        print(f"On {id} - Tag name '{key_to_delete}' is changed to 'EC2UPTIME'.")
                    if key_to_delete == "TEMPAutoScheduler":
                        ec2_client.create_tags(Resources=[id], Tags=[{'Key':"AutoScheduler",'Value':value_to_use}])
                        ec2_client.delete_tags(Resources=[id], Tags=[{'Key':key_to_delete}])
                        print(f"On {id} - Tag name '{key_to_delete}' is changed to 'AutoScheduler'.")
                except:
                    print(f"EC2 instance - '{id}' is missing")
        except:
            print("Something went wrong - Tags.")
