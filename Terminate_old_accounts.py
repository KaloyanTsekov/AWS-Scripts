import boto3

accounts = ["ACC ID here"]
for account_id in accounts:
    ACCOUNT = account_id
    boto3.setup_default_session(profile_name=ACCOUNT)

    print(f"We are going to delete account {ACCOUNT}\nAre you sure?\nType 'y' to confirm")
    confirmation = input()
    if not confirmation == "y":
        exit()

    #check if backups to the backupaccount are available   
    #check for ASG
    #check for Load Balancer
    

    #Release IPs
    """Terminate all stopped, running EC2"""
    ec2_resource = boto3.resource('ec2')
    ec2_client = boto3.client('ec2')
    instances = ec2_resource.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}])
    for instance in instances:
        ec2_client.terminate_instances(InstanceIds=[instance.id])
    instances = ec2_resource.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['stopped']}])
    for instance in instances:
        ec2_client.terminate_instances(InstanceIds=[instance.id])

    """Delete all non default Security Groups - WORKING"""
    all_groups = []
    security_groups_in_use = []
    """Get ALL security groups names"""
    security_groups_dict = ec2_client.describe_security_groups()
    security_groups = security_groups_dict['SecurityGroups']
    for groupobj in security_groups:
        if groupobj['GroupName'] == 'default':
            security_groups_in_use.append(groupobj['GroupId'])
        all_groups.append(groupobj['GroupId']) 
    for group in all_groups:
        try:       
            response = ec2_client.delete_security_group(GroupId=group)
            print(f"This group has been deleted {group}")
        except:
            print(f"Default group cannot be deleted by a user")

    """Snapshot DELETION - Working"""
    response = ec2_resource.snapshots.all()
    for snapshot in response:
        try:
            if snapshot.owner_id == ACCOUNT:
                snap_to_del = f"{snapshot.id}"
                ec2_client.delete_snapshot(SnapshotId=snap_to_del)
                print(f"Deleting Snapshot {snap_to_del}")
        except:
            print(f"We skipped this snapshot {snapshot.id}")

    #check for RDS

    """Empty S3 buckets Refactor it with function - Working"""
    s3_resource = boto3.resource('s3')
    buckets = [bucket.name for bucket in s3_resource.buckets.all()]

    for bucket in buckets:
        if "prod.obe" in bucket:
            print(f"prod.obe -> {bucket} ")
            my_bucket = s3_resource.Bucket(bucket)
            bucket_versioning = s3_resource.BucketVersioning(bucket)
            if bucket_versioning.status == 'Enabled':
                my_bucket.object_versions.delete()
            else:
                my_bucket.objects.all().delete()
        elif "customer.config" in bucket:
            print(f"customer.config -> {bucket} ")
            my_bucket = s3_resource.Bucket(bucket)
            bucket_versioning = s3_resource.BucketVersioning(bucket)
            if bucket_versioning.status == 'Enabled':
                my_bucket.object_versions.delete()
            else:
                my_bucket.objects.all().delete()
        elif "ftm-aws-config-bucket" in bucket:
            print(f"ftm-aws-config-bucket -> {bucket} ")
            my_bucket = s3_resource.Bucket(bucket)
            bucket_versioning = s3_resource.BucketVersioning(bucket)
            if bucket_versioning.status == 'Enabled':
                my_bucket.object_versions.delete()
            else:
                my_bucket.objects.all().delete()

    """" Check if VPC TAG 'x-chkp-vpn' is available - WORKING"""
    vpcs = ec2_client.describe_vpcs()
    is_true = False
    for vpc in vpcs['Vpcs']:
        print(f"\nImportant!\nOpen IPAM and free up this IP range {vpc['CidrBlock']}\n")
        if 'Tags' in vpc:
            for tag in vpc['Tags']:  
                if tag['Value'] == 'x-chkp-vpn': 
                    print(f"Bad news!'x-chkp-vpn' tag is presented. Check the guide")
                    is_true = True
    if is_true == False:
        print(f"Good news! Tag 'x-chkp-vpn' is NOT presented!")

    """Deleting CloudFormation STACKs - WORKING"""
    cfn_resource = boto3.resource('cloudformation')
    cfn_client = boto3.client('cloudformation')
    stacks = [stack.name for stack in cfn_resource.stacks.all()]
    for stack in stacks:
        if stack == "Master" or stack == "master":
            cfn_client.update_termination_protection(
            EnableTerminationProtection=False,
            StackName=stack)
            response = cfn_client.delete_stack(StackName=stack),
            print(f"Deleting {stack}")

        elif "spoke-vpc" in stack:
            try:
                cfn_client.update_termination_protection(
                EnableTerminationProtection=False,
                StackName=stack) 
                response = cfn_client.delete_stack(StackName=stack),
                print(f"Deleting {stack}")
            except:
                print(f"_________CANNOT Delete {stack}____________")

        elif "cloudckr" in stack or "cloudckr" in stack:
            cfn_client.update_termination_protection(
            EnableTerminationProtection=False,
            StackName=stack) 
            response = cfn_client.delete_stack(StackName=stack),
            print(f"Deleting {stack}")
        elif "mid-server-cross-account" in stack:
            cfn_client.update_termination_protection(
            EnableTerminationProtection=False,
            StackName=stack) 
            response = cfn_client.delete_stack(StackName=stack),
            print(f"Deleting {stack}")
        elif "AWS-Audit-Cross" in stack or "AWS-Cross-" in stack:
            cfn_client.update_termination_protection(
            EnableTerminationProtection=False,
            StackName=stack) 
            response = cfn_client.delete_stack(StackName=stack),
            print(f"Deleting {stack}")
        elif "vpn-by-tag" in stack:
            cfn_client.update_termination_protection(
            EnableTerminationProtection=False,
            StackName=stack)
            response = cfn_client.delete_stack(StackName=stack),
            print(f"Deleting {stack}")

    """Delete DynamoDB tables - WORKING"""
    dynamodb_resource = boto3.resource('dynamodb')
    all_tables = dynamodb_resource.tables.all()
    for table in all_tables:
        try:
            table.delete()
            print(f"Deleting DynamoDB Table {table}")
        except:
            print(f"Cannot delete DynamoDB Table {table}")

    elb_client = boto3.client('elb')

    vpcs = ec2_client.describe_vpcs()
    vpcgw = ec2_resource.internet_gateways.all()
    subnets = ec2_resource.subnets.all()
    route_tables = ec2_resource.route_tables.all()
    peering_connections = ec2_resource.vpc_peering_connections.all()
    nacls = ec2_resource.network_acls.all()
    endpoints = ec2_client.describe_vpc_endpoints()
    vpcs = ec2_resource.vpcs.all()
    tgwattachments = ec2_client.describe_transit_gateway_vpc_attachments()


    for endpoint in endpoints['VpcEndpoints']:
        response = ec2_client.delete_vpc_endpoints(VpcEndpointIds=[endpoint['VpcEndpointId'],])


    for tgwatt in tgwattachments['TransitGatewayVpcAttachments']:
        tgwattid = tgwatt['TransitGatewayAttachmentId']
        print(f"Deleting TGW attachment: {tgwattid}")
        response = ec2_client.delete_transit_gateway_vpc_attachment(
            TransitGatewayAttachmentId=tgwattid)


    """must be implemented"""
    # for peering_connection in peering_connections:
    #     print(peering_connection.id)   # -> pcx-07c7c40d58f

    """Deleting Route Tables"""
    for route_table in route_tables:       
        for route in route_table.routes:       
            if route.origin == "CreateRoute":
                ec2_client.delete_route(
                    RouteTableId=route.route_table_id,
                    DestinationCidrBlock=route.destination_cidr_block,)
            if not route_table.associations:
                ec2_client.delete_route_table(RouteTableId=route_table.id)
        for rtbassociation in route_table.associations: 
            if not rtbassociation.main: 
                try:
                    ec2_client.disassociate_route_table(
                    AssociationId=rtbassociation.id 
                    )
                    ec2_client.delete_route_table(
                    RouteTableId=route_table.id
                    )
                    print(f"Deleting {route_table.id}")
                except:
                    print(f"The routeTable {route_table.id} has dependencies and cannot be deleted.")  
            else:
                print(f"{rtbassociation.id} is Main Route Table association and cannot be deleted")

    """Deleting NACLs"""
    for nacl in nacls: 
        if nacl.is_default:
            print(f"Default NACL - {nacl.id} cannot be deleted")
        else:
            try:
                nacl.delete()
                print(f"Deleting NACL {nacl.id}")  #-> acl-05ee6a151d
            except:
                print(f"Cannot delete NACL {nacl.id}")  #-> acl-05ee6a151d

    """Deleting SUBNETS"""
    for subnet in subnets:
        for ni in subnet.network_interfaces.all():
            try:
                ni.delete()
                print(f"Deleting Network Interface: {ni.id}") #-> eni-03bd78a582
            except:
                print(f"Cannot delete {ni}")
        # print("---waiting 10 sec to refresh the ENIs")
        # time.sleep(10)
        try:
            subnet.delete()
            print(f"Deleting Subnet {subnet.id}")  #-> subnet-07da0d436c
        except:
            print(f"Cannot delete {subnet.id}")
                
    """must be implemented"""
    # vpcgw = ec2_resource.internet_gateways.all()
    # print(vpcs)

    vpc = [x.id for x in vpcs]  #If no VPC available it returns empty []
    for gw in vpcgw:
        try:
            gw.detach_from_vpc(
            DryRun=False,
            VpcId=vpc[0]
            )
            print(f"Detaching Internet Gateway: {gw.id}")
        except:
            print("No Internet Gateway attached to VPC")
        try:
            print(f"Deleting Internet Gateway: {gw.id}")
            gw.delete()
        except:
            print("No Internet Gateway to delete")



    """Deleting VPC"""
    for vpc in vpcs:
        try:
            vpc.delete()
            print(f"Deleting VPC {vpc.id}")
        except:
            print(f"Cannot delete VPC {vpc.id}")
                    