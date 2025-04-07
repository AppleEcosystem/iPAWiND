
# Telegram iOS app signer bot.

iPAWiND is an iOS app signer bot for Telegram. It allows users to sign and install iOS applications directly through Telegram, making the sideloading process more accessible.

Telegram Bot: [@ipawind_bot](https://t.me/ipawind_bot)

## Features

- Sign iOS apps (.ipa files) directly through Telegram
- Automatic provisioning profile management
- Support for various signing certificates
- Easy installation and configuration
- Docker support for simple deployment

## Prerequisites

- Linux server (Ubuntu/Debian recommended)
- Python 3.8+
- Node.js and npm
- Docker and Docker Compose (optional, for containerized setup)
- Telegram Bot API token

## Installation

### Step 1: Update and Install Essential Packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y zip unzip build-essential checkinstall zlib1g-dev libssl-dev git make g++ pkg-config  libminizip-dev  zlib1g-dev zip unzip nodejs
```

```bash
cd iPAWIND
```

```bash
npm install node-forge ocsp && nodejs tools/checker/resources.js
```

```bash
pip3 install -r requirements.txt
```


## Step 3: Install Docker
- Follow the Docker installation guide: https://docs.docker.com/engine/install/ubuntu/

```bash
docker compose up -d
```

## Step 4: setup cloudfalre worker shortner
- https://github.com/AppleEcosystem/ShortFlare



## Step 5: Configure Cloudflare R2 and Bot Settings

- Create an R2 bucket in your Cloudflare account.
- Then, edit the following configuration files:

- In bot/loader.py, update your Cloudflare R2 bucket settings
- In bot/config.py, add your bot token and required API keys

```bash
python -m bot
```

```bash
screen -dmS bot python3 -m bot
```

# Setup Complete
# Your iPAWiND setup is now ready. If you encounter any issues, double-check the configuration files and ensure all packages are properly installed. or create issue on github
