# iPAWiND Setup Guide

Follow the instructions below to set up iPAWiND.

```bash
# Step 1: Update and Install Essential Packages
sudo apt update && sudo apt upgrade -y
sudo apt install zip unzip build-essential checkinstall zlib1g-dev libssl-dev zip unzip nodejs p7zip-full python3 python3-pip npm -y

# Step 2: Set Up the iPAWiND Project
cd iPAWiND

# Install .deb packages
dpkg -i tools/deb/*.deb

# Install npm packages
npm install node-forge ocsp

# Run the resource checker
nodejs tools/checker/resources.js

# Install Python dependencies
pip3 install -r requirements.txt

# Step 3: Install Docker
# Follow the Docker installation guide: https://docs.docker.com/engine/install/ubuntu/

# After installing Docker, start the containers
docker compose up -d

# Step 4: Configure Cloudflare R2 and Bot Settings

# Create an R2 bucket in your Cloudflare account.
# Then, edit the following configuration files:

# In bot/loader.py, update your Cloudflare R2 bucket settings
# In bot/config.py, add your bot token and required API keys

# Setup Complete
# Your iPAWiND setup is now ready. If you encounter any issues, double-check the configuration files and ensure all packages are properly installed. or create issue on githuh
