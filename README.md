# Jira Ticket Analytics

A Streamlit dashboard for visualizing and analyzing Jira ticket data.

## Features

- Display ticket information and points worked by engineers
- Summarize activity by person (tickets assigned, comments made, days in progress)
- Interactive data visualizations
- Direct links to Jira tickets
- stubs exist to connect to Databricks to eventually push the data there

## Requirements

- Python 3.8+
- Jira account with API access

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   uv add -r requirements.txt
   ```

## Configuration

Create a `.env` file in the project root with your Jira credentials:

```
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-api-token
```

To create a Jira API token:
1. Log in to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy the token to your `.env` file

## Usage

Run the Streamlit app:

```bash
uv run streamlit run jira_tickets.py
```

In the app:
1. Select date range for analysis
2. Click "Fetch All ASA Tickets" to load data
3. View summary metrics, person activity, and ticket details

## Customization

The app is configured to show ASA project tickets. To modify for different projects, edit the `get_projects` function in `jira_tickets.py`. 