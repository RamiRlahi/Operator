from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

OUT = Path('output/pdf')
OUT.mkdir(parents=True, exist_ok=True)
NAVY = colors.HexColor('#15324b')
BLUE = colors.HexColor('#176b87')
PALE = colors.HexColor('#eaf3f6')
INK = colors.HexColor('#253746')
MUTED = colors.HexColor('#607381')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='CoverTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=25, leading=30, textColor=NAVY, alignment=TA_CENTER, spaceAfter=10))
styles.add(ParagraphStyle(name='Sub', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=16, textColor=BLUE, alignment=TA_CENTER, spaceAfter=8))
styles.add(ParagraphStyle(name='H1x', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, leading=19, textColor=NAVY, spaceBefore=12, spaceAfter=6, keepWithNext=True))
styles.add(ParagraphStyle(name='H2x', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=BLUE, spaceBefore=7, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name='Bodyx', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.5, leading=14, textColor=INK, spaceAfter=6))
styles.add(ParagraphStyle(name='Smallx', parent=styles['BodyText'], fontName='Helvetica', fontSize=8, leading=11, textColor=MUTED, spaceAfter=4))
styles.add(ParagraphStyle(name='Cellx', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.2, leading=11, textColor=INK, spaceAfter=0))
styles.add(ParagraphStyle(name='CellHeadx', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=8.2, leading=11, textColor=colors.white, spaceAfter=0))
styles.add(ParagraphStyle(name='Termx', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=NAVY, spaceAfter=2))

def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#d7e1e7'))
    canvas.line(0.65*inch, 0.52*inch, 7.85*inch, 0.52*inch)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.65*inch, 0.34*inch, 'The Operator | CS496 AI Engineering | Fall 2026')
    canvas.drawRightString(7.85*inch, 0.34*inch, f'Page {doc.page}')
    canvas.restoreState()

def P(txt, style='Bodyx'):
    return Paragraph(txt, styles[style])

def make_table(headers, rows, widths):
    data = [[P(x, 'CellHeadx') for x in headers]]
    data += [[P(str(x), 'Cellx') for x in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),NAVY), ('GRID',(0,0),(-1,-1),0.35,colors.HexColor('#d3dee5')),
        ('VALIGN',(0,0),(-1,-1),'TOP'), ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
    ]))
    return t

story = [Spacer(1,0.45*inch), P('PROJECT REPORT', 'Sub'), P('The Operator', 'CoverTitle'), P('A tool-using agent for support ticket triage', 'Sub'), Spacer(1,0.2*inch),
         P('<b>CS496 AI Engineering | Project 3</b><br/>Mediterranean Institute of Technology (MedTech)<br/>Project owner: Rami Rlahi | Instructor: Dr. Abdeldjalil Labed<br/>Language level: B2 English', 'Sub'),
         Spacer(1,0.25*inch), P('Project summary', 'H1x'),
         P('The Operator is a software agent that helps handle fictional customer support tickets. It reads ticket and account information, finds relevant company policies, and can prepare or carry out approved changes in a local SQLite database. The project focuses on safe tool use, clear approval steps, and reliable testing. The database contains sample data, so actions do not affect real customers.', 'Bodyx'),
         P('1. Purpose and scope', 'H1x'),
         P('Support work often requires several steps: understanding a request, checking the customer’s account, finding the correct policy, and updating a record. The Operator brings these steps into one controlled process. It is a project demonstration, not a live customer service system. Its tests and benchmark run offline with fictional data.', 'Bodyx'),
         P('The system can inspect information, update ticket details, save a reply draft, or record an approved action such as a refund or cancellation. Email and password reset actions create sandbox records only. The system does not send real emails or change real accounts.', 'Bodyx'),
         P('2. Main parts and tools', 'H1x'),
         P('The agent communicates with the application through six named tools. Each tool has a specific job.', 'Bodyx'),
         make_table(['Tool','Purpose'],[
             ('get_ticket','Reads the selected ticket, including the customer’s message.'),
             ('search_knowledge_base','Finds company policy and procedure articles.'),
             ('check_customer_status','Reads account details and order history for the ticket customer.'),
             ('update_ticket_status','Changes ticket status and adds tags after approval.'),
             ('draft_reply','Saves an approved reply in the local drafts table.'),
             ('execute_action','Records an approved sandbox action, such as a refund or cancellation.'),
         ],[1.65*inch,5.35*inch]),
         P('Read tools only inspect information. Write tools change stored information, so they need stronger checks. The system checks tool names and arguments before it runs a tool.', 'Bodyx'),
         P('3. How a request is handled', 'H1x'),
         P('For each request, the model can choose a tool or give a final answer. The application checks the choice, runs the tool, records its result, and sends that result back to the model. The model can then decide what to do next. This repeated process helps it use current ticket and account information instead of relying on a single guess.', 'Bodyx'),
         P('Before a write action, the terminal shows the action type, details, and key. A human operator can approve or reject it. If the operator rejects it, the run stops without making that change. Each accepted action and its related database update are saved together as one transaction.', 'Bodyx'),
         P('4. Safety controls', 'H1x'),
         make_table(['Control','How it helps'],[
             ('Fictional sandbox','The agent works with resettable SQLite sample data, not real customer records.'),
             ('Approval checkpoint','An operator must approve high-impact changes before they are made.'),
             ('Action keys','A repeated operation with the same key is detected, helping prevent duplicate refunds or other changes.'),
             ('Input and policy checks','Customer text and tool results are treated as data. Python checks enforce limits, recipient rules, and available tools.'),
             ('Database transaction','A write and its related update succeed together or are rolled back together if an error occurs.'),
             ('Execution limits','The loop has a maximum number of model attempts and stops on a final answer, refusal, provider error, or spending limit.'),
         ],[1.6*inch,5.4*inch]),
         P('The model can make mistakes, so safety does not depend only on the model following written instructions. The application also checks important rules in code.', 'Bodyx'),
         P('5. Testing and results', 'H1x'),
         P('The test suite and 35-scenario benchmark ran offline. Each scenario began with a reset database. The records included tool arguments, results, timing, approval decisions, and the reason the run stopped.', 'Bodyx'),
         make_table(['Measure','Offline result'],[
             ('Scenario success','35 of 35 passed the declared path and final-state checks.'),
             ('Ordered step accuracy','72.67% average match to the expected order of tool calls.'),
             ('Tool-call precision','72.67% average for expected calls that returned valid results or expected errors.'),
             ('Unmatched calls','1.20 per task on average.'),
             ('Injected-fault recovery','3 of 3 faults were recovered.'),
             ('Prompt-injection scenarios','7 of 7 passed escalation and blocked-action checks.'),
             ('Attempt-limit violations','0.'),
             ('Task latency','Median: 1.4 ms; 95th percentile: 3.0 ms.'),
             ('Average estimated tokens','4,503 per task.'),
         ],[2.0*inch,5.0*inch]),
         P('Scenario success checks whether the final result met the test rules. Ordered step accuracy checks the tool sequence. These measures differ: a task can succeed even if the agent made extra or different tool calls.', 'Bodyx'),
         P('6. Cost, limits, and future work', 'H1x'),
         P('The offline benchmark used zero API credits. Based on example input and output prices, estimated use was about $0.000803 per task, or $0.0803 for 100 similar tasks. This is an estimate, not a bill. The live model connection is configured locally, but live routing, usage, and prompt-injection behavior were not measured in this benchmark.', 'Bodyx'),
         P('The results apply to the fictional data and tests used here. They do not prove that every live customer request will be handled correctly. A useful next step is to run a controlled live evaluation with approved test accounts, then review errors and safety checks before any wider use.', 'Bodyx'),
         P('7. Conclusion', 'H1x'),
         P('The Operator shows how an AI agent can use tools to handle a support ticket through several steps. Its design combines database checks, human approval, action keys, and execution limits. Offline results were strong for the tested scenarios, while live performance and behavior still need separate evaluation.', 'Bodyx'),
         Spacer(1,6), P('For technical terms used in this report, see the separate Operator Terminology Guide.', 'Smallx')]
doc = SimpleDocTemplate(str(OUT/'Operator_Project_Report_B2.pdf'), pagesize=letter, rightMargin=0.65*inch, leftMargin=0.65*inch, topMargin=0.62*inch, bottomMargin=0.72*inch, title='The Operator - B2 Project Report', author='CS496 AI Engineering')
doc.build(story, onFirstPage=footer, onLaterPages=footer)

terms = [
('AI agent','A software system that uses an AI model to choose steps and tools to reach a goal.'),
('Autonomous','Able to carry out some steps without a person choosing every step. In this project, important changes still need human approval.'),
('Tool','A named function the agent can call to read information or request a change.'),
('Tool call','One request from the agent to run a particular tool with specific information.'),
('ReAct loop','A repeated process in which the model thinks about the next step, takes an action with a tool, and checks the result.'),
('Observation','Information returned by a tool after it runs.'),
('SQLite','A small database system that stores information in a local file. This project uses it for fictional records.'),
('Sandbox','A separated, safe place for testing. The project sandbox can be reset and does not contain live customer data.'),
('Read tool','A tool that looks up information without changing saved data.'),
('Write tool','A tool that changes saved information, such as a ticket or account record.'),
('Side effect','A change caused by an operation, such as adding a refund record or changing an order status.'),
('Idempotency','A safety property: repeating the same operation with the same key does not repeat its effect.'),
('Idempotency key','A unique label attached to an operation. The database uses it to recognize a repeated request.'),
('Transaction','A group of database changes treated as one unit. All changes are saved together, or none are saved.'),
('Rollback','Undoing changes from a transaction when an error occurs, so the database returns to its earlier state.'),
('Human-in-the-loop (HITL)','A design in which a person reviews or approves an action before the system continues.'),
('Prompt injection','Text that tries to trick an AI into ignoring its instructions. It can appear inside a customer message or retrieved information.'),
('Untrusted input','Information that may be incorrect or hostile, such as a customer message. The system should treat it as data, not as instructions.'),
('Guardrail','A rule or check that limits what the system can do. It may be written in model instructions or enforced by application code.'),
('Schema validation','Checking that the fields and values in a request have the required structure before using them.'),
('Dispatcher','Application code that checks a tool request and sends it to the correct tool.'),
('Bounded execution','A limit that ensures the agent cannot keep running forever, for example a maximum number of attempts.'),
('Model attempt','One request sent to the AI model. It is counted even if the model does not call a tool.'),
('Provider error','A problem from the external AI service or its connection, such as a timeout.'),
('Latency','The time between making a request and receiving a result.'),
('Median','The middle value after results are sorted. Half of measured tasks took less time and half took more.'),
('95th percentile','A value that 95% of measured tasks were at or below. It describes slower cases better than the median.'),
('Benchmark','A fixed set of tests used to measure system behavior in repeatable conditions.'),
('Scenario success','Whether a test case reached the expected final result and met its required checks.'),
('Ordered step accuracy','How often tool calls matched the expected tools and order in a benchmark.'),
('Tool-call precision','The share of expected tool calls that produced valid results or the expected errors.'),
('Fault injection','Deliberately adding a controlled error, such as a timeout, to see whether the system recovers safely.'),
('API credit','A unit of paid use for an online service. The offline benchmark used no API credits.'),
('Token','A small piece of text processed by an AI model. A token can be a word, part of a word, or punctuation.'),
]
gstory = [Spacer(1,0.15*inch), P('REFERENCE GUIDE', 'Sub'), P('Hard Terminology', 'CoverTitle'), P('The Operator | Plain-English explanations', 'Sub'), Spacer(1,5),
          P('Use this guide when a technical word in the project report is unfamiliar. Explanations are written in plain English and refer to this project where useful.', 'Bodyx')]
for term, definition in terms:
    gstory.append(KeepTogether([P(term, 'Termx'), P(definition, 'Bodyx'), Spacer(1,3)]))
gdoc = SimpleDocTemplate(str(OUT/'Operator_Terminology_Guide.pdf'), pagesize=letter, rightMargin=0.7*inch, leftMargin=0.7*inch, topMargin=0.62*inch, bottomMargin=0.72*inch, title='The Operator - Hard Terminology Guide', author='CS496 AI Engineering')
gdoc.build(gstory, onFirstPage=footer, onLaterPages=footer)
print('Created:', *(str(p) for p in sorted(OUT.glob('*.pdf'))), sep='\n')
