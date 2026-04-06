from __future__ import annotations

from pathlib import Path
import pandas as pd

# -----------------------------
# Paths (GitHub portable)
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "bktp_data"

INPUT_FILE = DATA_DIR / "cleaned_tickets.csv"
OUTPUT_FILE = DATA_DIR / "monthly_summary.csv"

# -----------------------------
# 1. Load cleaned dataset
# -----------------------------
df = pd.read_csv(INPUT_FILE)

# -----------------------------
# 2. Convert date columns back to datetime
# -----------------------------
df["ticket_created_at"] = pd.to_datetime(df["ticket_created_at"])
df["first_response_at"] = pd.to_datetime(df["first_response_at"])
df["resolved_at"] = pd.to_datetime(df["resolved_at"], errors="coerce")

# -----------------------------
# 3. Basic sanity check
# -----------------------------
print("\n--- BASIC INFO ---")
print(df.info())

print("\n--- FIRST 5 ROWS ---")
print(df.head())

# -----------------------------
# 4. Sort by time to compare early vs late
# -----------------------------
df_sorted = df.sort_values("ticket_created_at")

print("\n--- EARLY TICKETS (first 10) ---")
print(df_sorted[[
    "ticket_created_at",
    "response_time_hours",
    "resolution_time_hours",
    "csat_score",
    "sla_breached"
]].head(10))

print("\n--- LATE TICKETS (last 10) ---")
print(df_sorted[[
    "ticket_created_at",
    "response_time_hours",
    "resolution_time_hours",
    "csat_score",
    "sla_breached"
]].tail(10))

# -----------------------------
# 5. Create monthly aggregation
# -----------------------------
df["month"] = df["ticket_created_at"].dt.to_period("M")

monthly = df.groupby("month").agg({
    "response_time_hours": "mean",
    "resolution_time_hours": "mean",
    "csat_score": "mean",
    "ticket_id": "count",
    "sla_breached": lambda x: (x == "Yes").mean()
}).rename(columns={
    "ticket_id": "ticket_volume",
    "sla_breached": "sla_breach_rate"
})

print("\n--- MONTHLY SUMMARY ---")
print(monthly)

# -----------------------------
# 6. Filter examples (for deeper inspection)
# -----------------------------
tech = df[df["ticket_type"].str.contains("Technical", na=False)]

print("\n--- TECHNICAL TICKETS SAMPLE ---")
print(tech.head())

breached = df[df["sla_breached"] == "Yes"]

print("\n--- SLA BREACH SAMPLE ---")
print(breached.head())

high_priority = df[df["priority"] == "High"]

print("\n--- HIGH PRIORITY SAMPLE ---")
print(high_priority.head())

# -----------------------------
# 7. Export monthly summary
# -----------------------------
monthly.to_csv(OUTPUT_FILE)

print(f"\n--- FILE EXPORTED: {OUTPUT_FILE} ---")