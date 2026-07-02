# Example server env file — copy to runtime/secrets/fengji_api.env on the deploy host.
# DO NOT commit real values. DO NOT paste into chat or docs.
#
# DATABASE_URL=postgresql+psycopg://fengji:***@127.0.0.1:5432/fengji
# FENGJI_JWT_SECRET=<random 32+ chars>
# FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=0
# FENGJI_SUBSCRIPTION_REDEEM_CODES=
# FENGJI_PAYMENT_WEBHOOK_SECRET=
# FENGJI_SUBSCRIPTION_PERIOD_DAYS=30
# CORS_ORIGINS=https://your-domain.example

Write-Host @"
Copy this template to:
  C:\Users\Administrator\quant_futures\runtime\secrets\fengji_api.env

Required for W17-prod:
  DATABASE_URL
  FENGJI_JWT_SECRET  (>= 32 bytes; never commit)

Optional:
  FENGJI_ALLOW_MANUAL_SUBSCRIPTION_CONFIRM=1  (dev/manual confirm only)
  FENGJI_SUBSCRIPTION_REDEEM_CODES=standard:CODE,pro:CODE
  FENGJI_PAYMENT_WEBHOOK_SECRET=<webhook hmac secret>
"@
