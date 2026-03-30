# Architecture Design: Real-time Credit Risk Check

### What I'd build
Our current setup extracts deal data fine, so I wouldn't mess with that. The gap is we only catch credit issues *after* a deal is done. 

To solve this, I'd plug a risk check into the pipeline right after extraction, before confirming the deal. 

We need three pieces:
1. A counterparty ledger in the database tracking open exposure for clients. We can backfill this from historical data.
2. An evaluator function running during the pipeline. It grabs the buyer's current exposure, adds the new deal size, and checks it against their credit limit.
3. A simple alerter. If a deal exceeds a limit, it instantly emails the trading team to intervene. 

I'd keep this synchronous and in-process for now. No need to spin up separate microservices or queues until we hit actual scaling bottlenecks.

### Week 1 priority
The smallest thing we can do is getting the signal working. 

For week one, I'd skip building any UI. I'd seed the counterparty table, hardcode strict limits in a config file, and wire up basic email alerts. 
By Friday, the deals team should receive plain-text emails saying: "Deal ET-1234 pushes Meridian Energy to 90% of their limit — please review".

### Key risks
- **Stale data**: If we don't clear settled deals from the ledger, exposure numbers will keep growing and we'll flag safe deals. We absolutely need a daily cron job to clean the ledger.
- **Alert fatigue**: If we spam the team with false alarms, they'll just set up an Outlook rule to trash them. We must start strict and loosen based on feedback.
- **Bad extractions**: If the LLM hallucinates a crazy volume or gets the buyer's name wrong, the check fails. Every alert must link to the raw memo so humans can eyeball it.

### What I'd clarify first
I need to sit down with the risk team and pin down exactly how they define "exposure". Is it a simple sum of the open volume? Or do we calculate netting, mark-to-market, and delivery windows? 

If it's a simple sum, the data model is trivial. If we need netting across buy and sell positions, the schema gets complex. I'd definitely nail that down before writing code.
