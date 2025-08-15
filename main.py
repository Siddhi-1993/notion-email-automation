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
EMAIL_SIGNATURE = os.getenv('EMAIL_SIGNATURE', '')  # Optional email signature

# Database IDs
DEV_RELEASES_DB = os.getenv('DEV_RELEASES_DB')  # For launches
DEVELOPMENT_TASKS_DB = os.getenv('DEVELOPMENT_TASKS_DB')  # For bug fixes

# Fallback recipients if no recipients found in Dev Releases database
FALLBACK_RECIPIENTS = [email.strip() for email in os.getenv('RECIPIENTS', '').split(',') if email.strip()] if os.getenv('RECIPIENTS') else []
FALLBACK_CC_RECIPIENTS = [email.strip() for email in os.getenv('CC_RECIPIENTS', '').split(',') if email.strip()] if os.getenv('CC_RECIPIENTS') else []

# Initialize Notion client
notion = Client(auth=NOTION_TOKEN)

def get_recipients_from_releases():
    """Get email recipients from Dev Releases database based on recent/upcoming items"""
    try:
        # Get recent launches (completed in last 7 days)
        one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        today = datetime.now().isoformat()
        two_weeks_later = (datetime.now() + timedelta(days=14)).isoformat()
        
        # Query for items that should trigger notifications
        response = notion.databases.query(
            database_id=DEV_RELEASES_DB,
            filter={
                "or": [
                    # Recent completed items
                    {
                        "and": [
                            {
                                "property": "Status",
                                "status": {
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
                    },
                    # Upcoming items
                    {
                        "and": [
                            {
                                "or": [
                                    {
                                        "property": "Status",
                                        "status": {
                                            "equals": "Upcoming"
                                        }
                                    },
                                    {
                                        "property": "Status",
                                        "status": {
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
                ]
            }
        )
        
        to_recipients = set()  # Use set to avoid duplicates
        cc_recipients = set()
        
        for item in response['results']:
            properties = item['properties']
            
            # Extract To recipients
            if 'Email To' in properties:
                if properties['Email To'].get('rich_text'):
                    # Handle rich text format
                    email_text = ""
                    for text_item in properties['Email To']['rich_text']:
                        email_text += text_item['text']['content']
                    
                    if email_text.strip():
                        emails = email_text.split(',')
                        for email in emails:
                            email = email.strip()
                            if email and '@' in email:
                                to_recipients.add(email)
                                
                elif properties['Email To'].get('email'):
                    # Handle email property format
                    email = properties['Email To']['email'].strip()
                    if email and '@' in email:
                        to_recipients.add(email)
            
            # Extract CC recipients  
            if 'Email CC' in properties:
                if properties['Email CC'].get('rich_text'):
                    # Handle rich text format
                    email_text = ""
                    for text_item in properties['Email CC']['rich_text']:
                        email_text += text_item['text']['content']
                    
                    if email_text.strip():
                        emails = email_text.split(',')
                        for email in emails:
                            email = email.strip()
                            if email and '@' in email:
                                cc_recipients.add(email)
                                
                elif properties['Email CC'].get('email'):
                    # Handle email property format
                    email = properties['Email CC']['email'].strip()
                    if email and '@' in email:
                        cc_recipients.add(email)
        
        # Convert sets back to lists
        to_list = list(to_recipients)
        cc_list = list(cc_recipients)
        
        print(f"Recipients from Dev Releases - To: {len(to_list)}, CC: {len(cc_list)}")
        print(f"To recipients: {to_list}")
        print(f"CC recipients: {cc_list}")
        
        # If no recipients found in database, use fallback
        if not to_list and not cc_list:
            print("No recipients found in Dev Releases, using fallback")
            return FALLBACK_RECIPIENTS, FALLBACK_CC_RECIPIENTS
            
        return to_list, cc_list
        
    except Exception as e:
        print(f"Error fetching recipients from Dev Releases: {e}")
        print("Falling back to GitHub secrets")
        return FALLBACK_RECIPIENTS, FALLBACK_CC_RECIPIENTS

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
                        "status": {
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
        print(f"DEBUG: Recent launches query returned {len(response['results'])} results")
        if response['results']:
            print(f"DEBUG: First result: {json.dumps(response['results'][0], indent=2)}")
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
                                "status": {
                                    "equals": "Upcoming"
                                }
                            },
                            {
                                "property": "Status",
                                "status": {
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
        print(f"DEBUG: Upcoming launches query returned {len(response['results'])} results")
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
                        "status": {
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
        print(f"DEBUG: Bug fixes query returned {len(response['results'])} results")
        if response['results']:
            print(f"DEBUG: First bug fix result: {json.dumps(response['results'][0], indent=2)}")
        return response['results']
    except Exception as e:
        print(f"Error fetching bug fixes: {e}")
        return []

def extract_release_data(page):
    """Extract data from a Dev Releases page"""
    properties = page['properties']
    
    # Extract Event Name (title) - this is actually a property in Dev Releases
    title = "Untitled"
    if 'Event Name' in properties and properties['Event Name'].get('title'):
        try:
            if len(properties['Event Name']['title']) > 0:
                title = properties['Event Name']['title'][0]['text']['content']
        except (KeyError, IndexError, TypeError):
            title = f"Event {page['id'][-8:]}"
    
    # Extract Description
    description = ""
    if 'Description' in properties and properties['Description'].get('rich_text'):
        try:
            if len(properties['Description']['rich_text']) > 0:
                description = properties['Description']['rich_text'][0]['text']['content']
        except (KeyError, IndexError, TypeError):
            description = ""
    
    # Extract Date
    date = ""
    if 'Date' in properties and properties['Date'].get('date'):
        try:
            date = properties['Date']['date']['start']
        except (KeyError, TypeError):
            date = ""
    
    # Extract Status
    status = ""
    if 'Status' in properties and properties['Status'].get('status'):
        try:
            status = properties['Status']['status']['name']
        except (KeyError, TypeError):
            status = ""
    
    print(f"DEBUG: Extracted release data - Title: {title}, Date: {date}, Status: {status}")
    
    return {
        'title': title,
        'description': description,
        'date': date,
        'status': status
    }

def extract_task_data(page):
    """Extract data from a Development Tasks page"""
    properties = page['properties']
    
    # Extract the title - get it directly from the page object
    title = "Untitled"
    
    # Method 1: Get from page object title (this is where Notion stores the page title)
    if 'properties' in page:
        # Look for the title property (the one with type 'title')
        for prop_name, prop_data in properties.items():
            if prop_data.get('type') == 'title':
                if prop_data.get('title') and len(prop_data['title']) > 0:
                    try:
                        title = prop_data['title'][0]['text']['content']
                    except (KeyError, IndexError, TypeError):
                        title = f"Task {page['id'][-8:]}"
                    break
    
    # Method 2: Fallback to page ID if properties don't work
    if title == "Untitled":
        title = f"Task {page['id'][-8:]}"  # Use last 8 chars of ID
    
    # Extract Description
    description = ""
    if 'Description' in properties and properties['Description'].get('rich_text'):
        try:
            if len(properties['Description']['rich_text']) > 0:
                description = properties['Description']['rich_text'][0]['text']['content']
        except (KeyError, IndexError, TypeError):
            description = ""
    
    # Extract Done Date
    date = ""
    if 'Done Date' in properties and properties['Done Date'].get('date'):
        try:
            date = properties['Done Date']['date']['start']
        except (KeyError, TypeError):
            date = ""
    
    # Extract Priority
    priority = ""
    if 'Priority' in properties and properties['Priority'].get('select'):
        try:
            priority = properties['Priority']['select']['name']
        except (KeyError, TypeError):
            priority = ""
    
    print(f"DEBUG: Extracted task data - Title: {title}, Date: {date}, Priority: {priority}")
    
    return {
        'title': title,
        'description': description,
        'date': date,
        'priority': priority
    }

def load_signature():
    """Load email signature from file if it exists"""
    try:
        # Try to read signature file from the repository
        signature_files = ['signature.html', 'signature.txt', 'email-signature.html']
        
        for filename in signature_files:
            try:
                with open(filename, 'r', encoding='utf-8') as file:
                    signature_content = file.read().strip()
                    if signature_content:
                        print(f"Loaded signature from {filename}")
                        return signature_content
            except FileNotFoundError:
                continue
        
        # Fallback to environment variable
        if EMAIL_SIGNATURE:
            return EMAIL_SIGNATURE.replace('\\n', '<br>')
        
        return ""
    except Exception as e:
        print(f"Error loading signature: {e}")
        return EMAIL_SIGNATURE.replace('\\n', '<br>') if EMAIL_SIGNATURE else ""

def format_email_content(recent_launches, upcoming_launches, bug_fixes):
    """Format data into HTML email"""
    
    # Load signature
    signature_content = load_signature()
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto;">
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h1 style="color: #2c3e50; margin: 0;">Weekly Development Update</h1>
            <p style="margin: 5px 0 0 0; color: #6c757d;"><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
        </div>
        
        <h2 style="color: #28a745; border-bottom: 2px solid #28a745; padding-bottom: 5px;">🚀 Recent Launches ({len(recent_launches)} items)</h2>
        """
    
    if recent_launches:
        html_content += "<div style='background-color: #f8fff8; padding: 15px; border-radius: 5px; margin-bottom: 20px;'>"
        for launch in recent_launches:
            data = extract_release_data(launch)
            formatted_date = ""
            if data['date']:
                try:
                    date_obj = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                    formatted_date = date_obj.strftime('%B %d, %Y at %I:%M %p')
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
    
    html_content += f"""
        <h2 style="color: #fd7e14; border-bottom: 2px solid #fd7e14; padding-bottom: 5px;">📅 Upcoming Launches ({len(upcoming_launches)} items)</h2>
        """
    
    if upcoming_launches:
        html_content += "<div style='background-color: #fff8f0; padding: 15px; border-radius: 5px; margin-bottom: 20px;'>"
        for launch in upcoming_launches:
            data = extract_release_data(launch)
            formatted_date = ""
            if data['date']:
                try:
                    date_obj = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                    formatted_date = date_obj.strftime('%B %d, %Y at %I:%M %p')
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
    
    html_content += f"""
        <h2 style="color: #dc3545; border-bottom: 2px solid #dc3545; padding-bottom: 5px;">🐛 Bug Fixes ({len(bug_fixes)} items)</h2>
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
        </div>"""
    
    # Add signature if provided
    if signature_content:
        html_content += f"""
        <div style="margin-top: 30px; padding-top: 20px; border-top: 2px solid #e9ecef;">
            <div style="font-family: Arial, sans-serif; color: #495057;">
                {signature_content}
            </div>
        </div>"""
    
    html_content += """
    </body>
    </html>
    """
    
    return html_content

def send_email(content):
    """Send the formatted email"""
    # Get recipients from Dev Releases database
    recipients, cc_recipients = get_recipients_from_releases()
    
    if not recipients and not cc_recipients:
        print("No recipients configured!")
        return
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Weekly Development Release Notes - {datetime.now().strftime('%B %d, %Y')}"
    msg['From'] = EMAIL_USER
    
    # Set To and CC recipients
    if recipients:
        msg['To'] = ', '.join(recipients)
    if cc_recipients:
        msg['CC'] = ', '.join(cc_recipients)
    
    html_part = MIMEText(content, 'html')
    msg.attach(html_part)
    
    # Combine all recipients for actual sending
    all_recipients = []
    if recipients:
        all_recipients.extend([email.strip() for email in recipients])
    if cc_recipients:
        all_recipients.extend([email.strip() for email in cc_recipients])
    
    try:
        # Gmail SMTP configuration (adjust for other providers)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        
        # Send to all recipients (both To and CC)
        if all_recipients:
            server.send_message(msg, to_addrs=all_recipients)
        
        server.quit()
        print(f"Email sent successfully!")
        print(f"To: {', '.join(recipients) if recipients else 'None'}")
        print(f"CC: {', '.join(cc_recipients) if cc_recipients else 'None'}")
        print(f"Total recipients: {len(all_recipients)}")
        
    except Exception as e:
        print(f"Error sending email: {e}")
        raise e

def main():
    """Main function to orchestrate the email automation"""
    print("Starting weekly email automation...")
    print(f"Current date/time: {datetime.now().isoformat()}")
    print(f"Looking for items after: {(datetime.now() - timedelta(days=7)).isoformat()}")
    
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
