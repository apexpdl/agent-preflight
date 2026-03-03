"""Basic usage example."""

from agent_preflight import Preflight

pf = Preflight(cost_limit=1.00)


@pf.intercept
def search_contacts(query):
    return [{"name": "Sarah", "email": "sarah@acme.com"}]


@pf.intercept
def send_email(to, subject, body):
    print(f"Sending email to {to}")


@pf.intercept
def update_database(query):
    print(f"Running: {query}")


@pf.intercept
def delete_old_records(table, before_date):
    print(f"Deleting from {table}")


def my_agent_workflow():
    search_contacts("Sarah from Acme")
    send_email(to="sarah@acme.com", subject="Q3 Report", body="Hi Sarah...")
    update_database("UPDATE invoices SET status=sent WHERE quarter=Q3")
    delete_old_records("temp_reports", before_date="2025-01-01")


if __name__ == "__main__":
    plan = pf.dry_run(my_agent_workflow, task="Send Q3 report to Sarah")
    print(pf.format(plan))
    print(f"Actions: {len(plan.actions)}, Risk: {plan.overall_risk.value}")
