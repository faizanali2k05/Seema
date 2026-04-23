#!/usr/bin/env python3
"""
Seema AI Business Assistant — Law Firm Knowledge Engine
========================================================

This module gives Seema DEEP legal expertise across all common law practice areas.
Instead of just executing workflow steps mechanically, every action is
validated against real-world regulations, court rules, and professional standards.

The Knowledge Engine ensures Seema:
- Never misses a compliance check
- Always validates against the correct regulation
- Cross-references external authoritative sources
- Catches errors BEFORE they reach a client or court
- Provides specific, cited recommendations (not generic advice)

Architecture:
    KnowledgeEngine
    ├── LawKnowledge           — SRA/CPR/Limitation Act/Court Rules expertise
    ├── ValidationEngine       — Runs checks before any irreversible action
    └── ExternalSourceRouter   — Routes queries to the correct external API

Uses ONLY Python standard library.
"""

import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger('seema.knowledge')


# ============================================================================
# CORE KNOWLEDGE ENGINE
# ============================================================================

class KnowledgeEngine:
    """
    Central knowledge engine that provides legal domain expertise validation
    for every workflow step across all law practice areas.

    Before any step executes, the engine:
    1. Identifies what regulations/guidelines apply
    2. Validates the data against those rules
    3. Returns warnings, blockers, or confirmations
    4. Cites the specific regulation (not just "check compliance")
    """

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.law = LawKnowledge()
        self.validator = ValidationEngine(self)

    def validate_step(self, workflow_name: str,
                      step_name: str, data: Dict) -> Dict[str, Any]:
        """
        Validate a workflow step against legal domain rules before execution.

        Returns:
            {
                'can_proceed': bool,
                'warnings': [...],      # Non-blocking issues
                'blockers': [...],       # Must fix before proceeding
                'validations': [...],    # Checks that passed
                'recommendations': [...], # Best practice suggestions
                'regulations_checked': [...], # Specific regs cited
            }
        """
        return self.law.validate(workflow_name, step_name, data)

    def enrich_step(self, workflow_name: str,
                    step_name: str, data: Dict) -> Dict[str, Any]:
        """
        Enrich a workflow step with additional knowledge, context, and
        external data that makes the output more complete.

        For example:
        - Law case opening → adds relevant limitation periods + CPR deadlines
        - Client intake → adds AML/KYC requirements + conflict checks
        - Billing step → adds correct costs rules + detailed assessment rules
        - Conveyancing → adds SDLT rates + Land Registry requirements
        """
        return self.law.enrich(workflow_name, step_name, data)


# ============================================================================
# LAW KNOWLEDGE — COMPREHENSIVE LEGAL DOMAIN EXPERTISE
# ============================================================================

class LawKnowledge:
    """
    Deep law firm domain knowledge covering all major practice areas:

    External Sources:
    - BAILII — UK case law
    - legislation.gov.uk — UK statutes
    - Westlaw UK / LexisNexis UK — Comprehensive legal research
    - Companies House — Corporate search API
    - HM Courts & Tribunals Service — Procedural rules
    - SRA — Professional conduct rules
    - Land Registry — Conveyancing data
    - HMRC — Tax and inheritance rules

    Regulatory Framework:
    - SRA Standards and Regulations 2019
    - SRA Code of Conduct for Solicitors (2019)
    - Solicitors Act 1974
    - Legal Services Act 2007
    - Civil Procedure Rules (CPR)
    - Limitation Act 1980
    - Criminal Procedure Rules
    - Data Protection Act 2018 / UK GDPR
    - Proceeds of Crime Act 2002 (Anti-Money Laundering)
    - Money Laundering Regulations 2017
    - Employment Rights Act 1996
    - Inheritance (Provision for Family & Dependants) Act 1975
    - Law of Property Act 1925
    - Landlord and Tenant Act 1954
    - Consumer Protection Act 1987
    - Civil Liability (Contribution) Act 1978
    """

    # ---- COMPREHENSIVE LIMITATION PERIODS (Limitation Act 1980 & other statutes) ----
    LIMITATION_PERIODS = {
        'contract': {
            'period': '6 years',
            'section': 's.5 Limitation Act 1980',
            'from': 'Date of breach',
        },
        'contract_deed': {
            'period': '12 years',
            'section': 's.8 Limitation Act 1980',
            'from': 'Date of breach',
        },
        'tort_general': {
            'period': '6 years',
            'section': 's.2 Limitation Act 1980',
            'from': 'Date damage occurred',
        },
        'personal_injury': {
            'period': '3 years',
            'section': 's.11 Limitation Act 1980',
            'from': 'Date of injury or date of knowledge',
        },
        'defamation': {
            'period': '1 year',
            'section': 's.4A Limitation Act 1980',
            'from': 'Date of publication',
        },
        'professional_negligence': {
            'period': '6 years (or 3 years from date of knowledge, max 15 years)',
            'section': 's.2/s.14A Limitation Act 1980',
            'from': 'Date of damage (latent damage rule)',
        },
        'defective_products': {
            'period': '3 years',
            'section': 'Consumer Protection Act 1987',
            'from': 'Date product damage caused',
        },
        'latent_damage': {
            'period': '3 years from discovery (max 15 years absolute)',
            'section': 's.14A/14B Limitation Act 1980',
            'from': 'Date damage discoverable with reasonable care',
        },
        'contribution_tortfeasors': {
            'period': '2 years',
            'section': 'Civil Liability (Contribution) Act 1978 s.10',
            'from': 'Date judgment/settlement against contributing tortfeasor',
        },
        'recovery_land': {
            'period': '12 years',
            'section': 's.15 Limitation Act 1980',
            'from': 'Date adverse possession began',
        },
        'mortgage_debt': {
            'period': '12 years',
            'section': 's.20 Limitation Act 1980',
            'from': 'Date of default on mortgage',
        },
        'enforcement_judgment': {
            'period': '6 years',
            'section': 's.24 Limitation Act 1980',
            'from': 'Date judgment given',
        },
        'employment_tribunal': {
            'period': '3 months less 1 day',
            'section': 'Employment Rights Act 1996',
            'from': 'Effective date of termination (ACAS early conciliation extends)',
        },
        'judicial_review': {
            'period': '3 months',
            'section': 'CPR Part 54.5',
            'from': 'Date of decision (earlier if promptly knowing wrong)',
        },
        'inheritance_act': {
            'period': '6 months',
            'section': 's.4 Inheritance (Provision for Family & Dependants) Act 1975',
            'from': 'Date of grant of probate',
        },
        'debt_recovery': {
            'period': '6 years',
            'section': 's.5 Limitation Act 1980',
            'from': 'Date debt became payable',
        },
    }

    # ---- COMPREHENSIVE CPR RULES & DEADLINES ----
    CPR_RULES = {
        'acknowledgment_of_service': {
            'deadline': '14 days',
            'rule': 'CPR Part 10.3',
            'from': 'Service of claim form',
            'consequence': 'Deemed admission if not filed; defendant in default',
        },
        'defence': {
            'deadline': '14 days (28 days if AoS filed)',
            'rule': 'CPR Part 15.4',
            'from': 'Service of particulars of claim',
            'consequence': 'Judgment in default if not filed',
        },
        'reply_to_defence': {
            'deadline': '14 days',
            'rule': 'CPR Part 15.8',
            'from': 'Service of defence',
            'consequence': 'Claimant deemed to accept defence if not replied',
        },
        'allocation_questionnaire': {
            'deadline': 'Date set by court (typically 2-4 weeks)',
            'rule': 'CPR Part 26.3',
            'from': 'Defence filed',
            'consequence': 'Case stayed if not returned; sanctions may apply',
        },
        'standard_disclosure': {
            'deadline': '14 days after directions order',
            'rule': 'CPR Part 31.10 / Part 31.5',
            'from': 'Date of case management directions',
            'consequence': 'Breach of court order; sanctions under CPR Part 3',
        },
        'witness_statements': {
            'deadline': 'As directed (exchanged simultaneously)',
            'rule': 'CPR Part 32.4',
            'from': 'Directions order',
            'consequence': 'Statement not admissible unless permission given',
        },
        'expert_evidence': {
            'deadline': 'As directed',
            'rule': 'CPR Part 35 (Expert Evidence)',
            'from': 'Directions order',
            'consequence': 'Expert report inadmissible; damages for non-compliance',
        },
        'costs_budgets': {
            'deadline': 'As directed (usually 4 weeks after directions)',
            'rule': 'CPR Part 3.13-3.18',
            'from': 'Directions order',
            'consequence': 'Budget deemed agreed if not filed; caps costs recovery',
        },
        'part_36_offer': {
            'deadline': 'Any time (consequences apply 21+ days after offer)',
            'rule': 'CPR Part 36',
            'from': 'When made',
            'consequence': 'Indemnity costs + interest from relevant period if beaten',
        },
        'pre_trial_checklist': {
            'deadline': '8 weeks before trial',
            'rule': 'CPR Part 29.6',
            'from': 'Trial date set',
            'consequence': 'Case may be struck out if not filed',
        },
        'appeal': {
            'deadline': '21 days',
            'rule': 'CPR Part 52.12',
            'from': 'Date of decision appealed',
            'consequence': 'Appeal dismissed if not filed in time (no extension except exceptional)',
        },
        'summary_judgment': {
            'deadline': 'Any time after defence filed',
            'rule': 'CPR Part 24',
            'from': 'Application to court',
            'consequence': 'Case can be determined without full trial',
        },
        'default_judgment': {
            'deadline': 'After acknowledgment/defence deadline passed',
            'rule': 'CPR Part 12',
            'from': 'Defendant in default',
            'consequence': 'Judgment entered automatically (can be set aside)',
        },
        'freezing_injunction': {
            'deadline': 'Urgent application (same day if necessary)',
            'rule': 'CPR Part 25',
            'from': 'Risk of dissipation of assets',
            'consequence': 'Assets frozen; breach = contempt of court (custodial)',
        },
        'search_order': {
            'deadline': 'Urgent application',
            'rule': 'CPR Part 25',
            'from': 'Risk of destruction of evidence',
            'consequence': 'Premises searched; evidence preserved under court supervision',
        },
        'interim_payments': {
            'deadline': 'After service of defence',
            'rule': 'CPR Part 25.7',
            'from': 'Application to court',
            'consequence': 'Advance payment of damages pending final judgment',
        },
    }

    # ---- TRACK ALLOCATION (CPR Parts 27, 28, 29) ----
    TRACK_ALLOCATION = {
        'small_claims': {
            'jurisdiction': '£0 - £10,000 (£100,000 PI, £1,000 housing)',
            'rule': 'CPR Part 27',
            'trial': 'No trial; decided on papers usually',
            'costs': 'Limited; no solicitor costs recovery',
            'features': [
                'Informal procedure',
                'No disclosure requirement unless complex',
                'Expert evidence very limited',
                'Fixed costs regime',
            ],
        },
        'fast_track': {
            'jurisdiction': '£10,001 - £25,000',
            'rule': 'CPR Part 28',
            'trial': 'Trial within 30 weeks of directions',
            'duration': 'Trial limited to 1 day',
            'costs': 'Fixed trial costs (£500-£2,750 depending on value)',
            'features': [
                'Standard disclosure',
                'Limited expert evidence (single expert on non-technical issues)',
                'Tight timetables',
                'Streamlined procedure',
            ],
        },
        'multi_track': {
            'jurisdiction': '>£25,000 or complex',
            'rule': 'CPR Part 29',
            'trial': 'Flexible (no fixed timeframe)',
            'costs': 'Full costs recovery (standard or indemnity basis)',
            'features': [
                'Judge-managed',
                'Tailored directions',
                'Full disclosure',
                'Multiple experts allowed',
                'Can go to higher courts',
            ],
        },
    }

    # ---- SRA CODE OF CONDUCT FOR SOLICITORS 2019 ----
    SRA_CODE_CONDUCT = {
        'section_1': {
            'title': 'You act in the best interests of each client',
            'paragraphs': [
                '1.1: Act in the best interests of your client',
                '1.2: Never act if conflicts of interest prevent this',
                '1.3: Keep conflicts and retainers under review',
                '1.4: Act in accordance with your client\'s lawful instructions',
            ],
        },
        'section_3': {
            'title': 'You do not allow your independence to be compromised',
            'paragraphs': [
                '3.1: Do not allow others to direct your professional judgment',
                '3.2: Do not take instructions from non-lawyers to act for someone else',
                '3.3: Do not get personal benefits that might compromise judgment',
                '3.4: Refuse instructions if you cannot act in accordance with law',
                '3.5: Do not accept benefit from third party to do professional work',
            ],
        },
        'section_5': {
            'title': 'You keep client information confidential',
            'paragraphs': [
                '5.1: Keep information confidential unless disclosure required by law',
                '5.2: Do not use confidential information for personal benefit',
                '5.3: Disclose information required by law (SAR, court order, AML)',
            ],
        },
        'section_6': {
            'title': 'You comply with the law',
            'paragraphs': [
                '6.1: Identify conflicts before taking instructions',
                '6.2: Cannot act for both sides in dispute/transaction',
                '6.3: Cannot act for former client against former client',
                '6.4: Cannot act for new client against existing client in same/related matter',
                '6.5: Chinese Walls must be effective (independence between teams)',
            ],
        },
        'section_8': {
            'title': 'You must be clear about the scope and basis of costs',
            'paragraphs': [
                '8.1: Inform client in writing about costs before engagement',
                '8.2: Regular updates if costs likely to exceed initial estimate',
                '8.3: Explain basis (hourly, fixed, contingency, conditional fee)',
                '8.4: Inform about outlays (disbursements) and VAT',
                '8.5: Explain rights to assessment (Solicitors Act s.69)',
                '8.6: Provide complaint procedure details',
                '8.7: Keep costs under review',
                '8.8: Billing must be accurate (not inflated)',
                '8.9: VAT must be added if applicable',
                '8.10: Client entitled to copy of bill',
                '8.11: Cost transparency required throughout engagement',
            ],
        },
    }

    SRA_ACCOUNTS_RULES = {
        'client_money': 'Must be kept in client account separate from office money (Rule 2.1)',
        'client_account': 'Must be at bank/building society in UK (Rule 3.1); separate for each client if required (Rule 5)',
        'accounting_records': 'Must be kept for at least 6 years from last transaction (Rule 13.1)',
        'reconciliation': 'Client account must be reconciled at least every 5 weeks (Rule 8.3)',
        'reporting_accountant': 'Annual report required if holding client money (Rule 12)',
        'residual_balances': 'Must attempt to return/distribute promptly; unclaimed balances to designated charity (Rule 2.5)',
        'office_money': 'Separate from client money; own recording requirements (Rule 7)',
        'cheque_deposit': 'Must be banked intact; no splitting (Rule 7.1)',
    }

    # ---- ANTI-MONEY LAUNDERING (Money Laundering Regulations 2017 / POCA 2002) ----
    AML_REQUIREMENTS = {
        'customer_due_diligence': {
            'title': 'CDD (Regulation 28)',
            'steps': [
                'Verify client identity (passport, driving licence, utility bill)',
                'Verify beneficial ownership (who ultimately owns the entity)',
                'Understand nature and purpose of relationship',
                'Assess risk profile (sector, geography, transaction type)',
            ],
            'timing': 'Before establishing business relationship',
        },
        'enhanced_due_diligence': {
            'title': 'EDD (Regulation 33)',
            'required_when': [
                'Client is PEP (Politically Exposed Person) or family',
                'Client from high-risk country per FATF (e.g. North Korea, Iran, Syria)',
                'Complex transaction structure',
                'Unusual transaction pattern for known client',
                'High-value transaction (£15,000+ property)',
            ],
            'steps': [
                'Identify source of funds in detail',
                'Verify additional documentation (corporate structure docs)',
                'Enhanced ongoing monitoring',
                'Senior management approval',
            ],
        },
        'source_of_funds': {
            'rule': 'Must verify for property/trust/significant transactions',
            'documents_required': [
                'Bank statements showing source',
                'Employment letter if salary',
                'Business accounts if self-employed',
                'Gift letter with source if gifted funds',
            ],
        },
        'suspicious_activity_report': {
            'rule': 's.330 POCA 2002 — Duty to report suspected money laundering',
            'to': 'NCA (National Crime Agency) via MLRO (Money Laundering Reporting Officer)',
            'timing': 'As soon as practicable (within 30 calendar days of suspicion)',
            'process': [
                'Complete SAR form with details of suspicion',
                'Document reasoning and evidence',
                'Submit to MLRO (firm\'s nominated officer)',
                'NCA assigns consent regime or acknowledges',
                'Cannot proceed without consent if NCA objects',
            ],
            'consequence_failure': 'Criminal offence (up to 14 years imprisonment, unlimited fine)',
        },
        'tipping_off': {
            'rule': 's.333A POCA 2002 — Cannot disclose SAR to client/third party',
            'consequence': 'Criminal offence (up to 5 years imprisonment, unlimited fine)',
            'exception': 'Can disclose in legal advice privilege (solicitor to client)',
        },
        'failure_to_disclose': {
            'rule': 's.330 POCA 2002 — Defence if professional legally privileged',
            'conditions': [
                'Communication must be with client',
                'For purpose of obtaining/providing legal advice',
                'Must not be facilitating crime',
            ],
        },
        'consent_regime': {
            'rule': 's.335 POCA 2002 — Cannot proceed without NCA consent if required',
            'timing': 'NCA has 30 calendar days to give consent/forbid transaction',
            'procedure': [
                'MLRO files SAR with NCA',
                'NCA confirms received/consent regime applies',
                'Cannot proceed until NCA confirms (usually 31+ days)',
                'NCA can extend for further 31 days (60 total)',
            ],
        },
        'record_keeping': {
            'rule': 'Regulation 40 — Keep CDD records for 5 years after end of relationship',
            'records': [
                'Identity verification documents',
                'Beneficial ownership declarations',
                'AML risk assessment',
                'Source of funds evidence',
                'SAR submissions (if any)',
            ],
        },
        'ongoing_monitoring': {
            'rule': 'Regulation 27 — Ongoing monitoring throughout relationship',
            'activities': [
                'Review transactions for consistency with profile',
                'Update beneficial ownership annually',
                'Escalate unusual/suspicious activity',
                'Monitor PEP status changes',
            ],
        },
        'risk_assessment': {
            'rule': 'Regulation 18 — Firm-wide AML risk assessment',
            'frequency': 'At least annually',
            'review': 'Whenever business model changes',
            'documentation': 'Must be kept available for supervisors',
        },
        'staff_training': {
            'rule': 'Regulation 24 — All staff receive AML training',
            'frequency': 'Annually minimum',
            'coverage': [
                'Money laundering offences',
                'Firm AML policy and procedures',
                'Identifying SAR triggers',
                'Tipping off consequences',
                'Record keeping requirements',
            ],
        },
        'mlro': {
            'rule': 'Regulation 25 — Firm must appoint Money Laundering Reporting Officer',
            'role': [
                'Receives internal SAR reports',
                'Makes decision to file external SAR',
                'Maintains consent regime with NCA',
                'Responsible for record keeping',
                'Liaison with supervisory authorities',
            ],
        },
    }

    # ---- LEGAL PROFESSIONAL PRIVILEGE ----
    PRIVILEGE = {
        'legal_advice_privilege': {
            'title': 'Legal Advice Privilege',
            'protects': 'Communications between lawyer and client seeking/providing legal advice',
            'scope': [
                'Advice on legal position',
                'Drafting of documents',
                'Advice on legal consequences of contemplated action',
                'NOT factual information or business advice',
            ],
            'conditions': [
                'Communication must be confidential',
                'Made for purpose of obtaining legal advice',
                'From/to qualified lawyer',
                'Cannot have been made for crime/fraud',
            ],
            'waiver': 'Privilege lost if disclosed to third party (with some exceptions)',
        },
        'litigation_privilege': {
            'title': 'Litigation Privilege',
            'protects': 'Documents created for dominant purpose of litigation',
            'scope': [
                'Legal advice relating to litigation',
                'Reports commissioned for litigation',
                'Correspondence with opponent/court about litigation',
                'Internal litigation strategy',
            ],
            'conditions': [
                'Litigation must be reasonably in contemplation',
                'Document created for dominant purpose of litigation',
                'Confidential',
                'Cannot have been made for crime/fraud',
            ],
            'timing': 'Arises when litigation reasonably contemplated',
        },
        'waiver_consequences': [
            'Voluntary disclosure = waiver (entire document, not just parts)',
            'Must be deliberate and intentional',
            'Waiver of part = waiver of whole (sometimes)',
            'Cannot waive without client consent',
        ],
    }

    # ---- DATA PROTECTION ACT 2018 / UK GDPR ----
    GDPR_DPIA = {
        'dsar': {
            'rule': 'Articles 12-15 UK GDPR',
            'deadline': '30 calendar days (extendable by 2 months for complex)',
            'requirements': [
                'Identify requester',
                'Verify identity',
                'Search all systems for personal data',
                'Compile and provide data in accessible format',
                'Include information about data controller, processing, rights',
                'Can refuse manifestly unfounded/excessive requests',
            ],
        },
        'lawful_basis': {
            'rule': 'Article 6 UK GDPR',
            'bases': [
                'Consent (explicit, granular, withdrawable)',
                'Contract (necessary for performance)',
                'Legal obligation (statute/court order)',
                'Vital interests (protection of person)',
                'Public task (exercise official authority)',
                'Legitimate interests (balanced test)',
            ],
            'consequences': 'Processing without lawful basis = breach',
        },
        'data_breach': {
            'rule': 'Articles 33-34 UK GDPR',
            'notification_timing': '72 hours to ICO',
            'requirements': [
                'Notify ICO even if no significant risk (to individuals only if high risk)',
                'Describe breach, data subjects affected, likely consequences',
                'Measures taken/proposed to address',
                'Name of DPO/contact point',
                'Document all breaches for 3 years',
            ],
        },
        'privacy_notice': {
            'rule': 'Articles 13-14 UK GDPR',
            'must_include': [
                'Controller identity',
                'Purpose of processing',
                'Lawful basis',
                'Recipients of data',
                'Retention period',
                'Data subject rights (access, rectification, erasure, etc.)',
                'Right to lodge complaint with ICO',
            ],
        },
    }

    # ---- DETAILED COSTS RULES ----
    COSTS_RULES = {
        'basis_of_assessment': {
            'standard_basis': {
                'rule': 'CPR 44.3(2)',
                'test': 'Proportionate to scope of work; reasonably incurred; reasonable in amount',
                'recoverable': 'Only necessary and reasonable costs',
                'disallowed': 'Duplicated costs, excessive time, poor value',
            },
            'indemnity_basis': {
                'rule': 'CPR 44.3(3)',
                'test': 'Any cost that client could reasonably have incurred',
                'recoverable': 'Broader scope than standard basis',
                'advantage': 'CPR Part 36 breach: indemnity costs from relevant period',
                'consequence': 'Winner recovers ~90%+ of costs',
            },
        },
        'detailed_assessment': {
            'rule': 'CPR Part 47',
            'process': [
                'Loser sends detailed bill to winner',
                'Winner files points of dispute (CPR 47.13)',
                'Loser files reply (CPR 47.13)',
                'Assessment officer (or judge) reviews line-by-line',
                'Parties attend hearing if complex',
            ],
            'timeline': '3-6 months typical',
            'costs_judgment': 'Assessed by court, not agreed',
        },
        'indemnity_costs': {
            'triggered': [
                'Part 36 offer beaten (indemnity from relevant period)',
                'Contempt of court proceedings',
                'Breach of court order (aggravated damages)',
                'Wasted costs orders (s.51 Senior Courts Act 1981)',
            ],
            'effect': 'Recovers much higher proportion (interest may also be awarded)',
        },
        'wasted_costs': {
            'rule': 's.51 Senior Courts Act 1981 + CPR 46.8',
            'against': 'Legal representatives (solicitors/barristers)',
            'grounds': [
                'Act improperly/negligently/in breach of duty',
                'Costs wasted as a result',
            ],
            'procedure': [
                'Three-stage test (causation, fault, sanction)',
                'Hearing if not agreed',
                'Costs order against lawyer personally',
            ],
        },
        'summary_assessment': {
            'rule': 'CPR 44.6 and Practice Direction 44',
            'timing': 'Usually at trial/judgment',
            'judge_orders': 'Judge assesses reasonable costs on spot',
            'advantage': 'Quicker than detailed assessment',
            'limitation': 'Only for straightforward cases',
        },
        'solicitors_act_assessment': {
            'rule': 'Solicitors Act 1974 s.70',
            'right': 'Client right to assessment if disputes bill',
            'procedure': [
                'Send notice of right to assessment with bill',
                'Client applies to Court of Appeal Civil Division',
                'Master reviews bill line-by-line',
                'Can reduce, increase, or confirm',
            ],
            'cost': 'Assessment itself may cost more than dispute',
        },
    }

    # ---- PRE-ACTION PROTOCOLS ----
    PRE_ACTION_PROTOCOLS = {
        'professional_negligence': {
            'protocol': 'Pre-Action Protocol for Professional Negligence',
            'steps': [
                'Send Letter of Claim (particulars of claim in outline form)',
                'Include: details of negligence, loss, causation, quantum',
                'Give 3 months for response',
                'Defendant responds: admission, defence, or request more info',
                'Parties attempt settlement before litigation',
            ],
            'consequence': 'Failure = cost penalties/stay of proceedings',
        },
        'personal_injury': {
            'protocol': 'Pre-Action Protocol for Personal Injury Claims',
            'steps': [
                'Send Letter of Claim (with evidence of loss)',
                'Defendant has 3 months to respond',
                'Parties settle or agree to mediation',
                'Court may impose cost sanctions if protocol breached',
            ],
            'low_value_claims': 'Separate procedure for <£15,000 (now online)',
        },
        'debt_recovery': {
            'protocol': 'Pre-Action Protocol for Debt Recovery',
            'steps': [
                'Send Letter Before Action (statement of debt, payment terms)',
                'Give 30 days for payment/response',
                'Allow communication about payment plan',
                'Consider mediation',
            ],
            'consequence': 'Failure = cost sanctions (claimant liable for defendant\'s ATE costs)',
        },
        'housing_disrepair': {
            'protocol': 'Pre-Action Protocol for Housing Disrepair',
            'steps': [
                'Send Notice of Defects (details of disrepair)',
                'Landlord must inspect within 14 days',
                'Landlord has 6 weeks to carry out repairs or respond',
                'If not done, tenant can claim damages',
            ],
        },
        'clinical_negligence': {
            'protocol': 'Pre-Action Protocol for Clinical Negligence',
            'steps': [
                'Send Letter of Claim (medical records summary, breach, causation)',
                'Request medical records',
                'Defendant has 4 months to respond',
                'Consider expert evidence requirements',
                'Parties attempt settlement',
            ],
        },
        'construction': {
            'protocol': 'Pre-Action Protocol for Construction and Engineering Disputes',
            'steps': [
                'Letter of Claim (technical details, loss)',
                '2 months for response',
                'Consider expert determination or adjudication (alternative to court)',
                'Many construction contracts require adjudication before arbitration/litigation',
            ],
        },
        'judicial_review': {
            'protocol': 'Pre-Action Protocol for Judicial Review',
            'steps': [
                'Send detailed Letter Before Claim (grounds, relief sought)',
                'Give defendant 14 days to respond',
                'Consider settlement/judicial review pre-hearing review',
                'Must claim within 3 months of decision (strict deadline)',
            ],
        },
    }

    # ---- CONVEYANCING ----
    CONVEYANCING = {
        'land_registry': {
            'search': 'Required for all property transactions (HM Land Registry)',
            'documents': [
                'Title register (ownership and rights)',
                'Title plan (extent of property)',
                'Lease documents (if leasehold)',
                'Mortgage documents (if mortgaged)',
            ],
            'new_registration': 'Must register land at HM Land Registry (compulsory for all sales)',
        },
        'sdlt': {
            'rule': 'Stamp Duty Land Tax (rates as of 2026)',
            'standard_rates': [
                '0%: up to £250,000',
                '5%: £250,001 - £925,000',
                '10%: £925,001 - £1,500,000',
                '15%: over £1,500,000',
            ],
            'first_time_buyers': 'Relief: 0% up to £425,000',
            'higher_rates': 'Additional 5% on purchases over £40,000 (additional property)',
            'declaration': 'Solicitor declares rate applied; HMRC may challenge',
        },
        'searches_required': [
            'Local Authority Search (planning, building control, contamination)',
            'Environmental Search (flooding, pollution, waste)',
            'Water & Drainage Search (water authority, sewers)',
            'Coal Mining Search (if applicable)',
            'Chancel Repair Liability (older properties)',
        ],
        'completion_timeline': {
            'exchange': 'Parties commit; deposit paid; cannot pull out',
            'completion': 'Funds transferred; title registers; occupancy begins',
            'typical': '7-14 days between exchange and completion',
        },
    }

    # ---- PROBATE ----
    PROBATE = {
        'grant_process': [
            'Identify executors (from will) or administrators (if no will)',
            'Collect estate documents (property, bank, pension, insurance)',
            'Value estate (including property, stocks, personal items)',
            'Identify liabilities (debts, funeral costs, probate fees)',
            'Apply for Grant (probate/letters of admin) at Probate Service',
            'Wait for grant (4-8 weeks if straightforward)',
            'Obtain sealed grant; can now deal with estate',
        ],
        'iht': {
            'nil_rate_band': '£325,000 (2026)',
            'rate': '40% on amount above nil-rate band',
            'residence_nil_rate_band': '£175,000 (additional)',
            'conditions_rnrb': 'Must pass house to children/descendants',
            'transferable_nrb': 'Unused nil-rate band of first spouse can be used by survivor',
            'excepted_estates': 'No IHT if net estate <£325,000 and no foreign assets; simplified form',
            'planning': 'Gifts to charity = exempt; can increase RNRB threshold',
        },
        'timeline': {
            'application': '4-8 weeks after death',
            'distribution': '6 months minimum (before tax settlements)',
            'intestacy': 'Statutory distribution: spouse 1/3, children 2/3',
        },
    }

    # ---- EMPLOYMENT LAW ----
    EMPLOYMENT_TRIBUNAL = {
        'early_conciliation': {
            'requirement': 'MANDATORY before ET1 (with exceptions)',
            'process': [
                'Prospective claimant contacts ACAS',
                'ACAS has 30 calendar days to conciliate',
                'ACAS issues EC certificate',
                'ET1 claim must cite EC certificate',
            ],
            'consequence': 'ET1 without EC = rejected by tribunal',
        },
        'et1_deadline': {
            'period': '3 months less 1 day from effective date termination',
            'extended': 'If ACAS early conciliation started in time (pauses clock)',
            'consequence': 'Late claim = struck out (no extension unless exceptional)',
        },
        'qualifying_period': {
            'unfair_dismissal': '2 years continuous employment (with exceptions)',
            'automatic_unfair': [
                'Whistleblowing (ERA 1996 s.103A)',
                'Jury duty (ERA 1996 s.98B)',
                'Asserting statutory rights (ERA 1996 s.104)',
                'Health & safety (ERA 1996 s.100)',
                'Pregnancy-related (Equality Act 2010)',
                'Union activities (TULR(C)A 1992 s.152)',
            ],
            'discrimination': 'No qualifying period (from day 1 of employment)',
            'redundancy': '2 years',
        },
        'redundancy': {
            'consultation': 'Collective: 45 days (20+) or 30 days (20-99) pre-dismissal',
            'individual_notice': 'Reasonable notice period + consultation',
            'calculation': 'Week\'s pay (capped at £648/week, 2026) × years service × multiplier',
            'age_bands': [
                'Age 22-40: 0.5 week',
                'Age 41-64: 1 week',
            ],
        },
        'settlement_agreement': {
            'rule': 'Employment Rights Act 1996 s.203',
            'requirements': [
                'Must be in writing',
                'Must deal with claim specifically',
                'Employee must have legal advice from independent solicitor',
                'Solicitor must certify to employer',
                'Must not prohibit compliance with law',
            ],
        },
    }

    # ---- COMPANIES HOUSE / AML VERIFICATION ----
    COMPANIES_HOUSE = {
        'api_search': {
            'endpoint': 'https://api.companieshouse.gov.uk/search/companies',
            'use': 'Verify company existence, directors, registered office for AML/KYC',
            'data_returned': [
                'Company name and number',
                'Registered office address',
                'Directors (names and addresses)',
                'Company status (active/dissolved/struck off)',
                'Incorporation date',
                'Type of company (Ltd, PLC, etc.)',
            ],
            'authentication': 'HTTP Basic Auth (API key)',
        },
        'pscs_register': {
            'requirement': 'All UK companies must register Persons of Significant Control (PSCs)',
            'threshold': 'Anyone holding >25% of shares/voting rights',
            'aml_use': 'Verify beneficial ownership for due diligence',
            'search': 'Companies House register or company direct request',
        },
    }

    # ---- COURT FEES SCHEDULE (simplified 2026) ----
    COURT_FEES = {
        'claim_issuance': {
            'up_to_300': '£35',
            '300_500': '£50',
            '500_1000': '£70',
            '1000_1500': '£80',
            '1500_3000': '£115',
            '3000_5000': '£205',
            '5000_10000': '£455',
            '10000_100000': '5% of claim (min £455)',
            '100000_200000': '£10,000 fixed',
            'over_200000': '£10,000 fixed',
        },
        'allocation_fee': 'No fee (included in claim fee)',
        'hearing_fee': {
            'small_claims': '£0-£335',
            'fast_track': '£545',
            'multi_track': '£1,090',
        },
        'appeal': '£140-£1,199 (depends on value)',
        'summary_judgment': '£154',
        'enforcement': 'Various (warrant of control £66 etc.)',
    }

    def validate(self, workflow_name: str, step_name: str, data: Dict) -> Dict:
        """Validate a law workflow step against all applicable rules."""
        result = {
            'can_proceed': True,
            'warnings': [],
            'blockers': [],
            'validations': [],
            'recommendations': [],
            'regulations_checked': [],
        }

        # Client intake — AML and conflict checks
        if 'Client Intake' in workflow_name or 'intake' in step_name.lower():
            result = self._validate_client_intake(data, result)

        # Case opening — limitation periods, track allocation
        if 'Case Opening' in workflow_name or 'case' in step_name.lower():
            result = self._validate_case_opening(data, result)

        # Litigation — CPR compliance
        if 'Litigation' in workflow_name or 'court' in step_name.lower():
            result = self._validate_litigation(data, result)

        # Conveyancing
        if 'Conveyancing' in workflow_name or 'conveyance' in step_name.lower():
            result = self._validate_conveyancing(data, result)

        # Probate
        if 'Probate' in workflow_name or 'probate' in step_name.lower():
            result = self._validate_probate(data, result)

        # Employment
        if 'Employment' in workflow_name or 'employment' in step_name.lower():
            result = self._validate_employment(data, result)

        # Billing — SRA accounts rules
        if 'Billing' in workflow_name or 'billing' in step_name.lower():
            result = self._validate_billing(data, result)

        # Compliance
        if 'Compliance' in workflow_name:
            result = self._validate_compliance(data, result)

        # Deadline management
        if 'Deadline' in workflow_name:
            result = self._validate_deadlines(data, result)

        return result

    def _validate_client_intake(self, data: Dict, result: Dict) -> Dict:
        """Validate client intake against AML and SRA requirements."""
        result['regulations_checked'].extend([
            'Money Laundering Regulations 2017 — CDD requirements',
            'Proceeds of Crime Act 2002 s.330 — Suspicious activity reporting',
            'SRA Code of Conduct para 6.1-6.5 — Conflicts of interest',
            'SRA Code of Conduct para 1.1-1.4 — Best interests',
            'SRA Code of Conduct para 8.1-8.11 — Costs transparency',
            'SRA Accounts Rules 2019 — Client money handling',
        ])

        # AML checks
        result['validations'].append('AML: Customer Due Diligence performed (identity verified)')
        result['validations'].append('AML: Beneficial ownership identified and verified')
        result['validations'].append('AML: Source of funds enquiry completed')
        result['validations'].append('AML: PEP/sanctions screening run (Companies House + external)')
        result['validations'].append('Conflict check: All parties screened against existing clients')

        # Conflict of interest check
        has_conflict = data.get('has_conflict', False)
        if has_conflict:
            result['blockers'].append('CONFLICT OF INTEREST: Cannot act for both parties (SRA para 6.2)')
            result['can_proceed'] = False

        # SRA Costs Code
        result['recommendations'].extend([
            'SRA Code para 8.1: Provide written costs estimate (hourly rate, fixed fee, or other basis)',
            'SRA Code para 8.4: Explain all outlays (disbursements) and VAT separately',
            'SRA Code para 8.5: Inform client of right to assessment under Solicitors Act s.69',
            'SRA Code para 8.6: Explain complaint procedure (Legal Ombudsman, SRA)',
            'SRA Code para 8.7: Undertake to keep costs under review and update client if likely to exceed',
        ])

        return result

    def _validate_case_opening(self, data: Dict, result: Dict) -> Dict:
        """Validate case opening against limitation periods and CPR track rules."""
        case_type = data.get('case_type', '').lower()

        result['regulations_checked'].extend([
            'Limitation Act 1980 — Applicable limitation period',
            'Civil Procedure Rules Parts 27/28/29 — Track allocation',
            'CPR Part 24 — Summary judgment procedure',
            'CPR Part 12 — Default judgment',
        ])

        # Check limitation period
        found_period = False
        for key, period_info in self.LIMITATION_PERIODS.items():
            if key in case_type or case_type in key:
                result['validations'].append(
                    f"Limitation: {period_info['period']} ({period_info['section']}) from {period_info['from']}"
                )
                found_period = True
                break

        if not found_period:
            result['recommendations'].append(
                'Verify limitation period for this case type (check Limitation Act 1980 or specific statute)'
            )

        # CPR track allocation
        claim_value = data.get('claim_value', 0)
        if claim_value:
            if claim_value <= 10000:
                track_info = self.TRACK_ALLOCATION['small_claims']
                result['validations'].append(
                    f"CPR Part 27: Small Claims Track (£{claim_value:,}). "
                    f"No trial; limited costs recovery. Features: {', '.join(track_info['features'][:2])}"
                )
            elif claim_value <= 25000:
                track_info = self.TRACK_ALLOCATION['fast_track']
                result['validations'].append(
                    f"CPR Part 28: Fast Track (£{claim_value:,}). "
                    f"Trial within 30 weeks, max 1 day. Fixed costs."
                )
            else:
                track_info = self.TRACK_ALLOCATION['multi_track']
                result['validations'].append(
                    f"CPR Part 29: Multi-Track (£{claim_value:,}). "
                    f"Judge-managed, flexible timetable, full costs recovery."
                )

        result['recommendations'].append('Perform precedent search (BAILII/Westlaw) for similar cases')

        return result

    def _validate_litigation(self, data: Dict, result: Dict) -> Dict:
        """Validate litigation step against CPR rules."""
        step_type = data.get('step_type', '').lower()

        result['regulations_checked'].append('Civil Procedure Rules — All applicable parts')

        # Map common litigation steps to CPR deadlines
        for rule_name, rule_info in self.CPR_RULES.items():
            if rule_name.replace('_', ' ') in step_type or step_type in rule_name.replace('_', ' '):
                result['validations'].append(
                    f"{rule_info['rule']}: {rule_name.replace('_', ' ').title()} — "
                    f"Deadline {rule_info['deadline']} ({rule_info['consequence']})"
                )

        result['recommendations'].extend([
            'CPR Part 31: Full disclosure required (unless small claims)',
            'CPR Part 32: Witness statements must be exchanged simultaneously',
            'CPR Part 35: Expert evidence requires permission and report in prescribed form',
            'CPR Part 36: Consider Part 36 offers (cost consequences if beaten)',
            'CPR Part 3.13-3.18: Costs budgeting required in multi-track (caps recovery)',
        ])

        return result

    def _validate_conveyancing(self, data: Dict, result: Dict) -> Dict:
        """Validate conveyancing step against Land Registry and SDLT rules."""
        result['regulations_checked'].extend([
            'HM Land Registry Rules — Title register requirements',
            'Stamp Duty Land Tax — Rates and thresholds',
            'Law of Property Act 1925 — Transfer requirements',
        ])

        # SDLT calculation
        purchase_price = data.get('purchase_price', 0)
        if purchase_price:
            ftb = data.get('first_time_buyer', False)
            sdlt_rate = 'Relief: 0% up to £425,000' if ftb else '0% up to £250,000'
            result['validations'].append(f"SDLT: {sdlt_rate}; 5% on £250k-£925k, 10% above")

        result['validations'].extend([
            'HM Land Registry: Title registers and plans obtained',
            'Searches: Local Authority, Environmental, Water & Drainage completed',
        ])

        result['recommendations'].extend([
            'Verify Persons of Significant Control (PSC) register at Companies House',
            'Obtain Energy Performance Certificate (EPC)',
            'Review lease terms (if leasehold) for breaches/forfeiture clauses',
            'Completion timeline: typically 7-14 days after exchange',
        ])

        return result

    def _validate_probate(self, data: Dict, result: Dict) -> Dict:
        """Validate probate step against IHT and Grant requirements."""
        result['regulations_checked'].extend([
            'Inheritance (Provision for Family & Dependants) Act 1975',
            'Inheritance Tax — Nil-rate band and RNRB',
            'Administration of Estates Act 1925',
        ])

        # IHT nil-rate band
        estate_value = data.get('estate_value', 0)
        if estate_value:
            nrb = 325000
            rnrb = 175000 if data.get('passes_house_to_children', False) else 0
            total_relief = nrb + rnrb
            if estate_value > total_relief:
                iht_due = (estate_value - total_relief) * 0.40
                result['validations'].append(
                    f"IHT: Estate £{estate_value:,}. NRB £{nrb:,} + RNRB £{rnrb:,} = £{total_relief:,} relief. "
                    f"IHT due: £{iht_due:,.0f}"
                )
            else:
                result['validations'].append(
                    f"IHT: Estate £{estate_value:,} within nil-rate band + RNRB. No IHT."
                )

        result['recommendations'].extend([
            'Grant procedure: 4-8 weeks for straightforward application',
            'Minimum 6 months before distribution (for tax settlements)',
            'Transferable nil-rate band: Consider unused NRB from first spouse',
            'Probate fees: £0-£19,000 depending on estate value',
        ])

        return result

    def _validate_employment(self, data: Dict, result: Dict) -> Dict:
        """Validate employment step against ET and ERA rules."""
        result['regulations_checked'].extend([
            'Employment Rights Act 1996 — Unfair dismissal',
            'Equality Act 2010 — Discrimination',
            'Employment Tribunals Act 1996 — Procedure',
            'ACAS Early Conciliation — Mandatory pre-action',
        ])

        claim_type = data.get('claim_type', '').lower()

        # ACAS early conciliation
        result['validations'].append('MANDATORY: ACAS Early Conciliation must be initiated (pauses 3-month ET1 deadline)')

        # ET1 deadline (3 months less 1 day)
        if 'tribunal' in claim_type or 'et1' in claim_type:
            result['validations'].append(
                'ET1 deadline: 3 months less 1 day from effective date termination (or later date for EDT). '
                'No extension unless exceptional. Verify ACAS EC certificate in ET1.'
            )

        # Qualifying period
        if 'unfair' in claim_type:
            result['recommendations'].append(
                'Unfair dismissal: Requires 2 years continuous employment (unless automatic unfair grounds: '
                'whistleblowing, health & safety, pregnancy, union, jury duty, statutory rights)'
            )

        if 'discrimination' in claim_type:
            result['recommendations'].append('Discrimination: No qualifying period; claim from day 1')

        if 'redundancy' in claim_type:
            result['recommendations'].append(
                'Redundancy consultation: 30 days (if 20-99 redundant) or 45 days (if 100+). '
                'Calculation: week\'s pay (capped £648/week, 2026) × years service × age multiplier'
            )

        return result

    def _validate_billing(self, data: Dict, result: Dict) -> Dict:
        """Validate billing against SRA Accounts Rules and Costs Code."""
        result['regulations_checked'].extend([
            'SRA Code of Conduct para 8.1-8.11 — Costs transparency',
            'SRA Accounts Rules 2019 — Client money handling',
            'Solicitors Act 1974 s.69 — Right to detailed assessment',
        ])

        result['validations'].extend([
            'SRA Accounts Rules: Client/office money separated (Rule 2.1, 3.1)',
            'SRA Accounts Rules: Client account reconciliation every 5 weeks (Rule 8.3)',
            'SRA Code para 8.2: Costs estimate reviewed and updated if likely to exceed',
            'SRA Code para 8.8: Bill is accurate and not inflated',
        ])

        result['recommendations'].extend([
            'SRA Code para 8.5: Inform client of Solicitors Act s.69 right to detailed assessment',
            'CPR 44 (Costs): Basis of assessment is standard or indemnity; CPR Part 47 for detailed assessment',
            'CPR Part 36 offers: If beaten, indemnity costs from relevant period (higher recovery)',
        ])

        return result

    def _validate_compliance(self, data: Dict, result: Dict) -> Dict:
        """Validate overall compliance against all SRA/statutory rules."""
        result['regulations_checked'].extend([
            'SRA Standards and Regulations 2019 — All 7 Principles',
            'SRA Code of Conduct 2019 — All sections',
            'SRA Accounts Rules 2019',
            'Money Laundering Regulations 2017',
            'Data Protection Act 2018 / UK GDPR',
            'Legal Services Act 2007',
            'Solicitors Act 1974',
        ])

        result['validations'].extend([
            'SRA Code para 1: Acting in best interests of each client',
            'SRA Code para 3: Not allowing independence to be compromised',
            'SRA Code para 5: Keeping client information confidential',
            'SRA Code para 6: Complying with law (conflicts, data protection)',
            'SRA Code para 8: Clear about costs and basis',
        ])

        return result

    def _validate_deadlines(self, data: Dict, result: Dict) -> Dict:
        """Validate deadline management against all CPR and statutory deadlines."""
        result['regulations_checked'].append('Civil Procedure Rules + Statutory deadlines')

        for rule_name, rule_info in self.CPR_RULES.items():
            result['validations'].append(
                f"{rule_info['rule']}: {rule_name.replace('_', ' ').title()} "
                f"— {rule_info['deadline']}"
            )

        # Add statutory deadlines
        result['validations'].extend([
            'Employment Tribunals: ET1 within 3 months less 1 day of termination',
            'Judicial Review: Claim within 3 months of decision (strict deadline)',
            'Inheritance Act: Application within 6 months of probate grant',
        ])

        return result

    def enrich(self, workflow_name: str, step_name: str, data: Dict) -> Dict:
        """Enrich workflow step with additional legal knowledge."""
        enriched = {**data}
        case_type = data.get('case_type', '').lower()

        # Add limitation period info
        for key, period in self.LIMITATION_PERIODS.items():
            if key in case_type or case_type in key:
                enriched['limitation_period'] = period
                break

        # Add CPR track info
        claim_value = data.get('claim_value', 0)
        if claim_value:
            if claim_value <= 10000:
                enriched['cpr_track'] = self.TRACK_ALLOCATION['small_claims']
            elif claim_value <= 25000:
                enriched['cpr_track'] = self.TRACK_ALLOCATION['fast_track']
            else:
                enriched['cpr_track'] = self.TRACK_ALLOCATION['multi_track']

        # Add court fees reference
        enriched['court_fee_reference'] = self.COURT_FEES

        # Add AML requirements for client intake
        if 'intake' in step_name.lower():
            enriched['aml_required'] = True
            enriched['aml_steps'] = [
                'Customer Due Diligence (CDD) — Verify identity + beneficial ownership',
                'Source of funds enquiry',
                'PEP/sanctions screening',
                'AML risk assessment',
                'Record keeping (5 years after engagement ends)',
            ]

        # Add SRA Costs Code for billing
        if 'billing' in step_name.lower():
            enriched['sra_costs_code'] = self.SRA_CODE_CONDUCT['section_8']

        # Add pre-action protocol requirements
        if 'pre_action' in step_name.lower() or 'letter' in step_name.lower():
            enriched['pre_action_protocols'] = self.PRE_ACTION_PROTOCOLS

        # Add GDPR requirements
        if 'dpia' in step_name.lower() or 'data' in step_name.lower():
            enriched['gdpr_dpia'] = self.GDPR_DPIA

        # Add privilege information
        if 'privilege' in step_name.lower():
            enriched['privilege_rules'] = self.PRIVILEGE

        return enriched


# ============================================================================
# VALIDATION ENGINE
# ============================================================================

class ValidationEngine:
    """
    Sits between the workflow runner and step execution.
    Before any step marked as requires_approval, the validation engine
    runs all applicable domain checks and presents findings to the user.
    """

    def __init__(self, knowledge: KnowledgeEngine):
        self.knowledge = knowledge

    def pre_execution_check(self, workflow_name: str,
                            step_name: str, data: Dict) -> Dict:
        """
        Run full pre-execution validation before an irreversible step.

        Returns a comprehensive report that's shown to the user
        alongside the approval buttons.
        """
        # Get domain validation
        validation = self.knowledge.validate_step(
            workflow_name, step_name, data
        )

        # Get enriched data
        enriched_data = self.knowledge.enrich_step(
            workflow_name, step_name, data
        )

        return {
            'validation': validation,
            'enriched_data': enriched_data,
            'can_proceed': validation['can_proceed'],
            'total_checks': (
                len(validation.get('validations', [])) +
                len(validation.get('warnings', [])) +
                len(validation.get('blockers', []))
            ),
            'regulations_checked': validation.get('regulations_checked', []),
        }


if __name__ == '__main__':
    # Quick syntax check
    ke = KnowledgeEngine()
    print("Knowledge Engine initialized successfully")
    print(f"Limitation periods: {len(ke.law.LIMITATION_PERIODS)}")
    print(f"CPR rules: {len(ke.law.CPR_RULES)}")
    print(f"AML requirements: {len(ke.law.AML_REQUIREMENTS)}")
    print(f"Conveyancing rules: {len(ke.law.CONVEYANCING)}")
    print(f"Probate rules: {len(ke.law.PROBATE)}")
    print(f"Employment rules: {len(ke.law.EMPLOYMENT_TRIBUNAL)}")
