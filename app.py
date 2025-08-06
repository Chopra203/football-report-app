from flask import Flask, render_template, request, send_file, url_for, redirect, flash, abort, Response
import io
import os
import time
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

from sqlalchemy import func 
from reportlab.lib import colors
import csv 

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import black, blue, HexColor, lightgrey
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from flask_migrate import Migrate

from dotenv import load_dotenv
load_dotenv()

# IMPORTANT: Ensure this line is present and correct at the very top of your file
from werkzeug.security import generate_password_hash, check_password_hash 


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here' # IMPORTANT: CHANGE THIS TO A STRONG, UNIQUE, LONG SECRET KEY!

# --- Configuration for file uploads ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Configuration for PDF report storage ---
REPORT_FOLDER = 'reports'
app.config['REPORT_FOLDER'] = REPORT_FOLDER

# --- Database Configuration (SQLite) ---
# Use the live DATABASE_URL if it's available, otherwise use local SQLite
database_uri = os.environ.get('DATABASE_URL') or 'sqlite:///football_reports.db'
app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Database Models ---

class Club(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    users = db.relationship('User', backref='club', lazy=True)
    players = db.relationship('Player', backref='club', lazy=True)
    matches = db.relationship('Match', backref='club', lazy=True)

    def __repr__(self):
        return f'<Club {self.name}>'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_name = db.Column(db.String(100), nullable=False)
    coach_name = db.Column(db.String(100)) # ADD THIS LINE
    sub_team = db.Column(db.String(50)) 
    
    player_team = db.Column(db.String(100))
    primary_positions = db.Column(db.String(100))
    report_period_start = db.Column(db.String(20))
    report_period_end = db.Column(db.String(20))
    matches_covered = db.Column(db.Text)

    matches_played = db.Column(db.Integer)
    total_minutes_played = db.Column(db.Integer)
    goals = db.Column(db.Integer)
    assists = db.Column(db.Integer)

    technical_tactical_notes = db.Column(db.Text)
    physical_notes = db.Column(db.Text)
    psychological_notes = db.Column(db.Text)
    social_notes = db.Column(db.Text)

    overall_performance_summary = db.Column(db.Text)
    key_strengths_exhibited = db.Column(db.Text)
    primary_areas_development = db.Column(db.Text)
    recommended_action_plan = db.Column(db.Text)

    jersey_number = db.Column(db.Integer)
    position = db.Column(db.String(50))
    dob = db.Column(db.String(20))
    preferred_foot = db.Column(db.String(20))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    
    pdf_report_path = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)

    def __repr__(self):
        return f'<Player {self.player_name} ({self.jersey_number})>'

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    competition = db.Column(db.String(100))
    season = db.Column(db.String(50))
    match_date = db.Column(db.String(20), nullable=False)
    venue = db.Column(db.String(100))
    weather_pitch_conditions = db.Column(db.Text)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    final_score_home = db.Column(db.Integer)
    final_score_away = db.Column(db.Integer)
    home_formation_initial = db.Column(db.String(50))
    away_formation_initial = db.Column(db.String(50))
    home_lineup_notes = db.Column(db.Text)
    away_lineup_notes = db.Column(db.Text)
    home_attacking_phase = db.Column(db.Text)
    home_defensive_phase = db.Column(db.Text)
    home_key_transitions = db.Column(db.Text)
    away_attacking_phase = db.Column(db.Text)
    away_defensive_phase = db.Column(db.Text)
    away_key_transitions = db.Column(db.Text)
    overall_match_summary = db.Column(db.Text)
    key_turning_points = db.Column(db.Text)
    man_of_the_match = db.Column(db.String(100))
    final_analyst_notes = db.Column(db.Text)

    pdf_report_path = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)

    def __repr__(self):
        return f'<Match {self.home_team} vs {self.away_team} on {self.match_date}>'


# --- Flask-Login User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Helper function for checking allowed file extensions ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- ReportLab Style Definitions ---
_styles = getSampleStyleSheet()
_styles.add(ParagraphStyle(
    name='MyCenteredTitle',
    alignment=TA_CENTER,
    fontSize=24,
    spaceAfter=16,
    fontName='Helvetica-Bold',
    textColor=colors.HexColor('#4CAF50')
))
_styles.add(ParagraphStyle(
    name='MySectionHeading',
    alignment=TA_LEFT,
    leftIndent=0,
    fontSize=16,
    # spaceAfter is no longer needed here
    spaceBefore=16,
    fontName='Helvetica-Bold',
    textColor=colors.HexColor('#212121')
))
_styles.add(ParagraphStyle(name='MyKeyInfo', fontSize=10, spaceAfter=6, leading=14, fontName='Helvetica'))
_styles.add(ParagraphStyle(
    name='CombinedBodyText',
    fontSize=10,
    spaceAfter=10,
    leading=14,
    alignment=TA_JUSTIFY, # Changed from TA_LEFT
    fontName='Helvetica',
    textColor=colors.HexColor('#4F4F4F')
))
_styles.add(ParagraphStyle(name='MatchDetail', fontSize=11, spaceAfter=8, leading=14, fontName='Helvetica'))
# --- PDF Generation Functions (Directly uses Player/Match object attributes) ---

# In app.py

# ... (all your existing imports should be here)
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from datetime import datetime # Make sure this import is here
from reportlab.lib.units import inch # And this one
from reportlab.lib import colors # And this one
# ... (rest of your app.py code)
from datetime import datetime # Make sure this import is here
from reportlab.lib.units import inch # And this one
from reportlab.lib import colors # And this one

def format_date_dmy(date_string):
    """Safely converts a YYYY-MM-DD string to DD/MM/YYYY for display."""
    if not date_string: return ''
    try: return datetime.strptime(date_string, '%Y-%m-%d').strftime('%d/%m/%Y')
    except (ValueError, TypeError): return date_string

def draw_header(canvas, doc, logo_path=None):
    """Draws the custom header and page background on each page."""
    canvas.saveState()
    page_width, page_height = doc.pagesize

    # --- NEW: Set the background color for the entire page ---
    # This draws a colored rectangle that covers the whole page.
    canvas.setFillColor(colors.HexColor('#FFFFFF'))
    canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)

    # --- Header drawing logic (we reset the color for the text and lines) ---
    canvas.setFont('Helvetica', 10)
    canvas.setFillColor(colors.HexColor('#06402B')) # Color for header text
    canvas.setStrokeColor(colors.HexColor('#e3dede'))
    canvas.setLineWidth(0.5)

    # Define a consistent Y position for the header from the top of the page
    header_y_position = page_height - 0.7 * inch
    text_y_position = header_y_position + 0.1 * inch

    # 1. Horizontal Line
    canvas.line(doc.leftMargin, header_y_position, page_width - doc.rightMargin, header_y_position)

    # 2. Left and Right Text
    canvas.drawString(doc.leftMargin, text_y_position, "ANALYSIS HUB")
    canvas.drawRightString(page_width - doc.rightMargin, text_y_position, f"Date: {time.strftime('%d/%m/%Y')}")

    # 3. Symmetrical Vertical Separators
    side_column_width = 2.2 * inch
    separator_1_x = doc.leftMargin + side_column_width
    separator_2_x = page_width - doc.rightMargin - side_column_width
    separator_y_top = header_y_position + 0.3 * inch

    canvas.line(separator_1_x, header_y_position, separator_1_x, separator_y_top)
    canvas.line(separator_2_x, header_y_position, separator_2_x, separator_y_top)

    # 4. Center Logo
    if logo_path and os.path.exists(logo_path):
        logo_width, logo_height = 0.4 * inch, 0.4 * inch
        logo_x = page_width / 2 - (logo_width / 2)
        logo_y = text_y_position - 0.05 * inch
        canvas.drawImage(logo_path, logo_x, logo_y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')

    canvas.restoreState()
    
def draw_footer(canvas, doc):
    """Draws the custom footer on each page."""
    canvas.saveState()
    page_width = doc.width + doc.leftMargin * 2
    canvas.setFont('Helvetica', 10)
    canvas.setFillColor(colors.HexColor('#06402B'))
    line_y = 0.75 * inch
    canvas.setStrokeColor(colors.HexColor('#e3dede'))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, line_y, page_width - doc.rightMargin, line_y)
    canvas.drawString(doc.leftMargin, line_y - 0.2 * inch, "ANALYSIS HUB")
    canvas.drawRightString(page_width - doc.rightMargin, line_y - 0.2 * inch, f"Page: {doc.page}")
    canvas.restoreState()

# --- PDF Generation Functions ---
# In app.py, replace the existing create_detailed_player_report_pdf function

def create_detailed_player_report_pdf(player_obj, logo_path=None):
    """Creates the full PDF with final alignment and styling applied to all sections."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=1.0*inch, bottomMargin=0.75*inch)
    elements = []

    # --- Reusable Style for all 2-column tables ---
    notes_table_style = TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 1), (0, -1), 'MIDDLE'), # Middle-aligns the first column (labels)
        ('VALIGN', (1, 1), (1, -1), 'TOP'),    # Top-aligns the second column (notes)
        ('SPAN', (0, 0), (-1, 0)),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (0, 0), 16),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#212121')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 16),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#FFFFFF')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
        ('GRID', (0, 1), (-1, -1), 0.25, colors.HexColor('#A3CA9B')),
        ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#4F4F4F')),
    ])

    # --- Style for the 4-column Vitals table ---
    vitals_table_style = TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#4F4F4F')),
        ('SPAN', (0, 0), (-1, 0)),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (0, 0), 16),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#212121')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 16),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#4CAF50')), 
        ('BACKGROUND', (2, 1), (2, -1), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#FFFFFF')), 
        ('TEXTCOLOR', (2, 1), (2, -1), colors.HexColor('#FFFFFF')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
        ('FONTNAME', (2, 1), (2, -1), 'Helvetica'),
        ('GRID', (0, 1), (-1, -1), 0.25, colors.HexColor('#A3CA9B')),
    ])

    elements.append(Paragraph("Player Performance Report", _styles['MyCenteredTitle']))
    elements.append(Spacer(1, 0.3 * inch))

    # --- Section 1: Player Profile ---
    vitals_data = [
        ["Player Profile"],
        ['Player Name:', player_obj.player_name or '', 'Jersey Number:', player_obj.jersey_number or ''],
        ["Coach's Name:", player_obj.coach_name or '', 'Current Team:', player_obj.player_team or ''],
        ['Position:', player_obj.position or '', 'Other Positions:', player_obj.primary_positions or ''],
        ['Sub Team:', player_obj.sub_team or '', 'Date of Birth:', format_date_dmy(player_obj.dob)],
        ['Height (cm):', f"{player_obj.height or ''}", 'Weight (kg):', f"{player_obj.weight or ''}"],
        ['Preferred Foot:', player_obj.preferred_foot or '', 'Reporting Period:', f"{format_date_dmy(player_obj.report_period_start)} - {format_date_dmy(player_obj.report_period_end)}"]
    ]

    vitals_table = Table(vitals_data, colWidths=[doc.width*0.16, doc.width*0.34, doc.width*0.16, doc.width*0.34], splitByRow=1)
    vitals_table.setStyle(vitals_table_style)
    elements.append(vitals_table)
    elements.append(Spacer(1, 0.2 * inch))
    
    # --- Section 2: Performance Overview (Objective Metrics) ---
    snapshot_data = [
        ["Performance Overview (Objective Metrics)"],
        ['Matches Played:', player_obj.matches_played or ''],
        ['Total Minutes:', player_obj.total_minutes_played or ''],
        ['Goals:', player_obj.goals or ''],
        ['Assists:', player_obj.assists or '']
    ]
    snapshot_table = Table(snapshot_data, colWidths=[doc.width*0.3, doc.width*0.7], splitByRow=1)
    snapshot_table.setStyle(notes_table_style)
    elements.append(snapshot_table)
    elements.append(Spacer(1, 0.2 * inch))

    # --- Section 3: Player Assessment (4-Corner Model) ---
    assessment_data = [
        ["Player Assessment (4-Corner Model)"],
        ['Technical / Tactical:', Paragraph(str(player_obj.technical_tactical_notes or ''), _styles['CombinedBodyText'])],
        ['Physical Attributes:',  Paragraph(str(player_obj.physical_notes or ''), _styles['CombinedBodyText'])],
        ['Psychological:',        Paragraph(str(player_obj.psychological_notes or ''), _styles['CombinedBodyText'])],
        ['Social:',  Paragraph(str(player_obj.social_notes or ''), _styles['CombinedBodyText'])]
    ]
    assessment_table = Table(assessment_data, colWidths=[doc.width*0.3, doc.width*0.7], splitByRow=1)
    assessment_table.setStyle(notes_table_style)
    elements.append(assessment_table)
    elements.append(Spacer(1, 0.2 * inch))

    # --- Section 4: Development & Action Plan ---
    development_data = [
        ["Development & Action Plan"],
        ['Performance Summary:',   Paragraph(str(player_obj.overall_performance_summary or ''), _styles['CombinedBodyText'])],
        ['Key Strengths:',         Paragraph(str(player_obj.key_strengths_exhibited or ''), _styles['CombinedBodyText'])],
        ['Areas for Improvement:', Paragraph(str(player_obj.primary_areas_development or ''), _styles['CombinedBodyText'])],
        ['Recommended Plan:', Paragraph(str(player_obj.recommended_action_plan or ''), _styles['CombinedBodyText'])]
    ]
    development_table = Table(development_data, colWidths=[doc.width*0.3, doc.width*0.7], splitByRow=1)
    development_table.setStyle(notes_table_style)
    elements.append(development_table)

    doc.build(elements, onFirstPage=lambda c, d: (draw_header(c, d, logo_path), draw_footer(c, d)), onLaterPages=lambda c, d: (draw_header(c, d, logo_path), draw_footer(c, d)))
    buffer.seek(0)
    return buffer

def create_match_report_pdf(match_obj, club_name, logo_path=None):
    """Creates the PDF for a match report with all final visual and alignment adjustments."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=1.0*inch, bottomMargin=0.75*inch)
    elements = []

    # --- Reusable Style for all 2-column tables in this report ---
    notes_table_style = TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 1), (0, -1), 'MIDDLE'), # Middle-aligns the first column (labels)
        ('VALIGN', (1, 1), (1, -1), 'TOP'),    # Top-aligns the second column (notes)
        ('SPAN', (0, 0), (-1, 0)),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (0, 0), 16),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#212121')),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 16),
        ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#FFFFFF')),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica'),
        ('GRID', (0, 1), (-1, -1), 0.25, colors.HexColor('#A3CA9B')),
        ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#4F4F4F')),
    ])

    elements.append(Paragraph("Match Performance Report", _styles['MyCenteredTitle']))
    elements.append(Spacer(1, 0.3 * inch))

    # --- Section 1: Match Vitals ---
    vitals_data = [
        ["Match Information"],
        ['Competition:', match_obj.competition or ''],
        ['Season:', match_obj.season or ''],
        ['Match Date:', format_date_dmy(match_obj.match_date)],
        ['Venue:', match_obj.venue or ''],
        ['Home Team:', match_obj.home_team or ''],
        ['Away Team:', match_obj.away_team or ''],
        ['Final Score:', f"{match_obj.final_score_home if match_obj.final_score_home is not None else 'N/A'} - {match_obj.final_score_away if match_obj.final_score_away is not None else 'N/A'}"]
    ]
    vitals_table = Table(vitals_data, colWidths=[doc.width*0.3, doc.width*0.7], splitByRow=1)
    vitals_table.setStyle(notes_table_style) # Reusing the notes style works well here
    elements.append(vitals_table)
    elements.append(Spacer(1, 0.2 * inch))

    # --- Section 2: Team & Player Setup ---
    setup_data = [
        ["Team & Player Setup"],
        ['Home Team Formation:', Paragraph(str(match_obj.home_formation_initial or ''), _styles['CombinedBodyText'])],
        ['Home Team Lineup Notes:', Paragraph(str(match_obj.home_lineup_notes or ''), _styles['CombinedBodyText'])],
        ['Away Team Formation:', Paragraph(str(match_obj.away_formation_initial or ''), _styles['CombinedBodyText'])],
        ['Away Team Lineup Notes:', Paragraph(str(match_obj.away_lineup_notes or ''), _styles['CombinedBodyText'])],
    ]
    setup_table = Table(setup_data, colWidths=[doc.width*0.3, doc.width*0.7], splitByRow=1)
    setup_table.setStyle(notes_table_style)
    elements.append(setup_table)
    elements.append(Spacer(1, 0.2 * inch))

    # --- Section 3: Tactical Analysis ---
    tactics_data = [
        ["Tactical Analysis"],
        ['Home Team - Attacking Phase:', Paragraph(str(match_obj.home_attacking_phase or ''), _styles['CombinedBodyText'])],
        ['Home Team - Defensive Phase:', Paragraph(str(match_obj.home_defensive_phase or ''), _styles['CombinedBodyText'])],
        ['Home Team - Transitional Play:', Paragraph(str(match_obj.home_key_transitions or ''), _styles['CombinedBodyText'])],
        ['Away Team - Attacking Phase:', Paragraph(str(match_obj.away_attacking_phase or ''), _styles['CombinedBodyText'])],
        ['Away Team - Defensive Phase:', Paragraph(str(match_obj.away_defensive_phase or ''), _styles['CombinedBodyText'])],
        ['Away Team - Transitional Play:', Paragraph(str(match_obj.away_key_transitions or ''), _styles['CombinedBodyText'])],
    ]
    tactics_table = Table(tactics_data, colWidths=[doc.width*0.3, doc.width*0.7], splitByRow=1)
    tactics_table.setStyle(notes_table_style)
    elements.append(tactics_table)
    elements.append(Spacer(1, 0.2 * inch))

    # --- Section 4: Conclusive Summary ---
    summary_data = [
        ["Match Summary & Insights"],
        ['Overall Match Summary:', Paragraph(str(match_obj.overall_match_summary or ''), _styles['CombinedBodyText'])],
        ['Key Turning Point(s):', Paragraph(str(match_obj.key_turning_points or ''), _styles['CombinedBodyText'])],
        ['Man of the Match:', Paragraph(str(match_obj.man_of_the_match or ''), _styles['CombinedBodyText'])],
        ['Final Notes:', Paragraph(str(match_obj.final_analyst_notes or ''), _styles['CombinedBodyText'])],
    ]
    summary_table = Table(summary_data, colWidths=[doc.width*0.3, doc.width*0.7], splitByRow=1)
    summary_table.setStyle(notes_table_style)
    elements.append(summary_table)

    doc.build(elements, onFirstPage=lambda c, d: (draw_header(c, d, logo_path), draw_footer(c, d)), onLaterPages=lambda c, d: (draw_header(c, d, logo_path), draw_footer(c, d)))
    buffer.seek(0)
    return buffer

# --- Flask Routes ---

@app.route('/')
@login_required
def select_report_type():
    return render_template('select_report_type.html')


@app.route('/create_player_report_form', methods=['GET'])
@login_required
def create_player_report_form():
    report_type_choice = request.args.get('report_type_choice')
    
    if report_type_choice not in ['default_detailed_player_report', 'default_summary_player_report']:
        flash('Invalid player report type selected.', 'danger')
        return redirect(url_for('select_report_type'))
        
    return render_template('input_form.html', player=None, form_data=None, report_type_choice=report_type_choice)


@app.route('/generate_player_report', methods=['POST'])
@login_required
def generate_player_report():
    form_data = request.form
    report_type_choice = form_data.get('report_type_choice', 'default_detailed_player_report')

    # --- Server-Side Validation ---
    errors = []
    if not form_data.get('player_name'):
        errors.append('Player Name is required.')
    
    # Process and validate numeric fields
    player_data_dict = {}
    numeric_fields = {
        'jersey_number': int, 'matches_played': int, 'total_minutes_played': int, 
        'goals': int, 'assists': int, 'height': float, 'weight': float
    }
    for field, type_converter in numeric_fields.items():
        value = form_data.get(field)
        if value:
            try:
                converted_value = type_converter(value)
                if converted_value < 0:
                    errors.append(f'{field.replace("_", " ").title()} must be a non-negative number.')
                else:
                    player_data_dict[field] = converted_value
            except (ValueError, TypeError):
                errors.append(f'{field.replace("_", " ").title()} must be a valid number.')
                player_data_dict[field] = None
        else:
            player_data_dict[field] = None

    if errors:
        for error in errors:
            flash(error, 'danger')
        return render_template('input_form.html', player=None, report_type_choice=report_type_choice, form_data=form_data)
    # --- End Validation ---

    logo_path = None
    if 'club_logo' in request.files:
        file = request.files['club_logo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(f"{current_user.id}_{file.filename}")
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(logo_path)
    
    # **FIX**: Use time.time() to generate a unique timestamp for the filename
    unique_timestamp = int(time.time())
    player_name = form_data.get('player_name', 'Unnamed_Player').replace(' ', '_')
    pdf_filename = f"Player_Report_{player_name}_{unique_timestamp}.pdf"
    
    # Create Player object
    new_player = Player(
        club_id=current_user.club.id,
        player_name=form_data.get('player_name'),
        coach_name=form_data.get('coach_name'),
        sub_team=form_data.get('sub_team'),
        player_team=current_user.club.name,
        primary_positions=form_data.get('primary_positions'),
        report_period_start=form_data.get('report_period_start'),
        report_period_end=form_data.get('report_period_end'),
        matches_covered=form_data.get('matches_covered'),
        technical_tactical_notes=form_data.get('technical_tactical_notes'),
        physical_notes=form_data.get('physical_notes'),
        psychological_notes=form_data.get('psychological_notes'),
        social_notes=form_data.get('social_notes'),
        overall_performance_summary=form_data.get('overall_performance_summary'),
        key_strengths_exhibited=form_data.get('key_strengths_exhibited'),
        primary_areas_development=form_data.get('primary_areas_development'),
        recommended_action_plan=form_data.get('recommended_action_plan'),
        position=form_data.get('position'),
        dob=form_data.get('dob'),
        preferred_foot=form_data.get('preferred_foot'),
        pdf_report_path=pdf_filename,
        **player_data_dict # Add validated numeric fields
    )

    # Generate and save PDF
    if report_type_choice == 'default_summary_player_report':
        pdf_buffer = create_summary_player_report_pdf(new_player, logo_path) 
    else:
        pdf_buffer = create_detailed_player_report_pdf(new_player, logo_path)
    
    full_pdf_path = os.path.join(app.config['REPORT_FOLDER'], pdf_filename)
    with open(full_pdf_path, 'wb') as f:
        f.write(pdf_buffer.getbuffer())

    # Commit to DB and cleanup
    db.session.add(new_player)
    db.session.commit()

    if logo_path and os.path.exists(logo_path):
        os.remove(logo_path)
    
    flash('Player report generated and saved successfully!', 'success')
    return redirect(url_for('list_players'))


@app.route('/players')
@login_required
def list_players():
    players = Player.query.filter_by(club_id=current_user.club.id).order_by(Player.player_name).all()
    return render_template('player_list.html', players=players)

@app.route('/download_report/<path:filename>')
@login_required
def download_report(filename):
    secure_name = secure_filename(filename)
    
    player_report = Player.query.filter_by(pdf_report_path=secure_name, club_id=current_user.club.id).first()
    match_report = Match.query.filter_by(pdf_report_path=secure_name, club_id=current_user.club.id).first()

    if not (player_report or match_report):
        abort(404)

    report_file_path = os.path.join(app.config['REPORT_FOLDER'], secure_name)
    if os.path.exists(report_file_path):
        return send_file(report_file_path, as_attachment=True)
    else:
        abort(404)


@app.route('/edit_player/<int:player_id>', methods=['GET', 'POST'])
@login_required
def edit_player(player_id):
    player = db.session.query(Player).filter_by(id=player_id, club_id=current_user.club.id).first_or_404()

    if request.method == 'POST':
        form_data = request.form
        report_type_choice = form_data.get('report_type_choice', 'default_detailed_player_report')

        # --- Server-Side Validation ---
        errors = []
        if not form_data.get('player_name'):
            errors.append('Player Name is required.')
        
        # Process and validate numeric fields
        numeric_fields = {
            'jersey_number': int, 'matches_played': int, 'total_minutes_played': int, 
            'goals': int, 'assists': int, 'height': float, 'weight': float
        }
        for field, type_converter in numeric_fields.items():
            value = form_data.get(field)
            if value:
                try:
                    converted_value = type_converter(value)
                    if converted_value < 0:
                        errors.append(f'{field.replace("_", " ").title()} must be a non-negative number.')
                    else:
                        setattr(player, field, converted_value)
                except (ValueError, TypeError):
                    errors.append(f'{field.replace("_", " ").title()} must be a valid number.')
                    setattr(player, field, None)
            else:
                setattr(player, field, None)

        if errors:
            for error in errors:
                flash(error, 'danger')
            # Pass form_data to repopulate the form with invalid data for correction
            return render_template('input_form.html', player=player, report_type_choice=report_type_choice, form_data=form_data)
        # --- End Validation ---

        # Update text-based fields
        player.player_name = form_data.get('player_name')
        player.position = form_data.get('position')
        player.dob = form_data.get('dob')
        player.preferred_foot = form_data.get('preferred_foot')
        player.sub_team = form_data.get('sub_team')
        player.primary_positions = form_data.get('primary_positions')
        player.report_period_start = form_data.get('report_period_start')
        player.report_period_end = form_data.get('report_period_end')
        player.matches_covered = form_data.get('matches_covered')
        player.technical_tactical_notes = form_data.get('technical_tactical_notes')
        player.physical_notes = form_data.get('physical_notes')
        player.psychological_notes = form_data.get('psychological_notes')
        player.social_notes = form_data.get('social_notes')
        player.overall_performance_summary = form_data.get('overall_performance_summary')
        player.key_strengths_exhibited = form_data.get('key_strengths_exhibited')
        player.primary_areas_development = form_data.get('primary_areas_development')
        player.recommended_action_plan = form_data.get('recommended_action_plan')

        logo_path = None
        if 'club_logo' in request.files:
            file = request.files['club_logo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{current_user.id}_{file.filename}")
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(logo_path)
        
        # Regenerate PDF
        if report_type_choice == 'default_summary_player_report':
            pdf_buffer = create_summary_player_report_pdf(player, logo_path)
        else:
            pdf_buffer = create_detailed_player_report_pdf(player, logo_path)
        
        full_pdf_path = os.path.join(app.config['REPORT_FOLDER'], player.pdf_report_path)
        with open(full_pdf_path, 'wb') as f:
            f.write(pdf_buffer.getbuffer())

        db.session.commit()

        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)

        flash('Player report updated successfully!', 'success')
        return redirect(url_for('list_players'))
    
    return render_template('input_form.html', player=player, form_data=None, report_type_choice=request.args.get('report_type_choice', 'default_detailed_player_report'))

@app.route('/delete_player/<int:player_id>', methods=['POST'])
@login_required
def delete_player(player_id):
    player = db.session.query(Player).filter_by(id=player_id, club_id=current_user.club.id).first_or_404()

    pdf_file_path = os.path.join(app.config['REPORT_FOLDER'], player.pdf_report_path)
    if os.path.exists(pdf_file_path):
        try:
            os.remove(pdf_file_path)
        except OSError as e:
            flash(f'Error deleting PDF report file: {e}', 'danger')

    db.session.delete(player)
    db.session.commit()

    flash(f'Player "{player.player_name}" and their report have been deleted.', 'success')
    return redirect(url_for('list_players'))


# --- Match Report Routes ---

@app.route('/create_match_report_form', methods=['GET'])
@login_required
def create_match_report_form():
    report_type_choice = request.args.get('report_type_choice')
    
    if report_type_choice != 'default_match_report':
        flash('Invalid match report type selected.', 'danger')
        return redirect(url_for('select_report_type'))

    return render_template('match_input_form.html', match=None, form_data=None, report_type_choice=report_type_choice)


@app.route('/generate_match_report', methods=['POST'])
@login_required
def generate_match_report():
    form_data = request.form
    report_type_choice = form_data.get('report_type_choice')

    # --- Server-Side Validation ---
    errors = []
    if not form_data.get('match_date'): errors.append('Match Date is required.')
    if not form_data.get('home_team'): errors.append('Home Team Name is required.')
    if not form_data.get('away_team'): errors.append('Away Team Name is required.')

    # Process and validate numeric fields
    match_data_dict = {}
    numeric_fields_match = ['final_score_home', 'final_score_away']
    for field in numeric_fields_match:
        value = form_data.get(field)
        if value:
            try:
                converted_value = int(value)
                if converted_value < 0:
                    errors.append(f'{field.replace("_", " ").title()} must be a non-negative number.')
                else:
                    match_data_dict[field] = converted_value
            except (ValueError, TypeError):
                errors.append(f'{field.replace("_", " ").title()} must be a valid number.')
                match_data_dict[field] = None
        else:
            match_data_dict[field] = None
    
    if errors:
        for error in errors:
            flash(error, 'danger')
        return render_template('match_input_form.html', match=None, report_type_choice=report_type_choice, form_data=form_data)
    # --- End Validation ---

    logo_path = None
    if 'club_logo' in request.files:
        file = request.files['club_logo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(f"{current_user.id}_{file.filename}")
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(logo_path)

    # **FIX**: Use time.time() to generate a unique timestamp for the filename
    unique_timestamp = int(time.time())
    home_team_name = form_data.get('home_team', 'Home').replace(' ', '_')
    away_team_name = form_data.get('away_team', 'Away').replace(' ', '_')
    pdf_filename = f"Match_Report_{home_team_name}_vs_{away_team_name}_{unique_timestamp}.pdf"

    # Create Match object
    new_match = Match(
        club_id=current_user.club.id,
        competition=form_data.get('competition'),
        season=form_data.get('season'),
        match_date=form_data.get('match_date'),
        venue=form_data.get('venue'),
        weather_pitch_conditions=form_data.get('weather_pitch_conditions'),
        home_team=form_data.get('home_team'),
        away_team=form_data.get('away_team'),
        home_formation_initial=form_data.get('home_formation_initial'),
        away_formation_initial=form_data.get('away_formation_initial'),
        home_lineup_notes=form_data.get('home_lineup_notes'),
        away_lineup_notes=form_data.get('away_lineup_notes'),
        home_attacking_phase=form_data.get('home_attacking_phase'),
        home_defensive_phase=form_data.get('home_defensive_phase'),
        home_key_transitions=form_data.get('home_key_transitions'),
        away_attacking_phase=form_data.get('away_attacking_phase'),
        away_defensive_phase=form_data.get('away_defensive_phase'),
        away_key_transitions=form_data.get('away_key_transitions'),
        overall_match_summary=form_data.get('overall_match_summary'),
        key_turning_points=form_data.get('key_turning_points'),
        man_of_the_match=form_data.get('man_of_the_match'),
        final_analyst_notes=form_data.get('final_analyst_notes'),
        pdf_report_path=pdf_filename,
        **match_data_dict # Add validated numeric fields
    )
    
    # Generate and save PDF
    club_name = current_user.club.name
    pdf_buffer = create_match_report_pdf(new_match, club_name, logo_path)
    full_pdf_path = os.path.join(app.config['REPORT_FOLDER'], pdf_filename)
    with open(full_pdf_path, 'wb') as f:
        f.write(pdf_buffer.getbuffer())

    # Commit to DB and cleanup
    db.session.add(new_match)
    db.session.commit()

    if logo_path and os.path.exists(logo_path):
        os.remove(logo_path)
    
    flash('Match report generated and saved successfully!', 'success')
    return redirect(url_for('list_matches'))

@app.route('/matches')
@login_required
def list_matches():
    matches = Match.query.filter_by(club_id=current_user.club.id).order_by(Match.match_date.desc()).all()
    return render_template('match_list.html', matches=matches)

@app.route('/edit_match/<int:match_id>', methods=['GET', 'POST'])
@login_required
def edit_match(match_id):
    match = db.session.query(Match).filter_by(id=match_id, club_id=current_user.club.id).first_or_404()

    if request.method == 'POST':
        form_data = request.form
        report_type_choice = form_data.get('report_type_choice')
        
        # --- Server-Side Validation ---
        errors = []
        if not form_data.get('match_date'): errors.append('Match Date is required.')
        if not form_data.get('home_team'): errors.append('Home Team Name is required.')
        if not form_data.get('away_team'): errors.append('Away Team Name is required.')

        numeric_fields_match = ['final_score_home', 'final_score_away']
        for field in numeric_fields_match:
            value = form_data.get(field)
            if value:
                try:
                    converted_value = int(value)
                    if converted_value < 0:
                        errors.append(f'{field.replace("_", " ").title()} must be a non-negative number.')
                    else:
                        setattr(match, field, converted_value)
                except (ValueError, TypeError):
                    errors.append(f'{field.replace("_", " ").title()} must be a valid number.')
                    setattr(match, field, None)
            else:
                 setattr(match, field, None)

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('match_input_form.html', match=match, report_type_choice=report_type_choice, form_data=form_data)
        # --- End Validation ---

        # Update text-based fields
        match.competition = form_data.get('competition')
        match.season = form_data.get('season')
        match.match_date = form_data.get('match_date')
        match.venue = form_data.get('venue')
        match.weather_pitch_conditions = form_data.get('weather_pitch_conditions')
        match.home_team = form_data.get('home_team')
        match.away_team = form_data.get('away_team')
        match.home_formation_initial = form_data.get('home_formation_initial')
        match.away_formation_initial = form_data.get('away_formation_initial')
        match.home_lineup_notes = form_data.get('home_lineup_notes')
        match.away_lineup_notes = form_data.get('away_lineup_notes')
        match.home_attacking_phase = form_data.get('home_attacking_phase')
        match.home_defensive_phase = form_data.get('home_defensive_phase')
        match.home_key_transitions = form_data.get('home_key_transitions')
        match.away_attacking_phase = form_data.get('away_attacking_phase')
        match.away_defensive_phase = form_data.get('away_defensive_phase')
        match.away_key_transitions = form_data.get('away_key_transitions')
        match.overall_match_summary = form_data.get('overall_match_summary')
        match.key_turning_points = form_data.get('key_turning_points')
        match.man_of_the_match = form_data.get('man_of_the_match')
        match.final_analyst_notes = form_data.get('final_analyst_notes')

        logo_path = None
        if 'club_logo' in request.files:
            file = request.files['club_logo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"{current_user.id}_{file.filename}")
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(logo_path)
        
        # Regenerate PDF
        pdf_buffer = create_match_report_pdf(match, logo_path) 
        full_pdf_path = os.path.join(app.config['REPORT_FOLDER'], match.pdf_report_path)
        with open(full_pdf_path, 'wb') as f:
            f.write(pdf_buffer.getbuffer())
        
        db.session.commit()

        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)

        flash('Match report updated successfully!', 'success')
        return redirect(url_for('list_matches'))
    
    return render_template('match_input_form.html', match=match, form_data=None, report_type_choice=request.args.get('report_type_choice'))

@app.route('/delete_match/<int:match_id>', methods=['POST'])
@login_required
def delete_match(match_id):
    match = db.session.query(Match).filter_by(id=match_id, club_id=current_user.club.id).first_or_404()

    pdf_file_path = os.path.join(app.config['REPORT_FOLDER'], match.pdf_report_path)
    if os.path.exists(pdf_file_path):
        try:
            os.remove(pdf_file_path)
        except OSError as e:
            flash(f'Error deleting PDF report file: {e}', 'danger')

    flash_message = f'Match report for "{match.home_team} vs {match.away_team}" on {match.match_date} has been deleted.'
    db.session.delete(match)
    db.session.commit()

    flash(flash_message, 'success')
    return redirect(url_for('list_matches'))


# --- User Authentication Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('select_report_type'))

    form_data = request.form
    if request.method == 'POST':
        club_name = form_data.get('club_name')
        username = form_data.get('username')
        password = form_data.get('password')

        errors = []
        if not club_name: errors.append('Club Name is required.')
        if not username: errors.append('Username is required.')
        if not password: 
            errors.append('Password is required.')
        elif len(password) < 6:
            errors.append('Password must be at least 6 characters long.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('register.html', form_data=form_data)

        club = Club.query.filter(func.lower(Club.name) == func.lower(club_name)).first()
        if not club:
            club = Club(name=club_name)
            db.session.add(club)
            # Must commit here to get club.id for the user
            db.session.commit()

        existing_user = User.query.filter(func.lower(User.username) == func.lower(username)).first()
        if existing_user:
            flash(f'Username "{username}" already exists. Please choose a different one.', 'danger')
            return render_template('register.html', form_data=form_data)

        new_user = User(username=username, club_id=club.id)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash(f'Account created for {username} at {club_name}! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form_data=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('select_report_type'))

    form_data = request.form
    if request.method == 'POST':
        username = form_data.get('username')
        password = form_data.get('password')
        
        if not username or not password:
            flash('Both username and password are required.', 'danger')
            return render_template('login.html', form_data=form_data)

        user = User.query.filter(func.lower(User.username) == func.lower(username)).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('select_report_type'))
        else:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html', form_data=form_data)

    return render_template('login.html', form_data=None)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    # Ensure necessary folders exist
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(REPORT_FOLDER):
        os.makedirs(REPORT_FOLDER)
    
    with app.app_context():
        db.create_all()
    
    app.run(debug=True)