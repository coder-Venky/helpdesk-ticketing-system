import os
import click
from flask.cli import with_appcontext
from app import create_app
from app.extensions import db

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.cli.command('seed')
@with_appcontext
def seed_db():
    """Seed the database with demo data."""
    from app.models.user import User
    from app.models.ticket import Ticket
    from app.models.attachment import ActivityLog, Notification

    click.echo('Creating tables...')
    db.create_all()

    # Check if already seeded
    if User.query.filter_by(email='admin@helpdesk.com').first():
        click.echo('Database already seeded!')
        return

    click.echo('Creating demo users...')
    admin = User(name='Admin User', email='admin@helpdesk.com', role='admin',
                department='IT', phone='+1-555-0001')
    admin.set_password('Admin@123')

    eng1 = User(name='Alex Engineer', email='alex@helpdesk.com', role='engineer',
               department='IT Support', phone='+1-555-0002')
    eng1.set_password('Eng@12345')

    eng2 = User(name='Sara Tech', email='sara@helpdesk.com', role='engineer',
               department='Network', phone='+1-555-0003')
    eng2.set_password('Eng@12345')

    user1 = User(name='John Smith', email='john@company.com', role='user',
                department='Sales', phone='+1-555-0100')
    user1.set_password('User@1234')

    user2 = User(name='Mary Johnson', email='mary@company.com', role='user',
                department='HR', phone='+1-555-0101')
    user2.set_password('User@1234')

    user3 = User(name='Bob Wilson', email='bob@company.com', role='user',
                department='Finance', phone='+1-555-0102')
    user3.set_password('User@1234')

    db.session.add_all([admin, eng1, eng2, user1, user2, user3])
    db.session.flush()

    click.echo('Creating demo tickets...')
    import random
    from datetime import datetime, timedelta

    ticket_data = [
        ('Laptop screen flickering', 'My laptop screen keeps flickering. It started yesterday.', 'Hardware', 'high', 'in_progress', eng1.id),
        ('Cannot access VPN', 'Getting error when connecting to company VPN from home.', 'Network', 'critical', 'open', None),
        ('Outlook not syncing emails', 'My Outlook stopped receiving emails since this morning.', 'Email', 'medium', 'resolved', eng2.id),
        ('Need Adobe Acrobat license', 'Requesting Adobe Acrobat Pro license for my machine.', 'Software', 'low', 'open', None),
        ('Printer offline in Marketing dept', 'The shared printer on Floor 3 shows as offline.', 'Hardware', 'medium', 'in_progress', eng1.id),
        ('Password reset for SAP system', 'Locked out of SAP after too many failed attempts.', 'Access', 'high', 'resolved', eng2.id),
        ('Slow internet connection', 'Internet is very slow since last week. Affecting work.', 'Network', 'medium', 'open', None),
        ('New PC setup required', 'New employee joining Monday, needs workstation setup.', 'Hardware', 'medium', 'closed', eng1.id),
        ('Software installation request', 'Need AutoCAD installed for the Engineering team.', 'Software', 'low', 'open', None),
        ('Email not sending attachments', 'Cannot send emails with attachments over 5MB.', 'Email', 'medium', 'in_progress', eng2.id),
        ('Monitor resolution issue', 'External monitor shows wrong resolution after update.', 'Hardware', 'low', 'resolved', eng1.id),
        ('Microsoft Teams crashing', 'Teams crashes every 30 minutes during video calls.', 'Software', 'high', 'open', None),
    ]

    users = [user1, user2, user3]
    for i, (title, desc, cat, priority, status, assignee) in enumerate(ticket_data):
        created_days_ago = random.randint(0, 30)
        created_at = datetime.utcnow() - timedelta(days=created_days_ago)
        resolved_at = None
        if status in ('resolved', 'closed'):
            resolved_at = created_at + timedelta(hours=random.randint(2, 48))

        ticket = Ticket(
            ticket_number=Ticket.generate_ticket_number(),
            title=title,
            description=desc,
            category=cat,
            priority=priority,
            status=status,
            created_by_id=users[i % len(users)].id,
            assigned_to_id=assignee,
            created_at=created_at,
            resolved_at=resolved_at,
        )
        db.session.add(ticket)
        db.session.flush()

        log = ActivityLog(ticket_id=ticket.id, user_id=users[i % len(users)].id,
                         action='created', description=f'Ticket created by {users[i % len(users)].name}',
                         created_at=created_at)
        db.session.add(log)
        if assignee:
            log2 = ActivityLog(ticket_id=ticket.id, user_id=admin.id, action='assigned',
                              description='Ticket assigned by admin', created_at=created_at + timedelta(minutes=5))
            db.session.add(log2)

    db.session.commit()
    click.echo('[OK] Database seeded successfully!')
    click.echo('\n[Demo Accounts]')
    click.echo('  Admin:    admin@helpdesk.com / Admin@123')
    click.echo('  Engineer: alex@helpdesk.com / Eng@12345')
    click.echo('  Engineer: sara@helpdesk.com / Eng@12345')
    click.echo('  User:     john@company.com / User@1234')
    click.echo('  User:     mary@company.com / User@1234')


@app.cli.command('init-db')
@with_appcontext
def init_db():
    """Create all database tables."""
    db.create_all()
    click.echo('[OK] Database tables created.')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
