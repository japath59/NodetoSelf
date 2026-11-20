import pandas as pd
import numpy as np

from natural_disaster_calculation import calculate_severity

# ============================================================
# STEP 1: LOAD AND EXAMINE COMBINED DATASET
# ============================================================

# Uses the same filtering, imputation, and normalization
# as the project's actual severity calculation.
analysis_df = calculate_severity()

print("Dataset shape:", analysis_df.shape)

print("\nRecords by source:")
print(analysis_df["Source"].value_counts())

print("\nDisaster types:")
print(analysis_df["Disaster Type"].value_counts())

columns = [
    "deaths_imputed",
    "affected_imputed",
    "damage_imputed",
    "death_score",
    "affected_score",
    "damage_score"
]

for col in columns:
    values = pd.to_numeric(
        analysis_df[col], errors="coerce"
    )

    print(f"\n{col}")
    print("Missing:", values.isna().sum())
    print("Zero:", (values == 0).sum())
    print("Positive:", (values > 0).sum())
    print("Maximum:", values.max())

print("\nImputation counts:")
for col in [
    "deaths_was_imputed",
    "affected_was_imputed",
    "damage_was_imputed"
]:
    print(col, analysis_df[col].sum())


# ============================================================
# STEP 2: HUMANITARIAN SEVERITY SENSITIVITY ANALYSIS
# ============================================================

human_weights = [0.5, 0.6, 0.7, 0.8]

humanitarian_models = []

for w in human_weights:
    death_weight = round(w * 100)
    affected_weight = 100 - death_weight

    name = f"humanitarian_{death_weight}_{affected_weight}"

    analysis_df[name] = (
        w * analysis_df["death_score"]
        + (1 - w) * analysis_df["affected_score"]
    )

    humanitarian_models.append(name)

print("\n===================================")
print("HUMANITARIAN RANK CORRELATIONS")
print("===================================")

print(
    analysis_df[humanitarian_models]
    .corr(method="spearman")
    .round(4)
    .to_string()
)

# Compare top 100 against existing 70/30 baseline
human_baseline = set(
    analysis_df.nlargest(
        100, "humanitarian_70_30"
    ).index
)

print("\n===================================")
print("HUMANITARIAN TOP 100 OVERLAP")
print("===================================")

for col in humanitarian_models:
    top = set(
        analysis_df.nlargest(100, col).index
    )

    overlap = len(human_baseline & top)

    print(
        f"{col}: {overlap}/100 ({overlap}%)"
    )


# ============================================================
# STEP 3: HUMANITARIAN VS ECONOMIC DAMAGE
# ============================================================

analysis_df["humanitarian"] = (
    analysis_df["humanitarian_70_30"]
)

analysis_df["economic"] = (
    analysis_df["damage_score"]
)

# Use only records with positive reported damage,
# rather than imputed damage.
damage_df = analysis_df[
    analysis_df["Total Damage, Adjusted ('000 US$)"] > 0
].copy()

print("\n===================================")
print("HUMANITARIAN VS REPORTED DAMAGE")
print("===================================")

for col in humanitarian_models:
    correlation = damage_df[col].corr(
        damage_df["economic"],
        method="spearman"
    )

    print(f"{col}: {correlation:.4f}")

print(
    "\nRecords with positive reported damage:",
    len(damage_df)
)

print("\n===================================")
print("CORRELATIONS BY DISASTER TYPE")
print("===================================")

for disaster_type, group in damage_df.groupby(
    "Disaster Type"
):
    if len(group) >= 30:
        correlation = group["humanitarian"].corr(
            group["economic"],
            method="spearman"
        )

        print(
            f"{disaster_type}: "
            f"n={len(group)}, "
            f"correlation={correlation:.4f}"
        )


# ============================================================
# STEP 4: POSITIVE-IMPACT DISASTER STABILITY
# ============================================================

positive_df = analysis_df[
    (analysis_df["deaths_imputed"] > 0)
    | (analysis_df["affected_imputed"] > 0)
].copy()

print("\n===================================")
print("POSITIVE-IMPACT RANK CORRELATIONS")
print("===================================")

print(
    positive_df[humanitarian_models]
    .corr(method="spearman")
    .round(4)
    .to_string()
)

print("\nPositive-impact records:", len(positive_df))


# ============================================================
# STEP 5: OVERALL SEVERITY WEIGHT SENSITIVITY
# ============================================================

# First percentage = humanitarian weight
# Second percentage = economic damage weight

weights = [20, 25, 30, 40, 50, 60, 70, 80]

severity_models = []

for human_weight in weights:
    economic_weight = 100 - human_weight

    name = f"overall_{human_weight}_{economic_weight}"

    analysis_df[name] = (
        (human_weight / 100) * analysis_df["humanitarian"]
        + (economic_weight / 100) * analysis_df["economic"]
    )

    severity_models.append(name)

print("\n===================================")
print("OVERALL SEVERITY RANK CORRELATIONS")
print("===================================")

print(
    analysis_df[severity_models]
    .corr(method="spearman")
    .round(4)
    .to_string()
)

# Compare against current 25/75 model
baseline_col = "overall_25_75"

# Use a common complete-case population for every comparison.
complete_df = analysis_df.dropna(
    subset=severity_models
).copy()

print("\nComplete records:", len(complete_df))
print(
    "Excluded records:",
    len(analysis_df) - len(complete_df)
)

top_n = min(100, len(complete_df))

baseline = set(
    complete_df.nlargest(top_n, baseline_col).index
)

print("\n===================================")
print("TOP 100 OVERLAP WITH 25/75 MODEL")
print("===================================")

for col in severity_models:
    top = set(
        complete_df.nlargest(top_n, col).index
    )

    overlap = len(baseline & top)

    print(
        f"{col}: {overlap}/{top_n} "
        f"({100 * overlap / top_n:.1f}%)"
    )


# ============================================================
# STEP 6: MOST SEVERE DISASTERS UNDER CURRENT WEIGHTS
# ============================================================

print("\n===================================")
print("TOP 10 DISASTERS: 25/75 BASELINE")
print("===================================")

display_columns = [
    "DisNo.",
    "Source",
    "Country",
    "Disaster Type",
    "Start Year",
    "death_score",
    "affected_score",
    "damage_score",
    "humanitarian",
    "overall_25_75"
]

print(
    complete_df.nlargest(10, baseline_col)[
        display_columns
    ]
    .round(2)
    .to_string(index=False)
)


# ============================================================
# STEP 7: TOP 100 FREQUENCY ACROSS WEIGHTS
# ============================================================

complete_df["top100_frequency"] = 0

for col in severity_models:
    top_indices = complete_df.nlargest(
        top_n, col
    ).index

    complete_df.loc[
        top_indices, "top100_frequency"
    ] += 1

print("\n===================================")
print("TOP 100 FREQUENCY")
print("===================================")

print(
    complete_df["top100_frequency"]
    .value_counts()
    .sort_index()
    .to_string()
)

print(
    "\nDisasters appearing in every scenario:",
    (
        complete_df["top100_frequency"]
        == len(severity_models)
    ).sum()
)

# Verify that the baseline reproduces the production score.
difference = (
    complete_df["overall_25_75"]
    - complete_df["severity_score"]
).abs()

print(
    "\nMaximum difference from production severity:",
    difference.max()
)

# ============================================================
# STEP 8: IMPUTATION ROBUSTNESS CHECK
# ============================================================

print("\n===================================")
print("IMPUTATION ROBUSTNESS CHECK")
print("===================================")

# Only records with complete original impact data
reported_df = complete_df[
    (~complete_df["deaths_was_imputed"])
    & (~complete_df["affected_was_imputed"])
    & (~complete_df["damage_was_imputed"])
    & complete_df["Total Deaths"].notna()
    & complete_df["Total Affected"].notna()
    & complete_df[
        "Total Damage, Adjusted ('000 US$)"
    ].notna()
].copy()

print("All complete records:", len(complete_df))
print("Fully reported records:", len(reported_df))

# Compare the baseline against alternative weights
# within the fully reported subset.
reported_top_n = min(100, len(reported_df))

reported_baseline = set(
    reported_df.nlargest(
        reported_top_n, "overall_25_75"
    ).index
)

print("\nTop 100 overlap within reported-only records:")

for col in severity_models:
    top = set(
        reported_df.nlargest(
            reported_top_n, col
        ).index
    )

    overlap = len(reported_baseline & top)

    print(
        f"{col}: {overlap}/{reported_top_n} "
        f"({100 * overlap / reported_top_n:.1f}%)"
    )

print("\nRank correlations on reported-only records:")

print(
    reported_df[severity_models]
    .corr(method="spearman")
    .round(4)
    .to_string()
)

# How many of the original baseline top 100
# have at least one imputed impact?
baseline_top_df = complete_df.nlargest(
    100, "overall_25_75"
)

imputed_in_top100 = (
    baseline_top_df[
        [
            "deaths_was_imputed",
            "affected_was_imputed",
            "damage_was_imputed"
        ]
    ]
    .any(axis=1)
    .sum()
)

print(
    "\nBaseline top 100 with at least one imputed impact:",
    imputed_in_top100
)
