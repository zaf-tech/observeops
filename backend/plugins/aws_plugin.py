"""AWS plugin — boto3. Covers EC2, S3, IAM, RDS, VPC, Lambda. READ-ONLY."""
import os
import logging

from base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class AWSPlugin(BasePlugin):
    name = "aws"
    credential_keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]

    def is_available(self) -> bool:
        return all(os.getenv(k) for k in self.credential_keys)

    def get_metadata(self) -> dict:
        try:
            import boto3
            sts = boto3.client("sts")
            identity = sts.get_caller_identity()
            return {
                "platform": self.name,
                "account_id": identity.get("Account"),
                "arn": identity.get("Arn"),
                "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            }
        except Exception as exc:
            logger.warning("AWS get_metadata failed: %s", exc)
            return {"platform": self.name}

    def run_scan(self) -> list[dict]:
        if not self.is_available():
            return []
        findings = []
        try:
            import boto3
            region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            session = boto3.Session(region_name=region)
            findings += self._scan_s3(session)
            findings += self._scan_ec2(session)
            findings += self._scan_iam(session)
            findings += self._scan_rds(session)
            findings += self._scan_lambda(session)
            findings += self._scan_security_groups(session)
        except Exception as exc:
            logger.error("AWS scan failed: %s", exc)
        return findings

    # ── S3 ────────────────────────────────────────────────────────────
    def _scan_s3(self, session) -> list[dict]:
        findings = []
        try:
            s3 = session.client("s3")
            buckets = s3.list_buckets().get("Buckets", [])
            for bucket in buckets:
                name = bucket["Name"]
                resource = f"s3://{name}"
                # Public access block
                try:
                    pab = s3.get_public_access_block(Bucket=name)
                    cfg = pab["PublicAccessBlockConfiguration"]
                    if not all([cfg.get("BlockPublicAcls"), cfg.get("BlockPublicPolicy"),
                                cfg.get("IgnorePublicAcls"), cfg.get("RestrictPublicBuckets")]):
                        findings.append(self._finding(
                            resource, "CRITICAL", "security",
                            "S3 bucket does not fully block public access",
                            "Enable all four Block Public Access settings on the bucket",
                            {"public_access_block": cfg},
                        ))
                except s3.exceptions.NoSuchPublicAccessBlockConfiguration:
                    findings.append(self._finding(
                        resource, "CRITICAL", "security",
                        "S3 bucket has no Public Access Block configuration",
                        "Add a Public Access Block configuration to prevent accidental exposure",
                    ))
                except Exception:
                    pass
                # Versioning
                try:
                    ver = s3.get_bucket_versioning(Bucket=name)
                    if ver.get("Status") != "Enabled":
                        findings.append(self._finding(
                            resource, "MEDIUM", "reliability",
                            "S3 bucket versioning is not enabled",
                            "Enable versioning to protect against accidental deletion",
                        ))
                except Exception:
                    pass
                # Encryption
                try:
                    s3.get_bucket_encryption(Bucket=name)
                except Exception:
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        "S3 bucket server-side encryption is not configured",
                        "Enable SSE-S3 or SSE-KMS encryption on the bucket",
                    ))
        except Exception as exc:
            logger.warning("S3 scan error: %s", exc)
        return findings

    # ── EC2 ───────────────────────────────────────────────────────────
    def _scan_ec2(self, session) -> list[dict]:
        findings = []
        try:
            ec2 = session.client("ec2")
            reservations = ec2.describe_instances(
                Filters=[{"Name": "instance-state-name", "Values": ["running", "stopped"]}]
            ).get("Reservations", [])
            for res in reservations:
                for inst in res.get("Instances", []):
                    iid = inst["InstanceId"]
                    resource = f"ec2/{iid}"
                    tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                    # Stopped instances
                    if inst["State"]["Name"] == "stopped":
                        findings.append(self._finding(
                            resource, "LOW", "cost",
                            f"EC2 instance {iid} is stopped but still incurring EBS costs",
                            "Terminate the instance or take a snapshot and delete it if no longer needed",
                            {"instance_type": inst.get("InstanceType"), "tags": tags},
                        ))
                    # Missing Name tag
                    if "Name" not in tags:
                        findings.append(self._finding(
                            resource, "LOW", "compliance",
                            f"EC2 instance {iid} has no Name tag",
                            "Apply consistent tagging for cost allocation and governance",
                        ))
                    # Public IP on non-intentional instance
                    if inst.get("PublicIpAddress") and not tags.get("public-facing"):
                        findings.append(self._finding(
                            resource, "MEDIUM", "security",
                            f"EC2 instance {iid} has a public IP address",
                            "Confirm public IP is intentional; use NAT gateway for private workloads",
                            {"public_ip": inst["PublicIpAddress"]},
                        ))
        except Exception as exc:
            logger.warning("EC2 scan error: %s", exc)
        return findings

    # ── IAM ───────────────────────────────────────────────────────────
    def _scan_iam(self, session) -> list[dict]:
        findings = []
        try:
            iam = session.client("iam")
            # Root account MFA
            summary = iam.get_account_summary()["SummaryMap"]
            if summary.get("AccountMFAEnabled", 0) == 0:
                findings.append(self._finding(
                    "iam/root", "CRITICAL", "security",
                    "Root account does not have MFA enabled",
                    "Enable MFA on the root account immediately",
                ))
            # Users without MFA
            paginator = iam.get_paginator("list_users")
            for page in paginator.paginate():
                for user in page["Users"]:
                    uname = user["UserName"]
                    mfa_devices = iam.list_mfa_devices(UserName=uname)["MFADevices"]
                    if not mfa_devices:
                        findings.append(self._finding(
                            f"iam/user/{uname}", "HIGH", "security",
                            f"IAM user '{uname}' has no MFA device configured",
                            "Enable MFA for all IAM users with console access",
                        ))
                    # Access key age
                    keys = iam.list_access_keys(UserName=uname)["AccessKeyMetadata"]
                    for key in keys:
                        from datetime import timezone, datetime, timedelta
                        age = datetime.now(timezone.utc) - key["CreateDate"]
                        if age > timedelta(days=90):
                            findings.append(self._finding(
                                f"iam/user/{uname}/key/{key['AccessKeyId']}", "HIGH", "security",
                                f"IAM access key for '{uname}' is {age.days} days old (>90 days)",
                                "Rotate access keys every 90 days",
                                {"key_id": key["AccessKeyId"], "age_days": age.days},
                            ))
        except Exception as exc:
            logger.warning("IAM scan error: %s", exc)
        return findings

    # ── RDS ───────────────────────────────────────────────────────────
    def _scan_rds(self, session) -> list[dict]:
        findings = []
        try:
            rds = session.client("rds")
            instances = rds.describe_db_instances().get("DBInstances", [])
            for db in instances:
                resource = f"rds/{db['DBInstanceIdentifier']}"
                if db.get("PubliclyAccessible"):
                    findings.append(self._finding(
                        resource, "CRITICAL", "security",
                        "RDS instance is publicly accessible",
                        "Set PubliclyAccessible=false and place the instance in a private subnet",
                        {"engine": db.get("Engine"), "endpoint": db.get("Endpoint", {}).get("Address")},
                    ))
                if not db.get("MultiAZ"):
                    findings.append(self._finding(
                        resource, "MEDIUM", "reliability",
                        "RDS instance is not Multi-AZ",
                        "Enable Multi-AZ for production databases to ensure high availability",
                    ))
                if not db.get("StorageEncrypted"):
                    findings.append(self._finding(
                        resource, "HIGH", "security",
                        "RDS instance storage is not encrypted",
                        "Enable storage encryption (requires snapshot restore for existing instances)",
                    ))
        except Exception as exc:
            logger.warning("RDS scan error: %s", exc)
        return findings

    # ── Lambda ────────────────────────────────────────────────────────
    def _scan_lambda(self, session) -> list[dict]:
        findings = []
        try:
            lam = session.client("lambda")
            paginator = lam.get_paginator("list_functions")
            for page in paginator.paginate():
                for fn in page["Functions"]:
                    resource = f"lambda/{fn['FunctionName']}"
                    # Runtime deprecation check
                    deprecated = ["python3.8", "python3.7", "nodejs14.x", "nodejs12.x", "ruby2.7"]
                    if fn.get("Runtime") in deprecated:
                        findings.append(self._finding(
                            resource, "HIGH", "reliability",
                            f"Lambda function uses deprecated runtime: {fn['Runtime']}",
                            f"Upgrade runtime to a supported version",
                            {"runtime": fn["Runtime"]},
                        ))
        except Exception as exc:
            logger.warning("Lambda scan error: %s", exc)
        return findings

    # ── Security Groups ───────────────────────────────────────────────
    def _scan_security_groups(self, session) -> list[dict]:
        findings = []
        try:
            ec2 = session.client("ec2")
            sgs = ec2.describe_security_groups().get("SecurityGroups", [])
            for sg in sgs:
                resource = f"ec2/sg/{sg['GroupId']}"
                for rule in sg.get("IpPermissions", []):
                    for cidr in rule.get("IpRanges", []):
                        if cidr.get("CidrIp") == "0.0.0.0/0":
                            port = rule.get("FromPort", "all")
                            findings.append(self._finding(
                                resource, "HIGH", "security",
                                f"Security group {sg['GroupId']} allows inbound 0.0.0.0/0 on port {port}",
                                "Restrict inbound rules to known IP ranges",
                                {"group_name": sg.get("GroupName"), "port": port},
                            ))
        except Exception as exc:
            logger.warning("Security group scan error: %s", exc)
        return findings
