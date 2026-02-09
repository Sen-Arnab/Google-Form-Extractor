import streamlit as st
import requests
from bs4 import BeautifulSoup
import boto3
import json
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import os

def detect_question_type(item):
    """Detect the type of question from the form item"""
    # Check for grid questions (multiple radiogroups or groups)
    radiogroups = item.find_all('div', {'role': 'radiogroup'})
    groups = item.find_all('div', {'role': 'group'})
    
    if len(radiogroups) > 1:
        return 'grid'
    if len(groups) > 1:
        return 'checkbox_grid'
    
    # Check for radio buttons (single choice)
    if item.find('div', {'role': 'radio'}) or item.find('input', {'type': 'radio'}):
        return 'radio'
    
    # Check for checkboxes (multiple choice)
    if item.find('div', {'role': 'checkbox'}) or item.find('input', {'type': 'checkbox'}):
        return 'checkbox'
    
    # Check for dropdown
    if item.find('select') or item.find('div', {'role': 'listbox'}):
        return 'dropdown'
    
    # Check for text input
    if item.find('input', {'type': 'text'}) or item.find('textarea'):
        return 'text'
    
    # Check for date/time
    if item.find('input', {'type': 'date'}) or item.find('input', {'type': 'time'}):
        return 'date'
    
    # Default to text if can't determine
    return 'text'

st.set_page_config(page_title="Google Form Auto-Filler", page_icon="📝", layout="wide")

# Google OAuth configuration
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
REDIRECT_URI = st.secrets.get("GOOGLE_REDIRECT_URI", "https://localhost:8501")

def init_oauth_flow():
    """Initialize OAuth flow from Streamlit secrets"""
    try:
        client_id = st.secrets.get("GOOGLE_CLIENT_ID")
        client_secret = st.secrets.get("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            return None
            
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        return flow
    except Exception as e:
        st.error(f"OAuth initialization failed: {str(e)}")
        return None

def get_auth_url():
    """Get Google OAuth authorization URL"""
    flow = init_oauth_flow()
    if flow:
        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url
    return None

def get_user_email_from_token(access_token):
    """Get user email from Google OAuth token"""
    try:
        response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get('email')
    except Exception as e:
        st.warning(f"Could not fetch user email: {str(e)}")
    return None

def make_authenticated_request(url, access_token=None):
    """Make request with optional OAuth token"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    cookies = {}
    
    if access_token:
        headers['Authorization'] = f'Bearer {access_token}'
        cookies['oauth_token'] = access_token
    
    return requests.get(url, headers=headers, cookies=cookies, timeout=15)

st.title("📝 Google Form Auto-Filler")
st.markdown("Extract questions from Google Forms and generate AI-powered answers using AWS Bedrock")

# Initialize session state for OAuth
if 'google_token' not in st.session_state:
    st.session_state.google_token = None
if 'use_auth' not in st.session_state:
    st.session_state.use_auth = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

# Get email from token if authenticated
if st.session_state.google_token and not st.session_state.user_email:
    st.session_state.user_email = get_user_email_from_token(st.session_state.google_token)

col1, col2 = st.columns([3, 1])
with col1:
    form_url = st.text_input("Enter Google Form URL:", placeholder="https://docs.google.com/forms/d/...", key="form_url_input")
with col2:
    st.write("")
    st.write("")
    extract_btn = st.button("🚀 Extract & Answer", type="primary", use_container_width=True)

# Options
col_opt1, col_opt2 = st.columns(2)
with col_opt1:
    use_auth = st.checkbox("🔐 Use Google Auth", help="For private/restricted forms")
with col_opt2:
    submit_form = st.checkbox("📤 Auto-submit form", help="Submit form with AI answers (experimental - may not work for all forms)")

# Show Google Auth UI only if checkbox is enabled
if use_auth and not st.session_state.google_token:
    st.markdown("### Google Authentication")
    
    auth_method = st.radio("Choose authentication method:", 
                           ["Manual Token", "OAuth Flow (requires setup)"])
    
    if auth_method == "Manual Token":
        st.warning("⚠️ Manual token method is for advanced users only. Use at your own risk.")
        st.markdown("""
        **Get your access token:**
        1. Open Google Form in browser while signed in
        2. Open Developer Tools (F12)
        3. Go to Application → Cookies
        4. Copy the value of `SID` or `SAPISID` cookie
        """)
        
        manual_token = st.text_input("Paste your Google session token:", type="password", key="manual_token_input")
        if st.button("Use Token") and manual_token:
            st.session_state.google_token = manual_token
            st.rerun()
    
    else:  # OAuth Flow
        auth_url = get_auth_url()
        if auth_url:
            st.markdown(f"[🔗 Click here to authorize with Google]({auth_url})")
            auth_code = st.text_input("Paste the authorization code:", key="oauth_code_input")
            if st.button("Submit Code"):
                try:
                    flow = init_oauth_flow()
                    flow.fetch_token(code=auth_code)
                    st.session_state.google_token = flow.credentials.token
                    st.success("✅ Authenticated successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Authentication failed: {str(e)}")
        else:
            st.warning("⚠️ OAuth not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to Streamlit secrets.")

if st.session_state.google_token:
    if st.session_state.user_email:
        st.success(f"✅ Signed in as: {st.session_state.user_email}")
    else:
        st.success("✅ Google authentication active")
    if st.button("🚪 Sign Out"):
        st.session_state.google_token = None
        st.session_state.user_email = None
        st.rerun()

# Email handling for form submission
user_email = None
if submit_form:
    if st.session_state.user_email:
        # Authenticated - use email from token
        user_email = st.session_state.user_email
        st.info(f"📧 Form will be submitted as: **{user_email}**")
    else:
        # Not authenticated - ask for email
        user_email = st.text_input("📧 Your Email (for form submission):", placeholder="your.email@example.com", key="email_input")
        if not user_email:
            st.warning("⚠️ Email required for form submission")

st.markdown("---")

if extract_btn:
    if not form_url:
        st.error("❌ Please provide a form URL")
    elif not form_url.startswith("https://docs.google.com/forms/"):
        st.error("❌ Please provide a valid Google Form URL (must start with https://docs.google.com/forms/)")
    else:
        with st.spinner("🔄 Fetching form..."):
            try:
                # Use authenticated request if token available
                response = make_authenticated_request(form_url, st.session_state.google_token)
                
                # Check if authentication is required
                if response.status_code == 401 or "Sign in" in response.text[:1000]:
                    st.error("❌ This form requires authentication. Enable 'Use Google Auth' above.")
                    st.stop()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract form action URL and entry IDs
                form_element = soup.find('form')
                form_action = form_element.get('action') if form_element else None
                
                # Extract questions
                questions = []
                form_data = {}
                
                # Try method 1: role-based extraction
                for item in soup.find_all('div', {'role': 'listitem'}):
                    question_text = item.find('div', {'role': 'heading'})
                    if question_text:
                        q_type = detect_question_type(item)
                        q = {"question": question_text.get_text(strip=True), "options": [], "entry_id": None, "type": q_type}
                        
                        # Extract entry ID from input name
                        input_elem = item.find('input', {'name': True})
                        if input_elem:
                            entry_name = input_elem.get('name')
                            if entry_name and 'entry.' in entry_name:
                                # Handle formats like 'entry.123456789' or 'entry.123456789_sentinel'
                                q["entry_id"] = entry_name.split('_')[0] if '_' in entry_name else entry_name
                        
                        # Extract options only for choice-based questions
                        if q_type in ['radio', 'checkbox', 'dropdown', 'grid', 'checkbox_grid']:
                            # For grid questions
                            if q_type in ['grid', 'checkbox_grid']:
                                # Extract row labels first
                                rows = item.find_all('div', class_='wzWPxe')
                                q["rows"] = []
                                row_texts = set()
                                for r in rows:
                                    r_text = r.get_text(strip=True)
                                    if r_text and r_text not in row_texts:
                                        row_texts.add(r_text)
                                        q["rows"].append(r_text)
                                
                                # Extract column headers (options) - filter out row labels
                                headers = item.find_all('div', class_='V4d7Ke')
                                seen_headers = set()
                                for h in headers:
                                    h_text = h.get_text(strip=True)
                                    if h_text and h_text not in seen_headers and h_text not in row_texts:
                                        seen_headers.add(h_text)
                                        q["options"].append(h_text)
                            
                            # For dropdown, extract from listbox
                            elif q_type == 'dropdown':
                                listbox = item.find('div', {'role': 'listbox'})
                                if listbox:
                                    for opt in listbox.find_all('span', class_='vRMGwf'):
                                        opt_text = opt.get_text(strip=True)
                                        if opt_text and opt_text != 'Choose':
                                            q["options"].append(opt_text)
                            
                            # For radio/checkbox, try span extraction first
                            else:
                                option_spans = item.find_all('span', class_='aDTYNe')
                                for opt_span in option_spans:
                                    opt_text = opt_span.get_text(strip=True)
                                    if opt_text:
                                        q["options"].append(opt_text)
                                
                                # If no options found, try data-value from radio/checkbox elements
                                if not q["options"]:
                                    role = 'radio' if q_type == 'radio' else 'checkbox'
                                    elements = item.find_all('div', {'role': role, 'data-value': True})
                                    seen = set()
                                    for elem in elements:
                                        val = elem.get('data-value')
                                        if val and val not in seen:
                                            seen.add(val)
                                            q["options"].append(val)
                        
                        # If no options found but it's a choice type, treat as text
                        if q_type in ['radio', 'checkbox', 'dropdown'] and not q["options"]:
                            q["type"] = 'text'
                        
                        questions.append(q)
                
                # Try method 2: class-based extraction if method 1 fails
                if not questions:
                    for item in soup.find_all('div', class_='Qr7Oae'):
                        question_elem = item.find('span', class_='M7eMe')
                        if question_elem:
                            q_type = detect_question_type(item)
                            q = {"question": question_elem.get_text(strip=True), "options": [], "entry_id": None, "type": q_type}
                            
                            # Extract entry ID from input name
                            input_elem = item.find('input', {'name': True})
                            if input_elem:
                                entry_name = input_elem.get('name')
                                if entry_name and 'entry.' in entry_name:
                                    q["entry_id"] = entry_name.split('_')[0] if '_' in entry_name else entry_name
                            
                            # Extract radio/checkbox options
                            option_spans = item.find_all('span', class_='aDTYNe')
                            for opt_span in option_spans:
                                opt_text = opt_span.get_text(strip=True)
                                if opt_text:
                                    q["options"].append(opt_text)
                            
                            questions.append(q)
                
                if not questions:
                    st.warning("⚠️ No questions found. Form may require authentication or have a different structure.")
                else:
                    st.success(f"✅ Found {len(questions)} question(s)")
                    st.markdown("---")
                    
                    # Generate answers using Bedrock
                    try:
                        bedrock = boto3.client(
                            'bedrock-runtime',
                            region_name=st.secrets.get("AWS_DEFAULT_REGION", "eu-north-1"),
                            aws_access_key_id=st.secrets.get("AWS_ACCESS_KEY_ID"),
                            aws_secret_access_key=st.secrets.get("AWS_SECRET_ACCESS_KEY")
                        )
                    except Exception as e:
                        st.error(f"❌ AWS Bedrock initialization failed: {str(e)}")
                        st.stop()
                    
                    for i, q in enumerate(questions, 1):
                        with st.container():
                            st.markdown(f"### Question {i}")
                            st.markdown(f"**{q['question']}**")
                            
                            # Display question type badge
                            type_emoji = {
                                'radio': '🔘',
                                'checkbox': '☑️',
                                'dropdown': '📋',
                                'grid': '📊',
                                'checkbox_grid': '☑️📊',
                                'text': '✏️',
                                'date': '📅'
                            }
                            st.caption(f"{type_emoji.get(q['type'], '❓')} Type: {q['type'].replace('_', ' ').title()}")
                            
                            if q['type'] in ['grid', 'checkbox_grid'] and q.get('rows') and q.get('options'):
                                # Grid question - answer each row
                                grid_answers = {}
                                
                                for row in q['rows']:
                                    options_list = '\n'.join([f"{i+1}. {opt}" for i, opt in enumerate(q['options'])])
                                    
                                    if q['type'] == 'grid':
                                        # Single choice per row
                                        prompt = f"""Question: {q['question']}

For this row, pick the best matching option.

Row: {row}

Options:
{options_list}

Your answer (just the number):"""
                                        
                                        body = json.dumps({
                                            "anthropic_version": "bedrock-2023-05-31",
                                            "max_tokens": 3,
                                            "temperature": 0.3,
                                            "system": "Respond only with the option number.",
                                            "messages": [{"role": "user", "content": prompt}]
                                        })
                                    else:
                                        # Multiple choice per row (checkbox grid)
                                        prompt = f"""Question: {q['question']}

For this row, select all applicable options.

Row: {row}

Options:
{options_list}

Reply with comma-separated numbers (e.g., "1" or "1,2"):"""
                                        
                                        body = json.dumps({
                                            "anthropic_version": "bedrock-2023-05-31",
                                            "max_tokens": 20,
                                            "temperature": 0.3,
                                            "system": "You must respond only with comma-separated numbers. Pick at least one option.",
                                            "messages": [{"role": "user", "content": prompt}]
                                        })
                                    
                                    with st.spinner(f"🤖 Answering: {row[:30]}..."):
                                        try:
                                            response = bedrock.invoke_model(
                                                modelId="eu.anthropic.claude-sonnet-4-20250514-v1:0",
                                                body=body
                                            )
                                            result = json.loads(response['body'].read())
                                            answer = result['content'][0]['text'].strip()
                                            
                                            # Parse answer
                                            if q['type'] == 'grid':
                                                match = re.search(r'\d+', answer)
                                                if match:
                                                    choice_num = int(match.group())
                                                    if 1 <= choice_num <= len(q['options']):
                                                        grid_answers[row] = [choice_num - 1]
                                            else:
                                                numbers = re.findall(r'\d+', answer)
                                                selected = []
                                                for num_str in numbers:
                                                    choice_num = int(num_str)
                                                    if 1 <= choice_num <= len(q['options']):
                                                        selected.append(choice_num - 1)
                                                if selected:
                                                    grid_answers[row] = selected
                                        except Exception as e:
                                            st.error(f"Error for row '{row}': {str(e)}")
                                
                                # Display as table
                                import pandas as pd
                                table_data = []
                                for row in q['rows']:
                                    row_data = {'': row}
                                    for col_idx, col in enumerate(q['options']):
                                        if row in grid_answers and col_idx in grid_answers[row]:
                                            row_data[col] = '✅'
                                        else:
                                            row_data[col] = ''
                                    table_data.append(row_data)
                                
                                df = pd.DataFrame(table_data)
                                st.dataframe(df, use_container_width=True, hide_index=True)
                            
                            elif q['options'] and q['type'] in ['radio', 'dropdown']:
                                # Single choice question - return number
                                options_list = '\n'.join([f"{i+1}. {opt}" for i, opt in enumerate(q['options'])])
                                
                                prompt = f"""Pick the most likely answer. If you don't know, guess.

Question: {q['question']}

Options:
{options_list}

Your answer (just the number):"""
                                
                                body = json.dumps({
                                    "anthropic_version": "bedrock-2023-05-31",
                                    "max_tokens": 3,
                                    "temperature": 0.3,
                                    "system": "You must always pick one option number. If unsure, make your best guess. Respond only with the number.",
                                    "messages": [{"role": "user", "content": prompt}]
                                })
                                
                                with st.spinner("🤖 AI is thinking..."):
                                    try:
                                        response = bedrock.invoke_model(
                                            modelId="eu.anthropic.claude-sonnet-4-20250514-v1:0",
                                            body=body
                                        )
                                    except Exception as e:
                                        st.error(f"❌ Bedrock API error: {str(e)}")
                                        continue
                                
                                result = json.loads(response['body'].read())
                                answer = result['content'][0]['text'].strip()
                                
                                # Parse the number from response
                                selected_idx = -1
                                try:
                                    # Extract first number from response
                                    import re
                                    match = re.search(r'\d+', answer)
                                    if match:
                                        choice_num = int(match.group())
                                        if 1 <= choice_num <= len(q['options']):
                                            selected_idx = choice_num - 1
                                except:
                                    pass
                                
                                # Display options with tick for selected answer
                                st.markdown("**Options:**")
                                for idx, opt in enumerate(q['options']):
                                    if idx == selected_idx:
                                        st.success(f"✅ {opt}")
                                    else:
                                        st.write(f"⚪ {opt}")
                                
                                # Show what LLM returned for debugging
                                if selected_idx == -1:
                                    st.warning(f"⚠️ Could not parse LLM response: '{answer}'")
                                else:
                                    # Store answer for form submission
                                    if q.get('entry_id'):
                                        form_data[q['entry_id']] = q['options'][selected_idx]
                            
                            elif q['options'] and q['type'] == 'checkbox':
                                # Multiple choice (checkbox) - can select multiple
                                options_list = '\n'.join([f"{i+1}. {opt}" for i, opt in enumerate(q['options'])])
                                prompt = f"""Select all applicable answers for this question. You can pick multiple.

Question: {q['question']}

Options:
{options_list}

Reply with comma-separated numbers (e.g., "1,3" or "2,4,5"). If only one applies, just that number."""
                                
                                body = json.dumps({
                                    "anthropic_version": "bedrock-2023-05-31",
                                    "max_tokens": 20,
                                    "temperature": 0.3,
                                    "system": "Respond only with comma-separated numbers of applicable options.",
                                    "messages": [{"role": "user", "content": prompt}]
                                })
                                
                                with st.spinner("🤖 AI is thinking..."):
                                    try:
                                        response = bedrock.invoke_model(
                                            modelId="eu.anthropic.claude-sonnet-4-20250514-v1:0",
                                            body=body
                                        )
                                    except Exception as e:
                                        st.error(f"❌ Bedrock API error: {str(e)}")
                                        continue
                                
                                result = json.loads(response['body'].read())
                                answer = result['content'][0]['text'].strip()
                                
                                # Parse multiple numbers from response
                                selected_indices = []
                                try:
                                    # Extract all numbers from response
                                    numbers = re.findall(r'\d+', answer)
                                    for num_str in numbers:
                                        choice_num = int(num_str)
                                        if 1 <= choice_num <= len(q['options']):
                                            selected_indices.append(choice_num - 1)
                                except:
                                    pass
                                
                                # Display options with ticks for selected answers
                                st.markdown("**Options:**")
                                for idx, opt in enumerate(q['options']):
                                    if idx in selected_indices:
                                        st.success(f"✅ {opt}")
                                    else:
                                        st.write(f"⚪ {opt}")
                                
                                if not selected_indices:
                                    st.warning(f"⚠️ Could not parse LLM response: '{answer}'")
                                else:
                                    # Store multiple answers for form submission
                                    if q.get('entry_id'):
                                        # Google Forms expects multiple values for checkboxes
                                        form_data[q['entry_id']] = [q['options'][i] for i in selected_indices]
                            
                            else:
                                # Text/open-ended question - descriptive answer
                                if q['type'] == 'text':
                                    prompt = f"Question: {q['question']}\n\nProvide a brief, direct answer (1-2 sentences max)."
                                    max_tokens = 100
                                elif q['type'] == 'date':
                                    prompt = f"Question: {q['question']}\n\nProvide a date in format: YYYY-MM-DD or MM/DD/YYYY."
                                    max_tokens = 20
                                else:
                                    prompt = f"Question: {q['question']}\n\nProvide an appropriate answer."
                                    max_tokens = 100
                                
                                body = json.dumps({
                                    "anthropic_version": "bedrock-2023-05-31",
                                    "max_tokens": max_tokens,
                                    "temperature": 0.7,
                                    "messages": [{"role": "user", "content": prompt}]
                                })
                                
                                with st.spinner("🤖 AI is thinking..."):
                                    try:
                                        response = bedrock.invoke_model(
                                            modelId="eu.anthropic.claude-sonnet-4-20250514-v1:0",
                                            body=body
                                        )
                                    except Exception as e:
                                        st.error(f"❌ Bedrock API error: {str(e)}")
                                        continue
                                
                                result = json.loads(response['body'].read())
                                answer = result['content'][0]['text'].strip()
                                st.info(f"💡 **Answer:** {answer}")
                                
                                # Store text answer for form submission
                                if q.get('entry_id'):
                                    form_data[q['entry_id']] = answer
                            
                            st.markdown("---")
                    
                    # Submit form if requested
                    if submit_form and form_action and form_data:
                        st.markdown("### 📤 Form Submission")
                        
                        if not user_email:
                            st.error("❌ Please provide your email to submit the form")
                        else:
                            # Add email to form data
                            form_data['emailAddress'] = user_email
                            
                            try:
                                # Use authenticated request for submission
                                headers = {}
                                cookies = {}
                                
                                if st.session_state.google_token:
                                    headers['Authorization'] = f'Bearer {st.session_state.google_token}'
                                    cookies['oauth_token'] = st.session_state.google_token
                                
                                submit_response = requests.post(
                                    form_action, 
                                    data=form_data,
                                    headers=headers,
                                    cookies=cookies,
                                    timeout=15
                                )
                                
                                if submit_response.status_code == 200:
                                    st.success("✅ Form submitted successfully!")
                                elif submit_response.status_code == 401:
                                    st.error("❌ Form submission requires authentication. Please enable 'Use Google Auth' and sign in.")
                                else:
                                    st.error(f"❌ Form submission failed with status code: {submit_response.status_code}")
                            except Exception as submit_error:
                                st.error(f"❌ Form submission error: {str(submit_error)}")
                    elif submit_form and not form_action:
                        st.warning("⚠️ Could not extract form submission URL")
                        
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    <p>Powered by AWS Bedrock (Claude Sonnet 4) • Built with Streamlit</p>
</div>
""", unsafe_allow_html=True)
