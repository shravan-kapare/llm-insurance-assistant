import streamlit as st
import os
import tempfile
import json
from datetime import datetime
import sqlite3
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import smtplib
from email.message import EmailMessage
import re

from document_parser import extract_text_from_pdf, extract_text_from_docx, chunk_text
from retriever import build_vector_index, search
from query_parser import parse_query
from decision_engine import evaluate_decision

# --- SQLite Setup ---
def init_db():
    os.makedirs("logs", exist_ok=True)
    conn = sqlite3.connect("logs/decisions.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            query TEXT,
            parsed TEXT,
            clauses TEXT,
            decision TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(timestamp, query, parsed, clauses, decision):
    conn = sqlite3.connect("logs/decisions.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO decisions (timestamp, query, parsed, clauses, decision)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, query, json.dumps(parsed), json.dumps(clauses), json.dumps(decision)))
    conn.commit()
    conn.close()

# --- Streamlit Setup ---
st.set_page_config(page_title="LLM Insurance Assistant", layout="centered")
st.title("📑 LLM-Based Insurance Decision Assistant")

for key in ["parsed", "decision", "retrieved", "email_sent", "show_form", "output_logged", "last_file", "last_query"]:
    if key not in st.session_state:
        st.session_state[key] = False if key in ["email_sent", "show_form", "output_logged"] else None

uploaded_file = st.file_uploader("📤 Upload Policy Document (PDF or DOCX)", type=["pdf", "docx"])

def generate_pdf(query, parsed, clauses, decision):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    elements = [Paragraph("📑 Insurance Decision Report", styles["Title"]), Spacer(1, 12)]
    elements.append(Paragraph(f"📝 <b>Query:</b> {query}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("🔍 <b>Parsed Query:</b>", styles["Heading2"]))
    for k, v in parsed.items():
        elements.append(Paragraph(f"{k}: {v}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("📄 <b>Retrieved Clauses:</b>", styles["Heading2"]))
    for c in clauses:
        elements.append(Paragraph(c, styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("📌 <b>Final Decision:</b>", styles["Heading2"]))
    for k, v in decision.items():
        elements.append(Paragraph(f"{k}: {v}", styles["Normal"]))
    doc.build(elements)
    buffer.seek(0)
    return buffer

def send_email(to_email, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "noreply@llmassistant.com"
    msg["To"] = to_email
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login("noreply@llmassistant.com", "your_app_password")
        smtp.send_message(msg)

def extract_json_from_text(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None

# --- Main Logic ---
init_db()
if uploaded_file:
    # Reset state when file changes
    if st.session_state.last_file != uploaded_file.name:
        st.session_state.parsed = None
        st.session_state.retrieved = None
        st.session_state.decision = None
        st.session_state.output_logged = False
        st.session_state.last_file = uploaded_file.name

    suffix = os.path.splitext(uploaded_file.name)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.read())
        file_path = tmp.name

    text = extract_text_from_pdf(file_path) if suffix == ".pdf" else extract_text_from_docx(file_path)
    chunks = chunk_text(text)
    build_vector_index(chunks)

    st.success("✅ Document processed and indexed!")
    query = st.text_input("📝 Enter your insurance query")

    if query:
        # Reset state when query changes
        if st.session_state.last_query != query:
            st.session_state.parsed = None
            st.session_state.retrieved = None
            st.session_state.decision = None
            st.session_state.output_logged = False
            st.session_state.last_query = query

        if not st.session_state.parsed:
            st.session_state.parsed = parse_query(query)
        parsed = st.session_state.parsed

        if "error" in parsed:
            st.error("❌ Failed to parse query. Try rephrasing.")
        else:
            st.markdown("## 🔍 Parsed Query")
            st.json(parsed)

            if not st.session_state.retrieved:
                st.session_state.retrieved = search(query)
            retrieved = st.session_state.retrieved
            clause_chunks = [f"[Chunk {i}] {chunk}" for i, chunk in retrieved]

            st.markdown("---")
            st.markdown("## 📄 Retrieved Clauses")
            for c in clause_chunks:
                st.markdown(f"> {c[:300]}...")

            if not st.session_state.decision:
                st.session_state.decision = evaluate_decision(parsed, clause_chunks)
            decision = st.session_state.decision

            decision_json = extract_json_from_text(decision)

            if decision_json:
                st.markdown("## 📌 Final Decision")
                st.markdown(f"- **Decision**: **{decision_json.get('decision')}**")
                st.markdown(f"- **Amount**: **{decision_json.get('amount')}**")
                st.markdown(f"- **Justification**: **{decision_json.get('justification')}**")

                # ✅ Save only once per query/file
                if not st.session_state.output_logged:
                    timestamp = datetime.now().isoformat()
                    log_data = {
                        "timestamp": timestamp,
                        "query": query,
                        "parsed": parsed,
                        "retrieved_clauses": clause_chunks,
                        "decision": decision_json
                    }

                    log_path = "logs/output_log.json"
                    existing_logs = []
                    if os.path.exists(log_path):
                        with open(log_path, "r") as f:
                            try:
                                data = json.load(f)
                                existing_logs = data if isinstance(data, list) else [data]
                            except json.JSONDecodeError:
                                existing_logs = []

                    existing_logs.append(log_data)
                    with open(log_path, "w") as f:
                        json.dump(existing_logs, f, indent=2)

                    save_to_db(timestamp, query, parsed, clause_chunks, decision_json)
                    st.session_state.output_logged = True

                pdf_buffer = generate_pdf(query, parsed, clause_chunks, decision_json)
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_buffer,
                    file_name="insurance_decision_report.pdf",
                    mime="application/pdf"
                )

                if decision_json.get("decision", "").lower() == "approved":
                    st.markdown("### ✅ This claim is approved!")

                    if not st.session_state.email_sent and not st.session_state.show_form:
                        if st.button("📨 Inform Insurance Company"):
                            st.session_state.show_form = True

                    if st.session_state.show_form and not st.session_state.email_sent:
                        with st.form("contact_form", clear_on_submit=False):
                            name = st.text_input("👤 Full Name")
                            phone = st.text_input("📱 Mobile Number")
                            submitted = st.form_submit_button("Send Email")

                            if submitted and name and phone:
                                email_body = f"""
Dear Insurance Team,

A new insurance claim has been processed with the following details:

👤 Name: {name}
📱 Mobile: {phone}
📌 Status: {decision_json.get("decision")}
💰 Amount: {decision_json.get("amount")}
🧾 Justification: {decision_json.get("justification")}

Please follow up directly with the claimant.

-- LLM Insurance Assistant
                                """
                                try:
                                    send_email(
                                        to_email="claims@insurancecompany.com",
                                        subject="New Approved Claim",
                                        body=email_body
                                    )
                                    st.session_state.email_sent = True
                                    st.success("📨 We’ve sent your claim request to the insurance company. They will contact you shortly.")
                                except Exception as e:
                                    st.error(f"❌ Email failed: {e}")
                            elif submitted:
                                st.warning("⚠️ Please enter all required details.")
                    elif st.session_state.email_sent:
                        st.success("📨 We’ve sent your claim request to the insurance company. They will contact you shortly.")
            else:
                st.error("⚠️ Could not parse decision JSON.")
                st.code(decision)