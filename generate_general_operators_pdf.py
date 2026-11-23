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
        footer_text = f"Operators in General: Theoretical Knowledge Guide | Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 25, footer_text)
        self.drawString(36, 25, "Computer Science & AI Engineering — Exam Preparation")
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
        topMargin=38,
        bottomMargin=46,
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
        spaceAfter=5,
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
    story.append(Paragraph("Operators in General: Comprehensive Oral Exam Guide", title_style))
    story.append(Paragraph("Computer Science & AI Engineering | Core Theory, Syntax, and Mechanics", subtitle_style))
    story.append(Paragraph("<b>Scope:</b> Programming Language Operators, Relational Operators, and AI/Computational Operators &nbsp;|&nbsp; <b>Format:</b> 1-Sentence Answers", meta_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceAfter=10))

    # Comprehensive list of General Operator questions
    qa_data = [
        (
            "1. Foundational Definition",
            "What is an operator in computer science and programming languages?",
            "An operator is a specialized symbol or keyword that instructs the compiler or interpreter to perform a specific mathematical, relational, or logical manipulation on one or more operands."
        ),
        (
            "2. Operator Arity",
            "How are operators classified according to their arity (operand count)?",
            "Operators are classified as unary when they accept one operand, binary when they accept two operands, and ternary when they operate on three operands."
        ),
        (
            "3. Precedence vs. Associativity",
            "What is the fundamental difference between operator precedence and operator associativity?",
            "Precedence determines the priority order in which different operators are evaluated in an expression, whereas associativity specifies the direction of evaluation for operators sharing equal precedence."
        ),
        (
            "4. Identity vs. Equality Operators",
            "What is the crucial difference between the equality operator (==) and the identity operator (is)?",
            "The equality operator checks whether two operands possess identical values, whereas the identity operator verifies whether both operands point to the exact same memory address."
        ),
        (
            "5. Short-Circuit Evaluation",
            "What is short-circuit evaluation in logical boolean operators?",
            "Short-circuit evaluation is the execution rule where the second operand of a logical AND or OR expression is evaluated only if the first operand is insufficient to determine the overall truth value."
        ),
        (
            "6. Operator Overloading",
            "What is operator overloading and how does it function in object-oriented languages?",
            "Operator overloading is a form of polymorphism allowing user-defined classes to define custom implementations for standard language operators using special methods such as dunder functions."
        ),
        (
            "7. Bitwise Operators",
            "What are bitwise operators and at what computational level do they operate?",
            "Bitwise operators manipulate integers at the individual binary digit level by executing boolean algebraic operations on corresponding bit positions."
        ),
        (
            "8. True Division vs. Floor Division",
            "How do true division (/) and floor division (//) operators differ in modern languages?",
            "True division always yields a floating-point quotient, whereas floor division truncates the division result down to the nearest integer."
        ),
        (
            "9. The Walrus Assignment Operator",
            "What is the purpose of the walrus assignment expression operator (:=)?",
            "The walrus operator enables assignment expressions by allowing a variable to be initialized and evaluated simultaneously within a conditional test or expression."
        ),
        (
            "10. Membership Operators",
            "What are membership operators and what do they verify?",
            "Membership operators test whether a target value or substring exists within a collection or sequence, returning a boolean result without requiring explicit indexing loops."
        ),
        (
            "11. Ternary Conditional Operator",
            "What is the ternary operator and what structural advantage does it offer?",
            "The ternary operator evaluates a boolean condition to select between two return expressions in a single compact statement, eliminating multi-line if-else branching."
        ),
        (
            "12. State-Space Search Operators in AI",
            "What is a search or transition operator in classical artificial intelligence?",
            "In state-space search, an operator is a transition function that transforms a current problem state into a valid successor state subject to preconditions and transition costs."
        ),
        (
            "13. Genetic Algorithm Operators",
            "What are genetic operators in evolutionary algorithms and what roles do they serve?",
            "Genetic operators are stochastic mechanisms, primarily crossover and mutation, that combine parental traits and introduce random perturbations to generate novel candidate solutions."
        ),
        (
            "14. Tensor / Computational Graph Operators",
            "What is an operator in deep learning frameworks like PyTorch or TensorFlow?",
            "In deep learning frameworks, an operator is an atomic computational node in a directed acyclic graph that performs a specific mathematical tensor transformation during forward and backward passes."
        ),
        (
            "15. Relational Algebra Operators",
            "What are relational operators in database systems and relational query engines?",
            "Relational operators, such as select, project, join, and union, are formal mathematical mappings that accept relations as input and produce filtered or combined relations as output."
        ),
        (
            "16. Differential Optimization Operators",
            "What is the role of differential operators such as gradients in machine learning optimization?",
            "Differential operators compute the vector of first-order partial derivatives of a scalar loss function with respect to model weights to determine the direction of steepest descent."
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
                ("TOPPADDING", (0, 0), (-1, -1), 4.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )

        story.append(KeepTogether([card, Spacer(1, 6)]))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated {filename}")

if __name__ == "__main__":
    out_pdf = os.path.abspath("Operators_General_Knowledge_Exam_Guide.pdf")
    build_pdf(out_pdf)

