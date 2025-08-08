import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY is not set. Please add it to your .env file.")

client = Groq(api_key=api_key)

def parse_query(text):
    prompt = f"""
You are an expert insurance query parser. 
Extract these fields from the input query:
- age (as number)
- gender (male/female)
- procedure (surgery, consultation etc.)
- location (city or state)
- policy_duration (e.g. '3-month', '1 year')

Input: "{text}"

Respond ONLY with JSON like this (no explanation, no markdown):

{{
  "age": 46,
  "gender": "male",
  "procedure": "knee surgery",
  "location": "Pune",
  "policy_duration": "3-month"
}}
"""

    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}]
    )

    output = response.choices[0].message.content.strip()

    try:
        return json.loads(output)
    except json.JSONDecodeError:
        print("\n⚠️ LLM response could not be parsed as JSON.")
        print("Raw response from Groq:\n", output)
        return {"error": "Failed to parse query", "raw_response": output}
