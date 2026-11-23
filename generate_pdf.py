import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748b"))
        footer_text = f"The Operator — Oral Defense Q&A Guide | Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 25, footer_text)
        self.drawString(36, 25, "CS496 AI Engineering — MedTech")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(36, 38, letter[0] - 36, 38)
        self.restoreState()


def build_pdf(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=48,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#2563eb"),
        spaceAfter=6,
    )

    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
    )

    q_num_style = ParagraphStyle(
        "QNum",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1e3a8a"),
    )

    q_text_style = ParagraphStyle(
        "QText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
    )

    ans_label_style = ParagraphStyle(
        "AnsLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#047857"),
    )

    ans_text_style = ParagraphStyle(
        "AnsText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
    )

    tag_style = ParagraphStyle(
        "TopicTag",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )

    story = []

    # Title & Header
    story.append(Paragraph("The Operator: Viva & Oral Defense Guide", title_style))
    story.append(Paragraph("CS496 AI Engineering — Project 3 (MedTech) | Rapid 1-Sentence Answer Cards", subtitle_style))
    story.append(Paragraph("<b>Project Owner:</b> Rami Rlahi &nbsp;|&nbsp; <b>Instructor:</b> Dr. Abdeldjalil Labed &nbsp;|&nbsp; <b>Evaluation:</b> 35 Scenarios / 100% Pass", meta_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceAfter=14))

    # 12 Curated Questions and strictly 1-sentence answers
    qa_data = [
        (
            "1. Architecture & Reasoning Pattern",
            "Why did you choose the ReAct (Reason + Act) loop pattern over a static workflow pipeline?",
            "The ReAct loop enables the agent to dynamically inspect non-deterministic customer data, execute multi-step tool reasoning, and self-correct from validation errors before committing state changes."
        ),
        (
            "2. Mathematical Termination Guarantee",
            "How does your agent mathematically guarantee that the execution loop will always terminate without runaway execution?",
            "Loop termination is strictly guaranteed by four independent bounds: a hard step ceiling of 10 steps, a cumulative monetary budget cap of $0.25, an identical action cycle detector, and a normal done-rule condition."
        ),
        (
            "3. State Safety & Write Idempotency",
            "What is idempotency and how does your system prevent duplicate database side effects like double refunds?",
            "Idempotency is enforced by requiring deterministic keys formatted as {ticket_id}-{action_type}-{id} before executing writes, verifying prior execution in the database, and leveraging SQLite unique constraints to block duplicate mutations."
        ),
        (
            "4. Postmortem Bug: Tag Idempotency",
            "How did you resolve the tag set idempotency bug identified during benchmark regression testing?",
            "We replaced strict set equality checking with subset containment, ensuring that re-submitting an existing tag subset does not trigger an unnecessary database rewrite when tags cumulatively expand."
        ),
        (
            "5. Threat Modeling & Prompt Injection",
            "What is an indirect prompt injection attack and how does your architecture defend against it?",
            "Indirect prompt injection occurs when untrusted customer inputs contain adversarial override commands, which we mitigate through structural <UNTRUSTED_CUSTOMER_INPUT> delimiters, system prompt invariants, and hard programmatic policy caps such as the $150 refund limit."
        ),
        (
            "6. Human-in-the-Loop Checkpoint Gatekeeper",
            "What happens when a human operator rejects a proposed write action at the checkpoint gate?",
            "The checkpoint returns a UserRejectionError, prompting the loop to immediately record the operator's rationale, mark the trajectory status as HUMAN_REJECTED, and halt execution without altering database state."
        ),
        (
            "7. Error Taxonomy & Self-Correction",
            "Why does the system suppress raw Python stack traces and return formatted plain-text diagnostics to the LLM?",
            "Clean schema error messages prevent context window pollution and provide actionable parameter feedback that enables the LLM to successfully self-correct malformed arguments in its very next turn."
        ),
        (
            "8. Evaluation Metrics & Trajectory Analysis",
            "Why is your Overall Task Success Rate 100% while Per-Step Accuracy is only 56.43%?",
            "Task Success Rate measures whether the final business objective was achieved, whereas Per-Step Accuracy penalizes valid alternative paths or extra exploratory queries that still arrive at the correct final resolution."
        ),
        (
            "9. Postmortem Bug: Substring Collision",
            "What caused the 'delivered' substring false-positive bug and how was it corrected?",
            "The agent used a naive substring search for the word 'delivered' to block invalid shipment cancellations, which unintentionally blocked legitimate damaged-item refund requests because the customer's purchase history legitimately contained 'Status: DELIVERED'."
        ),
        (
            "10. Dual-Engine LLM Infrastructure",
            "Why did you implement a dual-engine LLM architecture with a deterministic mock client?",
            "The dual architecture decouples regression testing from external cloud API network partitions, rate limits, and billing costs, allowing 100% reproducible offline test execution alongside live OpenAI integration."
        ),
        (
            "11. Account Hijacking & Security Invariants",
            "How do you prevent an attacker from bypassing policy constraints to steal customer accounts via password reset?",
            "The execute_action tool strictly validates that the requested password reset destination matches the verified customer email on record, throwing a SecurityViolationError if an external address is requested."
        ),
        (
            "12. Cost Economics & 100x Scale Modeling",
            "What is the projected operational cost of running this agent at a scale of 10,000 tickets per day?",
            "At an average consumption of 5,200 tokens ($0.00082 USD) per ticket using gpt-4o-mini, processing 10,000 tickets costs approximately $8.25 per day."
        ),
    ]

    for topic, q, a in qa_data:
        # Build a visual card for each Q&A
        table_content = [
            [
                Paragraph(f"<b>TOPIC:</b> {topic.upper()}", tag_style),
            ],
            [
                Paragraph(f"<b>Question:</b> {q}", q_text_style),
            ],
            [
                Paragraph(f"<b>1-Sentence Answer:</b> {a}", ans_text_style),
            ],
        ]

        card = Table(table_content, colWidths=[letter[0] - 72])
        card.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ])
        )

        story.append(KeepTogether([card, Spacer(1, 9)]))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {filename}")

if __name__ == "__main__":
    out_pdf = os.path.abspath("Operator_Viva_Exam_Questions.pdf")
    build_pdf(out_pdf)

