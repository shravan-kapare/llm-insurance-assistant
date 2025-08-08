import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY is not set. Please add it to your .env file.")

client = Groq(api_key=api_key)

def evaluate_decision(query_info, retrieved_clauses):
    prompt = f"""
Query Info:
{query_info}

Relevant Clauses:
{retrieved_clauses}

Answer in this JSON format:
{{
  "decision": "Approved/Rejected",
  "amount": "Amount in INR if applicable",
  "justification": "Reason for decision with referenced clause"
}}
"""
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content
