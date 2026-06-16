"""
Create realistic test documents for tagging validation.
These documents contain proper business content with names, dates, amounts,
departments, and categories to properly test SpaCy NER and taxonomy matching.
"""
import os

BASE = r"C:\Users\DELL\Downloads\TestDocuments\real_test_docs"
os.makedirs(BASE, exist_ok=True)

docs = {
    # ===== FINANCE / INVOICES =====
    "invoice_acme_consulting_2024.txt": """
INVOICE

Invoice Number: INV-2024-0847
Date: March 15, 2024
Due Date: April 15, 2024

From:
Acme Consulting Pvt. Ltd.
123 Brigade Road, Bangalore, Karnataka 560001
GSTIN: 29AABCU9603R1ZM

Bill To:
Rajesh Kumar, Chief Financial Officer
TechVision Systems Ltd.
Plot 42, HITEC City, Hyderabad, Telangana 500081

Description                          Qty    Unit Price     Amount
-------------------------------------------------------------------
Enterprise Architecture Review       1      INR 2,50,000   INR 2,50,000
Cloud Migration Assessment           1      INR 1,75,000   INR 1,75,000
Security Audit & Penetration Test    1      INR 3,00,000   INR 3,00,000
Database Optimization Services       40 hrs INR 5,000/hr   INR 2,00,000

Subtotal:                                                  INR 9,25,000
GST (18%):                                                 INR 1,66,500
Total Due:                                                 INR 10,91,500

Payment Terms: Net 30 days
Bank: HDFC Bank, Brigade Road Branch
Account: 50100248796315
IFSC: HDFC0000123

Authorized Signatory: Priya Sharma, Finance Manager
""",

    # ===== HR / OFFER LETTER =====
    "offer_letter_amit_verma.txt": """
CONFIDENTIAL

TechVision Systems Ltd.
Human Resources Department
Plot 42, HITEC City, Hyderabad, Telangana 500081

Date: January 10, 2024

To: Mr. Amit Verma
Address: 156, Koramangala 4th Block, Bangalore, Karnataka 560034

Subject: Offer of Employment - Senior Software Engineer

Dear Amit,

We are pleased to offer you the position of Senior Software Engineer in our
Engineering Department at TechVision Systems Ltd., reporting to Ms. Sneha Patel,
Vice President of Engineering.

Start Date: February 1, 2024

Compensation Package:
- Base Salary: INR 24,00,000 per annum (INR 2,00,000 per month)
- Performance Bonus: Up to 15% of annual base salary
- Stock Options: 5,000 shares vesting over 4 years
- Joining Bonus: INR 1,50,000 (one-time)

Benefits:
- Health Insurance: Coverage for self, spouse and 2 dependents
- Provident Fund: As per statutory requirements
- Leave: 24 days paid leave + 12 public holidays
- Professional Development: INR 50,000 annual learning allowance

Probation Period: 6 months
Notice Period: 90 days after probation

Please sign and return this letter by January 20, 2024 to confirm acceptance.

Warm regards,

Meera Krishnan
Head of Human Resources
TechVision Systems Ltd.
Email: meera.krishnan@techvision.com
Phone: +91-40-6789-0123
""",

    # ===== LEGAL / CONTRACT =====
    "service_agreement_2024.txt": """
SERVICE LEVEL AGREEMENT

Agreement No: SLA-2024-0392
Effective Date: April 1, 2024
Expiry Date: March 31, 2025

BETWEEN:

(1) TechVision Systems Ltd. ("Client")
    Represented by: Vikram Rao, Chief Operating Officer
    Registered Address: Plot 42, HITEC City, Hyderabad, Telangana 500081
    CIN: U72200TG2015PTC102456

AND

(2) CloudFirst Infrastructure Pvt. Ltd. ("Service Provider")
    Represented by: Ananya Desai, Managing Director
    Registered Address: Tower B, Prestige Tech Park, Bangalore, Karnataka 560066
    CIN: U72300KA2018PTC118234

SCOPE OF SERVICES:
1. Managed Cloud Infrastructure (AWS, Azure) - 24x7 monitoring
2. Database Administration (PostgreSQL, MongoDB, OpenSearch)
3. Security Operations Center (SOC) services
4. Disaster Recovery and Business Continuity
5. Network Management and Optimization

SERVICE LEVELS:
- Uptime Guarantee: 99.95% monthly
- Critical Incident Response: 15 minutes
- Major Incident Response: 1 hour
- Minor Incident Response: 4 hours
- Monthly Reporting and Review Meetings

FINANCIAL TERMS:
- Monthly Retainer: INR 15,00,000
- Annual Contract Value: INR 1,80,00,000
- Payment Terms: Net 15 days from invoice date
- Late Payment Penalty: 1.5% per month

TERMINATION:
- Either party may terminate with 90 days written notice
- Immediate termination for material breach
- Transition assistance period: 6 months

GOVERNING LAW:
This Agreement shall be governed by the laws of India.
Disputes to be resolved through arbitration in Hyderabad.

SIGNATURES:

For TechVision Systems Ltd.          For CloudFirst Infrastructure Pvt. Ltd.
Vikram Rao                            Ananya Desai
Chief Operating Officer               Managing Director
Date: March 25, 2024                  Date: March 25, 2024
""",

    # ===== TAX / COMPLIANCE =====
    "tax_computation_fy2024.txt": """
TAX COMPUTATION SHEET - FINANCIAL YEAR 2023-2024

Company: TechVision Systems Ltd.
PAN: AABCT1234F
Assessment Year: 2024-2025
Prepared by: Suresh Iyer, Tax Consultant, Deloitte India

INCOME COMPUTATION:
                                              Amount (INR)
Revenue from Operations                       45,00,00,000
Other Income (Interest, Dividends)             2,30,00,000
TOTAL INCOME                                  47,30,00,000

DEDUCTIONS:
Employee Costs                                18,50,00,000
Administrative Expenses                        5,20,00,000
Depreciation                                   3,80,00,000
Research & Development (Section 35)            2,00,00,000
CSR Expenditure                                  45,00,000
TOTAL DEDUCTIONS                              30,15,00,000

TAXABLE INCOME                                17,15,00,000

TAX LIABILITY:
Income Tax (25.17%)                            4,31,67,000
Surcharge (7%)                                   30,21,690
Health & Education Cess (4%)                     18,47,548
TOTAL TAX LIABILITY                            4,80,36,238

Advance Tax Paid:
Q1 (June 15, 2023):       1,20,00,000
Q2 (September 15, 2023):  1,20,00,000
Q3 (December 15, 2023):   1,20,00,000
Q4 (March 15, 2024):      1,00,00,000
TDS Credits:                 20,36,238
TOTAL ADVANCE TAX:         4,80,36,238

Balance Tax Due: NIL

Filing Deadline: October 31, 2024
Authorized by: Rajesh Kumar, CFO
Reviewed by: Suresh Iyer, Deloitte India
""",

    # ===== ENGINEERING / TECHNICAL REPORT =====
    "system_performance_report_q1.txt": """
QUARTERLY SYSTEM PERFORMANCE REPORT
Q1 2024 (January - March 2024)

Prepared by: Engineering Department
Author: Karthik Menon, Lead DevOps Engineer
Reviewed by: Sneha Patel, VP Engineering
Distribution: Internal - Engineering, Operations, Security

1. INFRASTRUCTURE OVERVIEW
   - Primary Region: AWS ap-south-1 (Mumbai)
   - DR Region: AWS ap-southeast-1 (Singapore)
   - Total EC2 Instances: 127
   - EKS Clusters: 3 (Production, Staging, Dev)
   - RDS Instances: 8 (PostgreSQL 15.4)
   - OpenSearch Domains: 2

2. PERFORMANCE METRICS
   Service              Uptime    Avg Latency    P99 Latency    Error Rate
   ---------------------------------------------------------------------------
   API Gateway          99.98%    45ms           180ms          0.02%
   Authentication       99.99%    32ms           95ms           0.01%
   Document Service     99.95%    120ms          450ms          0.05%
   Search Service       99.97%    85ms           320ms          0.03%
   Notification Service 99.96%    28ms           75ms           0.04%

3. INCIDENTS
   - Jan 15: Database connection pool exhaustion (P1, resolved in 25 min)
   - Feb 8: Certificate renewal failure on load balancer (P2, resolved in 45 min)
   - Mar 22: Redis cluster node failure, auto-failover (P3, no customer impact)

4. COST ANALYSIS
   Service          Monthly Cost    Change vs Q4 2023
   -------------------------------------------------------
   EC2 Compute      INR 8,50,000    +5%
   RDS Database     INR 4,20,000    -2%
   S3 Storage       INR 1,80,000    +12%
   Data Transfer    INR 2,10,000    +8%
   TOTAL            INR 16,60,000   +4.5%

5. SECURITY SUMMARY
   - 0 critical vulnerabilities found
   - 3 medium vulnerabilities patched
   - SOC2 Type II audit scheduled: May 2024
   - Last penetration test: February 2024 by Mandiant

Recommendations:
1. Migrate to Graviton3 instances for 25% cost savings
2. Implement auto-scaling for Document Service
3. Upgrade OpenSearch to version 2.11 for improved performance
""",

    # ===== COMPLIANCE / POLICY =====
    "data_protection_policy_v3.txt": """
DATA PROTECTION AND PRIVACY POLICY
Version 3.2 | Effective Date: January 1, 2024

TechVision Systems Ltd.
Compliance Department

Approved by:
- Anand Sharma, Chief Compliance Officer
- Dr. Kavitha Nair, Data Protection Officer
- Vikram Rao, Chief Operating Officer

1. PURPOSE
This policy establishes the framework for protecting personal data and ensuring
compliance with the Digital Personal Data Protection Act 2023 (DPDPA),
General Data Protection Regulation (GDPR), and ISO 27001:2022.

2. SCOPE
This policy applies to all employees, contractors, and third-party vendors of
TechVision Systems Ltd. who process personal data of Indian and EU residents.

3. DATA CLASSIFICATION
   Level 1 - Public: Press releases, marketing materials
   Level 2 - Internal: Employee handbooks, meeting notes
   Level 3 - Confidential: Customer data, financial records, HR records
   Level 4 - Restricted: PAN/Aadhaar data, health records, legal hold documents

4. CONSENT MANAGEMENT
   - Valid consent must be obtained before processing personal data
   - Consent must be freely given, specific, informed, and unambiguous
   - Data subjects have the right to withdraw consent at any time
   - Consent records must be maintained for audit purposes

5. DATA RETENTION
   Category                     Retention Period
   ------------------------------------------------
   Employee Records             7 years after exit
   Financial Transactions       8 years
   Customer Communications      3 years
   System Logs                  1 year
   CCTV Footage                 90 days

6. BREACH NOTIFICATION
   - Internal notification: Within 4 hours of discovery
   - CERT-In notification: Within 6 hours (as per DPDPA)
   - Data subject notification: Within 72 hours
   - Board notification: Within 24 hours for critical breaches

7. PENALTIES
   Non-compliance may result in:
   - Fines up to INR 250 crore under DPDPA
   - EUR 20 million or 4% of annual turnover under GDPR
   - Disciplinary action including termination

Contact: dpo@techvision.com | +91-40-6789-0200
Last Review Date: December 15, 2023
Next Review Date: June 15, 2024
""",

    # ===== PURCHASE ORDER =====
    "purchase_order_laptops_2024.txt": """
PURCHASE ORDER

PO Number: PO-2024-1156
Date: February 20, 2024
Department: IT Procurement
Requested by: Sanjay Gupta, IT Manager

Vendor: Dell Technologies India Pvt. Ltd.
Contact: Neha Chopra, Enterprise Account Manager
Address: DLF Cyber City, Gurgaon, Haryana 122002

Ship To: TechVision Systems Ltd., HITEC City, Hyderabad

Item    Description                          Qty   Unit Price    Total
------------------------------------------------------------------------
1       Dell Latitude 7440 (i7, 16GB, 512GB)  25   INR 95,000   INR 23,75,000
2       Dell UltraSharp 27" Monitor U2723QE   25   INR 42,000   INR 10,50,000
3       Dell Thunderbolt Dock WD22TB4         25   INR 18,500   INR 4,62,500
4       Dell Pro Wireless Keyboard & Mouse     25   INR 4,500    INR 1,12,500

Subtotal:                                                       INR 40,00,000
GST (18%):                                                      INR 7,20,000
Grand Total:                                                    INR 47,20,000

Payment Terms: Net 30 days
Delivery Date: March 10, 2024
Warranty: 3 years on-site

Approved by:
Sanjay Gupta, IT Manager
Rajesh Kumar, CFO (for amounts > INR 10,00,000)

Vendor Acknowledgment:
Neha Chopra, Enterprise Account Manager
Date: February 21, 2024
""",

    # ===== MEETING MINUTES =====
    "board_meeting_minutes_jan2024.txt": """
BOARD OF DIRECTORS MEETING MINUTES

Company: TechVision Systems Ltd.
Date: January 28, 2024
Time: 10:00 AM - 1:30 PM IST
Location: Board Room, 12th Floor, HITEC City, Hyderabad

PRESENT:
1. Dr. Arun Nair - Chairman
2. Vikram Rao - Chief Operating Officer & Director
3. Rajesh Kumar - Chief Financial Officer & Director
4. Dr. Kavitha Nair - Independent Director
5. Sunil Mehta - Independent Director (via video conference)
6. Ananya Desai - Nominee Director (CloudFirst)

IN ATTENDANCE:
- Meera Krishnan, Company Secretary
- Sneha Patel, VP Engineering (for Agenda Item 3)

AGENDA AND RESOLUTIONS:

1. CONFIRMATION OF PREVIOUS MINUTES
   The minutes of the Board Meeting held on October 15, 2023 were confirmed
   and signed by the Chairman.

2. FINANCIAL RESULTS - Q3 FY2024
   Mr. Rajesh Kumar presented Q3 results:
   - Revenue: INR 12.5 crore (up 18% YoY)
   - EBITDA: INR 3.1 crore (EBITDA margin 24.8%)
   - Net Profit: INR 2.2 crore
   - Cash reserves: INR 15.8 crore
   - Employee count: 450 (up from 380 last year)

   RESOLVED: The Board approved the unaudited Q3 financial statements.

3. TECHNOLOGY ROADMAP 2024
   Ms. Sneha Patel presented the 2024 technology roadmap:
   - AI/ML integration in document processing (Budget: INR 2.5 crore)
   - Migration to microservices architecture (Timeline: Q2-Q3)
   - ISO 27001 certification renewal
   - Customer-facing API platform launch (Q4)

   RESOLVED: The Board approved the technology investment of INR 2.5 crore.

4. EMPLOYEE STOCK OPTION PLAN (ESOP)
   RESOLVED: The Board approved the grant of 50,000 stock options to eligible
   employees under the TechVision ESOP 2020 scheme at an exercise price of
   INR 150 per share.

5. AUDIT COMMITTEE REPORT
   Dr. Kavitha Nair, Chair of the Audit Committee, reported:
   - Internal audit findings: 3 observations, all addressed
   - Statutory audit (Deloitte): No qualifications expected
   - Related party transactions: All at arm's length

6. NEXT MEETING: April 25, 2024

Meeting adjourned at 1:30 PM.

Meera Krishnan
Company Secretary
""",

    # ===== SECURITY / INCIDENT REPORT =====
    "security_incident_report_feb2024.txt": """
SECURITY INCIDENT REPORT

Incident ID: SEC-2024-0023
Severity: P2 - Major
Classification: CONFIDENTIAL

Date of Incident: February 14, 2024
Time of Detection: 03:45 AM IST
Time of Resolution: 06:30 AM IST
Total Downtime: 0 minutes (no service impact)

Reported by: Arjun Reddy, Security Operations Center
Incident Commander: Prashant Joshi, CISO

INCIDENT SUMMARY:
Unauthorized access attempt detected on the production API gateway from
IP addresses originating in Eastern Europe (77.88.xx.xx range). The SOC team
identified a credential stuffing attack targeting the /api/v2/auth endpoint
with approximately 15,000 login attempts over 45 minutes.

TIMELINE:
03:45 - Anomaly detection alert triggered (rate limiting threshold)
03:48 - SOC analyst Arjun Reddy acknowledged and began investigation
04:00 - WAF rules updated to block offending IP ranges
04:15 - Confirmed no successful authentication from attacking IPs
04:30 - Forensic log collection initiated
05:00 - Contacted ISP for upstream blocking
06:30 - Incident closed, all attacking IPs blocked

IMPACT ASSESSMENT:
- No data breach confirmed
- No customer accounts compromised
- Zero successful logins from attacking source
- WAF blocked 14,847 requests

ROOT CAUSE:
Credential stuffing using credentials from a third-party data breach
(not TechVision's data). Attackers used a botnet with 127 unique IP addresses.

REMEDIATION:
1. Implemented progressive rate limiting (5 attempts per minute per IP)
2. Enabled CAPTCHA after 3 failed login attempts
3. Added geographic restrictions for admin endpoints
4. Scheduled mandatory password reset for all admin accounts

Cost of Incident: INR 50,000 (staff overtime + forensic analysis tools)

Approved by:
Prashant Joshi, CISO
Vikram Rao, COO
""",

    # ===== IDENTITY DOCUMENT =====
    "employee_id_verification.txt": """
EMPLOYEE IDENTITY VERIFICATION FORM

Company: TechVision Systems Ltd.
Department: Human Resources
Form Reference: HR/ID/2024/0456

Employee Details:
Full Name: Deepa Venkatesh
Employee ID: TV-2024-0189
Date of Birth: August 12, 1992
Gender: Female
Nationality: Indian

Contact Information:
Mobile: +91-9876543210
Email: deepa.venkatesh@techvision.com
Address: Flat 302, Prestige Lakeside Habitat, Whitefield, Bangalore 560066

Identity Documents Verified:
1. Aadhaar Card: XXXX-XXXX-4567 (verified via DigiLocker)
2. PAN Card: BXEPV1234K
3. Passport: T1234567 (valid until December 2029)
4. Driving License: KA-04-2018-0012345

Emergency Contact:
Name: Ravi Venkatesh (Spouse)
Phone: +91-9876543211
Relationship: Husband

Verification Completed by: Meera Krishnan, HR Head
Date: February 5, 2024

Background Verification Status: Completed - No discrepancies found
Agency: AuthBridge Research Services Pvt. Ltd.
Report Reference: AB/BGV/2024/8901
""",
}

# Write all documents
for filename, content in docs.items():
    filepath = os.path.join(BASE, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"Created: {filepath} ({len(content)} chars)")

print(f"\nTotal: {len(docs)} realistic test documents created in {BASE}")
print("These cover: Invoice, Offer Letter, Contract, Tax Computation,")
print("Performance Report, Data Protection Policy, Purchase Order,")
print("Board Meeting Minutes, Security Incident Report, Employee ID Verification")
