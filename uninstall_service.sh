#!/bin/bash
# uninstall_service.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="mein_projekt"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo -e "${YELLOW}Deinstalliere $SERVICE_NAME...${NC}"

# Dienst stoppen & deaktivieren
if systemctl is-active --quiet "$SERVICE_NAME.service"; then
  echo -e "${YELLOW}Stoppe Dienst...${NC}"
  sudo systemctl stop "$SERVICE_NAME.service"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME.service"; then
  echo -e "${YELLOW}Deaktiviere Autostart...${NC}"
  sudo systemctl disable "$SERVICE_NAME.service" --quiet
fi

# Service-Datei löschen
if [[ -f "$SERVICE_FILE" ]]; then
  echo -e "${YELLOW}Entferne $SERVICE_FILE...${NC}"
  sudo rm -f "$SERVICE_FILE"
  sudo systemctl daemon-reload
  sudo systemctl reset-failed
else
  echo -e "${YELLOW}Service-Datei nicht gefunden – bereits entfernt?${NC}"
fi

# Optional: venv löschen
read -p "Soll das venv-Verzeichnis ($VENV_DIR) GELÖSCHT werden? (j/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Jj]$ ]]; then
  echo -e "${YELLOW}Lösche $VENV_DIR...${NC}"
  rm -rf "$VENV_DIR"
else
  echo -e "${GREEN}venv bleibt erhalten: $VENV_DIR${NC}"
fi

echo -e "${GREEN}Deinstallation abgeschlossen!${NC}"