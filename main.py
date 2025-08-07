import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from notion_client import Client
from datetime import datetime, timedelta
import json

# Configuration
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
RECIPIENTS = os.getenv('RECIPIENTS').split(',')  # comma-separated emails

# Database IDs
DEV_RELEASES_DB = os.getenv('DEV_RELEASES_DB')  # For launches
DEVELOPMENT_TASKS_DB = os.getenv('DEVELOPMENT_TASKS_DB')  # For bug fixes

# Initialize Notion client
notion = Client(auth=NOTION_TOKEN)

def get_recent_launches():
    """Get completed launches from the past week"""
    one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    
    try:
        response = notion.databases.query(
            database_id=DEV_RELEASES_DB,
            filter={
                "and": [
                    {
                        "property": "Status",
                        "select": {
                            "equals": "Completed"
                        }
                    },
                    {
                        "property": "Date",
                        "date": {
                            "after": one_week_ago
                        }
                    }
                ]
            }
        )
        return response['results']
    except Exception as e:
        print(f"Error fetching recent launches: {e}")
        return []

def get_upcoming_launches():
    """Get upcoming launches for next 2 weeks"""
    today = datetime.now().isoformat()
    two_weeks_later = (datetime.now() + timedelta(days=14)).isoformat()
    
    try:
        response = notion.databases.query(
            database_id=DEV_RELEASES_DB,
            filter={
                "and": [
                    {
                        "or": [
                            {
                                "property": "Status",
                                "select": {
                                    "equals": "Upcoming"
                                }
                            },
                            {
                                "property": "Status",
                                "select": {
                                    "equals": "In Progress"
                                }
                            }
                        ]
                    },
                    {
                        "property": "Date",
                        "date": {
                            "after": today
                        }
                    },
                    {
                        "property": "Date",
                        "date": {
                            "before": two_weeks_later
                        }
                    }
                ]
            }
        )
        return response['results']
    except Exception as e:
        print(f"Error fetching upcoming launches: {e}")
        return []

def get_bug_fixes():
    """Get bug fixes from the past week"""
    one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    
    try:
        response = notion.databases.query(
            database_id=DEVELOPMENT_TASKS_DB,
            filter={
                "and": [
                    {
                        "property": "Type",
                        "select": {
                            "equals": "Bug"
                        }
                    },
                    {
                        "property": "Status",
                        "select": {
                            "equals": "Done"
                        }
                    },
                    {
                        "property": "Done Date",
                        "date": {
                            "after": one_week_ago
                        }
                    }
                ]
            }
        )
        return response['results']
    except Exception as e:
        print(f"Error fetching bug fixes: {e}")
        return []

def extract_release_data(page):
    """Extract data from a Dev Releases page"""
    properties = page['properties']
    
    # Extract Event Name (title)
    title = "Untitled"
    if 'Event Name' in properties and properties['Event Name']['title']:
        title = properties['Event Name']['title'][0]['text']['content']
    
    # Extract Description
    description = ""
    if 'Description' in properties and properties['Description']['rich_text']:
        description = properties['Description']['rich_text'][0]['text']['content']
    
    # Extract Date
    date = ""
    if 'Date' in properties and properties['Date']['date']:
        date = properties['Date']['date']['start']
    
    # Extract Status
    status = ""
    if 'Status' in properties and properties['Status']['select']:
        status = properties['Status']['select']['name']
    
    return {
        'title': title,
        'description': description,
        'date': date,
        'status': status
    }

def extract_task_data(page):
    """Extract data from a Development Tasks page"""
    properties = page['properties']
    
    # Extract Task Name (assuming it's stored in the title property)
    title = "Untitled"
    # Check for different possible title property names
    title_properties = ['Name', 'Title', 'Task', 'Task Name']
    for prop_name in title_properties:
        if prop_name in properties and properties[prop_name]['title']:
            title = properties[prop_name]['title'][0]['text']['content']
            break
    
    # If no title found in title properties, get from the page title
    if title == "Untitled" and 'title' in page:
        title = page['title'][0]['text']['content'] if page['title'] else "Untitled"
    
    # Extract Description
    description = ""
    if 'Description' in properties and properties['Description']['rich_text']:
        description = properties['Description']['rich_text'][0]['text']['content']
    
    # Extract Done Date
    date = ""
    if 'Done Date' in properties and properties['Done Date']['date']:
        date = properties['Done Date']['date']['start']
    
    # Extract Priority
    priority = ""
    if 'Priority' in properties and properties['Priority']['select']:
        priority = properties['Priority']['select']['name']
    
    return {
        'title': title,
        'description': description,
        'date': date,
        'priority': priority
    }

def format_email_content(recent_launches, upcoming_launches, bug_fixes):
    """Format data into HTML email"""
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto;">
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h1 style="color: #2c3e50; margin: 0;">Weekly Development Update</h1>
            <p style="margin: 5px 0 0 0; color: #6c757d;"><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
        </div>
        
        <h2 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 5px;">🚀 Recent Launches</h2>
        """
    
    if recent_launches:
        html_content += "<div style='background-color: #f8fff8; padding: 15px; border-radius: 5px; margin-bottom: 20px;'>"
        for launch in recent_launches:
            data = extract_release_data(launch)
            formatted_date = ""
            if data['date']:
                try:
                    date_obj = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                    formatted_date = date_obj.strftime('%B %d, %Y')
                except:
                    formatted_date = data['date']
            
            html_content += f"""
            <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #28a745;">
                <h4 style="margin: 0 0 5px 0; color: #2c3e50;">{data['title']}</h4>
                <p style="margin: 0 0 5px 0; font-size: 14px; color: #6c757d;">
                    <strong>Released:</strong> {formatted_date} | <strong>Status:</strong> {data['status']}
                </p>
                <p style="margin: 0; color: #495057;">{data['description']}</p>
            </div>
            """
        html_content += "</div>"
    else:
        html_content += "<p style='color: #6c757d; font-style: italic; background-color: #f8f9fa; padding: 15px; border-radius: 5px;'>No launches completed this week.</p>"
    
    html_content += """
        <h2 style="color: #fd7e14; border-bottom: 2px solid #fd7e14; padding-bottom: 5px;">📅 Upcoming Launches</h2>
        """
    
    if upcoming_launches:
        html_content += "<div style='background-color: #fff8f0; padding: 15px; border-radius: 5px; margin-bottom: 20px;'>"
        for launch in upcoming_launches:
            data = extract_release_data(launch)
            formatted_date = ""
            if data['date']:
                try:
                    date_obj = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                    formatted_date = date_obj.strftime('%B %d, %Y')
                except:
                    formatted_date = data['date']
            
            html_content += f"""
            <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #fd7e14;">
                <h4 style="margin: 0 0 5px 0; color: #2c3e50;">{data['title']}</h4>
                <p style="margin: 0 0 5px 0; font-size: 14px; color: #6c757d;">
                    <strong>Planned:</strong> {formatted_date} | <strong>Status:</strong> {data['status']}
                </p>
                <p style="margin: 0; color: #495057;">{data['description']}</p>
            </div>
            """
        html_content += "</div>"
    else:
        html_content += "<p style='color: #6c757d; font-style: italic; background-color: #f8f9fa; padding: 15px; border-radius: 5px;'>No upcoming launches in the next 2 weeks.</p>"
    
    html_content += """
        <h2 style="color: #dc3545; border-bottom: 2px solid #dc3545; padding-bottom: 5px;">🐛 Bug Fixes</h2>
        """
    
    if bug_fixes:
        html_content += "<div style='background-color: #fff5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px;'>"
        for fix in bug_fixes:
            data = extract_task_data(fix)
            formatted_date = ""
            if data['date']:
                try:
                    date_obj = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                    formatted_date = date_obj.strftime('%B %d, %Y')
                except:
                    formatted_date = data['date']
            
            priority_badge = ""
            if data['priority']:
                priority_color = "#6c757d"
                if data['priority'].lower() in ['high', 'critical']:
                    priority_color = "#dc3545"
                elif data['priority'].lower() == 'medium':
                    priority_color = "#fd7e14" 
                priority_badge = f"<span style='background-color: {priority_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;'>{data['priority']}</span>"
            
            html_content += f"""
            <div style="margin-bottom: 15px; padding: 10px; border-left: 4px solid #dc3545;">
                <h4 style="margin: 0 0 5px 0; color: #2c3e50;">{data['title']} {priority_badge}</h4>
                <p style="margin: 0 0 5px 0; font-size: 14px; color: #6c757d;">
                    <strong>Fixed:</strong> {formatted_date}
                </p>
                <p style="margin: 0; color: #495057;">{data['description']}</p>
            </div>
            """
        html_content += "</div>"
    else:
        html_content += "<p style='color: #6c757d; font-style: italic; background-color: #f8f9fa; padding: 15px; border-radius: 5px;'>No bug fixes completed this week.</p>"
    
    html_content += """
        <hr style="margin: 30px 0; border: none; border-top: 1px solid #e9ecef;">
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center;">
            <p style="color: #6c757d; font-size: 14px; margin: 0;">
                📊 This weekly update was automatically generated from our Notion workspace.<br>
                For questions or additional details, please reach out to the development team.
            </p>
        </div>
    </body>
    </html>
    """
    
    return html_content

def send_email(content):
    """Send the formatted email"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Weekly Development Update - {datetime.now().strftime('%B %d, %Y')}"
    msg['From'] = EMAIL_USER
    msg['To'] = ', '.join(RECIPIENTS)
    
    html_part = MIMEText(content, 'html')
    msg.attach(html_part)
    
    try:
        # Gmail SMTP configuration (adjust for other providers)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        
        # Send to each recipient
        for recipient in RECIPIENTS:
            server.send_message(msg, to_addrs=[recipient.strip()])
        
        server.quit()
        print(f"Email sent successfully to {len(RECIPIENTS)} recipients!")
        
    except Exception as e:
        print(f"Error sending email: {e}")
        raise e

def main():
    """Main function to orchestrate the email automation"""
    print("Starting weekly email automation...")
    
    try:
        print("Fetching recent launches from Dev Releases...")
        recent_launches = get_recent_launches()
        print(f"Found {len(recent_launches)} recent launches")
        
        print("Fetching upcoming launches from Dev Releases...")
        upcoming_launches = get_upcoming_launches()
        print(f"Found {len(upcoming_launches)} upcoming launches")
        
        print("Fetching bug fixes from Development Tasks...")
        bug_fixes = get_bug_fixes()
        print(f"Found {len(bug_fixes)} bug fixes")
        
        print("Formatting email content...")
        email_content = format_email_content(recent_launches, upcoming_launches, bug_fixes)
        
        print("Sending email...")
        send_email(email_content)
        
        print("Weekly email automation completed successfully!")
        
    except Exception as e:
        print(f"Error in main execution: {e}")
        raise e

if __name__ == "__main__":
    main()
