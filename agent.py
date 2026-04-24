import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai

import logging

# Setup Agent Logging
logging.basicConfig(
    filename='logs/agent_session.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("NewsAgent")

load_dotenv(override=True)

app = Flask(__name__)
CORS(app)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "").strip())

import resend

import resend

resend.api_key = os.environ.get("RESEND_API_KEY", "").strip()

# Define the Tool / Function that the Agent can call
def send_email_summary(recipient_email: str, subject: str, html_body: str) -> str:
    """Sends an email summary of the high-impact news directly to the user using Resend."""
    print("========================================")
    print("[AGENT] INITIATED TOOL CALL: send_email_summary (RESEND)")
    print(f"To: {recipient_email}")
    print(f"Subject: {subject}")
    print("========================================")
    
    if not resend.api_key:
        print("Notice: RESEND_API_KEY not set in .env.")
        return "FAILED: RESEND_API_KEY missing in .env"
        
    try:
        # Note: Resend Free Tier requires "onboarding@resend.dev" as the sender 
        params = {
            "from": "onboarding@resend.dev",
            "to": recipient_email,
            "subject": subject,
            "html": html_body
        }
        
        email = resend.Emails.send(params)
        logger.info(f"Email sent successfully via Resend to {recipient_email}")
        return f"SUCCESS: Email sent via Resend. ID: {email['id']}"
    except Exception as e:
        logger.error(f"Resend failed: {e}")
        return f"FAILED to send email via Resend: {e}"

# Give the tool to the Gemini Model
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    tools=[send_email_summary],
    generation_config=genai.GenerationConfig(response_mime_type="text/plain")
)

@app.route("/filter", methods=["POST"])
def filter_news():
    data = request.json
    articles = data.get("articles", [])
    interests = data.get("interests", "General Tech")
    user_email = data.get("email", "user@example.com")
    
    # --- MOCK MODE TO BYPASS QUOTA LIMITS ---
    MOCK_MODE = True 
    if MOCK_MODE:
        logger.info(f"--- NEW SESSION ---")
        logger.info(f"Interests: {interests} | Email: {user_email}")
        logger.info(f"Scraper found {len(articles)} articles.")
        
        print(f"QUOTA BREACHED: RUNNING IN MOCK MODE (Interests: {interests})")
        
        # 1. Simulate intelligent filtering based on interests
        interest_list = [i.strip().lower() for i in interests.split(",")]
        summary_body = f"""
        <div style='font-family: Arial, sans-serif; color: #202124; max-width: 600px; margin: auto;'>
            <h2 style='color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px;'>
                Agentic News: {interests}
            </h2>
            <p style='color: #70757a;'>Curated by your Autonomous Agent</p>
            <ul style='list-style-type: none; padding: 0;'>
        """
        
        decisions = []
        kept_count = 0
        for i, art in enumerate(articles):
            # Fix missing URL (often happens on Search Results)
            url = art.get('url')
            if not url or str(url) == "None" or str(url) == "null" or url == "#":
                search_query = art['title'].replace(' ', '+')
                url = f"https://www.google.com/search?q={search_query}&tbm=nws"
                art['url'] = url

            # Log for debugging
            logger.info(f"Processing: {art['title']} | URL: {url}")
            
            # Fuzzy interest matching (matches any part of the interest)
            matches_interest = any(keyword.strip().lower() in art['title'].lower() or keyword.strip().lower() in art['snippet'].lower() for keyword in interest_list)
            
            # Keep if interest match
            is_kept = matches_interest
            
            reasoning = f"Matched interest: {interests}" if is_kept else "Filtered: Not related to your search."
            
            decisions.append({"id": art['id'], "isKept": is_kept, "reasoning": reasoning})
            
            if is_kept:
                kept_count += 1
                summary_body += f"""
                <li style='margin-bottom: 20px; padding: 15px; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; list-style-type: none;'>
                    <div style='font-size: 18px; font-weight: bold;'>
                        <a href='{url}' target='_blank' style='color: #1a73e8; text-decoration: none;'>
                            {art['title']} &rarr;
                        </a>
                    </div>
                </li>
                """
        
        summary_body += "</ul><p style='font-size: 12px; color: #70757a; text-align: center; border-top: 1px solid #eee; padding-top: 10px;'>Personalized News Agent Summary</p></div>"


        
        # Trigger the email tool
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        subject = f"Your Daily News Digest [{now}]"
        
        if kept_count > 0:
            logger.info(f"Triggering email tool for {kept_count} articles.")
            send_email_summary(user_email, subject, summary_body)
        else:
            logger.warning("No articles matched user interests. Sending status email.")
            status_body = f"<h2>News Agent Update</h2><p>No news items matching <b>'{interests}'</b> were found on your current screen. Try searching for this topic on Google News first!</p>"
            send_email_summary(user_email, f"News Agent Update [{now}]", status_body)
        
        # Return the simulated decisions
        return jsonify(decisions)
    # ----------------------------------------

    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"error": "GEMINI_API_KEY missing in .env"}), 500

    prompt = f"""
    You are an autonomous news curation Agent. 
    1. Filter these articles based on the user's interests: {interests}.
    2. Remove obvious clickbait and low-impact gossip.
    3. Keep only high-impact news.
    4. If you find high-impact articles, YOU MUST use the `send_email_summary` tool to email a short HTML summary to: {user_email}.
    
    Articles:
    {json.dumps(articles, indent=2)}
    
    IMPORTANT: Once you have called the email tool, you must respond to ME with strict JSON formatting.
    Return an array of objects where each object has:
    - "id": string (the article id)
    - "isKept": boolean
    - "reasoning": string
    """
    
    # Enable automatic tool calling
    chat = model.start_chat(enable_automatic_function_calling=True)
    
    try:
        response = chat.send_message(prompt)
        
        # Clean potential markdown backticks from AI response
        res_text = response.text.strip()
        if res_text.startswith("```json"):
            res_text = res_text.replace("```json", "").replace("```", "").strip()
        elif res_text.startswith("```"):
            res_text = res_text.replace("```", "").strip()
            
        # Log raw response for debugging
        print(f"[AGENT] RAW RESPONSE: {res_text}")
            
        # Parse Gemini's JSON output
        try:
            decisions = json.loads(res_text)
        except json.JSONDecodeError:
            # Robust fallback: Find the JSON array inside the text using regex
            import re
            match = re.search(r"(\[.*\])", res_text, re.DOTALL)
            if match:
                try:
                    decisions = json.loads(match.group(1))
                except:
                    raise ValueError(f"AI response contained invalid JSON: {res_text}")
            else:
                raise ValueError(f"AI response did not contain a JSON array: {res_text}")
                
        return jsonify(decisions)
    except Exception as e:
        print(f"Agent Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("Starting Agentic API Server with Tool Calling on http://localhost:5000")
    app.run(port=5000, debug=True)
