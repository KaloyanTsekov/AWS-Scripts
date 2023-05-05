import boto3

ACCOUNT = 'PUT your ORG. master ACC id here'
boto3.setup_default_session(profile_name=ACCOUNT)
org = boto3.client('organizations')
paginator = org.get_paginator('list_children')

token = ''
wehavetostop = False
total_accounts = []
counter = 0
while wehavetostop == False:
    if token == '':
        response_iterator = paginator.paginate(
        ParentId='<ORGID>', ###
        ChildType='ACCOUNT',
        PaginationConfig={
            'MaxItems': 100,
            'PageSize': 20,})
        for el in response_iterator:

            for id in el['Children']:
                total_accounts.append(id['Id'])
                counter += 1   
            if 'NextToken' in el:
                token = el['NextToken']
            else:
                wehavetostop = True
                break

    elif token != '':      
        response_iterator = paginator.paginate(
        ParentId='<ORGID>', ###
        ChildType='ACCOUNT',
        PaginationConfig={
            'MaxItems': 100,
            'PageSize': 20,
            'StartingToken':token})
        for el in response_iterator:
            for id in el['Children']:
                total_accounts.append(id['Id'])
                counter += 1
            if el['NextToken'] is not None:
                token = el['NextToken']
            else:
                wehavetostop = True
                break
print(total_accounts)
print(f"-------")
print(counter)

AdminRole = []

for account in total_accounts:
    account = f"{account}"
    print(f"\n   {account}")
    
    try:
        boto3.setup_default_session(profile_name=account)
        iam = boto3.client('iam')
        try:
            response = iam.get_role(
                RoleName='DAdmin'
                )
            print(response)
        except:
            print("DAdmin role is not presented")
            AdminRole.append(account)
    except:
        print(f"----Can't connect to {account}. Check if the account is in config.txt")

print(AdminRole)










#response = org.describe_organization()


#response = org.describe_organizational_unit(
#     OrganizationalUnitId='o-lpsxgmt9z7'
# )
# print(response)

# response = org.list_accounts(MaxResults=20)

# print(response)

# response = org.list_accounts(
# #         )
# # print(response)
# response = org.list_accounts(
#         )
# print(response)
# ntoken = ''
# while True:
    
#     if response['NextToken']:
#         ntoken = response['NextToken']
#         response = org.list_accounts(
#         NextToken=ntoken)
#     # elif response['NextToken'] == None:
#     #     response = org.list_accounts()   
#     else:
#         print("yes yes yes dom dom ")
#         response = org.list_accounts()
#         print(response)
#         break

# response = org.list_organizational_units_for_parent(
#     ParentId='ou-yu9k-glyw2i7c',)
# print(response)