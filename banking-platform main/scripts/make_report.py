"""Generate the self-contained, <=10-page A4 technical report (ReportLab)."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether,
                               PageBreak, PageTemplate, Paragraph, Spacer, Table,
                               TableStyle)

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "output/pdf/Technical_Report.pdf"
pdfmetrics.registerFont(TTFont("ReportSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("ReportSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFontFamily("ReportSans", normal="ReportSans", bold="ReportSans-Bold")
NAVY = colors.HexColor("#0E233B")
TEAL = colors.HexColor("#117F88")
LIGHT = colors.HexColor("#EAF5F5")
GRAY = colors.HexColor("#475569")


class Architecture(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = 480, 215

    def draw(self):
        c = self.canv

        def block(x, y, w, h, label, shade=LIGHT):
            c.setFillColor(shade)
            c.setStrokeColor(TEAL)
            c.roundRect(x, y, w, h, 7, fill=1, stroke=1)
            c.setFillColor(NAVY)
            c.setFont("ReportSans-Bold", 9)
            c.drawCentredString(x + w / 2, y + h / 2 - 3, label)

        def wire(x1, y1, x2, y2):
            c.setStrokeColor(GRAY)
            c.setLineWidth(1.1)
            c.line(x1, y1, x2, y2)

        block(175, 180, 130, 30, "Banking Client")
        block(175, 126, 130, 30, "Gateway")
        block(175, 68, 130, 30, "2PC Coordinator")
        block(5, 68, 125, 30, "Shard A: A1 / A2")
        block(350, 68, 125, 30, "Shard B: B1 / B2")
        block(5, 5, 125, 30, "PostgreSQL A", colors.HexColor("#EEF1F6"))
        block(175, 5, 130, 30, "Coordinator DB", colors.HexColor("#EEF1F6"))
        block(350, 5, 125, 30, "PostgreSQL B", colors.HexColor("#EEF1F6"))
        wire(240, 180, 240, 156)
        wire(240, 126, 240, 98)
        wire(175, 141, 67, 141)
        wire(67, 141, 67, 98)
        wire(305, 141, 412, 141)
        wire(412, 141, 412, 98)
        wire(175, 82, 130, 82)
        wire(305, 82, 350, 82)
        wire(67, 68, 67, 35)
        wire(240, 68, 240, 35)
        wire(412, 68, 412, 35)


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="Cover", parent=styles["Title"], fontName="ReportSans-Bold",
                          fontSize=24, leading=29, textColor=NAVY, spaceAfter=13))
styles.add(ParagraphStyle(name="Subtitle", fontName="ReportSans", fontSize=11,
                          leading=16, textColor=GRAY, alignment=TA_CENTER, spaceAfter=13))
styles.add(ParagraphStyle(name="SectionTitle", fontName="ReportSans-Bold", fontSize=16,
                          leading=20, textColor=NAVY, spaceBefore=10, spaceAfter=11))
styles.add(ParagraphStyle(name="BodySmall", fontName="ReportSans", fontSize=9.5,
                          leading=14, spaceAfter=8, textColor=NAVY))
styles.add(ParagraphStyle(name="Small", fontName="ReportSans", fontSize=8.2,
                          leading=12, spaceAfter=5, textColor=NAVY))
styles.add(ParagraphStyle(name="TableHead", fontName="ReportSans-Bold", fontSize=8.5,
                          leading=11, textColor=colors.white))
styles.add(ParagraphStyle(name="TableCell", fontName="ReportSans", fontSize=8.3,
                          leading=11, textColor=NAVY))


def p(s, small=False):
    return Paragraph(s, styles["Small" if small else "BodySmall"])


def section(label):
    return Paragraph(label, styles["SectionTitle"])


def bullets(items):
    return [p("&#8226; " + item) for item in items]


def tbl(rows, widths):
    data = [[Paragraph(str(cell), styles["TableHead" if index == 0 else "TableCell"])
             for cell in row] for index, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, TEAL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def footer(canvas, doc):
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(TEAL)
    canvas.line(22 * mm, 19 * mm, width - 22 * mm, 19 * mm)
    canvas.setFont("ReportSans", 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(22 * mm, 13 * mm, "Distributed Systems / Assignment 2 - Technical Report")
    canvas.drawRightString(width - 22 * mm, 13 * mm, f"Page {doc.page}")
    canvas.restoreState()


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=22 * mm,
                          rightMargin=22 * mm, topMargin=20 * mm, bottomMargin=26 * mm,
                          title="Assignment 2 - Distributed Banking Platform Technical Report",
                          author="Distributed Banking Platform Project")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  leftPadding=0, rightPadding=0, bottomPadding=0, topPadding=0)
    doc.addPageTemplates(PageTemplate(id="normal", frames=[frame], onPage=footer))
    story = []

    # Page 1: executive view and architecture.
    story += [Spacer(1, 15 * mm), Paragraph("Distributed Banking<br/>Platform", styles["Cover"]),
              Paragraph("Assignment 2 - Sharding, Replication &amp; Distributed Transactions",
                        styles["Subtitle"]),
              p("<b>Core stack:</b> Python 3.12, FastAPI, PostgreSQL 16, psycopg3, Docker Compose."),
              p("<b>Scope:</b> Two independent account shards, two stateless application replicas per shard, "
                "Gateway failover, local ACID operations, real PostgreSQL 2PC, durable decisions and recovery."),
              Spacer(1, 7 * mm), Architecture(),
              p("<b>Live verification (2026-10-25):</b> An Apple Silicon Mac with Docker 29.1.3 "
                "and Compose 2.40.3 built and ran all nine core containers. Actual student-supplied "
                "terminal transcripts confirm all seven experiments, 5/5 protocol tests, real "
                "Coordinator/participant recovery, and PostgreSQL restart persistence. A final "
                "seven-image rebuild was followed by a second successful run of every experiment "
                "and the participant-outage recovery test."), PageBreak()]

    # Page 2: placement, routing and ACID.
    story += [section("1. Sharding and routing"),
              tbl([["Shard", "Account range", "App replicas", "Persistent database"],
                   ["A", "A0001 - A1000", "A1, A2", "db-a"],
                   ["B", "A1001 - A2000", "B1, B2", "db-b"]],
                  [60, 125, 112, 160]), Spacer(1, 7 * mm),
              p("A JSON Shard Map defines disjoint numeric ranges. Both Gateway and shard servers reject "
                "invalid/misrouted account IDs. Each authoritative balance exists only in its owning "
                "PostgreSQL database; both replicas of a shard share that database."),
              section("2. Load balancing and availability"),
              p("The Gateway polls each replica every second, verifies the response shard ID, and uses "
                "a per-shard, lock-protected Round Robin counter. Transport failures and HTTP 5xx "
                "responses mark that replica unhealthy; subsequent requests are retried on another "
                "healthy replica of the <b>same shard</b>. Each response and log identifies the replica."),
              section("3. Concurrency and local ACID"),
              *bullets(["Balances use NUMERIC(20,2); negative balance is disallowed by SQL constraints.",
                        "Deposits, withdrawals, and same-shard transfers use database transactions and "
                        "row-level FOR UPDATE locks; transfer locks both accounts in stable ID order.",
                        "Every local write has a UUID idempotency receipt. Replays return its stored "
                        "result; conflicting reuse gets HTTP 409. Lock waits have a bounded timeout.",
                        "Seed creates 2,000 sample accounts; subsequent restarts skip an already complete "
                        "shard seed, avoiding locks from prepared transactions. Docker volumes preserve "
                        "data and journals."]), PageBreak()]

    # Page 3: sequence and durability.
    story += [section("4. Real two-phase commit (2PC)"),
              p("Cross-shard transfers are assigned a unique transaction UUID. The Coordinator "
                "persistently tracks INITIATED, PREPARING, PREPARED, COMMIT_DECIDED / ABORT_DECIDED, "
                "and COMPLETED. Participant-side PREPARE performs a tentative debit or credit plus "
                "receipt insertion, then calls PostgreSQL <b>PREPARE TRANSACTION</b>. This is not "
                "a pair of unrelated committed UPDATE statements."),
              tbl([["Step", "Coordinator / participant interaction", "Durability point"],
                   ["1", "Coordinator -> DB C: INSERT INITIATED, then PREPARING", "Coordinator journal"],
                   ["2", "Coordinator -> A: PREPARE debit; A -> Coordinator: YES", "Postgres A prepared XID"],
                   ["3", "Coordinator -> B: PREPARE credit; B -> Coordinator: YES", "Postgres B prepared XID"],
                   ["4", "Coordinator -> DB C: PREPARED, then COMMIT_DECIDED", "<b>Commit decision durable before messages</b>"],
                   ["5", "Coordinator -> A/B: COMMIT; each runs COMMIT PREPARED", "Atomic balance + receipt"],
                   ["6", "Coordinator -> DB C: store each ACK; COMPLETED", "Both ACKs required for success"]],
                  [43, 250, 164]), Spacer(1, 6 * mm),
              p("<b>NO vote:</b> Coordinator records ABORT_DECIDED before messaging both shards. "
                "ABORT creates a durable participant tombstone before ROLLBACK PREPARED, preventing "
                "a late PREPARE from undoing the abort. Duplicate COMMIT or ABORT is detected by "
                "the participant journal, prepared-XID listing and in-transaction committed receipts."),
              p("<b>Response rule:</b> COMMITTED is returned only after both participant ACKs. "
                "When a participant is unreachable, the externally visible state is PENDING, "
                "retrievable via transaction ID or original request UUID."), PageBreak()]

    # Page 4: recovery decision table.
    story += [section("5. Durable recovery and failure injection"),
              p("The Coordinator DB stores every global decision and participant acknowledgement. "
                "On restart and every two seconds, the recovery worker scans incomplete records. "
                "Database advisory locks serialize recovery with active coordinations. Undecided "
                "transactions are durably ABORTed; COMMIT_DECIDED transactions are retried toward "
                "COMMIT only. The decision is never reversed after persistence."),
              tbl([["Injected failure", "Expected invariant", "Executable proof"],
                   ["First shard YES, second NO", "Abort first prepared XID, no balance effect", "test_protocol.py: second vote rejection"],
                   ["Coordinator stops after PREPARED", "After restart, durable ABORT and rollback both", "experiment_6.sh: after_prepare"],
                   ["Coordinator stops after COMMIT_DECIDED", "Recover same COMMIT, collect both ACKs", "experiment_6.sh: after_commit_decision"],
                   ["Shard B unreachable after COMMIT", "PENDING until restored, then COMMITTED", "experiment_participant_disconnect.sh"],
                   ["Repeated COMMIT/ABORT", "No double debit/credit; receipts unchanged", "test_duplicate_commit_messages"],
                   ["Concurrent overlapping transfers", "Atomic outcomes and conserved sum", "test_experiment_7"]],
                  [130, 163, 164]), Spacer(1, 7 * mm),
              p("A hard Coordinator crash uses <b>os._exit(91)</b> immediately after a durable "
                "PREPARED or COMMIT_DECIDED write. The restart test queries DB C, checks the "
                "retained decision, then verifies participant receipts, cleanup of pg_prepared_xacts "
                "and final acknowledgements. Fault injection is opt-in and internal-token protected."), PageBreak()]

    # Page 5: test matrix and truthful results.
    story += [section("6. Required experiments and observed status"),
              tbl([["#", "Experiment", "Acceptance check", "Mac result"],
                   ["1", "Shard distribution", "Exclusive DB records + correct routing", "PASS"],
                   ["2", "Replica load", "A1/A2 and B1/B2 observed", "PASS"],
                   ["3", "Concurrent replica operations", "40 writes; balance 1000.00", "PASS"],
                   ["4", "Replica interruption", "Stop A1; 183 served, 0 failed", "PASS"],
                   ["5", "Local and distributed transfer", "Atomic local SQL + both 2PC ACKs", "PASS"],
                   ["6", "Interrupted 2PC", "PREPARED -> ABORT; COMMIT_DECIDED -> COMMIT", "PASS"],
                   ["7", "Concurrent shared-account 2PC", "12 committed; sum 4000.00", "PASS"]],
                  [27, 148, 190, 92]), Spacer(1, 8 * mm),
              p("<b>Supplementary observed checks:</b> Five protocol tests passed (retry-safe deposit/transfer, "
                "participant NO vote, repeated COMMIT, insufficient funds). Participant B outage: "
                "durable COMMIT remained PENDING with A acknowledged; B returned; both ACKs became true "
                "and the same transaction finished COMMITTED. The outage test passed again after "
                "rebuilding all images. Both shard DBs showed zero remaining pg_prepared_xacts; all "
                "three PostgreSQL servers reported max_prepared_transactions=100."),
              p("<b>Persistence:</b> After actual restarts of db-a, db-b, and db-coordinator, balances "
                "A0091=979.00 and A1091=1021.00 were unchanged. An existing Coordinator record "
                "remained COMPLETED / COMMIT with both acknowledgements true. The full non-disruptive "
                "integration suite passed 10/10 tests in 2.96 seconds without cache warnings; "
                "4 unit tests and a full CLI smoke test also passed on the rebuilt images."), PageBreak()]

    # Page 6: limitations and delivery.
    story += [section("7. Limitations and next steps"),
              *bullets(["Classic 2PC may block participant rows while the Coordinator or a DB is "
                        "unreachable. The assignment does not require PostgreSQL database failover.",
                        "Public end-user authentication, TLS, audit compliance, multicurrency, "
                        "high availability for Coordinator DB, and production observability are outside this educational core.",
                        "Optional Bonus I (live migration to shard C with CDC, epochs and crash "
                        "recovery) and Bonus II (custom automatic replica replacement) are NOT "
                        "IMPLEMENTED and require prior student approval.",
                        "Mac validation transcripts constitute actual external Docker evidence; the original "
                        "code-generation sandbox had no Docker. GitHub/Docker Hub publication is not done.",
                        "A fault test revealed redundant account seeding could block on prepared XIDs; "
                        "the startup guard and no-deps Coordinator restart were applied and recovery retested."]),
              section("8. Artifacts / reproducibility"),
              *bullets(["docker-compose.yml, Dockerfile, .env.example and PostgreSQL SQL schemas;",
                        "Four FastAPI banking replicas, shard-aware Gateway, independent 2PC Coordinator, CLI;",
                        "Unit tests, DB-backed integration tests, seven experiment scripts plus "
                        "participant-outage fault injection;",
                        "README, architecture/2PC sequence diagram, requirement matrix, "
                        "15-minute demo plan, GitHub and Docker Hub instructions."]),
              Spacer(1, 12 * mm),
              p("<b>Engineering conclusion.</b> The mandatory 2PC protocol and seven graded experiments "
                "were exercised successfully on the student's Docker host, including real prepared XIDs, "
                "Coordinator hard crashes, participant disconnection, replay and persistence. The observed "
                "startup deadlock was repaired and retested. This is an educational prototype, not a "
                "production-ready financial system; publish only after replacing development secrets."),
              Spacer(1, 5 * mm), p("Reference: University PDF, <i>Assignment 2: Distributed Banking Platform</i>, "
                                 "sections 1-9. The repository README gives complete commands and "
                                 "reproducibility details.", small=True)]

    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    main()

