#!/bin/bash
# update_service.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
REQUIREMENTS_FILE="$PROJECT_DIR/requirements.txt"
SERVICE_NAME="MeshDresdenBot"

echo -e "${YELLOW}Aktualisiere $SERVICE_NAME...${NC}"

# Prüfen: Dienst existiert?
if ! systemctl list-unit-files | grep -q "$SERVICE_NAME.service"; then
  echo -e "${RED}FEHLER: Dienst $SERVICE_NAME nicht installiert!${NC}"
  echo "Führe zuerst install_service.sh aus."
  exit 1
fi

# requirements neu installieren
if [[ -f "$REQUIREMENTS_FILE" ]]; then
  echo -e "${YELLOW}Aktualisiere Abhängigkeiten...${NC}"
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip > /dev/null
  pip install -r "$REQUIREMENTS_FILE" --upgrade || { echo -e "${RED}pip fehlgeschlagen!${NC}"; exit 1; }
  deactivate
else
  echo -e "${YELLOW}Keine requirements.txt – überspringe pip.${NC}"
fi

# Dienst neu starten
echo -e "${YELLOW}Starte Dienst neu...${NC}"
sudo systemctl restart "$SERVICE_NAME.service"

sleep 2
if systemctl is-active --quiet "$SERVICE_NAME.service"; then
  echo -e "${GREEN}UPDATE ERFOLGREICH: $SERVICE_NAME läuft (neueste Version)${NC}"
else
  echo -e "${RED}FEHLER nach Update!${NC}"
  journalctl -u "$SERVICE_NAME.service" --since "5 minutes ago" | tail -20
  exit 1
fi