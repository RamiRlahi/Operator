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
        footer_text = f"AI Engineering: Operators & Autonomous Agents — Knowledge Guide | Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 25, footer_text)
        self.drawString(36, 25, "CS496 AI Engineering — Theoretical Concepts")
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

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#2563eb"),
        spaceAfter=6,
    )

    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )

    q_text_style = ParagraphStyle(
        "QText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#0f172a"),
    )

    ans_text_style = ParagraphStyle(
        "AnsText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
    )

    tag_style = ParagraphStyle(
        "TopicTag",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1d4ed8"),
    )

    story = []

    # Title & Header
    story.append(Paragraph("AI Operators & Autonomous Systems: Conceptual Oral Exam", title_style))
    story.append(Paragraph("CS496 AI Engineering | Core Theory, Definitions, and Operating Principles", subtitle_style))
    story.append(Paragraph("<b>Subject:</b> Autonomous Agents & Operators &nbsp;|&nbsp; <b>Format:</b> Question & Single-Sentence Answer Cards", meta_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceAfter=12))

    # Pure knowledge / conceptual questions and 1-sentence answers
    qa_data = [
        (
            "1. Concept of an 'Operator'",
            "What distinguishes an 'Operator' or autonomous agent from a standard conversational chatbot?",
            "An operator is an agentic system equipped with reasoning loops and tool execution capabilities that autonomously perceives environment state, plans multi-step actions, and performs state-modifying operations on external systems rather than merely producing conversational text."
        ),
        (
            "2. The ReAct Framework",
            "What is the foundational principle of the ReAct (Reasoning + Acting) paradigm in AI engineering?",
            "ReAct synergizes chain-of-thought reasoning with domain-specific tool execution by iteratively alternating between generating thoughts to track plans and executing actions to observe environmental feedback."
        ),
        (
            "3. Write Idempotency",
            "What does idempotency mean in the context of tool execution, and why is it essential for autonomous agents?",
            "Idempotency is the property where an operation can be applied multiple times without changing the result beyond the initial execution, preventing catastrophic duplicate side effects during agent retries or re-planning."
        ),
        (
            "4. Indirect Prompt Injection (OWASP LLM01)",
            "What is an indirect prompt injection attack, and how does it compromise an agent via tool outputs?",
            "Indirect prompt injection occurs when untrusted data retrieved from external tools or databases contains adversarial instructions that hijack the model's execution context away from its original system prompt."
        ),
        (
            "5. Deterministic vs. Prompt Guardrails",
            "What is the fundamental difference between prompt-based guardrails and programmatic deterministic guardrails?",
            "Prompt-based guardrails rely on the probabilistic compliance of the language model to follow instructions, whereas deterministic guardrails enforce rigid, non-bypassable constraints directly in the execution code."
        ),
        (
            "6. Halting Problem & Bounded Execution",
            "Why are autonomous agent loops vulnerable to non-termination, and how is bounded execution guaranteed in computer science?",
            "Because autonomous decision-making can enter infinite reasoning or action cycles, bounded execution must enforce deterministic halting constraints such as hard iteration ceilings, monetary budget caps, and cycle detectors."
        ),
        (
            "7. Human-in-the-Loop (HITL) Architecture",
            "What is the primary architectural purpose of a Human-in-the-Loop (HITL) checkpoint in operational agent systems?",
            "A Human-in-the-Loop checkpoint establishes an authorization gatekeeper that halts autonomous execution before high-consequence state modifications, requiring verified human approval to proceed."
        ),
        (
            "8. Step Accuracy vs. Task Success Rate",
            "How does per-step accuracy differ from overall task success rate when evaluating agent trajectories?",
            "Per-step accuracy measures whether each discrete tool invocation strictly matches an ideal gold-standard path, whereas overall task success rate measures whether the agent successfully converged on the correct final system state regardless of exploratory steps."
        ),
        (
            "9. Read Tools vs. Write Tools",
            "In agent engineering, what is the core architectural difference between read tools and write tools?",
            "Read tools are idempotent, side-effect-free operations that query environment state, whereas write tools mutate persistent external state and require schema validation, transaction management, and approval barriers."
        ),
        (
            "10. Boundary Schema Validation",
            "Why is strict schema validation using tools like Pydantic critical at the boundary between language models and external APIs?",
            "Strict schema validation intercepts hallucinated, malformed, or missing parameters before tool execution, translating runtime errors into structured feedback that the model can understand and self-correct."
        ),
        (
            "11. ReAct vs. Plan-and-Solve (ReWOO)",
            "What is the core conceptual difference between a ReAct agent and a Plan-and-Solve agent?",
            "ReAct plans dynamically one step at a time based on continuous observation feedback, whereas Plan-and-Solve generates a complete upfront execution plan before running tools with minimal inter-step reasoning."
        ),
        (
            "12. Action Cycle Pathology",
            "What is an action cycle in agentic execution loops and how is it computationally detected?",
            "An action cycle is a pathology where an agent repeatedly executes the exact same tool with identical arguments, detected by tracking a hash or signature of consecutive tool invocations and halting when a frequency threshold is exceeded."
        ),
        (
            "13. Context Window Degradation",
            "How does trajectory length impact LLM reasoning reliability and token economics in multi-step agent loops?",
            "Longer trajectories increase cumulative token consumption while degrading reasoning accuracy due to attention attenuation over lengthy observation histories."
        ),
        (
            "14. Error Taxonomy & Fault Recovery",
            "Why should an autonomous agent system categorize errors into distinct taxonomical classes rather than treating all failures generically?",
            "Categorizing errors into distinct classes allows the control loop to apply specialized automated recovery strategies for recoverable errors while immediately escalating or halting on security violations."
        ),
    ]

    for topic, q, a in qa_data:
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
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ])
        )

        story.append(KeepTogether([card, Spacer(1, 7)]))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {filename}")

if __name__ == "__main__":
    out_pdf = os.path.abspath("Operator_Theoretical_Knowledge_Questions.pdf")
    build_pdf(out_pdf)

