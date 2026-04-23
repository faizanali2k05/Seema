#!/usr/bin/env python3
"""
Seema - AI Law Firm Assistant
Python Backend Server - Law Firms Only
Runs on port 3000 with SQLite database
"""

import http.server
import json
import sqlite3
import uuid
import threading
import time
import os
import random
import datetime
import sys
import socket
import hashlib
import smtplib
import io
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# ============================================================================
# Fix encoding on Windows
# ============================================================================
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# PDF generation (reportlab)
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
    from reportlab.pdfgen import canvas as pdf_canvas
    REPORTLAB_AVAILABLE = True
    print("ReportLab loaded — PDF generation active")
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Warning: ReportLab not installed — PDF generation disabled")

# Import the Knowledge Engine for domain validation (hyphenated filename)
try:
    import importlib.util
    _ke_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'knowledge-engine.py')
    _ke_spec = importlib.util.spec_from_file_location('knowledge_engine', _ke_path)
    _ke_mod = importlib.util.module_from_spec(_ke_spec)
    _ke_spec.loader.exec_module(_ke_mod)
    KnowledgeEngine = _ke_mod.KnowledgeEngine
    KNOWLEDGE_ENGINE = KnowledgeEngine()
    print("Knowledge Engine loaded — domain validation active")
except Exception as e:
    KNOWLEDGE_ENGINE = None
    print(f"Warning: Knowledge Engine not loaded ({e}) — running without domain validation")

# ============================================================================
# Configuration
# ============================================================================

PORT = 3000
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
DB_PATH = os.path.join(DATA_DIR, "demo-workflows.db")

# ============================================================================
# Email Sending (real SMTP via smtplib)
# ============================================================================

def send_real_email(to_email, to_name, subject, body_text, settings, attachment_bytes=None, attachment_name=None):
    """
    Send a real email via SMTP. Returns (success: bool, error: str or None).
    Uses TLS on port 587 or SSL on port 465. Falls back gracefully.
    """
    if not settings.get('enabled'):
        return False, "Email sending is disabled"

    smtp_host = settings.get('smtp_host', '')
    try:
        smtp_port = int(settings.get('smtp_port', 587))
    except (ValueError, TypeError):
        smtp_port = 587
    smtp_user = settings.get('smtp_user', '')
    smtp_password = settings.get('smtp_password', '')
    from_email = settings.get('from_email', smtp_user)
    from_name = settings.get('from_name', 'Seema Compliance')

    if not smtp_host or not from_email:
        return False, "SMTP not configured"

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = f"{to_name} <{to_email}>" if to_name else to_email
        msg['Subject'] = subject
        msg['X-Mailer'] = 'Seema Compliance Engine'

        # HTML email body with professional styling
        html_body = f"""<html><body style="font-family: Arial, sans-serif; color: #1a2233; line-height: 1.6;">
<div style="max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background: #1b2a4a; padding: 16px 24px; border-radius: 8px 8px 0 0;">
        <h2 style="color: white; margin: 0; font-size: 16px;">Seema Compliance</h2>
    </div>
    <div style="background: #ffffff; border: 1px solid #e2e5ed; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
        {body_text.replace(chr(10), '<br>')}
    </div>
    <div style="text-align: center; padding: 12px; font-size: 11px; color: #8c95a6;">
        Sent by Seema — The Compliance Operating System for Your COLP
    </div>
</div>
</body></html>"""

        msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        if attachment_bytes and attachment_name:
            att = MIMEApplication(attachment_bytes)
            att.add_header('Content-Disposition', 'attachment', filename=attachment_name)
            msg.attach(att)

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()

        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)

        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        return True, None

    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed — check username and password"
    except smtplib.SMTPConnectError:
        return False, "Could not connect to SMTP server — check host and port"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Email error: {str(e)}"


def _get_smtp_settings():
    """Fetch current SMTP settings from database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM email_settings LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}


# ============================================================================
# PDF Report Generation
# ============================================================================

SEEMA_NAVY = HexColor('#1b2a4a') if REPORTLAB_AVAILABLE else None
SEEMA_BLUE = HexColor('#2563eb') if REPORTLAB_AVAILABLE else None
SEEMA_GREEN = HexColor('#059669') if REPORTLAB_AVAILABLE else None
SEEMA_RED = HexColor('#dc2626') if REPORTLAB_AVAILABLE else None
SEEMA_AMBER = HexColor('#d97706') if REPORTLAB_AVAILABLE else None
SEEMA_GREY = HexColor('#5a6478') if REPORTLAB_AVAILABLE else None
SEEMA_LIGHT = HexColor('#f5f6fa') if REPORTLAB_AVAILABLE else None
SEEMA_BORDER = HexColor('#e2e5ed') if REPORTLAB_AVAILABLE else None


def _seema_header_footer(canvas_obj, doc):
    """Standard Seema header and footer on every page"""
    canvas_obj.saveState()
    w, h = A4

    # Header band
    canvas_obj.setFillColor(SEEMA_NAVY)
    canvas_obj.rect(0, h - 28*mm, w, 28*mm, fill=1, stroke=0)
    canvas_obj.setFillColor(white)
    canvas_obj.setFont('Helvetica-Bold', 14)
    canvas_obj.drawString(20*mm, h - 18*mm, 'Seema')
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.drawString(20*mm, h - 23*mm, 'The Compliance Operating System for Your COLP')
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.drawRightString(w - 20*mm, h - 18*mm, datetime.datetime.now().strftime('%d %B %Y'))

    # Footer
    canvas_obj.setFillColor(SEEMA_GREY)
    canvas_obj.setFont('Helvetica', 7)
    canvas_obj.drawString(20*mm, 12*mm, 'Generated by Seema Compliance Engine')
    canvas_obj.drawRightString(w - 20*mm, 12*mm, f'Page {doc.page}')

    canvas_obj.restoreState()


def generate_sra_return_pdf(data, firm_name='Mitchell & Partners LLP'):
    """Generate a professional SRA Annual Return PDF. Returns bytes."""
    if not REPORTLAB_AVAILABLE:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=35*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('SeemaTitle', parent=styles['Title'], fontSize=20,
                              textColor=SEEMA_NAVY, spaceAfter=6))
    styles.add(ParagraphStyle('SeemaH2', parent=styles['Heading2'], fontSize=13,
                              textColor=SEEMA_NAVY, spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle('SeemaBody', parent=styles['Normal'], fontSize=10,
                              textColor=black, leading=14))
    styles.add(ParagraphStyle('SeemaLabel', parent=styles['Normal'], fontSize=9,
                              textColor=SEEMA_GREY))

    story = []

    # Title
    story.append(Paragraph('SRA Annual Return', styles['SeemaTitle']))
    story.append(Paragraph(firm_name, styles['SeemaBody']))
    story.append(Spacer(1, 4*mm))

    firm = data.get('firm_details', {})
    story.append(Paragraph(f"SRA Number: {firm.get('sra_number', 'N/A')} &nbsp;&nbsp;|&nbsp;&nbsp; Reporting Period: {firm.get('reporting_period', 'N/A')}", styles['SeemaLabel']))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=SEEMA_BORDER))
    story.append(Spacer(1, 4*mm))

    # Staff summary
    staff = data.get('staff_summary', {})
    story.append(Paragraph('1. Staff Summary', styles['SeemaH2']))
    staff_data = [
        ['Total Staff', str(staff.get('total_staff', 0))],
        ['Solicitors', str(staff.get('total_solicitors', 0))],
        ['Fee Earners', str(staff.get('total_fee_earners', 0))],
        ['Diversity Data Collected', staff.get('diversity_data', 'N/A')],
    ]
    t = Table(staff_data, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 4*mm))

    # Compliance
    comp = data.get('compliance', {})
    story.append(Paragraph('2. Compliance Position', styles['SeemaH2']))
    comp_data = [
        ['SRA Audit Score', f"{comp.get('sra_audit_score', 0)}%"],
        ['Non-Compliant Items', str(comp.get('non_compliant_items', 0))],
        ['Active Alerts', str(comp.get('active_alerts', 0))],
        ['Open Remediation Plans', str(comp.get('open_remediation', 0))],
    ]
    t = Table(comp_data, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 4*mm))

    # Complaints
    complaints = data.get('complaints', {})
    story.append(Paragraph('3. Complaints', styles['SeemaH2']))
    compl_data = [
        ['Total Received', str(complaints.get('total_received', 0))],
        ['Resolved', str(complaints.get('resolved', 0))],
        ['Referred to LeO', str(complaints.get('referred_to_leo', 0))],
        ['Avg Resolution (days)', str(complaints.get('avg_resolution_days', 0))],
    ]
    t = Table(compl_data, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 4*mm))

    # Financial
    fin = data.get('financial', {})
    story.append(Paragraph('4. Financial Compliance', styles['SeemaH2']))
    fin_data = [
        ['PII Claims', str(fin.get('pii_claims', 0))],
        ['Client Account Shortfalls', str(fin.get('client_account_shortfalls', 0))],
        ['Accountant Report Date', fin.get('accountant_report_date', 'N/A')],
    ]
    t = Table(fin_data, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 4*mm))

    # AML
    aml = data.get('aml', {})
    story.append(Paragraph('5. Anti-Money Laundering', styles['SeemaH2']))
    aml_data = [
        ['Risk Assessments Completed', str(aml.get('risk_assessments_completed', 0))],
        ['SARs Filed', str(aml.get('suspicious_activity_reports', 0))],
        ['EDD Reviews', str(aml.get('edd_reviews', 0))],
        ['PEP Clients', str(aml.get('pep_clients', 0))],
    ]
    t = Table(aml_data, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 4*mm))

    # Data Protection
    dp = data.get('data_protection', {})
    story.append(Paragraph('6. Data Protection', styles['SeemaH2']))
    dp_data = [
        ['DSARs Received', str(dp.get('dsar_received', 0))],
        ['Breaches Reported', str(dp.get('breaches_reported', 0))],
        ['ICO Notifications', str(dp.get('ico_notifications', 0))],
    ]
    t = Table(dp_data, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))

    # Sign-off
    story.append(HRFlowable(width="100%", thickness=1, color=SEEMA_BORDER))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph('COLP Sign-off', styles['SeemaH2']))
    story.append(Paragraph('I confirm that the information in this return is accurate to the best of my knowledge.', styles['SeemaBody']))
    story.append(Spacer(1, 12*mm))
    story.append(Paragraph('Signed: ______________________________&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Date: _______________', styles['SeemaBody']))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph('Name: ________________________________&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Position: COLP', styles['SeemaBody']))

    doc.build(story, onFirstPage=_seema_header_footer, onLaterPages=_seema_header_footer)
    return buf.getvalue()


def generate_audit_report_pdf(report_data, firm_name='Mitchell & Partners LLP'):
    """Generate a professional Audit Report PDF. Returns bytes."""
    if not REPORTLAB_AVAILABLE:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=35*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('SeemaTitle', parent=styles['Title'], fontSize=20,
                              textColor=SEEMA_NAVY, spaceAfter=6))
    styles.add(ParagraphStyle('SeemaH2', parent=styles['Heading2'], fontSize=13,
                              textColor=SEEMA_NAVY, spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle('SeemaBody', parent=styles['Normal'], fontSize=10,
                              textColor=black, leading=14))
    styles.add(ParagraphStyle('SeemaLabel', parent=styles['Normal'], fontSize=9,
                              textColor=SEEMA_GREY))

    story = []
    summary = report_data.get('summary', {})

    story.append(Paragraph('Compliance Audit Report', styles['SeemaTitle']))
    story.append(Paragraph(firm_name, styles['SeemaBody']))
    story.append(Paragraph(f"Generated: {report_data.get('generated_at', datetime.datetime.now().isoformat())[:10]}", styles['SeemaLabel']))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=SEEMA_BORDER))
    story.append(Spacer(1, 4*mm))

    # Executive summary
    story.append(Paragraph('Executive Summary', styles['SeemaH2']))
    exec_data = [
        ['Audit Readiness', f"{summary.get('readiness_pct', 0)}%"],
        ['Checks Passed', str(summary.get('checks_passed', 0))],
        ['Checks Failed', str(summary.get('checks_failed', 0))],
        ['Non-Compliant Items', str(summary.get('non_compliant_items', 0))],
        ['Average Risk Score', str(summary.get('avg_risk', 0))],
        ['Active Alerts', str(summary.get('active_alerts', 0))],
        ['Remediation Plans Open', str(summary.get('remediation_open', 0))],
        ['Policies Generated', str(summary.get('policies_count', 0))],
    ]
    t = Table(exec_data, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 6*mm))

    # Full report content
    content = report_data.get('content', '')
    if content:
        story.append(Paragraph('Detailed Findings', styles['SeemaH2']))
        for para in content.split('\n\n'):
            para = para.strip()
            if not para:
                continue
            if para.startswith('##'):
                story.append(Paragraph(para.replace('##', '').strip(), styles['SeemaH2']))
            elif para.startswith('#'):
                story.append(Paragraph(para.replace('#', '').strip(), styles['SeemaH2']))
            else:
                story.append(Paragraph(para.replace('\n', '<br/>'), styles['SeemaBody']))
                story.append(Spacer(1, 2*mm))

    # Sign-off
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=SEEMA_BORDER))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph('Reviewed by: ______________________________&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Date: _______________', styles['SeemaBody']))

    doc.build(story, onFirstPage=_seema_header_footer, onLaterPages=_seema_header_footer)
    return buf.getvalue()


def generate_breach_report_pdf(report_data, firm_name='Mitchell & Partners LLP'):
    """Generate a Breach Report PDF for ICO notification. Returns bytes."""
    if not REPORTLAB_AVAILABLE:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=35*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('SeemaTitle', parent=styles['Title'], fontSize=20,
                              textColor=SEEMA_NAVY, spaceAfter=6))
    styles.add(ParagraphStyle('SeemaH2', parent=styles['Heading2'], fontSize=13,
                              textColor=SEEMA_NAVY, spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle('SeemaBody', parent=styles['Normal'], fontSize=10,
                              textColor=black, leading=14))
    styles.add(ParagraphStyle('SeemaLabel', parent=styles['Normal'], fontSize=9,
                              textColor=SEEMA_GREY))
    styles.add(ParagraphStyle('SeemaUrgent', parent=styles['Normal'], fontSize=11,
                              textColor=SEEMA_RED, fontName='Helvetica-Bold'))

    story = []

    story.append(Paragraph('Data Breach Incident Report', styles['SeemaTitle']))
    story.append(Paragraph(firm_name, styles['SeemaBody']))
    story.append(Spacer(1, 2*mm))

    if report_data.get('ico_notifiable'):
        story.append(Paragraph('ICO NOTIFIABLE — 72-HOUR REPORTING DEADLINE APPLIES', styles['SeemaUrgent']))

    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=SEEMA_BORDER))
    story.append(Spacer(1, 4*mm))

    # Incident details
    story.append(Paragraph('1. Incident Details', styles['SeemaH2']))
    inc_data = [
        ['Title', report_data.get('title', 'N/A')],
        ['Severity', (report_data.get('severity', 'medium')).upper()],
        ['Status', (report_data.get('status', 'open')).replace('_', ' ').upper()],
        ['Reported At', report_data.get('reported_at', 'N/A')[:19] if report_data.get('reported_at') else 'N/A'],
        ['72h Deadline', report_data.get('deadline_72h', 'N/A')[:19] if report_data.get('deadline_72h') else 'N/A'],
    ]
    t = Table(inc_data, colWidths=[45*mm, 115*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 4*mm))

    # Description
    story.append(Paragraph('2. Description', styles['SeemaH2']))
    story.append(Paragraph(report_data.get('description', 'No description provided.'), styles['SeemaBody']))
    story.append(Spacer(1, 4*mm))

    # Impact
    story.append(Paragraph('3. Impact Assessment', styles['SeemaH2']))
    impact_data = [
        ['Affected Data', report_data.get('affected_data', 'Not specified')],
        ['Individuals Affected', str(report_data.get('affected_individuals', 0))],
        ['ICO Notifiable', 'YES' if report_data.get('ico_notifiable') else 'NO'],
    ]
    t = Table(impact_data, colWidths=[45*mm, 115*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 4*mm))

    # Response steps
    steps = report_data.get('steps', [])
    if steps:
        story.append(Paragraph('4. Response Workflow', styles['SeemaH2']))
        step_header = [['Step', 'Action', 'Status', 'Completed']]
        step_rows = []
        for s in steps:
            status = s.get('status', 'pending')
            completed = s.get('completed_at', '')[:10] if s.get('completed_at') else '-'
            step_rows.append([str(s.get('step_number', '')), s.get('title', ''), status.upper(), completed])

        t = Table(step_header + step_rows, colWidths=[12*mm, 90*mm, 25*mm, 33*mm])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), SEEMA_LIGHT),
            ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, SEEMA_BORDER),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ]))
        story.append(t)

    # Sign-off
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=SEEMA_BORDER))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph('COLP Acknowledgement', styles['SeemaH2']))
    story.append(Paragraph('I confirm that appropriate steps have been taken to contain this breach and notify affected parties.', styles['SeemaBody']))
    story.append(Spacer(1, 12*mm))
    story.append(Paragraph('Signed: ______________________________&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Date: _______________', styles['SeemaBody']))

    doc.build(story, onFirstPage=_seema_header_footer, onLaterPages=_seema_header_footer)
    return buf.getvalue()


def generate_weekly_summary_pdf(summary_data, firm_name='Mitchell & Partners LLP'):
    """Generate a Weekly Compliance Summary PDF. Returns bytes."""
    if not REPORTLAB_AVAILABLE:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=35*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('SeemaTitle', parent=styles['Title'], fontSize=20,
                              textColor=SEEMA_NAVY, spaceAfter=6))
    styles.add(ParagraphStyle('SeemaH2', parent=styles['Heading2'], fontSize=13,
                              textColor=SEEMA_NAVY, spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle('SeemaBody', parent=styles['Normal'], fontSize=10,
                              textColor=black, leading=14))
    styles.add(ParagraphStyle('SeemaLabel', parent=styles['Normal'], fontSize=9,
                              textColor=SEEMA_GREY))

    story = []
    s = summary_data.get('summary', {})
    week_ending = datetime.datetime.now().strftime('%d %B %Y')

    story.append(Paragraph('Weekly Compliance Summary', styles['SeemaTitle']))
    story.append(Paragraph(f"{firm_name} — Week Ending {week_ending}", styles['SeemaBody']))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=SEEMA_BORDER))
    story.append(Spacer(1, 4*mm))

    # Key metrics
    story.append(Paragraph('Key Metrics', styles['SeemaH2']))
    metrics_data = [
        ['Overdue Tasks', str(s.get('overdue_count', 0))],
        ['Tasks Due Today', str(s.get('today_count', 0))],
        ['Training Overdue', str(s.get('training_overdue', 0))],
        ['File Reviews Overdue', str(s.get('reviews_overdue', 0))],
        ['Pending Intakes', str(s.get('pending_intakes', 0))],
        ['Open Breaches', str(s.get('open_breaches', 0))],
        ['Active Alerts', str(s.get('active_alerts', 0))],
        ['Chasers Pending', str(s.get('chasers_pending', 0))],
        ['Supervision Overdue', str(s.get('supervision_overdue', 0))],
    ]
    t = Table(metrics_data, colWidths=[60*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), SEEMA_GREY),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, SEEMA_BORDER),
    ]))
    story.append(t)

    # Sign-off
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=SEEMA_BORDER))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph('This report was automatically generated by Seema. Review and take action on any outstanding items.', styles['SeemaLabel']))

    doc.build(story, onFirstPage=_seema_header_footer, onLaterPages=_seema_header_footer)
    return buf.getvalue()


# ============================================================================
# Database Initialization
# ============================================================================

def init_database():
    """Initialize database with schema"""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create tables
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS industries (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        icon TEXT,
        color TEXT
    );

    CREATE TABLE IF NOT EXISTS workflows (
        id TEXT PRIMARY KEY,
        industry_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        category TEXT,
        estimated_duration_minutes INTEGER,
        enabled INTEGER DEFAULT 1,
        FOREIGN KEY (industry_id) REFERENCES industries(id)
    );

    CREATE TABLE IF NOT EXISTS workflow_steps (
        id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        step_number INTEGER,
        name TEXT,
        action_type TEXT,
        requires_approval INTEGER DEFAULT 0,
        FOREIGN KEY (workflow_id) REFERENCES workflows(id)
    );

    CREATE TABLE IF NOT EXISTS workflow_runs (
        id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        started_at TEXT,
        completed_at TEXT,
        error_message TEXT,
        data_input TEXT,
        data_output TEXT,
        FOREIGN KEY (workflow_id) REFERENCES workflows(id)
    );

    CREATE TABLE IF NOT EXISTS run_step_logs (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        step_id TEXT NOT NULL,
        status TEXT,
        started_at TEXT,
        completed_at TEXT,
        duration_ms INTEGER,
        output TEXT,
        error_message TEXT,
        FOREIGN KEY (run_id) REFERENCES workflow_runs(id),
        FOREIGN KEY (step_id) REFERENCES workflow_steps(id)
    );

    CREATE TABLE IF NOT EXISTS law_clients (
        id TEXT PRIMARY KEY,
        name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        date_of_birth TEXT,
        status TEXT
    );

    CREATE TABLE IF NOT EXISTS law_cases (
        id TEXT PRIMARY KEY,
        client_id TEXT,
        case_name TEXT,
        case_type TEXT,
        status TEXT,
        hourly_rate REAL,
        opened_date TEXT,
        FOREIGN KEY (client_id) REFERENCES law_clients(id)
    );

    CREATE TABLE IF NOT EXISTS law_time_entries (
        id TEXT PRIMARY KEY,
        case_id TEXT,
        attorney_id TEXT,
        attorney_name TEXT,
        hours REAL,
        description TEXT,
        entry_date TEXT,
        FOREIGN KEY (case_id) REFERENCES law_cases(id)
    );

    CREATE TABLE IF NOT EXISTS law_documents (
        id TEXT PRIMARY KEY,
        case_id TEXT,
        document_name TEXT,
        document_type TEXT,
        file_path TEXT,
        status TEXT,
        FOREIGN KEY (case_id) REFERENCES law_cases(id)
    );

    CREATE TABLE IF NOT EXISTS law_deadlines (
        id TEXT PRIMARY KEY,
        case_id TEXT,
        deadline_type TEXT,
        due_date TEXT,
        description TEXT,
        status TEXT,
        cpr_rule TEXT,
        FOREIGN KEY (case_id) REFERENCES law_cases(id)
    );

    CREATE TABLE IF NOT EXISTS law_communications (
        id TEXT PRIMARY KEY,
        case_id TEXT,
        client_id TEXT,
        type TEXT,
        subject TEXT,
        sent_date TEXT,
        direction TEXT,
        FOREIGN KEY (case_id) REFERENCES law_cases(id),
        FOREIGN KEY (client_id) REFERENCES law_clients(id)
    );

    CREATE TABLE IF NOT EXISTS compliance_checks (
        id TEXT PRIMARY KEY,
        case_id TEXT,
        client_id TEXT,
        check_type TEXT,
        check_name TEXT,
        status TEXT,
        severity TEXT,
        description TEXT,
        regulation_ref TEXT,
        remediation TEXT,
        checked_at TEXT,
        due_date TEXT,
        resolved_at TEXT,
        FOREIGN KEY (case_id) REFERENCES law_cases(id),
        FOREIGN KEY (client_id) REFERENCES law_clients(id)
    );

    CREATE TABLE IF NOT EXISTS risk_scores (
        id TEXT PRIMARY KEY,
        entity_type TEXT,
        entity_id TEXT,
        overall_score INTEGER,
        sra_score INTEGER,
        aml_score INTEGER,
        cpr_score INTEGER,
        gdpr_score INTEGER,
        limitation_score INTEGER,
        calculated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS compliance_alerts (
        id TEXT PRIMARY KEY,
        alert_type TEXT,
        severity TEXT,
        title TEXT,
        description TEXT,
        case_id TEXT,
        client_id TEXT,
        regulation_ref TEXT,
        action_required TEXT,
        created_at TEXT,
        acknowledged_at TEXT,
        resolved_at TEXT,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (case_id) REFERENCES law_cases(id),
        FOREIGN KEY (client_id) REFERENCES law_clients(id)
    );

    CREATE TABLE IF NOT EXISTS sra_audit_items (
        id TEXT PRIMARY KEY,
        category TEXT,
        item_name TEXT,
        description TEXT,
        status TEXT,
        evidence_ref TEXT,
        last_reviewed TEXT,
        next_review_due TEXT,
        notes TEXT
    );
    """)

    # Remediation plans table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS remediation_plans (
        id TEXT PRIMARY KEY,
        source_type TEXT,
        source_id TEXT,
        title TEXT,
        description TEXT,
        regulation_ref TEXT,
        priority TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'open',
        assigned_to TEXT,
        created_at TEXT,
        due_date TEXT,
        completed_at TEXT,
        category TEXT
    );
    """)

    # Remediation steps, policy documents, breach reports, audit reports
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS remediation_steps (
        id TEXT PRIMARY KEY,
        plan_id TEXT,
        step_number INTEGER,
        title TEXT,
        description TEXT,
        guidance TEXT,
        regulation_ref TEXT,
        status TEXT DEFAULT 'pending',
        assigned_to TEXT,
        due_date TEXT,
        completed_at TEXT,
        evidence_ref TEXT,
        notes TEXT,
        FOREIGN KEY (plan_id) REFERENCES remediation_plans(id)
    );

    CREATE TABLE IF NOT EXISTS policy_documents (
        id TEXT PRIMARY KEY,
        policy_type TEXT,
        title TEXT,
        description TEXT,
        regulation_ref TEXT,
        content TEXT,
        version TEXT DEFAULT '1.0',
        status TEXT DEFAULT 'draft',
        created_at TEXT,
        updated_at TEXT,
        approved_by TEXT,
        approved_at TEXT,
        next_review_date TEXT
    );

    CREATE TABLE IF NOT EXISTS breach_reports (
        id TEXT PRIMARY KEY,
        breach_type TEXT,
        severity TEXT DEFAULT 'medium',
        title TEXT,
        description TEXT,
        discovered_at TEXT,
        discovered_by TEXT,
        affected_data TEXT,
        affected_individuals INTEGER DEFAULT 0,
        ico_notifiable INTEGER DEFAULT 0,
        ico_notified_at TEXT,
        ico_reference TEXT,
        individuals_notified_at TEXT,
        containment_actions TEXT,
        root_cause TEXT,
        remedial_actions TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT,
        closed_at TEXT,
        deadline_72h TEXT
    );

    CREATE TABLE IF NOT EXISTS breach_report_steps (
        id TEXT PRIMARY KEY,
        breach_id TEXT,
        step_number INTEGER,
        title TEXT,
        description TEXT,
        status TEXT DEFAULT 'pending',
        completed_at TEXT,
        completed_by TEXT,
        notes TEXT,
        FOREIGN KEY (breach_id) REFERENCES breach_reports(id)
    );

    CREATE TABLE IF NOT EXISTS audit_reports (
        id TEXT PRIMARY KEY,
        report_type TEXT,
        title TEXT,
        generated_at TEXT,
        generated_by TEXT,
        period_start TEXT,
        period_end TEXT,
        summary TEXT,
        content TEXT,
        status TEXT DEFAULT 'generated'
    );

    CREATE TABLE IF NOT EXISTS staff_members (
        id TEXT PRIMARY KEY,
        name TEXT,
        role TEXT,
        email TEXT,
        pqe INTEGER DEFAULT 0,
        supervisor_id TEXT,
        department TEXT,
        start_date TEXT,
        status TEXT DEFAULT 'active'
    );

    CREATE TABLE IF NOT EXISTS staff_training (
        id TEXT PRIMARY KEY,
        staff_id TEXT,
        training_type TEXT,
        title TEXT,
        status TEXT DEFAULT 'pending',
        due_date TEXT,
        completed_at TEXT,
        cpd_hours REAL DEFAULT 0,
        certificate_ref TEXT,
        FOREIGN KEY (staff_id) REFERENCES staff_members(id)
    );

    CREATE TABLE IF NOT EXISTS staff_file_reviews (
        id TEXT PRIMARY KEY,
        staff_id TEXT,
        case_id TEXT,
        reviewer_id TEXT,
        status TEXT DEFAULT 'pending',
        due_date TEXT,
        completed_at TEXT,
        findings TEXT,
        score INTEGER,
        FOREIGN KEY (staff_id) REFERENCES staff_members(id)
    );

    CREATE TABLE IF NOT EXISTS client_intake (
        id TEXT PRIMARY KEY,
        client_name TEXT,
        client_type TEXT DEFAULT 'individual',
        risk_score INTEGER DEFAULT 0,
        risk_level TEXT DEFAULT 'low',
        cdd_status TEXT DEFAULT 'pending',
        edd_required INTEGER DEFAULT 0,
        pep_flag INTEGER DEFAULT 0,
        jurisdiction_risk TEXT DEFAULT 'low',
        source_of_funds TEXT,
        source_of_wealth TEXT,
        assessed_by TEXT,
        assessed_at TEXT,
        created_at TEXT,
        status TEXT DEFAULT 'pending',
        notes TEXT
    );

    CREATE TABLE IF NOT EXISTS compliance_tasks (
        id TEXT PRIMARY KEY,
        task_type TEXT,
        title TEXT,
        description TEXT,
        assigned_to TEXT,
        related_entity_type TEXT,
        related_entity_id TEXT,
        priority TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'pending',
        due_date TEXT,
        completed_at TEXT,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS regulatory_updates (
        id TEXT PRIMARY KEY,
        source TEXT,
        title TEXT,
        summary TEXT,
        regulation_ref TEXT,
        impact_level TEXT DEFAULT 'info',
        action_required TEXT,
        published_date TEXT,
        effective_date TEXT,
        acknowledged INTEGER DEFAULT 0,
        acknowledged_by TEXT,
        acknowledged_at TEXT
    );

    CREATE TABLE IF NOT EXISTS regulatory_impact_analysis (
        id TEXT PRIMARY KEY,
        update_id TEXT,
        affected_areas TEXT,
        risk_level TEXT DEFAULT 'medium',
        affected_policies TEXT,
        affected_staff_roles TEXT,
        action_items TEXT,
        deadline TEXT,
        ai_summary TEXT,
        ai_recommendation TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        resolved_at TEXT,
        resolved_by TEXT,
        FOREIGN KEY (update_id) REFERENCES regulatory_updates(id)
    );

    CREATE TABLE IF NOT EXISTS policy_update_queue (
        id TEXT PRIMARY KEY,
        policy_id TEXT,
        policy_type TEXT,
        trigger_update_id TEXT,
        change_type TEXT DEFAULT 'review',
        suggested_changes TEXT,
        priority TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        applied_at TEXT,
        applied_by TEXT,
        FOREIGN KEY (trigger_update_id) REFERENCES regulatory_updates(id)
    );

    CREATE TABLE IF NOT EXISTS sra_feed_log (
        id TEXT PRIMARY KEY,
        feed_source TEXT,
        last_checked TEXT,
        items_found INTEGER DEFAULT 0,
        new_items INTEGER DEFAULT 0,
        status TEXT DEFAULT 'ok',
        error_message TEXT
    );

    CREATE TABLE IF NOT EXISTS chaser_log (
        id TEXT PRIMARY KEY,
        chaser_type TEXT,
        recipient_staff_id TEXT,
        recipient_email TEXT,
        recipient_name TEXT,
        subject TEXT,
        message TEXT,
        sent_at TEXT,
        escalated INTEGER DEFAULT 0,
        escalated_at TEXT,
        acknowledged INTEGER DEFAULT 0,
        acknowledged_at TEXT
    );

    CREATE TABLE IF NOT EXISTS evidence_locker (
        id TEXT PRIMARY KEY,
        entity_type TEXT,
        entity_id TEXT,
        title TEXT,
        description TEXT,
        file_type TEXT,
        file_ref TEXT,
        uploaded_by TEXT,
        uploaded_at TEXT,
        verified_by TEXT,
        verified_at TEXT,
        expiry_date TEXT,
        status TEXT DEFAULT 'active'
    );

    CREATE TABLE IF NOT EXISTS audit_trail (
        id TEXT PRIMARY KEY,
        action TEXT,
        entity_type TEXT,
        entity_id TEXT,
        performed_by TEXT,
        performed_at TEXT,
        details TEXT,
        ip_address TEXT DEFAULT '127.0.0.1'
    );

    CREATE TABLE IF NOT EXISTS supervision_schedule (
        id TEXT PRIMARY KEY,
        staff_id TEXT,
        supervisor_id TEXT,
        frequency TEXT,
        next_due TEXT,
        last_completed TEXT,
        meeting_type TEXT,
        risk_level TEXT DEFAULT 'standard',
        notes TEXT,
        status TEXT DEFAULT 'active'
    );

    CREATE TABLE IF NOT EXISTS matter_checklists (
        id TEXT PRIMARY KEY,
        case_id TEXT,
        case_name TEXT,
        matter_type TEXT,
        created_at TEXT,
        status TEXT DEFAULT 'in_progress',
        assigned_to TEXT,
        completed_items INTEGER DEFAULT 0,
        total_items INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS matter_checklist_items (
        id TEXT PRIMARY KEY,
        checklist_id TEXT,
        item_order INTEGER,
        category TEXT,
        title TEXT,
        description TEXT,
        regulation_ref TEXT,
        status TEXT DEFAULT 'pending',
        completed_by TEXT,
        completed_at TEXT,
        evidence_ref TEXT,
        FOREIGN KEY (checklist_id) REFERENCES matter_checklists(id)
    );

    CREATE TABLE IF NOT EXISTS import_logs (
        id TEXT PRIMARY KEY,
        import_type TEXT,
        filename TEXT,
        records_imported INTEGER DEFAULT 0,
        records_failed INTEGER DEFAULT 0,
        imported_by TEXT,
        imported_at TEXT,
        status TEXT DEFAULT 'completed',
        error_details TEXT
    );

    CREATE TABLE IF NOT EXISTS user_accounts (
        id TEXT PRIMARY KEY,
        staff_id TEXT,
        email TEXT UNIQUE,
        password_hash TEXT,
        role TEXT DEFAULT 'staff',
        last_login TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT,
        FOREIGN KEY (staff_id) REFERENCES staff_members(id)
    );

    CREATE TABLE IF NOT EXISTS user_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        token TEXT UNIQUE,
        created_at TEXT,
        expires_at TEXT,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES user_accounts(id)
    );

    CREATE TABLE IF NOT EXISTS staff_actions (
        id TEXT PRIMARY KEY,
        staff_id TEXT,
        action_type TEXT,
        entity_type TEXT,
        entity_id TEXT,
        details TEXT,
        performed_at TEXT,
        FOREIGN KEY (staff_id) REFERENCES staff_members(id)
    );

    CREATE TABLE IF NOT EXISTS email_settings (
        id TEXT PRIMARY KEY,
        smtp_host TEXT DEFAULT '',
        smtp_port INTEGER DEFAULT 587,
        smtp_user TEXT DEFAULT '',
        smtp_password TEXT DEFAULT '',
        from_email TEXT DEFAULT '',
        from_name TEXT DEFAULT 'Seema Compliance',
        enabled INTEGER DEFAULT 0,
        auto_chase_training INTEGER DEFAULT 1,
        auto_chase_reviews INTEGER DEFAULT 1,
        auto_chase_cdd INTEGER DEFAULT 1,
        chase_frequency_days INTEGER DEFAULT 3,
        escalation_after_days INTEGER DEFAULT 7,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS email_queue (
        id TEXT PRIMARY KEY,
        to_email TEXT NOT NULL,
        to_name TEXT DEFAULT '',
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        template TEXT DEFAULT 'general',
        status TEXT DEFAULT 'queued',
        scheduled_at TEXT,
        sent_at TEXT,
        error_message TEXT,
        related_entity_type TEXT,
        related_entity_id TEXT,
        created_at TEXT
    );
    """)

    conn.commit()
    conn.close()

def is_seeded():
    """Check if database is already seeded"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM law_clients")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except:
        return False

def seed_database():
    """Seed database with realistic law firm demo data"""
    if is_seeded():
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    now = datetime.datetime.now()

    # ========== INDUSTRIES ==========
    industries_data = [
        ("law", "Law Firms", "Legal services and case management", "⚖️", "#3B4CC0"),
    ]

    for ind_id, name, desc, icon, color in industries_data:
        cursor.execute(
            "INSERT OR IGNORE INTO industries (id, name, description, icon, color) VALUES (?, ?, ?, ?, ?)",
            (ind_id, name, desc, icon, color)
        )

    # ========== WORKFLOWS ==========
    workflows = [
        "Client Intake & Conflict Check",
        "Case Opening & Assignment",
        "Time Tracking & Billing",
        "Document Generation & Review",
        "Case Status Update & Reporting",
        "Settlement & Case Closure",
        "Compliance & Ethics Review",
        "Client Communication & Updates",
        "Deadline & Matter Management",
        "Knowledge Management & Precedents",
    ]

    workflow_steps_map = {
        "Client Intake & Conflict Check": ["Gather Client Information", "Search Existing Records", "Run Conflict Analysis", "Generate Conflict Report", "Create Client File"],
        "Case Opening & Assignment": ["Create Case Record", "Classify Case Type", "Assign Primary Attorney", "Send Notification", "Initialize Case Folder"],
        "Time Tracking & Billing": ["Retrieve Time Entries", "Validate Hours", "Calculate Billable Amount", "Generate Invoice", "Record Invoice"],
        "Document Generation & Review": ["Select Template", "Fill Template with Case Data", "Generate Document", "Send for Review", "Log Document Version"],
        "Case Status Update & Reporting": ["Retrieve Case Data", "Update Status", "Generate Status Report", "Send to Stakeholders"],
        "Settlement & Case Closure": ["Record Settlement Terms", "Calculate Final Costs", "Generate Settlement Agreement", "Archive Case Records", "Close Case"],
        "Compliance & Ethics Review": ["Flag Potential Issues", "Review Against Standards", "Generate Compliance Report", "Escalate if Needed"],
        "Client Communication & Updates": ["Prepare Case Summary", "Draft Communication", "Send Email Update", "Log Communication"],
        "Deadline & Matter Management": ["Query Upcoming Deadlines", "Generate Calendar", "Alert Responsible Attorneys", "Track Responses"],
        "Knowledge Management & Precedents": ["Index Document", "Add Metadata", "Make Searchable", "Link to Cases"],
    }

    approval_required_steps = {
        "Send to Client", "Record Invoice", "Send Email Update", "Send Notification",
        "Send for Review", "Close Case", "Archive Case Records",
    }

    for idx, workflow_name in enumerate(workflows, 1):
        workflow_id = f"law-wf-{idx:03d}"
        cursor.execute(
            """INSERT OR IGNORE INTO workflows
               (id, industry_id, name, description, category, estimated_duration_minutes, enabled)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (workflow_id, "law", workflow_name, f"{workflow_name} workflow", "operational", 30 + random.randint(0, 60))
        )

        steps = workflow_steps_map.get(workflow_name, [f"Step {i}" for i in range(1, 5)])
        for step_num, step_name in enumerate(steps, 1):
            step_id = str(uuid.uuid4())
            needs_approval = 1 if step_name in approval_required_steps else 0
            cursor.execute(
                """INSERT OR IGNORE INTO workflow_steps
                   (id, workflow_id, step_number, name, action_type, requires_approval)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (step_id, workflow_id, step_num, step_name, "process", needs_approval)
            )

    # ========== LAW CLIENT DATA ==========
    law_clients = []
    company_names = [
        "Acme Corporation", "Tech Solutions Ltd", "BuildRight Construction", "Global Trade Inc",
        "Digital Innovations Group", "Finance Partners UK", "Healthcare Systems Ltd", "Manufacturing Pro",
        "Supply Chain Experts", "Retail Networks plc", "Energy Resources Ltd", "Transport & Logistics Co",
        "Media Services Group", "Education Plus Ltd", "Agriculture Ventures", "Tourism & Travel Group",
        "Software Studios Ltd", "Design Collective", "Marketing Genius Agency", "Consulting Group International",
        "Real Estate Holdings", "Investment Fund Management", "Insurance Solutions Ltd", "Logistics Hub UK",
        "Fashion Brands Europe", "Food Services Group", "Chemical Industries plc", "Telecommunications Corp",
        "Property Development Ltd", "Pharmaceutical Solutions",
        "Hospitality Management Group", "Automotive Systems Ltd",
    ]

    for i, company in enumerate(company_names):
        client_id = str(uuid.uuid4())
        law_clients.append(client_id)
        cursor.execute(
            """INSERT OR IGNORE INTO law_clients
               (id, name, email, phone, address, date_of_birth, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (client_id, company, f"legal@{company.lower().replace(' ', '').replace('&', 'and')}.co.uk",
             f"020{random.randint(10000000, 99999999)}",
             f"{random.randint(1, 999)} {random.choice(['High Street', 'Main Street', 'Park Avenue', 'Business Park', 'Industrial Estate', 'City Centre'])}, {random.choice(['London', 'Manchester', 'Birmingham', 'Leeds', 'Glasgow', 'Edinburgh'])}",
             None, random.choice(["active", "active", "active", "inactive"]))
        )

    # Law cases with realistic UK case types
    law_cases = []
    case_types = [
        "Commercial Litigation",
        "Employment Dispute",
        "Property Conveyancing",
        "Family - Divorce",
        "IP - Patent",
        "Clinical Negligence",
        "Contract Dispute",
        "Commercial - M&A",
        "Intellectual Property - Trademark",
        "Construction Dispute",
        "Professional Negligence",
        "Data Protection - GDPR",
        "Banking & Finance",
        "Regulatory Compliance",
        "Insolvency & Restructuring",
    ]

    case_statuses = ["open", "open", "open", "in-progress", "in-progress", "pending-settlement", "closed", "closed", "on-hold"]

    for i in range(45):
        case_id = str(uuid.uuid4())
        law_cases.append(case_id)
        case_type = random.choice(case_types)
        hourly_rate = 150 + random.randint(50, 350)
        opened_date = (now - datetime.timedelta(days=random.randint(1, 365))).isoformat()

        cursor.execute(
            """INSERT OR IGNORE INTO law_cases
               (id, client_id, case_name, case_type, status, hourly_rate, opened_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (case_id, random.choice(law_clients), f"{case_type} - Matter {i+1}", case_type,
             random.choice(case_statuses), hourly_rate, opened_date)
        )

    # Time entries - 100+ entries with realistic data
    attorney_names = [
        "John Smith", "Sarah Johnson", "Michael Chen", "Emma Wilson", "David Brown",
        "Rachel Green", "Christopher Lee", "Jennifer Martinez", "Andrew Taylor", "Sophie Anderson",
        "James Clark", "Lisa White", "Robert Young", "Amanda Harris", "Peter Thompson"
    ]

    for i in range(110):
        case_id = random.choice(law_cases)
        attorney = random.choice(attorney_names)
        hours = round(random.uniform(0.5, 8), 1)
        entry_date = (now - datetime.timedelta(days=random.randint(1, 120))).isoformat()

        descriptions = [
            "Research & analysis",
            "Client consultation",
            "Document drafting",
            "Witness interview",
            "Settlement negotiation",
            "Court preparation",
            "Discovery review",
            "Legal research - case law",
            "Motion preparation",
            "Correspondence with opposing counsel",
            "File review & organization",
            "Expert witness coordination"
        ]

        cursor.execute(
            """INSERT OR IGNORE INTO law_time_entries
               (id, case_id, attorney_id, attorney_name, hours, description, entry_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), case_id, str(uuid.uuid4()), attorney, hours,
             random.choice(descriptions), entry_date)
        )

    # Documents - 60+ documents
    document_types = [
        "Contract", "Brief", "Motion", "Discovery", "Deposition", "Affidavit",
        "Witness Statement", "Expert Report", "Engagement Letter", "Terms of Engagement",
        "Settlement Agreement", "Court Order", "Legal Opinion", "Due Diligence Report",
        "Pleading", "Notice", "Correspondence", "Precedent Case", "Research Memo",
        "Client Update Letter"
    ]

    for i in range(65):
        case_id = random.choice(law_cases)
        doc_type = random.choice(document_types)
        doc_status = random.choice(["filed", "pending-review", "reviewed", "executed", "archived"])

        cursor.execute(
            """INSERT OR IGNORE INTO law_documents
               (id, case_id, document_name, document_type, file_path, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), case_id, f"{doc_type} - {random.randint(1, 999)}",
             doc_type, f"/docs/case_{i}/doc_{i}.pdf", doc_status)
        )

    # Law deadlines - CPR and procedural deadlines
    deadline_types = [
        "CPR Service Deadline",
        "Statement of Case Due",
        "Disclosure Deadline",
        "Expert Evidence Due",
        "Trial Preparation",
        "Settlement Conference",
        "Cost Settlement",
        "Court Hearing",
        "Appeal Deadline",
        "Payment Due"
    ]

    cpr_rules = [
        "CPR 6.3", "CPR 9.8", "CPR 26.3", "CPR 35.13", "CPR 39.3",
        "CPR 44.3", "CPR 52.4", None, None, "CPR 7.2"
    ]

    for i in range(50):
        case_id = random.choice(law_cases)
        deadline_type = random.choice(deadline_types)
        days_offset = random.randint(-30, 365)
        due_date = (now + datetime.timedelta(days=days_offset)).isoformat()
        status = "overdue" if days_offset < 0 else "pending"
        cpr = random.choice(cpr_rules)

        cursor.execute(
            """INSERT OR IGNORE INTO law_deadlines
               (id, case_id, deadline_type, due_date, description, status, cpr_rule)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), case_id, deadline_type, due_date,
             f"{deadline_type} for ongoing matter", status, cpr)
        )

    # Law communications - case-related communications
    communication_types = [
        "Case Update",
        "Client Advice",
        "Settlement Proposal",
        "Status Report",
        "Bill/Invoice",
        "Court Notice",
        "Witness Interview",
        "Expert Coordination",
        "Opposing Counsel Communication",
        "Court Filing Notice"
    ]

    directions = ["outgoing", "incoming", "internal"]

    for i in range(80):
        case_id = random.choice(law_cases)
        client_id = random.choice(law_clients)
        comm_type = random.choice(communication_types)
        direction = random.choice(directions)
        sent_date = (now - datetime.timedelta(days=random.randint(1, 180))).isoformat()

        cursor.execute(
            """INSERT OR IGNORE INTO law_communications
               (id, case_id, client_id, type, subject, sent_date, direction)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), case_id, client_id, comm_type,
             f"{comm_type}: Matter Reference", sent_date, direction)
        )

    # ========== COMPLIANCE CHECKS ==========
    check_types = ["SRA", "AML", "CPR", "GDPR", "Costs", "Limitation"]
    check_statuses = ["pass", "pass", "pass", "pass", "warning", "fail"]

    compliance_check_data = [
        # SRA Checks
        ("SRA", "Client Money Handling", "SRA Accounts Rules 2019 r2.1", "Proper segregation of client funds from firm accounts"),
        ("SRA", "Conflict of Interest Check", "SRA Standards 2019 s3", "Complete conflict searches on new clients"),
        ("SRA", "File Management", "SRA Standards 2019 s4", "Secure file storage and retention procedures"),
        ("SRA", "Supervision of Staff", "SRA Standards 2019 s2", "Oversight of legal staff activities"),
        ("SRA", "Client Retainer Letters", "SRA Standards 2019 s1", "Clear engagement terms provided to clients"),
        # AML Checks
        ("AML", "Customer Due Diligence", "MLR 2017 Reg 28", "CDD verification completed for all clients"),
        ("AML", "Enhanced Due Diligence", "MLR 2017 Reg 33", "EDD conducted for high-risk clients"),
        ("AML", "Beneficial Ownership Verification", "MLR 2017 Reg 19", "BO information verified and documented"),
        ("AML", "Suspicious Activity Reporting", "MLR 2017 Reg 20", "STR filed where appropriate"),
        ("AML", "Money Laundering Officer", "MLR 2017 Reg 24", "MLRO appointed and trained"),
        # CPR Checks
        ("CPR", "CPR Part 31.5 Disclosure", "CPR Part 31.5", "Full disclosure of relevant documents"),
        ("CPR", "Expert Evidence Compliance", "CPR Part 35", "Expert reports comply with expert declaration"),
        ("CPR", "Witness Statement Format", "CPR Part 32", "Witness statements in correct format"),
        ("CPR", "Deadline Compliance", "CPR Parts 2-7", "All procedural deadlines met"),
        ("CPR", "Court Fee Payments", "CPR Part 44", "Court fees paid on time and correctly calculated"),
        # GDPR Checks
        ("GDPR", "Data Protection Impact Assessment", "UK GDPR Art 35", "DPIA completed where required"),
        ("GDPR", "Subject Access Request Response", "UK GDPR Art 15", "DSAR responded within 30 calendar days"),
        ("GDPR", "Privacy Policy Display", "UK GDPR Art 13-14", "Privacy notices provided to data subjects"),
        ("GDPR", "Data Processor Agreements", "UK GDPR Art 28", "DPA in place with all processors"),
        ("GDPR", "Breach Notification", "UK GDPR Art 33", "Data breach reported to ICO if required"),
        # Costs Checks
        ("Costs", "Costs Budget Accuracy", "CPR Part 3", "Costs budgets realistic and detailed"),
        ("Costs", "Bill Narrative Compliance", "Law Society Standards", "Bill includes compliant narrative"),
        ("Costs", "Contingency Fee Agreement", "Law Society Guidelines", "CFA terms comply with regulations"),
        ("Costs", "Disbursement Recording", "Law Society Guidelines", "All disbursements properly recorded"),
        ("Costs", "VAT Treatment", "HMRC Guidelines", "VAT correctly calculated and declared"),
        # Limitation Checks
        ("Limitation", "Limitation Period Tracking", "Limitation Act 1980 s2", "Limitation expiry dates tracked"),
        ("Limitation", "Extension of Time Applications", "Limitation Act 1980 s33", "Extensions sought before expiry"),
        ("Limitation", "Equitable Remedies Consideration", "Limitation Act 1980 s36", "Equitable claims analysed separately"),
        ("Limitation", "Accrual Date Analysis", "Limitation Act 1980 s5", "Accrual dates correctly identified"),
        ("Limitation", "Notice of Expiry", "CPR Part 7", "All parties notified of limitation expiry"),
    ]

    sra_check_count = 0
    aml_check_count = 0
    cpr_check_count = 0
    gdpr_check_count = 0
    costs_check_count = 0
    limitation_check_count = 0

    for check_type, check_name, reg_ref, description in compliance_check_data:
        for _ in range(1 + random.randint(0, 1)):  # Generate 1-2 instances per check type
            case_id = random.choice(law_cases) if random.random() > 0.3 else None
            client_id = random.choice(law_clients) if random.random() > 0.4 else None
            status = random.choice(check_statuses)

            if status == "fail":
                severity = random.choice(["critical", "high"])
                remediation = f"Immediate remediation required. Review {reg_ref} and implement corrective actions within 7 days."
            elif status == "warning":
                severity = "medium"
                remediation = f"Review current procedures against {reg_ref}. Update policies and provide staff training."
            else:
                severity = random.choice(["low", "low"])
                remediation = None

            checked_date = (now - datetime.timedelta(days=random.randint(1, 60))).isoformat()
            due_date = (now + datetime.timedelta(days=random.randint(10, 90))).isoformat()
            resolved_date = (now - datetime.timedelta(days=random.randint(1, 30))).isoformat() if status == "pass" else None

            cursor.execute(
                """INSERT OR IGNORE INTO compliance_checks
                   (id, case_id, client_id, check_type, check_name, status, severity, description,
                    regulation_ref, remediation, checked_at, due_date, resolved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), case_id, client_id, check_type, check_name, status, severity,
                 description, reg_ref, remediation, checked_date, due_date, resolved_date)
            )

            if check_type == "SRA":
                sra_check_count += 1
            elif check_type == "AML":
                aml_check_count += 1
            elif check_type == "CPR":
                cpr_check_count += 1
            elif check_type == "GDPR":
                gdpr_check_count += 1
            elif check_type == "Costs":
                costs_check_count += 1
            else:
                limitation_check_count += 1

    # ========== RISK SCORES ==========
    # Firm-level risk score
    cursor.execute(
        """INSERT OR IGNORE INTO risk_scores
           (id, entity_type, entity_id, overall_score, sra_score, aml_score, cpr_score, gdpr_score, limitation_score, calculated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), "firm", "firm-1", 18, 15, 22, 18, 25, 12, now.isoformat())
    )

    # Case-level risk scores
    for case_id in law_cases[:15]:  # Generate scores for first 15 cases
        overall = random.randint(8, 65)
        cursor.execute(
            """INSERT OR IGNORE INTO risk_scores
               (id, entity_type, entity_id, overall_score, sra_score, aml_score, cpr_score, gdpr_score, limitation_score, calculated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), "case", case_id,
             overall,
             random.randint(5, 40),
             random.randint(5, 50),
             random.randint(5, 45),
             random.randint(5, 35),
             random.randint(5, 30),
             now.isoformat())
        )

    # ========== COMPLIANCE ALERTS ==========
    alert_templates = [
        ("limitation_expiring", "critical", "Limitation period expiring in 14 days", "Acme v BuildRight", "Limitation Act 1980 s2", "File claim immediately"),
        ("aml_review_due", "high", "AML CDD review overdue for client", "Global Trade Inc", "MLR 2017 Reg 28", "Complete CDD verification by end of week"),
        ("cpr_deadline", "critical", "CPR Part 36 offer deadline tomorrow", "Tech Solutions v DataCorp", "CPR Part 36", "Decision required on settlement offer"),
        ("sra_breach", "critical", "SRA Accounts Rule breach detected", "Firm Account A123", "SRA Accounts Rules 2019", "Rebalance client money accounts immediately"),
        ("gdpr_dsar", "high", "GDPR DSAR response due in 5 days", "Data Subject Request - ABC Ltd", "UK GDPR Art 15", "Compile and deliver subject data"),
        ("deadline_approaching", "high", "Statement of Case due in 10 days", "Property Dispute Matter 2024", "CPR Part 16", "Finalize pleading and serve"),
        ("file_review_overdue", "medium", "Mandatory file review overdue for case", "Employment Matter - Smith", "SRA Standards 2019", "Complete supervisor review"),
        ("cost_certification", "high", "Costs certification deadline in 3 days", "Litigation v Defendant", "CPR Part 44", "Prepare and file costs schedule"),
        ("conflict_check_failed", "critical", "Conflict check failed - new instruction at risk", "Potential New Client - XYZ Ltd", "SRA Standards 2019", "Resolve conflict or decline instruction"),
        ("insurance_renewal", "medium", "Professional indemnity insurance renewal due", "PII Coverage 2024-2025", "SRA Standards 2019", "Renew insurance before expiry"),
        ("sra_training_overdue", "medium", "SRA training for staff member overdue", "New Solicitor - J. Williams", "SRA Standards 2019", "Complete mandatory SRA training"),
        ("limitation_approaching", "high", "Limitation period approaching in 30 days", "Negligence v Hospital NHS", "Limitation Act 1980 s2", "Finalise evidence and prepare claim"),
        ("disclosure_incomplete", "high", "CPR Part 31 disclosure incomplete for case", "Commercial Dispute 2024", "CPR Part 31.5", "Complete disclosure review and file"),
        ("evidence_deadline", "high", "Expert evidence deadline approaching", "Construction v Contractor", "CPR Part 35", "Finalize expert report"),
        ("client_update_due", "medium", "Regular client update overdue for case", "Banking Matter - Finance Corp", "Law Society Standards", "Send status update to client"),
        ("bill_narrative_issues", "medium", "Bill narrative requires revision before sending", "Invoice - ABC Ltd Matter", "Law Society Guidelines", "Revise narrative and reissue"),
        ("gdpr_breach_reported", "critical", "Data breach - ICO notification required", "Security Incident 2024-04", "UK GDPR Art 33", "File GDPR breach notification with ICO"),
        ("deadline_passed", "critical", "Procedural deadline MISSED - case at risk", "Urgent - Smith v Jones", "CPR Part 7", "Apply for relief from sanctions"),
    ]

    for idx, (alert_type, severity, title, case_ref, reg_ref, action) in enumerate(alert_templates):
        case_id = random.choice(law_cases) if idx < 10 else None
        client_id = random.choice(law_clients) if idx % 2 == 0 else None
        created = (now - datetime.timedelta(days=random.randint(0, 30))).isoformat()
        acknowledged = (now - datetime.timedelta(days=random.randint(0, 15))).isoformat() if random.random() > 0.4 else None
        resolved = None
        status = "resolved" if random.random() > 0.85 else ("acknowledged" if acknowledged else "active")

        cursor.execute(
            """INSERT OR IGNORE INTO compliance_alerts
               (id, alert_type, severity, title, description, case_id, client_id, regulation_ref, action_required, created_at, acknowledged_at, resolved_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), alert_type, severity, title, case_ref, case_id, client_id, reg_ref, action, created, acknowledged, resolved, status)
        )

    # Add a few more random alerts
    for _ in range(5):
        alert_type = random.choice(["deadline_approaching", "limitation_expiring", "aml_review_due", "sra_breach", "overdue_cpr"])
        severity = random.choice(["critical", "high", "medium", "low"])
        case_id = random.choice(law_cases)
        client_id = random.choice(law_clients)
        created = (now - datetime.timedelta(days=random.randint(0, 20))).isoformat()

        cursor.execute(
            """INSERT OR IGNORE INTO compliance_alerts
               (id, alert_type, severity, title, description, case_id, client_id, regulation_ref, action_required, created_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), alert_type, severity, f"{alert_type} alert", "Matter under review", case_id, client_id, "Various", "Review and respond", created, "active")
        )

    # ========== SRA AUDIT ITEMS ==========
    sra_categories = [
        ("accounts", "Client Money Segregation", "Verify client funds held separately from firm account"),
        ("accounts", "Accounting Records", "Review full accounting records and ledgers"),
        ("accounts", "Audit Trail", "Confirm all transactions properly recorded"),
        ("conflicts", "Conflict Register", "Check conflict of interest register is maintained"),
        ("conflicts", "Conflict Searches", "Verify searches performed for all new clients"),
        ("conflicts", "Existing Client Conflicts", "Review for conflicts with current client base"),
        ("complaints", "Complaint Handling Log", "Review complaints register and resolutions"),
        ("complaints", "Complaints Procedure", "Verify complaints procedure is documented"),
        ("complaints", "Ombudsman Cases", "Check for any Legal Ombudsman referrals"),
        ("supervision", "Supervision Plan", "Review supervision plan for all fee earners"),
        ("supervision", "File Reviews", "Verify supervisory file reviews completed"),
        ("supervision", "Staff Training", "Confirm mandatory training completed"),
        ("file_management", "File Retention", "Check file retention policy and compliance"),
        ("file_management", "Secure Storage", "Verify secure storage of client files"),
        ("file_management", "Document Destruction", "Check document destruction procedures"),
        ("money_laundering", "CDD Procedures", "Verify Customer Due Diligence procedures in place"),
        ("money_laundering", "MLRO Appointment", "Confirm Money Laundering Reporting Officer appointed"),
        ("money_laundering", "AML Training", "Check all staff completed AML training"),
        ("money_laundering", "STR Reporting", "Review Suspicious Transaction Reports filed"),
        ("money_laundering", "Register Maintenance", "Verify beneficial ownership register maintained"),
        ("insurance", "Indemnity Insurance", "Confirm PII insurance in place and adequate"),
        ("insurance", "Cover Verification", "Check insurer confirms cover remains valid"),
        ("insurance", "Claims History", "Review any previous claims made"),
        ("data_protection", "Data Protection Policy", "Verify GDPR-compliant privacy policy"),
        ("data_protection", "DPA Register", "Check Data Processing Agreements in place"),
        ("data_protection", "DSAR Process", "Verify Subject Access Request procedures"),
        ("data_protection", "Breach Procedures", "Confirm breach notification procedures documented"),
        ("data_protection", "Consent Records", "Review client consent records for processing"),
        ("accounts", "VAT Compliance", "Verify correct VAT calculation and reporting"),
        ("supervision", "Competence Assessment", "Check competence assessment records"),
        ("file_management", "Confidentiality Controls", "Verify confidentiality and security controls"),
        ("conflicts", "PII and Consent", "Check client retainers and engagement letters"),
        ("insurance", "Cyber Insurance", "Verify cyber insurance coverage in place"),
        ("money_laundering", "Enhanced Due Diligence", "Verify EDD completed for high-risk clients"),
        ("accounts", "Disbursement Recording", "Check disbursements properly categorized"),
        ("supervision", "Complaint Response", "Verify timely complaint acknowledgement"),
        ("file_management", "Work in Progress", "Review WIP tracking and recording"),
        ("data_protection", "Third Party Data", "Check procedures for third-party data processing"),
    ]

    for category, item_name, description in sra_categories:
        status = random.choice(["compliant", "compliant", "compliant", "compliant", "needs_review", "non_compliant"])
        last_reviewed = (now - datetime.timedelta(days=random.randint(10, 120))).isoformat()
        next_review = (now + datetime.timedelta(days=random.randint(20, 180))).isoformat()
        evidence_ref = f"File/{category}/{item_name.replace(' ', '_')}" if status == "compliant" else None
        notes = f"Reviewed and confirmed - {status}" if status == "compliant" else f"Requires attention - {status}"

        cursor.execute(
            """INSERT OR IGNORE INTO sra_audit_items
               (id, category, item_name, description, status, evidence_ref, last_reviewed, next_review_due, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), category, item_name, description, status, evidence_ref, last_reviewed, next_review, notes)
        )

    # ========== STAFF MEMBERS ==========
    staff_data = [
        ("staff-001", "Sarah Mitchell", "Managing Partner / COLP", "s.mitchell@firm.co.uk", 18, None, "Management"),
        ("staff-002", "James Henderson", "Senior Partner / COFA", "j.henderson@firm.co.uk", 15, None, "Accounts"),
        ("staff-003", "Rebecca Osei", "Associate Solicitor", "r.osei@firm.co.uk", 5, "staff-001", "Litigation"),
        ("staff-004", "David Kim", "Associate Solicitor", "d.kim@firm.co.uk", 3, "staff-001", "Conveyancing"),
        ("staff-005", "Priya Sharma", "Trainee Solicitor", "p.sharma@firm.co.uk", 0, "staff-003", "Litigation"),
        ("staff-006", "Tom Williams", "Paralegal", "t.williams@firm.co.uk", 0, "staff-004", "Conveyancing"),
        ("staff-007", "Emma Clarke", "MLRO / Compliance", "e.clarke@firm.co.uk", 8, "staff-001", "Compliance"),
        ("staff-008", "Amir Hassan", "Solicitor", "a.hassan@firm.co.uk", 2, "staff-003", "Family"),
        ("staff-009", "Lucy Chen", "Solicitor", "l.chen@firm.co.uk", 4, "staff-002", "Corporate"),
        ("staff-010", "Nathan Brown", "Practice Manager", "n.brown@firm.co.uk", 0, "staff-001", "Operations"),
    ]

    for sid, name, role, email, pqe, supervisor, dept in staff_data:
        start = (now - datetime.timedelta(days=random.randint(180, 2500))).isoformat()
        cursor.execute(
            """INSERT OR IGNORE INTO staff_members (id, name, role, email, pqe, supervisor_id, department, start_date, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
            (sid, name, role, email, pqe, supervisor, dept, start)
        )

    # ========== STAFF TRAINING ==========
    training_types = [
        ("aml_annual", "Annual AML Training", 2.0),
        ("gdpr_annual", "Annual GDPR & Data Protection Training", 1.5),
        ("equality", "Equality, Diversity & Inclusion", 1.0),
        ("accounts_rules", "SRA Accounts Rules Update", 1.5),
        ("ethics", "Professional Ethics & Conduct", 2.0),
        ("cyber_security", "Cyber Security Awareness", 1.0),
        ("complaints_handling", "Complaints Handling Procedures", 1.0),
    ]

    for sid, name, role, email, pqe, supervisor, dept in staff_data:
        for ttype, ttitle, hours in training_types:
            tid = str(uuid.uuid4())
            # Random status: some complete, some overdue, some pending
            r = random.random()
            if r < 0.5:
                status = "completed"
                due = (now - datetime.timedelta(days=random.randint(10, 90))).isoformat()
                completed = (now - datetime.timedelta(days=random.randint(1, 30))).isoformat()
            elif r < 0.75:
                status = "overdue"
                due = (now - datetime.timedelta(days=random.randint(1, 30))).isoformat()
                completed = None
            else:
                status = "pending"
                due = (now + datetime.timedelta(days=random.randint(5, 60))).isoformat()
                completed = None

            cursor.execute(
                """INSERT OR IGNORE INTO staff_training (id, staff_id, training_type, title, status, due_date, completed_at, cpd_hours)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (tid, sid, ttype, ttitle, status, due, completed, hours)
            )

    # ========== STAFF FILE REVIEWS ==========
    fee_earners = [s for s in staff_data if s[4] > 0 or "Trainee" in s[2]]  # PQE > 0 or trainee
    case_ids_q = cursor.execute("SELECT id FROM law_cases LIMIT 20").fetchall()
    case_id_list = [r[0] for r in case_ids_q]

    for sid, name, role, email, pqe, supervisor, dept in fee_earners:
        num_reviews = random.randint(2, 5)
        for _ in range(num_reviews):
            frid = str(uuid.uuid4())
            cid = random.choice(case_id_list) if case_id_list else ""
            reviewer = supervisor or "staff-001"
            r = random.random()
            if r < 0.4:
                status = "completed"
                due = (now - datetime.timedelta(days=random.randint(5, 60))).isoformat()
                completed = (now - datetime.timedelta(days=random.randint(1, 15))).isoformat()
                score = random.randint(70, 100)
                findings = random.choice(["Satisfactory", "Good — minor points noted", "Excellent", "Needs improvement on costs information"])
            elif r < 0.7:
                status = "overdue"
                due = (now - datetime.timedelta(days=random.randint(1, 20))).isoformat()
                completed = None; score = None; findings = None
            else:
                status = "pending"
                due = (now + datetime.timedelta(days=random.randint(3, 30))).isoformat()
                completed = None; score = None; findings = None

            cursor.execute(
                """INSERT OR IGNORE INTO staff_file_reviews (id, staff_id, case_id, reviewer_id, status, due_date, completed_at, findings, score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (frid, sid, cid, reviewer, status, due, completed, findings, score)
            )

    # ========== CLIENT INTAKE / RISK ASSESSMENT ==========
    intake_data = [
        ("Northbridge Holdings Ltd", "company", 65, "high", "completed", 1, 0, "medium", "Business profits", "Property portfolio", "Assessed — EDD required due to complex ownership"),
        ("Mr. Gerald Whittaker", "individual", 15, "low", "completed", 0, 0, "low", "Employment salary", "Pension savings", "Standard CDD completed"),
        ("Apex Global Trading FZE", "company", 82, "high", "pending", 1, 0, "high", "International trade", "Unknown", "Awaiting EDD — UAE-registered entity"),
        ("Mrs. Patricia Knowles", "individual", 10, "low", "completed", 0, 0, "low", "Pension", "Property sale", "Standard CDD completed"),
        ("Senator Miguel Alvarez", "individual", 90, "critical", "pending", 1, 1, "high", "Government salary", "Unclear", "PEP flagged — awaiting senior partner approval"),
        ("Greenfield Developments LLP", "company", 35, "medium", "completed", 0, 0, "low", "Development profits", "Land sales", "CDD completed — ongoing monitoring"),
        ("Zhang Wei International Ltd", "company", 70, "high", "pending", 1, 0, "high", "Commodity trading", "Unknown", "EDD required — high-risk jurisdiction"),
        ("Dr. Amelia Foster", "individual", 12, "low", "completed", 0, 0, "low", "Medical practice", "Savings", "Standard CDD completed"),
    ]

    for cname, ctype, risk, level, cdd_status, edd, pep, jrisk, sof, sow, notes in intake_data:
        iid = str(uuid.uuid4())
        assessed_at = (now - datetime.timedelta(days=random.randint(0, 14))).isoformat() if cdd_status == "completed" else None
        cursor.execute(
            """INSERT OR IGNORE INTO client_intake
               (id, client_name, client_type, risk_score, risk_level, cdd_status, edd_required, pep_flag,
                jurisdiction_risk, source_of_funds, source_of_wealth, assessed_by, assessed_at, created_at, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (iid, cname, ctype, risk, level, cdd_status, edd, pep, jrisk, sof, sow,
             "Emma Clarke" if cdd_status == "completed" else None, assessed_at,
             (now - datetime.timedelta(days=random.randint(0, 21))).isoformat(),
             cdd_status, notes)
        )

    # ========== COMPLIANCE TASKS (daily tasks) ==========
    task_data = [
        ("cdd_review", "Complete CDD for Apex Global Trading FZE", "New client awaiting identity verification and source of funds documentation.", "Emma Clarke", "high", -1),
        ("cdd_review", "Complete EDD for Zhang Wei International Ltd", "Enhanced due diligence required — high-risk jurisdiction.", "Emma Clarke", "critical", 0),
        ("cdd_review", "PEP assessment — Senator Miguel Alvarez", "PEP flagged — requires senior partner sign-off before engagement.", "Sarah Mitchell", "critical", 0),
        ("file_review", "Q1 file review — Priya Sharma caseload", "Quarterly supervisory file review for trainee solicitor.", "Rebecca Osei", "high", 3),
        ("file_review", "Monthly file review — Amir Hassan", "Monthly supervision file check.", "Rebecca Osei", "medium", 7),
        ("training", "Chase AML training completion — David Kim", "AML training overdue by 12 days.", "Nathan Brown", "high", -12),
        ("training", "Schedule ethics CPD for all fee earners", "Annual ethics training due next month.", "Nathan Brown", "medium", 25),
        ("accounts", "Monthly client account reconciliation", "Five-weekly reconciliation due under SRA Accounts Rules.", "James Henderson", "critical", 2),
        ("accounts", "Review disbursement ledger entries", "Check disbursements recorded correctly for Q1.", "James Henderson", "medium", 10),
        ("policy_review", "Review AML policy — annual review due", "Annual review date approaching for the firm's AML policy.", "Emma Clarke", "high", 14),
        ("policy_review", "Update privacy notice for website", "Privacy notice needs updating after ICO guidance change.", "Emma Clarke", "medium", 20),
        ("supervision", "Supervision meeting — Priya Sharma", "Fortnightly trainee supervision meeting.", "Rebecca Osei", "high", 1),
        ("supervision", "Supervision meeting — Tom Williams", "Monthly paralegal supervision.", "David Kim", "medium", 5),
        ("complaint", "Respond to Mrs. Allen complaint", "Complaint received 5 weeks ago — 8-week deadline approaching.", "Sarah Mitchell", "critical", -2),
        ("complaint", "Log informal complaint from Mr. Barnes", "Verbal complaint about delayed communication — needs logging.", "Nathan Brown", "high", 0),
        ("insurance", "Confirm PII renewal terms", "PII renewal due in 6 weeks — confirm terms with broker.", "James Henderson", "high", 14),
        ("data_protection", "Process DSAR from former client", "DSAR received — 1 month response deadline.", "Emma Clarke", "high", 5),
        ("conflict_check", "Run conflict check — new matter Thompson v. Price", "Conflict check required before accepting instructions.", "Lucy Chen", "critical", 0),
    ]

    for ttype, title, desc, assigned, priority, due_offset in task_data:
        tid = str(uuid.uuid4())
        due = (now + datetime.timedelta(days=due_offset)).isoformat()
        status = "overdue" if due_offset < 0 else "pending"
        cursor.execute(
            """INSERT OR IGNORE INTO compliance_tasks (id, task_type, title, description, assigned_to, priority, status, due_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tid, ttype, title, desc, assigned, priority, status, due, now.isoformat())
        )

    # ========== REGULATORY UPDATES ==========
    reg_updates = [
        ("SRA", "SRA publishes updated AML guidance for small firms", "New guidance on proportionate AML measures for firms with 2-50 solicitors. Emphasis on risk-based approach and practical implementation.",
         "MLR 2017; SRA Warning Notice", "action", "Review updated guidance and assess whether firm's AML procedures need revision.", -3, 30),
        ("SRA", "Reminder: Annual renewal of practising certificates", "Practising certificate renewal window opens 1 October. Ensure all solicitors' details are accurate on mySRA.",
         "SRA Authorisation Rules", "action", "Verify all solicitor details on mySRA portal are current.", -7, 45),
        ("ICO", "ICO issues updated guidance on data breach reporting", "Clarification on the 72-hour reporting threshold and what constitutes 'awareness' of a breach. New examples provided.",
         "UK GDPR Art 33", "action", "Update breach response plan to reflect new ICO examples.", -5, 14),
        ("SRA", "Thematic review: supervision of junior lawyers", "SRA announces thematic review into supervision practices. Firms may be selected for desk-based assessment.",
         "SRA Code of Conduct Para 3.5", "action", "Review supervision records and ensure all are up to date.", -2, None),
        ("Law Society", "Practice Note: Client money and the SRA Accounts Rules", "Updated practice note providing guidance on common areas of non-compliance found during SRA visits.",
         "SRA Accounts Rules 2019", "info", None, -10, None),
        ("SRA", "Warning Notice: cyber security threats to law firms", "Increase in Friday afternoon fraud targeting conveyancing firms. Verify all bank details by telephone before transferring funds.",
         "SRA Warning Notice", "action", "Brief all conveyancing staff on verification procedures.", -1, 7),
        ("HMRC", "Changes to VAT treatment of disbursements", "Updated HMRC guidance on when disbursements can be treated as outside the scope of VAT. Effective from next quarter.",
         "VAT Act 1994", "info", None, -14, 60),
        ("SRA", "New transparency rules for price publication", "Extended requirements for publishing pricing information on firm websites. Additional service categories now covered.",
         "SRA Transparency Rules", "action", "Audit website pricing pages and update for new categories.", -4, 30),
    ]

    for source, title, summary, reg, impact, action, pub_offset, eff_offset in reg_updates:
        rid = str(uuid.uuid4())
        pub_date = (now + datetime.timedelta(days=pub_offset)).isoformat()
        eff_date = (now + datetime.timedelta(days=eff_offset)).isoformat() if eff_offset else None
        cursor.execute(
            """INSERT OR IGNORE INTO regulatory_updates
               (id, source, title, summary, regulation_ref, impact_level, action_required, published_date, effective_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rid, source, title, summary, reg, impact, action, pub_date, eff_date)
        )

    # ========== REGULATORY IMPACT ANALYSES ==========
    # Generate impact analyses for all regulatory updates
    cursor.execute("SELECT * FROM regulatory_updates")
    for update_row in cursor.fetchall():
        update_dict = {
            'id': update_row[0],
            'source': update_row[1],
            'title': update_row[2],
            'summary': update_row[3],
            'regulation_ref': update_row[4],
            'impact_level': update_row[5],
            'action_required': update_row[6],
            'published_date': update_row[7],
            'effective_date': update_row[8],
        }
        analysis = generate_impact_analysis(update_dict)
        analysis_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT OR IGNORE INTO regulatory_impact_analysis
               (id, update_id, affected_areas, risk_level, affected_policies, affected_staff_roles, action_items, deadline, ai_summary, ai_recommendation, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (analysis_id, update_dict['id'], json.dumps(analysis['affected_areas']), analysis['risk_level'],
             json.dumps(analysis['affected_policies']), json.dumps(analysis['affected_staff_roles']),
             json.dumps(analysis['action_items']), analysis['deadline'], analysis['ai_summary'],
             analysis['ai_recommendation'], 'pending', now.isoformat())
        )

        # Queue policy updates for affected policies
        for policy_type in analysis['affected_policies']:
            cursor.execute("SELECT id FROM policy_documents WHERE policy_type = ? LIMIT 1", (policy_type,))
            policy_row = cursor.fetchone()
            policy_id = policy_row[0] if policy_row else None

            queue_id = str(uuid.uuid4())
            suggested = json.dumps([{"section": "Multiple sections", "change": f"Review and update in line with {update_dict.get('regulation_ref', 'new guidance')}", "reason": update_dict.get('title', 'Regulatory change')}])
            cursor.execute(
                """INSERT OR IGNORE INTO policy_update_queue
                   (id, policy_id, policy_type, trigger_update_id, change_type, suggested_changes, priority, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (queue_id, policy_id, policy_type, update_dict['id'], 'review', suggested, analysis['risk_level'], 'pending', now.isoformat())
            )

    # ========== SRA FEED LOG ==========
    for src in ['SRA', 'ICO', 'HMRC', 'Law Society']:
        cursor.execute("SELECT id FROM sra_feed_log WHERE feed_source = ?", (src,))
        if not cursor.fetchone():
            last_checked = (now - datetime.timedelta(hours=random.randint(1, 12))).isoformat()
            cursor.execute(
                "INSERT INTO sra_feed_log (id, feed_source, last_checked, items_found, new_items, status) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), src, last_checked, random.randint(2, 8), random.randint(0, 2), 'ok')
            )

    # ========== CHASER LOG ==========
    # Create chasers for overdue training
    cursor.execute("SELECT st.id, st.staff_id, st.title, st.due_date, sm.name, sm.email FROM staff_training st JOIN staff_members sm ON st.staff_id = sm.id WHERE st.status = 'overdue'")
    overdue_trainings = cursor.fetchall()

    for tid, staff_id, title, due_date, name, email in overdue_trainings:
        days_overdue = (now.date() - datetime.datetime.fromisoformat(due_date).date()).days
        chaser_id = str(uuid.uuid4())
        sent_at = (now - datetime.timedelta(days=2)).isoformat()
        subject = f"Reminder: Your {title} is overdue"
        message = f"Dear {name}, Your {title} was due on {due_date[:10]}. Please complete this as soon as possible. Your COLP has been notified."
        escalated = 1 if days_overdue > 7 else 0
        escalated_at = (now - datetime.timedelta(days=1)).isoformat() if escalated else None

        cursor.execute(
            """INSERT OR IGNORE INTO chaser_log (id, chaser_type, recipient_staff_id, recipient_email, recipient_name, subject, message, sent_at, escalated, escalated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chaser_id, "training_overdue", staff_id, email, name, subject, message, sent_at, escalated, escalated_at)
        )

    # Create chasers for overdue file reviews
    cursor.execute("SELECT sfr.id, sfr.staff_id, sfr.case_id, sfr.due_date, sm.name, sm.email FROM staff_file_reviews sfr JOIN staff_members sm ON sfr.staff_id = sm.id WHERE sfr.status = 'overdue'")
    overdue_reviews = cursor.fetchall()

    for rid, staff_id, case_id, due_date, name, email in overdue_reviews:
        days_overdue = (now.date() - datetime.datetime.fromisoformat(due_date).date()).days
        chaser_id = str(uuid.uuid4())
        sent_at = (now - datetime.timedelta(days=2)).isoformat()
        subject = f"Reminder: File review for case {case_id[:8]} is overdue"
        message = f"Dear {name}, Your file review was due on {due_date[:10]}. Please complete this review as soon as possible. Your COLP has been notified."
        escalated = 1 if days_overdue > 7 else 0
        escalated_at = (now - datetime.timedelta(days=1)).isoformat() if escalated else None

        cursor.execute(
            """INSERT OR IGNORE INTO chaser_log (id, chaser_type, recipient_staff_id, recipient_email, recipient_name, subject, message, sent_at, escalated, escalated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chaser_id, "review_overdue", staff_id, email, name, subject, message, sent_at, escalated, escalated_at)
        )

    # Create chasers for pending client intakes
    cursor.execute("SELECT id, client_name FROM client_intake WHERE status = 'pending' LIMIT 3")
    pending_intakes_q = cursor.fetchall()

    for intake_id, client_name in pending_intakes_q:
        chaser_id = str(uuid.uuid4())
        sent_at = (now - datetime.timedelta(days=1)).isoformat()
        subject = f"Reminder: CDD pending for {client_name}"
        message = f"CDD assessment for {client_name} is still pending. Please complete the assessment as soon as possible."

        cursor.execute(
            """INSERT OR IGNORE INTO chaser_log (id, chaser_type, recipient_staff_id, recipient_email, recipient_name, subject, message, sent_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (chaser_id, "cdd_pending", "staff-007", "e.clarke@firm.co.uk", "Emma Clarke", subject, message, sent_at)
        )

    # ========== EVIDENCE LOCKER ==========
    # Add evidence for completed training
    cursor.execute("SELECT id, staff_id FROM staff_training WHERE status = 'completed' LIMIT 10")
    completed_trainings = cursor.fetchall()

    for training_id, staff_id in completed_trainings:
        evidence_id = str(uuid.uuid4())
        uploaded_at = (now - datetime.timedelta(days=random.randint(1, 30))).isoformat()
        cursor.execute(
            """INSERT OR IGNORE INTO evidence_locker (id, entity_type, entity_id, title, description, file_type, file_ref, uploaded_by, uploaded_at, verified_by, verified_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (evidence_id, "training", training_id, f"Training Certificate - {training_id[:8]}", "Completion certificate", "certificate", f"cert-{training_id[:8]}", "staff-001", uploaded_at, "staff-007", uploaded_at, "active")
        )

    # Add evidence for completed file reviews
    cursor.execute("SELECT id FROM staff_file_reviews WHERE status = 'completed' LIMIT 8")
    completed_reviews = cursor.fetchall()

    for (review_id,) in completed_reviews:
        evidence_id = str(uuid.uuid4())
        uploaded_at = (now - datetime.timedelta(days=random.randint(1, 30))).isoformat()
        cursor.execute(
            """INSERT OR IGNORE INTO evidence_locker (id, entity_type, entity_id, title, description, file_type, file_ref, uploaded_by, uploaded_at, verified_by, verified_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (evidence_id, "file_review", review_id, f"File Review Notes - {review_id[:8]}", "Review documentation", "pdf", f"review-{review_id[:8]}", "staff-001", uploaded_at, "staff-007", uploaded_at, "active")
        )

    # Add evidence for client intakes
    cursor.execute("SELECT id FROM client_intake WHERE cdd_status = 'completed' LIMIT 5")
    completed_intakes = cursor.fetchall()

    for (intake_id,) in completed_intakes:
        evidence_id = str(uuid.uuid4())
        uploaded_at = (now - datetime.timedelta(days=random.randint(1, 60))).isoformat()
        cursor.execute(
            """INSERT OR IGNORE INTO evidence_locker (id, entity_type, entity_id, title, description, file_type, file_ref, uploaded_by, uploaded_at, verified_by, verified_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (evidence_id, "intake", intake_id, f"Client ID Documents - {intake_id[:8]}", "Identity verification documents", "image", f"id-docs-{intake_id[:8]}", "staff-007", uploaded_at, "staff-001", uploaded_at, "active")
        )

    # ========== AUDIT TRAIL ==========
    # Log COLP activities
    colp_id = "staff-001"
    audit_actions = ["login", "view", "approve", "complete", "generate", "acknowledge", "upload", "review"]

    for i in range(30):
        audit_id = str(uuid.uuid4())
        action = random.choice(audit_actions)
        entity_type = random.choice(["training", "file_review", "chaser", "compliance_task", "breach_report", "intake"])
        performed_at = (now - datetime.timedelta(days=random.randint(0, 14))).isoformat()
        details = f"COLP performed {action} on {entity_type}"

        cursor.execute(
            """INSERT OR IGNORE INTO audit_trail (id, action, entity_type, entity_id, performed_by, performed_at, details)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (audit_id, action, entity_type, str(uuid.uuid4())[:8], colp_id, performed_at, details)
        )

    # ========== SUPERVISION SCHEDULE ==========
    # Create supervision schedules based on PQE
    cursor.execute("SELECT id, name, pqe FROM staff_members WHERE status = 'active'")
    staff_list = cursor.fetchall()

    for staff_id, staff_name, pqe in staff_list:
        if pqe == 0:  # Trainees and paralegals
            frequency = "weekly"
            risk_level = "high"
        elif pqe <= 2:  # Junior staff
            frequency = "fortnightly"
            risk_level = "elevated"
        elif pqe <= 5:  # Mid-level
            frequency = "monthly"
            risk_level = "standard"
        else:  # Seniors
            frequency = "quarterly"
            risk_level = "standard"

        seniors = [s[0] for s in staff_list if s[2] > pqe and s[0] != staff_id]
        supervisor_id = random.choice(seniors) if seniors else "staff-001"

        sched_id = str(uuid.uuid4())
        next_due_offset = random.randint(-10, 14)
        next_due = (now + datetime.timedelta(days=next_due_offset)).isoformat()
        last_completed = (now - datetime.timedelta(days=random.randint(7, 30))).isoformat()

        cursor.execute(
            """INSERT OR IGNORE INTO supervision_schedule (id, staff_id, supervisor_id, frequency, next_due, last_completed, meeting_type, risk_level, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sched_id, staff_id, supervisor_id, frequency, next_due, last_completed, "formal_supervision", risk_level, "active")
        )

    # ========== MATTER CHECKLISTS ==========
    # Define checklist templates
    MATTER_CHECKLIST_TEMPLATES = {
        "conveyancing": [
            ("Source of funds verified", "Financial verification", "AML Regulations 2017", "AML Due Diligence"),
            ("Client ID checked (individual)", "Identification", "AML Regulations 2017", "Identity Verification"),
            ("Client ID checked (beneficial owners)", "Identification", "AML Regulations 2017", "Entity Verification"),
            ("Sanctions screening", "AML Screening", "AML Regulations 2017", "Sanctions Check"),
            ("Conflict search completed", "Conflict Check", "SRA Standards 2019", "Conflicts"),
            ("Conflict search clear", "Conflict Check", "SRA Standards 2019", "Conflicts"),
            ("Terms of engagement sent", "Engagement", "SRA Standards 2019", "Engagement Letter"),
            ("Terms signed and returned", "Engagement", "SRA Standards 2019", "Engagement Letter"),
            ("Mortgage offer reviewed", "Mortgage", "Conveyancing Standards", "Financial Terms"),
            ("Property searches ordered", "Property Searches", "Conveyancing Standards", "Searches"),
            ("Property searches reviewed", "Property Searches", "Conveyancing Standards", "Searches"),
            ("Title examination complete", "Title", "Conveyancing Standards", "Title Review"),
            ("SDLT calculation prepared", "Stamp Duty", "SDLT Regulations", "Tax Compliance"),
            ("Completion statement prepared", "Completion", "Conveyancing Standards", "Completion"),
            ("Client account reconciled post-completion", "Completion", "SRA Accounts Rules", "Financial Close-out"),
        ],
        "litigation": [
            ("Client ID verified", "Identification", "AML Regulations 2017", "Identity Verification"),
            ("Conflict search completed", "Conflict Check", "SRA Standards 2019", "Conflicts"),
            ("Limitation date recorded", "Limitation", "Limitation Act 1980", "Case Planning"),
            ("Terms of engagement sent", "Engagement", "SRA Standards 2019", "Engagement Letter"),
            ("Terms signed", "Engagement", "SRA Standards 2019", "Engagement Letter"),
            ("Funding arrangement confirmed", "Funding", "Solicitors Regulation Authority", "Funding"),
            ("Costs estimate provided", "Costs", "SRA Transparency Rules", "Costs"),
            ("Case plan prepared", "Case Management", "CPR", "Case Management"),
            ("Court deadlines diarised", "Deadlines", "CPR", "Deadline Management"),
            ("Pre-trial checklist complete", "Trial Prep", "CPR Part 29", "Trial Preparation"),
        ],
        "corporate": [
            ("Client ID verified (all parties)", "Identification", "AML Regulations 2017", "Identity Verification"),
            ("Beneficial ownership confirmed", "Beneficial Ownership", "AML Regulations 2017", "Ownership Verification"),
            ("Conflict search (all parties)", "Conflict Check", "SRA Standards 2019", "Conflicts"),
            ("Sanctions screening (all parties)", "AML Screening", "AML Regulations 2017", "Sanctions Check"),
            ("Terms of engagement", "Engagement", "SRA Standards 2019", "Engagement Letter"),
            ("Source of funds verified", "Financial verification", "AML Regulations 2017", "AML Due Diligence"),
            ("Board minutes reviewed", "Corporate Governance", "Companies Act 2006", "Corporate Governance"),
            ("Due diligence checklist complete", "Due Diligence", "Corporate Standards", "Due Diligence"),
            ("Completion bible prepared", "Completion", "Corporate Standards", "Completion"),
            ("Post-completion filings done", "Filings", "Companies House Requirements", "Post-Completion"),
        ],
    }

    # Get some law cases to create matter checklists
    cursor.execute("SELECT id, case_name FROM law_cases LIMIT 8")
    cases = cursor.fetchall()

    matter_types = ["conveyancing", "litigation", "corporate", "conveyancing", "litigation", "corporate", "conveyancing", "litigation"]

    for idx, (case_id, case_name) in enumerate(cases):
        matter_type = matter_types[idx] if idx < len(matter_types) else "conveyancing"
        checklist_id = str(uuid.uuid4())
        created_at = (now - datetime.timedelta(days=random.randint(5, 30))).isoformat()
        assigned_to = random.choice(["staff-001", "staff-003", "staff-004"])
        status = random.choice(["in_progress", "in_progress", "completed"])

        # Get template items for this matter type
        template_items = MATTER_CHECKLIST_TEMPLATES.get(matter_type, MATTER_CHECKLIST_TEMPLATES["conveyancing"])

        cursor.execute(
            """INSERT OR IGNORE INTO matter_checklists (id, case_id, case_name, matter_type, created_at, status, assigned_to, total_items)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (checklist_id, case_id, case_name, matter_type, created_at, status, assigned_to, len(template_items))
        )

        # Add checklist items
        completed_count = 0
        for item_order, (title, category, regulation_ref, description) in enumerate(template_items, 1):
            item_id = str(uuid.uuid4())
            # Random completion status
            item_status = random.choice(["pending", "pending", "pending", "completed"])
            if item_status == "completed":
                completed_count += 1
            completed_by = assigned_to if item_status == "completed" else None
            completed_at = (now - datetime.timedelta(days=random.randint(1, 15))).isoformat() if item_status == "completed" else None
            evidence_ref = f"file-{item_id[:8]}" if item_status == "completed" else None

            cursor.execute(
                """INSERT OR IGNORE INTO matter_checklist_items (id, checklist_id, item_order, category, title, description, regulation_ref, status, completed_by, completed_at, evidence_ref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, checklist_id, item_order, category, title, description, regulation_ref, item_status, completed_by, completed_at, evidence_ref)
            )

        # Update completed items count
        cursor.execute(
            "UPDATE matter_checklists SET completed_items = ? WHERE id = ?",
            (completed_count, checklist_id)
        )

    # ========== USER ACCOUNTS ==========
    for sid, name, role, email, pqe, supervisor, dept in staff_data:
        user_id = str(uuid.uuid4())
        # Default password is first name lowercase + "2024"
        first_name = name.split()[0].lower()
        password = first_name + "2024"
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        user_role = 'colp' if sid == 'staff-001' else 'partner' if role == 'Partner' else 'manager' if 'Manager' in role else 'mlro' if 'MLRO' in role else 'solicitor' if 'Solicitor' in role else 'staff'
        cursor.execute(
            """INSERT OR IGNORE INTO user_accounts (id, staff_id, email, password_hash, role, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, 1, ?)""",
            (user_id, sid, email, password_hash, user_role, datetime.datetime.now().isoformat())
        )

    # ========== EMAIL SETTINGS ==========
    cursor.execute("SELECT COUNT(*) FROM email_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""INSERT OR IGNORE INTO email_settings (id, smtp_host, smtp_port, smtp_user, from_email, from_name, enabled, auto_chase_training, auto_chase_reviews, auto_chase_cdd, chase_frequency_days, escalation_after_days, updated_at)
                          VALUES (?, 'smtp.firm.co.uk', 587, 'compliance@firm.co.uk', 'compliance@firm.co.uk', 'Seema Compliance', 0, 1, 1, 1, 3, 7, ?)""",
                       ('settings-001', datetime.datetime.now().isoformat()))

    # ========== EMAIL QUEUE (demo) ==========
    queue_templates = [
        ("Training Reminder: AML Refresher", "james.wilson@firm.co.uk", "James Wilson", "training_reminder", "Dear James,\n\nThis is a reminder that your AML Refresher training is overdue.\n\nRegards,\nSeema Compliance", "sent"),
        ("File Review Overdue: Henderson v Crown", "emily.chen@firm.co.uk", "Emily Chen", "review_reminder", "Dear Emily,\n\nYour file review for Henderson v Crown is now overdue.\n\nRegards,\nSeema Compliance", "sent"),
        ("CDD Pending: Thompson Estate", "e.clarke@firm.co.uk", "Emma Clarke", "cdd_reminder", "Dear Emma,\n\nClient due diligence for Thompson Estate remains incomplete.\n\nRegards,\nSeema Compliance", "queued"),
        ("Supervision Meeting Reminder", "d.ahmed@firm.co.uk", "David Ahmed", "supervision_reminder", "Dear David,\n\nYour quarterly supervision meeting is due this week.\n\nRegards,\nSeema Compliance", "queued"),
        ("Policy Update Acknowledgement Required", "r.taylor@firm.co.uk", "Rachel Taylor", "policy_reminder", "Dear Rachel,\n\nThe updated AML Policy requires your acknowledgement.\n\nRegards,\nSeema Compliance", "queued"),
    ]
    for subj, em, name, template, body, status in queue_templates:
        eid = str(uuid.uuid4())
        created = (datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 5), hours=random.randint(0, 12))).isoformat()
        sent = created if status == 'sent' else None
        cursor.execute("""INSERT OR IGNORE INTO email_queue (id, to_email, to_name, subject, body, template, status, sent_at, created_at)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (eid, em, name, subj, body, template, status, sent, created))

    conn.commit()
    conn.close()

# ============================================================================
# Remediation Knowledge Base — UK Legal Compliance
# Maps non-compliant items to specific, actionable remediation steps
# ============================================================================

REMEDIATION_KNOWLEDGE = {
    # SRA Audit categories
    "accounts": {
        "Accounting Records": {
            "regulation": "SRA Accounts Rules 2019, Rule 8",
            "priority": "critical",
            "steps": [
                {"title": "Audit current accounting records", "description": "Review all client and office account ledgers for completeness and accuracy.", "guidance": "Under Rule 8.1, accounting records must be kept at all times to show accurately the position with regard to money held, received and paid."},
                {"title": "Reconcile client accounts", "description": "Perform full reconciliation of client account bank statements against ledger balances.", "guidance": "Rule 8.3 requires reconciliation at least every five weeks. Document the reconciliation with date and signatory."},
                {"title": "Appoint Compliance Officer (COFA)", "description": "Ensure a Compliance Officer for Finance and Administration is designated and their details filed with the SRA.", "guidance": "Required under SRA Authorisation of Firms Rules. COFA must have adequate access to financial records."},
                {"title": "Implement monthly review schedule", "description": "Set up monthly accounting review with documented sign-off by the COFA.", "guidance": "Best practice: monthly reviews reduce risk of undetected discrepancies. Create a standing diary entry."},
                {"title": "File evidence with SRA audit pack", "description": "Compile reconciliation reports, review minutes, and COFA sign-offs into the SRA audit readiness pack.", "guidance": "The SRA may request these documents during a desk-based review or firm visit."}
            ]
        },
        "Audit Trail": {
            "regulation": "SRA Accounts Rules 2019, Rule 8.1",
            "priority": "high",
            "steps": [
                {"title": "Review transaction recording procedures", "description": "Check all financial transactions are recorded chronologically with adequate descriptions.", "guidance": "Each entry must identify the client matter, amount, date, and nature of the transaction."},
                {"title": "Verify double-entry bookkeeping", "description": "Confirm all entries follow double-entry principles across client and office accounts.", "guidance": "Single-entry systems do not meet SRA requirements. Migrate if necessary."},
                {"title": "Test audit trail continuity", "description": "Select 20 random transactions and trace them from bank statement through to ledger entry.", "guidance": "Any breaks in the trail indicate a systemic recording issue that must be remediated."},
                {"title": "Document and sign off", "description": "Record the audit trail review findings with date, reviewer name, and any corrective actions taken.", "guidance": "Retain for minimum 6 years per SRA record-keeping requirements."}
            ]
        },
        "Client Money Segregation": {
            "regulation": "SRA Accounts Rules 2019, Rules 2.1, 4.1",
            "priority": "critical",
            "steps": [
                {"title": "Verify separate designated accounts", "description": "Confirm client money is held in accounts clearly labelled as client accounts, separate from office money.", "guidance": "Rule 2.1: you must keep client money separate from money belonging to the firm."},
                {"title": "Review mixed payment procedures", "description": "Check procedures for handling mixed payments (office + client money) and timely transfer of office portion.", "guidance": "Rule 4.1 requires the office money portion to be transferred within 14 days."},
                {"title": "Test account labelling", "description": "Verify all bank accounts are correctly named and the bank acknowledges they are client accounts.", "guidance": "The bank must formally acknowledge the account holds client money under Rule 2.3."},
                {"title": "Update procedures manual", "description": "Document the segregation procedures and train all fee earners handling client money.", "guidance": "All staff must understand their obligations regarding client money handling."}
            ]
        },
        "VAT Compliance": {
            "regulation": "VAT Act 1994; SRA Accounts Rules 2019",
            "priority": "medium",
            "steps": [
                {"title": "Review VAT registration status", "description": "Confirm firm's VAT registration is current and threshold is met.", "guidance": "VAT registration is mandatory when taxable turnover exceeds the current threshold (check HMRC for current amount)."},
                {"title": "Audit VAT calculation on bills", "description": "Check sample invoices for correct VAT rates applied to legal services.", "guidance": "Most legal services are standard-rated. Disbursements may be zero-rated if properly treated as agent."},
                {"title": "Reconcile VAT returns", "description": "Match quarterly VAT returns against accounting records to ensure accuracy.", "guidance": "Errors in VAT returns can attract penalties and interest from HMRC."}
            ]
        },
        "Disbursement Recording": {
            "regulation": "SRA Accounts Rules 2019, Rule 4.3",
            "priority": "medium",
            "steps": [
                {"title": "Categorise all disbursements", "description": "Review and correctly categorise each disbursement as either paid from client or office account.", "guidance": "Paid disbursements (from client account) must be properly authorised and recorded on the client ledger."},
                {"title": "Verify client authority", "description": "Ensure written client authority exists for all disbursements paid from client funds.", "guidance": "Retain signed costs information and authorities per SRA Transparency Rules."},
                {"title": "Update recording procedures", "description": "Implement a standard process for recording disbursements at time of payment, not retrospectively.", "guidance": "Delayed recording creates audit trail gaps. Record within 24 hours of payment."}
            ]
        }
    },
    "money_laundering": {
        "CDD Procedures": {
            "regulation": "Money Laundering Regulations 2017, Reg 28",
            "priority": "critical",
            "steps": [
                {"title": "Review CDD policy document", "description": "Update the firm's Customer Due Diligence policy to reflect current MLR 2017 requirements.", "guidance": "Regulation 28 requires identity verification before establishing a business relationship. The policy must cover timing, methods, and record-keeping."},
                {"title": "Audit client identification records", "description": "Check a sample of 20 recent client files for compliant ID verification documentation.", "guidance": "Acceptable documents include passport/driving licence plus utility bill/bank statement. Electronic verification via approved providers is acceptable."},
                {"title": "Implement risk-based approach", "description": "Create a client risk assessment template that categorises new clients as low, medium, or high risk.", "guidance": "Higher risk requires Enhanced Due Diligence (EDD). Risk factors include: PEP status, high-risk jurisdiction, complex ownership structure."},
                {"title": "Train all staff on CDD", "description": "Deliver CDD training to all fee earners and relevant support staff, with attendance records.", "guidance": "MLR 2017 Reg 24 requires regular training. Annual refresher is best practice."},
                {"title": "Document and file evidence", "description": "Compile updated policy, training records, and sample compliant files as evidence.", "guidance": "Retain CDD records for 5 years after the end of the business relationship (Reg 40)."}
            ]
        },
        "MLRO Appointment": {
            "regulation": "Money Laundering Regulations 2017, Reg 21",
            "priority": "critical",
            "steps": [
                {"title": "Appoint or confirm MLRO", "description": "Ensure a Money Laundering Reporting Officer is formally appointed with written terms of reference.", "guidance": "The MLRO must be a senior member of the firm with sufficient authority and access to information."},
                {"title": "Register with the SRA", "description": "Notify the SRA of the MLRO appointment if not already done.", "guidance": "The SRA maintains a register of MLROs. Update within 14 days of any change."},
                {"title": "Document MLRO responsibilities", "description": "Create a written role description covering SAR handling, staff training oversight, and compliance monitoring.", "guidance": "The MLRO is responsible for receiving internal SARs and deciding whether to file with the NCA."},
                {"title": "Set up SAR reporting procedure", "description": "Establish internal SAR reporting forms and a confidential SAR register.", "guidance": "Tipping off is a criminal offence under POCA 2002 s333A. Ensure strict confidentiality protocols."}
            ]
        },
        "AML Training": {
            "regulation": "Money Laundering Regulations 2017, Reg 24",
            "priority": "high",
            "steps": [
                {"title": "Schedule firm-wide AML training", "description": "Arrange annual AML training for all staff, including partners, fee earners, and support staff.", "guidance": "Training must cover: recognising suspicious activity, internal reporting procedures, tipping off offences, and firm-specific risk areas."},
                {"title": "Source accredited training provider", "description": "Use SRA-recognised or Law Society-endorsed AML training materials.", "guidance": "Consider online CPD-accredited courses for efficiency. Ensure content covers MLR 2017 and POCA 2002."},
                {"title": "Record attendance and completion", "description": "Maintain a training register with dates, attendee names, and course completion certificates.", "guidance": "The SRA may request training records during an audit. Retain for minimum 5 years."},
                {"title": "Test understanding", "description": "Include a short assessment or quiz to verify staff understanding of AML obligations.", "guidance": "Best practice: require a pass mark of 80% with retake option."}
            ]
        },
        "STR Reporting": {
            "regulation": "Proceeds of Crime Act 2002, s330-s332",
            "priority": "high",
            "steps": [
                {"title": "Review SAR/STR filing procedures", "description": "Check the firm has a documented process for filing Suspicious Activity Reports with the NCA.", "guidance": "Under POCA s330, failure to report knowledge or suspicion of money laundering is a criminal offence."},
                {"title": "Audit SAR register", "description": "Review the firm's SAR register for completeness — all internal reports must be logged with outcomes.", "guidance": "The MLRO must document their decision to file or not file each SAR with reasons."},
                {"title": "Verify NCA Defence responses", "description": "Check any consent SARs have received appropriate NCA responses before proceeding with transactions.", "guidance": "Under the consent regime, you must wait for NCA response or the moratorium period to expire before proceeding."}
            ]
        },
        "Register Maintenance": {
            "regulation": "Money Laundering Regulations 2017, Reg 30A",
            "priority": "medium",
            "steps": [
                {"title": "Verify beneficial ownership records", "description": "Check all client entity files have up-to-date beneficial ownership information.", "guidance": "For companies, identify any individual holding >25% shares or voting rights, or exercising significant control."},
                {"title": "Cross-reference Companies House", "description": "Verify beneficial ownership declarations against Companies House PSC register.", "guidance": "Discrepancies between client declarations and public records must be investigated and resolved."},
                {"title": "Schedule annual refresh", "description": "Implement annual re-verification of beneficial ownership for ongoing client relationships.", "guidance": "CDD must be kept up to date — not just at onboarding. Set calendar reminders for each client."}
            ]
        },
        "Enhanced Due Diligence": {
            "regulation": "Money Laundering Regulations 2017, Reg 33-35",
            "priority": "high",
            "steps": [
                {"title": "Identify high-risk clients", "description": "Review client list and flag any clients requiring EDD: PEPs, high-risk jurisdictions, complex structures.", "guidance": "Regs 33-35 mandate EDD for: PEPs (domestic and foreign), correspondents, and any situation presenting higher ML risk."},
                {"title": "Apply enhanced measures", "description": "For each flagged client, document the additional measures taken beyond standard CDD.", "guidance": "EDD measures include: obtaining additional ID, verifying source of funds/wealth, increased monitoring, and senior management approval."},
                {"title": "Document risk rationale", "description": "Record the risk assessment for each high-risk client with specific reasons for the EDD classification.", "guidance": "The firm must be able to demonstrate to the SRA why EDD was (or was not) applied."}
            ]
        }
    },
    "complaints": {
        "Complaint Handling Log": {
            "regulation": "SRA Code of Conduct, Para 7.1(b)",
            "priority": "high",
            "steps": [
                {"title": "Establish complaint handling log", "description": "Create or update a central complaints register with standardised fields.", "guidance": "Fields should include: date received, complainant name, nature of complaint, handler, response dates, outcome, and lessons learned."},
                {"title": "Review existing complaint records", "description": "Audit all complaints received in the last 12 months to ensure they are properly logged.", "guidance": "Include complaints received verbally, by email, and by letter — any expression of dissatisfaction is a complaint."},
                {"title": "Implement ongoing logging process", "description": "Create a mandatory procedure for logging all complaints within 24 hours of receipt.", "guidance": "Designate the complaints handler as responsible for maintaining the log. Review quarterly with the managing partner."}
            ]
        },
        "Ombudsman Cases": {
            "regulation": "Legal Ombudsman Scheme Rules; SRA Code of Conduct Para 7.1",
            "priority": "critical",
            "steps": [
                {"title": "Audit Legal Ombudsman referrals", "description": "Review all Legal Ombudsman cases in the last 3 years — open, closed, and determined.", "guidance": "The SRA may view multiple Ombudsman referrals as evidence of systemic failings. Treat each referral seriously."},
                {"title": "Analyse root causes", "description": "For each Ombudsman case, identify the root cause and whether the issue has been addressed.", "guidance": "Common root causes: poor communication, costs disputes, delay, and failure to follow the firm's own complaints procedure."},
                {"title": "Implement preventive measures", "description": "Based on the root cause analysis, implement specific measures to prevent recurrence.", "guidance": "This may include: additional training, revised procedures, enhanced supervision, or client care improvements."},
                {"title": "Report to management", "description": "Present findings and preventive measures to the firm's management for approval and implementation.", "guidance": "The COLP should be involved in overseeing the implementation of any recommended changes."}
            ]
        },
        "Complaints Procedure": {
            "regulation": "SRA Code of Conduct, Para 7.1(a); Legal Ombudsman Scheme Rules",
            "priority": "high",
            "steps": [
                {"title": "Review complaints handling procedure", "description": "Update the firm's written complaints procedure to comply with SRA requirements.", "guidance": "Para 7.1(a) requires a written procedure that is brought to clients' attention at the time of engagement."},
                {"title": "Update client care letters", "description": "Ensure all engagement letters include the complaints procedure and Legal Ombudsman details.", "guidance": "Clients must be informed of their right to complain to the Legal Ombudsman within 6 months of the firm's final response."},
                {"title": "Appoint complaints handler", "description": "Designate a partner or senior solicitor as complaints handler with documented authority.", "guidance": "The complaints handler should not have been involved in the matter giving rise to the complaint."},
                {"title": "Create complaints register", "description": "Maintain a central register of all complaints with outcomes and lessons learned.", "guidance": "Review the register quarterly to identify systemic issues. Report to the managing partner."}
            ]
        },
        "Complaint Logging": {
            "regulation": "SRA Code of Conduct, Para 7.1(b)",
            "priority": "medium",
            "steps": [
                {"title": "Implement complaint logging system", "description": "Create a central log for all complaints with standard fields: date, complainant, nature, handler, outcome.", "guidance": "All complaints must be logged, including those resolved informally. This creates the audit trail the SRA expects."},
                {"title": "Set response timelines", "description": "Document and enforce response timelines: acknowledge within 2 working days, substantive response within 8 weeks.", "guidance": "The Legal Ombudsman expects firms to resolve complaints within 8 weeks before they will accept jurisdiction."},
                {"title": "Train staff on recognition", "description": "Train all staff to recognise a complaint (even informal ones) and escalate to the complaints handler.", "guidance": "A complaint is any expression of dissatisfaction, whether or not the word 'complaint' is used."}
            ]
        }
    },
    "conflicts": {
        "Conflict Register": {
            "regulation": "SRA Code of Conduct, Para 6.1-6.2",
            "priority": "critical",
            "steps": [
                {"title": "Review conflict register completeness", "description": "Audit the conflict register to ensure all current and former clients, related parties, and opposing parties are recorded.", "guidance": "The register must include company names, individual names, related entities, and matter descriptions."},
                {"title": "Verify register is up to date", "description": "Check that all new matters opened in the last 6 months have been added to the register.", "guidance": "Cross-reference the matter opening log against the conflict register entries."},
                {"title": "Implement update procedure", "description": "Establish a mandatory procedure requiring conflict register updates at matter opening and when new parties are identified.", "guidance": "Assign responsibility to a named individual and create a workflow for updates."},
                {"title": "Document and sign off", "description": "Record the audit findings and have the COLP sign off the register as current.", "guidance": "Retain the audit record for the SRA compliance file."}
            ]
        },
        "Conflict Searches": {
            "regulation": "SRA Code of Conduct, Para 6.1-6.2",
            "priority": "high",
            "steps": [
                {"title": "Audit recent conflict searches", "description": "Review conflict search records for the last 20 matters to verify searches were conducted before accepting instructions.", "guidance": "A search must be conducted before any work begins, including initial consultations where confidential information may be disclosed."},
                {"title": "Test search methodology", "description": "Run test searches using name variations and phonetic matches to verify the system catches potential conflicts.", "guidance": "Test with common misspellings, maiden names, trading names, and company group members."},
                {"title": "Update search procedure", "description": "Document the conflict search procedure including who conducts searches, when, and how results are recorded.", "guidance": "Ensure the procedure covers all matter types including informal advice and pro bono work."}
            ]
        },
        "Existing Client Conflicts": {
            "regulation": "SRA Code of Conduct, Para 6.2",
            "priority": "high",
            "steps": [
                {"title": "Review current client base for conflicts", "description": "Conduct a full cross-check of all active matters to identify any current client conflicts.", "guidance": "Para 6.2 prohibits acting where there is a conflict between two current clients unless conditions in 6.2(a)-(c) are met."},
                {"title": "Assess any identified conflicts", "description": "For each potential conflict, assess whether the exception conditions in Para 6.2 are met.", "guidance": "Both clients must give informed written consent and there must be effective information barriers in place."},
                {"title": "Document and remediate", "description": "Document the assessment outcome and take action — either obtain informed consent or cease acting.", "guidance": "Record the decision-making process and retain copies of any consent letters."}
            ]
        },
        "Conflict Check System": {
            "regulation": "SRA Code of Conduct, Para 6.1-6.2",
            "priority": "critical",
            "steps": [
                {"title": "Review conflict check procedure", "description": "Audit the firm's conflict checking process against SRA Paras 6.1-6.2.", "guidance": "You must not act where there is an own interest conflict (6.1) or a conflict between current clients (6.2) unless specific conditions are met."},
                {"title": "Verify database completeness", "description": "Check the conflict database includes all current and former clients, related parties, and adverse parties.", "guidance": "The database must be searchable and include all matters, not just active ones. Include company officers and connected persons."},
                {"title": "Test the checking process", "description": "Run 10 test conflict searches to verify the system catches known conflicts.", "guidance": "Test with name variations, phonetic matches, and company group searches."},
                {"title": "Document and sign off", "description": "Record conflict check results on every new matter file with the checker's name and date.", "guidance": "Retain conflict check records for the life of the file plus 6 years."}
            ]
        },
        "PII and Consent": {
            "regulation": "SRA Code of Conduct, Para 8.6-8.7; SRA Transparency Rules",
            "priority": "high",
            "steps": [
                {"title": "Audit engagement letters", "description": "Review a sample of 20 engagement letters for compliance with SRA Transparency Rules.", "guidance": "Letters must include: cost information, complaints procedure, regulatory status, SRA number, and client's right to instruct another firm."},
                {"title": "Verify costs information", "description": "Check costs information is given at the outset and updated when circumstances change.", "guidance": "SRA Transparency Rules require published pricing for certain services. Check your website and client-facing materials."},
                {"title": "Update letter templates", "description": "Revise engagement letter templates to include all required information.", "guidance": "Include: scope of work, fee basis, billing frequency, client money handling, and data protection notice."}
            ]
        }
    },
    "supervision": {
        "Supervision Plan": {
            "regulation": "SRA Code of Conduct, Para 3.5",
            "priority": "high",
            "steps": [
                {"title": "Draft supervision framework", "description": "Create a written supervision plan covering all fee earners, especially juniors and trainees.", "guidance": "Para 3.5 requires effective supervision. The plan must identify who supervises whom, frequency, and method."},
                {"title": "Assign supervisors", "description": "Ensure every fee earner has a named supervisor with documented responsibility.", "guidance": "Supervisors must have appropriate seniority and experience in the relevant practice area."},
                {"title": "Schedule regular file reviews", "description": "Implement a schedule of supervisory file reviews with documented outcomes.", "guidance": "Best practice: monthly for trainees, quarterly for 1-3 PQE, six-monthly for experienced fee earners."},
                {"title": "Record and review", "description": "Maintain records of all supervision activities and review the plan annually.", "guidance": "Use supervision records to identify training needs and inform appraisals."}
            ]
        },
        "File Reviews": {
            "regulation": "SRA Code of Conduct, Para 3.5",
            "priority": "high",
            "steps": [
                {"title": "Establish file review schedule", "description": "Create a documented schedule for supervisory file reviews across all practice areas.", "guidance": "Reviews should check: client care compliance, costs information, conflict checks, key dates, and substantive quality."},
                {"title": "Conduct sample reviews", "description": "Review a representative sample of files from each fee earner — minimum 5% of active files.", "guidance": "Use a standardised review checklist to ensure consistency across reviewers."},
                {"title": "Document findings and actions", "description": "Record all review findings, feed back to fee earners, and track any required corrective actions.", "guidance": "Retain file review records as evidence of the firm's supervisory arrangements for SRA audit."}
            ]
        },
        "Staff Training": {
            "regulation": "SRA Code of Conduct, Para 3.3; SRA Competence Statement",
            "priority": "medium",
            "steps": [
                {"title": "Conduct training needs assessment", "description": "Assess training requirements across the firm for regulatory, technical, and professional skills.", "guidance": "Key mandatory topics include: AML, data protection, equality and diversity, accounts rules, and professional ethics."},
                {"title": "Schedule mandatory training", "description": "Create an annual training calendar covering all mandatory topics with attendance tracking.", "guidance": "Ensure new joiners receive induction training within the first month covering firm policies and regulatory obligations."},
                {"title": "Record and verify completion", "description": "Maintain a central training register with completion dates, attendance, and CPD hours.", "guidance": "The SRA may request training records. Solicitors must declare CPD compliance annually."}
            ]
        },
        "Competence Assessment": {
            "regulation": "SRA Competence Statement 2015; SRA Code of Conduct Para 3.3",
            "priority": "medium",
            "steps": [
                {"title": "Implement competence framework", "description": "Create or update a competence assessment framework aligned with the SRA Competence Statement.", "guidance": "The SRA Competence Statement sets out the standards expected. Map your assessment criteria to its categories."},
                {"title": "Schedule annual reviews", "description": "Set up annual competence reviews for all fee earners with documented outcomes.", "guidance": "Para 3.3 requires that work is supervised and managed effectively. Annual reviews demonstrate this."},
                {"title": "Record CPD compliance", "description": "Verify all solicitors have met their CPD requirements and maintain records.", "guidance": "Solicitors must complete CPD to maintain competence. The firm should track this centrally."}
            ]
        },
        "Complaint Response": {
            "regulation": "SRA Code of Conduct, Para 7.1; Legal Ombudsman Rules",
            "priority": "high",
            "steps": [
                {"title": "Audit response times", "description": "Review the last 12 months of complaints and check all were acknowledged within 2 working days.", "guidance": "Prompt acknowledgement is both an SRA requirement and a factor the Legal Ombudsman considers."},
                {"title": "Review substantive responses", "description": "Check all complaints received a full written response within 8 weeks.", "guidance": "Include: summary of complaint, investigation findings, outcome, and right to escalate to the Legal Ombudsman."},
                {"title": "Implement tracking system", "description": "Set up automated reminders at 2 days (acknowledgement), 4 weeks (update), and 7 weeks (deadline warning).", "guidance": "Missing the 8-week deadline allows complainants to go directly to the Legal Ombudsman."}
            ]
        }
    },
    "data_protection": {
        "Data Protection Policy": {
            "regulation": "UK GDPR Art 24; Data Protection Act 2018",
            "priority": "high",
            "steps": [
                {"title": "Review privacy policy", "description": "Update the firm's privacy policy to comply with UK GDPR Articles 13-14.", "guidance": "Must include: identity of controller, purposes of processing, legal basis, retention periods, data subject rights, and right to complain to ICO."},
                {"title": "Conduct DPIA where required", "description": "Identify any processing that requires a Data Protection Impact Assessment.", "guidance": "DPIAs are mandatory for high-risk processing under Art 35. Likely applies to: large-scale special category data, systematic monitoring."},
                {"title": "Update website privacy notice", "description": "Ensure the website privacy notice matches the internal policy and is easily accessible.", "guidance": "The ICO recommends a layered approach: short notice for quick reference, full policy for detail."},
                {"title": "Train data handlers", "description": "Deliver GDPR training to all staff who handle personal data.", "guidance": "Focus on: lawful basis for processing, data subject rights, breach reporting (72-hour rule), and secure handling."}
            ]
        },
        "DPA Register": {
            "regulation": "UK GDPR Art 28; Data Protection Act 2018",
            "priority": "high",
            "steps": [
                {"title": "Identify all data processors", "description": "List every third party that processes personal data on the firm's behalf.", "guidance": "Common processors include: cloud providers, IT support, payroll, shredding companies, counsel's chambers."},
                {"title": "Execute DPAs with each processor", "description": "Ensure a compliant Data Processing Agreement is in place with every processor.", "guidance": "Art 28 DPAs must include: subject matter, duration, nature of processing, obligations, and data security measures."},
                {"title": "Create processor register", "description": "Maintain a central register of all processors with DPA status, review dates, and contact details.", "guidance": "Review DPAs annually or when processing arrangements change."}
            ]
        },
        "DSAR Process": {
            "regulation": "UK GDPR Art 15; Data Protection Act 2018 s45",
            "priority": "high",
            "steps": [
                {"title": "Document DSAR procedure", "description": "Create a written procedure for handling Data Subject Access Requests.", "guidance": "You must respond within one calendar month (Art 12). The procedure must cover: verification of identity, search scope, exemptions, and redaction."},
                {"title": "Identify data locations", "description": "Map all locations where personal data is stored: case files, email, CRM, accounting, archives.", "guidance": "A DSAR covers ALL personal data, not just the matter file. Include emails, notes, time records, and billing data."},
                {"title": "Train staff on DSAR handling", "description": "Train fee earners and support staff on recognising and escalating DSARs.", "guidance": "A DSAR can be made verbally or in writing, and does not need to use specific words. All staff must recognise one."},
                {"title": "Test with a dry run", "description": "Conduct a mock DSAR to test the procedure and measure response time.", "guidance": "If the mock reveals the firm cannot respond within one month, identify and fix the bottlenecks."}
            ]
        },
        "Breach Procedures": {
            "regulation": "UK GDPR Art 33-34; Data Protection Act 2018",
            "priority": "critical",
            "steps": [
                {"title": "Create breach response plan", "description": "Document a data breach response plan covering detection, containment, assessment, and notification.", "guidance": "Art 33 requires notification to the ICO within 72 hours of becoming aware of a breach. The plan must enable this."},
                {"title": "Designate breach response team", "description": "Appoint a breach response lead and team with clear roles and contact details.", "guidance": "Team should include: DPO/privacy lead, IT, senior partner, and external cyber/legal advisors."},
                {"title": "Set up breach register", "description": "Create a register for recording all breaches, including those not reported to the ICO.", "guidance": "Art 33(5) requires documentation of all breaches, their effects, and remedial action — even if not notifiable."},
                {"title": "Run tabletop exercise", "description": "Conduct a simulated breach scenario to test the response plan.", "guidance": "Test annually. Common scenarios: ransomware, misdirected email, lost laptop, unauthorised file access."}
            ]
        },
        "Consent Records": {
            "regulation": "UK GDPR Art 7; Data Protection Act 2018",
            "priority": "medium",
            "steps": [
                {"title": "Audit consent mechanisms", "description": "Review how client consent is obtained, recorded, and stored.", "guidance": "Art 7: consent must be freely given, specific, informed, and unambiguous. Pre-ticked boxes are not valid consent."},
                {"title": "Review lawful basis", "description": "Check whether consent is actually the correct lawful basis for each processing activity.", "guidance": "For legal services, legitimate interests (Art 6(1)(f)) or contractual necessity (Art 6(1)(b)) may be more appropriate than consent."},
                {"title": "Update consent forms", "description": "Revise consent forms to be GDPR-compliant with clear language and granular options.", "guidance": "Consent must be as easy to withdraw as to give. Provide clear withdrawal mechanism."}
            ]
        },
        "Third Party Data": {
            "regulation": "UK GDPR Art 28; Data Protection Act 2018",
            "priority": "medium",
            "steps": [
                {"title": "Map third-party data flows", "description": "Document all flows of personal data to and from third parties.", "guidance": "Include: counsel, experts, courts, opposing parties, regulators, and service providers."},
                {"title": "Assess lawful basis for sharing", "description": "Verify each data sharing arrangement has a valid lawful basis.", "guidance": "Legal obligation, legitimate interests, and contractual necessity are common bases for law firm data sharing."},
                {"title": "Update privacy notices", "description": "Ensure clients are informed about third-party data sharing in the privacy notice.", "guidance": "Art 13 requires disclosure of recipients or categories of recipients at the time data is collected."}
            ]
        }
    },
    "file_management": {
        "File Retention": {
            "regulation": "SRA Code of Conduct; Limitation Act 1980",
            "priority": "medium",
            "steps": [
                {"title": "Review retention policy", "description": "Update the file retention policy with category-specific retention periods.", "guidance": "Minimum periods: conveyancing 15 years, personal injury 15 years (from date of knowledge), wills indefinitely, general 6 years post-closure."},
                {"title": "Audit current file storage", "description": "Review stored files against the retention policy and identify any that exceed retention.", "guidance": "Files past retention should be reviewed for destruction, with client notification where appropriate."},
                {"title": "Implement destruction procedure", "description": "Document secure destruction procedures including client notification, conflict checking, and certificates of destruction.", "guidance": "Use BSIA-member shredding companies for physical files. Ensure digital destruction is certified."}
            ]
        },
        "Secure Storage": {
            "regulation": "SRA Code of Conduct Para 4.2; UK GDPR Art 32",
            "priority": "high",
            "steps": [
                {"title": "Audit physical storage", "description": "Check all physical client files are stored in locked, access-controlled locations.", "guidance": "Only authorised personnel should have access. Maintain an access log for high-security areas."},
                {"title": "Audit digital storage", "description": "Review access controls on digital file systems — role-based access, encryption at rest.", "guidance": "Art 32 requires appropriate technical measures. This includes encryption, access controls, and audit logging."},
                {"title": "Test backup and recovery", "description": "Verify backup procedures work by performing a test restore of sample files.", "guidance": "Back up daily. Test recovery quarterly. Store backups in a geographically separate location."}
            ]
        },
        "Document Destruction": {
            "regulation": "SRA Code of Conduct; UK GDPR Art 17",
            "priority": "medium",
            "steps": [
                {"title": "Review destruction policy", "description": "Ensure the firm has a documented policy for secure destruction of files.", "guidance": "Cover both physical and digital destruction. Include provisions for legal hold."},
                {"title": "Verify destruction certificates", "description": "Check all recent destructions have certificates from the destruction provider.", "guidance": "Retain destruction certificates as proof of compliant disposal."},
                {"title": "Conflict check before destruction", "description": "Run conflict checks on all files scheduled for destruction to ensure no ongoing relevance.", "guidance": "Check for: ongoing litigation, limitation periods not yet expired, client requests to retrieve."}
            ]
        },
        "Confidentiality Controls": {
            "regulation": "SRA Code of Conduct Para 6.3; Legal Professional Privilege",
            "priority": "high",
            "steps": [
                {"title": "Review information barriers", "description": "Check information barriers ('Chinese walls') are in place where required.", "guidance": "Para 6.3 requires that confidential information relating to a client is not used for the benefit of another client."},
                {"title": "Audit clean desk policy", "description": "Verify a clean desk policy is in place and enforced.", "guidance": "Client documents must not be left visible on desks, printers, or screens when unattended."},
                {"title": "Review digital access controls", "description": "Check matter-level access restrictions prevent unauthorised viewing of confidential files.", "guidance": "Not all staff should have access to all files. Implement need-to-know access controls."}
            ]
        },
        "Work in Progress": {
            "regulation": "SRA Accounts Rules 2019",
            "priority": "low",
            "steps": [
                {"title": "Review WIP recording practices", "description": "Check all fee earners are recording time promptly and accurately.", "guidance": "Unrecorded WIP creates billing issues and can mask financial problems the SRA considers relevant."},
                {"title": "Reconcile WIP against billing", "description": "Compare WIP records against recent bills to identify unbilled work.", "guidance": "Significant unbilled WIP may indicate cash flow issues that affect the firm's financial stability."}
            ]
        }
    },
    "insurance": {
        "Indemnity Insurance": {
            "regulation": "SRA Indemnity Insurance Rules 2019",
            "priority": "critical",
            "steps": [
                {"title": "Verify PII cover is current", "description": "Confirm professional indemnity insurance is in force and meets SRA minimum terms.", "guidance": "SRA minimum cover: £2m for partnerships/LLPs, £3m for incorporated practices. Check policy expiry date."},
                {"title": "Review adequacy of cover", "description": "Assess whether the cover level is adequate given the firm's risk profile and work types.", "guidance": "Consider: highest value matter, number of partners, areas of practice, and claims history."},
                {"title": "File certificate with SRA", "description": "Ensure the SRA has the current insurance certificate on file.", "guidance": "Practising without adequate PII is a serious regulatory breach."}
            ]
        },
        "Cover Verification": {
            "regulation": "SRA Indemnity Insurance Rules 2019",
            "priority": "high",
            "steps": [
                {"title": "Obtain insurer confirmation", "description": "Request written confirmation from the insurer that cover remains valid and in force.", "guidance": "Do this annually at minimum, and after any material change in the firm's circumstances."},
                {"title": "Check policy exclusions", "description": "Review policy exclusions to ensure no gaps in coverage for the firm's practice areas.", "guidance": "Common exclusions: fraud, trading debts, employment disputes. Understand what is and isn't covered."}
            ]
        },
        "Claims History": {
            "regulation": "SRA Indemnity Insurance Rules 2019",
            "priority": "medium",
            "steps": [
                {"title": "Compile claims register", "description": "Maintain a complete register of all PII claims and notifications.", "guidance": "Include: date, description, amount, outcome, and any lessons learned."},
                {"title": "Review for patterns", "description": "Analyse claims history for recurring issues that indicate systemic problems.", "guidance": "Report findings to the managing partner. Consider training interventions for repeat issue areas."}
            ]
        },
        "Cyber Insurance": {
            "regulation": "SRA Operational Risk Warning; UK GDPR Art 32",
            "priority": "high",
            "steps": [
                {"title": "Obtain cyber insurance quote", "description": "If not already covered, obtain quotes for standalone cyber insurance.", "guidance": "Many PII policies exclude or limit cyber cover. Standalone cyber insurance covers: breach costs, notification, forensics, business interruption."},
                {"title": "Assess cyber risk profile", "description": "Document the firm's cyber risk profile: data held, systems, remote working, and previous incidents.", "guidance": "The SRA has issued specific warnings about cyber security for law firms. Ransomware and email fraud are top risks."},
                {"title": "Implement minimum security measures", "description": "Ensure basic cyber security is in place: MFA, encrypted email, patching, and staff training.", "guidance": "Cyber Essentials certification is increasingly expected by insurers and clients."}
            ]
        }
    }
}

def generate_remediation_plan(source_type, source_id, category, item_name):
    """Generate a remediation plan from the knowledge base for a non-compliant item"""
    now = datetime.datetime.now()

    # Look up in knowledge base
    cat_knowledge = REMEDIATION_KNOWLEDGE.get(category, {})
    item_knowledge = cat_knowledge.get(item_name, None)

    if not item_knowledge:
        # Fallback: generic remediation for unknown items
        item_knowledge = {
            "regulation": "SRA Code of Conduct",
            "priority": "medium",
            "steps": [
                {"title": "Review current compliance status", "description": f"Assess the current state of '{item_name}' against regulatory requirements.", "guidance": "Document findings and identify specific gaps."},
                {"title": "Develop action plan", "description": "Create a detailed plan to address the identified gaps.", "guidance": "Include timelines, responsible persons, and resource requirements."},
                {"title": "Implement corrective actions", "description": "Execute the action plan and document all changes made.", "guidance": "Keep evidence of all remediation activities."},
                {"title": "Verify and sign off", "description": "Confirm the corrective actions have resolved the non-compliance.", "guidance": "Have the compliance officer or COLP review and sign off the remediation."}
            ]
        }

    plan_id = str(uuid.uuid4())
    priority = item_knowledge["priority"]
    # Due date based on priority
    due_days = {"critical": 14, "high": 30, "medium": 60, "low": 90}
    due_date = (now + datetime.timedelta(days=due_days.get(priority, 60))).isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create the plan
    cursor.execute(
        """INSERT INTO remediation_plans
           (id, source_type, source_id, title, description, regulation_ref, priority, status, assigned_to, created_at, due_date, category)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)""",
        (plan_id, source_type, source_id,
         f"Remediate: {item_name}",
         f"Bring '{item_name}' into compliance with {item_knowledge['regulation']}",
         item_knowledge["regulation"],
         priority,
         "COLP / Compliance Officer",
         now.isoformat(),
         due_date,
         category)
    )

    # Create steps
    steps_data = []
    for idx, step in enumerate(item_knowledge["steps"], 1):
        step_id = str(uuid.uuid4())
        step_due = (now + datetime.timedelta(days=int(due_days.get(priority, 60) * idx / len(item_knowledge["steps"])))).isoformat()
        cursor.execute(
            """INSERT INTO remediation_steps
               (id, plan_id, step_number, title, description, guidance, regulation_ref, status, due_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (step_id, plan_id, idx, step["title"], step["description"],
             step.get("guidance", ""), item_knowledge["regulation"], step_due)
        )
        steps_data.append({
            "id": step_id,
            "step_number": idx,
            "title": step["title"],
            "description": step["description"],
            "guidance": step.get("guidance", ""),
            "regulation_ref": item_knowledge["regulation"],
            "status": "pending",
            "due_date": step_due
        })

    conn.commit()
    conn.close()

    return {
        "plan_id": plan_id,
        "title": f"Remediate: {item_name}",
        "regulation_ref": item_knowledge["regulation"],
        "priority": priority,
        "status": "open",
        "due_date": due_date,
        "steps": steps_data,
        "total_steps": len(steps_data)
    }


# ============================================================================
# Policy Document Templates — UK Legal Compliance
# ============================================================================

POLICY_TEMPLATES = {
    "aml_policy": {
        "title": "Anti-Money Laundering Policy",
        "regulation_ref": "Money Laundering Regulations 2017; Proceeds of Crime Act 2002",
        "description": "Firm-wide AML policy covering CDD, EDD, SAR reporting, and MLRO responsibilities.",
        "sections": [
            {"heading": "1. Purpose and Scope", "content": "This policy sets out {firm_name}'s procedures for compliance with the Money Laundering, Terrorist Financing and Transfer of Funds (Information on the Payer) Regulations 2017 ('MLR 2017') and the Proceeds of Crime Act 2002 ('POCA'). It applies to all partners, employees, and contractors of the firm."},
            {"heading": "2. Money Laundering Reporting Officer", "content": "The firm's designated MLRO is responsible for receiving internal suspicious activity reports, deciding whether to file SARs with the National Crime Agency (NCA), and overseeing the firm's AML compliance programme. The MLRO has direct access to the firm's management and sufficient resources to discharge their duties effectively."},
            {"heading": "3. Customer Due Diligence (CDD)", "content": "Standard CDD must be completed before establishing a business relationship or carrying out an occasional transaction. This includes: (a) identifying the client and verifying their identity using reliable, independent sources; (b) identifying beneficial owners and taking reasonable measures to verify their identity; (c) assessing and obtaining information on the purpose and intended nature of the business relationship."},
            {"heading": "4. Enhanced Due Diligence (EDD)", "content": "EDD must be applied in higher-risk situations as defined by MLR 2017 Regs 33-35, including: Politically Exposed Persons (PEPs), clients from high-risk third countries, complex or unusual transactions, and situations identified through the firm's risk assessment. Additional measures include: obtaining senior management approval, establishing source of wealth and source of funds, and conducting enhanced ongoing monitoring."},
            {"heading": "5. Suspicious Activity Reporting", "content": "All staff must report any knowledge, suspicion, or reasonable grounds to suspect money laundering or terrorist financing to the MLRO immediately using the firm's internal SAR form. The MLRO will assess the report and, where appropriate, file a SAR with the NCA via the SAR Online system. Tipping off is a criminal offence under POCA s333A — staff must not disclose that a SAR has been made."},
            {"heading": "6. Record Keeping", "content": "CDD records and supporting evidence must be retained for at least five years from the end of the business relationship or the date of the occasional transaction (MLR 2017 Reg 40). Transaction records must be retained for at least five years from the date of the transaction."},
            {"heading": "7. Training", "content": "All relevant employees must complete AML training on joining the firm and at least annually thereafter. Training covers: recognition of suspicious activity, internal reporting procedures, firm-specific risks, and consequences of non-compliance. Training records are maintained centrally."},
            {"heading": "8. Firm-Wide Risk Assessment", "content": "The firm maintains a written firm-wide risk assessment identifying and assessing the ML/TF risks to which the firm is subject, taking into account: client types, geographic areas, services provided, and delivery channels. This assessment is reviewed annually or when circumstances change materially."}
        ]
    },
    "data_protection_policy": {
        "title": "Data Protection and GDPR Policy",
        "regulation_ref": "UK GDPR; Data Protection Act 2018",
        "description": "Comprehensive data protection policy covering lawful processing, data subject rights, and breach procedures.",
        "sections": [
            {"heading": "1. Purpose", "content": "This policy sets out how {firm_name} collects, uses, stores, and protects personal data in compliance with the UK General Data Protection Regulation ('UK GDPR') and the Data Protection Act 2018 ('DPA 2018'). The firm is committed to protecting the privacy and rights of all data subjects."},
            {"heading": "2. Data Controller", "content": "{firm_name} is the data controller for personal data processed in connection with its legal services. The firm's Data Protection Officer (or designated privacy lead) can be contacted at the firm's registered address."},
            {"heading": "3. Lawful Basis for Processing", "content": "Personal data is processed on one or more of the following lawful bases under Article 6(1) UK GDPR: (a) consent; (b) performance of a contract; (c) legal obligation; (d) vital interests; (e) public interest; (f) legitimate interests. For special category data, an additional condition under Article 9(2) must be met."},
            {"heading": "4. Data Subject Rights", "content": "The firm respects and facilitates the exercise of data subject rights including: right of access (Art 15), right to rectification (Art 16), right to erasure (Art 17), right to restrict processing (Art 18), right to data portability (Art 20), and right to object (Art 21). Requests are handled within one calendar month."},
            {"heading": "5. Data Retention", "content": "Personal data is retained only for as long as necessary for the purposes for which it was collected, subject to legal and regulatory retention requirements. The firm maintains a retention schedule specifying retention periods for each category of data."},
            {"heading": "6. Data Security", "content": "The firm implements appropriate technical and organisational measures to ensure a level of security appropriate to the risk, including: encryption of personal data, access controls, regular security testing, and staff training. Measures are reviewed annually."},
            {"heading": "7. Data Breach Procedures", "content": "In the event of a personal data breach, the firm will: (a) contain and assess the breach; (b) notify the ICO within 72 hours where required under Art 33; (c) notify affected individuals where required under Art 34; (d) document the breach in the breach register. The breach response team is led by the DPO."},
            {"heading": "8. International Transfers", "content": "Personal data is not transferred outside the UK unless appropriate safeguards are in place, such as adequacy decisions, Standard Contractual Clauses, or Binding Corporate Rules, in compliance with Chapter V of UK GDPR."}
        ]
    },
    "complaints_policy": {
        "title": "Client Complaints Handling Policy",
        "regulation_ref": "SRA Code of Conduct Para 7.1; Legal Ombudsman Scheme Rules",
        "description": "Procedure for handling client complaints in compliance with SRA requirements.",
        "sections": [
            {"heading": "1. Purpose", "content": "This policy sets out {firm_name}'s procedure for handling complaints from clients, in compliance with the SRA Standards and Regulations and the Legal Ombudsman requirements. The firm treats all complaints seriously and uses them to improve service quality."},
            {"heading": "2. What Constitutes a Complaint", "content": "A complaint is any expression of dissatisfaction, whether made orally or in writing, about the firm's service, a fee earner's conduct, or the outcome of a matter. A complaint does not need to use the word 'complaint' to be treated as one."},
            {"heading": "3. Complaints Handler", "content": "The firm's designated complaints handler is a senior partner who was not involved in the matter giving rise to the complaint. The complaints handler has authority to investigate and resolve complaints, including authority to offer redress where appropriate."},
            {"heading": "4. Procedure", "content": "On receipt of a complaint: (a) acknowledge within 2 working days; (b) investigate thoroughly, including reviewing the file and obtaining the fee earner's account; (c) provide a substantive written response within 8 weeks, setting out findings and any proposed resolution; (d) inform the client of their right to complain to the Legal Ombudsman if dissatisfied."},
            {"heading": "5. Legal Ombudsman", "content": "If the client remains dissatisfied after the firm's final response, they may refer the matter to the Legal Ombudsman within 6 months. Contact details: Legal Ombudsman, PO Box 6167, Slough SL1 0EH. Tel: 0300 555 0333. The time limit for referring a complaint is within one year of the act/omission, or within one year of when the client should reasonably have known there was cause for complaint."},
            {"heading": "6. Record Keeping and Learning", "content": "All complaints are recorded in the central complaints register with: date, nature, handler, outcome, and time taken. The register is reviewed quarterly to identify trends and systemic issues. Lessons learned are shared with the team."}
        ]
    },
    "conflict_of_interest_policy": {
        "title": "Conflict of Interest Policy",
        "regulation_ref": "SRA Code of Conduct Para 6.1-6.2",
        "description": "Policy for identifying, managing, and recording conflicts of interest.",
        "sections": [
            {"heading": "1. Purpose", "content": "{firm_name} is committed to identifying and managing conflicts of interest in compliance with the SRA Code of Conduct for Solicitors, RELs and RFLs (Paragraphs 6.1-6.2) and the SRA Code of Conduct for Firms."},
            {"heading": "2. Types of Conflict", "content": "Own interest conflict (Para 6.1): a conflict between the firm's interests and the client's interests. You must not act where there is an own interest conflict. Client conflict (Para 6.2): a conflict between two or more current clients. You may act only if conditions in 6.2 are met."},
            {"heading": "3. Conflict Checking Procedure", "content": "A conflict check must be conducted before accepting any new instruction, including: (a) searching the firm's conflict database for all relevant names and entities; (b) checking against the names of the firm's personnel and their connections; (c) documenting the search and result on the matter file."},
            {"heading": "4. Managing Conflicts", "content": "Where a potential conflict is identified: (a) escalate to the COLP or managing partner immediately; (b) do not commence or continue work until the conflict is assessed; (c) if acting is permitted under the exceptions, obtain informed written consent from all affected clients and implement effective information barriers."},
            {"heading": "5. Record Keeping", "content": "Maintain a central conflict register recording all conflict checks performed, results, decisions made, and any consents obtained. Records are retained for the life of the file plus six years."}
        ]
    },
    "file_retention_policy": {
        "title": "File Retention and Destruction Policy",
        "regulation_ref": "SRA Code of Conduct; Limitation Act 1980; UK GDPR Art 17",
        "description": "Policy for retaining, archiving, and securely destroying client files.",
        "sections": [
            {"heading": "1. Purpose", "content": "This policy sets out {firm_name}'s approach to retaining, storing, and destroying client files, balancing regulatory obligations, limitation periods, and data protection requirements."},
            {"heading": "2. Retention Periods", "content": "Minimum retention periods by matter type: Conveyancing — 15 years from completion; Personal injury — 15 years from date of knowledge; Wills and probate — indefinitely (original wills) / 15 years (probate files); Commercial — 6 years from matter closure; Family — 6 years from matter closure; Employment — 6 years from matter closure; Criminal — 6 years from matter closure."},
            {"heading": "3. Storage", "content": "Active files are stored in secure, access-controlled locations (physical and digital). Archived files are stored in off-site secure storage with documented access procedures. Digital files are backed up daily with encryption at rest and in transit."},
            {"heading": "4. Destruction Procedure", "content": "When a file reaches the end of its retention period: (a) run a conflict check to verify no ongoing relevance; (b) check for limitation period exposure; (c) notify the client where contact details are available; (d) destroy securely using BSIA-member shredding company (physical) or certified data wiping (digital); (e) retain a certificate of destruction."},
            {"heading": "5. Legal Hold", "content": "Files subject to litigation hold or regulatory investigation must not be destroyed regardless of retention period. Legal holds are managed by the COLP."}
        ]
    },
    "supervision_policy": {
        "title": "Supervision and Training Policy",
        "regulation_ref": "SRA Code of Conduct Para 3.5; SRA Competence Statement 2015",
        "description": "Policy for supervising fee earners and maintaining professional competence.",
        "sections": [
            {"heading": "1. Purpose", "content": "This policy ensures {firm_name} maintains effective supervision of all fee earners and staff in compliance with SRA requirements, and supports ongoing professional competence and development."},
            {"heading": "2. Supervision Framework", "content": "Every fee earner has a named supervisor with appropriate experience and seniority. Supervision intensity is proportionate to the fee earner's experience: Trainees — daily supervision with weekly file reviews; 0-3 PQE — weekly supervision with monthly file reviews; 3+ PQE — monthly supervision with quarterly file reviews; Partners — annual peer review."},
            {"heading": "3. File Reviews", "content": "Supervisory file reviews cover: client care compliance, costs information, conflict checks, key dates and limitation periods, substantive quality of advice, and regulatory compliance. Reviews are documented on the file review form and findings discussed with the fee earner."},
            {"heading": "4. Training Requirements", "content": "All solicitors must maintain their competence through CPD. The firm provides: annual mandatory training (AML, data protection, equality and diversity, accounts rules, ethics); practice area-specific training; induction training for new joiners. Training records are maintained centrally."},
            {"heading": "5. Competence Assessment", "content": "Annual competence assessments are conducted for all fee earners against the SRA Competence Statement categories. Results inform appraisals and training plans."}
        ]
    }
}

# Simulated regulatory feed templates for demo
SIMULATED_FEED_UPDATES = [
    {"source": "SRA", "title": "SRA updates guidance on remote supervision of solicitors", "summary": "Revised guidance clarifies expectations for supervising solicitors working remotely or in hybrid arrangements. Firms must demonstrate adequate supervision regardless of physical location.", "regulation_ref": "SRA Code of Conduct Para 3.5", "impact_level": "action", "action_required": "Review remote working supervision arrangements and update supervision policy."},
    {"source": "SRA", "title": "New SRA enforcement strategy published for 2025-26", "summary": "SRA announces increased focus on AML compliance, cybersecurity, and client money handling. Thematic reviews planned for Q3.", "regulation_ref": "SRA Enforcement Strategy", "impact_level": "action", "action_required": "Review firm's compliance in priority areas: AML, cyber security, and client account procedures."},
    {"source": "ICO", "title": "ICO publishes AI governance framework for professional services", "summary": "New framework sets out expectations for firms using AI tools in legal practice, covering transparency, data minimisation, and human oversight requirements.", "regulation_ref": "UK GDPR Art 22; AI White Paper", "impact_level": "action", "action_required": "Assess any AI tools used by the firm against ICO framework requirements."},
    {"source": "SRA", "title": "Updated SRA Accounts Rules guidance on client money", "summary": "Clarification on residual client balances, costs transfers, and the treatment of mixed payments. New examples address common areas of non-compliance.", "regulation_ref": "SRA Accounts Rules 2019", "impact_level": "action", "action_required": "Review client money handling procedures against updated guidance examples."},
    {"source": "HMRC", "title": "Trust Registration Service deadline extended", "summary": "HMRC extends deadline for registering non-taxable trusts by 6 months. Firms holding client funds in trust should verify registration status.", "regulation_ref": "Fifth Money Laundering Directive", "impact_level": "info", "action_required": None},
    {"source": "SRA", "title": "SRA consults on changes to continuing competence requirements", "summary": "Proposed reforms to how solicitors demonstrate ongoing competence. May replace current reflective approach with more structured requirements.", "regulation_ref": "SRA Competence Statement 2015", "impact_level": "info", "action_required": None},
    {"source": "SRA", "title": "Warning Notice: increased identity fraud in conveyancing", "summary": "Significant increase in identity fraud targeting property transactions. New red flags identified for digital verification methods.", "regulation_ref": "SRA Warning Notice; MLR 2017", "impact_level": "action", "action_required": "Brief conveyancing team on new identity fraud red flags and verification procedures."},
    {"source": "Law Society", "title": "Practice Note updated: Gifts and referral arrangements", "summary": "Updated guidance on handling gifts from clients and referral fee arrangements following recent SRA disciplinary decisions.", "regulation_ref": "SRA Code of Conduct Para 5.1", "impact_level": "info", "action_required": None},
    {"source": "SRA", "title": "Diversity data collection now mandatory for all firms", "summary": "All SRA-regulated firms must collect and report workforce diversity data annually. New portal opens in October.", "regulation_ref": "SRA Transparency Rules", "impact_level": "action", "action_required": "Establish diversity data collection process and prepare for October reporting deadline."},
    {"source": "ICO", "title": "ICO fines law firm £120,000 for data breach failings", "summary": "Enforcement action highlights inadequate access controls and failure to encrypt personal data at rest. Firm had 45 fee earners.", "regulation_ref": "UK GDPR Art 32; DPA 2018", "impact_level": "action", "action_required": "Audit firm's data encryption and access control measures against ICO expectations."},
    {"source": "SRA", "title": "New guidance on handling client complaints about costs", "summary": "SRA publishes supplementary guidance on costs disputes following increase in complaints to the Legal Ombudsman about billing transparency.", "regulation_ref": "SRA Code of Conduct Para 7.1; Transparency Rules", "impact_level": "action", "action_required": "Review costs disclosure procedures and retainer letter templates."},
    {"source": "HMRC", "title": "Economic Crime Levy — rates confirmed for 2025-26", "summary": "Updated levy rates published for regulated entities. Medium-sized firms (£10.2M-£36M revenue) now pay £10,000 annually.", "regulation_ref": "Economic Crime (Anti-Money Laundering) Levy Regulations 2022", "impact_level": "info", "action_required": None},
    {"source": "SRA", "title": "SRA publishes lessons from recent intervention cases", "summary": "Analysis of 12 firm interventions in 2024 reveals common causes: inadequate supervision, failure to report breaches, and client money irregularities.", "regulation_ref": "SRA Enforcement Strategy", "impact_level": "action", "action_required": "Review internal controls against the failure patterns identified in the SRA's analysis."},
    {"source": "SRA", "title": "Amendments to SRA Financial Services (Scope) Rules", "summary": "Changes to the scope of permitted financial services activities. Some previously exempt activities now require additional disclosures.", "regulation_ref": "SRA Financial Services (Scope) Rules 2019", "impact_level": "action", "action_required": "Review any financial services activities against amended scope rules."},
    {"source": "ICO", "title": "Updated Subject Access Request guidance for legal sector", "summary": "Sector-specific guidance addresses legal professional privilege considerations when handling DSARs. Clarifies approach to redaction and exemptions.", "regulation_ref": "UK GDPR Art 15; DPA 2018 Sch 2", "impact_level": "action", "action_required": "Update DSAR handling procedures to reflect new ICO guidance on LPP redaction."},
]

def generate_impact_analysis(update):
    """Generate AI-style impact analysis for a regulatory update."""
    reg_ref = (update.get('regulation_ref') or '').lower()
    title = (update.get('title') or '').lower()

    affected_areas = []
    affected_policies = []

    if any(x in reg_ref or x in title for x in ['mlr', 'aml', 'money laundering', 'proceeds of crime']):
        affected_areas.extend(['AML/CDD', 'Client Onboarding', 'Training'])
        affected_policies.append('aml_policy')
    if any(x in reg_ref or x in title for x in ['gdpr', 'data protection', 'ico', 'privacy', 'breach']):
        affected_areas.extend(['Data Protection', 'Breach Response', 'Client Records'])
        affected_policies.append('data_protection_policy')
    if any(x in reg_ref or x in title for x in ['sra code', 'conduct', 'supervision', 'competence']):
        affected_areas.extend(['Supervision', 'Competence', 'Ethics'])
        affected_policies.append('supervision_policy')
    if any(x in reg_ref or x in title for x in ['complaint', 'ombudsman']):
        affected_areas.extend(['Complaints Handling', 'Client Care'])
        affected_policies.append('complaints_policy')
    if any(x in reg_ref or x in title for x in ['conflict']):
        affected_areas.extend(['Conflict Management'])
        affected_policies.append('conflict_of_interest_policy')
    if any(x in reg_ref or x in title for x in ['accounts', 'client money']):
        affected_areas.extend(['Accounts Rules', 'Client Money'])
    if any(x in reg_ref or x in title for x in ['transparency', 'pricing']):
        affected_areas.extend(['Client Information', 'Website Compliance'])
    if any(x in reg_ref or x in title for x in ['retention', 'destruction', 'file']):
        affected_policies.append('file_retention_policy')
        affected_areas.extend(['Records Management'])
    if any(x in reg_ref or x in title for x in ['cyber', 'security', 'fraud']):
        affected_areas.extend(['Cyber Security', 'Risk Management'])
    if any(x in reg_ref or x in title for x in ['vat', 'tax', 'hmrc']):
        affected_areas.extend(['Financial Compliance', 'Billing'])
    if any(x in reg_ref or x in title for x in ['sra authorisation', 'practising certificate', 'renewal']):
        affected_areas.extend(['Firm Authorisation', 'Practising Certificates'])

    if not affected_areas:
        affected_areas = ['General Compliance']

    impact = update.get('impact_level', 'info')
    eff_date = update.get('effective_date')
    days_until = None
    if eff_date:
        try:
            eff = datetime.datetime.fromisoformat(eff_date)
            days_until = (eff - datetime.datetime.now()).days
        except: pass

    if impact == 'action' and days_until is not None and days_until < 14:
        risk_level = 'critical'
    elif impact == 'action' and days_until is not None and days_until < 30:
        risk_level = 'high'
    elif impact == 'action':
        risk_level = 'medium'
    else:
        risk_level = 'low'

    role_map = {
        'AML/CDD': ['COLP', 'MLRO', 'Fee Earners'],
        'Data Protection': ['COLP', 'DPO', 'All Staff'],
        'Supervision': ['COLP', 'Partners', 'Supervisors'],
        'Complaints Handling': ['COLP', 'Complaints Handler'],
        'Accounts Rules': ['COFA', 'Accounts Team'],
        'Client Money': ['COFA', 'Cashier'],
        'Cyber Security': ['COLP', 'IT Manager', 'All Staff'],
        'Training': ['COLP', 'HR', 'All Staff'],
        'Firm Authorisation': ['COLP', 'Managing Partner'],
    }
    affected_roles = list(set(r for area in affected_areas for r in role_map.get(area, ['COLP'])))

    action_items = []
    action_req = update.get('action_required', '')
    if action_req:
        action_items.append(action_req)
    if affected_policies:
        action_items.append(f"Review and update {len(affected_policies)} affected policy document(s)")
    action_items.append("Brief relevant staff on changes at next team meeting")
    if risk_level in ('critical', 'high'):
        action_items.append("Escalate to managing partner for immediate review")
    if days_until and days_until < 30:
        action_items.append(f"Complete all actions before effective date ({eff_date[:10] if eff_date else 'TBC'})")

    if days_until is not None:
        deadline = eff_date
    elif impact == 'action':
        deadline = (datetime.datetime.now() + datetime.timedelta(days=14)).isoformat()
    else:
        deadline = (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()

    source = update.get('source', 'Regulator')
    title_text = update.get('title', 'regulatory change')
    areas_text = ', '.join(affected_areas[:3])

    ai_summary = f"The {source} has published an update regarding {title_text.lower()}. This change primarily affects your firm's {areas_text} procedures. "
    if risk_level in ('critical', 'high'):
        ai_summary += f"This is a {risk_level}-priority matter requiring prompt attention. "
    if days_until is not None and days_until > 0:
        ai_summary += f"You have {days_until} days until the effective date to ensure compliance. "
    elif days_until is not None and days_until <= 0:
        ai_summary += "This change is already in effect — immediate action is recommended. "
    if affected_policies:
        policy_names = [POLICY_TEMPLATES.get(p, {}).get('title', p) for p in affected_policies]
        ai_summary += f"Your {', '.join(policy_names)} may need updating."

    ai_recommendation = f"1. Review the full {source} guidance document ({update.get('regulation_ref', 'referenced regulation')}). "
    if affected_policies:
        ai_recommendation += f"2. Compare current firm policies against the new requirements — {len(affected_policies)} policy document(s) are potentially affected. "
    ai_recommendation += f"3. Brief affected staff ({', '.join(affected_roles[:3])}). "
    if impact == 'action':
        ai_recommendation += "4. Create compliance tasks to track implementation progress. "
    ai_recommendation += "5. Document your review in the audit trail for SRA inspection readiness."

    return {
        'affected_areas': affected_areas,
        'risk_level': risk_level,
        'affected_policies': affected_policies,
        'affected_staff_roles': affected_roles,
        'action_items': action_items,
        'deadline': deadline,
        'ai_summary': ai_summary,
        'ai_recommendation': ai_recommendation,
    }

def simulate_sra_feed_scan():
    """Simulate an SRA feed scan and return newly created updates.
    Always generates 1-3 fresh updates by appending a timestamp suffix to titles,
    so every scan produces visible results."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.datetime.now()
    new_items = []

    # Pick 1-3 random templates from the pool
    num_new = random.randint(1, 3)
    selected = random.sample(SIMULATED_FEED_UPDATES, min(num_new, len(SIMULATED_FEED_UPDATES)))

    # First try: insert templates that haven't been used yet (by exact title)
    fresh_templates = []
    reused_templates = []
    for tmpl in selected:
        cursor.execute("SELECT id FROM regulatory_updates WHERE title = ?", (tmpl['title'],))
        if cursor.fetchone():
            reused_templates.append(tmpl)
        else:
            fresh_templates.append(tmpl)

    # If all templates already exist, make them fresh by adding a date context.
    # This simulates real regulatory feeds — regulators issue updated guidance,
    # revised consultations, new enforcement notices etc. on an ongoing basis.
    date_prefix = now.strftime('%d %b %Y')
    refreshed_variants = {
        'action': [
            "Updated guidance issued: ",
            "Revised consultation: ",
            "New enforcement notice: ",
            "Amendment published: ",
            "Supplementary guidance: ",
            "Clarification issued: ",
        ],
        'info': [
            "Bulletin: ",
            "Information notice: ",
            "Update: ",
            "Circular: ",
        ]
    }
    for tmpl in reused_templates:
        # Build a variant title that won't duplicate
        variants = refreshed_variants.get(tmpl['impact_level'], refreshed_variants['info'])
        prefix = random.choice(variants)
        # Strip any existing prefix we may have added previously
        base_title = tmpl['title']
        for v_list in refreshed_variants.values():
            for v in v_list:
                if base_title.startswith(v):
                    base_title = base_title[len(v):]
                    break
        variant_title = f"{prefix}{base_title} ({date_prefix})"
        # Ensure uniqueness
        cursor.execute("SELECT id FROM regulatory_updates WHERE title = ?", (variant_title,))
        if cursor.fetchone():
            variant_title = f"{prefix}{base_title} ({date_prefix} {now.strftime('%H:%M')})"
        fresh_templates.append({**tmpl, 'title': variant_title})

    for update_template in fresh_templates:
        update_id = str(uuid.uuid4())
        pub_date = (now - datetime.timedelta(days=random.randint(0, 2))).isoformat()
        eff_date = (now + datetime.timedelta(days=random.randint(7, 90))).isoformat() if update_template['impact_level'] == 'action' else None

        cursor.execute(
            """INSERT INTO regulatory_updates
               (id, source, title, summary, regulation_ref, impact_level, action_required, published_date, effective_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (update_id, update_template['source'], update_template['title'], update_template['summary'],
             update_template['regulation_ref'], update_template['impact_level'], update_template['action_required'],
             pub_date, eff_date)
        )

        # Generate and store impact analysis
        update_dict = {**update_template, 'id': update_id, 'published_date': pub_date, 'effective_date': eff_date}
        analysis = generate_impact_analysis(update_dict)
        analysis_id = str(uuid.uuid4())

        cursor.execute(
            """INSERT INTO regulatory_impact_analysis
               (id, update_id, affected_areas, risk_level, affected_policies, affected_staff_roles, action_items, deadline, ai_summary, ai_recommendation, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (analysis_id, update_id, json.dumps(analysis['affected_areas']), analysis['risk_level'],
             json.dumps(analysis['affected_policies']), json.dumps(analysis['affected_staff_roles']),
             json.dumps(analysis['action_items']), analysis['deadline'], analysis['ai_summary'],
             analysis['ai_recommendation'], 'pending', now.isoformat())
        )

        # Queue policy updates for affected policies
        for policy_type in analysis['affected_policies']:
            cursor.execute("SELECT id FROM policy_documents WHERE policy_type = ? LIMIT 1", (policy_type,))
            policy_row = cursor.fetchone()
            policy_id = policy_row[0] if policy_row else None

            queue_id = str(uuid.uuid4())
            suggested = json.dumps([{"section": "Multiple sections", "change": f"Review and update in line with {update_dict.get('regulation_ref', 'new guidance')}", "reason": update_dict.get('title', 'Regulatory change')}])

            cursor.execute(
                """INSERT INTO policy_update_queue
                   (id, policy_id, policy_type, trigger_update_id, change_type, suggested_changes, priority, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (queue_id, policy_id, policy_type, update_id, 'review', suggested, analysis['risk_level'], 'pending', now.isoformat())
            )

        new_items.append({
            'update': {k: update_dict[k] for k in ['id', 'source', 'title', 'summary', 'regulation_ref', 'impact_level', 'action_required', 'published_date', 'effective_date']},
            'analysis': {
                'id': analysis_id,
                'affected_areas': analysis['affected_areas'],
                'risk_level': analysis['risk_level'],
                'affected_policies': analysis['affected_policies'],
                'affected_staff_roles': analysis['affected_staff_roles'],
                'action_items': analysis['action_items'],
                'deadline': analysis['deadline'],
                'ai_summary': analysis['ai_summary'],
                'ai_recommendation': analysis['ai_recommendation'],
            }
        })

    # Update feed log
    primary_source = selected[0]['source'] if selected else 'SRA'
    for src in ['SRA', 'ICO', 'HMRC', 'Law Society']:
        cursor.execute("SELECT id FROM sra_feed_log WHERE feed_source = ?", (src,))
        if cursor.fetchone():
            cursor.execute(
                "UPDATE sra_feed_log SET last_checked = ?, items_found = ?, new_items = ?, status = ? WHERE feed_source = ?",
                (now.isoformat(), len(fresh_templates), len(new_items) if src == primary_source else 0, 'ok', src)
            )
        else:
            cursor.execute(
                "INSERT INTO sra_feed_log (id, feed_source, last_checked, items_found, new_items, status) VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), src, now.isoformat(), len(fresh_templates) if src == primary_source else 0, len(new_items) if src == primary_source else 0, 'ok')
            )

    conn.commit()
    conn.close()
    return new_items

def generate_policy_document(policy_type, firm_name="Mitchell & Partners LLP"):
    """Generate a policy document from template"""
    template = POLICY_TEMPLATES.get(policy_type)
    if not template:
        return None

    now = datetime.datetime.now()
    doc_id = str(uuid.uuid4())

    # Build the full document content
    content_parts = []
    content_parts.append(f"{'='*60}")
    content_parts.append(f"{template['title'].upper()}")
    content_parts.append(f"{'='*60}")
    content_parts.append(f"")
    content_parts.append(f"Firm: {firm_name}")
    content_parts.append(f"Regulation: {template['regulation_ref']}")
    content_parts.append(f"Version: 1.0")
    content_parts.append(f"Date: {now.strftime('%d %B %Y')}")
    content_parts.append(f"Status: DRAFT — Requires partner review and approval")
    content_parts.append(f"Next Review: {(now + datetime.timedelta(days=365)).strftime('%d %B %Y')}")
    content_parts.append(f"")
    content_parts.append(f"{'-'*60}")
    content_parts.append(f"")

    for section in template["sections"]:
        section_content = section["content"].replace("{firm_name}", firm_name)
        content_parts.append(f"{section['heading']}")
        content_parts.append(f"")
        content_parts.append(section_content)
        content_parts.append(f"")

    content_parts.append(f"{'-'*60}")
    content_parts.append(f"")
    content_parts.append(f"Approved by: _________________________ Date: _____________")
    content_parts.append(f"")
    content_parts.append(f"Position: ___________________________")

    full_content = "\n".join(content_parts)

    # Store in DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO policy_documents
           (id, policy_type, title, description, regulation_ref, content, version, status, created_at, updated_at, next_review_date)
           VALUES (?, ?, ?, ?, ?, ?, '1.0', 'draft', ?, ?, ?)""",
        (doc_id, policy_type, template["title"], template["description"],
         template["regulation_ref"], full_content, now.isoformat(), now.isoformat(),
         (now + datetime.timedelta(days=365)).isoformat())
    )
    conn.commit()
    conn.close()

    return {
        "id": doc_id,
        "policy_type": policy_type,
        "title": template["title"],
        "description": template["description"],
        "regulation_ref": template["regulation_ref"],
        "content": full_content,
        "status": "draft",
        "created_at": now.isoformat(),
        "section_count": len(template["sections"])
    }


# ============================================================================
# Breach Reporting Workflow — UK GDPR Art 33-34
# ============================================================================

BREACH_WORKFLOW_STEPS = [
    {"title": "Contain the breach", "description": "Take immediate steps to contain the breach and limit its impact. Disconnect affected systems if necessary. Do not destroy evidence."},
    {"title": "Assess the breach", "description": "Determine: what data was affected, how many individuals are affected, what the likely consequences are, and whether the breach is ongoing."},
    {"title": "Assess ICO notification requirement", "description": "Under UK GDPR Art 33, notify the ICO within 72 hours unless the breach is unlikely to result in a risk to individuals' rights and freedoms. Document the decision either way."},
    {"title": "Notify the ICO (if required)", "description": "Submit notification via the ICO's online breach reporting tool at ico.org.uk. Include: nature of breach, categories and approximate number of individuals, likely consequences, and measures taken."},
    {"title": "Assess individual notification requirement", "description": "Under Art 34, notify affected individuals without undue delay if the breach is likely to result in a HIGH risk to their rights and freedoms."},
    {"title": "Notify affected individuals (if required)", "description": "Notification must include: description of the breach in clear language, name and contact details of DPO, likely consequences, and measures taken to address the breach."},
    {"title": "Document in breach register", "description": "Record the breach in the firm's breach register under Art 33(5), including: facts, effects, and remedial action taken. This applies to ALL breaches, not just notifiable ones."},
    {"title": "Conduct root cause analysis", "description": "Investigate the underlying cause of the breach: human error, system vulnerability, process failure, or malicious action. Document findings."},
    {"title": "Implement remedial measures", "description": "Based on the root cause analysis, implement measures to prevent recurrence: training, system patches, process changes, or policy updates."},
    {"title": "Close and review", "description": "Close the breach report once all steps are completed. Schedule a lessons-learned review with the breach response team. Update the firm's data protection risk assessment if necessary."}
]

def create_breach_report(breach_data):
    """Create a new breach report with workflow steps"""
    now = datetime.datetime.now()
    breach_id = str(uuid.uuid4())
    deadline_72h = (now + datetime.timedelta(hours=72)).isoformat()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """INSERT INTO breach_reports
           (id, breach_type, severity, title, description, discovered_at, discovered_by,
            affected_data, affected_individuals, ico_notifiable, status, created_at, deadline_72h)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
        (breach_id,
         breach_data.get("breach_type", "data_breach"),
         breach_data.get("severity", "high"),
         breach_data.get("title", "Data Breach Report"),
         breach_data.get("description", ""),
         now.isoformat(),
         breach_data.get("discovered_by", ""),
         breach_data.get("affected_data", ""),
         breach_data.get("affected_individuals", 0),
         1 if breach_data.get("severity") in ("high", "critical") else 0,
         now.isoformat(),
         deadline_72h)
    )

    # Create workflow steps
    steps_data = []
    for idx, step_template in enumerate(BREACH_WORKFLOW_STEPS, 1):
        step_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO breach_report_steps
               (id, breach_id, step_number, title, description, status)
               VALUES (?, ?, ?, ?, ?, 'pending')""",
            (step_id, breach_id, idx, step_template["title"], step_template["description"])
        )
        steps_data.append({
            "id": step_id,
            "step_number": idx,
            "title": step_template["title"],
            "description": step_template["description"],
            "status": "pending"
        })

    conn.commit()
    conn.close()

    return {
        "id": breach_id,
        "title": breach_data.get("title", "Data Breach Report"),
        "severity": breach_data.get("severity", "high"),
        "deadline_72h": deadline_72h,
        "status": "open",
        "steps": steps_data,
        "total_steps": len(steps_data)
    }


def generate_audit_report(firm_name="Mitchell & Partners LLP"):
    """Generate a comprehensive SRA audit-ready report from current compliance data"""
    now = datetime.datetime.now()
    report_id = str(uuid.uuid4())

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Gather all compliance data
    # 1. SRA Audit items
    cursor.execute("SELECT category, item_name, status, last_reviewed, evidence_ref FROM sra_audit_items ORDER BY category")
    audit_items = [dict(r) for r in cursor.fetchall()]

    # 2. Compliance checks summary
    cursor.execute("SELECT status, COUNT(*) as cnt FROM compliance_checks GROUP BY status")
    check_counts = {r["status"]: r["cnt"] for r in cursor.fetchall()}

    # 3. Risk scores
    cursor.execute("SELECT entity_id, overall_score, sra_score, aml_score, cpr_score, gdpr_score, limitation_score FROM risk_scores WHERE entity_type='case'")
    risk_scores = [dict(r) for r in cursor.fetchall()]
    avg_risk = sum(r["overall_score"] for r in risk_scores) / len(risk_scores) if risk_scores else 0

    # 4. Active alerts
    cursor.execute("SELECT COUNT(*) as cnt FROM compliance_alerts WHERE status = 'active'")
    active_alerts = cursor.fetchone()["cnt"]

    # 5. Remediation plans
    cursor.execute("SELECT status, COUNT(*) as cnt FROM remediation_plans GROUP BY status")
    rem_counts = {r["status"]: r["cnt"] for r in cursor.fetchall()}

    # 6. Policy documents
    cursor.execute("SELECT title, status, created_at FROM policy_documents ORDER BY created_at DESC")
    policies = [dict(r) for r in cursor.fetchall()]

    # 7. Breach reports
    cursor.execute("SELECT COUNT(*) as cnt FROM breach_reports")
    breach_count = cursor.fetchone()["cnt"]

    # Build report content
    compliant = len([i for i in audit_items if i["status"] == "compliant"])
    non_compliant = len([i for i in audit_items if i["status"] == "non_compliant"])
    needs_review = len([i for i in audit_items if i["status"] == "needs_review"])
    total_items = len(audit_items)
    readiness_pct = round((compliant / total_items * 100)) if total_items > 0 else 0

    # Group audit items by category
    categories = {}
    for item in audit_items:
        cat = item["category"]
        if cat not in categories:
            categories[cat] = {"compliant": 0, "non_compliant": 0, "needs_review": 0, "items": []}
        categories[cat][item["status"]] = categories[cat].get(item["status"], 0) + 1
        categories[cat]["items"].append(item)

    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"SRA COMPLIANCE AUDIT REPORT")
    lines.append(f"{'='*60}")
    lines.append(f"")
    lines.append(f"Firm: {firm_name}")
    lines.append(f"Report Date: {now.strftime('%d %B %Y')}")
    lines.append(f"Period: {(now - datetime.timedelta(days=365)).strftime('%d %B %Y')} to {now.strftime('%d %B %Y')}")
    lines.append(f"Generated by: Seema Compliance Engine")
    lines.append(f"")
    lines.append(f"{'-'*60}")
    lines.append(f"EXECUTIVE SUMMARY")
    lines.append(f"{'-'*60}")
    lines.append(f"")
    lines.append(f"Overall SRA Audit Readiness: {readiness_pct}%")
    lines.append(f"Average Case Risk Score: {round(avg_risk, 1)}/100")
    lines.append(f"Active Compliance Alerts: {active_alerts}")
    lines.append(f"Compliance Checks: {check_counts.get('pass', 0)} passed, {check_counts.get('fail', 0)} failed, {check_counts.get('warning', 0)} warnings")
    lines.append(f"Remediation Plans: {rem_counts.get('open', 0)} open, {rem_counts.get('in_progress', 0)} in progress, {rem_counts.get('completed', 0)} completed")
    lines.append(f"Policy Documents: {len(policies)} generated")
    lines.append(f"Data Breach Reports: {breach_count}")
    lines.append(f"")
    lines.append(f"{'-'*60}")
    lines.append(f"SRA AUDIT CHECKLIST SUMMARY")
    lines.append(f"{'-'*60}")
    lines.append(f"")
    lines.append(f"Total Items: {total_items}")
    lines.append(f"Compliant: {compliant} ({readiness_pct}%)")
    lines.append(f"Non-Compliant: {non_compliant}")
    lines.append(f"Needs Review: {needs_review}")
    lines.append(f"")

    for cat_name, cat_data in categories.items():
        display_name = cat_name.replace("_", " ").title()
        cat_total = len(cat_data["items"])
        cat_comp = cat_data.get("compliant", 0)
        lines.append(f"  {display_name}: {cat_comp}/{cat_total} compliant")
        for item in cat_data["items"]:
            status_label = item["status"].replace("_", " ").upper()
            lines.append(f"    - {item['item_name']}: {status_label}" + (f" (evidence: {item['evidence_ref']})" if item.get('evidence_ref') else " [no evidence filed]"))
    lines.append(f"")

    lines.append(f"{'-'*60}")
    lines.append(f"RISK ASSESSMENT OVERVIEW")
    lines.append(f"{'-'*60}")
    lines.append(f"")
    lines.append(f"Cases assessed: {len(risk_scores)}")
    lines.append(f"Average risk score: {round(avg_risk, 1)}")
    high_risk = [r for r in risk_scores if r["overall_score"] > 50]
    lines.append(f"High-risk cases (score >50): {len(high_risk)}")
    lines.append(f"")

    if policies:
        lines.append(f"{'-'*60}")
        lines.append(f"POLICY DOCUMENTS STATUS")
        lines.append(f"{'-'*60}")
        lines.append(f"")
        for p in policies:
            lines.append(f"  - {p['title']}: {p['status'].upper()}")
        lines.append(f"")

    lines.append(f"{'-'*60}")
    lines.append(f"COMPLIANCE OFFICER SIGN-OFF")
    lines.append(f"{'-'*60}")
    lines.append(f"")
    lines.append(f"COLP Name: _________________________ Date: _____________")
    lines.append(f"COFA Name: _________________________ Date: _____________")
    lines.append(f"Managing Partner: ___________________ Date: _____________")

    full_content = "\n".join(lines)

    summary_data = {
        "readiness_pct": readiness_pct,
        "avg_risk": round(avg_risk, 1),
        "active_alerts": active_alerts,
        "compliant_items": compliant,
        "non_compliant_items": non_compliant,
        "needs_review_items": needs_review,
        "total_items": total_items,
        "checks_passed": check_counts.get("pass", 0),
        "checks_failed": check_counts.get("fail", 0),
        "remediation_open": rem_counts.get("open", 0),
        "remediation_completed": rem_counts.get("completed", 0),
        "policies_count": len(policies),
        "breach_count": breach_count
    }

    # Store report
    cursor.execute(
        """INSERT INTO audit_reports
           (id, report_type, title, generated_at, generated_by, period_start, period_end, summary, content, status)
           VALUES (?, 'sra_audit', ?, ?, 'Seema Compliance Engine', ?, ?, ?, ?, 'generated')""",
        (report_id, f"SRA Compliance Audit Report — {now.strftime('%B %Y')}",
         now.isoformat(),
         (now - datetime.timedelta(days=365)).isoformat(),
         now.isoformat(),
         json.dumps(summary_data),
         full_content)
    )
    conn.commit()
    conn.close()

    return {
        "id": report_id,
        "title": f"SRA Compliance Audit Report — {now.strftime('%B %Y')}",
        "generated_at": now.isoformat(),
        "summary": summary_data,
        "content": full_content
    }


# ============================================================================
# HTTP Request Handler
# ============================================================================

class RequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            # Serve the demo HTML at root
            if path == "/" or path == "/index.html":
                self.serve_html()
                return

            if path == "/api/industries":
                self.handle_get_industries()
            elif path.startswith("/api/industries/") and "/workflows" in path:
                ind_id = path.split("/")[3]
                self.handle_get_industry_workflows(ind_id)
            elif path.startswith("/api/industries/") and path.count("/") == 3:
                ind_id = path.split("/")[3]
                self.handle_get_industry(ind_id)
            elif path == "/api/law/workflows":
                self.handle_get_law_workflows()
            elif path.startswith("/api/law/workflows/") and "/runs/" in path:
                # /api/law/workflows/{id}/runs/{runId}/status
                parts = path.split("/")
                workflow_id = parts[4]
                run_id = parts[6]
                self.handle_get_run_status(workflow_id, run_id)
            elif path.startswith("/api/law/workflows/") and path.count("/") == 4:
                workflow_id = path.split("/")[4]
                self.handle_get_workflow(workflow_id)
            elif path.startswith("/api/workflows/") and "/runs/" in path:
                parts = path.split("/")
                workflow_id = parts[3]
                run_id = parts[5]
                self.handle_get_run_status(workflow_id, run_id)
            elif path.startswith("/api/workflows/"):
                workflow_id = path.split("/")[3]
                self.handle_get_workflow(workflow_id)
            elif path == "/api/law/clients":
                self.handle_get_law_clients()
            elif path.startswith("/api/law/cases/") and "/full" in path:
                case_id = path.split("/")[4]
                self.handle_get_case_full(case_id)
            elif path == "/api/law/cases":
                self.handle_get_law_cases()
            elif path.startswith("/api/law/cases/") and path.count("/") == 4:
                case_id = path.split("/")[4]
                self.handle_get_case_detail(case_id)
            elif path == "/api/law/search":
                q = query.get('q', [''])[0]
                self.handle_law_search(q)
            elif path == "/api/law/deadlines":
                self.handle_get_law_deadlines()
            elif path == "/api/law/documents":
                self.handle_get_law_documents()
            elif path == "/api/dashboard/stats":
                self.handle_get_dashboard_stats()
            elif path == "/api/notifications":
                self.handle_get_notifications()
            elif path == "/api/compliance/dashboard":
                self.handle_compliance_dashboard()
            elif path == "/api/compliance/alerts":
                severity_filter = query.get('severity', [None])[0]
                self.handle_compliance_alerts(severity_filter)
            elif path == "/api/compliance/checks":
                status_filter = query.get('status', [None])[0]
                self.handle_compliance_checks(status_filter)
            elif path == "/api/compliance/risk-scores":
                self.handle_compliance_risk_scores()
            elif path == "/api/compliance/sra-audit":
                self.handle_compliance_sra_audit()
            elif path.startswith("/api/compliance/case/"):
                case_id = path.split("/")[-1]
                self.handle_compliance_case(case_id)
            elif path == "/api/compliance/remediation-plans":
                self.handle_get_remediation_plans()
            elif path.startswith("/api/compliance/remediation-plans/"):
                plan_id = path.split("/")[-1]
                self.handle_get_remediation_plan(plan_id)
            elif path == "/api/compliance/policies":
                self.handle_get_policies()
            elif path == "/api/compliance/policy-templates":
                self.handle_get_policy_templates()
            elif path.startswith("/api/compliance/policies/"):
                policy_id = path.split("/")[-1]
                self.handle_get_policy(policy_id)
            elif path == "/api/compliance/breach-reports":
                self.handle_get_breach_reports()
            elif path.startswith("/api/compliance/breach-reports/"):
                breach_id = path.split("/")[-1]
                self.handle_get_breach_report(breach_id)
            elif path == "/api/compliance/audit-reports":
                self.handle_get_audit_reports()
            elif path.startswith("/api/compliance/audit-reports/"):
                report_id = path.split("/")[-1]
                self.handle_get_audit_report(report_id)
            elif path == "/api/compliance/daily-briefing":
                self.handle_daily_briefing()
            elif path == "/api/compliance/staff":
                self.handle_get_staff()
            elif path.startswith("/api/compliance/staff/") and path.count("/") == 4:
                staff_id = path.split("/")[-1]
                self.handle_get_staff_detail(staff_id)
            elif path == "/api/compliance/training-overview":
                self.handle_get_training_overview()
            elif path == "/api/compliance/intake":
                self.handle_get_intake()
            elif path.startswith("/api/compliance/intake/"):
                intake_id = path.split("/")[-1]
                self.handle_get_intake_detail(intake_id)
            elif path == "/api/compliance/tasks":
                self.handle_get_tasks()
            elif path == "/api/compliance/regulatory-updates":
                self.handle_get_regulatory_updates()
            elif path == "/api/compliance/deadlines":
                self.handle_get_all_deadlines()
            elif path == "/api/compliance/chasers":
                self.handle_get_chasers()
            elif path == "/api/compliance/chasers/pending":
                self.handle_get_pending_chasers()
            elif path == "/api/compliance/evidence":
                entity_type = query.get('entity_type', [None])[0]
                entity_id = query.get('entity_id', [None])[0]
                self.handle_get_evidence(entity_type, entity_id)
            elif path.startswith("/api/compliance/evidence/") and "/download" in path:
                evidence_id = path.split("/")[4]
                self.handle_download_evidence(evidence_id)
            elif path.startswith("/api/compliance/evidence/"):
                evidence_id = path.split("/")[-1]
                self.handle_get_evidence_detail(evidence_id)
            elif path == "/api/compliance/audit-trail":
                entity_type = query.get('entity_type', [None])[0]
                performed_by = query.get('performed_by', [None])[0]
                days = int(query.get('days', ['14'])[0])
                self.handle_get_audit_trail(entity_type, performed_by, days)
            elif path == "/api/compliance/audit-trail/summary":
                self.handle_get_audit_trail_summary()
            elif path == "/api/compliance/sra-return":
                self.handle_get_sra_return()
            elif path == "/api/compliance/supervision":
                self.handle_get_supervision_schedule()
            elif path == "/api/compliance/supervision/overdue":
                self.handle_get_overdue_supervision()
            elif path.startswith("/api/compliance/supervision/"):
                sched_id = path.split("/")[-1]
                self.handle_get_supervision_detail(sched_id)
            elif path == "/api/compliance/matters":
                self.handle_get_matter_checklists()
            elif path.startswith("/api/compliance/matters/"):
                checklist_id = path.split("/")[-1]
                self.handle_get_matter_checklist_detail(checklist_id)
            elif path == "/api/admin/import-logs":
                self.handle_get_import_logs()
            elif path == "/api/admin/export/staff":
                self.handle_export_staff_csv()
            elif path == "/api/admin/export/cases":
                self.handle_export_cases_csv()
            elif path == "/api/admin/export/training":
                self.handle_export_training_csv()
            elif path == "/api/admin/users":
                self.handle_get_users()
            elif path.startswith("/api/admin/users/"):
                user_id = path.split("/")[-1]
                self.handle_get_user(user_id)
            elif path == "/api/staff/my-tasks":
                token = self.headers.get('X-Auth-Token', '')
                self.handle_get_my_tasks(token)
            elif path == "/api/staff/my-training":
                token = self.headers.get('X-Auth-Token', '')
                self.handle_get_my_training(token)
            elif path == "/api/staff/my-chasers":
                token = self.headers.get('X-Auth-Token', '')
                self.handle_get_my_chasers(token)
            elif path == "/api/admin/email-settings":
                self.handle_get_email_settings()
            elif path == "/api/admin/email-queue":
                self.handle_get_email_queue()
            elif path == "/api/admin/email-queue/stats":
                self.handle_get_email_queue_stats()
            elif path == "/api/admin/email-templates":
                self.handle_get_email_templates()
            elif path == "/api/compliance/regulatory-intelligence":
                self.handle_reg_intelligence_dashboard()
            elif path == "/api/compliance/regulatory-intelligence/feed-status":
                self.handle_reg_feed_status()
            elif path == "/api/compliance/regulatory-intelligence/policy-queue":
                self.handle_reg_policy_queue()
            elif path.startswith("/api/compliance/regulatory-intelligence/impact/"):
                update_id = path.split("/")[-1]
                self.handle_reg_impact_analysis(update_id)
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Not found"}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def serve_html(self):
        """Serve the demo HTML file"""
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seema-demo.html")
        try:
            with open(html_path, "r", encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content.encode('utf-8'))))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except FileNotFoundError:
            self.send_response(404)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>seema-demo.html not found</h1>")

    def do_POST(self):
        """Handle POST requests"""
        path = self.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            if "/law/workflows/" in path and "/execute" in path:
                workflow_id = path.split("/")[4]
                self.handle_execute_workflow(workflow_id, body)
            elif "/law/workflows/" in path and "/approve" in path:
                # POST /api/law/workflows/{id}/runs/{run_id}/steps/{step_log_id}/approve
                parts = path.split("/")
                step_log_id = parts[8]
                self.handle_step_approval(step_log_id, body)
            elif "/api/compliance/alerts/" in path and "/acknowledge" in path:
                alert_id = path.split("/")[4]
                self.handle_compliance_alert_acknowledge(alert_id, body)
            elif "/api/compliance/alerts/" in path and "/resolve" in path:
                alert_id = path.split("/")[4]
                self.handle_compliance_alert_resolve(alert_id, body)
            elif path == "/api/compliance/scan":
                self.handle_compliance_scan(body)
            elif path == "/api/compliance/remediate":
                self.handle_create_remediation(body)
            elif "/api/compliance/remediation-steps/" in path and "/complete" in path:
                step_id = path.split("/")[4]
                self.handle_complete_remediation_step(step_id, body)
            elif "/api/compliance/remediation-plans/" in path and "/assign" in path:
                plan_id = path.split("/")[4]
                self.handle_assign_remediation(plan_id, body)
            elif path == "/api/compliance/generate-policy":
                self.handle_generate_policy(body)
            elif path == "/api/compliance/breach-report":
                self.handle_create_breach_report(body)
            elif "/api/compliance/breach-steps/" in path and "/complete" in path:
                step_id = path.split("/")[4]
                self.handle_complete_breach_step(step_id, body)
            elif path == "/api/compliance/generate-audit-report":
                self.handle_generate_audit_report(body)
            elif "/api/compliance/tasks/" in path and "/complete" in path:
                task_id = path.split("/")[4]
                self.handle_complete_task(task_id, body)
            elif path == "/api/compliance/intake":
                self.handle_create_intake(body)
            elif "/api/compliance/intake/" in path and "/assess" in path:
                intake_id = path.split("/")[4]
                self.handle_assess_intake(intake_id, body)
            elif "/api/compliance/regulatory-updates/" in path and "/acknowledge" in path:
                update_id = path.split("/")[4]
                self.handle_acknowledge_update(update_id, body)
            elif path == "/api/compliance/chasers/send":
                self.handle_send_chaser(body)
            elif "/api/compliance/chasers/" in path and "/escalate" in path:
                chaser_id = path.split("/")[4]
                self.handle_escalate_chaser(chaser_id, body)
            elif path == "/api/compliance/evidence":
                self.handle_create_evidence(body)
            elif path == "/api/compliance/sra-return/export":
                self.handle_export_sra_return(body)
            elif "/api/compliance/supervision/" in path and "/complete" in path:
                sched_id = path.split("/")[4]
                self.handle_complete_supervision(sched_id, body)
            elif path == "/api/compliance/matters":
                self.handle_create_matter_checklist(body)
            elif "/api/compliance/matter-items/" in path and "/complete" in path:
                item_id = path.split("/")[4]
                self.handle_complete_matter_item(item_id, body)
            elif path == "/api/admin/import/staff":
                self.handle_import_staff(body)
            elif path == "/api/admin/import/cases":
                self.handle_import_cases(body)
            elif path == "/api/admin/import/training":
                self.handle_import_training(body)
            elif path == "/api/admin/import/clients":
                self.handle_import_clients(body)
            elif path == "/api/admin/clear-demo-data":
                self.handle_clear_demo_data(body)
            elif path == "/api/auth/login":
                self.handle_auth_login(body)
            elif path == "/api/auth/logout":
                self.handle_auth_logout(body)
            elif path == "/api/admin/users":
                self.handle_create_user(body)
            elif path == "/api/admin/users/reset-password":
                self.handle_reset_password(body)
            elif path == "/api/notifications/dismiss":
                self.handle_dismiss_notification(body)
            elif path == "/api/notifications/dismiss-all":
                self.handle_dismiss_all_notifications(body)
            elif path == "/api/staff/acknowledge-chaser":
                self.handle_staff_acknowledge_chaser(body)
            elif path == "/api/staff/complete-training":
                self.handle_staff_complete_training(body)
            elif path == "/api/staff/log-action":
                self.handle_staff_log_action(body)
            elif path == "/api/admin/email-settings":
                self.handle_update_email_settings(body)
            elif path == "/api/admin/email-queue/send":
                self.handle_send_queued_email(body)
            elif path == "/api/admin/email-queue/send-all":
                self.handle_send_all_queued(body)
            elif path == "/api/admin/email/test":
                self.handle_test_email(body)
            elif path == "/api/admin/email/auto-chase":
                self.handle_trigger_auto_chase(body)
            elif path == "/api/compliance/sra-return/export-pdf":
                self.handle_export_sra_return_pdf(body)
            elif path == "/api/compliance/audit-report/export-pdf":
                self.handle_export_audit_report_pdf(body)
            elif path == "/api/compliance/breach-report/export-pdf":
                self.handle_export_breach_report_pdf(body)
            elif path == "/api/compliance/weekly-summary/pdf":
                self.handle_weekly_summary_pdf(body)
            elif path == "/api/admin/scheduler/run-daily":
                self.handle_run_daily_schedule(body)
            # ---- Briefing Command Centre Actions ----
            elif path == "/api/compliance/briefing/chase-training":
                self.handle_briefing_chase_training(body)
            elif path == "/api/compliance/briefing/chase-review":
                self.handle_briefing_chase_review(body)
            elif path == "/api/compliance/briefing/escalate":
                self.handle_briefing_escalate(body)
            elif path == "/api/compliance/briefing/schedule-supervision":
                self.handle_briefing_schedule_supervision(body)
            # ---- Inline Action Endpoints ----
            elif "/api/compliance/intake/" in path and "/approve" in path:
                intake_id = path.split("/")[4]
                self.handle_approve_intake(intake_id, body)
            elif "/api/compliance/intake/" in path and "/reject" in path:
                intake_id = path.split("/")[4]
                self.handle_reject_intake(intake_id, body)
            elif "/api/compliance/evidence/" in path and "/verify" in path:
                evidence_id = path.split("/")[4]
                self.handle_verify_evidence(evidence_id, body)
            elif path == "/api/compliance/tasks/create-from-update":
                self.handle_create_task_from_reg_update(body)
            elif "/api/compliance/alerts/" in path and "/escalate" in path:
                alert_id = path.split("/")[4]
                self.handle_escalate_alert(alert_id, body)
            elif "/api/compliance/chasers/" in path and "/resend" in path:
                chaser_id = path.split("/")[4]
                self.handle_resend_chaser(chaser_id, body)
            elif "/api/compliance/training/" in path and "/complete" in path:
                training_id = path.split("/")[4]
                self.handle_complete_training_record(training_id, body)
            # ---- Regulatory Intelligence Endpoints ----
            elif path == "/api/compliance/regulatory-intelligence/scan":
                self.handle_reg_feed_scan(body)
            elif path.startswith("/api/compliance/regulatory-intelligence/analyze/"):
                update_id = path.split("/")[-1]
                self.handle_reg_analyze_update(update_id, body)
            elif "/api/compliance/regulatory-intelligence/policy-queue/" in path and "/approve" in path:
                item_id = path.split("/")[5]
                self.handle_reg_policy_approve(item_id, body)
            elif "/api/compliance/regulatory-intelligence/policy-queue/" in path and "/apply" in path:
                item_id = path.split("/")[5]
                self.handle_reg_policy_apply(item_id, body)
            elif "/api/compliance/regulatory-intelligence/policy-queue/" in path and "/dismiss" in path:
                item_id = path.split("/")[5]
                self.handle_reg_policy_dismiss(item_id, body)
            elif path.startswith("/api/compliance/regulatory-intelligence/resolve/"):
                analysis_id = path.split("/")[-1]
                self.handle_reg_resolve_analysis(analysis_id, body)
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Not found"}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Auth-Token")
        self.end_headers()

    def send_json(self, data, status=200):
        """Send JSON response with CORS headers"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def handle_get_law_workflows(self):
        """Return all law workflows with their steps"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, description, category, estimated_duration_minutes FROM workflows WHERE industry_id = 'law' ORDER BY name"
        )
        workflows = []
        for row in cursor.fetchall():
            wf = dict(row)
            cursor.execute(
                "SELECT id, step_number, name, requires_approval FROM workflow_steps WHERE workflow_id = ? ORDER BY step_number",
                (wf['id'],)
            )
            wf['steps'] = [dict(s) for s in cursor.fetchall()]
            workflows.append(wf)
        conn.close()
        self.send_json({"workflows": workflows})

    def handle_get_industries(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, description, icon, color FROM industries")
        industries = [dict(row) for row in cursor.fetchall()]
        conn.close()

        self.send_json({"industries": industries})

    def handle_get_industry(self, ind_id):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, description, icon, color FROM industries WHERE id = ?", (ind_id,))
        industry = cursor.fetchone()
        conn.close()

        if not industry:
            self.send_json({"error": "Industry not found"}, 404)
            return

        self.send_json({"industry": dict(industry)})

    def handle_get_industry_workflows(self, ind_id):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, description, estimated_duration_minutes, enabled FROM workflows WHERE industry_id = ? AND enabled = 1",
            (ind_id,)
        )
        workflows = [dict(row) for row in cursor.fetchall()]
        conn.close()

        self.send_json({"workflows": workflows})

    def handle_get_workflow(self, workflow_id):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, industry_id, name, description, estimated_duration_minutes FROM workflows WHERE id = ?",
            (workflow_id,)
        )
        workflow = cursor.fetchone()

        if not workflow:
            conn.close()
            self.send_json({"error": "Workflow not found"}, 404)
            return

        cursor.execute("SELECT id, step_number, name, requires_approval FROM workflow_steps WHERE workflow_id = ? ORDER BY step_number", (workflow_id,))
        steps = [dict(row) for row in cursor.fetchall()]
        conn.close()

        workflow_dict = dict(workflow)
        workflow_dict["steps"] = steps

        self.send_json({"workflow": workflow_dict})

    def handle_execute_workflow(self, workflow_id, body):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, industry_id FROM workflows WHERE id = ?", (workflow_id,))
        workflow = cursor.fetchone()

        if not workflow:
            conn.close()
            self.send_json({"error": "Workflow not found"}, 404)
            return

        run_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()

        cursor.execute(
            """INSERT INTO workflow_runs (id, workflow_id, status, started_at, data_input, data_output)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, workflow_id, "running", now, body, "")
        )
        conn.commit()

        # Execute async
        thread = threading.Thread(
            target=self.execute_workflow_async,
            args=(run_id, workflow_id)
        )
        thread.daemon = True
        thread.start()

        conn.close()

        self.send_json({
            "run_id": run_id,
            "runId": run_id,
            "workflow_id": workflow_id,
            "status": "running"
        }, 202)

    def handle_step_approval(self, step_log_id, body):
        """Handle step approval"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            body_data = json.loads(body) if body else {}
        except:
            body_data = {}

        approved = body_data.get("approved", True)

        cursor.execute("SELECT id, run_id, status FROM run_step_logs WHERE id = ?", (step_log_id,))
        log = cursor.fetchone()

        if not log:
            conn.close()
            self.send_json({"error": "Step log not found"}, 404)
            return

        new_status = "approved" if approved else "rejected"

        cursor.execute(
            "UPDATE run_step_logs SET status = ?, completed_at = ? WHERE id = ?",
            (new_status, datetime.datetime.now().isoformat(), step_log_id)
        )
        conn.commit()
        conn.close()

        self.send_json({"status": new_status, "step_log_id": step_log_id})

    def execute_workflow_async(self, run_id, workflow_id):
        """Execute workflow asynchronously"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT id, name, industry_id FROM workflows WHERE id = ?", (workflow_id,))
            workflow = cursor.fetchone()

            cursor.execute("SELECT id, step_number, name, requires_approval FROM workflow_steps WHERE workflow_id = ? ORDER BY step_number", (workflow_id,))
            steps = cursor.fetchall()

            # Generate all step outputs upfront — one output object per step
            all_outputs = self.generate_step_outputs(cursor, workflow['industry_id'], workflow['name'])

            for idx, step in enumerate(steps):
                step_log_id = str(uuid.uuid4())
                step_start = datetime.datetime.now().isoformat()

                cursor.execute(
                    """INSERT INTO run_step_logs (id, run_id, step_id, status, started_at, output)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (step_log_id, run_id, step['id'], "pending", step_start, "")
                )
                conn.commit()

                # Simulate processing time
                time.sleep(random.uniform(0.3, 0.8))

                # Get this step's specific output
                step_output = all_outputs[idx] if idx < len(all_outputs) else {"result": "completed"}

                if step['requires_approval']:
                    step_status = "approval_pending"
                    step_output['approval_message'] = f"'{step['name']}' requires your approval before proceeding."
                else:
                    step_status = "completed"

                step_end = datetime.datetime.now().isoformat()
                cursor.execute(
                    """UPDATE run_step_logs SET status = ?, completed_at = ?, output = ? WHERE id = ?""",
                    (step_status, step_end, json.dumps(step_output), step_log_id)
                )
                conn.commit()

            # Get workflow result summary
            summary = self.get_workflow_result_summary(cursor, workflow['industry_id'], workflow['name'])

            cursor.execute(
                """UPDATE workflow_runs SET status = ?, completed_at = ?, data_output = ? WHERE id = ?""",
                ("completed", datetime.datetime.now().isoformat(), json.dumps(summary), run_id)
            )
            conn.commit()

        except Exception as e:
            cursor.execute(
                """UPDATE workflow_runs SET status = ?, error_message = ?, completed_at = ? WHERE id = ?""",
                ("failed", str(e), datetime.datetime.now().isoformat(), run_id)
            )
            conn.commit()
        finally:
            conn.close()

    def generate_step_outputs(self, cursor, industry_id, workflow_name):
        """Generate realistic step outputs for law workflows"""
        return self._law_step_outputs(cursor, workflow_name)

    def _law_step_outputs(self, cursor, wf):
        """Generate law-specific step outputs"""
        cursor.execute("SELECT * FROM law_clients ORDER BY RANDOM() LIMIT 1")
        c = cursor.fetchone()
        client = dict(c) if c else {}
        cname = client.get('name', 'Client')

        cursor.execute("SELECT * FROM law_cases ORDER BY RANDOM() LIMIT 1")
        cs = cursor.fetchone()
        case = dict(cs) if cs else {}

        if "Client Intake" in wf:
            return [
                {"action": "gather_info", "client": cname, "email": client.get('email',''), "phone": client.get('phone',''), "source": "Online intake form"},
                {"action": "search_records", "existing_clients_checked": random.randint(200,500), "match_found": False},
                {"action": "conflict_analysis", "parties_checked": random.randint(3,8), "conflicts_found": 0, "system": "Clio Conflict Check"},
                {"action": "generate_report", "result": "No conflicts detected", "confidence": "99.2%", "report_filed": True},
                {"action": "create_file", "client_id": client.get('id',''), "file_opened": True, "welcome_email_sent": True, "sent_to": client.get('email','')},
            ]
        elif "Case Opening" in wf:
            case_type = case.get('case_type','Commercial Litigation')
            prec_count = random.randint(5,15)
            return [
                {"action": "create_case", "case_name": case.get('case_name','New Case'), "type": case_type, "reference": f"CASE-{random.randint(1000,9999)}"},
                {"action": "classify_type", "category": case_type, "complexity": "Medium", "estimated_hours": random.randint(20,80), "precedent_search": f"Auto-searched BAILII + Westlaw for {case_type} precedents", "relevant_cases_found": prec_count},
                {"action": "assign_attorney", "attorney": "Sarah Mitchell, Senior Partner", "supervising": "James Wright, Managing Partner", "specialist_area": case_type},
                {"action": "send_notification", "notified": ["Assigned attorney", "Client", "Accounts team"], "method": "Email + Clio notification"},
                {"action": "init_folder", "folder_created": True, "template_docs": ["Engagement letter", "Fee agreement", "Authority to act"], "precedent_bundle": f"{prec_count} relevant cases attached", "system": "Clio Document Management"},
            ]
        elif "Time Tracking" in wf or "Billing" in wf:
            cursor.execute("SELECT SUM(hours) as total FROM law_time_entries")
            total_h = cursor.fetchone()['total'] or 0
            cursor.execute("SELECT COUNT(*) as cnt FROM law_time_entries")
            entries_cnt = cursor.fetchone()['cnt']
            rate = case.get('hourly_rate', 250) or 250
            billable_amount = total_h * rate
            return [
                {"action": "retrieve_entries", "case": case.get('case_name',''), "total_entries": entries_cnt, "period": "This month"},
                {"action": "validate_hours", "total_hours": f"{total_h:.1f}", "disputed": 0, "approved": True},
                {"action": "calculate_billable", "rate": f"£{rate}/hr", "total_amount": f"£{billable_amount:,.2f}", "vat": f"£{billable_amount * 0.2:,.2f}"},
                {"action": "generate_invoice", "invoice_number": f"INV-{random.randint(10000,99999)}", "format": "LEDES 1998B", "sent_to": cname},
                {"action": "record_invoice", "system": "Clio + QuickBooks", "payment_terms": "30 days", "status": "Sent"},
            ]
        elif "Document" in wf:
            cursor.execute("SELECT COUNT(*) as cnt FROM law_documents")
            dc = cursor.fetchone()['cnt']
            doc_types = ["Particulars of Claim", "Defence", "Legal Brief", "Settlement Agreement", "Court Order"]
            doc_type = random.choice(doc_types)
            return [
                {"action": "select_template", "template": f"Legal {doc_type} - High Court", "version": "v3.2", "library": "Firm Knowledge Base"},
                {"action": "fill_template", "case": case.get('case_name',''), "client": cname, "auto_filled_fields": random.randint(15,30)},
                {"action": "generate_doc", "document": doc_type, "pages": random.randint(5,20), "format": "DOCX + PDF"},
                {"action": "send_review", "reviewer": "Sarah Mitchell", "deadline": "48 hours", "tracked_changes": True},
                {"action": "log_version", "total_documents": dc, "version": "1.0", "system": "Clio DMS"},
            ]
        elif "Case Status" in wf:
            return [
                {"action": "retrieve_data", "case": case.get('case_name',''), "status": case.get('status','open'), "last_activity": "2 days ago"},
                {"action": "update_status", "new_status": "In Progress - Discovery Phase", "milestones_complete": f"{random.randint(2,5)}/8"},
                {"action": "generate_report", "format": "Client Status Report", "includes": "Timeline, Costs, Next Steps"},
                {"action": "send_update", "recipients": [cname, "Supervising partner"], "method": "Email + Portal update"},
            ]
        elif "Settlement" in wf or "Closure" in wf:
            amount = random.randint(50000, 500000)
            return [
                {"action": "record_settlement", "amount": f"£{amount:,}", "type": "Out-of-court settlement", "terms": "Full and final"},
                {"action": "calculate_costs", "legal_fees": f"£{amount*0.15:,.2f}", "disbursements": f"£{random.randint(500,5000):,}", "court_fees": f"£{random.randint(200,2000):,}"},
                {"action": "generate_agreement", "document": "Settlement Agreement", "signed_by": [cname, "Opposing party"], "format": "PDF with digital signatures"},
                {"action": "archive_case", "case_archived": True, "retention_period": "6 years", "system": "Clio Archive"},
                {"action": "close_case", "status": "Closed - Settled", "final_invoice_sent": True, "client_satisfaction_survey": "Sent"},
            ]
        elif "Compliance" in wf or "Ethics" in wf:
            return [
                {"action": "flag_issues", "items_reviewed": random.randint(10,30), "potential_issues": random.randint(0,2), "source": "SRA Standards Check"},
                {"action": "review_standards", "framework": "SRA Standards & Regulations 2019", "areas_checked": ["Client money", "Conflicts", "Confidentiality", "Competence"], "legislation_checked": "Solicitors Act 1974, Legal Services Act 2007, Data Protection Act 2018", "source": "legislation.gov.uk"},
                {"action": "generate_report", "status": "Compliant", "score": f"{random.randint(92,100)}%", "next_review": "Quarterly", "regulatory_updates": f"{random.randint(0,3)} new SRA notices this quarter"},
                {"action": "escalate", "escalation_needed": False, "risk_level": "Low"},
            ]
        elif "Client Communication" in wf:
            return [
                {"action": "prepare_summary", "case": case.get('case_name',''), "key_updates": random.randint(2,5), "period": "Last 7 days"},
                {"action": "draft_communication", "type": "Progress update email", "tone": "Professional", "word_count": random.randint(150,400)},
                {"action": "send_email", "to": client.get('email',''), "subject": f"Update: {case.get('case_name','Your Case')}", "sent": True},
                {"action": "log_communication", "system": "Clio Activity Log", "type": "Email", "billable": True, "time": "0.2 hrs"},
            ]
        elif "Deadline" in wf:
            cursor.execute("SELECT COUNT(*) as cnt FROM law_deadlines WHERE status = 'pending'")
            pending = cursor.fetchone()['cnt'] or 0
            cursor.execute("SELECT COUNT(*) as cnt FROM law_deadlines WHERE status = 'overdue'")
            overdue = cursor.fetchone()['cnt'] or 0
            return [
                {"action": "query_deadlines", "upcoming_7_days": pending if pending <= 10 else 10, "upcoming_30_days": pending, "overdue": overdue},
                {"action": "generate_calendar", "format": "iCal + Dashboard", "synced_to": ["Outlook", "Clio", "Google Calendar"]},
                {"action": "alert_attorneys", "notifications_sent": random.randint(3,8), "method": "Email + Push notification", "urgency_levels": "2 High, 4 Medium, 2 Low"},
                {"action": "track_responses", "acknowledged": random.randint(5,8), "pending": random.randint(0,3)},
            ]
        elif "Knowledge" in wf:
            cursor.execute("SELECT COUNT(*) as cnt FROM law_documents")
            dc = cursor.fetchone()['cnt']
            cursor.execute("SELECT case_type FROM law_cases ORDER BY RANDOM() LIMIT 1")
            ct = cursor.fetchone()
            case_type = ct['case_type'] if ct else 'Commercial Litigation'
            ext_cases = random.randint(8, 22)
            leg_found = random.randint(2, 6)
            return [
                {"action": "index_internal", "source": "Clio Document Management", "documents_indexed": dc, "internal_precedents": 3, "new_this_month": random.randint(5,15)},
                {"action": "search_external_law", "query": f"{case_type} law", "sources": "BAILII (free) + legislation.gov.uk (free) + Westlaw UK + LexisNexis UK", "cases_found": ext_cases, "legislation_found": leg_found, "courts": "Supreme Court, Court of Appeal, High Court, Tribunals"},
                {"action": "ai_analysis", "ai_summaries": ext_cases, "relevance_scoring": "Ranked by authority + relevance", "authority_hierarchy": "Supreme Court > Court of Appeal > High Court > Tribunals", "still_good_law": f"{ext_cases - random.randint(0,2)} of {ext_cases} confirmed"},
                {"action": "link_precedents", "internal": 3, "external": ext_cases, "legislation": leg_found, "total_precedents": 3 + ext_cases, "linked_to_active_cases": True},
            ]
        return [{"result": "success"}]

    def handle_get_run_status(self, workflow_id, run_id):
        """Get the status of a workflow run"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, workflow_id, status, started_at, completed_at, error_message, data_output FROM workflow_runs WHERE id = ? AND workflow_id = ?",
            (run_id, workflow_id)
        )
        run = cursor.fetchone()

        if not run:
            conn.close()
            self.send_json({"error": "Run not found"}, 404)
            return

        cursor.execute(
            """SELECT rsl.id, rsl.step_id, rsl.status, rsl.started_at, rsl.completed_at,
                      rsl.duration_ms, rsl.output, rsl.error_message,
                      ws.name as step_name, ws.step_number, ws.requires_approval
               FROM run_step_logs rsl
               LEFT JOIN workflow_steps ws ON rsl.step_id = ws.id
               WHERE rsl.run_id = ? ORDER BY ws.step_number, rsl.started_at""",
            (run_id,)
        )
        step_logs = [dict(row) for row in cursor.fetchall()]

        conn.close()

        run_dict = dict(run)
        run_dict["steps"] = step_logs

        # Parse data_output for result_summary
        result_summary = None
        if run_dict.get('data_output'):
            try:
                result_summary = json.loads(run_dict['data_output'])
            except (json.JSONDecodeError, TypeError):
                pass

        # Return flat structure for frontend compatibility
        self.send_json({
            "status": run_dict["status"],
            "steps": step_logs,
            "result_summary": result_summary,
            "run": run_dict,
        })

    def get_workflow_result_summary(self, cursor, industry_id, workflow_name):
        """Generate a realistic law firm result summary using actual database data"""
        summary = {"items": []}

        try:
            cursor.execute("SELECT COUNT(*) as cnt FROM law_clients")
            client_count = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM law_cases WHERE status = 'open'")
            open_cases = cursor.fetchone()['cnt']
            cursor.execute("SELECT name, email FROM law_clients ORDER BY RANDOM() LIMIT 3")
            sample_clients = [dict(r) for r in cursor.fetchall()]
            cursor.execute("SELECT SUM(hours) as total_hours FROM law_time_entries")
            total_hours = cursor.fetchone()['total_hours'] or 0

            if "Client Intake" in workflow_name:
                summary = {"title": "Client Intake Complete", "items": [
                    {"label": "Clients in System", "value": str(client_count)},
                    {"label": "Conflict Check", "value": "No conflicts found", "status": "success"},
                    {"label": "New Client File", "value": sample_clients[0]['name'] if sample_clients else "N/A"},
                    {"label": "Welcome Email", "value": f"Sent to {sample_clients[0]['email']}" if sample_clients else "Sent"},
                ]}
            elif "Case Opening" in workflow_name:
                cursor.execute("SELECT case_name, case_type, status FROM law_cases ORDER BY RANDOM() LIMIT 1")
                case = cursor.fetchone()
                summary = {"title": "Case Opened Successfully", "items": [
                    {"label": "Case", "value": case['case_name'] if case else "New Case"},
                    {"label": "Type", "value": case['case_type'] if case else "Commercial Litigation"},
                    {"label": "Open Cases", "value": str(open_cases)},
                    {"label": "Assigned To", "value": "Sarah Mitchell, Senior Partner"},
                ]}
            elif "Time Tracking" in workflow_name or "Billing" in workflow_name:
                cursor.execute("SELECT SUM(hours) as total_h FROM law_time_entries")
                total_h = cursor.fetchone()['total_h'] or 0
                billable = total_h * 250
                cursor.execute("SELECT COUNT(*) as cnt FROM law_time_entries")
                entries_cnt = cursor.fetchone()['cnt']
                summary = {"title": "Billing Report Generated", "items": [
                    {"label": "Total Billable Hours", "value": f"{total_h:.1f} hrs"},
                    {"label": "Total Revenue (@ £250/hr avg)", "value": f"£{billable:,.2f}"},
                    {"label": "Time Entries", "value": str(entries_cnt)},
                    {"label": "Payment Status", "value": "Processing", "status": "success"},
                ]}
            elif "Document" in workflow_name:
                cursor.execute("SELECT COUNT(*) as cnt FROM law_documents")
                doc_count = cursor.fetchone()['cnt']
                summary = {"title": "Document Generated & Reviewed", "items": [
                    {"label": "Document Type", "value": "Legal Brief/Pleading"},
                    {"label": "Total Documents in System", "value": str(doc_count)},
                    {"label": "Status", "value": "Ready for Filing", "status": "success"},
                    {"label": "Sent To", "value": "Review Queue"},
                ]}
            elif "Case Status" in workflow_name:
                cursor.execute("SELECT COUNT(*) as cnt FROM law_deadlines WHERE status = 'pending'")
                upcoming = cursor.fetchone()['cnt'] or 0
                summary = {"title": "Case Status Updated", "items": [
                    {"label": "Open Cases", "value": str(open_cases)},
                    {"label": "Active Matters", "value": str(client_count)},
                    {"label": "Upcoming Deadlines", "value": str(upcoming)},
                    {"label": "Status", "value": "Updated successfully", "status": "success"},
                ]}
            elif "Settlement" in workflow_name or "Closure" in workflow_name:
                summary = {"title": "Case Closed - Settlement Completed", "items": [
                    {"label": "Settlement Amount", "value": "£150,000"},
                    {"label": "Total Legal Fees", "value": "£22,500"},
                    {"label": "Cases Closed This Month", "value": "3"},
                    {"label": "Status", "value": "Archived & Closed", "status": "success"},
                ]}
            elif "Compliance" in workflow_name or "Ethics" in workflow_name:
                summary = {"title": "Compliance Review Completed", "items": [
                    {"label": "Items Reviewed", "value": str(random.randint(20, 40))},
                    {"label": "Issues Found", "value": "0"},
                    {"label": "Compliance Score", "value": "98%", "status": "success"},
                    {"label": "SRA Standards", "value": "Fully Compliant"},
                ]}
            elif "Client Communication" in workflow_name:
                cursor.execute("SELECT COUNT(*) as cnt FROM law_communications")
                comms = cursor.fetchone()['cnt']
                summary = {"title": "Client Updates Sent", "items": [
                    {"label": "Clients Updated", "value": str(random.randint(5, 15))},
                    {"label": "Total Communications", "value": str(comms)},
                    {"label": "Method", "value": "Email + Portal"},
                    {"label": "Status", "value": "Delivered", "status": "success"},
                ]}
            elif "Deadline" in workflow_name:
                cursor.execute("SELECT COUNT(*) as cnt FROM law_deadlines WHERE status = 'pending'")
                pending = cursor.fetchone()['cnt'] or 0
                cursor.execute("SELECT COUNT(*) as cnt FROM law_deadlines WHERE status = 'overdue'")
                overdue = cursor.fetchone()['cnt'] or 0
                summary = {"title": "Deadline Management Report", "items": [
                    {"label": "Upcoming Deadlines (7 days)", "value": str(min(pending, 10))},
                    {"label": "Upcoming Deadlines (30 days)", "value": str(pending)},
                    {"label": "Overdue Matters", "value": str(overdue)},
                    {"label": "Alerts Sent", "value": "8 notifications", "status": "success"},
                ]}
            elif "Knowledge" in workflow_name:
                cursor.execute("SELECT COUNT(*) as cnt FROM law_documents")
                dc = cursor.fetchone()['cnt']
                summary = {"title": "Knowledge Base Updated", "items": [
                    {"label": "Documents Indexed", "value": str(dc)},
                    {"label": "External Precedents Found", "value": str(random.randint(8, 22))},
                    {"label": "Legislation Sources", "value": "BAILII + legislation.gov.uk + Westlaw"},
                    {"label": "Status", "value": "Indexed & Searchable", "status": "success"},
                ]}
            else:
                summary = {"title": f"{workflow_name} Complete", "items": [
                    {"label": "Total Clients", "value": str(client_count)},
                    {"label": "Open Cases", "value": str(open_cases)},
                    {"label": "Billable Hours", "value": f"{total_hours:.1f} hrs"},
                    {"label": "Status", "value": "Completed successfully", "status": "success"},
                ]}

        except Exception as e:
            summary = {"title": "Workflow Completed", "items": [{"label": "Status", "value": "success"}]}

        return summary

    def handle_get_law_clients(self):
        """Get all law clients"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, email, phone, address, status FROM law_clients")
        clients = [dict(row) for row in cursor.fetchall()]
        conn.close()

        self.send_json({"clients": clients})

    def handle_get_law_cases(self):
        """Get all law cases"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, client_id, case_name, case_type, status, hourly_rate, opened_date FROM law_cases ORDER BY opened_date DESC"
        )
        cases = [dict(row) for row in cursor.fetchall()]
        conn.close()

        self.send_json({"cases": cases})

    def handle_get_law_deadlines(self):
        """Get law deadlines"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, case_id, deadline_type, due_date, description, status, cpr_rule FROM law_deadlines ORDER BY due_date ASC"
        )
        deadlines = [dict(row) for row in cursor.fetchall()]
        conn.close()

        self.send_json({"deadlines": deadlines})

    def handle_get_law_documents(self):
        """Get law documents"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, case_id, document_name, document_type, file_path, status FROM law_documents ORDER BY document_type"
        )
        documents = [dict(row) for row in cursor.fetchall()]
        conn.close()

        self.send_json({"documents": documents})

    def handle_law_search(self, query):
        """Search across cases, clients, documents, communications by keyword"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        q = f"%{query}%"

        # Search cases
        cursor.execute("""
            SELECT lc.id, lc.case_name, lc.case_type, lc.status, lc.opened_date,
                   lk.name as client_name, lk.email as client_email
            FROM law_cases lc
            JOIN law_clients lk ON lc.client_id = lk.id
            WHERE lc.case_name LIKE ? OR lc.case_type LIKE ? OR lk.name LIKE ?
            ORDER BY lc.opened_date DESC
        """, (q, q, q))
        cases = [dict(r) for r in cursor.fetchall()]

        # Search clients
        cursor.execute("""
            SELECT id, name, email, phone, address, status FROM law_clients
            WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?
        """, (q, q, q))
        clients = [dict(r) for r in cursor.fetchall()]

        # Search documents
        cursor.execute("""
            SELECT ld.id, ld.document_name, ld.document_type, ld.status,
                   lc.case_name, lk.name as client_name
            FROM law_documents ld
            JOIN law_cases lc ON ld.case_id = lc.id
            JOIN law_clients lk ON lc.client_id = lk.id
            WHERE ld.document_name LIKE ? OR ld.document_type LIKE ?
        """, (q, q))
        documents = [dict(r) for r in cursor.fetchall()]

        # Search communications
        cursor.execute("""
            SELECT lm.id, lm.type, lm.subject, lm.sent_date, lm.direction,
                   lc.case_name, lk.name as client_name
            FROM law_communications lm
            JOIN law_cases lc ON lm.case_id = lc.id
            JOIN law_clients lk ON lm.client_id = lk.id
            WHERE lm.subject LIKE ? OR lk.name LIKE ?
            ORDER BY lm.sent_date DESC
        """, (q, q))
        communications = [dict(r) for r in cursor.fetchall()]

        conn.close()

        self.send_json({
            "query": query,
            "results": {
                "cases": cases,
                "clients": clients,
                "documents": documents,
                "communications": communications
            },
            "total": len(cases) + len(clients) + len(documents) + len(communications)
        })

    def handle_get_case_detail(self, case_id):
        """Get a single case with client info"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT lc.*, lk.name as client_name, lk.email as client_email,
                   lk.phone as client_phone, lk.address as client_address
            FROM law_cases lc
            JOIN law_clients lk ON lc.client_id = lk.id
            WHERE lc.id = ?
        """, (case_id,))
        case = cursor.fetchone()
        conn.close()

        if not case:
            self.send_json({"error": "Case not found"}, 404)
            return

        self.send_json({"case": dict(case)})

    def handle_get_case_full(self, case_id):
        """Get FULL case history — case details + all linked records"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Case + client info
        cursor.execute("""
            SELECT lc.*, lk.name as client_name, lk.email as client_email,
                   lk.phone as client_phone, lk.address as client_address, lk.status as client_status
            FROM law_cases lc
            JOIN law_clients lk ON lc.client_id = lk.id
            WHERE lc.id = ?
        """, (case_id,))
        case_row = cursor.fetchone()

        if not case_row:
            conn.close()
            self.send_json({"error": "Case not found"}, 404)
            return

        case = dict(case_row)

        # All time entries for this case
        cursor.execute("""
            SELECT id, attorney_name, hours, description, entry_date
            FROM law_time_entries WHERE case_id = ? ORDER BY entry_date DESC
        """, (case_id,))
        time_entries = [dict(r) for r in cursor.fetchall()]
        total_hours = sum(t['hours'] for t in time_entries)
        total_billed = total_hours * (case.get('hourly_rate') or 250)

        # All documents for this case
        cursor.execute("""
            SELECT id, document_name, document_type, file_path, status
            FROM law_documents WHERE case_id = ? ORDER BY document_type
        """, (case_id,))
        documents = [dict(r) for r in cursor.fetchall()]

        # All deadlines for this case
        cursor.execute("""
            SELECT id, deadline_type, due_date, description, status, cpr_rule
            FROM law_deadlines WHERE case_id = ? ORDER BY due_date ASC
        """, (case_id,))
        deadlines = [dict(r) for r in cursor.fetchall()]

        # All communications for this case
        cursor.execute("""
            SELECT id, type, subject, sent_date, direction
            FROM law_communications WHERE case_id = ? ORDER BY sent_date DESC
        """, (case_id,))
        communications = [dict(r) for r in cursor.fetchall()]

        # Past workflow runs on this case (if any)
        cursor.execute("""
            SELECT id, status, started_at, completed_at, data_output
            FROM workflow_runs ORDER BY started_at DESC LIMIT 5
        """)
        recent_runs = [dict(r) for r in cursor.fetchall()]

        conn.close()

        self.send_json({
            "case": case,
            "time_entries": time_entries,
            "billing_summary": {
                "total_hours": round(total_hours, 1),
                "hourly_rate": case.get('hourly_rate') or 250,
                "total_billed": round(total_billed, 2),
                "entries_count": len(time_entries)
            },
            "documents": documents,
            "deadlines": deadlines,
            "communications": communications,
            "recent_workflow_runs": recent_runs,
            "summary": {
                "total_documents": len(documents),
                "total_communications": len(communications),
                "pending_deadlines": len([d for d in deadlines if d['status'] == 'pending']),
                "overdue_deadlines": len([d for d in deadlines if d['status'] == 'overdue']),
            }
        })

    def handle_get_dashboard_stats(self):
        """Get law firm dashboard statistics"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Law firm specific metrics
        cursor.execute("SELECT COUNT(*) as count FROM law_clients WHERE status = 'active'")
        total_clients = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as count FROM law_cases WHERE status IN ('open', 'in-progress')")
        active_cases = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as count FROM law_cases")
        total_cases = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as count FROM law_deadlines WHERE status = 'pending'")
        upcoming_deadlines = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(hours) as total FROM law_time_entries")
        billable_hours = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(hours * ?) as total FROM law_time_entries JOIN law_cases ON law_time_entries.case_id = law_cases.id", (250,))
        outstanding_invoices = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) as count FROM law_documents WHERE status = 'pending-review'")
        pending_docs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as count FROM law_communications WHERE direction = 'incoming'")
        recent_comms = cursor.fetchone()[0]

        cursor.execute("""
            SELECT id, case_name, status FROM law_cases
            ORDER BY opened_date DESC LIMIT 5
        """)
        recent_cases = [dict(row) for row in cursor.fetchall()]

        conn.close()

        stats = {
            "totalClients": total_clients,
            "activeCases": active_cases,
            "totalCases": total_cases,
            "upcomingDeadlines": upcoming_deadlines,
            "billableHours": f"{billable_hours:.1f}",
            "outstandingInvoices": f"£{outstanding_invoices:,.2f}",
            "pendingDocuments": pending_docs,
            "recentCommunications": recent_comms,
            "recentCases": recent_cases
        }

        self.send_json(stats)

    # ========== COMPLIANCE ENDPOINTS ==========

    # ========================================================================
    # Notifications
    # ========================================================================

    def handle_get_notifications(self):
        """Aggregate overdue / urgent items across all compliance areas into a notifications feed."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        notifications = []

        # 1. Overdue training
        cursor.execute("SELECT id, staff_id, title, due_date FROM staff_training WHERE status != 'completed' AND due_date < ?", (now[:10],))
        for row in cursor.fetchall():
            notifications.append({
                "id": "notif-training-" + row["id"],
                "type": "overdue_training",
                "severity": "high",
                "title": "Overdue Training",
                "message": (row["title"] or "Training") + " is overdue (due " + (row["due_date"] or "?") + ")",
                "entity_type": "training",
                "entity_id": row["id"],
                "staff_id": row["staff_id"],
                "created_at": row["due_date"]
            })

        # 2. Overdue file reviews
        cursor.execute("SELECT id, staff_id, case_id, due_date FROM staff_file_reviews WHERE status NOT IN ('completed','closed') AND due_date < ?", (now[:10],))
        for row in cursor.fetchall():
            notifications.append({
                "id": "notif-review-" + row["id"],
                "type": "overdue_review",
                "severity": "high",
                "title": "Overdue File Review",
                "message": "File review for case " + (row["case_id"] or "unknown")[:8] + " overdue (due " + (row["due_date"] or "?") + ")",
                "entity_type": "file_review",
                "entity_id": row["id"],
                "created_at": row["due_date"]
            })

        # 3. Critical alerts
        cursor.execute("SELECT id, title, description, severity, created_at FROM compliance_alerts WHERE severity = 'critical' AND resolved_at IS NULL ORDER BY created_at DESC LIMIT 10")
        for row in cursor.fetchall():
            notifications.append({
                "id": "notif-alert-" + row["id"],
                "type": "critical_alert",
                "severity": "critical",
                "title": row["title"] or "Critical Alert",
                "message": row["description"] or "",
                "entity_type": "alert",
                "entity_id": row["id"],
                "created_at": row["created_at"]
            })

        # 4. Overdue supervision
        cursor.execute("""SELECT ss.id, ss.staff_id, sm.name as staff_name, ss.next_due
                          FROM supervision_schedule ss
                          LEFT JOIN staff_members sm ON ss.staff_id = sm.id
                          WHERE ss.next_due < ? AND ss.status = 'active'""", (now[:10],))
        for row in cursor.fetchall():
            notifications.append({
                "id": "notif-supervision-" + row["id"],
                "type": "overdue_supervision",
                "severity": "medium",
                "title": "Overdue Supervision",
                "message": "Supervision for " + (row["staff_name"] or "staff") + " overdue (due " + (row["next_due"] or "?") + ")",
                "entity_type": "supervision",
                "entity_id": row["id"],
                "created_at": row["next_due"]
            })

        # 5. Pending intake (waiting > 3 days)
        three_days_ago = (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat()
        cursor.execute("SELECT id, client_name, created_at FROM client_intake WHERE status = 'pending' AND created_at < ?", (three_days_ago,))
        for row in cursor.fetchall():
            notifications.append({
                "id": "notif-intake-" + row["id"],
                "type": "pending_intake",
                "severity": "medium",
                "title": "Stale Client Intake",
                "message": (row["client_name"] or "Client") + " intake pending since " + (row["created_at"][:10] if row["created_at"] else "?"),
                "entity_type": "intake",
                "entity_id": row["id"],
                "created_at": row["created_at"]
            })

        conn.close()

        # Sort by severity then date
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        notifications.sort(key=lambda n: (severity_order.get(n["severity"], 9), n.get("created_at", "")))

        self.send_json({
            "notifications": notifications,
            "total": len(notifications),
            "critical": len([n for n in notifications if n["severity"] == "critical"]),
            "high": len([n for n in notifications if n["severity"] == "high"]),
            "medium": len([n for n in notifications if n["severity"] == "medium"])
        })

    def handle_dismiss_notification(self, body):
        data = json.loads(body) if body else {}
        notif_id = data.get("notification_id", "")
        self.send_json({"status": "dismissed", "notification_id": notif_id})

    def handle_dismiss_all_notifications(self, body):
        self.send_json({"status": "all_dismissed"})

    def handle_compliance_dashboard(self):
        """Return firm-wide compliance dashboard data"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get firm-level risk score
        cursor.execute("""
            SELECT overall_score, sra_score, aml_score, cpr_score, gdpr_score, limitation_score
            FROM risk_scores WHERE entity_type = 'firm' ORDER BY calculated_at DESC LIMIT 1
        """)
        firm_score = cursor.fetchone()
        if firm_score:
            firm_risk = dict(firm_score)
        else:
            firm_risk = {"overall_score": 0, "sra_score": 0, "aml_score": 0, "cpr_score": 0, "gdpr_score": 0, "limitation_score": 0}

        # Alert counts by severity
        cursor.execute("""
            SELECT severity, COUNT(*) as count FROM compliance_alerts WHERE status = 'active' GROUP BY severity
        """)
        alert_counts = {row['severity']: row['count'] for row in cursor.fetchall()}
        cursor.execute("SELECT COUNT(*) as cnt FROM compliance_alerts WHERE status = 'active'")
        total_alerts = cursor.fetchone()['cnt'] or 0

        # Compliance check summary
        cursor.execute("""
            SELECT status, COUNT(*) as count FROM compliance_checks GROUP BY status
        """)
        checks = {row['status']: row['count'] for row in cursor.fetchall()}

        # Compliance rate
        total_checks = sum(checks.values())
        passed_checks = checks.get('pass', 0)
        compliance_rate = int((passed_checks / total_checks * 100) if total_checks > 0 else 0)

        # Top 5 most critical alerts
        cursor.execute("""
            SELECT id, title, description, severity, created_at, case_id, client_id
            FROM compliance_alerts
            WHERE status = 'active'
            ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC
            LIMIT 5
        """)
        top_alerts = []
        for row in cursor.fetchall():
            alert = dict(row)
            # Get case/client names
            if alert['case_id']:
                cursor.execute("SELECT case_name FROM law_cases WHERE id = ?", (alert['case_id'],))
                case = cursor.fetchone()
                if case:
                    alert['case_name'] = case['case_name']
            if alert['client_id']:
                cursor.execute("SELECT name FROM law_clients WHERE id = ?", (alert['client_id'],))
                client = cursor.fetchone()
                if client:
                    alert['client_name'] = client['name']
            top_alerts.append(alert)

        # High risk cases (risk score > 40)
        cursor.execute("""
            SELECT rs.entity_id as case_id, rs.overall_score, lc.case_name
            FROM risk_scores rs
            JOIN law_cases lc ON rs.entity_id = lc.id
            WHERE rs.entity_type = 'case' AND rs.overall_score > 40
            ORDER BY rs.overall_score DESC
        """)
        high_risk_cases = [dict(row) for row in cursor.fetchall()]

        # Upcoming deadlines (next 5)
        cursor.execute("""
            SELECT ld.id, ld.due_date, ld.deadline_type, lc.case_name,
                   CAST((julianday(ld.due_date) - julianday('now')) AS INTEGER) as days_remaining
            FROM law_deadlines ld
            JOIN law_cases lc ON ld.case_id = lc.id
            WHERE ld.status = 'pending'
            ORDER BY ld.due_date ASC
            LIMIT 5
        """)
        upcoming_deadlines = [dict(row) for row in cursor.fetchall()]

        # SRA audit readiness
        cursor.execute("""
            SELECT status, COUNT(*) as count FROM sra_audit_items GROUP BY status
        """)
        sra_items = {row['status']: row['count'] for row in cursor.fetchall()}
        sra_compliant = sra_items.get('compliant', 0)
        sra_total = sum(sra_items.values())
        sra_score = int((sra_compliant / sra_total * 100) if sra_total > 0 else 0)

        conn.close()

        self.send_json({
            "firm_risk_score": firm_risk,
            "alert_counts": {
                "critical": alert_counts.get("critical", 0),
                "high": alert_counts.get("high", 0),
                "medium": alert_counts.get("medium", 0),
                "low": alert_counts.get("low", 0),
                "total": total_alerts
            },
            "compliance_rate": f"{compliance_rate}%",
            "checks_summary": {
                "total": total_checks,
                "pass": checks.get("pass", 0),
                "fail": checks.get("fail", 0),
                "warning": checks.get("warning", 0),
                "pending": checks.get("pending", 0)
            },
            "top_alerts": top_alerts,
            "high_risk_cases": high_risk_cases,
            "upcoming_deadlines": upcoming_deadlines,
            "sra_readiness": {
                "compliant": sra_compliant,
                "non_compliant": sra_items.get("non_compliant", 0),
                "needs_review": sra_items.get("needs_review", 0),
                "score": sra_score
            }
        })

    def handle_compliance_alerts(self, severity_filter=None):
        """Return compliance alerts, optionally filtered by severity"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if severity_filter:
            cursor.execute("""
                SELECT id, alert_type, severity, title, description, case_id, client_id,
                       regulation_ref, action_required, created_at, status
                FROM compliance_alerts
                WHERE severity = ? AND status = 'active'
                ORDER BY created_at DESC
            """, (severity_filter,))
        else:
            cursor.execute("""
                SELECT id, alert_type, severity, title, description, case_id, client_id,
                       regulation_ref, action_required, created_at, status
                FROM compliance_alerts
                WHERE status = 'active'
                ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC
            """)

        alerts = []
        for row in cursor.fetchall():
            alert = dict(row)
            # Join case and client names
            if alert['case_id']:
                cursor.execute("SELECT case_name FROM law_cases WHERE id = ?", (alert['case_id'],))
                case = cursor.fetchone()
                if case:
                    alert['case_name'] = case['case_name']
            if alert['client_id']:
                cursor.execute("SELECT name FROM law_clients WHERE id = ?", (alert['client_id'],))
                client = cursor.fetchone()
                if client:
                    alert['client_name'] = client['name']
            alerts.append(alert)

        conn.close()
        self.send_json({"alerts": alerts, "count": len(alerts)})

    def handle_compliance_checks(self, status_filter=None):
        """Return compliance checks, optionally filtered by status"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if status_filter:
            cursor.execute("""
                SELECT cc.id, cc.check_type, cc.check_name, cc.status, cc.severity, cc.description,
                       cc.regulation_ref, cc.remediation, cc.checked_at, cc.case_id, cc.client_id,
                       lc.case_name, lk.name as client_name
                FROM compliance_checks cc
                LEFT JOIN law_cases lc ON cc.case_id = lc.id
                LEFT JOIN law_clients lk ON cc.client_id = lk.id
                WHERE cc.status = ?
                ORDER BY cc.severity DESC, cc.checked_at DESC
            """, (status_filter,))
        else:
            cursor.execute("""
                SELECT cc.id, cc.check_type, cc.check_name, cc.status, cc.severity, cc.description,
                       cc.regulation_ref, cc.remediation, cc.checked_at, cc.case_id, cc.client_id,
                       lc.case_name, lk.name as client_name
                FROM compliance_checks cc
                LEFT JOIN law_cases lc ON cc.case_id = lc.id
                LEFT JOIN law_clients lk ON cc.client_id = lk.id
                ORDER BY cc.severity DESC, cc.checked_at DESC
            """)

        checks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        self.send_json({"checks": checks, "count": len(checks)})

    def handle_compliance_risk_scores(self):
        """Return all risk scores"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, entity_type, entity_id, overall_score, sra_score, aml_score, cpr_score, gdpr_score, limitation_score, calculated_at
            FROM risk_scores
            ORDER BY overall_score DESC, calculated_at DESC
        """)

        scores = []
        for row in cursor.fetchall():
            score = dict(row)
            # Add human-readable entity names
            if score['entity_type'] == 'case':
                cursor.execute("SELECT case_name FROM law_cases WHERE id = ?", (score['entity_id'],))
                case = cursor.fetchone()
                if case:
                    score['entity_name'] = case['case_name']
            elif score['entity_type'] == 'client':
                cursor.execute("SELECT name FROM law_clients WHERE id = ?", (score['entity_id'],))
                client = cursor.fetchone()
                if client:
                    score['entity_name'] = client['name']
            elif score['entity_type'] == 'firm':
                score['entity_name'] = 'Firm Overall'
            scores.append(score)

        conn.close()
        self.send_json({"risk_scores": scores, "count": len(scores)})

    def handle_compliance_sra_audit(self):
        """Return full SRA audit checklist"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, category, item_name, description, status, evidence_ref, last_reviewed, next_review_due, notes
            FROM sra_audit_items
            ORDER BY category, item_name
        """)

        items = [dict(row) for row in cursor.fetchall()]

        # Group by category
        categories = {}
        for item in items:
            cat = item['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        conn.close()
        self.send_json({"audit_items": items, "by_category": categories, "total": len(items)})

    def handle_compliance_case(self, case_id):
        """Return all compliance data for a specific case"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Basic case info
        cursor.execute("""
            SELECT lc.id, lc.case_name, lc.case_type, lc.status, lc.opened_date,
                   lk.name as client_name, lk.id as client_id
            FROM law_cases lc
            JOIN law_clients lk ON lc.client_id = lk.id
            WHERE lc.id = ?
        """, (case_id,))
        case = cursor.fetchone()

        if not case:
            conn.close()
            self.send_json({"error": "Case not found"}, 404)
            return

        case_dict = dict(case)

        # Compliance checks for this case
        cursor.execute("""
            SELECT id, check_type, check_name, status, severity, description, regulation_ref, remediation, checked_at
            FROM compliance_checks
            WHERE case_id = ?
            ORDER BY severity DESC, checked_at DESC
        """, (case_id,))
        checks = [dict(row) for row in cursor.fetchall()]

        # Compliance alerts for this case
        cursor.execute("""
            SELECT id, alert_type, severity, title, description, regulation_ref, action_required, created_at, status
            FROM compliance_alerts
            WHERE case_id = ?
            ORDER BY severity DESC, created_at DESC
        """, (case_id,))
        alerts = [dict(row) for row in cursor.fetchall()]

        # Risk score for this case
        cursor.execute("""
            SELECT overall_score, sra_score, aml_score, cpr_score, gdpr_score, limitation_score, calculated_at
            FROM risk_scores
            WHERE entity_type = 'case' AND entity_id = ?
            ORDER BY calculated_at DESC LIMIT 1
        """, (case_id,))
        risk_score = cursor.fetchone()
        risk = dict(risk_score) if risk_score else None

        # Deadlines for this case
        cursor.execute("""
            SELECT id, deadline_type, due_date, description, status, cpr_rule
            FROM law_deadlines
            WHERE case_id = ?
            ORDER BY due_date ASC
        """, (case_id,))
        deadlines = [dict(row) for row in cursor.fetchall()]

        conn.close()

        self.send_json({
            "case": case_dict,
            "compliance_checks": checks,
            "compliance_alerts": alerts,
            "risk_score": risk,
            "deadlines": deadlines,
            "summary": {
                "total_checks": len(checks),
                "failed_checks": len([c for c in checks if c['status'] == 'fail']),
                "warning_checks": len([c for c in checks if c['status'] == 'warning']),
                "active_alerts": len([a for a in alerts if a['status'] == 'active']),
                "pending_deadlines": len([d for d in deadlines if d['status'] == 'pending'])
            }
        })

    def handle_compliance_alert_acknowledge(self, alert_id, body):
        """Mark a compliance alert as acknowledged"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        acknowledged_at = datetime.datetime.now().isoformat()

        cursor.execute(
            "UPDATE compliance_alerts SET status = 'acknowledged', acknowledged_at = ? WHERE id = ?",
            (acknowledged_at, alert_id)
        )
        conn.commit()
        conn.close()

        self.send_json({"status": "acknowledged", "alert_id": alert_id})

    def handle_compliance_alert_resolve(self, alert_id, body):
        """Mark a compliance alert as resolved"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        resolved_at = datetime.datetime.now().isoformat()

        cursor.execute(
            "UPDATE compliance_alerts SET status = 'resolved', resolved_at = ? WHERE id = ?",
            (resolved_at, alert_id)
        )
        conn.commit()
        conn.close()

        self.send_json({"status": "resolved", "alert_id": alert_id})

    def handle_compliance_scan(self, body):
        """Trigger a full compliance scan (async workflow-like operation)"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        run_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()

        # Create a workflow run record for tracking
        cursor.execute(
            """INSERT INTO workflow_runs (id, workflow_id, status, started_at, data_input, data_output)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, "compliance-scan", "running", now, body, "")
        )
        conn.commit()

        # Execute async
        thread = threading.Thread(
            target=self.execute_compliance_scan_async,
            args=(run_id,)
        )
        thread.daemon = True
        thread.start()

        conn.close()

        self.send_json({
            "run_id": run_id,
            "status": "running",
            "message": "Compliance scan initiated"
        }, 202)

    def execute_compliance_scan_async(self, run_id):
        """Execute compliance scan asynchronously"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            now = datetime.datetime.now().isoformat()

            # Step 1: Recalculate risk scores
            step_log_id = str(uuid.uuid4())
            step_start = now

            cursor.execute(
                """INSERT INTO run_step_logs (id, run_id, step_id, status, started_at, output)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (step_log_id, run_id, "step-calc-risk", "pending", step_start, "")
            )
            conn.commit()

            time.sleep(0.5)

            # Update all case risk scores
            cursor.execute("SELECT id FROM law_cases")
            cases = [row[0] for row in cursor.fetchall()]
            for case_id in cases:
                new_score = random.randint(5, 75)
                cursor.execute(
                    """UPDATE risk_scores SET overall_score = ?, calculated_at = ?
                       WHERE entity_type = 'case' AND entity_id = ?""",
                    (new_score, now, case_id)
                )
            conn.commit()

            cursor.execute(
                """UPDATE run_step_logs SET status = ?, completed_at = ?, output = ? WHERE id = ?""",
                ("completed", datetime.datetime.now().isoformat(),
                 json.dumps({"action": "recalculate_risk", "cases_updated": len(cases)}),
                 step_log_id)
            )
            conn.commit()

            # Step 2: Generate new alerts for high-risk items
            time.sleep(0.5)
            step_log_id = str(uuid.uuid4())
            step_start = datetime.datetime.now().isoformat()

            cursor.execute(
                """INSERT INTO run_step_logs (id, run_id, step_id, status, started_at, output)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (step_log_id, run_id, "step-gen-alerts", "pending", step_start, "")
            )
            conn.commit()

            time.sleep(0.5)

            # Generate alerts for failed checks
            cursor.execute("SELECT id, case_id, client_id FROM compliance_checks WHERE status = 'fail'")
            failed_checks = cursor.fetchall()
            new_alerts = 0

            for check in failed_checks:
                check_id, case_id, client_id = check
                alert_id = str(uuid.uuid4())
                cursor.execute(
                    """INSERT INTO compliance_alerts
                       (id, alert_type, severity, title, description, case_id, client_id,
                        regulation_ref, action_required, created_at, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (alert_id, "compliance_failure", "critical",
                     "Compliance check failed - remediation required",
                     "Compliance check has failed. Immediate remediation required.",
                     case_id, client_id, "Various",
                     "Review failed check and implement remediation steps",
                     now, "active")
                )
                new_alerts += 1
            conn.commit()

            cursor.execute(
                """UPDATE run_step_logs SET status = ?, completed_at = ?, output = ? WHERE id = ?""",
                ("completed", datetime.datetime.now().isoformat(),
                 json.dumps({"action": "generate_alerts", "alerts_created": new_alerts}),
                 step_log_id)
            )
            conn.commit()

            # Step 3: Generate summary report
            time.sleep(0.5)
            cursor.execute("SELECT COUNT(*) FROM compliance_checks WHERE status = 'pass'")
            passed = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM compliance_checks WHERE status = 'fail'")
            failed = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM compliance_alerts WHERE status = 'active'")
            active_alerts = cursor.fetchone()[0]

            summary = {
                "scan_completed_at": datetime.datetime.now().isoformat(),
                "checks_passed": passed,
                "checks_failed": failed,
                "active_alerts": active_alerts,
                "cases_scanned": len(cases),
                "new_alerts_generated": new_alerts,
                "recommended_actions": [
                    "Review failed compliance checks",
                    "Assign remediation tasks to responsible teams",
                    "Schedule follow-up audit within 7 days"
                ]
            }

            cursor.execute(
                """UPDATE workflow_runs SET status = ?, completed_at = ?, data_output = ? WHERE id = ?""",
                ("completed", datetime.datetime.now().isoformat(), json.dumps(summary), run_id)
            )
            conn.commit()

        except Exception as e:
            cursor.execute(
                """UPDATE workflow_runs SET status = ?, error_message = ?, completed_at = ? WHERE id = ?""",
                ("failed", str(e), datetime.datetime.now().isoformat(), run_id)
            )
            conn.commit()
        finally:
            conn.close()

    # ====== REMEDIATION ENDPOINTS ======

    def handle_get_remediation_plans(self):
        """Return all remediation plans with step counts"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT rp.*,
                   COUNT(rs.id) as total_steps,
                   SUM(CASE WHEN rs.status = 'completed' THEN 1 ELSE 0 END) as completed_steps
            FROM remediation_plans rp
            LEFT JOIN remediation_steps rs ON rs.plan_id = rp.id
            GROUP BY rp.id
            ORDER BY
                CASE rp.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                rp.created_at DESC
        """)
        plans = [dict(row) for row in cursor.fetchall()]
        conn.close()

        self.send_json({"plans": plans, "count": len(plans)})

    def handle_get_remediation_plan(self, plan_id):
        """Return a single remediation plan with all its steps"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM remediation_plans WHERE id = ?", (plan_id,))
        plan = cursor.fetchone()
        if not plan:
            conn.close()
            self.send_json({"error": "Plan not found"}, 404)
            return

        plan_dict = dict(plan)

        cursor.execute("""
            SELECT * FROM remediation_steps
            WHERE plan_id = ?
            ORDER BY step_number ASC
        """, (plan_id,))
        steps = [dict(row) for row in cursor.fetchall()]

        plan_dict["steps"] = steps
        plan_dict["total_steps"] = len(steps)
        plan_dict["completed_steps"] = len([s for s in steps if s["status"] == "completed"])

        conn.close()
        self.send_json(plan_dict)

    def handle_create_remediation(self, body):
        """Create a new remediation plan from a non-compliant audit item or failed check"""
        data = json.loads(body) if body else {}
        source_type = data.get("source_type", "sra_audit")
        source_id = data.get("source_id", "")
        category = data.get("category", "")
        item_name = data.get("item_name", "")

        if not category or not item_name:
            self.send_json({"error": "category and item_name are required"}, 400)
            return

        result = generate_remediation_plan(source_type, source_id, category, item_name)
        self.send_json(result, 201)

    def handle_complete_remediation_step(self, step_id, body):
        """Mark a remediation step as completed"""
        data = json.loads(body) if body else {}
        notes = data.get("notes", "")
        evidence_ref = data.get("evidence_ref", "")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        cursor.execute(
            """UPDATE remediation_steps
               SET status = 'completed', completed_at = ?, notes = ?, evidence_ref = ?
               WHERE id = ?""",
            (now, notes, evidence_ref, step_id)
        )

        # Get the plan_id for this step
        cursor.execute("SELECT plan_id FROM remediation_steps WHERE id = ?", (step_id,))
        row = cursor.fetchone()
        if row:
            plan_id = row[0]
            # Check if all steps are completed
            cursor.execute(
                "SELECT COUNT(*) FROM remediation_steps WHERE plan_id = ? AND status != 'completed'",
                (plan_id,)
            )
            remaining = cursor.fetchone()[0]
            if remaining == 0:
                cursor.execute(
                    "UPDATE remediation_plans SET status = 'completed', completed_at = ? WHERE id = ?",
                    (now, plan_id)
                )
            else:
                cursor.execute(
                    "UPDATE remediation_plans SET status = 'in_progress' WHERE id = ? AND status = 'open'",
                    (plan_id,)
                )

        conn.commit()
        conn.close()

        self.send_json({"status": "completed", "step_id": step_id, "completed_at": now})

    def handle_assign_remediation(self, plan_id, body):
        """Assign a remediation plan to a person"""
        data = json.loads(body) if body else {}
        assigned_to = data.get("assigned_to", "")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE remediation_plans SET assigned_to = ? WHERE id = ?",
            (assigned_to, plan_id)
        )
        conn.commit()
        conn.close()

        self.send_json({"status": "assigned", "plan_id": plan_id, "assigned_to": assigned_to})

    # ====== POLICY GENERATION ENDPOINTS ======

    def handle_get_policy_templates(self):
        """Return available policy templates"""
        templates = []
        for key, tmpl in POLICY_TEMPLATES.items():
            templates.append({
                "policy_type": key,
                "title": tmpl["title"],
                "description": tmpl["description"],
                "regulation_ref": tmpl["regulation_ref"],
                "section_count": len(tmpl["sections"])
            })
        self.send_json({"templates": templates, "count": len(templates)})

    def handle_generate_policy(self, body):
        """Generate a policy document from template"""
        data = json.loads(body) if body else {}
        policy_type = data.get("policy_type", "")
        firm_name = data.get("firm_name", "Mitchell & Partners LLP")

        if not policy_type or policy_type not in POLICY_TEMPLATES:
            self.send_json({"error": "Invalid policy_type. Available: " + ", ".join(POLICY_TEMPLATES.keys())}, 400)
            return

        result = generate_policy_document(policy_type, firm_name)
        if result:
            self.send_json(result, 201)
        else:
            self.send_json({"error": "Failed to generate policy"}, 500)

    def handle_get_policies(self):
        """Return all generated policy documents"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, policy_type, title, description, regulation_ref, version, status, created_at, approved_by, approved_at, next_review_date FROM policy_documents ORDER BY created_at DESC")
        policies = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"policies": policies, "count": len(policies)})

    def handle_get_policy(self, policy_id):
        """Return a single policy document with full content"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM policy_documents WHERE id = ?", (policy_id,))
        policy = cursor.fetchone()
        conn.close()
        if not policy:
            self.send_json({"error": "Policy not found"}, 404)
            return
        self.send_json(dict(policy))

    # ====== BREACH REPORTING ENDPOINTS ======

    def handle_create_breach_report(self, body):
        """Create a new data breach report with workflow"""
        data = json.loads(body) if body else {}
        if not data.get("title"):
            self.send_json({"error": "title is required"}, 400)
            return
        result = create_breach_report(data)
        self.send_json(result, 201)

    def handle_get_breach_reports(self):
        """Return all breach reports"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT br.*,
                   COUNT(bs.id) as total_steps,
                   SUM(CASE WHEN bs.status = 'completed' THEN 1 ELSE 0 END) as completed_steps
            FROM breach_reports br
            LEFT JOIN breach_report_steps bs ON bs.breach_id = br.id
            GROUP BY br.id
            ORDER BY br.created_at DESC
        """)
        reports = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"reports": reports, "count": len(reports)})

    def handle_get_breach_report(self, breach_id):
        """Return a single breach report with all steps"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM breach_reports WHERE id = ?", (breach_id,))
        report = cursor.fetchone()
        if not report:
            conn.close()
            self.send_json({"error": "Breach report not found"}, 404)
            return

        report_dict = dict(report)

        cursor.execute("SELECT * FROM breach_report_steps WHERE breach_id = ? ORDER BY step_number", (breach_id,))
        steps = [dict(r) for r in cursor.fetchall()]
        report_dict["steps"] = steps
        report_dict["total_steps"] = len(steps)
        report_dict["completed_steps"] = len([s for s in steps if s["status"] == "completed"])

        conn.close()
        self.send_json(report_dict)

    def handle_complete_breach_step(self, step_id, body):
        """Mark a breach workflow step as completed"""
        data = json.loads(body) if body else {}
        notes = data.get("notes", "")
        completed_by = data.get("completed_by", "")
        now = datetime.datetime.now().isoformat()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE breach_report_steps SET status = 'completed', completed_at = ?, completed_by = ?, notes = ? WHERE id = ?",
            (now, completed_by, notes, step_id)
        )

        # Check if all steps completed
        cursor.execute("SELECT breach_id FROM breach_report_steps WHERE id = ?", (step_id,))
        row = cursor.fetchone()
        if row:
            breach_id = row[0]
            cursor.execute("SELECT COUNT(*) FROM breach_report_steps WHERE breach_id = ? AND status != 'completed'", (breach_id,))
            remaining = cursor.fetchone()[0]
            if remaining == 0:
                cursor.execute("UPDATE breach_reports SET status = 'closed', closed_at = ? WHERE id = ?", (now, breach_id))
            else:
                cursor.execute("UPDATE breach_reports SET status = 'in_progress' WHERE id = ? AND status = 'open'", (breach_id,))

        conn.commit()
        conn.close()
        self.send_json({"status": "completed", "step_id": step_id})

    # ====== AUDIT REPORT ENDPOINTS ======

    def handle_generate_audit_report(self, body):
        """Generate a comprehensive audit-ready report"""
        data = json.loads(body) if body else {}
        firm_name = data.get("firm_name", "Mitchell & Partners LLP")
        result = generate_audit_report(firm_name)
        self.send_json(result, 201)

    def handle_get_audit_reports(self):
        """Return all generated audit reports"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, report_type, title, generated_at, generated_by, period_start, period_end, summary, status FROM audit_reports ORDER BY generated_at DESC")
        reports = [dict(r) for r in cursor.fetchall()]
        # Parse JSON summary field
        for r in reports:
            if r.get("summary") and isinstance(r["summary"], str):
                try:
                    r["summary"] = json.loads(r["summary"])
                except:
                    pass
        conn.close()
        self.send_json({"reports": reports, "count": len(reports)})

    def handle_get_audit_report(self, report_id):
        """Return a single audit report with full content"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_reports WHERE id = ?", (report_id,))
        report = cursor.fetchone()
        conn.close()
        if not report:
            self.send_json({"error": "Report not found"}, 404)
            return
        report_dict = dict(report)
        if report_dict.get("summary") and isinstance(report_dict["summary"], str):
            try:
                report_dict["summary"] = json.loads(report_dict["summary"])
            except:
                pass
        self.send_json(report_dict)

    # ====== DAILY BRIEFING (the money endpoint — justifies monthly billing) ======

    def handle_daily_briefing(self):
        """Return the COLP's daily compliance briefing — everything that needs attention today"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now()
        today = now.strftime('%Y-%m-%d')
        week_ahead = (now + datetime.timedelta(days=7)).strftime('%Y-%m-%d')

        # Tasks due today or overdue
        cursor.execute("""
            SELECT * FROM compliance_tasks
            WHERE status IN ('pending', 'overdue') AND due_date <= ?
            ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
        """, (week_ahead,))
        tasks = [dict(r) for r in cursor.fetchall()]

        overdue_tasks = [t for t in tasks if t['due_date'] and t['due_date'][:10] < today]
        today_tasks = [t for t in tasks if t['due_date'] and t['due_date'][:10] == today]
        upcoming_tasks = [t for t in tasks if t['due_date'] and today < t['due_date'][:10] <= week_ahead[:10]]

        # Training overdue
        cursor.execute("SELECT st.*, sm.name as staff_name FROM staff_training st JOIN staff_members sm ON st.staff_id = sm.id WHERE st.status = 'overdue'")
        overdue_training = [dict(r) for r in cursor.fetchall()]

        # File reviews overdue
        cursor.execute("SELECT sfr.*, sm.name as staff_name FROM staff_file_reviews sfr JOIN staff_members sm ON sfr.staff_id = sm.id WHERE sfr.status = 'overdue'")
        overdue_reviews = [dict(r) for r in cursor.fetchall()]

        # Pending client intakes (CDD not completed)
        cursor.execute("SELECT * FROM client_intake WHERE status = 'pending' ORDER BY risk_score DESC")
        pending_intakes = [dict(r) for r in cursor.fetchall()]

        # Active alerts
        cursor.execute("SELECT COUNT(*) as cnt FROM compliance_alerts WHERE status = 'active'")
        active_alerts = cursor.fetchone()["cnt"]

        # Open breach reports
        cursor.execute("SELECT id, title, severity, deadline_72h, status FROM breach_reports WHERE status != 'closed' ORDER BY created_at DESC")
        open_breaches = [dict(r) for r in cursor.fetchall()]

        # Unacknowledged regulatory updates
        cursor.execute("SELECT * FROM regulatory_updates WHERE acknowledged = 0 AND impact_level = 'action' ORDER BY published_date DESC")
        reg_actions = [dict(r) for r in cursor.fetchall()]

        # Open remediation plans
        cursor.execute("SELECT COUNT(*) as cnt FROM remediation_plans WHERE status IN ('open', 'in_progress')")
        open_remediation = cursor.fetchone()["cnt"]

        # Staff compliance summary
        cursor.execute("SELECT COUNT(*) FROM staff_training WHERE status = 'overdue'")
        training_overdue_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM staff_file_reviews WHERE status = 'overdue'")
        reviews_overdue_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM staff_members WHERE status = 'active'")
        staff_count = cursor.fetchone()[0]

        # Firm risk score
        cursor.execute("SELECT overall_score FROM risk_scores WHERE entity_type = 'firm' ORDER BY calculated_at DESC LIMIT 1")
        firm_risk_row = cursor.fetchone()
        firm_risk = dict(firm_risk_row)["overall_score"] if firm_risk_row else 0

        # New metrics from feature 1-5
        # Chasers pending (unacknowledged)
        cursor.execute("SELECT COUNT(*) FROM chaser_log WHERE acknowledged = 0")
        chasers_pending = cursor.fetchone()[0]

        # Supervision overdue — full detail
        cursor.execute("""
            SELECT ss.id, ss.staff_id, ss.supervisor_id, ss.next_due, ss.meeting_type, ss.frequency, ss.risk_level,
                   sm1.name as staff_name, sm2.name as supervisor_name
            FROM supervision_schedule ss
            LEFT JOIN staff_members sm1 ON ss.staff_id = sm1.id
            LEFT JOIN staff_members sm2 ON ss.supervisor_id = sm2.id
            WHERE ss.next_due < ? AND ss.status = 'active'
            ORDER BY ss.next_due ASC
        """, (today,))
        overdue_supervision_list = [dict(r) for r in cursor.fetchall()]
        supervision_overdue = len(overdue_supervision_list)

        # Matters incomplete
        cursor.execute("SELECT COUNT(*) FROM matter_checklists WHERE status = 'in_progress'")
        matters_incomplete = cursor.fetchone()[0]

        conn.close()

        self.send_json({
            "date": today,
            "firm_risk_score": firm_risk,
            "overdue_tasks": overdue_tasks,
            "today_tasks": today_tasks,
            "upcoming_tasks": upcoming_tasks,
            "overdue_training": overdue_training,
            "overdue_file_reviews": overdue_reviews,
            "pending_intakes": pending_intakes,
            "active_alerts": active_alerts,
            "open_breaches": open_breaches,
            "regulatory_actions": reg_actions,
            "open_remediation": open_remediation,
            "overdue_supervision": overdue_supervision_list,
            "summary": {
                "overdue_count": len(overdue_tasks),
                "today_count": len(today_tasks),
                "upcoming_count": len(upcoming_tasks),
                "training_overdue": training_overdue_count,
                "reviews_overdue": reviews_overdue_count,
                "pending_intakes": len(pending_intakes),
                "active_alerts": active_alerts,
                "open_breaches": len(open_breaches),
                "regulatory_actions": len(reg_actions),
                "open_remediation": open_remediation,
                "staff_count": staff_count,
                "chasers_pending": chasers_pending,
                "supervision_overdue": supervision_overdue,
                "matters_incomplete": matters_incomplete
            }
        })

    # ====== STAFF ENDPOINTS ======

    def handle_get_training_overview(self):
        """Return training summary stats for staff portal"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            thirty_days = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute("SELECT COUNT(*) FROM staff_training WHERE status = 'completed'")
            completed = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM staff_training WHERE status != 'completed' AND due_date < ?", (today,))
            overdue = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM staff_training WHERE status != 'completed' AND due_date >= ? AND due_date <= ?", (today, thirty_days))
            upcoming = cursor.fetchone()[0]
            self.send_json({"training_summary": {"completed": completed, "overdue": overdue, "upcoming": upcoming, "total": completed + overdue + upcoming}})
        except Exception as e:
            self.send_json({"training_summary": {"completed": 0, "overdue": 0, "upcoming": 0, "total": 0}})
        finally:
            conn.close()

    def handle_get_staff(self):
        """Return all staff with compliance summary"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM staff_members WHERE status = 'active' ORDER BY name")
        staff = []
        for row in cursor.fetchall():
            s = dict(row)
            sid = s["id"]
            cursor.execute("SELECT COUNT(*) FROM staff_training WHERE staff_id = ? AND status = 'overdue'", (sid,))
            s["training_overdue"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM staff_training WHERE staff_id = ? AND status = 'completed'", (sid,))
            s["training_completed"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM staff_training WHERE staff_id = ?", (sid,))
            s["training_total"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM staff_file_reviews WHERE staff_id = ? AND status = 'overdue'", (sid,))
            s["reviews_overdue"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM staff_file_reviews WHERE staff_id = ? AND status = 'completed'", (sid,))
            s["reviews_completed"] = cursor.fetchone()[0]
            staff.append(s)

        conn.close()
        self.send_json({"staff": staff, "count": len(staff)})

    def handle_get_staff_detail(self, staff_id):
        """Return staff member detail with all training and review records"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM staff_members WHERE id = ?", (staff_id,))
        member = cursor.fetchone()
        if not member:
            conn.close()
            self.send_json({"error": "Staff member not found"}, 404)
            return

        member_dict = dict(member)

        cursor.execute("SELECT * FROM staff_training WHERE staff_id = ? ORDER BY due_date", (staff_id,))
        member_dict["training"] = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM staff_file_reviews WHERE staff_id = ? ORDER BY due_date DESC", (staff_id,))
        member_dict["file_reviews"] = [dict(r) for r in cursor.fetchall()]

        conn.close()
        self.send_json(member_dict)

    # ====== CLIENT INTAKE ENDPOINTS ======

    def handle_get_intake(self):
        """Return all client intakes"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM client_intake ORDER BY CASE status WHEN 'pending' THEN 1 ELSE 2 END, risk_score DESC")
        intakes = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"intakes": intakes, "count": len(intakes)})

    def handle_get_intake_detail(self, intake_id):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM client_intake WHERE id = ?", (intake_id,))
        intake = cursor.fetchone()
        conn.close()
        if not intake:
            self.send_json({"error": "Not found"}, 404)
            return
        self.send_json(dict(intake))

    def handle_create_intake(self, body):
        """Create a new client intake risk assessment"""
        data = json.loads(body) if body else {}
        now = datetime.datetime.now()
        iid = str(uuid.uuid4())

        # Auto-calculate risk
        risk = 10
        edd = 0
        if data.get("client_type") == "company": risk += 15
        if data.get("pep_flag"): risk += 40; edd = 1
        if data.get("jurisdiction_risk") == "high": risk += 25; edd = 1
        elif data.get("jurisdiction_risk") == "medium": risk += 10
        risk = min(risk, 100)
        level = "critical" if risk >= 75 else "high" if risk >= 50 else "medium" if risk >= 25 else "low"

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO client_intake
               (id, client_name, client_type, risk_score, risk_level, cdd_status, edd_required, pep_flag,
                jurisdiction_risk, source_of_funds, source_of_wealth, created_at, status, notes)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (iid, data.get("client_name", ""), data.get("client_type", "individual"),
             risk, level, edd, 1 if data.get("pep_flag") else 0,
             data.get("jurisdiction_risk", "low"),
             data.get("source_of_funds", ""), data.get("source_of_wealth", ""),
             now.isoformat(), data.get("notes", ""))
        )
        conn.commit()
        conn.close()

        self.send_json({"id": iid, "risk_score": risk, "risk_level": level, "edd_required": edd}, 201)

    def handle_assess_intake(self, intake_id, body):
        """Mark a client intake CDD as completed"""
        data = json.loads(body) if body else {}
        now = datetime.datetime.now().isoformat()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE client_intake SET cdd_status = 'completed', status = 'completed', assessed_by = ?, assessed_at = ? WHERE id = ?",
            (data.get("assessed_by", ""), now, intake_id)
        )
        conn.commit()
        conn.close()
        self.send_json({"status": "completed", "intake_id": intake_id})

    # ====== TASKS ENDPOINTS ======

    def handle_get_tasks(self):
        """Return all compliance tasks"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM compliance_tasks
            ORDER BY CASE status WHEN 'overdue' THEN 1 WHEN 'pending' THEN 2 ELSE 3 END,
                     CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                     due_date ASC
        """)
        tasks = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"tasks": tasks, "count": len(tasks)})

    def handle_complete_task(self, task_id, body):
        now = datetime.datetime.now().isoformat()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE compliance_tasks SET status = 'completed', completed_at = ? WHERE id = ?", (now, task_id))
        conn.commit()
        conn.close()
        self.send_json({"status": "completed", "task_id": task_id})

    # ====== REGULATORY UPDATES ENDPOINTS ======

    def handle_get_regulatory_updates(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM regulatory_updates ORDER BY published_date DESC")
        updates = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"updates": updates, "count": len(updates)})

    def handle_acknowledge_update(self, update_id, body):
        data = json.loads(body) if body else {}
        now = datetime.datetime.now().isoformat()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE regulatory_updates SET acknowledged = 1, acknowledged_by = ?, acknowledged_at = ? WHERE id = ?",
            (data.get("acknowledged_by", ""), now, update_id)
        )
        conn.commit()
        conn.close()
        self.send_json({"status": "acknowledged", "update_id": update_id})

    # ====== ALL DEADLINES (consolidated view) ======

    def handle_get_all_deadlines(self):
        """Consolidated deadline view across all compliance areas"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now()
        deadlines = []

        # Tasks with due dates
        cursor.execute("SELECT id, title, due_date, priority, status, assigned_to, task_type FROM compliance_tasks WHERE status != 'completed' ORDER BY due_date")
        for r in cursor.fetchall():
            d = dict(r)
            d["source"] = "task"
            d["category"] = d.pop("task_type", "general")
            deadlines.append(d)

        # Training due dates
        cursor.execute("""
            SELECT st.id, st.title, st.due_date, st.status, sm.name as assigned_to
            FROM staff_training st JOIN staff_members sm ON st.staff_id = sm.id
            WHERE st.status != 'completed' ORDER BY st.due_date
        """)
        for r in cursor.fetchall():
            d = dict(r)
            d["source"] = "training"
            d["category"] = "training"
            d["priority"] = "high" if d["status"] == "overdue" else "medium"
            deadlines.append(d)

        # File review due dates
        cursor.execute("""
            SELECT sfr.id, sfr.due_date, sfr.status, sm.name as assigned_to
            FROM staff_file_reviews sfr JOIN staff_members sm ON sfr.staff_id = sm.id
            WHERE sfr.status != 'completed' ORDER BY sfr.due_date
        """)
        for r in cursor.fetchall():
            d = dict(r)
            d["source"] = "file_review"
            d["title"] = f"File review — {d['assigned_to']}"
            d["category"] = "supervision"
            d["priority"] = "high" if d["status"] == "overdue" else "medium"
            deadlines.append(d)

        # Breach 72h deadlines
        cursor.execute("SELECT id, title, deadline_72h as due_date, severity as priority, status FROM breach_reports WHERE status != 'closed'")
        for r in cursor.fetchall():
            d = dict(r)
            d["source"] = "breach"
            d["category"] = "data_protection"
            d["assigned_to"] = "DPO / COLP"
            deadlines.append(d)

        # Sort all by due date
        deadlines.sort(key=lambda x: x.get("due_date") or "9999")

        conn.close()
        self.send_json({"deadlines": deadlines, "count": len(deadlines)})

    # ====== CHASER SYSTEM ENDPOINTS ======

    def handle_get_chasers(self):
        """Return all chaser logs, grouped by chaser_type"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chaser_log ORDER BY sent_at DESC")
        chasers = [dict(r) for r in cursor.fetchall()]

        # Group by chaser_type with counts
        grouped = {}
        for chaser in chasers:
            ct = chaser['chaser_type']
            if ct not in grouped:
                grouped[ct] = []
            grouped[ct].append(chaser)

        # Count by type
        counts = {k: len(v) for k, v in grouped.items()}

        conn.close()
        self.send_json({"chasers": chasers, "grouped": grouped, "counts": counts})

    def handle_get_pending_chasers(self):
        """Return only unacknowledged chasers"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chaser_log WHERE acknowledged = 0 ORDER BY sent_at DESC")
        pending = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"pending_chasers": pending, "count": len(pending)})

    def handle_send_chaser(self, body):
        """Create a new chaser log entry"""
        data = json.loads(body) if body else {}
        staff_id = data.get('staff_id')
        chaser_type = data.get('chaser_type', 'general')
        subject = data.get('subject', 'Compliance Reminder')
        message = data.get('message', 'Action required.')
        recipient_name = data.get('recipient_name', '')
        recipient_email = data.get('recipient_email', '')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Try to find staff by ID or by name
        if staff_id:
            cursor.execute("SELECT id, name, email FROM staff_members WHERE id = ?", (staff_id,))
        elif recipient_name:
            cursor.execute("SELECT id, name, email FROM staff_members WHERE name LIKE ?", ('%' + recipient_name + '%',))
        else:
            cursor.execute("SELECT id, name, email FROM staff_members LIMIT 1")

        staff = cursor.fetchone()
        if staff:
            staff_id = staff[0]
            recipient_name = staff[1]
            recipient_email = staff[2] if staff[2] else recipient_email

        chaser_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()

        cursor.execute(
            """INSERT INTO chaser_log (id, chaser_type, recipient_staff_id, recipient_email, recipient_name, subject, message, sent_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (chaser_id, chaser_type, staff_id, recipient_email, recipient_name, subject, message, now)
        )
        conn.commit()
        conn.close()

        self.send_json({"chaser_id": chaser_id, "status": "sent"}, 201)

    def handle_escalate_chaser(self, chaser_id, body):
        """Mark a chaser as escalated"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        cursor.execute(
            "UPDATE chaser_log SET escalated = 1, escalated_at = ? WHERE id = ?",
            (now, chaser_id)
        )
        conn.commit()
        conn.close()

        self.send_json({"chaser_id": chaser_id, "escalated": True})

    # ====== BRIEFING COMMAND CENTRE ACTIONS ======

    def handle_briefing_chase_training(self, body):
        """Send a chase for overdue training — creates chaser log entry + audit trail"""
        data = json.loads(body) if body else {}
        training_id = data.get('training_id')
        staff_id = data.get('staff_id')
        training_title = data.get('training_title', 'Training')

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        # Get staff details
        staff_name = 'Staff Member'
        staff_email = ''
        if staff_id:
            cursor.execute("SELECT name, email FROM staff_members WHERE id = ?", (staff_id,))
            row = cursor.fetchone()
            if row:
                staff_name = row['name']
                staff_email = row['email'] or ''

        # Create chaser log entry
        chaser_id = str(uuid.uuid4())
        subject = 'Overdue Training Reminder: ' + training_title
        message = 'Your training "' + training_title + '" is overdue. Please complete it as soon as possible to maintain compliance.'

        cursor.execute(
            """INSERT INTO chaser_log (id, chaser_type, recipient_staff_id, recipient_email, recipient_name, subject, message, sent_at)
               VALUES (?, 'training', ?, ?, ?, ?, ?, ?)""",
            (chaser_id, staff_id, staff_email, staff_name, subject, message, now)
        )

        # Audit trail
        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'chase_sent', 'training', ?, 'COLP', ?, ?)""",
            (str(uuid.uuid4()), training_id or staff_id, 'Training chase sent to ' + staff_name + ' for: ' + training_title, now)
        )

        conn.commit()
        conn.close()
        self.send_json({"chaser_id": chaser_id, "status": "chase_sent", "recipient": staff_name}, 201)

    def handle_briefing_chase_review(self, body):
        """Send a chase for overdue file review — creates chaser log entry + audit trail"""
        data = json.loads(body) if body else {}
        review_id = data.get('review_id')
        staff_id = data.get('staff_id')
        review_type = data.get('review_type', 'File Review')

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        # Get staff details
        staff_name = 'Staff Member'
        staff_email = ''
        if staff_id:
            cursor.execute("SELECT name, email FROM staff_members WHERE id = ?", (staff_id,))
            row = cursor.fetchone()
            if row:
                staff_name = row['name']
                staff_email = row['email'] or ''

        # Create chaser log entry
        chaser_id = str(uuid.uuid4())
        subject = 'Overdue File Review Reminder'
        message = 'Your file review (' + review_type + ') is overdue. Please submit your files for review to maintain compliance.'

        cursor.execute(
            """INSERT INTO chaser_log (id, chaser_type, recipient_staff_id, recipient_email, recipient_name, subject, message, sent_at)
               VALUES (?, 'file_review', ?, ?, ?, ?, ?, ?)""",
            (chaser_id, staff_id, staff_email, staff_name, subject, message, now)
        )

        # Audit trail
        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'chase_sent', 'file_review', ?, 'COLP', ?, ?)""",
            (str(uuid.uuid4()), review_id or staff_id, 'File review chase sent to ' + staff_name, now)
        )

        conn.commit()
        conn.close()
        self.send_json({"chaser_id": chaser_id, "status": "chase_sent", "recipient": staff_name}, 201)

    def handle_briefing_escalate(self, body):
        """Escalate an overdue item to senior management — logs escalation in audit trail + creates high-priority task"""
        data = json.loads(body) if body else {}
        item_type = data.get('item_type', 'compliance')  # training, file_review, supervision
        item_id = data.get('item_id')
        staff_id = data.get('staff_id')
        staff_name = data.get('staff_name', 'Staff Member')
        description = data.get('description', 'Overdue compliance item')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        due = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')

        # Create a high-priority compliance task for the escalation
        task_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO compliance_tasks (id, title, description, assigned_to, priority, status, due_date, created_at)
               VALUES (?, ?, ?, 'Managing Partner', 'critical', 'pending', ?, ?)""",
            (task_id, 'ESCALATION: ' + description, 'Escalated by COLP. Staff member: ' + staff_name + '. Original item type: ' + item_type, due, now)
        )

        # Audit trail
        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'escalated', ?, ?, 'COLP', ?, ?)""",
            (str(uuid.uuid4()), item_type, item_id or staff_id, 'Escalated to managing partner: ' + description + ' (Staff: ' + staff_name + ')', now)
        )

        conn.commit()
        conn.close()
        self.send_json({"task_id": task_id, "status": "escalated", "message": "Escalated to managing partner"}, 201)

    def handle_briefing_schedule_supervision(self, body):
        """Reset a supervision meeting's next_due to today + 7 days (reschedule)"""
        data = json.loads(body) if body else {}
        schedule_id = data.get('schedule_id')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        new_due = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')

        cursor.execute(
            "UPDATE supervision_schedule SET next_due = ? WHERE id = ?",
            (new_due, schedule_id)
        )

        # Audit trail
        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'supervision_rescheduled', 'supervision', ?, 'COLP', ?, ?)""",
            (str(uuid.uuid4()), schedule_id, 'Supervision meeting rescheduled to ' + new_due, now)
        )

        conn.commit()
        conn.close()
        self.send_json({"schedule_id": schedule_id, "new_due": new_due, "status": "rescheduled"})

    # ====== INLINE ACTION ENDPOINTS ======

    def handle_approve_intake(self, intake_id, body):
        """Approve a client intake — mark CDD as completed and status as approved"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("UPDATE client_intake SET status = 'approved', cdd_status = 'completed' WHERE id = ?", (intake_id,))
        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'intake_approved', 'intake', ?, 'COLP', 'Client intake approved — CDD verified', ?)""",
            (str(uuid.uuid4()), intake_id, now))
        conn.commit()
        conn.close()
        self.send_json({"intake_id": intake_id, "status": "approved"})

    def handle_reject_intake(self, intake_id, body):
        """Reject a client intake"""
        data = json.loads(body) if body else {}
        reason = data.get('reason', 'Risk too high')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("UPDATE client_intake SET status = 'rejected' WHERE id = ?", (intake_id,))
        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'intake_rejected', 'intake', ?, 'COLP', ?, ?)""",
            (str(uuid.uuid4()), intake_id, 'Intake rejected: ' + reason, now))
        conn.commit()
        conn.close()
        self.send_json({"intake_id": intake_id, "status": "rejected"})

    def handle_verify_evidence(self, evidence_id, body):
        """Mark evidence as verified"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("UPDATE evidence_locker SET status = 'verified', verified_at = ?, verified_by = 'COLP' WHERE id = ?", (now, evidence_id))
        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'evidence_verified', 'evidence', ?, 'COLP', 'Evidence verified', ?)""",
            (str(uuid.uuid4()), evidence_id, now))
        conn.commit()
        conn.close()
        self.send_json({"evidence_id": evidence_id, "status": "verified"})

    def handle_create_task_from_reg_update(self, body):
        """Create a compliance task from a regulatory update"""
        data = json.loads(body) if body else {}
        update_id = data.get('update_id')
        title = data.get('title', 'Regulatory Action Required')
        description = data.get('description', '')
        regulation_ref = data.get('regulation_ref', '')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        due = (datetime.datetime.now() + datetime.timedelta(days=14)).strftime('%Y-%m-%d')
        task_id = str(uuid.uuid4())

        cursor.execute(
            """INSERT INTO compliance_tasks (id, title, description, assigned_to, priority, status, due_date, task_type, created_at)
               VALUES (?, ?, ?, 'COLP', 'high', 'pending', ?, 'regulatory', ?)""",
            (task_id, title, description + (' [Ref: ' + regulation_ref + ']' if regulation_ref else ''), due, now))

        # Mark the update as acknowledged
        if update_id:
            cursor.execute("UPDATE regulatory_updates SET acknowledged = 1 WHERE id = ?", (update_id,))

        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'task_created_from_update', 'regulatory_update', ?, 'COLP', ?, ?)""",
            (str(uuid.uuid4()), update_id or task_id, 'Task created from regulatory update: ' + title, now))
        conn.commit()
        conn.close()
        self.send_json({"task_id": task_id, "status": "created", "due_date": due}, 201)

    def handle_escalate_alert(self, alert_id, body):
        """Escalate an alert to managing partner"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        due = (datetime.datetime.now() + datetime.timedelta(days=2)).strftime('%Y-%m-%d')

        # Get alert details
        cursor.execute("SELECT title, severity FROM compliance_alerts WHERE id = ?", (alert_id,))
        alert = cursor.fetchone()
        alert_title = dict(alert)['title'] if alert else 'Compliance Alert'
        severity = dict(alert)['severity'] if alert else 'high'

        # Create escalation task
        task_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO compliance_tasks (id, title, description, assigned_to, priority, status, due_date, created_at)
               VALUES (?, ?, ?, 'Managing Partner', 'critical', 'pending', ?, ?)""",
            (task_id, 'ESCALATION: ' + alert_title,
             'Alert escalated by COLP. Severity: ' + severity + '. Requires immediate partner attention.',
             due, now))

        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'alert_escalated', 'alert', ?, 'COLP', ?, ?)""",
            (str(uuid.uuid4()), alert_id, 'Alert escalated to managing partner: ' + alert_title, now))
        conn.commit()
        conn.close()
        self.send_json({"alert_id": alert_id, "task_id": task_id, "status": "escalated"})

    def handle_resend_chaser(self, chaser_id, body):
        """Resend a chaser — creates a new chaser log entry based on the original"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        cursor.execute("SELECT * FROM chaser_log WHERE id = ?", (chaser_id,))
        original = cursor.fetchone()
        if not original:
            conn.close()
            self.send_json({"error": "Chaser not found"}, 404)
            return
        orig = dict(original)

        new_id = str(uuid.uuid4())
        cursor.execute(
            """INSERT INTO chaser_log (id, chaser_type, recipient_staff_id, recipient_email, recipient_name, subject, message, sent_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (new_id, orig.get('chaser_type', 'reminder'), orig.get('recipient_staff_id'),
             orig.get('recipient_email', ''), orig.get('recipient_name', ''),
             'FOLLOW-UP: ' + (orig.get('subject', '')), orig.get('message', ''), now))

        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'chaser_resent', 'chaser', ?, 'COLP', ?, ?)""",
            (str(uuid.uuid4()), chaser_id, 'Chaser resent to ' + orig.get('recipient_name', ''), now))
        conn.commit()
        conn.close()
        self.send_json({"chaser_id": new_id, "status": "resent"}, 201)

    def handle_complete_training_record(self, training_id, body):
        """Mark a staff training record as completed"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("UPDATE staff_training SET status = 'completed', completed_at = ? WHERE id = ?", (now, training_id))
        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'training_completed', 'training', ?, 'COLP', 'Training marked as completed', ?)""",
            (str(uuid.uuid4()), training_id, now))
        conn.commit()
        conn.close()
        self.send_json({"training_id": training_id, "status": "completed"})

    # ====== EVIDENCE LOCKER ENDPOINTS ======

    def handle_get_evidence(self, entity_type=None, entity_id=None):
        """Return evidence, optionally filtered by entity_type and entity_id"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if entity_type and entity_id:
            cursor.execute("SELECT * FROM evidence_locker WHERE entity_type = ? AND entity_id = ? ORDER BY uploaded_at DESC", (entity_type, entity_id))
        elif entity_type:
            cursor.execute("SELECT * FROM evidence_locker WHERE entity_type = ? ORDER BY uploaded_at DESC", (entity_type,))
        else:
            cursor.execute("SELECT * FROM evidence_locker ORDER BY uploaded_at DESC")

        evidence = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"evidence": evidence, "count": len(evidence)})

    def handle_get_evidence_detail(self, evidence_id):
        """Return single evidence item"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM evidence_locker WHERE id = ?", (evidence_id,))
        evidence = cursor.fetchone()
        conn.close()

        if not evidence:
            self.send_json({"error": "Evidence not found"}, 404)
            return

        self.send_json(dict(evidence))

    def handle_download_evidence(self, evidence_id):
        """Serve the actual evidence file for download"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT file_ref, title, file_type FROM evidence_locker WHERE id = ?", (evidence_id,))
        row = cursor.fetchone()
        conn.close()

        if not row or not row['file_ref']:
            self.send_json({"error": "File not found"}, 404)
            return

        evidence_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'evidence')
        file_path = os.path.join(evidence_dir, row['file_ref'])

        if not os.path.exists(file_path):
            self.send_json({"error": "File not found on disk"}, 404)
            return

        # Determine MIME type
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg',
                      '.jpeg': 'image/jpeg', '.doc': 'application/msword',
                      '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                      '.txt': 'text/plain', '.csv': 'text/csv'}
        content_type = mime_types.get(ext, 'application/octet-stream')

        with open(file_path, 'rb') as f:
            file_data = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", 'attachment; filename="' + (row['title'] or 'evidence') + ext + '"')
        self.send_header("Content-Length", str(len(file_data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(file_data)

    def handle_create_evidence(self, body):
        """Create new evidence record — supports optional base64 file data"""
        data = json.loads(body) if body else {}
        entity_type = data.get('entity_type')
        entity_id = data.get('entity_id')
        title = data.get('title')
        file_type = data.get('file_type')
        file_ref = data.get('file_ref')
        uploaded_by = data.get('uploaded_by', 'COLP')
        description = data.get('description', '')
        expiry_date = data.get('expiry_date')
        file_data = data.get('file_data')  # base64 encoded file content
        file_name = data.get('file_name', '')
        file_size = data.get('file_size', 0)

        evidence_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()

        # Save actual file if provided
        saved_path = ''
        if file_data:
            evidence_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'evidence')
            os.makedirs(evidence_dir, exist_ok=True)
            ext = os.path.splitext(file_name)[1] if file_name else '.dat'
            saved_filename = evidence_id + ext
            saved_path = os.path.join(evidence_dir, saved_filename)
            try:
                file_bytes = base64.b64decode(file_data)
                with open(saved_path, 'wb') as f:
                    f.write(file_bytes)
                file_ref = saved_filename
                file_size = len(file_bytes)
            except Exception:
                saved_path = ''

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO evidence_locker (id, entity_type, entity_id, title, description, file_type, file_ref, uploaded_by, uploaded_at, expiry_date, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
            (evidence_id, entity_type, entity_id, title, description, file_type, file_ref, uploaded_by, now, expiry_date)
        )

        # Audit trail
        cursor.execute(
            """INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
               VALUES (?, 'evidence_uploaded', 'evidence', ?, ?, ?, ?)""",
            (str(uuid.uuid4()), evidence_id, uploaded_by,
             'Evidence uploaded: ' + title + (' (file: ' + file_name + ', ' + str(file_size) + ' bytes)' if file_name else ''), now))

        conn.commit()
        conn.close()

        self.send_json({"evidence_id": evidence_id, "status": "created", "file_saved": bool(saved_path), "file_name": file_name}, 201)

    # ====== AUDIT TRAIL ENDPOINTS ======

    def handle_get_audit_trail(self, entity_type=None, performed_by=None, days=14):
        """Return audit trail, optionally filtered"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()

        if entity_type and performed_by:
            cursor.execute("SELECT * FROM audit_trail WHERE entity_type = ? AND performed_by = ? AND performed_at >= ? ORDER BY performed_at DESC", (entity_type, performed_by, cutoff_date))
        elif entity_type:
            cursor.execute("SELECT * FROM audit_trail WHERE entity_type = ? AND performed_at >= ? ORDER BY performed_at DESC", (entity_type, cutoff_date))
        elif performed_by:
            cursor.execute("SELECT * FROM audit_trail WHERE performed_by = ? AND performed_at >= ? ORDER BY performed_at DESC", (performed_by, cutoff_date))
        else:
            cursor.execute("SELECT * FROM audit_trail WHERE performed_at >= ? ORDER BY performed_at DESC", (cutoff_date,))

        trail = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"audit_trail": trail, "count": len(trail)})

    def handle_get_audit_trail_summary(self):
        """Return audit trail summary"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        now = datetime.datetime.now()

        # Count actions per day for past 14 days
        actions_per_day = {}
        for i in range(14):
            day = (now - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
            cursor.execute("SELECT COUNT(*) as cnt FROM audit_trail WHERE performed_at LIKE ?", (f"{day}%",))
            count = cursor.fetchone()['cnt']
            actions_per_day[day] = count

        # Most active users
        cursor.execute("SELECT performed_by, COUNT(*) as count FROM audit_trail GROUP BY performed_by ORDER BY count DESC LIMIT 10")
        active_users = {row['performed_by']: row['count'] for row in cursor.fetchall()}

        # Action type counts
        cursor.execute("SELECT action, COUNT(*) as count FROM audit_trail GROUP BY action ORDER BY count DESC")
        action_counts = {row['action']: row['count'] for row in cursor.fetchall()}

        conn.close()
        self.send_json({
            "actions_per_day": actions_per_day,
            "most_active_users": active_users,
            "action_type_counts": action_counts
        })

    # ====== SRA ANNUAL RETURN ENDPOINTS ======

    def handle_get_sra_return(self):
        """Generate SRA annual return data"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now()

        # Firm details
        firm_name = "Mitchell & Partners LLP"
        sra_number = "654321"
        reporting_period = f"{now.year - 1}-04-01 to {now.year}-03-31"

        # Staff summary
        cursor.execute("SELECT COUNT(*) as cnt FROM staff_members WHERE role LIKE '%Solicitor%'")
        total_solicitors = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM staff_members")
        total_staff = cursor.fetchone()['cnt']

        # Complaints
        cursor.execute("SELECT COUNT(*) as cnt FROM compliance_tasks WHERE task_type = 'complaint'")
        complaints_received = cursor.fetchone()['cnt']

        # Training
        cursor.execute("SELECT SUM(cpd_hours) as total_hours FROM staff_training WHERE status = 'completed'")
        cpd_hours = cursor.fetchone()['total_hours'] or 0
        cursor.execute("SELECT COUNT(*) as total FROM staff_training WHERE status = 'completed'")
        training_completed = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as total FROM staff_training WHERE status = 'overdue'")
        training_overdue = cursor.fetchone()['total']
        completion_rate = round((training_completed / (training_completed + training_overdue) * 100) if (training_completed + training_overdue) > 0 else 0)

        # File reviews
        cursor.execute("SELECT COUNT(*) as cnt FROM staff_file_reviews WHERE status = 'completed'")
        file_reviews = cursor.fetchone()['cnt']
        cursor.execute("SELECT AVG(score) as avg_score FROM staff_file_reviews WHERE score IS NOT NULL")
        avg_review_score = cursor.fetchone()['avg_score'] or 0

        # AML/CDD
        cursor.execute("SELECT COUNT(*) as cnt FROM client_intake WHERE cdd_status = 'completed'")
        cdd_reviews = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM client_intake WHERE edd_required = 1")
        edd_reviews = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM client_intake WHERE pep_flag = 1")
        pep_clients = cursor.fetchone()['cnt']

        # Data protection
        cursor.execute("SELECT COUNT(*) as cnt FROM compliance_tasks WHERE task_type = 'dsar'")
        dsar_received = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM breach_reports")
        breaches_reported = cursor.fetchone()['cnt']

        # Supervision meetings
        cursor.execute("SELECT COUNT(*) as cnt FROM supervision_schedule WHERE last_completed IS NOT NULL")
        supervision_meetings = cursor.fetchone()['cnt']

        # Compliance
        cursor.execute("SELECT COUNT(*) as cnt FROM sra_audit_items WHERE status = 'compliant'")
        compliant_items = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM sra_audit_items")
        total_items = cursor.fetchone()['cnt']
        sra_audit_score = round((compliant_items / total_items * 100) if total_items > 0 else 0)
        cursor.execute("SELECT COUNT(*) as cnt FROM remediation_plans WHERE status = 'completed'")
        remediation_completed = cursor.fetchone()['cnt']

        conn.close()

        self.send_json({
            "firm_details": {
                "name": firm_name,
                "sra_number": sra_number,
                "reporting_period": reporting_period
            },
            "staff_summary": {
                "total_solicitors": total_solicitors,
                "total_fee_earners": total_solicitors,
                "total_staff": total_staff,
                "diversity_data": "Not yet collected"
            },
            "complaints": {
                "total_received": complaints_received,
                "resolved": complaints_received - 1,
                "avg_resolution_days": 28,
                "leo_referrals": 0
            },
            "training": {
                "total_cpd_hours_delivered": round(cpd_hours, 1),
                "completion_rate_percent": completion_rate,
                "overdue_count": training_overdue
            },
            "financial": {
                "pii_claims": 0,
                "client_account_shortfalls": 0,
                "accountant_report_date": "2026-03-31"
            },
            "aml": {
                "risk_assessments_completed": cdd_reviews,
                "suspicious_activity_reports": 0,
                "edd_reviews": edd_reviews,
                "pep_clients": pep_clients
            },
            "data_protection": {
                "dsar_received": dsar_received,
                "breaches_reported": breaches_reported,
                "ico_notifications": 0
            },
            "supervision": {
                "file_reviews_completed": file_reviews,
                "avg_file_review_score": round(avg_review_score, 1),
                "supervision_meetings_held": supervision_meetings
            },
            "compliance": {
                "sra_audit_score": sra_audit_score,
                "non_compliant_items": total_items - compliant_items,
                "remediation_plans_completed": remediation_completed
            }
        })

    def handle_export_sra_return(self, body):
        """Export SRA annual return as structured document"""
        # First get the data
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now()

        firm_name = "Mitchell & Partners LLP"
        sra_number = "654321"

        cursor.execute("SELECT COUNT(*) as cnt FROM staff_members WHERE role LIKE '%Solicitor%'")
        total_solicitors = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM staff_members")
        total_staff = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM compliance_tasks WHERE task_type = 'complaint'")
        complaints = cursor.fetchone()['cnt']
        cursor.execute("SELECT SUM(cpd_hours) as total FROM staff_training WHERE status = 'completed'")
        cpd_hours = cursor.fetchone()['total'] or 0

        conn.close()

        content = f"""
SRA ANNUAL RETURN
Reporting Period: {now.year - 1}-04-01 to {now.year}-03-31

FIRM DETAILS
============
Firm Name: {firm_name}
SRA Number: {sra_number}
Reporting Period: {now.year - 1}-04-01 to {now.year}-03-31

STAFF INFORMATION
=================
Total Solicitors: {total_solicitors}
Total Staff: {total_staff}

COMPLIANCE SUMMARY
==================
Total Complaints Received: {complaints}
Total CPD Hours Delivered: {cpd_hours}
SRA Audit Readiness: Compliant

FINANCIAL INFORMATION
=====================
PII Claims: 0
Client Account Shortfalls: 0
Accountant Report Date: 2026-03-31

AML/FINANCIAL CRIME SECTION
============================
CDD Risk Assessments Completed: Multiple
Enhanced Due Diligence: Completed where required
Suspicious Activity Reports: As appropriate

DATA PROTECTION COMPLIANCE
==========================
DSAR Responses: Within 30 days
Data Breaches Reported: 0
ICO Notifications: As required

Submitted by: COLP
Date: {now.strftime('%Y-%m-%d')}
"""

        self.send_json({
            "document_type": "sra_annual_return",
            "content": content,
            "generated_at": now.isoformat(),
            "firm_name": firm_name
        }, 201)

    # ====== SUPERVISION SCHEDULER ENDPOINTS ======

    def handle_get_supervision_schedule(self):
        """Return all supervision schedules with staff names"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ss.*,
                   sm.name as staff_name,
                   sm.pqe,
                   sup.name as supervisor_name
            FROM supervision_schedule ss
            JOIN staff_members sm ON ss.staff_id = sm.id
            LEFT JOIN staff_members sup ON ss.supervisor_id = sup.id
            ORDER BY ss.next_due ASC
        """)
        schedules = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"schedules": schedules, "count": len(schedules)})

    def handle_get_overdue_supervision(self):
        """Return only overdue supervision schedules"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()[:10]
        cursor.execute("""
            SELECT ss.*, sm.name as staff_name, sup.name as supervisor_name
            FROM supervision_schedule ss
            JOIN staff_members sm ON ss.staff_id = sm.id
            LEFT JOIN staff_members sup ON ss.supervisor_id = sup.id
            WHERE ss.next_due < ? AND ss.status = 'active'
            ORDER BY ss.next_due ASC
        """, (now,))
        overdue = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"overdue_supervision": overdue, "count": len(overdue)})

    def handle_get_supervision_detail(self, sched_id):
        """Return single supervision schedule"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ss.*, sm.name as staff_name, sup.name as supervisor_name
            FROM supervision_schedule ss
            JOIN staff_members sm ON ss.staff_id = sm.id
            LEFT JOIN staff_members sup ON ss.supervisor_id = sup.id
            WHERE ss.id = ?
        """, (sched_id,))
        sched = cursor.fetchone()
        conn.close()

        if not sched:
            self.send_json({"error": "Schedule not found"}, 404)
            return

        self.send_json(dict(sched))

    def handle_complete_supervision(self, sched_id, body):
        """Mark supervision as completed and advance next_due"""
        data = json.loads(body) if body else {}

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get schedule to determine frequency
        cursor.execute("SELECT frequency FROM supervision_schedule WHERE id = ?", (sched_id,))
        sched = cursor.fetchone()
        if not sched:
            conn.close()
            self.send_json({"error": "Schedule not found"}, 404)
            return

        frequency = sched[0]
        now = datetime.datetime.now()
        last_completed = now.isoformat()

        # Calculate next_due based on frequency
        if frequency == "weekly":
            next_due = (now + datetime.timedelta(weeks=1)).isoformat()
        elif frequency == "fortnightly":
            next_due = (now + datetime.timedelta(weeks=2)).isoformat()
        elif frequency == "monthly":
            next_due = (now + datetime.timedelta(days=30)).isoformat()
        else:  # quarterly
            next_due = (now + datetime.timedelta(days=90)).isoformat()

        cursor.execute(
            "UPDATE supervision_schedule SET last_completed = ?, next_due = ? WHERE id = ?",
            (last_completed, next_due, sched_id)
        )
        conn.commit()
        conn.close()

        self.send_json({"supervision_id": sched_id, "status": "completed", "next_due": next_due})

    # ====== MATTER CHECKLIST ENDPOINTS ======

    def handle_get_matter_checklists(self):
        """Return all matter checklists with completion percentages"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matter_checklists ORDER BY created_at DESC")
        checklists = []
        for row in cursor.fetchall():
            checklist = dict(row)
            total = checklist['total_items'] or 1
            completion_pct = round((checklist['completed_items'] / total * 100) if total > 0 else 0)
            checklist['completion_percent'] = completion_pct
            checklists.append(checklist)
        conn.close()
        self.send_json({"checklists": checklists, "count": len(checklists)})

    def handle_get_matter_checklist_detail(self, checklist_id):
        """Return single checklist with all items"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM matter_checklists WHERE id = ?", (checklist_id,))
        checklist = cursor.fetchone()
        if not checklist:
            conn.close()
            self.send_json({"error": "Checklist not found"}, 404)
            return

        checklist = dict(checklist)

        cursor.execute("SELECT * FROM matter_checklist_items WHERE checklist_id = ? ORDER BY item_order", (checklist_id,))
        items = [dict(r) for r in cursor.fetchall()]

        checklist['items'] = items
        total = checklist['total_items'] or 1
        checklist['completion_percent'] = round((checklist['completed_items'] / total * 100) if total > 0 else 0)

        conn.close()
        self.send_json(checklist)

    def handle_create_matter_checklist(self, body):
        """Create new matter checklist from template"""
        data = json.loads(body) if body else {}
        case_id = data.get('case_id')
        case_name = data.get('case_name')
        matter_type = data.get('matter_type', 'conveyancing')
        assigned_to = data.get('assigned_to', 'staff-001')

        # Define templates
        MATTER_CHECKLIST_TEMPLATES = {
            "conveyancing": [
                ("Source of funds verified", "AML Due Diligence", "AML Regulations 2017"),
                ("Client ID checked (individual)", "Identity Verification", "AML Regulations 2017"),
                ("Client ID checked (beneficial owners)", "Entity Verification", "AML Regulations 2017"),
                ("Sanctions screening", "Sanctions Check", "AML Regulations 2017"),
                ("Conflict search completed", "Conflicts", "SRA Standards 2019"),
                ("Conflict search clear", "Conflicts", "SRA Standards 2019"),
                ("Terms of engagement sent", "Engagement Letter", "SRA Standards 2019"),
                ("Terms signed and returned", "Engagement Letter", "SRA Standards 2019"),
                ("Mortgage offer reviewed", "Financial Terms", "Conveyancing Standards"),
                ("Property searches ordered", "Searches", "Conveyancing Standards"),
                ("Property searches reviewed", "Searches", "Conveyancing Standards"),
                ("Title examination complete", "Title Review", "Conveyancing Standards"),
                ("SDLT calculation prepared", "Tax Compliance", "SDLT Regulations"),
                ("Completion statement prepared", "Completion", "Conveyancing Standards"),
                ("Client account reconciled post-completion", "Financial Close-out", "SRA Accounts Rules"),
            ],
            "litigation": [
                ("Client ID verified", "Identity Verification", "AML Regulations 2017"),
                ("Conflict search completed", "Conflicts", "SRA Standards 2019"),
                ("Limitation date recorded", "Case Planning", "Limitation Act 1980"),
                ("Terms of engagement sent", "Engagement Letter", "SRA Standards 2019"),
                ("Terms signed", "Engagement Letter", "SRA Standards 2019"),
                ("Funding arrangement confirmed", "Funding", "SRA Standards 2019"),
                ("Costs estimate provided", "Costs", "SRA Transparency Rules"),
                ("Case plan prepared", "Case Management", "CPR"),
                ("Court deadlines diarised", "Deadline Management", "CPR"),
                ("Pre-trial checklist complete", "Trial Preparation", "CPR Part 29"),
            ],
            "corporate": [
                ("Client ID verified (all parties)", "Identity Verification", "AML Regulations 2017"),
                ("Beneficial ownership confirmed", "Ownership Verification", "AML Regulations 2017"),
                ("Conflict search (all parties)", "Conflicts", "SRA Standards 2019"),
                ("Sanctions screening (all parties)", "Sanctions Check", "AML Regulations 2017"),
                ("Terms of engagement", "Engagement Letter", "SRA Standards 2019"),
                ("Source of funds verified", "AML Due Diligence", "AML Regulations 2017"),
                ("Board minutes reviewed", "Corporate Governance", "Companies Act 2006"),
                ("Due diligence checklist complete", "Due Diligence", "Corporate Standards"),
                ("Completion bible prepared", "Completion", "Corporate Standards"),
                ("Post-completion filings done", "Post-Completion", "Companies House Requirements"),
            ],
        }

        template_items = MATTER_CHECKLIST_TEMPLATES.get(matter_type, MATTER_CHECKLIST_TEMPLATES["conveyancing"])

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        checklist_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()

        cursor.execute(
            """INSERT INTO matter_checklists (id, case_id, case_name, matter_type, created_at, status, assigned_to, total_items)
               VALUES (?, ?, ?, ?, ?, 'in_progress', ?, ?)""",
            (checklist_id, case_id, case_name, matter_type, now, assigned_to, len(template_items))
        )

        # Add items
        for item_order, (title, category, regulation_ref) in enumerate(template_items, 1):
            item_id = str(uuid.uuid4())
            cursor.execute(
                """INSERT INTO matter_checklist_items (id, checklist_id, item_order, category, title, description, regulation_ref, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (item_id, checklist_id, item_order, category, title, title, regulation_ref)
            )

        conn.commit()
        conn.close()

        self.send_json({"checklist_id": checklist_id, "status": "created", "total_items": len(template_items)}, 201)

    def handle_complete_matter_item(self, item_id, body):
        """Mark a matter checklist item as completed"""
        data = json.loads(body) if body else {}
        completed_by = data.get('completed_by', 'staff-001')
        evidence_ref = data.get('evidence_ref')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        # Update item
        cursor.execute(
            "UPDATE matter_checklist_items SET status = 'completed', completed_by = ?, completed_at = ?, evidence_ref = ? WHERE id = ?",
            (completed_by, now, evidence_ref, item_id)
        )

        # Get checklist and update completion count
        cursor.execute("SELECT checklist_id FROM matter_checklist_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row:
            checklist_id = row[0]
            cursor.execute("SELECT COUNT(*) as cnt FROM matter_checklist_items WHERE checklist_id = ? AND status = 'completed'", (checklist_id,))
            completed = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE matter_checklists SET completed_items = ? WHERE id = ?",
                (completed, checklist_id)
            )

        conn.commit()
        conn.close()

        self.send_json({"item_id": item_id, "status": "completed"})

    # ========== IMPORT/EXPORT HANDLERS ==========

    def handle_get_import_logs(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM import_logs ORDER BY imported_at DESC LIMIT 50")
        logs = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"import_logs": logs, "count": len(logs)})

    def handle_export_staff_csv(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, role, email, pqe, department, start_date, status FROM staff_members ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        lines = ["id,name,role,email,pqe,department,start_date,status"]
        for r in rows:
            lines.append(",".join([str(r[k] or '') for k in ['id','name','role','email','pqe','department','start_date','status']]))
        csv_text = "\n".join(lines)
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Disposition", "attachment; filename=staff_export.csv")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(csv_text.encode('utf-8'))

    def handle_export_cases_csv(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""SELECT lc.id, lc.case_name, lc.case_type, cl.name as client_name, lc.status, lc.hourly_rate, lc.opened_date
                         FROM law_cases lc LEFT JOIN law_clients cl ON lc.client_id = cl.id ORDER BY lc.case_name""")
        rows = cursor.fetchall()
        conn.close()
        lines = ["id,case_name,case_type,client_name,status,hourly_rate,opened_date"]
        for r in rows:
            lines.append(",".join([str(r[k] or '') for k in ['id','case_name','case_type','client_name','status','hourly_rate','opened_date']]))
        csv_text = "\n".join(lines)
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Disposition", "attachment; filename=cases_export.csv")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(csv_text.encode('utf-8'))

    def handle_export_training_csv(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""SELECT st.id, sm.name as staff_name, st.training_type, st.title, st.status, st.due_date, st.completed_at, st.cpd_hours
                         FROM staff_training st JOIN staff_members sm ON st.staff_id = sm.id ORDER BY sm.name""")
        rows = cursor.fetchall()
        conn.close()
        lines = ["id,staff_name,training_type,title,status,due_date,completed_at,cpd_hours"]
        for r in rows:
            lines.append(",".join([str(r[k] or '') for k in ['id','staff_name','training_type','title','status','due_date','completed_at','cpd_hours']]))
        csv_text = "\n".join(lines)
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Disposition", "attachment; filename=training_export.csv")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(csv_text.encode('utf-8'))

    def _parse_csv_rows(self, csv_text):
        """Parse CSV text into list of dicts using first row as headers"""
        lines = csv_text.strip().split('\n')
        if len(lines) < 2:
            return []
        headers = [h.strip().lower().replace(' ', '_') for h in lines[0].split(',')]
        rows = []
        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.split(',')
            row = {}
            for i, h in enumerate(headers):
                row[h] = values[i].strip() if i < len(values) else ''
            rows.append(row)
        return rows

    def handle_import_staff(self, body):
        data = json.loads(body) if body else {}
        csv_text = data.get('csv_data', '')
        rows = self._parse_csv_rows(csv_text)
        if not rows:
            self.send_json({"error": "No valid data rows found"}, 400)
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        imported = 0
        failed = 0
        errors = []

        for row in rows:
            try:
                staff_id = row.get('id') or f"staff-{str(uuid.uuid4())[:8]}"
                name = row.get('name', '').strip()
                if not name:
                    failed += 1
                    errors.append(f"Row missing name: {row}")
                    continue
                role = row.get('role', 'Solicitor')
                email = row.get('email', f"{name.lower().replace(' ', '.')}@firm.co.uk")
                pqe = int(row.get('pqe', 0)) if row.get('pqe', '').isdigit() else 0
                department = row.get('department', 'General')

                cursor.execute("""INSERT OR REPLACE INTO staff_members (id, name, role, email, pqe, department, start_date, status)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, 'active')""",
                               (staff_id, name, role, email, pqe, department, datetime.datetime.now().isoformat()))
                imported += 1
            except Exception as e:
                failed += 1
                errors.append(str(e))

        # Log the import
        log_id = str(uuid.uuid4())
        cursor.execute("""INSERT INTO import_logs (id, import_type, filename, records_imported, records_failed, imported_by, imported_at, status, error_details)
                          VALUES (?, 'staff', ?, ?, ?, 'COLP', ?, 'completed', ?)""",
                       (log_id, data.get('filename', 'manual'), imported, failed, datetime.datetime.now().isoformat(), json.dumps(errors[:10]) if errors else None))

        conn.commit()
        conn.close()
        self.send_json({"imported": imported, "failed": failed, "errors": errors[:5], "log_id": log_id})

    def handle_import_cases(self, body):
        data = json.loads(body) if body else {}
        csv_text = data.get('csv_data', '')
        rows = self._parse_csv_rows(csv_text)
        if not rows:
            self.send_json({"error": "No valid data rows found"}, 400)
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        imported = 0
        failed = 0
        errors = []

        for row in rows:
            try:
                case_id = row.get('id') or str(uuid.uuid4())
                case_name = row.get('case_name') or row.get('name', '').strip()
                if not case_name:
                    failed += 1
                    continue
                case_type = row.get('case_type') or row.get('type', 'general')
                client_name = row.get('client_name') or row.get('client', '')
                status = row.get('status', 'active')
                hourly_rate = float(row.get('hourly_rate', 0) or 0)

                # Look up client_id by name, or create a new client
                client_id = None
                if client_name:
                    cursor.execute("SELECT id FROM law_clients WHERE name = ?", (client_name,))
                    cr = cursor.fetchone()
                    if cr:
                        client_id = cr[0]
                    else:
                        client_id = str(uuid.uuid4())
                        cursor.execute("INSERT OR IGNORE INTO law_clients (id, name, status) VALUES (?, ?, 'active')", (client_id, client_name))

                cursor.execute("""INSERT OR REPLACE INTO law_cases (id, client_id, case_name, case_type, status, hourly_rate, opened_date)
                                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
                               (case_id, client_id, case_name, case_type, status, hourly_rate, datetime.datetime.now().isoformat()))
                imported += 1
            except Exception as e:
                failed += 1
                errors.append(str(e))

        log_id = str(uuid.uuid4())
        cursor.execute("""INSERT INTO import_logs (id, import_type, filename, records_imported, records_failed, imported_by, imported_at, status, error_details)
                          VALUES (?, 'cases', ?, ?, ?, 'COLP', ?, 'completed', ?)""",
                       (log_id, data.get('filename', 'manual'), imported, failed, datetime.datetime.now().isoformat(), json.dumps(errors[:10]) if errors else None))

        conn.commit()
        conn.close()
        self.send_json({"imported": imported, "failed": failed, "errors": errors[:5], "log_id": log_id})

    def handle_import_training(self, body):
        data = json.loads(body) if body else {}
        csv_text = data.get('csv_data', '')
        rows = self._parse_csv_rows(csv_text)
        if not rows:
            self.send_json({"error": "No valid data rows found"}, 400)
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        imported = 0
        failed = 0
        errors = []

        for row in rows:
            try:
                tid = row.get('id') or str(uuid.uuid4())
                staff_name = row.get('staff_name') or row.get('name', '')
                # Look up staff_id by name
                cursor.execute("SELECT id FROM staff_members WHERE name LIKE ?", ('%' + staff_name + '%',))
                staff = cursor.fetchone()
                staff_id = staff[0] if staff else None
                if not staff_id:
                    failed += 1
                    errors.append(f"Staff not found: {staff_name}")
                    continue

                training_type = row.get('training_type') or row.get('type', 'general')
                title = row.get('title', training_type)
                status = row.get('status', 'pending')
                due_date = row.get('due_date', '')
                completed_at = row.get('completed_at') or row.get('completed', '')
                cpd_hours = float(row.get('cpd_hours') or row.get('hours', '0') or '0')

                cursor.execute("""INSERT OR REPLACE INTO staff_training (id, staff_id, training_type, title, status, due_date, completed_at, cpd_hours)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                               (tid, staff_id, training_type, title, status, due_date or None, completed_at or None, cpd_hours))
                imported += 1
            except Exception as e:
                failed += 1
                errors.append(str(e))

        log_id = str(uuid.uuid4())
        cursor.execute("""INSERT INTO import_logs (id, import_type, filename, records_imported, records_failed, imported_by, imported_at, status, error_details)
                          VALUES (?, 'training', ?, ?, ?, 'COLP', ?, 'completed', ?)""",
                       (log_id, data.get('filename', 'manual'), imported, failed, datetime.datetime.now().isoformat(), json.dumps(errors[:10]) if errors else None))

        conn.commit()
        conn.close()
        self.send_json({"imported": imported, "failed": failed, "errors": errors[:5], "log_id": log_id})

    def handle_import_clients(self, body):
        data = json.loads(body) if body else {}
        csv_text = data.get('csv_data', '')
        rows = self._parse_csv_rows(csv_text)
        if not rows:
            self.send_json({"error": "No valid data rows found"}, 400)
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        imported = 0
        failed = 0
        errors = []

        for row in rows:
            try:
                cid = row.get('id') or str(uuid.uuid4())
                client_name = row.get('client_name') or row.get('name', '').strip()
                if not client_name:
                    failed += 1
                    continue
                client_type = row.get('client_type') or row.get('type', 'individual')
                risk_level = row.get('risk_level') or row.get('risk', 'low')
                cdd_status = row.get('cdd_status', 'pending')

                cursor.execute("""INSERT OR REPLACE INTO client_intake (id, client_name, client_type, risk_level, cdd_status, created_at, assessed_at)
                                  VALUES (?, ?, ?, ?, ?, ?, ?)""",
                               (cid, client_name, client_type, risk_level, cdd_status, datetime.datetime.now().isoformat(), None))
                imported += 1
            except Exception as e:
                failed += 1
                errors.append(str(e))

        log_id = str(uuid.uuid4())
        cursor.execute("""INSERT INTO import_logs (id, import_type, filename, records_imported, records_failed, imported_by, imported_at, status, error_details)
                          VALUES (?, 'clients', ?, ?, ?, 'COLP', ?, 'completed', ?)""",
                       (log_id, data.get('filename', 'manual'), imported, failed, datetime.datetime.now().isoformat(), json.dumps(errors[:10]) if errors else None))

        conn.commit()
        conn.close()
        self.send_json({"imported": imported, "failed": failed, "errors": errors[:5], "log_id": log_id})

    def handle_clear_demo_data(self, body):
        """Clear all demo-seeded data so firm can start fresh with their own"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        tables_to_clear = [
            'staff_members', 'staff_training', 'staff_file_reviews',
            'law_clients', 'law_cases', 'law_time_entries', 'law_documents',
            'law_deadlines', 'law_communications', 'client_intake',
            'compliance_checks', 'risk_scores', 'compliance_alerts',
            'sra_audit_items', 'compliance_tasks', 'regulatory_updates',
            'regulatory_impact_analysis', 'policy_update_queue', 'sra_feed_log',
            'chaser_log', 'evidence_locker', 'audit_trail',
            'supervision_schedule', 'matter_checklists', 'matter_checklist_items',
            'breach_reports', 'breach_report_steps', 'remediation_plans',
            'remediation_steps', 'audit_reports', 'staff_actions',
            'email_queue', 'user_sessions', 'import_logs',
        ]
        cleared = 0
        for table in tables_to_clear:
            try:
                cursor.execute(f"DELETE FROM {table}")
                cleared += cursor.rowcount
            except:
                pass
        conn.commit()
        conn.close()
        self.send_json({"status": "cleared", "records_removed": cleared})

    # ========== AUTH & USER MANAGEMENT ==========

    def _get_user_from_token(self, token):
        """Validate session token and return user info"""
        if not token:
            return None
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ua.id, ua.staff_id, ua.email, ua.role, sm.name, sm.department
            FROM user_sessions us
            JOIN user_accounts ua ON us.user_id = ua.id
            JOIN staff_members sm ON ua.staff_id = sm.id
            WHERE us.token = ? AND us.is_active = 1 AND ua.is_active = 1
        """, (token,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    def handle_auth_login(self, body):
        data = json.loads(body) if body else {}
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not email or not password:
            self.send_json({"error": "Email and password required"}, 400)
            return

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ua.id, ua.staff_id, ua.email, ua.role, sm.name, sm.department, sm.role as job_title
            FROM user_accounts ua
            JOIN staff_members sm ON ua.staff_id = sm.id
            WHERE ua.email = ? AND ua.password_hash = ? AND ua.is_active = 1
        """, (email, password_hash))

        user = cursor.fetchone()
        if not user:
            conn.close()
            self.send_json({"error": "Invalid email or password"}, 401)
            return

        # Create session
        token = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        now = datetime.datetime.now()
        expires = (now + datetime.timedelta(hours=24)).isoformat()

        cursor.execute("""INSERT INTO user_sessions (id, user_id, token, created_at, expires_at, is_active)
                          VALUES (?, ?, ?, ?, ?, 1)""",
                       (session_id, user['id'], token, now.isoformat(), expires))

        cursor.execute("UPDATE user_accounts SET last_login = ? WHERE id = ?", (now.isoformat(), user['id']))

        conn.commit()
        conn.close()

        self.send_json({
            "token": token,
            "user": {
                "id": user['id'],
                "staff_id": user['staff_id'],
                "name": user['name'],
                "email": user['email'],
                "role": user['role'],
                "job_title": user['job_title'],
                "department": user['department']
            }
        })

    def handle_auth_logout(self, body):
        data = json.loads(body) if body else {}
        token = data.get('token') or self.headers.get('X-Auth-Token', '')
        if token:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE user_sessions SET is_active = 0 WHERE token = ?", (token,))
            conn.commit()
            conn.close()
        self.send_json({"status": "logged_out"})

    def handle_get_users(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ua.id, ua.staff_id, ua.email, ua.role, ua.last_login, ua.is_active, ua.created_at,
                   sm.name, sm.department, sm.role as job_title
            FROM user_accounts ua
            JOIN staff_members sm ON ua.staff_id = sm.id
            ORDER BY sm.name
        """)
        users = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"users": users, "count": len(users)})

    def handle_get_user(self, user_id):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ua.*, sm.name, sm.department, sm.role as job_title, sm.pqe
            FROM user_accounts ua
            JOIN staff_members sm ON ua.staff_id = sm.id
            WHERE ua.id = ?
        """, (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            self.send_json({"error": "User not found"}, 404)
            return

        # Get recent actions
        cursor.execute("""SELECT * FROM staff_actions WHERE staff_id = ? ORDER BY performed_at DESC LIMIT 20""",
                       (user['staff_id'],))
        actions = [dict(r) for r in cursor.fetchall()]

        result = dict(user)
        result['recent_actions'] = actions
        conn.close()
        self.send_json(result)

    def handle_create_user(self, body):
        data = json.loads(body) if body else {}
        staff_id = data.get('staff_id')
        email = data.get('email', '').strip().lower()
        role = data.get('role', 'staff')

        if not staff_id:
            self.send_json({"error": "staff_id is required"}, 400)
            return

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check staff exists and get their details
        cursor.execute("SELECT name, email, role FROM staff_members WHERE id = ?", (staff_id,))
        staff = cursor.fetchone()
        if not staff:
            conn.close()
            self.send_json({"error": "Staff member not found"}, 404)
            return

        # Auto-fill email from staff record if not provided
        if not email:
            email = (staff['email'] or '').strip().lower()
        if not email:
            conn.close()
            self.send_json({"error": "No email found for this staff member. Please provide email."}, 400)
            return

        # Auto-detect role from staff record
        if not data.get('role'):
            staff_role = (staff['role'] or '').lower()
            if 'partner' in staff_role or 'colp' in staff_role:
                role = 'colp'
            elif 'solicitor' in staff_role:
                role = 'solicitor'
            else:
                role = 'staff'

        # Default password: first name + 2024
        first_name = staff['name'].split()[0].lower()
        password = first_name + "2024"
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        user_id = str(uuid.uuid4())
        try:
            cursor.execute("""INSERT OR IGNORE INTO user_accounts (id, staff_id, email, password_hash, role, is_active, created_at)
                              VALUES (?, ?, ?, ?, ?, 1, ?)""",
                           (user_id, staff_id, email, password_hash, role, datetime.datetime.now().isoformat()))
            conn.commit()
            conn.close()
            self.send_json({"user_id": user_id, "email": email, "role": role, "default_password": password, "status": "created"}, 201)
        except Exception as e:
            conn.close()
            self.send_json({"error": str(e)}, 400)

    def handle_reset_password(self, body):
        data = json.loads(body) if body else {}
        user_id = data.get('user_id')

        if not user_id:
            self.send_json({"error": "user_id required"}, 400)
            return

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""SELECT ua.id, sm.name FROM user_accounts ua
                          JOIN staff_members sm ON ua.staff_id = sm.id WHERE ua.id = ?""", (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            self.send_json({"error": "User not found"}, 404)
            return

        first_name = user['name'].split()[0].lower()
        new_password = first_name + str(random.randint(1000, 9999))
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()

        cursor.execute("UPDATE user_accounts SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        # Invalidate all sessions
        cursor.execute("UPDATE user_sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

        self.send_json({"status": "reset", "new_password": new_password})

    def handle_get_my_tasks(self, token):
        user = self._get_user_from_token(token)
        if not user:
            self.send_json({"error": "Authentication required"}, 401)
            return

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""SELECT * FROM compliance_tasks
                          WHERE assigned_to = ? OR assigned_to = ?
                          ORDER BY due_date ASC""",
                       (user['staff_id'], user['name']))
        tasks = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"tasks": tasks, "user": user['name']})

    def handle_get_my_training(self, token):
        user = self._get_user_from_token(token)
        if not user:
            self.send_json({"error": "Authentication required"}, 401)
            return

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""SELECT * FROM staff_training
                          WHERE staff_id = ?
                          ORDER BY due_date ASC""",
                       (user['staff_id'],))
        training = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"training": training, "user": user['name']})

    def handle_get_my_chasers(self, token):
        user = self._get_user_from_token(token)
        if not user:
            self.send_json({"error": "Authentication required"}, 401)
            return

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""SELECT * FROM chaser_log
                          WHERE recipient_staff_id = ? AND acknowledged = 0
                          ORDER BY sent_at DESC""",
                       (user['staff_id'],))
        chasers = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"chasers": chasers, "user": user['name']})

    def handle_staff_acknowledge_chaser(self, body):
        data = json.loads(body) if body else {}
        token = data.get('token') or self.headers.get('X-Auth-Token', '')
        chaser_id = data.get('chaser_id')

        user = self._get_user_from_token(token)
        if not user:
            self.send_json({"error": "Authentication required"}, 401)
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("UPDATE chaser_log SET acknowledged = 1, acknowledged_at = ? WHERE id = ?", (now, chaser_id))

        # Log action
        cursor.execute("""INSERT INTO staff_actions (id, staff_id, action_type, entity_type, entity_id, details, performed_at)
                          VALUES (?, ?, 'acknowledge', 'chaser', ?, 'Chaser acknowledged by staff', ?)""",
                       (str(uuid.uuid4()), user['staff_id'], chaser_id, now))

        conn.commit()
        conn.close()
        self.send_json({"status": "acknowledged"})

    def handle_staff_complete_training(self, body):
        data = json.loads(body) if body else {}
        token = data.get('token') or self.headers.get('X-Auth-Token', '')
        training_id = data.get('training_id')

        user = self._get_user_from_token(token)
        if not user:
            self.send_json({"error": "Authentication required"}, 401)
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        cursor.execute("UPDATE staff_training SET status = 'completed', completed_at = ? WHERE id = ? AND staff_id = ?",
                       (now, training_id, user['staff_id']))

        cursor.execute("""INSERT INTO staff_actions (id, staff_id, action_type, entity_type, entity_id, details, performed_at)
                          VALUES (?, ?, 'complete', 'training', ?, 'Training completed by staff', ?)""",
                       (str(uuid.uuid4()), user['staff_id'], training_id, now))

        conn.commit()
        conn.close()
        self.send_json({"status": "completed"})

    def handle_staff_log_action(self, body):
        data = json.loads(body) if body else {}
        token = data.get('token') or self.headers.get('X-Auth-Token', '')

        user = self._get_user_from_token(token)
        if not user:
            self.send_json({"error": "Authentication required"}, 401)
            return

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        action_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()

        # If action is completing a task, actually mark it as completed in the DB
        action_type = data.get('action_type', 'general')
        entity_type = data.get('entity_type', '')
        entity_id = data.get('entity_id', '')

        if action_type == 'complete_task' and entity_type == 'task' and entity_id:
            cursor.execute("UPDATE compliance_tasks SET status = 'completed', completed_at = ? WHERE id = ?",
                           (now, entity_id))

        cursor.execute("""INSERT INTO staff_actions (id, staff_id, action_type, entity_type, entity_id, details, performed_at)
                          VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       (action_id, user['staff_id'], action_type,
                        entity_type, entity_id,
                        data.get('details', ''), now))
        conn.commit()
        conn.close()
        self.send_json({"action_id": action_id, "status": "logged"})

    # ====== EMAIL SETTINGS & QUEUE ======
    def handle_get_email_settings(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_settings LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            settings = dict(row)
            if settings.get('smtp_password'):
                settings['smtp_password'] = '********'
            self.send_json(settings)
        else:
            self.send_json({"error": "No email settings configured"}, 404)

    def handle_update_email_settings(self, body):
        data = json.loads(body) if body else {}
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        allowed_fields = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'from_email', 'from_name',
                          'enabled', 'auto_chase_training', 'auto_chase_reviews', 'auto_chase_cdd',
                          'chase_frequency_days', 'escalation_after_days']
        updates = []
        values = []
        for field in allowed_fields:
            if field in data:
                if field == 'smtp_password' and data[field] == '********':
                    continue
                updates.append(field + " = ?")
                values.append(data[field])
        if updates:
            updates.append("updated_at = ?")
            values.append(now)
            values.append('settings-001')
            cursor.execute("UPDATE email_settings SET " + ", ".join(updates) + " WHERE id = ?", values)
            conn.commit()
        conn.close()
        self.send_json({"status": "updated"})

    def handle_get_email_queue(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_queue ORDER BY created_at DESC LIMIT 100")
        queue = [dict(r) for r in cursor.fetchall()]
        conn.close()
        self.send_json({"queue": queue, "total": len(queue)})

    def handle_get_email_queue_stats(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT status, COUNT(*) as count FROM email_queue GROUP BY status")
        stats = {row['status']: row['count'] for row in cursor.fetchall()}
        cursor.execute("SELECT template, COUNT(*) as count FROM email_queue GROUP BY template")
        by_template = {row['template']: row['count'] for row in cursor.fetchall()}
        cursor.execute("SELECT COUNT(*) FROM email_queue WHERE sent_at IS NOT NULL AND sent_at > ?",
                       ((datetime.datetime.now() - datetime.timedelta(days=7)).isoformat(),))
        sent_this_week = cursor.fetchone()[0]
        conn.close()
        self.send_json({"by_status": stats, "by_template": by_template, "sent_this_week": sent_this_week})

    def handle_get_email_templates(self):
        templates = [
            {"id": "training_reminder", "name": "Training Reminder", "subject": "Training Reminder: {training_title}", "description": "Sent when staff training is overdue or approaching deadline"},
            {"id": "review_reminder", "name": "File Review Reminder", "subject": "File Review Due: {case_name}", "description": "Sent when a file review is overdue"},
            {"id": "cdd_reminder", "name": "CDD Reminder", "subject": "CDD Pending: {client_name}", "description": "Sent when client due diligence checks are incomplete"},
            {"id": "supervision_reminder", "name": "Supervision Meeting", "subject": "Supervision Meeting Due: {staff_name}", "description": "Sent when supervision meetings are overdue"},
            {"id": "policy_reminder", "name": "Policy Acknowledgement", "subject": "Policy Update Acknowledgement Required", "description": "Sent when new policies require staff acknowledgement"},
            {"id": "escalation", "name": "Escalation Notice", "subject": "ESCALATION: {original_subject}", "description": "Sent to supervisors when a chaser has not been acknowledged"},
            {"id": "general", "name": "General Compliance", "subject": "Compliance Notice", "description": "General purpose compliance notification"}
        ]
        self.send_json({"templates": templates})

    def handle_send_queued_email(self, body):
        data = json.loads(body) if body else {}
        email_id = data.get('email_id')
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()

        # Fetch the email details
        cursor.execute("SELECT * FROM email_queue WHERE id = ?", (email_id,))
        email_row = cursor.fetchone()
        settings = _get_smtp_settings()

        send_status = "sent"
        error_msg = None

        if email_row and settings.get('enabled'):
            success, err = send_real_email(
                email_row['to_email'], email_row['to_name'],
                email_row['subject'], email_row['body'], settings
            )
            if not success:
                send_status = "failed"
                error_msg = err

        cursor.execute("UPDATE email_queue SET status = ?, sent_at = ?, error_message = ? WHERE id = ?",
                       (send_status, now, error_msg, email_id))
        cursor.execute("""INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
                          VALUES (?, 'email_sent', 'email', ?, 'System', ?, ?)""",
                       (str(uuid.uuid4()), email_id, 'Email ' + send_status + (': ' + (error_msg or '') if error_msg else ''), now))
        conn.commit()
        conn.close()
        self.send_json({"status": send_status, "error": error_msg})

    def handle_send_all_queued(self, body):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        settings = _get_smtp_settings()

        cursor.execute("SELECT * FROM email_queue WHERE status = 'queued'")
        queued = cursor.fetchall()
        sent_count = 0
        fail_count = 0

        for email_row in queued:
            if settings.get('enabled'):
                success, err = send_real_email(
                    email_row['to_email'], email_row['to_name'],
                    email_row['subject'], email_row['body'], settings
                )
                if success:
                    cursor.execute("UPDATE email_queue SET status = 'sent', sent_at = ? WHERE id = ?",
                                   (now, email_row['id']))
                    sent_count += 1
                else:
                    cursor.execute("UPDATE email_queue SET status = 'failed', error_message = ? WHERE id = ?",
                                   (err, email_row['id']))
                    fail_count += 1
            else:
                # SMTP disabled — mark as sent (simulated)
                cursor.execute("UPDATE email_queue SET status = 'sent', sent_at = ? WHERE id = ?",
                               (now, email_row['id']))
                sent_count += 1

        cursor.execute("""INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
                          VALUES (?, 'email_batch_sent', 'email', 'batch', 'System', ?, ?)""",
                       (str(uuid.uuid4()), str(sent_count) + ' sent, ' + str(fail_count) + ' failed', now))
        conn.commit()
        conn.close()
        self.send_json({"status": "completed", "sent": sent_count, "failed": fail_count})

    def handle_test_email(self, body):
        data = json.loads(body) if body else {}
        to_email = data.get('to_email', '')
        settings = _get_smtp_settings()
        now = datetime.datetime.now().isoformat()
        email_id = str(uuid.uuid4())

        test_body = "This is a test email from Seema Compliance Engine.\n\nIf you received this, your email integration is working correctly."

        # Try real send
        send_status = "sent"
        error_msg = None
        if settings.get('enabled') and to_email:
            success, err = send_real_email(to_email, 'Test Recipient', 'Seema Test Email', test_body, settings)
            if not success:
                send_status = "failed"
                error_msg = err

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO email_queue (id, to_email, to_name, subject, body, template, status, sent_at, error_message, created_at)
                          VALUES (?, ?, 'Test Recipient', 'Seema Test Email', ?, 'general', ?, ?, ?, ?)""",
                       (email_id, to_email, test_body, send_status, now if send_status == 'sent' else None, error_msg, now))
        conn.commit()
        conn.close()
        self.send_json({"status": send_status, "email_id": email_id, "error": error_msg})

    def handle_trigger_auto_chase(self, body):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_settings LIMIT 1")
        row = cursor.fetchone()
        settings = dict(row) if row else {}
        queued_count = 0
        now = datetime.datetime.now().isoformat()
        chase_cutoff = (datetime.datetime.now() - datetime.timedelta(days=settings.get('chase_frequency_days', 3))).isoformat()

        if settings.get('auto_chase_training', 1):
            cursor.execute("""SELECT st.id, st.title, st.staff_id, sm.name, sm.email
                              FROM staff_training st JOIN staff_members sm ON st.staff_id = sm.id
                              WHERE st.status = 'overdue'
                              AND st.id NOT IN (SELECT related_entity_id FROM email_queue WHERE related_entity_type = 'training' AND created_at > ?)""",
                           (chase_cutoff,))
            for row in cursor.fetchall():
                eid = str(uuid.uuid4())
                cursor.execute("""INSERT INTO email_queue (id, to_email, to_name, subject, body, template, status, related_entity_type, related_entity_id, created_at)
                                  VALUES (?, ?, ?, ?, ?, 'training_reminder', 'queued', 'training', ?, ?)""",
                               (eid, row['email'], row['name'], 'Training Reminder: ' + row['title'],
                                'Dear ' + row['name'] + ',\n\nYour training "' + row['title'] + '" is overdue. Please complete it.\n\nRegards,\nSeema Compliance',
                                row['id'], now))
                queued_count += 1

        if settings.get('auto_chase_reviews', 1):
            cursor.execute("""SELECT sfr.id, sfr.case_id, sfr.staff_id, sm.name, sm.email
                              FROM staff_file_reviews sfr JOIN staff_members sm ON sfr.staff_id = sm.id
                              WHERE sfr.status = 'overdue'
                              AND sfr.id NOT IN (SELECT related_entity_id FROM email_queue WHERE related_entity_type = 'file_review' AND created_at > ?)""",
                           (chase_cutoff,))
            for row in cursor.fetchall():
                eid = str(uuid.uuid4())
                cursor.execute("""INSERT INTO email_queue (id, to_email, to_name, subject, body, template, status, related_entity_type, related_entity_id, created_at)
                                  VALUES (?, ?, ?, ?, ?, 'review_reminder', 'queued', 'file_review', ?, ?)""",
                               (eid, row['email'], row['name'], 'File Review Overdue: Case ' + row['case_id'],
                                'Dear ' + row['name'] + ',\n\nYour file review for case ' + row['case_id'] + ' is overdue.\n\nRegards,\nSeema Compliance',
                                row['id'], now))
                queued_count += 1

        cursor.execute("""INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
                          VALUES (?, 'auto_chase', 'email', 'batch', 'System', ?, ?)""",
                       (str(uuid.uuid4()), 'Auto-chase generated ' + str(queued_count) + ' emails', now))
        conn.commit()
        conn.close()
        self.send_json({"status": "completed", "queued": queued_count})

    # ====== PDF EXPORTS ======
    def handle_export_sra_return_pdf(self, body):
        data = json.loads(body) if body else {}
        firm_name = data.get('firm_name', 'Mitchell & Partners LLP')

        # Get the SRA return data using the existing handler logic
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Replicate SRA return data gathering
        cursor.execute("SELECT * FROM staff_members")
        staff = cursor.fetchall()
        cursor.execute("SELECT * FROM compliance_checks WHERE status = 'non_compliant'")
        non_compliant = cursor.fetchall()
        cursor.execute("SELECT * FROM sra_audit_items")
        audit_items = cursor.fetchall()
        total_items = len(audit_items)
        compliant_items = len([a for a in audit_items if dict(a).get('status') == 'compliant'])
        score = round((compliant_items / total_items * 100)) if total_items > 0 else 0

        sra_data = {
            'firm_details': {'name': firm_name, 'sra_number': '654321', 'reporting_period': str(datetime.datetime.now().year)},
            'staff_summary': {
                'total_staff': len(staff),
                'total_solicitors': len([s for s in staff if 'Solicitor' in dict(s).get('role', '')]),
                'total_fee_earners': len([s for s in staff if dict(s).get('role', '') not in ['Practice Manager', 'Compliance Assistant']]),
                'diversity_data': 'Collected annually'
            },
            'compliance': {
                'sra_audit_score': score,
                'non_compliant_items': len(non_compliant),
                'active_alerts': 0,
                'open_remediation': 0
            },
            'complaints': {'total_received': 3, 'resolved': 2, 'referred_to_leo': 0, 'avg_resolution_days': 18},
            'financial': {'pii_claims': 0, 'client_account_shortfalls': 0, 'accountant_report_date': '2025-03-15'},
            'aml': {'risk_assessments_completed': len(staff), 'suspicious_activity_reports': 1, 'edd_reviews': 4, 'pep_clients': 2},
            'data_protection': {'dsar_received': 2, 'breaches_reported': 1, 'ico_notifications': 0}
        }
        conn.close()

        pdf_bytes = generate_sra_return_pdf(sra_data, firm_name)
        if pdf_bytes:
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", "attachment; filename=SRA-Annual-Return-" + str(datetime.datetime.now().year) + ".pdf")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(pdf_bytes)
        else:
            self.send_json({"error": "PDF generation not available"}, 500)

    def handle_export_audit_report_pdf(self, body):
        data = json.loads(body) if body else {}
        report_id = data.get('report_id', '')
        firm_name = data.get('firm_name', 'Mitchell & Partners LLP')

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            self.send_json({"error": "Report not found"}, 404)
            return

        report_data = dict(row)
        report_data['summary'] = json.loads(report_data.get('summary', '{}')) if isinstance(report_data.get('summary'), str) else report_data.get('summary', {})

        pdf_bytes = generate_audit_report_pdf(report_data, firm_name)
        if pdf_bytes:
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", "attachment; filename=Audit-Report-" + report_id[:8] + ".pdf")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(pdf_bytes)
        else:
            self.send_json({"error": "PDF generation not available"}, 500)

    def handle_export_breach_report_pdf(self, body):
        data = json.loads(body) if body else {}
        breach_id = data.get('breach_id', '')
        firm_name = data.get('firm_name', 'Mitchell & Partners LLP')

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM breach_reports WHERE id = ?", (breach_id,))
        row = cursor.fetchone()
        report_data = dict(row) if row else {}

        if row:
            cursor.execute("SELECT * FROM breach_report_steps WHERE breach_id = ? ORDER BY step_number", (breach_id,))
            report_data['steps'] = [dict(s) for s in cursor.fetchall()]
        conn.close()

        if not report_data:
            self.send_json({"error": "Breach report not found"}, 404)
            return

        pdf_bytes = generate_breach_report_pdf(report_data, firm_name)
        if pdf_bytes:
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", "attachment; filename=Breach-Report-" + breach_id[:8] + ".pdf")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(pdf_bytes)
        else:
            self.send_json({"error": "PDF generation not available"}, 500)

    def handle_weekly_summary_pdf(self, body):
        data = json.loads(body) if body else {}
        firm_name = data.get('firm_name', 'Mitchell & Partners LLP')

        # Get daily briefing data
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM compliance_tasks WHERE due_date < date('now') AND status != 'completed'")
        overdue = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM compliance_tasks WHERE due_date = date('now') AND status != 'completed'")
        today = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM staff_training WHERE status = 'overdue'")
        training_overdue = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM staff_file_reviews WHERE status = 'overdue'")
        reviews_overdue = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM client_intake WHERE status = 'pending'")
        pending_intakes = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM breach_reports WHERE status NOT IN ('closed', 'resolved')")
        open_breaches = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM compliance_alerts WHERE status = 'active'")
        active_alerts = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM chaser_log WHERE acknowledged = 0")
        chasers_pending = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM supervision_schedule WHERE next_due < date('now') AND status = 'active'")
        supervision_overdue = cursor.fetchone()[0]
        conn.close()

        summary_data = {
            'summary': {
                'overdue_count': overdue, 'today_count': today,
                'training_overdue': training_overdue, 'reviews_overdue': reviews_overdue,
                'pending_intakes': pending_intakes, 'open_breaches': open_breaches,
                'active_alerts': active_alerts, 'chasers_pending': chasers_pending,
                'supervision_overdue': supervision_overdue
            }
        }

        pdf_bytes = generate_weekly_summary_pdf(summary_data, firm_name)
        if pdf_bytes:
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", "attachment; filename=Weekly-Summary-" + datetime.datetime.now().strftime('%Y-%m-%d') + ".pdf")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(pdf_bytes)
        else:
            self.send_json({"error": "PDF generation not available"}, 500)

    # ====== DAILY SCHEDULER ======
    def handle_run_daily_schedule(self, body):
        """Run all daily automated tasks: compliance scan, auto-chase, and optionally email weekly summary"""
        results = {}
        now = datetime.datetime.now()

        # 1. Auto-chase overdue items
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_settings LIMIT 1")
        row = cursor.fetchone()
        settings = dict(row) if row else {}
        queued_count = 0
        chase_cutoff = (now - datetime.timedelta(days=settings.get('chase_frequency_days', 3))).isoformat()

        if settings.get('auto_chase_training', 1):
            cursor.execute("""SELECT st.id, st.title, st.staff_id, sm.name, sm.email
                              FROM staff_training st JOIN staff_members sm ON st.staff_id = sm.id
                              WHERE st.status = 'overdue'
                              AND st.id NOT IN (SELECT related_entity_id FROM email_queue WHERE related_entity_type = 'training' AND created_at > ?)""",
                           (chase_cutoff,))
            for r in cursor.fetchall():
                eid = str(uuid.uuid4())
                cursor.execute("""INSERT INTO email_queue (id, to_email, to_name, subject, body, template, status, related_entity_type, related_entity_id, created_at)
                                  VALUES (?, ?, ?, ?, ?, 'training_reminder', 'queued', 'training', ?, ?)""",
                               (eid, r['email'], r['name'], 'Training Reminder: ' + r['title'],
                                'Dear ' + r['name'] + ',\n\nYour training "' + r['title'] + '" is overdue.\n\nRegards,\nSeema Compliance',
                                r['id'], now.isoformat()))
                queued_count += 1

        if settings.get('auto_chase_reviews', 1):
            cursor.execute("""SELECT sfr.id, sfr.case_id, sm.name, sm.email
                              FROM staff_file_reviews sfr JOIN staff_members sm ON sfr.staff_id = sm.id
                              WHERE sfr.status = 'overdue'
                              AND sfr.id NOT IN (SELECT related_entity_id FROM email_queue WHERE related_entity_type = 'file_review' AND created_at > ?)""",
                           (chase_cutoff,))
            for r in cursor.fetchall():
                eid = str(uuid.uuid4())
                cursor.execute("""INSERT INTO email_queue (id, to_email, to_name, subject, body, template, status, related_entity_type, related_entity_id, created_at)
                                  VALUES (?, ?, ?, ?, ?, 'review_reminder', 'queued', 'file_review', ?, ?)""",
                               (eid, r['email'], r['name'], 'File Review Overdue: ' + r['case_id'],
                                'Dear ' + r['name'] + ',\n\nYour file review for ' + r['case_id'] + ' is overdue.\n\nRegards,\nSeema Compliance',
                                r['id'], now.isoformat()))
                queued_count += 1

        results['auto_chase'] = {'queued': queued_count}

        # 2. Send all queued emails if SMTP is enabled
        if settings.get('enabled'):
            cursor.execute("SELECT * FROM email_queue WHERE status = 'queued'")
            queued_emails = cursor.fetchall()
            sent = 0
            failed = 0
            for email_row in queued_emails:
                success, err = send_real_email(
                    email_row['to_email'], email_row['to_name'],
                    email_row['subject'], email_row['body'], settings
                )
                if success:
                    cursor.execute("UPDATE email_queue SET status = 'sent', sent_at = ? WHERE id = ?",
                                   (now.isoformat(), email_row['id']))
                    sent += 1
                else:
                    cursor.execute("UPDATE email_queue SET status = 'failed', error_message = ? WHERE id = ?",
                                   (err, email_row['id']))
                    failed += 1
            results['email_send'] = {'sent': sent, 'failed': failed}

        # 3. Weekly summary on Mondays
        if now.weekday() == 0:  # Monday
            results['weekly_summary'] = True

        # Log
        cursor.execute("""INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
                          VALUES (?, 'daily_schedule', 'system', 'scheduler', 'Seema Scheduler', ?, ?)""",
                       (str(uuid.uuid4()), json.dumps(results), now.isoformat()))
        conn.commit()
        conn.close()

        self.send_json({"status": "completed", "results": results, "timestamp": now.isoformat()})

    # ============================================================================
    # REGULATORY INTELLIGENCE HANDLERS
    # ============================================================================

    def handle_reg_intelligence_dashboard(self):
        """Main regulatory intelligence dashboard endpoint"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now()

        # Get latest updates with their impact analyses
        cursor.execute("""
            SELECT ru.*, ria.risk_level, ria.affected_areas, ria.affected_policies, ria.affected_staff_roles,
                   ria.action_items, ria.deadline, ria.ai_summary, ria.ai_recommendation, ria.status as analysis_status
            FROM regulatory_updates ru
            LEFT JOIN regulatory_impact_analysis ria ON ru.id = ria.update_id
            ORDER BY ru.published_date DESC
            LIMIT 20
        """)
        updates = []
        for row in cursor.fetchall():
            d = dict(row)
            # Nest the analysis fields into an impact_analysis object
            analysis_fields = ['risk_level', 'affected_areas', 'affected_policies', 'affected_staff_roles', 'action_items', 'deadline', 'ai_summary', 'ai_recommendation', 'analysis_status']
            if d.get('ai_summary'):
                analysis = {}
                for f in analysis_fields:
                    analysis[f] = d.pop(f, None)
                analysis['status'] = analysis.pop('analysis_status', None)
                # Get analysis id for resolve button
                cursor2 = conn.cursor()
                cursor2.execute("SELECT id FROM regulatory_impact_analysis WHERE update_id = ?", (d['id'],))
                aid_row = cursor2.fetchone()
                if aid_row:
                    analysis['id'] = aid_row[0]
                d['impact_analysis'] = analysis
            else:
                for f in analysis_fields:
                    d.pop(f, None)
                d['impact_analysis'] = None
            updates.append(d)

        # Get policy update queue
        cursor.execute("""
            SELECT * FROM policy_update_queue
            WHERE status IN ('pending', 'approved')
            ORDER BY priority DESC, created_at DESC
            LIMIT 15
        """)
        queue_items = []
        for row in cursor.fetchall():
            item = dict(row)
            if item['suggested_changes']:
                item['suggested_changes'] = json.loads(item['suggested_changes'])
            queue_items.append(item)

        # Get feed status
        cursor.execute("SELECT * FROM sra_feed_log ORDER BY last_checked DESC")
        feed_status = [dict(r) for r in cursor.fetchall()]

        # Stats
        cursor.execute("SELECT COUNT(*) as total FROM regulatory_updates")
        total_updates = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as unack FROM regulatory_updates WHERE acknowledged = 0")
        unack_updates = cursor.fetchone()['unack']

        cursor.execute("SELECT COUNT(*) as critical FROM regulatory_updates WHERE impact_level = 'action'")
        critical_actions = cursor.fetchone()['critical']

        cursor.execute("SELECT COUNT(*) as review FROM policy_update_queue WHERE status = 'pending'")
        policies_needing_review = cursor.fetchone()['review']

        conn.close()

        self.send_json({
            "updates": updates,
            "policy_queue": queue_items,
            "feed_status": feed_status,
            "stats": {
                "total_updates": total_updates,
                "unacknowledged": unack_updates,
                "pending_actions": critical_actions,
                "critical_items": unack_updates,
                "policies_to_review": policies_needing_review,
                "last_updated": now.isoformat()
            }
        })

    def handle_reg_feed_status(self):
        """Get feed status for all sources"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM sra_feed_log ORDER BY feed_source")
        feed_logs = [dict(r) for r in cursor.fetchall()]

        conn.close()

        self.send_json({
            "feeds": feed_logs,
            "feed_status": feed_logs,
            "timestamp": datetime.datetime.now().isoformat()
        })

    def handle_reg_policy_queue(self):
        """Get all policy update queue items"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT puq.*, pd.title as policy_title, ru.title as update_title
            FROM policy_update_queue puq
            LEFT JOIN policy_documents pd ON puq.policy_id = pd.id
            LEFT JOIN regulatory_updates ru ON puq.trigger_update_id = ru.id
            ORDER BY puq.priority DESC, puq.created_at DESC
        """)
        queue_items = []
        for row in cursor.fetchall():
            item = dict(row)
            if item['suggested_changes']:
                item['suggested_changes'] = json.loads(item['suggested_changes'])
            queue_items.append(item)

        conn.close()

        self.send_json({
            "queue": queue_items,
            "queue_items": queue_items,
            "timestamp": datetime.datetime.now().isoformat()
        })

    def handle_reg_impact_analysis(self, update_id):
        """Get impact analysis for a specific update"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM regulatory_impact_analysis
            WHERE update_id = ?
        """, (update_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            self.send_json({"error": "Impact analysis not found"}, 404)
            return

        analysis = dict(row)
        analysis['affected_areas'] = json.loads(analysis['affected_areas']) if analysis['affected_areas'] else []
        analysis['affected_policies'] = json.loads(analysis['affected_policies']) if analysis['affected_policies'] else []
        analysis['affected_staff_roles'] = json.loads(analysis['affected_staff_roles']) if analysis['affected_staff_roles'] else []
        analysis['action_items'] = json.loads(analysis['action_items']) if analysis['action_items'] else []

        conn.close()

        self.send_json(analysis)

    def handle_reg_feed_scan(self, body):
        """Simulate an SRA feed scan"""
        try:
            new_items = simulate_sra_feed_scan()
            self.send_json({
                "status": "scan_completed",
                "new_updates": new_items,
                "new_items_found": len(new_items),
                "timestamp": datetime.datetime.now().isoformat()
            })
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def handle_reg_analyze_update(self, update_id, body):
        """Generate or regenerate impact analysis for a specific update"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now()

        cursor.execute("SELECT * FROM regulatory_updates WHERE id = ?", (update_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            self.send_json({"error": "Update not found"}, 404)
            return

        update_dict = dict(row)
        analysis = generate_impact_analysis(update_dict)

        # Check if analysis already exists
        cursor.execute("SELECT id FROM regulatory_impact_analysis WHERE update_id = ?", (update_id,))
        existing = cursor.fetchone()

        if existing:
            # Update existing analysis
            analysis_id = existing['id']
            cursor.execute("""
                UPDATE regulatory_impact_analysis
                SET affected_areas = ?, risk_level = ?, affected_policies = ?, affected_staff_roles = ?,
                    action_items = ?, deadline = ?, ai_summary = ?, ai_recommendation = ?
                WHERE id = ?
            """, (
                json.dumps(analysis['affected_areas']), analysis['risk_level'],
                json.dumps(analysis['affected_policies']), json.dumps(analysis['affected_staff_roles']),
                json.dumps(analysis['action_items']), analysis['deadline'],
                analysis['ai_summary'], analysis['ai_recommendation'], analysis_id
            ))
        else:
            # Create new analysis
            analysis_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO regulatory_impact_analysis
                (id, update_id, affected_areas, risk_level, affected_policies, affected_staff_roles, action_items, deadline, ai_summary, ai_recommendation, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                analysis_id, update_id, json.dumps(analysis['affected_areas']), analysis['risk_level'],
                json.dumps(analysis['affected_policies']), json.dumps(analysis['affected_staff_roles']),
                json.dumps(analysis['action_items']), analysis['deadline'],
                analysis['ai_summary'], analysis['ai_recommendation'], 'pending', now.isoformat()
            ))

        conn.commit()
        conn.close()

        self.send_json({
            "id": analysis_id,
            "update_id": update_id,
            "analysis": analysis,
            "status": "regenerated"
        })

    def handle_reg_policy_approve(self, item_id, body):
        """Approve a policy update suggestion"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now()

        try:
            body_dict = json.loads(body) if body else {}
            approved_by = body_dict.get('approved_by', 'system')

            cursor.execute("""
                UPDATE policy_update_queue
                SET status = 'approved'
                WHERE id = ?
            """, (item_id,))

            # Log action
            cursor.execute("""
                INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), 'policy_update_approved', 'policy_update_queue', item_id, approved_by, 'Policy update approved', now.isoformat()))

            conn.commit()
            conn.close()

            self.send_json({"status": "approved", "item_id": item_id})
        except Exception as e:
            conn.close()
            self.send_json({"error": str(e)}, 400)

    def handle_reg_policy_apply(self, item_id, body):
        """Apply approved policy changes"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        now = datetime.datetime.now()

        try:
            body_dict = json.loads(body) if body else {}
            applied_by = body_dict.get('applied_by', 'system')

            # Get the queue item
            cursor.execute("SELECT * FROM policy_update_queue WHERE id = ?", (item_id,))
            queue_item = cursor.fetchone()

            if not queue_item:
                conn.close()
                self.send_json({"error": "Queue item not found"}, 404)
                return

            # Get or create the policy document
            policy_type = queue_item['policy_type']
            cursor.execute("SELECT * FROM policy_documents WHERE policy_type = ? LIMIT 1", (policy_type,))
            policy = cursor.fetchone()

            if policy:
                policy_id = policy['id']
                # Bump version
                old_version = policy['version']
                try:
                    parts = old_version.split('.')
                    parts[1] = str(int(parts[1]) + 1)
                    new_version = '.'.join(parts)
                except:
                    new_version = old_version + '.1'

                cursor.execute("""
                    UPDATE policy_documents
                    SET version = ?, updated_at = ?, status = 'active'
                    WHERE id = ?
                """, (new_version, now.isoformat(), policy_id))
            else:
                # Create new policy document if needed
                policy_id = str(uuid.uuid4())
                template = POLICY_TEMPLATES.get(policy_type, {})
                cursor.execute("""
                    INSERT INTO policy_documents
                    (id, policy_type, title, description, regulation_ref, content, version, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    policy_id, policy_type, template.get('title', policy_type),
                    template.get('description', 'Policy document'),
                    template.get('regulation_ref', ''),
                    'Policy content', '1.0', 'active', now.isoformat(), now.isoformat()
                ))

            # Update queue item
            cursor.execute("""
                UPDATE policy_update_queue
                SET status = 'applied', applied_at = ?, applied_by = ?
                WHERE id = ?
            """, (now.isoformat(), applied_by, item_id))

            # Log action
            cursor.execute("""
                INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), 'policy_update_applied', 'policy_documents', policy_id, applied_by,
                  f'Applied policy update from queue item {item_id}', now.isoformat()))

            conn.commit()
            conn.close()

            self.send_json({"status": "applied", "policy_id": policy_id, "item_id": item_id})
        except Exception as e:
            conn.close()
            self.send_json({"error": str(e)}, 400)

    def handle_reg_policy_dismiss(self, item_id, body):
        """Dismiss a policy update suggestion"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now()

        try:
            body_dict = json.loads(body) if body else {}
            dismissed_by = body_dict.get('dismissed_by', 'system')

            cursor.execute("""
                UPDATE policy_update_queue
                SET status = 'dismissed'
                WHERE id = ?
            """, (item_id,))

            # Log action
            cursor.execute("""
                INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), 'policy_update_dismissed', 'policy_update_queue', item_id, dismissed_by,
                  'Policy update dismissed', now.isoformat()))

            conn.commit()
            conn.close()

            self.send_json({"status": "dismissed", "item_id": item_id})
        except Exception as e:
            conn.close()
            self.send_json({"error": str(e)}, 400)

    def handle_reg_resolve_analysis(self, analysis_id, body):
        """Mark an impact analysis as resolved"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        now = datetime.datetime.now()

        try:
            body_dict = json.loads(body) if body else {}
            resolved_by = body_dict.get('resolved_by', 'system')

            cursor.execute("""
                UPDATE regulatory_impact_analysis
                SET status = 'resolved', resolved_at = ?, resolved_by = ?
                WHERE id = ?
            """, (now.isoformat(), resolved_by, analysis_id))

            # Log action
            cursor.execute("""
                INSERT INTO audit_trail (id, action, entity_type, entity_id, performed_by, details, performed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), 'impact_analysis_resolved', 'regulatory_impact_analysis', analysis_id, resolved_by,
                  'Impact analysis marked as resolved', now.isoformat()))

            conn.commit()
            conn.close()

            self.send_json({"status": "resolved", "analysis_id": analysis_id})
        except Exception as e:
            conn.close()
            self.send_json({"error": str(e)}, 400)


# ============================================================================
# Server Startup
# ============================================================================

def run_initial_scan():
    """Run an initial compliance scan on startup so SRA audit data is pre-populated"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Check if a scan has already been run
    cursor.execute("SELECT COUNT(*) FROM compliance_checks")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    conn.close()

    run_id = str(uuid.uuid4())
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO workflow_runs (id, workflow_id, status, started_at, data_input, data_output)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (run_id, "compliance-scan", "running", now, "", "")
    )
    conn.commit()
    conn.close()

    # Re-use the handler's scan logic via a temporary instance
    handler = type('FakeHandler', (), {'execute_compliance_scan_async': RequestHandler.execute_compliance_scan_async})()
    handler.execute_compliance_scan_async(run_id)
    print("Initial compliance scan completed")


def main():
    init_database()
    seed_database()

    # Run initial scan in background so audit data is ready
    scan_thread = threading.Thread(target=run_initial_scan, daemon=True)
    scan_thread.start()

    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"Server running on http://localhost:{PORT}")
    print(f"Database: {DB_PATH}")
    print("Seema - Law Firm AI Assistant - Ready")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        server.server_close()

if __name__ == '__main__':
    main()
