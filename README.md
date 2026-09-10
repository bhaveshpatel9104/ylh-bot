# YouLikeHits YouTube Likes Bot

Yeh bot automatically YouLikeHits pe YouTube videos like karke points earn karta hai.

---

## Setup (Ek baar karna hai)

### Step 1: Dependencies install karo
```
pip install -r requirements.txt
playwright install chromium
```

### Step 2: Credentials bharo
`.env` file kholke apni details daalo:
```
YLH_USERNAME=bhavesh647383
YLH_PASSWORD=apna_password_yahan
GOOGLE_EMAIL=apni_gmail@gmail.com
GOOGLE_PASSWORD=apna_gmail_password
```

### Step 3: Test run karo (browser dikhega)
.env mein `HEADLESS=false` rakho, phir:
```
python bot.py
```

### Step 4: Background mein chalao (browser nahi dikhega)
.env mein `HEADLESS=true` karo, phir `run_bot.bat` double-click karo.

---

## Files

| File | Kaam |
|------|------|
| `bot.py` | Main automation script |
| `config.py` | Settings loader |
| `.env` | Aapke credentials (private rakho) |
| `run_bot.bat` | Double-click se start |
| `logs/activity.log` | Bot ki activity log |

---

## Important Notes

- Pehli baar `HEADLESS=false` rakho — dekho sab theek chal raha hai
- Google 2FA enable hai toh pehli baar manually login karna padega
- `.env` file kisi ko share mat karo
- Bot band karna ho toh: window close karo ya `Ctrl+C`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Login fail | Password check karo .env mein |
| YouTube like nahi ho raha | Headless=false karke dekho |
| Points nahi aa rahe | YouLikeHits manually check karo |
| CAPTCHA aa gaya | Headless=false karke manually solve karo |
