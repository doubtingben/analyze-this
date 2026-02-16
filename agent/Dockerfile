FROM node:22-slim

# Install Python and git
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone the analyze-this repo for the Firestore MCP server
RUN git clone https://github.com/doubtingben/analyze-this.git /app/analyze-this

# Set up Python virtual environment and install dependencies
WORKDIR /app/analyze-this/backend
RUN python3 -m venv .venv && \
    .venv/bin/pip install --upgrade pip && \
    .venv/bin/pip install -r requirements.txt

# Copy agent source
WORKDIR /app/agent
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Copy the Docker-specific MCP config
COPY mcp-config.docker.json ./mcp-config.json

# Environment variables (override at runtime)
ENV IRC_SERVER=chat.interestedparticipant.org
ENV IRC_PORT=6697
ENV IRC_NICK=AnalyzeBot
ENV IRC_CHANNEL=#analyze-this
ENV MCP_CONFIG_FILE=/app/agent/mcp-config.json

CMD ["npm", "start"]
