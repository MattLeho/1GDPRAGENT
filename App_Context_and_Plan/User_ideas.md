USER IDEAS & PROJECT REQUIREMENTS
Project: Local GDPR Request Automation App
1. Core Vision & Deployment Strategy
The user wants a privacy-focused, automated system to exercise GDPR/CCPA rights (Access & Deletion). The primary constraint is that it must run locally, mimicking a native desktop application experience.
"I would really prefer to host this locally like just an app which I can open on my pc... I know I can run N8N locally."
"Or on Linux cause I might switch to linux soon."
Architecture Goal: A self-contained ecosystem (Frontend + Database + N8N) running on the user's machine (Windows or Linux).
The "Agent" Approach: The user wants to use AI agents (specifically N8N combined with LLMs) to handle the logic.
"I want to make the ai agents with N8N and then connect them with a webhook... Can also use huggingface agents as i might want to finetune a model to GDPR legistlation."
2. The Core "Bot" Logic
The user defined a specific workflow for the automation backend (N8N):
User Input: "I want to request [Company Name]."
Analysis: Bot fetches & analyzes the privacy policy.
"IDENTIFIES LINKS / DATA COLLECTED / used."
Summary: Creates a short summary for the user to review.
Drafting: Bot uses the company's specific GDPR policy to write a tailored request (Article 15 or 17).
User Feedback: Waits for user confirmation.
Execution: Clicks the button/sends email. Personal info is auto-appended.
Response Handling:
"Worker bot fires process with responses, auto replies."
"Can select an email linked to account that has been pre-populated."
3. Frontend & UI Requirements
A. Navigation
"In the homepage there's a navigation bar with home, requests, new, and settings at the top."
B. Home Page / Dashboard
The user wants a high-level overview of their data footprint.
Stats: "Amount of requests I've done that year and that month."
Data Visualization:
"A pie chart of the total amount of data received in gigabytes and where all of that data is coming from."
Action Items (Task List): "Companies that I've started but not replied to an email... and not confirmed the email."
Schedule: "A box showing the scheduled GDPR requests."
Review: A section at the bottom showing data or emails that need manual review.
C. New Request Page ("The Wizard")
A specific form flow to initiate agents:
Identity Panel: "A box to pick the identity or to create a new identity."
Company Search & Analysis:
"A box to create a company, search a company. And a button next to this to run the analysis... look up their privacy policy... find their email, how to send a GDPR request."
Scope Definition: "What the user wants... specific stuff or if they just want all of their data."
Dates: "If they want the data within a certain date."
Context Injection:
"Can add context, like files that the AI will analyze as part of its request. So like emails, receipts, all that kind of stuff."
Details: "Add notes... Check a box for data deletion."
Account ID Injection: "ID panel to add all of the account details... emails, usernames, name associated with the account."
D. View Requests Dashboard
A detailed management grid for ongoing processes.
Filtering: "Search bar, filter bar, sort bar, filter by tag, by company, by purchase, services."
The Cards:
"Cards that show the company, so a logo, the company name, the state, maybe a timeline if it's scheduled."
The "Zoom" Feature:
"A zoom icon in the corner where you can view the details... messages between the agent... actions the agent has taken, any previous data, any notes."
4. Specific Data Features
Encryption: The user implies a need for security regarding the "ID Panel" and stored data.
Data Export/Import: The ability to "View Data" returned by companies and analyze response rates.
Scheduling: The ability to set repeated requests (e.g., "Every 6 months").
"Scheduling after that, we'll only want the data from the last time they sent us data."
5. Technical Constraints Summary
Backend: N8N (Local).
Frontend: React/Next.js (implied by "App" nature and previous discussions).
Connectivity: Webhooks connecting the Frontend to N8N.
Future Proofing: Support for HuggingFace agents or fine-tuned local models for GDPR expertise.