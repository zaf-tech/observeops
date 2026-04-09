"""
Multi-Cloud Billing Collector — fetches real cost data from AWS, Azure, and GCP.
Called by synthesizer when cloud credentials are present and the user's
custom instructions mention billing, cost, or forecast keywords.

Returns a nested dict keyed by provider:
  {
    "aws":   { historical_months, current_month, current_mtd, forecast, top_services },
    "azure": { historical_months, current_month, current_mtd, top_services },
    "gcp":   { billing_account, budgets, note },
  }
Only providers with active credentials are included.
"""
import logging
import os
from datetime import date, timedelta
from calendar import monthrange

logger = logging.getLogger(__name__)

_BILLING_KEYWORDS = {
    "billing", "cost", "costs", "spend", "spending", "forecast",
    "invoice", "charges", "budget", "monthly", "price", "pricing",
    "expensive", "bill",
}


def should_collect_billing(custom_instructions: str) -> bool:
    """Return True if the user's instructions mention billing/cost topics."""
    text = custom_instructions.lower()
    return any(kw in text for kw in _BILLING_KEYWORDS)


def collect_billing_data() -> dict | None:
    """
    Collect billing data from all available cloud providers.
    Returns a dict with provider keys, or None if no data could be collected.
    """
    results: dict = {}

    # ── AWS ──────────────────────────────────────────────────────────
    if os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_PROFILE"):
        aws = _collect_aws()
        if aws:
            results["aws"] = aws

    # ── Azure ─────────────────────────────────────────────────────────
    if os.environ.get("AZURE_CLIENT_ID") and os.environ.get("AZURE_SUBSCRIPTION_ID"):
        azure = _collect_azure()
        if azure:
            results["azure"] = azure

    # ── GCP ───────────────────────────────────────────────────────────
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.environ.get("GCP_SERVICE_ACCOUNT_JSON"):
        gcp = _collect_gcp()
        if gcp:
            results["gcp"] = gcp

    return results or None


# ── AWS Cost Explorer ─────────────────────────────────────────────────

def _collect_aws() -> dict | None:
    try:
        import boto3
        from botocore.exceptions import ClientError

        region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        ce = boto3.client("ce", region_name=region)

        today = date.today()
        months = _last_n_months(today, 6)
        start_str = months[0]["start"]
        current_month_start = date(today.year, today.month, 1).isoformat()

        # Historical 6 months
        historical = []
        try:
            resp = ce.get_cost_and_usage(
                TimePeriod={"Start": start_str, "End": current_month_start},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )
            for result in resp.get("ResultsByTime", []):
                period_start = result["TimePeriod"]["Start"]
                amount = float(result["Total"]["UnblendedCost"]["Amount"])
                unit   = result["Total"]["UnblendedCost"]["Unit"]
                historical.append({
                    "month":  _month_label(period_start),
                    "amount": round(amount, 2),
                    "unit":   unit,
                })
        except Exception as exc:
            logger.warning("AWS historical cost query failed: %s", exc)

        # Current month MTD
        current_mtd = None
        try:
            tomorrow = (today + timedelta(days=1)).isoformat()
            resp = ce.get_cost_and_usage(
                TimePeriod={"Start": current_month_start, "End": tomorrow},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )
            for result in resp.get("ResultsByTime", []):
                amount = float(result["Total"]["UnblendedCost"]["Amount"])
                unit   = result["Total"]["UnblendedCost"]["Unit"]
                current_mtd = {"amount": round(amount, 2), "unit": unit}
        except Exception as exc:
            logger.warning("AWS MTD query failed: %s", exc)

        # Forecast
        forecast = None
        try:
            if today.month == 12:
                forecast_end = date(today.year + 1, 1, 1).isoformat()
            else:
                forecast_end = date(today.year, today.month + 1, 1).isoformat()
            forecast_start = today.isoformat()
            if forecast_start < forecast_end:
                resp = ce.get_cost_forecast(
                    TimePeriod={"Start": forecast_start, "End": forecast_end},
                    Granularity="MONTHLY",
                    Metric="UNBLENDED_COST",
                )
                total = resp.get("Total", {})
                forecast = {
                    "amount": round(float(total.get("Amount", 0)), 2),
                    "unit":   total.get("Unit", "USD"),
                }
        except Exception as exc:
            logger.warning("AWS forecast query failed: %s", exc)

        # Top services
        top_services = []
        try:
            tomorrow = (today + timedelta(days=1)).isoformat()
            resp = ce.get_cost_and_usage(
                TimePeriod={"Start": current_month_start, "End": tomorrow},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )
            services = []
            for result in resp.get("ResultsByTime", []):
                for group in result.get("Groups", []):
                    amt = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    if amt > 0:
                        services.append({
                            "service": group["Keys"][0],
                            "amount":  round(amt, 2),
                            "unit":    group["Metrics"]["UnblendedCost"]["Unit"],
                        })
            services.sort(key=lambda x: x["amount"], reverse=True)
            top_services = services[:10]
        except Exception as exc:
            logger.warning("AWS top services query failed: %s", exc)

        if not historical and not current_mtd:
            return None

        return {
            "currency":         "USD",
            "historical_months": historical,
            "current_month":     _month_label(current_month_start),
            "current_mtd":       current_mtd,
            "forecast":          forecast,
            "top_services":      top_services,
        }

    except ImportError:
        logger.warning("boto3 not installed — skipping AWS billing")
        return None
    except Exception as exc:
        logger.error("AWS billing collector error: %s", exc)
        return None


# ── Azure Cost Management ─────────────────────────────────────────────

def _collect_azure() -> dict | None:
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.costmanagement import CostManagementClient
        from azure.mgmt.costmanagement.models import (
            QueryDefinition, QueryTimePeriod, QueryDataset,
            QueryAggregation, QueryGrouping, QueryColumnType,
            GranularityType,
        )

        tenant_id       = os.environ.get("AZURE_TENANT_ID", "")
        client_id       = os.environ.get("AZURE_CLIENT_ID", "")
        client_secret   = os.environ.get("AZURE_CLIENT_SECRET", "")
        subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID", "")

        if not all([tenant_id, client_id, client_secret, subscription_id]):
            logger.info("Azure billing: missing credentials")
            return None

        credential = ClientSecretCredential(tenant_id, client_id, client_secret)
        client     = CostManagementClient(credential)
        scope      = f"/subscriptions/{subscription_id}"

        today = date.today()
        months = _last_n_months(today, 6)
        start_str = months[0]["start"]
        current_month_start = date(today.year, today.month, 1).isoformat()

        # Historical 6 months
        historical = []
        try:
            result = client.query.usage(
                scope=scope,
                parameters=QueryDefinition(
                    type="ActualCost",
                    timeframe="Custom",
                    time_period=QueryTimePeriod(
                        from_property=start_str + "T00:00:00Z",
                        to=current_month_start + "T00:00:00Z",
                    ),
                    dataset=QueryDataset(
                        granularity=GranularityType.MONTHLY,
                        aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                    ),
                ),
            )
            # result.rows = [[cost, currency, usageDate], ...]
            # result.columns gives the column names
            col_names = [c.name for c in (result.columns or [])]
            cost_idx  = next((i for i, c in enumerate(col_names) if "cost" in c.lower()), 0)
            date_idx  = next((i for i, c in enumerate(col_names) if "date" in c.lower()), 2)
            for row in (result.rows or []):
                if len(row) > cost_idx:
                    amount = round(float(row[cost_idx]), 2)
                    date_val = str(row[date_idx]) if len(row) > date_idx else ""
                    month_label = _month_label(date_val[:10]) if date_val else "?"
                    historical.append({"month": month_label, "amount": amount, "unit": "USD"})
        except Exception as exc:
            logger.warning("Azure historical cost query failed: %s", exc)

        # Current month MTD
        current_mtd = None
        try:
            tomorrow = (today + timedelta(days=1)).isoformat()
            result = client.query.usage(
                scope=scope,
                parameters=QueryDefinition(
                    type="ActualCost",
                    timeframe="Custom",
                    time_period=QueryTimePeriod(
                        from_property=current_month_start + "T00:00:00Z",
                        to=tomorrow + "T00:00:00Z",
                    ),
                    dataset=QueryDataset(
                        granularity=GranularityType.MONTHLY,
                        aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                    ),
                ),
            )
            col_names = [c.name for c in (result.columns or [])]
            cost_idx  = next((i for i, c in enumerate(col_names) if "cost" in c.lower()), 0)
            for row in (result.rows or []):
                if len(row) > cost_idx:
                    current_mtd = {"amount": round(float(row[cost_idx]), 2), "unit": "USD"}
                    break
        except Exception as exc:
            logger.warning("Azure MTD query failed: %s", exc)

        # Top services by ServiceName
        top_services = []
        try:
            tomorrow = (today + timedelta(days=1)).isoformat()
            result = client.query.usage(
                scope=scope,
                parameters=QueryDefinition(
                    type="ActualCost",
                    timeframe="Custom",
                    time_period=QueryTimePeriod(
                        from_property=current_month_start + "T00:00:00Z",
                        to=tomorrow + "T00:00:00Z",
                    ),
                    dataset=QueryDataset(
                        granularity=GranularityType.NONE,
                        aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                        grouping=[QueryGrouping(type=QueryColumnType.DIMENSION, name="ServiceName")],
                    ),
                ),
            )
            col_names = [c.name for c in (result.columns or [])]
            cost_idx  = next((i for i, c in enumerate(col_names) if "cost" in c.lower()), 0)
            svc_idx   = next((i for i, c in enumerate(col_names) if "service" in c.lower()), 1)
            services  = []
            for row in (result.rows or []):
                if len(row) > max(cost_idx, svc_idx):
                    amt = round(float(row[cost_idx]), 2)
                    if amt > 0:
                        services.append({"service": str(row[svc_idx]), "amount": amt, "unit": "USD"})
            services.sort(key=lambda x: x["amount"], reverse=True)
            top_services = services[:10]
        except Exception as exc:
            logger.warning("Azure top services query failed: %s", exc)

        if not historical and not current_mtd:
            return None

        return {
            "currency":          "USD",
            "subscription_id":   subscription_id[:8] + "…",
            "historical_months": historical,
            "current_month":     _month_label(current_month_start),
            "current_mtd":       current_mtd,
            "top_services":      top_services,
        }

    except ImportError:
        logger.warning("azure-mgmt-costmanagement not installed — skipping Azure billing")
        return None
    except Exception as exc:
        logger.error("Azure billing collector error: %s", exc)
        return None


# ── GCP Cloud Billing ─────────────────────────────────────────────────

def _collect_gcp() -> dict | None:
    """
    GCP billing data collection — multiple strategies in priority order:
    1. BigQuery billing export (most detailed — requires GCP_BILLING_BQ_DATASET)
    2. Cloud Monitoring billing metrics (current month only, no history)
    3. Budget API (budget amounts + spend alerts)
    4. Billing account info only (last resort)
    """
    try:
        import google.auth
        from google.cloud import billing_v1

        project_id = os.environ.get("GCP_PROJECT_ID", "")
        billing_client = billing_v1.CloudBillingClient()
        billing_account_name    = None
        billing_account_display = None

        if project_id:
            try:
                proj_billing = billing_client.get_project_billing_info(
                    name=f"projects/{project_id}"
                )
                billing_account_name    = proj_billing.billing_account_name
                billing_account_display = proj_billing.billing_account_name.split("/")[-1]
            except Exception as exc:
                logger.warning("GCP project billing info failed: %s", exc)

        # ── Strategy 1: BigQuery billing export ──────────────────────
        monthly_costs = []
        top_services  = []
        current_mtd   = None
        bq_dataset    = os.environ.get("GCP_BILLING_BQ_DATASET", "")
        if bq_dataset and project_id:
            try:
                from google.cloud import bigquery
                bq = bigquery.Client(project=project_id)
                today = date.today()
                months_list = _last_n_months(today, 6)
                start_str = months_list[0]["start"]
                current_month_start = date(today.year, today.month, 1).isoformat()

                # Historical months
                hist_query = f"""
                    SELECT
                        FORMAT_DATE('%Y-%m', DATE(usage_start_time)) AS month,
                        SUM(cost) AS total_cost,
                        currency
                    FROM `{project_id}.{bq_dataset}.gcp_billing_export_v1_*`
                    WHERE DATE(usage_start_time) >= '{start_str}'
                      AND DATE(usage_start_time) < '{current_month_start}'
                    GROUP BY month, currency
                    ORDER BY month ASC
                """
                for row in bq.query(hist_query).result():
                    monthly_costs.append({
                        "month":  _month_label(row["month"] + "-01"),
                        "amount": round(float(row["total_cost"]), 2),
                        "unit":   row["currency"],
                    })

                # Current month MTD
                mtd_query = f"""
                    SELECT SUM(cost) AS total_cost, currency
                    FROM `{project_id}.{bq_dataset}.gcp_billing_export_v1_*`
                    WHERE DATE(usage_start_time) >= '{current_month_start}'
                    GROUP BY currency
                """
                for row in bq.query(mtd_query).result():
                    current_mtd = {"amount": round(float(row["total_cost"]), 2), "unit": row["currency"]}
                    break

                # Top services current month
                svc_query = f"""
                    SELECT service.description AS service, SUM(cost) AS total_cost, currency
                    FROM `{project_id}.{bq_dataset}.gcp_billing_export_v1_*`
                    WHERE DATE(usage_start_time) >= '{current_month_start}'
                    GROUP BY service, currency
                    ORDER BY total_cost DESC
                    LIMIT 10
                """
                for row in bq.query(svc_query).result():
                    if float(row["total_cost"]) > 0:
                        top_services.append({
                            "service": row["service"],
                            "amount":  round(float(row["total_cost"]), 2),
                            "unit":    row["currency"],
                        })

                logger.info("GCP BigQuery billing: %d months, MTD=%s", len(monthly_costs), current_mtd)
            except Exception as exc:
                logger.warning("GCP BigQuery billing query failed: %s", exc)

        # ── Strategy 2: Cloud Monitoring billing metrics ─────────────
        # Gets current month spend when BigQuery export is not available
        if not monthly_costs and not current_mtd and project_id:
            try:
                from google.cloud import monitoring_v3
                from google.protobuf.timestamp_pb2 import Timestamp
                import time as _time

                client = monitoring_v3.MetricServiceClient()
                project_name = f"projects/{project_id}"
                today = date.today()
                current_month_start = date(today.year, today.month, 1)

                # billing/monthly_cost is available in Cloud Monitoring
                start_ts = Timestamp()
                start_ts.FromDatetime(
                    __import__("datetime").datetime.combine(current_month_start, __import__("datetime").time.min)
                )
                end_ts = Timestamp()
                end_ts.GetCurrentTime()

                interval = monitoring_v3.TimeInterval(
                    start_time=start_ts,
                    end_time=end_ts,
                )
                results = client.list_time_series(
                    request={
                        "name": project_name,
                        "filter": 'metric.type="billing.googleapis.com/billing/monthly_cost"',
                        "interval": interval,
                        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    }
                )
                total_cost = 0.0
                for ts in results:
                    for point in ts.points:
                        total_cost += point.value.double_value
                if total_cost > 0:
                    current_mtd = {"amount": round(total_cost, 2), "unit": "USD"}
                    logger.info("GCP Monitoring billing MTD: $%.2f", total_cost)
            except Exception as exc:
                logger.warning("GCP Cloud Monitoring billing metrics failed: %s", exc)

        # ── Strategy 3: Budget API ────────────────────────────────────
        budgets = []
        if billing_account_name:
            try:
                from google.cloud import billing_budgets_v1
                budget_client = billing_budgets_v1.BudgetServiceClient()
                for budget in budget_client.list_budgets(parent=billing_account_name):
                    amount = None
                    spend  = None
                    if budget.amount and budget.amount.specified_amount:
                        units  = budget.amount.specified_amount.units
                        nanos  = budget.amount.specified_amount.nanos
                        amount = units + nanos / 1e9
                    # budget.budget_filter has spend info in some versions
                    budgets.append({
                        "name":     budget.display_name or budget.name.split("/")[-1],
                        "budget":   round(amount, 2) if amount else None,
                        "currency": budget.amount.specified_amount.currency_code
                                    if (budget.amount and budget.amount.specified_amount) else "USD",
                    })
                    # If no MTD from other sources and we have a budget with spend, use it
                    if not current_mtd and budget.amount and budget.amount.last_period_amount:
                        pass  # last_period_amount is not always available
            except Exception as exc:
                logger.warning("GCP budget API failed: %s", exc)

        if not billing_account_name and not project_id:
            return None

        today = date.today()
        current_month_start = date(today.year, today.month, 1).isoformat()
        result: dict = {
            "project_id":      project_id,
            "billing_account": billing_account_display,
        }
        if budgets:
            result["budgets"] = budgets
        if monthly_costs:
            result["historical_months"] = monthly_costs
            result["current_month"]     = _month_label(current_month_start)
        if current_mtd:
            result["current_mtd"]   = current_mtd
            result["current_month"] = result.get("current_month") or _month_label(current_month_start)
        if top_services:
            result["top_services"] = top_services

        if not monthly_costs and not current_mtd:
            result["note"] = (
                "Detailed cost history requires BigQuery billing export to be enabled in GCP Console "
                "(Billing → Billing export → BigQuery export), then set the env var "
                "GCP_BILLING_BQ_DATASET=<dataset_name>. "
                "Current month spend via Cloud Monitoring was also unavailable."
            )

        return result

    except ImportError:
        logger.warning("google-cloud-billing not installed — skipping GCP billing")
        return None
    except Exception as exc:
        logger.error("GCP billing collector error: %s", exc)
        return None


# ── Helpers ──────────────────────────────────────────────────────────

def _last_n_months(ref: date, n: int) -> list[dict]:
    months = []
    year, month = ref.year, ref.month
    for _ in range(n):
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        days  = monthrange(year, month)[1]
        start = date(year, month, 1).isoformat()
        end   = date(year, month, days).isoformat()
        months.insert(0, {"start": start, "end": end})
    return months


def _month_label(iso_start: str) -> str:
    """Convert '2025-10-01' or '2025-10' → 'Oct 2025'."""
    try:
        s = iso_start[:10]
        if len(s) == 7:
            s += "-01"
        return date.fromisoformat(s).strftime("%b %Y")
    except Exception:
        return iso_start
