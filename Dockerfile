FROM python:3.10

# Set working directory
WORKDIR /app

# unar (The Unarchiver CLI) is needed to extract .cbr (RAR) archives.
# It's free/open-source, unlike the proprietary unrar binary.
RUN apt-get update \
    && apt-get install -y --no-install-recommends unar \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose port for Koyeb health checks
EXPOSE 8080

# Run the bot + webserver
CMD ["python", "bot.py"]
