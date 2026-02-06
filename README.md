# Google Form Auto-Filler

A Streamlit app that extracts questions from Google Forms and generates answers using AWS Bedrock (Claude).

## Setup

```bash
pip install -r requirements.txt
```

Ensure your AWS credentials are configured in `~/.aws/credentials`.

## Usage

```bash
streamlit run app.py
```

1. Enter a public Google Form URL
2. Click "Extract & Answer"

## Note

- Only works with publicly accessible Google Forms
- Forms requiring authentication won't be accessible
- Uses AWS Bedrock with Claude 3.5 Sonnet in eu-north-1 region
