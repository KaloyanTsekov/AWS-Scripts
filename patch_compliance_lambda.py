import boto3
import pandas as pd
from datetime import datetime
import json
import os
import uuid
import time
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

time_now = datetime.now()
today = time_now.strftime("%Y-%m-%d")


def lambda_handler(event, context):
    try:
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

        # Credentials of the user in the master account
        AWS_MASTER_USER_KEY = ssm_as_dict["AWS_MASTER_USER_KEY"]
        AWS_MASTER_USER_SECRET = ssm_as_dict["AWS_MASTER_USER_SECRET"]
        AWS_REGION = ssm_as_dict["AWS_REGION"]

        # S3 Bucket name that will store the .csv file.
        AWS_S3_BUCKET_NAME = ssm_as_dict["AWS_S3_BUCKET_NAME"]

        # Name of the generated .csv file.
        EXCEL_NAME = f"FLM-{today}.csv"

        # The full path to the file that will be uploaded to S3 and attached to the email.
        ATTACHMENT = f"/tmp/FLM-{today}.csv"

        # Email details.
        SENDER = ssm_as_dict["SENDER"]
        RECIPIENT = ssm_as_dict["RECIPIENT"]
        RECIPIENT_CC = ssm_as_dict["RECIPIENT_CC"]
        RECIPIENT_CC2 = ssm_as_dict["RECIPIENT_CC2"]
        RECIPIENT_CHM = ssm_as_dict["RECIPIENT_CHM"]
        SUBJECT = f"Patch Compliance report: {today}"
        BODY_TEXT = "Hello,\n\nHere it comes the latest patch compliance report.\nThis is just FYI, no action required. Please see the attached .csv file.\nIf you have any comments/concerns do not hesitate to contact us.\n\nRegards,\nAWS CloudOps Team"
        CHARSET = ssm_as_dict["CHARSET"]

        all_ec2 = []
        all_patched_ec2 = []
        no_maintenance_window_accounts = []
        empty_accounts = []
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
                region_name="eu-west-1",
            )

            iam = session.client("iam")
            account_alias = None
            paginator = iam.get_paginator("list_account_aliases")
            for alias in paginator.paginate():
                account_alias = alias["AccountAliases"]

            sts_session = session.client("sts")
            account_id = sts_session.get_caller_identity()["Account"]
            print(account_id)

            ec2_resource = session.resource("ec2")
            ec2_client = session.client("ec2")
            ssm_client = session.client("ssm")
            event_client = session.client("events")
            described_maintenance_windows = ssm_client.describe_maintenance_windows()
            maintenance_windows = described_maintenance_windows["WindowIdentities"]

            if maintenance_windows:
                for window in maintenance_windows:
                    try:
                        window_executions = (
                            ssm_client.describe_maintenance_window_executions(
                                WindowId=window["WindowId"],
                            )
                        )
                        window_id = window_executions["WindowExecutions"][0]["WindowId"]

                        window_execuction = ssm_client.get_maintenance_window_execution(
                            WindowExecutionId=window_executions["WindowExecutions"][0][
                                "WindowExecutionId"
                            ]
                        )

                        window_execution_id = window_execuction["WindowExecutionId"]
                        execution_task_id_as_list = window_execuction["TaskIds"]

                        for execution_task_id in execution_task_id_as_list:
                            print(f"{execution_task_id}")

                            task_invocation = ssm_client.describe_maintenance_window_execution_task_invocations(
                                WindowExecutionId=window_execution_id,
                                TaskId=execution_task_id,
                            )

                            task_invocation_id = task_invocation[
                                "WindowExecutionTaskInvocationIdentities"
                            ]

                            for win_exec_task_invocation_id in task_invocation_id:

                                win_exec_params = win_exec_task_invocation_id[
                                    "Parameters"
                                ]
                                win_exec_params_as_dict = json.loads(win_exec_params)
                                patch_groups = win_exec_params_as_dict["targets"]
                                for group in patch_groups:
                                    group_values = group["targetValues"]
                                    for group_value in group_values:
                                        instancespatchgroup = ssm_client.describe_instance_patch_states_for_patch_group(
                                            PatchGroup=group_value,
                                        )
                                        all_instances = instancespatchgroup[
                                            "InstancePatchStates"
                                        ]
                                        for ec2 in all_instances:
                                            additional_ec2_info = {}
                                            if (
                                                not ec2["InstanceId"]
                                                in additional_ec2_info
                                            ):
                                                additional_ec2_info[
                                                    ec2["InstanceId"]
                                                ] = None
                                            try:
                                                list_compliance = (
                                                    ssm_client.list_resource_compliance_summaries()
                                                )
                                                is_compliant = None
                                                for element in list_compliance[
                                                    "ResourceComplianceSummaryItems"
                                                ]:
                                                    if (
                                                        element["ComplianceType"]
                                                        == "Patch"
                                                    ):
                                                        if (
                                                            element["ResourceId"]
                                                            == ec2["InstanceId"]
                                                        ):
                                                            is_compliant = element[
                                                                "Status"
                                                            ]

                                                last_updated = ec2[
                                                    "OperationEndTime"
                                                ].date()

                                                ssm_instances = ssm_client.describe_instance_information(
                                                    InstanceInformationFilterList=[
                                                        {
                                                            "key": "InstanceIds",
                                                            "valueSet": [
                                                                ec2["InstanceId"]
                                                            ],
                                                        },
                                                    ]
                                                )
                                                platform_type = None
                                                for element in ssm_instances[
                                                    "InstanceInformationList"
                                                ]:
                                                    platform_type = element[
                                                        "PlatformName"
                                                    ]
                                                ec2_info = []
                                                ec2_info.append(ec2["InstanceId"])
                                                ec2_info.append(ec2["BaselineId"])
                                                ec2_info.append(ec2["InstalledCount"])
                                                ec2_info.append(ec2["MissingCount"])
                                                ec2_info.append(ec2["FailedCount"])
                                                ec2_info.append(last_updated)
                                                ec2_info.append(is_compliant)
                                                ec2_info.append(platform_type)

                                                additional_ec2_info[
                                                    ec2["InstanceId"]
                                                ] = ec2_info

                                                command_invocation = ssm_client.get_command_invocation(
                                                    CommandId=win_exec_task_invocation_id[
                                                        "ExecutionId"
                                                    ],
                                                    InstanceId=ec2["InstanceId"],
                                                )
                                                if (
                                                    command_invocation["StatusDetails"]
                                                    == "Success"
                                                ):
                                                    all_patched_ec2.append(
                                                        additional_ec2_info[
                                                            ec2["InstanceId"]
                                                        ]
                                                    )
                                            except:
                                                print(
                                                    f"EC2 instance: {ec2['InstanceId']} is most probably terminated"
                                                )
                    except:
                        print(f"WindowID - {window['WindowId']} is on disabled state")
                        continue
            else:
                no_maintenance_window_accounts.append(account_id)
                print("No maintenance window presented")
                continue
            all_instances = ec2_resource.instances.filter(
                Filters=[
                    {"Name": "instance-state-name", "Values": ["stopped", "running"]}
                ]
            )

            len_instances = 0

            if account_alias:
                account_alias_for_ec2 = account_alias[0]
            else:
                account_alias_for_ec2 = " - "

            for instance in all_instances:
                len_instances += 1

                ec2_apply_patching = False
                os_name_bool = False
                os_name = " - "
                Launch_time = " - "
                patched = "No"
                patch_group = " - "
                baseline_id = " - "
                installed_count = " - "
                missing_count = " - "
                failed_count = " - "
                last_update = " - "
                is_compliant = " - "
                platform_type = " - "

                application = " - "
                application_category = " - "
                application_number = " - "
                business_criticality = " - "
                business_owner = " - "
                business_unit = " - "
                classification = " - "
                environment = " - "
                organization = " - "
                owner = " - "
                project = " - "
                security = " - "
                service_type = " - "
                technical_owner = " - "
                wbs = " - "
                supplier = " - "

                ec2 = {
                    "account_id": account_id,
                    "acc_alias": account_alias_for_ec2,
                    "name": " - ",
                    "ec2": instance.id,
                    "ec2_apply_patching": " - ",
                    "patch_group": patch_group,
                    "os_name": os_name,
                    "ec2_state": instance.state["Name"],
                    "launch_date": instance.launch_time.date(),
                    "patched": patched,
                    "baseline_id": baseline_id,
                    "installed_count": installed_count,
                    "missing_count": missing_count,
                    "failed_count": failed_count,
                    "last_update": last_update,
                    "is_compliant": is_compliant,
                    "platform_type": platform_type,
                    "application": application,
                    "application_category": application_category,
                    "application_number": application_number,
                    "business_criticality": business_criticality,
                    "business_owner": business_owner,
                    "business_unit": business_unit,
                    "classification": classification,
                    "environment": environment,
                    "organization": organization,
                    "owner": owner,
                    "project": project,
                    "security": security,
                    "service_type": service_type,
                    "technical_owner": technical_owner,
                    "wbs": wbs,
                    "supplier": supplier,
                }

                if instance.tags:
                    # tag == {'Key': 'ApplyPatching', 'Value': 'true'}:
                    for tag in instance.tags:
                        if tag["Key"] == "ApplyPatching":
                            if tag["Value"] == "true":
                                ec2_apply_patching = True
                                ec2[
                                    "ec2_apply_patching"
                                ] = "true "  # tag["Value"].lower() - "true " is used because true is reserved in pandas and display the value as TRUE
                            else:
                                ec2["ec2_apply_patching"] = tag["Value"]

                        elif tag["Key"] == "Name":
                            name = tag["Value"]
                            ec2["name"] = name

                        elif tag["Key"] == "OSName":
                            os_name_bool = True
                            os_name = tag["Value"]
                            ec2["os_name"] = os_name

                        elif tag["Key"] == "Patch Group":
                            patch_group = tag["Value"]
                            ec2["patch_group"] = tag["Value"]

                        elif tag["Key"] == "Application":
                            application = tag["Value"]
                            ec2["application"] = tag["Value"]

                        elif tag["Key"] == "ApplicationCategory":
                            application_category = tag["Value"]
                            ec2["application_category"] = tag["Value"]

                        elif tag["Key"] == "ApplicationNumber":
                            application_number = tag["Value"]
                            ec2["application_number"] = tag["Value"]

                        elif tag["Key"] == "BusinessCriticality":
                            business_criticality = tag["Value"]
                            ec2["business_criticality"] = tag["Value"]

                        elif tag["Key"] == "BusinessOwner":
                            business_owner = tag["Value"]
                            ec2["business_owner"] = tag["Value"]

                        elif tag["Key"] == "BusinessUnit":
                            business_unit = tag["Value"]
                            ec2["business_unit"] = tag["Value"]

                        elif tag["Key"] == "Classification":
                            classification = tag["Value"]
                            ec2["classification"] = tag["Value"]

                        elif tag["Key"] == "Environment":
                            environment = tag["Value"]
                            ec2["environment"] = tag["Value"]

                        elif tag["Key"] == "Organization":
                            organization = tag["Value"]
                            ec2["organization"] = tag["Value"]

                        elif tag["Key"] == "Owner":
                            owner = tag["Value"]
                            ec2["owner"] = tag["Value"]

                        elif tag["Key"] == "Project":
                            project = tag["Value"]
                            ec2["project"] = tag["Value"]

                        elif tag["Key"] == "Security":
                            security = tag["Value"]
                            ec2["security"] = tag["Value"]

                        elif tag["Key"] == "ServiceType":
                            service_type = tag["Value"]
                            ec2["service_type"] = tag["Value"]

                        elif tag["Key"] == "TechnicalOwner":
                            technical_owner = tag["Value"]
                            ec2["technical_owner"] = tag["Value"]

                        elif tag["Key"] == "WBS":
                            wbs = tag["Value"]
                            ec2["wbs"] = tag["Value"]

                        elif tag["Key"] == "Supplier":
                            supplier = tag["Value"]
                            ec2["supplier"] = tag["Value"]

                for patched_ec2 in all_patched_ec2:
                    if instance.id == patched_ec2[0]:
                        ec2["patched"] = "Yes"
                        ec2["baseline_id"] = patched_ec2[1]
                        ec2["installed_count"] = patched_ec2[2]
                        ec2["missing_count"] = patched_ec2[3]
                        ec2["failed_count"] = patched_ec2[4]
                        ec2["last_update"] = patched_ec2[5]
                        ec2["is_compliant"] = patched_ec2[6]
                        ec2["platform_type"] = patched_ec2[7]
                        break

                all_ec2.append(ec2)
            if len_instances == 0:
                empty_accounts.append(account_id)

        ##### Pandas #####
        data = {
            "Num": [x + 1 for x in range(len(all_ec2))],
            "Account Id": [x["account_id"] for x in all_ec2],
            "Account Alias": [x["acc_alias"] for x in all_ec2],
            "EC2 Name": [x["name"] for x in all_ec2],
            "Instance Id": [x["ec2"] for x in all_ec2],
            "Applypatching": [x["ec2_apply_patching"] for x in all_ec2],
            "Patch Group": [x["patch_group"] for x in all_ec2],
            "OS name by Tag": [x["os_name"] for x in all_ec2],
            "Instance State": [x["ec2_state"] for x in all_ec2],
            "Created on": [x["launch_date"] for x in all_ec2],
            "Patched": [x["patched"] for x in all_ec2],
            "BaselineId": [x["baseline_id"] for x in all_ec2],
            "InstalledCount": [x["installed_count"] for x in all_ec2],
            "MissingCount": [x["missing_count"] for x in all_ec2],
            "FailedCount": [x["failed_count"] for x in all_ec2],
            "Last patched": [x["last_update"] for x in all_ec2],
            "Compliance status": [x["is_compliant"] for x in all_ec2],
            "Platform type": [x["platform_type"] for x in all_ec2],
            "Application": [x["application"] for x in all_ec2],
            "ApplicationCategory": [x["application_category"] for x in all_ec2],
            "ApplicationNumber": [x["application_number"] for x in all_ec2],
            "BusinessCriticality": [x["business_criticality"] for x in all_ec2],
            "BusinessOwner": [x["business_owner"] for x in all_ec2],
            "BusinessUnit": [x["business_unit"] for x in all_ec2],
            "Classification": [x["classification"] for x in all_ec2],
            "Environment": [x["environment"] for x in all_ec2],
            "Organization": [x["organization"] for x in all_ec2],
            "Owner": [x["owner"] for x in all_ec2],
            "Project": [x["project"] for x in all_ec2],
            "Security": [x["security"] for x in all_ec2],
            "ServiceType": [x["service_type"] for x in all_ec2],
            "TechnicalOwner": [x["technical_owner"] for x in all_ec2],
            "WBS": [x["wbs"] for x in all_ec2],
            "Supplier": [x["supplier"] for x in all_ec2],
        }

        df_marks1 = pd.DataFrame(data, index=[x + 1 for x in range(len(all_ec2))])
        df_marks1.to_csv(path_or_buf=f"/tmp/{EXCEL_NAME}", sep=(","), index=False)

        print("------------")
        print("No maintenance window presented")
        print(no_maintenance_window_accounts)
        print("------------")
        print("Accounts with no EC2")
        print(empty_accounts)
        print("------------")

        # We have to override the credentials, because the last assumed credentials are generated from the last IAM ARN role in the ARNLIST.
        AWS_USER_KEY = AWS_MASTER_USER_KEY
        AWS_USER_SECRET = AWS_MASTER_USER_SECRET

        class S3Service:
            def __init__(self):
                key = AWS_USER_KEY
                secret = AWS_USER_SECRET
                self.region = AWS_REGION
                self.bucket = AWS_S3_BUCKET_NAME
                self.s3 = boto3.client(
                    "s3",
                    region_name=self.region,
                    aws_access_key_id=key,
                    aws_secret_access_key=secret,
                )

            def upload(self, path, name):
                try:
                    self.s3.upload_file(path, self.bucket, name)
                except ClientError as e:
                    print(e.response["Error"]["Message"])
                else:
                    print(f"The excel file has been uploaded."),

        s3 = S3Service()
        s3.upload(ATTACHMENT, EXCEL_NAME)

        class SESService:
            def __init__(self):
                key = AWS_USER_KEY
                secret = AWS_USER_SECRET
                self.region = AWS_REGION
                self.ses = boto3.client(
                    "ses",
                    region_name=self.region,
                    aws_access_key_id=key,
                    aws_secret_access_key=secret,
                )

            def send_email(self, RECIPIENT_FUNC):
                # Create a multipart/mixed parent container.
                msg = MIMEMultipart("mixed")
                # Add subject, from and to lines.
                msg["Subject"] = SUBJECT
                msg["From"] = SENDER
                msg["To"] = RECIPIENT_FUNC
                # Create a multipart/alternative child container.
                msg_body = MIMEMultipart("alternative")
                # Encode the text content and set the character encoding. This step is
                # necessary if you're sending a message with characters outside the ASCII range.
                textpart = MIMEText(BODY_TEXT.encode(CHARSET), "plain", CHARSET)
                msg_body.attach(textpart)
                # Define the attachment part and encode it using MIMEApplication.
                att = MIMEApplication(open(ATTACHMENT, "rb").read())
                # Add a header to tell the email client to treat this part as an attachment,
                # and to give the attachment a name.
                att.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=os.path.basename(ATTACHMENT),
                )
                msg.attach(msg_body)
                msg.attach(att)
                try:
                    response = self.ses.send_raw_email(
                        Source=SENDER,
                        Destinations=[RECIPIENT_FUNC],
                        RawMessage={
                            "Data": msg.as_string(),
                        },
                    )
                except ClientError as ex:
                    print(ex.response["Error"]["Message"])
                else:
                    print(f"Email sent to {RECIPIENT_FUNC} ! Message ID:"),
                    print(response["MessageId"])

        ses = SESService()
        ses.send_email(RECIPIENT)
        ses.send_email(RECIPIENT_CC)
        ses.send_email(RECIPIENT_CC2)
        ses.send_email(RECIPIENT_CHM)
        return "The Report has been generated and stored to S3"

    except Exception as ex:
        print(ex)
