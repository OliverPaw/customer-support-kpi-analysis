from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

# -----------------------------
# Reproducibility
# -----------------------------
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)

# -----------------------------
# Paths (GitHub portable)
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "bktp_data"

INPUT_FILE = DATA_DIR / "customer_support_tickets.csv"
OUTPUT_FILE = DATA_DIR / "cleaned_tickets.csv"

# -----------------------------
# 1. Load raw CSV
# -----------------------------
df = pd.read_csv(
    INPUT_FILE,
    engine="python",
    on_bad_lines="skip"
)

# -----------------------------
# 2. Keep only useful columns
# -----------------------------
df = df[[
    "Ticket ID",
    "Date of Purchase",
    "Ticket Type",
    "Ticket Status",
    "Ticket Priority",
    "Ticket Channel",
    "Customer Satisfaction Rating"
]]

# -----------------------------
# 3. Rename columns
# -----------------------------
df = df.rename(columns={
    "Ticket ID": "ticket_id",
    "Date of Purchase": "purchase_date",
    "Ticket Type": "ticket_type",
    "Ticket Status": "raw_status",
    "Ticket Priority": "priority",
    "Ticket Channel": "channel",
    "Customer Satisfaction Rating": "csat_score"
})

# -----------------------------
# 4. Convert purchase date
# -----------------------------
df["purchase_date"] = pd.to_datetime(df["purchase_date"], errors="coerce")

# Drop rows where purchase date is missing
df = df.dropna(subset=["purchase_date"]).copy()

# -----------------------------
# 5. Format ticket_id
# -----------------------------
df["ticket_id"] = df["ticket_id"].apply(lambda x: f"T{x:05d}")

# -----------------------------
# 6. Assign team from ticket type
# -----------------------------
def assign_team(ticket_type):
    if pd.isna(ticket_type):
        return "General Support"
    elif "Billing" in ticket_type or "Refund" in ticket_type:
        return "Billing Support"
    elif "Technical" in ticket_type:
        return "Technical Support"
    else:
        return "General Support"

df["team"] = df["ticket_type"].apply(assign_team)

# -----------------------------
# 7. Assign agent from team
# -----------------------------
team_agents = {
    "General Support": ["Anna", "Lukas", "Mia"],
    "Technical Support": ["Jonas", "Sofia", "Daniel"],
    "Billing Support": ["Emma", "Noah"]
}

def assign_agent(team):
    return np.random.choice(team_agents[team])

df["agent_name"] = df["team"].apply(assign_agent)

# -----------------------------
# 8. Assign SLA target hours from priority
# -----------------------------
def assign_sla(priority):
    if priority == "Critical":
        return 2
    elif priority == "High":
        return 4
    elif priority == "Medium":
        return 8
    else:
        return 24

df["sla_target_hours"] = df["priority"].apply(assign_sla)

# -----------------------------
# 9. Create ticket_created_at with growing ticket demand over time
# -----------------------------
# Business logic:
# - The company grows over time
# - Later months get more incoming tickets
# - Tickets are distributed across months with increasing probability
# - Then each ticket gets a random day/time inside its assigned month

# Define analysis window
start_month = pd.Timestamp("2021-01-01")
end_month = pd.Timestamp("2022-12-01")

# Create one month-start date per month
month_starts = pd.date_range(start=start_month, end=end_month, freq="MS")

# Create increasing weights for later months
month_weights = np.linspace(1.0, 2.2, len(month_starts))
month_probabilities = month_weights / month_weights.sum()

# Randomly assign each ticket to a month using those probabilities
assigned_months = np.random.choice(month_starts, size=len(df), p=month_probabilities)
assigned_months = pd.to_datetime(assigned_months)

# Generate a random day within each assigned month
random_days = []
for month_start in assigned_months:
    next_month = month_start + pd.offsets.MonthBegin(1)
    days_in_month = (next_month - month_start).days
    random_day = np.random.randint(0, days_in_month)
    random_days.append(random_day)

random_days = np.array(random_days)

# Generate random business-hour times
random_hours = np.random.randint(8, 19, size=len(df))   # 08:00 to 18:59
random_minutes = np.random.randint(0, 60, size=len(df))
random_seconds = np.random.randint(0, 60, size=len(df))

# Build final ticket_created_at
df["ticket_created_at"] = (
    assigned_months
    + pd.to_timedelta(random_days, unit="D")
    + pd.to_timedelta(random_hours, unit="h")
    + pd.to_timedelta(random_minutes, unit="m")
    + pd.to_timedelta(random_seconds, unit="s")
)

# -----------------------------
# 10. Create realistic first response time in hours
# -----------------------------
# Some tickets will breach SLA on purpose
# Includes TEAM effect (bottleneck simulation)

def response_hours(priority, channel, team):
    # Base by priority
    if priority == "Critical":
        base = np.random.uniform(0.2, 3.5)
    elif priority == "High":
        base = np.random.uniform(1.0, 6.0)
    elif priority == "Medium":
        base = np.random.uniform(3.0, 12.0)
    else:
        base = np.random.uniform(6.0, 36.0)

    # Channel effect
    if channel == "Chat":
        base *= 0.8
    elif channel == "Email":
        base *= 1.15
    elif channel == "Phone":
        base *= 0.7
    elif channel == "Social media":
        base *= 1.1

    # Team effect
    if team == "Technical Support":
        base *= 1.3
    elif team == "General Support":
        base *= 1.1
    elif team == "Billing Support":
        base *= 0.9

    return round(base, 2)

df["response_time_hours"] = [
    response_hours(priority, channel, team)
    for priority, channel, team in zip(df["priority"], df["channel"], df["team"])
]

df["first_response_at"] = (
    df["ticket_created_at"] + pd.to_timedelta(df["response_time_hours"], unit="h")
)

# -----------------------------
# 11. Create realistic resolution time in hours
# -----------------------------
# Closed tickets get a resolved_at timestamp.
# Open / Pending usually remain unresolved.

def final_status(ticket_created_at):
    age_days = (pd.Timestamp("2023-06-30") - ticket_created_at).days

    if age_days > 90:
        return np.random.choice(
            ["Closed", "Pending Customer Response", "Open"],
            p=[0.90, 0.07, 0.03]
        )
    elif age_days > 30:
        return np.random.choice(
            ["Closed", "Pending Customer Response", "Open"],
            p=[0.75, 0.15, 0.10]
        )
    else:
        return np.random.choice(
            ["Closed", "Pending Customer Response", "Open"],
            p=[0.55, 0.25, 0.20]
        )

df["status"] = df["ticket_created_at"].apply(final_status)

def resolution_hours(ticket_type, priority):
    # Base by ticket type
    if pd.isna(ticket_type):
        base = np.random.uniform(12, 72)
    elif "Billing" in ticket_type or "Refund" in ticket_type:
        base = np.random.uniform(6, 48)
    elif "Cancellation" in ticket_type:
        base = np.random.uniform(4, 36)
    elif "Product inquiry" in ticket_type:
        base = np.random.uniform(8, 72)
    elif "Technical" in ticket_type:
        base = np.random.uniform(12, 120)
    else:
        base = np.random.uniform(12, 72)

    # Priority effect
    if priority == "Critical":
        base *= 0.75
    elif priority == "High":
        base *= 0.9
    elif priority == "Low":
        base *= 1.15

    return round(base, 2)

df["resolution_time_hours"] = [
    resolution_hours(ticket_type, priority)
    for ticket_type, priority in zip(df["ticket_type"], df["priority"])
]

df["resolved_at"] = pd.NaT

closed_mask = df["status"] == "Closed"
df.loc[closed_mask, "resolved_at"] = (
    df.loc[closed_mask, "ticket_created_at"]
    + pd.to_timedelta(df.loc[closed_mask, "resolution_time_hours"], unit="h")
)

# Make sure first response is always before resolution for closed tickets
bad_resolution_mask = closed_mask & (df["resolved_at"] < df["first_response_at"])
df.loc[bad_resolution_mask, "resolved_at"] = (
    df.loc[bad_resolution_mask, "first_response_at"]
    + pd.to_timedelta(np.random.uniform(1, 24, size=bad_resolution_mask.sum()), unit="h")
)

# -----------------------------
# 12. Inject performance degradation over time
# -----------------------------
min_date = df["ticket_created_at"].min()
max_date = df["ticket_created_at"].max()

df["time_progress"] = (
    (df["ticket_created_at"] - min_date) /
    (max_date - min_date)
)

# Degrade response time
df["response_time_hours"] = df["response_time_hours"] * (1 + df["time_progress"] * 0.8)

df["first_response_at"] = (
    df["ticket_created_at"] + pd.to_timedelta(df["response_time_hours"], unit="h")
)

# Degrade resolution time
df["resolution_time_hours"] = df["resolution_time_hours"] * (1 + df["time_progress"] * 1.0)

df.loc[closed_mask, "resolved_at"] = (
    df.loc[closed_mask, "ticket_created_at"] +
    pd.to_timedelta(df.loc[closed_mask, "resolution_time_hours"], unit="h")
)

# Ensure resolution happens after response
bad_resolution_mask = closed_mask & (df["resolved_at"] < df["first_response_at"])
df.loc[bad_resolution_mask, "resolved_at"] = (
    df.loc[bad_resolution_mask, "first_response_at"] +
    pd.to_timedelta(np.random.uniform(1, 24, size=bad_resolution_mask.sum()), unit="h")
)

# Increase SLA breaches over time
df["sla_breached"] = np.where(
    df["response_time_hours"] > df["sla_target_hours"] * (1 - df["time_progress"] * 0.3),
    "Yes",
    "No"
)

# Decrease CSAT over time
df["csat_score"] = df["csat_score"] - (df["time_progress"] * 1.5)
df["csat_score"] = df["csat_score"].clip(1, 5)

# -----------------------------
# 13. Keep / reorder final columns
# -----------------------------
df = df[[
    "ticket_id",
    "purchase_date",
    "ticket_created_at",
    "first_response_at",
    "resolved_at",
    "agent_name",
    "team",
    "channel",
    "priority",
    "ticket_type",
    "status",
    "sla_target_hours",
    "response_time_hours",
    "resolution_time_hours",
    "sla_breached",
    "csat_score"
]]

# Format datetime columns for export
df["purchase_date"] = df["purchase_date"].dt.strftime("%Y-%m-%d %H:%M:%S")
df["ticket_created_at"] = pd.to_datetime(df["ticket_created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
df["first_response_at"] = pd.to_datetime(df["first_response_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
df["resolved_at"] = pd.to_datetime(df["resolved_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

# -----------------------------
# 14. Save cleaned file
# -----------------------------
df.to_csv(OUTPUT_FILE, index=False)

# -----------------------------
# 15. Quick checks
# -----------------------------
print(f"Saved cleaned dataset to: {OUTPUT_FILE}")
print(df.head(10))
print(df.info())
print(df[[
    "purchase_date",
    "ticket_created_at",
    "first_response_at",
    "resolved_at",
    "response_time_hours",
    "resolution_time_hours",
    "sla_breached"
]].head(10))