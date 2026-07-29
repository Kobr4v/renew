# Auto Renew Tickhosting

Automatically renews TickHosting free game servers using Selenium + GitHub Actions, running every 4 hours.

## Features

- Auto-login to TickHosting (cookie-based, falls back to email/password)
- Auto-click the renew button
- Verifies renewal by checking expiration time
- Runs every 4 hours via GitHub Actions cron
- Optional Telegram push notifications
- Manual trigger support

## Setup

### 1. Register & Get Cookie

1. Register at [TickHosting](https://tickhosting.com/auth/login) with email/password
2. Open browser DevTools (F12)
3. Go to the Application tab
4. Refresh the page
5. Find the `pterodactyl_session` cookie value

### 2. GitHub Actions Secrets

Fork this repo, then go to Settings → Secrets and variables → Actions and add:

| Secret | Description |
|---|---|
| `EMAIL` | Your TickHosting login email |
| `PASSWORD` | Your TickHosting login password |
| `PTERODACTYL_SESSION` | The cookie value from step 1 |

Optional Telegram notifications — add both:

| Secret | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |

### 3. Verify

- The Action runs automatically every 4 hours via cron
- Check run status and logs in the Actions tab
- Trigger manually from the Actions tab at any time

## Notes

- Make sure your cookie, email, and password are valid
- Check Actions logs periodically to confirm the script is working
- Adjust the cron schedule in `.github/workflows/auto_renew.yml` if needed
