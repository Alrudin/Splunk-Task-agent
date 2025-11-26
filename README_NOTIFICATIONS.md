# Notification System Documentation

## Overview

The Splunk TA Generator notification system keeps users informed about their request lifecycle events through email and webhook notifications. The system supports customizable, per-user preferences and provides both email (SMTP) and webhook channels for maximum flexibility.

### Supported Event Types

- **APPROVED** - Request approved by an approver
- **REJECTED** - Request rejected with reason
- **COMPLETED** - TA generation and validation completed successfully
- **FAILED** - TA validation failed
- **TEST** - Test notification for verifying settings

## Architecture

The notification system follows an asynchronous, event-driven architecture:

```
Request Lifecycle Event
        ↓
    Celery Task
(send_notification_task)
        ↓
  NotificationService
    ↓         ↓
  Email    Webhook
(SMTP)    (HTTP POST)
```

### Key Components

1. **NotificationService** (`backend/services/notification_service.py`)
   - Core service handling notification logic
   - Template rendering with Jinja2
   - Multi-channel delivery (email/webhook)
   - User preference checking

2. **Celery Task** (`backend/tasks/send_notification_task.py`)
   - Asynchronous notification processing
   - Retry logic with exponential backoff
   - Isolated failure handling

3. **Email Templates** (`backend/templates/`)
   - HTML and plain text variants
   - Event-specific templates
   - Responsive, mobile-friendly design

4. **API Endpoints** (`backend/api/users.py`)
   - GET/PUT `/api/v1/users/me/notification-preferences`
   - POST `/api/v1/users/me/test-notification`

## Configuration

### Environment Variables

Configure notifications via environment variables in `.env`:

```bash
# Global Settings
NOTIFICATION_ENABLED=true              # Master toggle for all notifications
NOTIFICATION_FROM_NAME="Splunk TA Generator"

# SMTP Configuration
SMTP_ENABLED=true                      # Enable email notifications
SMTP_HOST=smtp.gmail.com              # SMTP server hostname
SMTP_PORT=587                          # 587 (TLS), 465 (SSL), 25 (plain)
SMTP_USER=notifications@example.com    # SMTP username
SMTP_PASSWORD=app-specific-password    # SMTP password
SMTP_FROM=noreply@example.com         # From email address
SMTP_USE_TLS=true                      # Use TLS encryption

# Webhook Configuration
WEBHOOK_TIMEOUT=10                     # HTTP timeout in seconds
WEBHOOK_RETRY_ATTEMPTS=3              # Number of retry attempts
```

### SMTP Provider Examples

#### Gmail
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
# Use App Password, not regular password
```

#### Office 365
```bash
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USE_TLS=true
```

#### SendGrid
```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
```

## Email Templates

Templates are located in `backend/templates/` and use Jinja2 syntax.

### Template Structure

```
backend/templates/
├── email_base.html          # Base template with header/footer
├── request_approved.html/txt # Approval notification
├── request_rejected.html/txt # Rejection notification
├── request_completed.html/txt # Successful completion
├── request_failed.html/txt    # Validation failure
└── request_test.html/txt      # Test notification
```

### Available Variables

All templates have access to:
- `{{ user_name }}` - User's display name
- `{{ user_email }}` - User's email address
- `{{ request_id }}` - Request UUID
- `{{ source_system }}` - Log source system name
- `{{ frontend_url }}` - Frontend application URL
- `{{ app_name }}` - Application name
- `{{ app_version }}` - Application version

Event-specific variables:
- Approval: `{{ approver_name }}`, `{{ approval_comment }}`
- Rejection: `{{ rejection_reason }}`, `{{ approver_name }}`
- Completion: `{{ validation_summary }}`, `{{ ta_download_url }}`
- Failure: `{{ error_message }}`, `{{ debug_bundle_url }}`

### Customizing Templates

1. Edit HTML templates for rich email clients
2. Edit TXT templates for plain text fallback
3. Test changes locally (see Testing section)
4. Templates hot-reload without restart

## Webhook Integration

### Payload Format

Webhooks receive JSON payloads via HTTP POST:

```json
{
  "event_type": "COMPLETED",
  "timestamp": "2025-01-15T10:30:00Z",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "subject": "TA Generation Completed - apache_logs",
  "request_id": "987e6543-b21a-34c5-d678-123456789000",
  "source_system": "apache_logs",
  "validation_summary": {
    "status": "PASSED",
    "event_count": 1000,
    "field_coverage": 0.95
  },
  "ta_download_url": "https://app.example.com/requests/987.../ta"
}
```

### Security

Webhooks include HMAC-SHA256 signatures in headers:

```
X-Signature: sha256=<hex-signature>
X-Event-Type: COMPLETED
User-Agent: Splunk TA Generator/1.0.0
```

Verify signatures using the JWT secret as the signing key.

### Integration Examples

#### Slack Incoming Webhook
```python
webhook_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX"
```

#### Microsoft Teams
```python
webhook_url = "https://outlook.office.com/webhook/..."
```

#### Custom Webhook Handler
```python
@app.post("/webhook")
async def handle_webhook(
    request: Request,
    x_signature: str = Header(None)
):
    # Verify signature
    body = await request.body()
    expected_sig = generate_hmac(body, secret_key)
    if x_signature != expected_sig:
        raise HTTPException(401)

    # Process notification
    data = await request.json()
    print(f"Event: {data['event_type']} for request {data['request_id']}")
```

## User Preferences API

### Get Current Preferences
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/users/me/notification-preferences
```

Response:
```json
{
  "email_notifications_enabled": true,
  "webhook_url": "https://hooks.slack.com/...",
  "notification_events": ["COMPLETED", "FAILED"]
}
```

### Update Preferences
```bash
curl -X PUT -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email_notifications_enabled": true,
    "webhook_url": "https://my-webhook.com/notify",
    "notification_events": ["COMPLETED", "FAILED", "APPROVED", "REJECTED"]
  }' \
  http://localhost:8000/api/v1/users/me/notification-preferences
```

### Send Test Notification
```bash
curl -X POST -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/users/me/test-notification
```

## Testing

### Local SMTP Testing with MailHog

1. Run MailHog in Docker:
```bash
docker run -p 1025:1025 -p 8025:8025 mailhog/mailhog
```

2. Configure `.env`:
```bash
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USE_TLS=false
```

3. View emails at http://localhost:8025

### Webhook Testing with RequestBin

1. Create a temporary webhook at https://requestbin.com
2. Update user preferences with the RequestBin URL
3. Trigger a test notification
4. View received payloads in RequestBin

### Manual Testing

```python
# Test notification directly
from backend.tasks.send_notification_task import send_notification_task

send_notification_task.apply_async(
    args=[
        "user-uuid-here",
        "TEST",
        None,
        {"message": "Manual test"}
    ],
    queue="notifications"
)
```

## Celery Workers

Notifications use a dedicated Celery queue for isolation:

```bash
# Start notification worker
celery -A backend.tasks.celery_app worker \
  --loglevel=info \
  --queues=notifications \
  --concurrency=2 \
  -n notification-worker@%h
```

## Troubleshooting

### Common Issues

#### Emails Not Sending

1. Check SMTP configuration:
```bash
SMTP_ENABLED=true  # Must be true
SMTP_HOST != smtp.example.com  # Must be real server
```

2. Verify credentials:
   - Gmail: Use App Password, not regular password
   - Enable "Less secure app access" if needed
   - Check firewall rules for port 587/465

3. Check Celery worker logs:
```bash
docker logs celery-worker | grep notification
```

#### Webhook Failures

1. Check webhook URL format:
   - Must start with http:// or https://
   - Must be accessible from server
   - Check firewall/proxy settings

2. Verify timeout settings:
   - Increase `WEBHOOK_TIMEOUT` if endpoints are slow
   - Check `WEBHOOK_RETRY_ATTEMPTS` for retry behavior

3. Test webhook manually:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"test": "data"}' \
  https://your-webhook-url
```

#### Audit Logs

Check notification history in audit logs:

```sql
SELECT * FROM audit_logs
WHERE action IN ('NOTIFICATION_SENT', 'NOTIFICATION_FAILED')
ORDER BY created_at DESC;
```

### Debug Mode

Enable debug logging:

```bash
LOG_LEVEL=DEBUG
```

Check logs for detailed notification processing:
```bash
grep -i notification /var/log/app.log
```

## Database Schema

User notification preferences are stored in the `users` table:

```sql
-- Added columns
email_notifications_enabled BOOLEAN DEFAULT true NOT NULL
webhook_url VARCHAR(2048)
notification_events JSON  -- Array of event types
```

Apply migration:
```bash
alembic upgrade head
```

## Security Considerations

1. **Credentials**: Store SMTP passwords as environment variables or K8s secrets
2. **Webhook URLs**: Validated for format and length (max 2048 chars)
3. **Rate Limiting**: Consider implementing rate limits for test notifications
4. **PII**: Minimize sensitive data in notifications
5. **Audit Trail**: All notifications logged for compliance

## Future Enhancements

- SMS notifications via Twilio
- In-app notifications with WebSockets
- Notification templates customizable per user
- Digest notifications (daily/weekly summaries)
- Priority levels (urgent/normal/low)
- Delivery status tracking and retry UI

## Support

For issues or questions:
1. Check this documentation
2. Review audit logs for notification history
3. Contact system administrators
4. Report bugs at: https://github.com/your-org/splunk-ta-generator/issues