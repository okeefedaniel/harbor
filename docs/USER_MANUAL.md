# Beacon User Manual

**State Grants Management Solution**
Version 1.0 | February 2026

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Public Portal](#3-public-portal)
4. [Applicant Guide](#4-applicant-guide)
5. [Reviewer Guide](#5-reviewer-guide)
6. [Program Officer Guide](#6-program-officer-guide)
7. [Fiscal Officer Guide](#7-fiscal-officer-guide)
8. [Agency Administrator Guide](#8-agency-administrator-guide)
9. [System Administrator Guide](#9-system-administrator-guide)
10. [Auditor Guide](#10-auditor-guide)
11. [Financial Management](#11-financial-management)
12. [Reporting](#12-reporting)
13. [Grant Closeout](#13-grant-closeout)
14. [Analytics & Dashboards](#14-analytics--dashboards)
15. [Notifications](#15-notifications)
16. [Language Settings](#16-language-settings)
17. [REST API Reference](#17-rest-api-reference)
18. [Appendix A: Application Status Reference](#appendix-a-application-status-reference)
19. [Appendix B: Award Status Reference](#appendix-b-award-status-reference)
20. [Appendix C: Compliance Checklist Items](#appendix-c-compliance-checklist-items)
21. [Appendix D: Keyboard & Navigation Tips](#appendix-d-keyboard--navigation-tips)

---

## 1. Introduction

Beacon is the state grants management system, built to streamline the entire grant lifecycle for state agencies, municipalities, nonprofits, and businesses. The system covers everything from discovering funding opportunities and submitting applications to managing awards, tracking finances, filing reports, and closing out completed grants.

### Key Capabilities

- **Grant opportunity discovery** -- browse and search available funding programs
- **Online application submission** -- create, edit, and submit grant applications with supporting documents
- **Peer review and scoring** -- assign reviewers and score applications using configurable rubrics
- **Award management** -- issue awards, manage amendments, and collect e-signatures via built-in signature flows or DocuSign
- **Financial tracking** -- manage budgets, process drawdown requests, and record transactions
- **Compliance reporting** -- submit progress and fiscal reports, generate SF-425 federal financial reports
- **Grant closeout** -- complete closeout checklists, document fund returns, and archive records
- **Analytics and visualization** -- statewide dashboards, interactive maps, and deadline calendars
- **Audit trail** -- immutable logging of all major actions for compliance and accountability

### User Roles

Beacon uses role-based access control with seven roles. Each role sees a tailored dashboard and has access to specific features:

| Role | Description |
|------|-------------|
| **Applicant** | External users (municipalities, nonprofits, businesses) who apply for and manage grants |
| **Reviewer** | Panel members who score and evaluate applications |
| **Program Officer** | Agency staff who create and manage grant programs |
| **Fiscal Officer** | Agency staff who manage budgets, drawdowns, and financial transactions |
| **Agency Administrator** | Agency leadership with full control over their agency's programs and staff |
| **System Administrator** | Beacon administrators with full access to all features across all agencies |
| **Auditor** | Compliance staff with read-only access to audit logs, reports, and financial records |

---

## 2. Getting Started

### 2.1 Registering an Account

If you are applying for a grant on behalf of an organization:

1. Navigate to the Beacon home page.
2. Click **Register to Apply**.
3. Fill in the registration form:
   - Username
   - Email address
   - First and last name
   - Phone number (optional)
   - Organization (select existing or leave blank to create one later)
   - Password (enter twice to confirm)
   - Accept the Terms of Service
4. Click **Register**.
5. You will be redirected to the login page. Sign in with your new credentials.

> **Note:** All new registrations are assigned the **Applicant** role. State agency staff are assigned roles by a System Administrator.

### 2.2 Logging In

Beacon supports two authentication methods:

- **Username and password** -- enter your credentials on the login page.
- **Microsoft SSO** -- click **Sign in with Microsoft** to authenticate via Microsoft Entra ID (Azure AD). This is the preferred method for state employees.

Multi-factor authentication (MFA) is supported for Microsoft SSO users.

### 2.3 Setting Up Your Organization Profile

Before submitting your first application, you must set up your organization profile:

1. Navigate to **Profile** (click your name in the top navigation bar).
2. If you don't have an organization linked, click **Create Organization**.
3. Fill in:
   - Organization name and type (municipality, nonprofit, business, etc.)
   - DUNS number, UEI number, and EIN
   - SAM.gov registration status and expiration date
   - Address, phone, and website
4. Click **Save**.

> **Tip:** Keep your SAM.gov registration current. Many grant programs require active SAM registration, which is checked during the compliance review.

### 2.4 Editing Your Profile

1. Click your name in the top navigation bar, then select **Profile**.
2. Update your first name, last name, email, title, or phone number.
3. Click **Save Changes**.

---

## 3. Public Portal

The public portal is accessible to everyone, including users who are not logged in.

### 3.1 Home Page

The home page provides an overview of the system:

- **Hero section** with links to browse opportunities or register
- **Stats bar** showing the number of active programs, total funding available, and participating agencies
- **Recent Opportunities** displaying the three most recently posted grant programs
- **How It Works** with a four-step guide: Register, Find Opportunities, Apply, and Track Progress

### 3.2 Browsing Opportunities

Click **View Funding Opportunities** from the home page (or use the navigation bar) to see all published grant programs.

**Filtering options:**
- **Agency** -- filter by the state agency offering the grant
- **Grant Type** -- competitive, non-competitive, formula, continuation, or other
- **Status** -- posted, accepting applications, under review, awards pending, or closed

**View modes:**
- **Card view** (default) -- shows each opportunity as a card with key details
- **List view** -- compact table format

Each opportunity card shows:
- Grant type badge
- Title and agency name
- Total funding available
- Application deadline (color-coded: red if 7 or fewer days remain, yellow if 30 or fewer)

If you are logged in, each card also shows whether you have already applied (and the status of your application).

### 3.3 Opportunity Details

Click on any opportunity to see its full details:

- Program description and eligibility criteria
- Funding details (total funding, minimum/maximum award amounts, match requirements)
- Timeline (posting date, application deadline, duration)
- Contact information for the program officer
- Downloadable documents (notice of funding availability, guidelines, budget templates, etc.)
- **Apply** button (if the program is accepting applications and you are logged in)

---

## 4. Applicant Guide

### 4.1 Your Dashboard

After logging in, the dashboard shows:

- **My Applications** -- count of your submitted applications
- **My Active Awards** -- count of awards currently in progress
- **Pending Actions** -- items requiring your attention (reports due, revision requests, etc.)
- A table of your recent applications with status and quick-action links
- A preview of available funding opportunities

### 4.2 Creating an Application

1. Browse the opportunities listing and click **View Details** on a program you're interested in.
2. On the opportunity detail page, click **Apply Now**.
3. If you haven't set up your organization profile yet, you'll be prompted to create one first.
4. Fill in the application form:
   - **Project title** -- a clear, descriptive name for your proposed project
   - **Project description** -- a detailed narrative of your project plan
   - **Requested amount** -- the dollar amount you are requesting
   - **Proposed start and end dates** -- the anticipated project timeline
   - **Match amount** (if applicable) -- the amount of matching funds your organization will provide
   - **Match description** (if applicable) -- how the match will be sourced
5. Click **Save as Draft** to save your progress without submitting.

### 4.3 Uploading Documents

From your application's detail page:

1. Click **Upload Document**.
2. Select the document type (narrative, budget, budget justification, letters of support, resumes, organizational chart, audit report, tax-exempt letter, or other).
3. Enter a title and optional description.
4. Select the file and click **Upload**.

You can upload multiple documents of different types.

### 4.4 Submitting an Application

When your application is complete:

1. Navigate to the application detail page.
2. Review all information and uploaded documents.
3. Click **Submit Application**.
4. Confirm the submission.

Once submitted, your application moves to **Submitted** status. You will receive a notification confirming receipt.

> **Important:** After submission, you cannot edit your application unless a program officer requests revisions.

### 4.5 Tracking Your Applications

Navigate to **My Applications** from the dashboard or navigation bar to see all your applications with their current status:

| Status | Meaning |
|--------|---------|
| Draft | Started but not yet submitted |
| Submitted | Received by the agency, awaiting review |
| Under Review | Being evaluated by agency staff or reviewers |
| Revision Requested | The agency has asked you to make changes (you can edit and resubmit) |
| Approved | Your application has been approved for funding |
| Denied | Your application was not selected |
| Withdrawn | You withdrew your application |

### 4.6 Responding to Revision Requests

If a program officer requests revisions:

1. You will receive a notification with the reviewer's comments.
2. Navigate to the application and click **Edit**.
3. Make the requested changes and upload any additional documents.
4. Click **Submit** to resubmit for review.

### 4.7 Withdrawing an Application

You may withdraw an application at any time before an award decision:

1. Navigate to the application detail page.
2. Click **Withdraw**.
3. Confirm the withdrawal.

### 4.8 Viewing Your Awards

Once your application is approved and an award is issued:

1. Navigate to **My Awards** from the dashboard.
2. Click on an award to view its details, including:
   - Award number, amount, and dates
   - Terms and conditions
   - Associated budgets and transactions
   - Required reports with due dates
   - E-signature status (if applicable)

### 4.9 Submitting Drawdown Requests

To request disbursement of awarded funds:

1. Navigate to the award detail page.
2. Click **Request Drawdown**.
3. Fill in:
   - Amount requested
   - Period start and end dates
   - Description of expenditures
4. Click **Submit**.

Your request will be reviewed by the agency's fiscal officer. You will be notified when it is approved, denied, or returned for revision.

### 4.10 Submitting Reports

Grant awards require periodic progress and fiscal reports:

1. Navigate to the award detail page and find the **Reports** section.
2. Click **Create Report**.
3. Select the report type and fill in the required information.
4. Attach any supporting documents.
5. Click **Submit** when the report is complete.

Reports move through the following workflow: Draft, Submitted, Under Review, and then Approved, Revision Requested, or Rejected.

---

## 5. Reviewer Guide

### 5.1 Reviewer Dashboard

After logging in, your dashboard shows:

- **Total Assigned** -- number of applications assigned to you
- **Completed** -- reviews you've finished
- **Pending** -- reviews still awaiting your evaluation
- A table of your assigned applications with status and due dates

### 5.2 Reviewing an Application

1. Click on a pending review assignment from your dashboard.
2. The review page shows the application details and the scoring rubric.
3. For each criterion in the rubric:
   - Enter your **score** (within the allowed range)
   - Add an optional **comment** explaining your assessment
4. When all criteria are scored, click **Submit Review**.

> **Important:** Once submitted, your review cannot be edited.

### 5.3 Conflict of Interest

If you have a conflict of interest with an assigned application:

1. Contact the program officer or agency administrator.
2. They can update your assignment status to **Recused**, which removes you from reviewing that application.

### 5.4 Viewing Review Summaries

After all assigned reviewers have completed their evaluations, a review summary is automatically generated. Program officers can view the aggregated scores, average scores, and recommendations.

---

## 6. Program Officer Guide

### 6.1 Creating a Grant Program

1. Navigate to **Grant Programs** from the navigation bar.
2. Click **Create Program**.
3. Fill in the program details:
   - **Program Information:** title, description, funding source, grant type, eligibility criteria
   - **Funding Details:** total funding, minimum and maximum award amounts, match requirements and percentage
   - **Timeline:** fiscal year, application deadline, posting date, duration in months, multi-year flag
   - **Contact Information:** name, email, and phone for the program contact
4. Click **Save** to create the program in Draft status.

### 6.2 Publishing a Program

To make a grant program visible to the public:

1. Navigate to the program's detail page.
2. Click **Publish**.
3. The program status changes to **Posted** and it becomes visible on the public opportunities listing.

You can unpublish a program at any time by clicking the publish toggle again.

### 6.3 Managing Applications

Navigate to **Applications** to view all applications for your agency's programs.

**Available actions:**
- **Filter** by program or status
- **Search** by title, applicant, or organization
- **Export CSV** to download application data
- Click on an application to view its full details

### 6.4 Reviewing and Changing Application Status

From an application's detail page:

1. Review the project details, uploaded documents, and compliance checklist.
2. To change the status, scroll to the **Status Change** section.
3. Select the new status and add a required comment explaining the decision.
4. Click **Update Status**.

**Allowed status transitions:**
- Submitted -> Under Review
- Under Review -> Approved, Denied, or Revision Requested

> **Note:** You cannot approve an application until all required compliance checklist items have been verified.

### 6.5 Managing the Compliance Checklist

When an application is submitted, a compliance checklist is automatically generated. To verify items:

1. Navigate to the application detail page.
2. In the **Compliance** section, click the toggle next to each item to mark it as verified.
3. Optionally add notes explaining the verification.

All required items must be verified before the application can be approved.

### 6.6 Adding Comments

From the application detail page:

1. Scroll to the **Comments** section.
2. Enter your comment.
3. Check **Internal** if the comment should only be visible to agency staff (not the applicant).
4. Click **Add Comment**.

### 6.7 Uploading Staff Documents

To upload internal due-diligence documents (verification reports, site visit notes, etc.):

1. Navigate to the application detail page.
2. In the **Staff Documents** section, click **Upload**.
3. Select the document type, enter a title and description, and upload the file.

Staff documents are never visible to applicants.

### 6.8 Assigning Reviewers

1. Navigate to the application detail page.
2. Click **Assign Reviewer**.
3. Select a reviewer and the scoring rubric to use.
4. Click **Assign**.

You can assign multiple reviewers to the same application.

### 6.9 Creating Awards

After approving an application:

1. Navigate to the approved application.
2. Click **Create Award**.
3. The award form is pre-populated from the application (title, amount, dates, match information).
4. An award number is automatically generated (format: ST-{Agency}-{FiscalYear}-{Sequence}).
5. Review and adjust the details as needed, including terms and conditions.
6. Click **Save**.

### 6.10 Requesting E-Signatures (DocuSign)

To send an award agreement for electronic signature via DocuSign:

1. Navigate to the award detail page.
2. Click **Request Signature**.
3. Enter the signer's name and email address.
4. Optionally add a CC email and notes.
5. Click **Send for Signature**.

The system creates a DocuSign envelope and tracks its status. Once signed, the signed document is automatically downloaded and the award status updates to **Executed**.

### 6.11 Signature Flows (Built-In)

Beacon includes a built-in document signing system as an alternative to DocuSign. Signature flows define a sequential series of signing steps, each assigned to a specific user or organizational role.

#### Overview

| Feature | DocuSign (6.10) | Built-In Flows (6.11) |
|---------|----------------|----------------------|
| External service | Yes (requires DocuSign account) | No (fully self-contained) |
| Signing methods | DocuSign's UI | Typed, uploaded image, or drawn |
| PDF field placement | Via DocuSign | Built-in PDF placement editor |
| Multi-step approval | Single signer | Sequential steps with roles |
| Standalone deployment | No | Yes (available as SignStreamer) |

#### Creating a Signature Flow

**Manual creation:**

1. Navigate to **Signature Flows** from the main navigation.
2. Click **Create Flow**.
3. Enter a name and description for the flow.
4. Optionally upload a PDF document template.
5. Click **Save**.

**Using the Template Builder wizard:**

1. Navigate to **Signature Flows** and click **Template Builder**.
2. **Step 1 — Flow Details**: Enter the flow name, description, and active status.
3. **Step 2 — Signing Steps**: Add one or more steps. For each step, specify:
   - **Step order** (sequence number)
   - **Assignment**: Choose a specific user or an organizational role (e.g., Director, Manager)
   - **Instructions** for the signer
4. **Step 3 — PDF Placement** *(optional)*: Upload a PDF and use the visual placement editor to position signature fields on the document pages.
5. **Step 4 — Review**: Confirm all settings and click **Save Flow**.

#### Adding Signing Steps

Each step in a flow represents one signer in the approval chain:

1. Open an existing flow and click **Add Step**.
2. Set the **step order** (steps execute sequentially, lowest number first).
3. Choose the assignment type:
   - **User**: Assign to a specific person.
   - **Role**: Assign to anyone holding that organizational role (e.g., "Director"). When a packet is initiated, the system resolves the role to available users.
4. Add optional **instructions** that the signer will see.
5. Click **Save**.

#### PDF Placement Editor

The placement editor lets you position signature fields visually on a PDF document:

1. Upload a PDF to the signature flow.
2. Open the **Placement Editor** from the flow detail page.
3. Click on the PDF page where you want to place a signature field.
4. Drag to resize the field as needed.
5. Assign the field to a specific signing step.
6. Save the placements.

Fields are rendered at the correct position when signers view the document.

#### Initiating a Signing Packet

A signing packet is a single instance of a signature flow applied to a specific document:

1. Navigate to **Packets** and click **New Packet**.
2. Select the signature flow to use.
3. Upload the document to be signed (if the flow doesn't already have a template).
4. Click **Initiate**.

The system creates the packet and notifies the first signer in the step sequence.

#### Signing a Document

When it is your turn to sign:

1. Open the signing packet from your notifications or the **Packets** list.
2. Review the document.
3. Choose your signature method:
   - **Type**: Enter your name to generate a signature.
   - **Upload**: Upload an image of your signature.
   - **Draw**: Draw your signature using a mouse or touchscreen.
4. Click **Submit Signature**.

The system records your signature and advances to the next step. Once all steps are complete, the packet status changes to **Completed**.

#### Managing Signature Roles

Roles allow you to assign signing steps by position rather than by individual user:

1. Navigate to **Roles** from the main navigation.
2. Click **Create Role**.
3. Enter:
   - **Key**: A machine-readable identifier (e.g., `director`, `legal`)
   - **Label**: A human-readable name (e.g., "Director", "Legal Counsel")
   - **Description** *(optional)*
4. Click **Save**.

Roles can be edited, deactivated (soft-disabled), or deleted. Deactivated roles remain visible in existing flows but are not available for new assignments.

---

## 7. Fiscal Officer Guide

### 7.1 Budget Management

#### Creating a Budget

1. Navigate to an award's detail page.
2. Click **Create Budget**.
3. Enter the fiscal year and total budget amount.
4. Click **Save**.

#### Adding Budget Line Items

1. Navigate to the budget detail page.
2. Click **Add Line Item**.
3. Select the budget category (personnel, fringe, travel, equipment, supplies, contractual, construction, indirect costs, or other).
4. Enter the amount and its breakdown between federal share, state share, and match share.
5. Add a description and any notes.
6. Click **Save**.

### 7.2 Processing Drawdown Requests

When a grantee submits a drawdown request:

1. Navigate to **Drawdowns** from the financial menu.
2. Click on a pending request to review its details.
3. Choose one of three actions:
   - **Approve** -- the request is approved for payment
   - **Deny** -- the request is denied (provide a reason)
   - **Return** -- the request is returned to the grantee for revision

The grantee is notified of the decision automatically.

### 7.3 Recording Transactions

To record a financial transaction against an award:

1. Navigate to the award's detail page.
2. Click **Record Transaction**.
3. Select the transaction type (obligation, drawdown, payment, refund, or adjustment).
4. Enter the amount, date, description, and reference numbers (including State ERP reference if applicable).
5. Click **Save**.

### 7.4 Budget vs. Actual Analysis

To compare budgeted amounts with actual spending:

1. Navigate to the award's detail page.
2. Click **Budget vs. Actual**.
3. The report shows a breakdown by budget category:
   - Budgeted amounts (federal, state, and match shares)
   - Actual spending
   - Remaining balance
   - Percentage used

### 7.5 Reviewing Fiscal Reports

1. Navigate to **Reports** from the navigation bar.
2. Filter by report type to find fiscal reports.
3. Click on a report to review its contents.
4. Choose to **Approve**, **Request Revision**, or **Reject**, providing comments as needed.

### 7.6 SF-425 Federal Financial Reporting

To generate and submit a federal financial report (Standard Form 425):

1. Navigate to the award's detail page.
2. Click **Generate SF-425**.
3. The system pre-populates financial data from drawdowns and transactions.
4. Review the figures and click **Submit**.
5. A grant manager must then approve the SF-425 before it is considered final.

---

## 8. Agency Administrator Guide

Agency administrators have all the capabilities of program officers and fiscal officers within their agency, plus additional administrative functions.

### 8.1 Managing Agency Staff

Work with a System Administrator to:
- Add new staff members to your agency
- Assign appropriate roles (program officer, fiscal officer, reviewer)
- Deactivate staff who have left the agency

### 8.2 Overseeing Programs and Applications

As an agency administrator, you can:
- View and manage all grant programs for your agency
- Review all applications across your agency's programs
- Approve or deny awards
- Monitor financial activity across all awards

### 8.3 Viewing Agency Analytics

The analytics dashboard (accessible from the navigation bar) provides agency-level metrics including:
- Number of active programs
- Total applications received
- Funding awarded and disbursed
- Approval rates

---

## 9. System Administrator Guide

### 9.1 User Management

1. Navigate to **Users** from the administration menu.
2. The user list shows all registered users with their roles and status.
3. Use the search bar to find specific users by name, username, or email.
4. Filter by role using the dropdown.
5. Click **Edit** next to a user to update their:
   - Role assignment
   - Agency assignment
   - State user flag
   - Active/inactive status

### 9.2 Statewide Analytics

The analytics dashboard provides comprehensive statewide metrics:

- **KPI Cards:** total programs, active awards, total funding, approval rate, overdue reports, pending drawdowns
- **Charts:**
  - Application status distribution (doughnut chart)
  - Funding by agency (bar chart)
  - Monthly award trends over the last 12 months (line chart)
  - Budget utilization for top 10 programs (grouped bar chart)
- **Agency breakdown** table with per-agency program, application, award, and funding counts
- **Recent activity** feeds showing the latest applications and awards

### 9.3 Map View

The interactive map displays grant distribution across state municipalities:

1. Navigate to **Map** from the navigation bar.
2. The choropleth map color-codes municipalities by total funding received.
3. Use the sidebar filters to narrow by agency or program.
4. Hover over a municipality to see award counts and total funding.

### 9.4 Django Admin

System administrators with staff privileges can access the Django admin interface at `/admin/` for direct database management. Use this for:
- Bulk data operations
- Troubleshooting data issues
- Managing agencies and funding sources
- Viewing raw audit logs

### 9.5 Audit Logs

Navigate to the audit log section to view a complete history of all system actions:

- User who performed the action
- Action type (create, update, delete, submit, approve, reject, status change, export)
- Entity affected (type and ID)
- Description and change details
- IP address and timestamp

Audit logs are immutable and cannot be edited or deleted.

---

## 10. Auditor Guide

### 10.1 Auditor Access

Auditors have read-only access across the system for compliance and oversight purposes:

- **Audit Logs** -- view the complete action history
- **Applications** -- review application details and compliance checklists
- **Awards** -- view award details, amendments, and financial summaries
- **Financial Records** -- review budgets, drawdowns, transactions, and budget vs. actual reports
- **Reports** -- view all submitted progress, fiscal, and SF-425 reports
- **Closeout Records** -- review closeout checklists and fund returns
- **Archived Records** -- access retained records per retention policy

### 10.2 Data Retention

The system enforces data retention policies:

| Policy | Duration | Use Case |
|--------|----------|----------|
| Standard | 7 years | Most grant records |
| Extended | 10 years | High-value or sensitive grants |
| Permanent | Indefinite | Records required for permanent retention |
| Federal | 3 years post-closeout | Federal grant compliance |

---

## 11. Financial Management

### 11.1 Budget Workflow

1. **Create budget** -- a fiscal officer or program officer creates a budget for an award, specifying the fiscal year and total amount.
2. **Add line items** -- individual budget categories are added with amounts broken down by federal, state, and match shares.
3. **Submit budget** -- the budget is submitted for approval.
4. **Approve budget** -- a fiscal officer or agency administrator approves the budget.

Budget categories include: personnel, fringe benefits, travel, equipment, supplies, contractual services, construction, indirect costs, and other.

### 11.2 Drawdown Workflow

1. **Grantee creates request** -- the grantee creates a drawdown request specifying the amount, period, and expenditure details. A request number is auto-generated (format: DR-{AwardNumber}-{Sequence}).
2. **Submit request** -- the grantee submits the request for review.
3. **Fiscal review** -- a fiscal officer reviews and takes one of three actions:
   - **Approve** -- funds are released
   - **Deny** -- request is rejected with a reason
   - **Return** -- request is sent back to the grantee for revision
4. **Payment** -- once approved, the transaction is recorded.

### 11.3 Transaction Types

| Type | Description |
|------|-------------|
| Obligation | Initial commitment of funds |
| Drawdown | Disbursement to grantee |
| Payment | Payment against an obligation |
| Refund | Return of funds |
| Adjustment | Correction or modification |

### 11.4 State ERP Integration

Awards can be mapped to State ERP account strings for integration with the state's financial system. The account string includes: fund, department, SID, program, account, and optional chartfield segments.

---

## 12. Reporting

### 12.1 Report Types

| Type | Description |
|------|-------------|
| Progress | Narrative report on project activities and milestones |
| Fiscal | Financial report on expenditures and budget status |
| Programmatic | Report on program outcomes and performance metrics |
| Final Progress | Comprehensive end-of-grant progress report |
| Final Fiscal | Comprehensive end-of-grant financial report |
| SF-425 | Federal Financial Report (Standard Form 425) |
| Custom | Agency-defined report format |

### 12.2 Report Submission Workflow

1. **Create report** -- from the award detail page, click **Create Report** and select the type.
2. **Fill in data** -- enter the reporting period, due date, and report content.
3. **Attach documents** -- upload any required supporting files.
4. **Submit** -- the report moves from Draft to Submitted status.
5. **Agency review** -- an agency staff member reviews and takes action:
   - **Approve** -- the report is accepted
   - **Request Revision** -- the report is returned with comments for correction
   - **Reject** -- the report is rejected

### 12.3 SF-425 Federal Financial Report

The SF-425 is a federally required financial report for awards with federal funding:

1. Navigate to the award and click **Generate SF-425**.
2. The system auto-populates key financial fields from transaction data:
   - Federal cash receipts
   - Federal expenditures
   - Federal unliquidated obligations
   - Recipient share expenditures
   - Remaining federal funds
3. Review the figures and submit.
4. A grant manager approves the final report.

### 12.4 Overdue Reports

Reports that are past their due date and still in Draft or Revision Requested status are flagged as overdue. These appear on:
- The deadline calendar
- The analytics dashboard (overdue reports count)
- Notification alerts

---

## 13. Grant Closeout

### 13.1 Initiating Closeout

When an award reaches its end date:

1. Navigate to **Closeout** from the navigation bar.
2. The closeout list shows awards that have passed their end date but haven't been closed out.
3. Click **Initiate Closeout** on the relevant award.
4. The system automatically creates a closeout checklist with six items:
   - Final Progress Report (required)
   - Final Fiscal Report (required)
   - Equipment Inventory (optional)
   - Audit Resolution (required)
   - Fund Return (required)
   - Record Retention (required)

### 13.2 Completing the Checklist

1. Navigate to the closeout detail page.
2. For each checklist item, click the toggle to mark it as complete.
3. Add notes as needed to document how each item was satisfied.

Progress indicators show how many items are completed and whether all required items have been addressed.

### 13.3 Recording Fund Returns

If the grantee has unspent funds to return:

1. Navigate to the closeout detail page.
2. Click **Record Fund Return**.
3. Enter the amount, reason for the return, and any reference information.
4. Click **Save**.

### 13.4 Uploading Closeout Documents

Upload final reports, audit documentation, and other closeout materials:

1. Click **Upload Document** from the closeout detail page.
2. Select the document type (final progress report, final fiscal report, audit report, inventory report, refund documentation, or other).
3. Upload the file and save.

### 13.5 Completing Closeout

Once all required checklist items are marked complete:

1. Click **Complete Closeout**.
2. The closeout status changes to **Completed**.
3. The award status automatically updates to **Completed**.

---

## 14. Analytics & Dashboards

### 14.1 Main Dashboard

Every user sees a role-appropriate dashboard upon login:

**Agency staff** see:
- Active awards count and total funding awarded
- Pending applications requiring attention
- Pending reviews awaiting completion
- Tables of recent applications and active awards
- Quick-action buttons for common tasks

**Applicants** see:
- Application and active award counts
- Pending actions (reports due, revision requests)
- Recent applications with status
- Available opportunities

### 14.2 Analytics Dashboard

Available to system administrators and agency administrators, the analytics dashboard provides:

- **Six KPI cards** with real-time metrics
- **Application status distribution** -- a doughnut chart showing the breakdown of all application statuses
- **Funding by agency** -- a horizontal bar chart comparing total funding across agencies
- **Monthly award trends** -- a line chart tracking awards issued over the past 12 months
- **Budget utilization** -- a grouped bar chart showing awarded vs. disbursed amounts for the top 10 programs

### 14.3 Deadline Calendar

The calendar view displays:

- **Overdue reports** highlighted in red
- **Upcoming grant application deadlines** with days remaining
- **Upcoming report due dates**
- **Awards expiring within 90 days**

The calendar is filtered based on your role: agency staff see items for their agency, and applicants see items for their own awards.

### 14.4 Map View

The interactive map shows grant distribution across state municipalities:

- Color-coded choropleth based on total funding
- Filterable by agency and program
- Hover to see municipality details (award count and total funding)
- Zoom and pan controls for navigation

---

## 15. Notifications

Beacon sends in-app notifications (and optionally email notifications) for key events:

| Event | Notified User(s) |
|-------|-------------------|
| Application submitted | Agency staff (program officers, agency admins) |
| Application status changed | Applicant |
| Award created | Award recipient |
| Amendment requested | Relevant agency staff |
| E-signature requested | Signer |
| E-signature completed | Agency staff |
| Drawdown status changed | Drawdown submitter |
| Report reviewed | Report submitter |
| Closeout initiated | Relevant users |

### Viewing Notifications

1. Click the notification bell icon in the navigation bar.
2. Unread notifications are highlighted.
3. Click a notification to mark it as read.
4. Click the link in the notification to navigate to the relevant item.

---

## 16. Language Settings

Beacon supports English and Spanish. To change your language:

1. Look for the language selector in the navigation bar or footer.
2. Select your preferred language.
3. The interface will update immediately.

Language preferences are stored in your session and persist until you change them or log out.

---

## 17. REST API Reference

Beacon provides a REST API for programmatic access. All endpoints require authentication.

**Base URL:** `/api/`

| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/grant-programs/` | GET, POST, PUT, DELETE | Manage grant programs |
| `/api/applications/` | GET, POST, PUT | Manage applications |
| `/api/awards/` | GET, POST, PUT | Manage awards |
| `/api/drawdown-requests/` | GET, POST | Manage drawdown requests |
| `/api/transactions/` | GET, POST | View and record transactions |
| `/api/budgets/` | GET, POST, PUT | Manage budgets |
| `/api/reports/` | GET, POST, PUT | Manage reports |
| `/api/organizations/` | GET, POST, PUT | Manage organizations |
| `/api/notifications/` | GET, PATCH | View and manage notifications |
| `/api/audit-logs/` | GET | View audit logs (admin/auditor only) |

**Filtering:** Use query parameters to filter results (e.g., `?status=submitted&agency=DCD`).

**Search:** Use the `search` parameter for full-text search (e.g., `?search=workforce`).

**Ordering:** Use the `ordering` parameter to sort results (e.g., `?ordering=-created_at`).

**Custom Actions:**
- `PATCH /api/notifications/{id}/mark-read/` -- mark a single notification as read
- `PATCH /api/notifications/mark-all-read/` -- mark all notifications as read

---

## Appendix A: Application Status Reference

| Status | Description | Who Can Trigger | Next Possible Statuses |
|--------|-------------|-----------------|----------------------|
| Draft | Application started, not yet submitted | Applicant (automatic) | Submitted, Withdrawn |
| Submitted | Application submitted for review | Applicant | Under Review, Withdrawn |
| Under Review | Being evaluated by agency staff | Program Officer | Approved, Denied, Revision Requested |
| Revision Requested | Applicant asked to make changes | Program Officer | Submitted (after edits), Withdrawn |
| Approved | Selected for funding | Program Officer | (Award created) |
| Denied | Not selected | Program Officer | (Final) |
| Withdrawn | Applicant withdrew | Applicant or Staff | (Final) |

---

## Appendix B: Award Status Reference

| Status | Description |
|--------|-------------|
| Draft | Award created, not yet finalized |
| Pending Approval | Awaiting administrative approval |
| Approved | Approved but not yet signed |
| Executed | Agreement signed (via DocuSign or manual) |
| Active | Award is in progress |
| On Hold | Temporarily suspended |
| Completed | All work finished, grant closed out |
| Terminated | Ended early |
| Cancelled | Cancelled before execution |

---

## Appendix C: Compliance Checklist Items

When an application is submitted, the following compliance items are automatically generated:

| Item | Required | Description |
|------|----------|-------------|
| SAM Registration Active | Yes | Verify the organization's SAM.gov registration is current |
| Tax-Exempt Status Verified | Yes | Verify tax-exempt status documentation |
| Audit Clearance | Yes | Confirm no outstanding audit findings |
| Debarment/Suspension Check | Yes | Verify the organization is not debarred or suspended |
| Budget Review Complete | Yes | Complete review of the proposed budget |
| Narrative Review Complete | Yes | Complete review of the project narrative |
| Insurance Verification | No | Verify required insurance coverage |
| Eligibility Confirmed | Yes | Confirm the applicant meets all eligibility criteria |
| Match Funds Verified | Yes* | Verify matching fund commitments (*only if match is required) |
| Conflict of Interest Check | Yes | Confirm no conflicts of interest exist |

---

## Appendix D: Keyboard & Navigation Tips

- Use the **navigation bar** at the top of every page to access major sections.
- **Breadcrumbs** are displayed below the navigation bar to show your current location.
- Use browser **back/forward** buttons to navigate between pages.
- **Tables** support sorting by clicking column headers.
- **CSV Export** buttons are available on list views for downloading data.
- Use **Ctrl+F** (or **Cmd+F** on Mac) to search within any page.

---

*This manual covers Beacon version 1.0, deployed February 2026. For technical support, contact the system administrator.*
