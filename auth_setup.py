#!/usr/bin/env python3
"""
Setup script for Google OAuth authentication
Run this once to authenticate and save credentials
"""

from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

SCOPES = ['https://www.googleapis.com/auth/forms.responses.readonly']

def main():
    print("Starting Google OAuth setup...")
    print("This will open a browser window for authentication.")
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        
        print("\n✅ Authentication successful!")
        print("Token saved to token.pickle")
        print("You can now run the Streamlit app.")
        
    except FileNotFoundError:
        print("\n❌ Error: credentials.json not found")
        print("Please download OAuth credentials from Google Cloud Console")
        print("See GOOGLE_AUTH_SETUP.md for instructions")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

if __name__ == '__main__':
    main()
