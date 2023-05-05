import boto3

accounts = ["ACC IDs here"]
no_connection = ""
text = ""
all_poblems = []
counter = 0
for account in accounts:
    account = f"{account}"
    try:
        boto3.setup_default_session(profile_name=account)
        print(f"\n   {account}")
        ec2_client = boto3.client('ec2')
        all_groups = []
        security_groups_in_use = []
        """Get ALL security groups names"""
        security_groups_dict = ec2_client.describe_security_groups()
        security_groups = security_groups_dict['SecurityGroups']
        response = ec2_client.describe_security_group_rules()
        for rule in response['SecurityGroupRules']:
            for element in rule:
                if element == "CidrIpv4":
                    if rule["CidrIpv4"] in ["<IP range>", "<IP range>","<IP range>"]:
                        print(f"{rule['CidrIpv4']} --- {rule}\n")
                        counter += 1
                        result = f'{account} ? {rule["GroupId"]} ? {rule["SecurityGroupRuleId"]} ? {rule["FromPort"]} ? {rule["ToPort"]} ? {rule["CidrIpv4"]}\n'
                        text += result

    except Exception as ex:
        print(f"Cant connect to {account}, {ex}")
        no_connection += f'{account} ? '
print(counter)
with open('sg_report.txt', 'a') as file:
    file.write(text)
    file.write(no_connection)
