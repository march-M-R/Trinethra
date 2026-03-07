# Trinetra Policy v1 - Rules

## Theft without police report
If claim_type contains THEFT and police_report is false, route to review. Hard stop.

## Claim amount thresholds
- >= 10,000: high amount signal, review depends on model + other factors
- >= 25,000: very high amount signal, elevated scrutiny