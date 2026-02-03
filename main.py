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
                            "after": today,
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
        return response['results']
    except Exception as e:
        print(f"Error fetching bug fixes: {e}")
        return []

def get_recipients_for_item(item):
    """Extract email recipients from a single item"""
    properties = item['properties']
    to_recipients = set()
    cc_recipients = set()
    
    # Extract To recipients
    if 'Email To' in properties:
        if properties['Email To'].get('rich_text'):
            email_text = ""
            for text_item in properties['Email To']['rich_text']:
                email_text += text_item['text']['content']
            
            if email_text.strip():
                emails = [e.strip() for e in email_text.split(',')]
                for email in emails:
                    if email and '@' in email and '.' in email:
                        email = email.replace(' ', '')
                        to_recipients.add(email)
                        
        elif properties['Email To'].get('email'):
            email = properties['Email To']['email'].strip()
            if email and '@' in email:
                to_recipients.add(email)
    
    # Extract CC recipients  
    if 'Email CC' in properties:
        if properties['Email CC'].get('rich_text'):
            email_text = ""
            for text_item in properties['Email CC']['rich_text']:
                email_text += text_item['text']['content']
            
            if email_text.strip():
                emails = [e.strip() for e in email_text.split(',')]
                for email in emails:
                    if email and '@' in email and '.' in email:
                        email = email.replace(' ', '')
                        cc_recipients.add(email)
                        
        elif properties['Email CC'].get('email'):
            email = properties['Email CC']['email'].strip()
            if email and '@' in email:
                cc_recipients.add(email)
    
    return list(to_recipients), list(cc_recipients)

def group_items_by_recipient(recent_launches, upcoming_launches, bug_fixes):
    """Group all items by their recipients - launches are personalized, bug fixes go to everyone"""
    recipient_data = {}  # {email: {'recent': [], 'upcoming': [], 'bugs': [], 'is_cc': bool}}
    
    # Process recent launches - personalized to stakeholders
    for item in recent_launches:
        to_list, cc_list = get_recipients_for_item(item)
        
        for email in to_list:
            if email not in recipient_data:
                recipient_data[email] = {'recent': [], 'upcoming': [], 'bugs': [], 'is_cc': False}
            recipient_data[email]['recent'].append(item)
        
        for email in cc_list:
            if email not in recipient_data:
                recipient_data[email] = {'recent': [], 'upcoming': [], 'bugs': [], 'is_cc': True}
            else:
                recipient_data[email]['is_cc'] = True
            recipient_data[email]['recent'].append(item)
    
    # Process upcoming launches - personalized to stakeholders
    for item in upcoming_launches:
        to_list, cc_list = get_recipients_for_item(item)
        
        for email in to_list:
            if email not in recipient_data:
                recipient_data[email] = {'recent': [], 'upcoming': [], 'bugs': [], 'is_cc': False}
            recipient_data[email]['upcoming'].append(item)
        
        for email in cc_list:
            if email not in recipient_data:
                recipient_data[email] = {'recent': [], 'upcoming': [], 'bugs': [], 'is_cc': True}
            else:
                recipient_data[email]['is_cc'] = True
            recipient_data[email]['upcoming'].append(item)
    
    # Bug fixes - send ALL bug fixes to ALL stakeholders who have any launches
    # This ensures everyone gets the same bug fix information
    for email in recipient_data.keys():
        recipient_data[email]['bugs'] = bug_fixes  # All bug fixes to everyone
    
    return recipient_data

def extract_release_data(page):
    """Extract data from a Dev Releases page"""
    properties = page['properties']
    
    # Extract Event Name (title)
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
    
    return {
        'title': title,
        'description': description,
        'date': date,
        'status': status
    }

def extract_task_data(page):
    """Extract data from a Development Tasks page"""
    properties = page['properties']
    
    # Extract the title
    title = "Untitled"
    
    # Look for the title property (the one with type 'title')
    for prop_name, prop_data in properties.items():
        if prop_data.get('type') == 'title':
            if prop_data.get('title') and len(prop_data['title']) > 0:
                try:
                    title = prop_data['title'][0]['text']['content']
                except (KeyError, IndexError, TypeError):
                    title = f"Task {page['id'][-8:]}"
                break
    
    # Fallback to page ID if properties don't work
    if title == "Untitled":
        title = f"Task {page['id'][-8:]}"
    
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
    
    # Sort items by date
    recent_launches = sorted(
        recent_launches,
        key=lambda x: x['properties'].get('Date', {}).get('date', {}).get('start', ''),
        reverse=True
    )
    
    upcoming_launches = sorted(
        upcoming_launches,
        key=lambda x: x['properties'].get('Date', {}).get('date', {}).get('start', '')
    )
    
    bug_fixes = sorted(
        bug_fixes,
        key=lambda x: x['properties'].get('Done Date', {}).get('date', {}).get('start', ''),
        reverse=True
    )
    
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

def send_personalized_email(recipient_email, content, is_cc=False):
    """Send a personalized email to a single recipient"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Weekly Development Release Notes - {datetime.now().strftime('%B %d, %Y')}"
    msg['From'] = EMAIL_USER
    msg['To'] = recipient_email
    
    html_part = MIMEText(content, 'html')
    msg.attach(html_part)
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        
        text = msg.as_string()
        server.sendmail(EMAIL_USER, [recipient_email], text)
        
        server.quit()
        print(f"Email sent successfully to {recipient_email} (CC: {is_cc})")
        
    except Exception as e:
        print(f"Error sending email to {recipient_email}: {e}")
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
        
        print("\nGrouping items by recipient...")
        recipient_data = group_items_by_recipient(recent_launches, upcoming_launches, bug_fixes)
        print(f"Found {len(recipient_data)} unique recipients")
        
        if not recipient_data:
            print("No recipients found with associated items. Exiting.")
            return
        
        # Send personalized emails to each recipient
        for recipient_email, data in recipient_data.items():
            print(f"\nProcessing email for {recipient_email}...")
            print(f"  - Recent launches: {len(data['recent'])}")
            print(f"  - Upcoming launches: {len(data['upcoming'])}")
            print(f"  - Bug fixes: {len(data['bugs'])}")
            
            # Format email with only this recipient's items
            email_content = format_email_content(
                data['recent'],
                data['upcoming'],
                data['bugs']
            )
            
            # Send email
            send_personalized_email(recipient_email, email_content, data['is_cc'])
        
        print(f"\nWeekly email automation completed successfully!")
        print(f"Total emails sent: {len(recipient_data)}")
        
    except Exception as e:
        print(f"Error in main execution: {e}")
        raise e

if __name__ == "__main__":
    main()
