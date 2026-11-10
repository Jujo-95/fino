# Fino

### Know what to do next with your cloud spending.

Fino is an AI FinOps copilot that turns cloud billing data into clear, actionable tasks. It helps teams understand where their money goes, investigate unexpected costs, and work through improvements with a consultant they can talk to.

You do not need to be a FinOps expert. Fino helps you ask the right questions, gather missing information, and take the next step.

## From cost visibility to continuous improvement

Cloud dashboards show you what happened. Fino helps you figure out what to do about it.

- **Understand your spending.** Identify the services, accounts, and teams behind your costs.
- **Investigate unexpected changes.** Understand whether a spike needs action or follow-up.
- **Find optimization opportunities.** Review usage, budgets, forecasts, and commitments with specialized assistance.
- **Get a practical next step.** Work through prioritized tickets rather than interpreting another dashboard alone.
- **Follow through.** Record decisions, track changes, and check subsequent data before treating an improvement as verified.

## How it works

### 1. Bring your data and business context

Connect supported cloud billing sources or import FOCUS-format files. Add the context that makes the numbers meaningful: who owns a project, what budget matters, or whether a deployment was planned.

If information is missing, Fino helps you identify what to provide and who to ask.

### 2. See your next step

Findings and onboarding requirements become tickets. Focus mode guides you through an objective; list mode lets you browse, filter, and investigate your tickets.

The workflow follows the FinOps phases: **Inform, Optimize, and Operate**.

### 3. Work through it with Fino

Ask a question in plain language or open a ticket's dedicated conversation. Fino consults specialist agents when needed and uses billing evidence, previous analyses, and your recorded decisions to guide the response.

> “What should I work on today?”
>
> “Help me resolve this ticket. What information do you need?”
>
> “My team says this spike was a one-off deployment. What should we do next?”

Fino can prepare ticket updates and follow-up plans for approval, helping you keep the conversation and the task connected.

### 4. Verify what changed

A recorded action is not the same as a verified result. Tickets can stay under observation while new data arrives, so subsequent analysis can assess whether the issue persists or the closure criteria have been met.

## One workspace for the whole process

| Area | What you can do |
| --- | --- |
| **Tickets** | Follow guided objectives, review priorities, and see completed work. |
| **Fino and its team** | Ask questions, investigate findings, and return to ticket conversations. |
| **Analysis** | Update the analysis and review previous executions and their evidence. |
| **Connections** | Manage supported billing sources, business context, tools, and AI providers. |

## Built for teams that need guidance, not more dashboards

Fino is intended for engineering, finance, and business teams that want a practical way to improve cloud cost management without requiring everyone to learn FinOps first.

It combines structured analysis with conversational support. Recommendations depend on the available evidence, and missing information should remain visible rather than being presented as certainty. Fino does not guarantee savings.

The methodology draws on the [FinOps Framework](https://www.finops.org/framework/) and uses [FOCUS](https://focus.finops.org/) billing data to support consistent analysis across cloud providers.

## Try it locally

Fino is currently a local pilot. The application interface is primarily in Spanish.

Requirements: Python 3.11+, uv, Node.js 20.19+, and npm.

```bash
cp .env.example .env
# Configure your AI provider credentials in .env.
bash run.sh
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). To start with labeled synthetic data, use `bash run.sh --demo`. Preparing synthetic data does not automatically call an AI model.

Provider credentials and customer workspaces are excluded from this repository. Review deployment requirements before exposing the application publicly.

## Learn more

- [Fino workspace](docs/23-FINO-WORKSPACE.md)
- [Remote data analysis and daily jobs](docs/22-REMOTE-ANALYSIS-AND-DAILY-JOBS.md)
- [Ticket lifecycle and verification](docs/30-TASK-LIFECYCLE.md)
- [Synthetic data laboratory](docs/11-SYNTHETIC-S3-LAB.md)
- [Production job considerations](docs/production-jobs.md)
- [Technical documentation](docs/) and [developer instructions](AGENTS.md)

Some technical documents remain in Spanish; early specifications describe historical designs.
