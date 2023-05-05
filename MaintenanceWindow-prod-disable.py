import boto3

#True to enable, False to disable MW
enabled = True
name = 'RunPatchBaseline-PROD'
#name = "RunPatchBaseline-Prod"
accounts = ["Put Your ACC ids here"]
no_access_accounts = []
failed_updаte = []
result_detailed = []
for account_id in accounts:
    # Ensure that the account is reachable
    try:
        # Establish session
        boto3.setup_default_session(profile_name=account_id)
        ssm_client = boto3.client("ssm")
        described_maintenance_windows = ssm_client.describe_maintenance_windows()
        maintenance_windows = described_maintenance_windows["WindowIdentities"]
        # If there is no MW presented, it will throw Exception
        if maintenance_windows: 
            # Loop through every MW if count of MV > 1:
            for window in maintenance_windows:
                # Add each window info in result_detailed list
                current_state = f"---Current state:{window}"
                result_detailed.append(current_state)
                print(current_state)
                
                if window['Name'] == name:
                    try:
                        #Enable/Disable MW based on "enabled" variable
                        update_mw = ssm_client.update_maintenance_window(WindowId=window['WindowId'], Enabled=enabled)
                        # Add the actual window info in result_detailed list
                        desired_state = f"---Desired state: {update_mw}"
                        result_detailed.append(desired_state)
                        print(desired_state)
                        # Add the actual window state in a result.txt file
                        with open('ftm-mw-prod-state/result.txt', 'a') as file:    
                            file.write(f"AccountId {account_id}:\nID:{window['WindowId']}, Name:{window['Name']}, State:{window['Enabled']} -> changed to: {update_mw['Enabled']}\n\n")
                    except:
                        # Add the Id of every account with failed MW.
                        print(f"Failed to update MW on account: {account_id}")
                        failed_updаte.append(account_id)
                else:
                    try:
                        # Add all IDs and NAMEs of each MW with different than expected name so we can guarantee all Prod MW are checked.
                        with open('ftm-mw-prod-state/mw_with_diff_names.txt', 'a') as file:    
                            file.write(f"AccountId {account_id}:\nID:{window['WindowId']}, Name:{window['Name']}, State:{window['Enabled']}\n\n")
                    except:
                        # Just to ensure that the script won't stop due to an error.
                        print(f"---Different MW name in account: {account_id}") 
        # Add detailed MW information for evey MW that we want. 
        with open('ftm-mw-prod-state/result_detailed.txt', 'a') as file:    
            file.write(f"AccountId {account_id}:\n{result_detailed}\n\n")
        # clear the list at the end of every loop to avoid double data
        result_detailed = []
    except:
        # Add all access denied accounts to a list
        print(f"--- Can't Connect to {account_id} ---")
        no_access_accounts.append(account_id)

# Add all access denied accounts to a no_access_accounts.txt file
with open('ftm-mw-prod-state/no_access_accounts.txt', 'a') as file:    
    file.write(f"Accounts:\n{no_access_accounts}")
 