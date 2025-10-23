# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of our Telegram Training Bot seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### How to Report a Security Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of the following methods:

1. **Email**: Send details to [your-email@example.com]
2. **GitHub Security Advisory**: Use the [Security Advisory](https://github.com/joanseamrexgage-ui/telegram-training-bot/security/advisories/new) feature

### What to Include in Your Report

Please include the following information to help us better understand the nature and scope of the issue:

- **Type of issue** (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- **Full paths of source file(s)** related to the manifestation of the issue
- **The location of the affected source code** (tag/branch/commit or direct URL)
- **Any special configuration** required to reproduce the issue
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept or exploit code** (if possible)
- **Impact of the issue**, including how an attacker might exploit it

### Response Timeline

- **Initial Response**: Within 48 hours of receiving your report
- **Status Update**: Within 5 business days regarding our evaluation and next steps
- **Resolution Timeline**: Depends on the severity and complexity of the issue

### What to Expect

1. **Acknowledgment**: We'll confirm receipt of your vulnerability report
2. **Investigation**: We'll investigate and validate the issue
3. **Resolution**: We'll develop and test a fix
4. **Disclosure**: We'll coordinate with you on public disclosure
5. **Credit**: We'll publicly acknowledge your responsible disclosure (if you wish)

## Security Best Practices for Users

### Environment Variables

**Never commit sensitive information to the repository:**

- ✅ Use `.env` files for sensitive data (already in `.gitignore`)
- ✅ Rotate credentials regularly
- ✅ Use strong, unique passwords for admin panel
- ✅ Limit `ADMIN_IDS` to trusted users only

### Database Security

**For production deployments:**

- ✅ Use PostgreSQL instead of SQLite
- ✅ Enable SSL/TLS for database connections
- ✅ Implement regular automated backups
- ✅ Restrict database access to localhost or specific IPs
- ✅ Use strong database passwords

### Bot Token Security

**Protect your Telegram Bot Token:**

- ✅ Never share your `BOT_TOKEN` publicly
- ✅ Revoke and regenerate tokens if compromised
- ✅ Use environment variables, never hardcode
- ✅ Monitor bot activity for suspicious behavior

### Deployment Security

**When deploying to production:**

- ✅ Use HTTPS/TLS for all external connections
- ✅ Keep dependencies up to date (enable Dependabot)
- ✅ Run bot with non-root user in Docker
- ✅ Implement rate limiting (already included)
- ✅ Enable fail2ban or similar for SSH protection
- ✅ Use firewall rules to restrict access

### Monitoring & Logging

**Security monitoring recommendations:**

- ✅ Enable Sentry or similar for error tracking
- ✅ Monitor logs for suspicious activity
- ✅ Set up alerts for failed admin login attempts
- ✅ Regularly review user activity logs
- ✅ Implement log rotation to prevent disk space issues

## Known Security Considerations

### Admin Panel Access

The admin panel is protected by:
- Password authentication (SHA-256 hashing)
- Rate limiting (3 attempts, 5-minute lockout)
- Activity logging

**Recommendations:**
- Use a strong, unique password (20+ characters)
- Change the default password immediately
- Restrict admin access to specific Telegram IDs

### Database Injection

The bot uses SQLAlchemy ORM with parameterized queries, which protects against SQL injection attacks. However:

- Always validate user input before processing
- Use Pydantic models for data validation
- Never execute raw SQL from user input

### Rate Limiting

Built-in rate limiting protects against spam and DoS attacks:
- Message rate limit: 3 messages per second
- Callback rate limit: 5 callbacks per second

Adjust these limits in `.env` if needed for your use case.

## Dependency Security

### Automated Security Scanning

We use:
- **Dependabot**: Automated dependency updates
- **GitHub Security Advisories**: Vulnerability alerts
- **Safety**: Python dependency security scanner
- **Trivy**: Container vulnerability scanner

### Manual Security Audits

We recommend:
- Regular dependency audits: `pip-audit`
- Code security scanning: `bandit`
- Secret scanning: `detect-secrets`

## Security Checklist for Deployment

Before deploying to production, ensure:

- [ ] All environment variables are set correctly
- [ ] Default passwords have been changed
- [ ] Database is properly secured
- [ ] HTTPS/TLS is enabled
- [ ] Firewall rules are configured
- [ ] Logging and monitoring are set up
- [ ] Backup strategy is in place
- [ ] Dependencies are up to date
- [ ] Security scanning is passing
- [ ] Admin IDs are restricted

## Incident Response

If a security incident occurs:

1. **Immediate**: Revoke compromised credentials
2. **Isolate**: Take affected systems offline if necessary
3. **Investigate**: Determine scope and impact
4. **Remediate**: Apply fixes and patches
5. **Notify**: Inform affected users if required
6. **Review**: Conduct post-incident analysis

## Contact

For security-related questions or concerns:
- **Email**: [security@example.com]
- **GitHub Security**: [Security Advisories](https://github.com/joanseamrexgage-ui/telegram-training-bot/security/advisories)

## Attribution

We appreciate the security research community's efforts to responsibly disclose vulnerabilities. Contributors will be acknowledged in our security hall of fame (if they wish).

---

**Last Updated**: 2025-10-23
**Version**: 1.0.0
