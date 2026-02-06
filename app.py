import streamlit as st
import requests
from bs4 import BeautifulSoup
import boto3
import json

st.set_page_config(page_title="Google Form Auto-Filler", page_icon="📝", layout="wide")

st.title("📝 Google Form Auto-Filler")
st.markdown("Extract questions from Google Forms and generate AI-powered answers using AWS Bedrock")

col1, col2 = st.columns([3, 1])
with col1:
    form_url = st.text_input("Enter Google Form URL:", placeholder="https://docs.google.com/forms/d/...")
with col2:
    st.write("")
    st.write("")
    extract_btn = st.button("🚀 Extract & Answer", type="primary", use_container_width=True)

if extract_btn:
    if not form_url:
        st.error("❌ Please provide a form URL")
    else:
        with st.spinner("🔄 Fetching form..."):
            try:
                response = requests.get(form_url)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract questions
                questions = []
                
                # Try method 1: role-based extraction
                for item in soup.find_all('div', {'role': 'listitem'}):
                    question_text = item.find('div', {'role': 'heading'})
                    if question_text:
                        q = {"question": question_text.get_text(strip=True), "options": []}
                        
                        # Extract options
                        options = item.find_all('div', {'role': 'radio'}) or item.find_all('div', {'role': 'checkbox'})
                        for opt in options:
                            opt_text = opt.get_text(strip=True)
                            if opt_text:
                                q["options"].append(opt_text)
                        
                        # Only add if we found options
                        if q["options"]:
                            questions.append(q)
                
                # Try method 2: class-based extraction if method 1 fails
                if not questions:
                    for item in soup.find_all('div', class_='Qr7Oae'):
                        question_elem = item.find('span', class_='M7eMe')
                        if question_elem:
                            q = {"question": question_elem.get_text(strip=True), "options": []}
                            
                            # Extract radio/checkbox options
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
                    bedrock = boto3.client('bedrock-runtime', region_name='eu-north-1')
                    
                    for i, q in enumerate(questions, 1):
                        with st.container():
                            st.markdown(f"### Question {i}")
                            st.markdown(f"**{q['question']}**")
                            
                            if q['options']:
                                prompt = f"Question: {q['question']}\nOptions: {', '.join(q['options'])}\n\nRespond with ONLY the best option text from the list above, nothing else."
                                
                                body = json.dumps({
                                    "anthropic_version": "bedrock-2023-05-31",
                                    "max_tokens": 200,
                                    "messages": [{"role": "user", "content": prompt}]
                                })
                                
                                with st.spinner("🤖 AI is thinking..."):
                                    response = bedrock.invoke_model(
                                        modelId="eu.anthropic.claude-sonnet-4-20250514-v1:0",
                                        body=body
                                    )
                                
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
                                
                                if selected_idx == -1:
                                    st.warning(f"⚠️ Could not match LLM response to any option")
                            else:
                                prompt = f"Question: {q['question']}\n\nProvide a brief, direct answer."
                                
                                body = json.dumps({
                                    "anthropic_version": "bedrock-2023-05-31",
                                    "max_tokens": 200,
                                    "messages": [{"role": "user", "content": prompt}]
                                })
                                
                                with st.spinner("🤖 AI is thinking..."):
                                    response = bedrock.invoke_model(
                                        modelId="eu.anthropic.claude-sonnet-4-20250514-v1:0",
                                        body=body
                                    )
                                
                                result = json.loads(response['body'].read())
                                answer = result['content'][0]['text'].strip()
                                st.info(f"💡 **Answer:** {answer}")
                            
                            st.markdown("---")
                        
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    <p>Powered by AWS Bedrock (Claude Sonnet 4) • Built with Streamlit</p>
</div>
""", unsafe_allow_html=True)
