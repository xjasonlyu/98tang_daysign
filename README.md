# 98tang Daysign Script

## How to use

1. Export cookies from Browser
2. Clone this repository
3. Add secrets in repo settings

## How to retrieve cURL command

1. Go to [`https://www.sehuatang.net/plugin.php?id=dd_sign&view=daysign`](https://www.sehuatang.net/plugin.php?id=dd_sign&view=daysign)
2. Press `F12` to open the developer console
3. Locate the `Network` tab
4. Right click the relevant request, and select `Copy as cURL`

## GitHub Actions Secrets

1. `CURL`: cURL command string (e.g. `curl -H 'xxx:xxx'`)
2. `CHAT_ID`(optional): @BotFather bot chat ID
3. `BOT_TOKEN`(optional): @BotFather bot token

## Telegram notification

[create a telegram bot](https://medium.com/@ManHay_Hong/how-to-create-a-telegram-bot-and-send-messages-with-python-4cf314d9fa3e)
