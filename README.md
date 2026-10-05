# 🎫 IT Helpdesk Ticketing System

A full-stack **IT Helpdesk Ticketing System** built with **Flask (Python)**, featuring role-based access control, JWT authentication, email notifications, file attachments, and PDF/Excel report generation.
---
## 🎬 Demo

> _A walkthrough of the system — login, ticket creation, assignment, and admin dashboard.
> 
## ✨ Features

https://github.com/user-attachments/assets/450bec05-c188-4796-be1f-b3be1e0cc192

### 🔐 Authentication & Security

- JWT-based authentication with access & refresh tokens
- bcrypt password hashing
- TOTP two-factor authentication (via `pyotp`)
- OTP-based email login
- Password reset via secure email link
- CSRF protection on all web forms
- 
### 🎫 Ticket Management

- Create tickets with **title, description, category, priority, tags, due date**
- Auto-generated ticket numbers (e.g. `TKT-202610-4821`)
- Status lifecycle: `Open → In Progress → Resolved → Closed`
- Priority levels: `Low | Medium | High | Critical`
- Categories: `Hardware, Software, Network, Access, Email, General, Change Request, Other`
- Role-based ticket visibility (users see own, engineers see assigned, admins see all)
- Full activity log per ticket
- 
### 💬 Comments & Attachments

- Threaded comments with **internal-only** notes for engineers/admins
- File attachments with upload validation (size & type)
- Secure file download with access control
- 
### 👥 User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full access — manage users, assign tickets, view all reports |
| **Engineer** | Manage assigned tickets, add internal comments |
| **User** | Create & track own tickets |

### 📊 Admin Dashboard & Reports

- Real-time dashboard with ticket metrics & analytics
- Export reports as **PDF** (ReportLab) and **Excel** (openpyxl)
- Filter by date range, status, category, and assignee
- 
### 🔔 Notifications

- In-app notification system for ticket updates, assignments, and comments
