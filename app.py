import streamlit as st
import requests
from bs4 import BeautifulSoup
import boto3
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import os

def detect_question_type(item):
    """Detect the type of question from the form item"""
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
                        if q_type in ['radio', 'checkbox', 'dropdown']:
                            options = item.find_all('div', {'role': 'radio'}) or item.find_all('div', {'role': 'checkbox'})
                            for opt in options:
                                opt_text = opt.get_text(strip=True)
                                if opt_text:
                                    q["options"].append(opt_text)
                        
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
                            if q_type in ['radio', 'checkbox', 'dropdown']:
                                for opt in item.find_all('span', class_='aDTYNe'):
                                    opt_text = opt.get_text(strip=True)
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
                                'text': '✏️',
                                'date': '📅'
                            }
                            st.caption(f"{type_emoji.get(q['type'], '❓')} Type: {q['type'].title()}")
                            
                            if q['options']:
                                # Multiple choice question
                                options_list = '\n'.join([f"- {opt}" for opt in q['options']])
                                prompt = f"""Question: {q['question']}

Available options:
{options_list}

Instructions: Reply with ONLY the exact text of the single best option from the list above. Do not add any explanation, reasoning, or extra text. Just the option text itself."""
                                
                                body = json.dumps({
                                    "anthropic_version": "bedrock-2023-05-31",
                                    "max_tokens": 50,
                                    "temperature": 0,
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
                                
                                # Find best matching option
                                selected_idx = -1
                                for idx, opt in enumerate(q['options']):
                                    if opt.lower() in answer.lower() or answer.lower() in opt.lower():
                                        selected_idx = idx
                                        break
                                
                                # Display options with tick for selected answer
                                st.markdown("**Options:**")
                                for idx, opt in enumerate(q['options']):
                                    if idx == selected_idx:
                                        st.success(f"✅ {opt}")
                                    else:
                                        st.write(f"⚪ {opt}")
                                
                                # Store answer for form submission
                                if selected_idx != -1 and q.get('entry_id'):
                                    form_data[q['entry_id']] = q['options'][selected_idx]
                                
                                if selected_idx == -1:
                                    st.warning(f"⚠️ Could not match LLM response to any option")
                            else:
                                # Text/open-ended question
                                prompt_type = "a brief, direct answer" if q['type'] == 'text' else "an appropriate value"
                                prompt = f"Question: {q['question']}\n\nProvide {prompt_type}."
                                
                                body = json.dumps({
                                    "anthropic_version": "bedrock-2023-05-31",
                                    "max_tokens": 200,
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
