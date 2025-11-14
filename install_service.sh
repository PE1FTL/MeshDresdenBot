#!/bin/bash
# install_service.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
REQUIREMENTS_FILE="$PROJECT_DIR/requirements.txt"
MAIN_SCRIPT="$PROJECT_DIR/app.py"  # ← ÄNDERN bei anderem Namen!
SERVICE_NAME="mein_projekt"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

CURRENT_USER="$(whoami)"
CURRENT_GROUP="$(id -gn)"

echo -e "${YELLOW}Installiere $SERVICE_NAME als Systemdienst...${NC}"

# Prüfungen
[[ ! -f "$REQUIREMENTS_FILE" ]] && { echo -e "${RED}FEHLER: $REQUIREMENTS_FILE fehlt!${NC}"; exit 1; }
[[ ! -f "$MAIN_SCRIPT" ]] && { echo -e "${RED}FEHLER: $MAIN_SCRIPT fehlt!${NC}"; exit 1; }

# venv
[[ ! -d "$VENV_DIR" ]] && { echo -e "${YELLOW}Erstelle venv...${NC}"; python3 -m venv "$VENV_DIR"; } || echo -e "${GREEN}venv existiert.${NC}"

# requirements
echo -e "${YELLOW}Installiere Abhängigkeiten...${NC}"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip > /dev/null
pip install -r "$REQUIREMENTS_FILE" || { echo -e "${RED}pip fehlgeschlagen!${NC}"; exit 1; }
deactivate

# Service-Datei
echo -e "${YELLOW}Erstelle systemd-Service...${NC}"
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Mein Python-Projekt als Dienst
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_GROUP
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$VENV_DIR/bin/python $MAIN_SCRIPT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Aktivieren
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME.service" --quiet
sudo systemctl restart "$SERVICE_NAME.service"

sleep 2
if systemctl is-active --quiet "$SERVICE_NAME.service"; then
  echo -e "${GREEN}ERFOLG: $SERVICE_NAME läuft!${NC}"
else
  echo -e "${RED}FEHLER: Dienst läuft nicht!${NC}"
  echo -e "Logs: ${YELLOW}journalctl -u $SERVICE_NAME.service -n 50${NC}"
  exit 1
fi

echo -e "${GREEN}Installation abgeschlossen!${NC}"