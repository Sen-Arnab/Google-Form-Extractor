# Google OAuth Setup Guide

## Prerequisites
- Google Cloud Project
- OAuth 2.0 Client ID

## Steps

### 1. Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Note your Project ID

### 2. Enable APIs
1. Go to "APIs & Services" → "Library"
2. Search and enable:
   - Google Forms API
   - Google Drive API (optional, for better access)

### 3. Create OAuth Credentials
1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Choose "Desktop app" as application type
4. Name it (e.g., "Form Auto-Filler")
5. Click "Create"

### 4. Download Credentials
1. Click the download icon next to your OAuth client
2. Save as `credentials.json`
3. Place in the app directory

### 5. First Run Authentication
```bash
python3 auth_setup.py
```

This will:
- Open browser for Google sign-in
- Request permissions
- Save token to `token.pickle`

### 6. Add to Streamlit Secrets (for deployment)
In Streamlit Cloud, add to secrets:
```toml
[google_oauth]
client_id = "your-client-id.apps.googleusercontent.com"
client_secret = "your-client-secret"
```

## Security Notes
- Never commit `credentials.json` or `token.pickle` to git
- These files are in `.gitignore`
- Tokens expire and need refresh
