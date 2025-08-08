import os
import json
from document_parser import extract_text_from_pdf, extract_text_from_docx, chunk_text
from query_parser import parse_query
from retriever import build_vector_index, search
from decision_engine import evaluate_decision

# === Step 1: Load and process the document ===

file_path = "data/sample_policy.pdf"  # You can change to .docx if needed
ext = os.path.splitext(file_path)[1]

if ext == ".pdf":
    text = extract_text_from_pdf(file_path)
elif ext == ".docx":
    text = extract_text_from_docx(file_path)
else:
    raise ValueError("Unsupported file type. Only PDF or DOCX are allowed.")

# Create FAISS index
chunks = chunk_text(text)
build_vector_index(chunks)

# === Step 2: Get user query ===
query = input("📝 Enter your insurance query:\n> ")

# === Step 3: Parse the query using LLM ===
parsed_query = parse_query(query)

if "error" in parsed_query:
    print("\n❌ Parsing failed. Try rephrasing your query.")
    print("LLM Response:", parsed_query.get("raw_response", ""))
    exit()

print("\n✅ Parsed Query:")
print(json.dumps(parsed_query, indent=2))

# === Step 4: Retrieve relevant clauses ===
retrieved = search(query)
indexed_clauses = [f"[Chunk {idx}] {chunk}" for idx, chunk in retrieved]

print("\n📄 Retrieved Clauses:")
for clause in indexed_clauses:
    print("-", clause[:150] + "...")  # Print short preview

# === Step 5: Evaluate the decision using LLM ===
response = evaluate_decision(parsed_query, indexed_clauses)
print("\n📌 Final Decision:")
print(response)

# === Step 6: Save log ===
log_data = {
    "query": query,
    "parsed": parsed_query,
    "retrieved_clauses": indexed_clauses,
    "decision": response
}

os.makedirs("logs", exist_ok=True)
with open("logs/output_log.json", "w") as f:
    json.dump(log_data, f, indent=2)

#46-year-old male, knee surgery in Pune, 3-month-old insurance policy
#python -m streamlit run i:/Hackrx/app.py

# streamlit run app.py