# Owner action — ClickHouse Cloud spend checkpoints

This is an account-owner console action. Database credentials and WatchTower code cannot read or
change ClickHouse Cloud billing controls.

## Values to enter

Configure notifications against **actual cumulative ClickHouse Cloud spend in USD** at:

| Checkpoint | Required response |
|---|---|
| **$100** | Pause new cost-generating tests and review service spend/credits. |
| **$200** | Stop non-essential cloud testing; continue only the minimum submission path after owner review. |
| **$300** | Hard project stop: perform no new paid ClickHouse work until the owner explicitly resolves funding. |

## Owner procedure

1. Sign in to the ClickHouse Cloud organization that owns the WatchTower service.
2. Open the organization/service **Billing**, **Usage**, or **Cost controls** area—the exact label may
   vary with the current console.
3. Confirm the selected organization and service are the WatchTower resources, not another project.
4. Add alert/checkpoint notifications for **$100**, **$200**, and **$300 USD actual cumulative
   spend** and direct them to the project owner's monitored email.
5. Do not add a personal payment method or change the service plan while doing this task.
6. Record the current cumulative spend, currency, promotional-credit balance, alert recipients, and
   configuration timestamp in the project report. Save a private screenshot that exposes no secret.
7. If the console supports only one native threshold, set **$100** first, contact ClickHouse
   hackathon support for the supported multi-threshold method, and track $200/$300 manually until it
   is configured. Do not represent manual reminders as native alerts.

These notifications do not replace manual review. At each checkpoint, stop and inspect spend before
continuing. The $300 checkpoint is the project’s ClickHouse hard-stop policy.
