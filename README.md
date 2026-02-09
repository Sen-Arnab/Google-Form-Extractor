# Google Form Auto-Filler

A Streamlit app that extracts questions from Google Forms and generates answers using AWS Bedrock (Claude).

## Features

- 📝 Extract questions and options from public Google Forms
- 🤖 AI-powered answer generation using AWS Bedrock Claude Sonnet 4
- ✅ Visual display of selected answers
- 🎨 Clean, modern UI

## Setup

### Local Development

```bash
# Clone the repository
git clone https://github.com/Sen-Arnab/Google-Form-Extractor.git
cd Google-Form-Extractor

# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials
# Option 1: Use AWS CLI
aws configure

# Option 2: Create .streamlit/secrets.toml
mkdir -p .streamlit
cat > .streamlit/secrets.toml << EOF
AWS_ACCESS_KEY_ID = "your-access-key-id"
AWS_SECRET_ACCESS_KEY = "your-secret-access-key"
AWS_DEFAULT_REGION = "eu-north-1"
EOF

# Run the app
streamlit run app.py
```

### Deploy to Streamlit Community Cloud

1. Go to https://share.streamlit.io/
2. Sign in with GitHub
3. Click "New app"
4. Select repository: `Sen-Arnab/Google-Form-Extractor`
5. Main file path: `app.py`
6. Click "Advanced settings" → "Secrets"
7. Add your AWS credentials:
```toml
AWS_ACCESS_KEY_ID = "your-access-key-id"
AWS_SECRET_ACCESS_KEY = "your-secret-access-key"
AWS_DEFAULT_REGION = "eu-north-1"
```
8. Click "Deploy"

## Usage

1. Enter a public Google Form URL
2. Click "🚀 Extract & Answer"
3. View AI-generated answers with selected options marked ✅

## Requirements

- Python 3.8+
- AWS account with Bedrock access
- Public Google Form (forms requiring authentication won't work)

## Note

- Only works with publicly accessible Google Forms
- Forms requiring authentication won't be accessible
- Uses AWS Bedrock with Claude Sonnet 4 in eu-north-1 region
- **Auto-submit feature is experimental** and may not work for all forms due to Google's CSRF protection

## Known Limitations

- OAuth authentication for private forms is not fully functional
- Form submission may fail due to Google's security measures
- Complex form types (file upload, grid questions) are not supported

## Tech Stack

- **Frontend**: Streamlit
- **AI Model**: AWS Bedrock (Claude Sonnet 4)
- **Web Scraping**: BeautifulSoup4, Requests
- **Cloud**: AWS (Bedrock)

