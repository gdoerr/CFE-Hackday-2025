import streamlit as st
import os
from datetime import datetime, timedelta
from jira import JIRA
from dotenv import load_dotenv
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import plotly.graph_objects as go

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Jira Ticket Analytics",
    page_icon="📊",
    layout="wide"
)

# Title and description
st.title("Jira Ticket Analytics")
st.markdown("""
This dashboard shows ticket information and points worked by engineers for March 2025.
""")

# Jira connection function
def connect_to_jira():
    try:
        jira_url = os.getenv('JIRA_URL')
        jira_email = os.getenv('JIRA_EMAIL')
        jira_token = os.getenv('JIRA_API_TOKEN')
        
        # Validate environment variables
        if not jira_url or not jira_email or not jira_token:
            st.error("Missing environment variables. Please check your .env file contains:")
            st.error("JIRA_URL, JIRA_EMAIL, and JIRA_API_TOKEN")
            return None
            
        # Remove trailing slash from URL if present
        jira_url = jira_url.rstrip('/')
        
        # First try a direct API call to verify credentials
        auth = HTTPBasicAuth(jira_email, jira_token)
        response = requests.get(
            f"{jira_url}/rest/api/3/myself",
            auth=auth
        )
        
        if response.status_code == 401:
            st.error("Authentication failed (401 Unauthorized). Please check your credentials.")
            return None
        elif response.status_code != 200:
            st.error(f"Failed to authenticate with Jira. Status code: {response.status_code}")
            return None
            
        jira = JIRA(
            server=jira_url,
            basic_auth=(jira_email, jira_token)
        )
        return jira
    except Exception as e:
        st.error(f"Failed to connect to Jira: {str(e)}")
        return None

# Function to get all projects
def get_projects(jira):
    try:
        # Try direct API call first
        jira_url = os.getenv('JIRA_URL').rstrip('/')
        jira_email = os.getenv('JIRA_EMAIL')
        jira_token = os.getenv('JIRA_API_TOKEN')
        
        auth = HTTPBasicAuth(jira_email, jira_token)
        response = requests.get(
            f"{jira_url}/rest/api/3/project",
            auth=auth
        )
        
        if response.status_code == 401:
            st.error("Authentication failed (401 Unauthorized) when fetching projects")
            return {}
        elif response.status_code != 200:
            st.error(f"Failed to fetch projects. Status code: {response.status_code}")
            return {}
            
        projects_data = response.json()
        # Filter projects that start with "ASA"
        asa_projects = [project for project in projects_data if project['key'].startswith('ASA')]
        
        # Create project dictionary
        project_dict = {project['key']: project['name'] for project in asa_projects}
        
        if not project_dict:
            st.warning("No ASA projects found. Please check if you have access to any ASA projects.")
        
        return project_dict
    except Exception as e:
        st.error(f"Failed to fetch projects: {str(e)}")
        return {}

# Function to fetch tickets for a specific project
def fetch_tickets_for_project(jira, project_key, start_date, end_date):
    jql = f'project = {project_key} AND updated >= "{start_date}" AND updated <= "{end_date}" ORDER BY updated DESC'
    try:
        # Include comments in the initial fetch to avoid multiple API calls
        issues = jira.search_issues(jql, maxResults=1000, expand='comments')
        return issues
    except Exception as e:
        st.error(f"Failed to fetch tickets for project {project_key}: {str(e)}")
        return []

# Function to fetch all tickets from all ASA projects
def fetch_all_asa_tickets(jira, project_keys, start_date, end_date):
    all_issues = []
    for project_key in project_keys:
        issues = fetch_tickets_for_project(jira, project_key, start_date, end_date)
        all_issues.extend(issues)
    return all_issues

# Function to get user email from Jira
def get_user_email(jira, display_name):
    try:
        # In GDPR strict mode, we can't search by username/display name
        # Instead, we'll try to get the user from the assignee field of an issue
        # This is a workaround since we can't directly search for users
        
        # First, try to find an issue assigned to this person
        jql = f'assignee = "{display_name}" ORDER BY updated DESC'
        issues = jira.search_issues(jql, maxResults=1)
        
        if issues:
            # Get the assignee's accountId from the first issue
            assignee = issues[0].fields.assignee
            if assignee:
                # Now use the accountId to get the user details
                user = jira.user(assignee.accountId)
                return user.emailAddress
        
        # If we couldn't find an issue assigned to this person,
        # try to find an issue with a comment from this person
        jql = f'comment ~ "{display_name}" ORDER BY updated DESC'
        issues = jira.search_issues(jql, maxResults=1)
        
        if issues:
            # Get the comment author's accountId
            comments = jira.comments(issues[0])
            for comment in comments:
                if comment.author.displayName == display_name:
                    user = jira.user(comment.author.accountId)
                    return user.emailAddress
        
        return None
    except Exception as e:
        st.error(f"Failed to get email for user {display_name}: {str(e)}")
        return None

# Function to calculate days in "In Progress" status
def calculate_days_in_progress(jira, issue, start_date, end_date):
    try:
        # Get the changelog for the issue
        changelog = jira.issue(issue.key, expand='changelog').changelog
        
        # Initialize variables
        days_in_progress = 0
        current_status = None
        status_start_date = None
        
        # Convert start_date and end_date to datetime objects for comparison
        # Make them timezone-aware by using UTC
        start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=None)
        end_datetime = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=None)
        
        # Process the changelog entries
        for history in changelog.histories:
            for item in history.items:
                if item.field == 'status':
                    # Get the timestamp of the change
                    # Parse the timestamp and remove timezone info for consistent comparison
                    change_time_str = history.created
                    if '+' in change_time_str or '-' in change_time_str:
                        # If the timestamp has timezone info, parse it and remove the timezone
                        change_time = datetime.strptime(change_time_str, '%Y-%m-%dT%H:%M:%S.%f%z')
                        change_time = change_time.replace(tzinfo=None)
                    else:
                        # If no timezone info, parse as is
                        change_time = datetime.strptime(change_time_str, '%Y-%m-%dT%H:%M:%S.%f')
                    
                    # If this is before our start date, just update the current status
                    if change_time < start_datetime:
                        current_status = item.toString
                        continue
                    
                    # If we were in "In Progress" status, calculate days
                    if current_status == "In Progress" and status_start_date:
                        # Calculate the end of the period (either the change time or our end date)
                        period_end = min(change_time, end_datetime)
                        # Calculate the start of the period (either the status start or our start date)
                        period_start = max(status_start_date, start_datetime)
                        # Calculate days (add 1 to include both start and end days)
                        days = (period_end - period_start).days + 1
                        days_in_progress += max(0, days)
                    
                    # Update current status and start date
                    current_status = item.toString
                    status_start_date = change_time
        
        # Check if the issue is still in "In Progress" status
        if current_status == "In Progress" and status_start_date:
            # Calculate days from status start to our end date
            # Use current time without timezone info
            current_time = datetime.now().replace(tzinfo=None)
            period_end = min(current_time, end_datetime)
            period_start = max(status_start_date, start_datetime)
            days = (period_end - period_start).days + 1
            days_in_progress += max(0, days)
        
        return days_in_progress
    except Exception as e:
        st.error(f"Failed to calculate days in progress for {issue.key}: {str(e)}")
        return 0

# Function to process tickets and get comments
def process_tickets_with_comments(issues, jira, start_date, end_date):
    tickets_data = []
    
    # Get base Jira URL for creating issue links
    jira_url = os.getenv('JIRA_URL').rstrip('/')
    
    for issue in issues:
        # Comments are already included in the issue object
        comment_count = len(issue.fields.comment.comments) if hasattr(issue.fields, 'comment') else 0
        
        # Calculate days in progress
        days_in_progress = calculate_days_in_progress(jira, issue, start_date, end_date)
        
        # Get story points
        story_points = issue.fields.customfield_10016 if hasattr(issue.fields, 'customfield_10016') else 0
        
        # Get assignee
        assignee = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"
        
        # Get status
        status = issue.fields.status.name
        
        # Get the last modified date
        last_modified = issue.fields.updated
        
        # Create issue URL
        issue_url = f"{jira_url}/browse/{issue.key}"
        
        tickets_data.append({
            'Key': issue.key,
            'Summary': issue.fields.summary,
            'Status': status,
            'Assignee': assignee,
            'Story Points': story_points,
            'Days in Progress': days_in_progress,
            'Comment Count': comment_count,
            'Last Modified': last_modified,
            'URL': issue_url
        })
    
    return pd.DataFrame(tickets_data)

# Function to create person summary
def create_person_summary(df, jira, issues):
    # Get unique people (excluding "Unassigned")
    all_people = set()
    all_people.update([person for person in df['Assignee'].unique() if person != 'Unassigned'])
    
    # Create a dictionary to store comment counts by person
    comment_counts = {}
    
    # Process all issues to count comments by person
    for _, row in df.iterrows():
        issue_key = row['Key']
        # Get the issue object that was previously fetched
        issue = next((issue for issue in issues if issue.key == issue_key), None)
        if issue and hasattr(issue.fields, 'comment'):
            for comment in issue.fields.comment.comments:
                commenter = comment.author.displayName
                all_people.add(commenter)
                comment_counts[commenter] = comment_counts.get(commenter, 0) + 1
    
    # Create summary data
    summary_data = []
    for person in sorted(all_people):
        # Count tickets assigned to this person (excluding "Unassigned")
        assigned_tickets = len(df[(df['Assignee'] == person) & (df['Assignee'] != 'Unassigned')])
        
        # Get comment count from our pre-calculated dictionary
        comments_made = comment_counts.get(person, 0)
        
        # Calculate total days in progress for this person's assigned tickets
        days_in_progress = df[df['Assignee'] == person]['Days in Progress'].sum()
        
        # Get email for this person
        email = get_user_email(jira, person)
        
        summary_data.append({
            'Person': person,
            'Email': email,
            'Tickets Assigned': assigned_tickets,
            'Comments Made': comments_made,
            'Days In Progress': days_in_progress,
            'Total Activity': assigned_tickets + comments_made
        })
    
    return pd.DataFrame(summary_data)

# Main app logic
def main():
    # Connect to Jira
    jira = connect_to_jira()
    if not jira:
        st.error(f"Failed to connect to Jira")
        st.stop()

    # Get projects
    projects = get_projects(jira)
    if not projects:
        st.error(f"Failed to fetch projects")
        st.stop()

    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime(2025, 3, 1))
    with col2:
        end_date = st.date_input("End Date", datetime(2025, 3, 31))

    # Fetch and display data
    if st.button("Fetch All ASA Tickets"):
        with st.spinner("Fetching tickets from all ASA projects..."):
            # Fetch tickets from all ASA projects
            all_issues = fetch_all_asa_tickets(jira, list(projects.keys()), start_date, end_date)
            
            if all_issues:
                # Process tickets and get comments
                df = process_tickets_with_comments(all_issues, jira, start_date, end_date)
                
                # Display summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Tickets", len(df))
                with col2:
                    st.metric("Total Story Points", df['Story Points'].sum())
                with col3:
                    st.metric("Total Comments", df['Comment Count'].sum())
                with col4:
                    st.metric("Total Days In Progress", df['Days in Progress'].sum())
                
                # Create and display person summary
                st.subheader("Summary by Person")
                person_summary = create_person_summary(df, jira, all_issues)
                st.dataframe(person_summary, use_container_width=True)
                
                # Display person summary chart
                st.subheader("Activity by Person")
                person_activity = person_summary.set_index('Person')[['Tickets Assigned', 'Comments Made', 'Days In Progress']]
                fig = go.Figure(data=[
                    go.Bar(name='Tickets Assigned', x=person_activity.index, y=person_activity['Tickets Assigned']),
                    go.Bar(name='Comments Made', x=person_activity.index, y=person_activity['Comments Made']),
                    go.Bar(name='Days In Progress', x=person_activity.index, y=person_activity['Days In Progress'])
                ])
                fig.update_layout(
                    title='Activity by Person',
                    xaxis_title='Person',
                    yaxis_title='Count',
                    barmode='group'
                )
                st.plotly_chart(fig)
                
                # Display tickets table with a separate column for links
                st.subheader("Ticket Details")
                
                # Create a copy of the dataframe for display
                display_df = df.copy()
                
                # Store the URL in a separate column
                display_df = display_df.copy()
                
                # Display the dataframe with a hyperlink column
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    column_config={
                        "Key": st.column_config.TextColumn("Key"),
                        "URL": st.column_config.LinkColumn("Jira Link", display_text="View in Jira")
                    }
                )
            else:
                st.warning("No tickets found for the selected date range.")

if __name__ == "__main__":
    main() 