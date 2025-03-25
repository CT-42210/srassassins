#!/bin/bash

# Srassassins Flask Application Deployment Script
# This script should be run from /var/www/srassassins
# Handles both new installations and re-runs by overwriting existing files

# Exit on any error
set -e

# Display a status message
echo "===== Setting up Srassassins Flask Application ====="

# Check if we're in the right directory
if [ "$(pwd)" != "/var/www/srassassins" ]; then
    echo "Error: This script must be run from /var/www/srassassins"
    exit 1
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Force flag for overwriting existing virtual environment
FORCE_REINSTALL=true

# Handle existing virtual environment
if [ -d "venv" ]; then
    if [ "$FORCE_REINSTALL" = true ]; then
        echo "Removing existing virtual environment..."
        rm -rf venv
        echo "Creating new Python virtual environment..."
        python3 -m venv venv
    else
        echo "Using existing virtual environment..."
    fi
else
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install required packages from requirements.txt
echo "Installing dependencies from requirements.txt..."
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "Error: requirements.txt not found!"
    exit 1
fi

# Initialize database with handling for existing migrations
echo "Initialize Database"
if [ -d "migrations" ]; then
    # If migrations directory exists and we're forcing reinstall, remove it
    if [ "$FORCE_REINSTALL" = true ]; then
        echo "Removing existing migrations directory..."
        rm -rf migrations
        echo "Initializing fresh database migration..."
        flask db init
    else
        echo "Migrations directory already exists, skipping initialization..."
    fi
else
    echo "Initializing database migration..."
    flask db init
fi

# Always run migrate and upgrade
echo "Running database migrations..."
flask db migrate
flask db upgrade

# Determine the correct Apache configuration directory for cPanel on Alma OS
if [ -d "/usr/local/apache/conf/userdata/std/2_4/_/srassassins" ]; then
    # cPanel with per-user vhosts configuration
    APACHE_CONF_DIR="/usr/local/apache/conf/userdata/std/2_4/_/srassassins"
    mkdir -p "$APACHE_CONF_DIR"
elif [ -d "/usr/local/apache/conf/vhosts" ]; then
    # cPanel with centralized vhosts configuration
    APACHE_CONF_DIR="/usr/local/apache/conf/vhosts"
elif [ -d "/etc/httpd/conf.d" ]; then
    # Standard Alma OS location
    APACHE_CONF_DIR="/etc/httpd/conf.d"
elif [ -d "/etc/apache2/conf.d" ]; then
    # Alternative location
    APACHE_CONF_DIR="/etc/apache2/conf.d"
else
    # Fallback to a common location and ensure it exists
    echo "Warning: Could not find standard Apache configuration directory."
    APACHE_CONF_DIR="/usr/local/apache/conf.d"
    mkdir -p "$APACHE_CONF_DIR"
fi

echo "Using Apache configuration directory: $APACHE_CONF_DIR"

# Stop existing service if running
if systemctl is-active --quiet srassassins.service; then
    echo "Stopping existing srassassins service..."
    systemctl stop srassassins.service
fi

# Copy service file instead of creating it
echo "Copying systemd service file..."
if [ -f "/var/www/srassassins/srassassins.service" ]; then
    cp -f "/var/www/srassassins/srassassins.service" "/etc/systemd/system/srassassins.service"
    echo "Service file copied to /etc/systemd/system/srassassins.service"
else
    echo "Error: srassassins.service file not found in the repository!"
    exit 1
fi

# Copy Apache configuration file instead of creating it
echo "Copying Apache configuration file..."
if [ -f "/var/www/srassassins/srassassins.conf" ]; then
    cp -f "/var/www/srassassins/srassassins.conf" "${APACHE_CONF_DIR}/srassassins.conf"
    echo "Apache configuration copied to ${APACHE_CONF_DIR}/srassassins.conf"
else
    echo "Error: srassassins.conf file not found in the repository!"
    exit 1
fi

# Enable Apache proxy modules for cPanel
echo "Enabling Apache proxy modules for cPanel..."

# Determine Apache config locations for cPanel
if [ -d "/usr/local/apache/conf" ]; then
    APACHE_CONF_DIR="/usr/local/apache/conf"
    APACHE_MODULES_FILE="${APACHE_CONF_DIR}/includes/pre_main_global.conf"
elif [ -d "/etc/apache2" ]; then
    APACHE_CONF_DIR="/etc/apache2"
    APACHE_MODULES_FILE="${APACHE_CONF_DIR}/conf.d/includes.conf"
else
    APACHE_CONF_DIR="/etc/httpd"
    APACHE_MODULES_FILE="${APACHE_CONF_DIR}/conf/includes/pre_main_global.conf"
fi

# Create directory if it doesn't exist
mkdir -p "$(dirname "$APACHE_MODULES_FILE")"

# Check if proxy modules are already enabled
if [ -f "$APACHE_MODULES_FILE" ]; then
    if ! grep -q "mod_proxy.so\|proxy_module" "$APACHE_MODULES_FILE"; then
        echo "# Added by srassassins setup script" >> "$APACHE_MODULES_FILE"
        echo "LoadModule proxy_module modules/mod_proxy.so" >> "$APACHE_MODULES_FILE"
        echo "LoadModule proxy_http_module modules/mod_proxy_http.so" >> "$APACHE_MODULES_FILE"
        echo "Proxy modules added to $APACHE_MODULES_FILE"
    else
        echo "Proxy modules already enabled in $APACHE_MODULES_FILE"
    fi
else
    echo "# Added by srassassins setup script" > "$APACHE_MODULES_FILE"
    echo "LoadModule proxy_module modules/mod_proxy.so" >> "$APACHE_MODULES_FILE"
    echo "LoadModule proxy_http_module modules/mod_proxy_http.so" >> "$APACHE_MODULES_FILE"
    echo "Created $APACHE_MODULES_FILE with proxy modules"
fi

# Enable and start the Gunicorn service
echo "Starting Gunicorn service..."
systemctl daemon-reload
systemctl enable srassassins.service
systemctl restart srassassins.service  # Use restart instead of start to handle re-runs

# Restart Apache (cPanel method)
echo "Restarting Apache..."
if [ -f "/scripts/restartsrv_apache" ]; then
    # cPanel restart script
    /scripts/restartsrv_apache
elif [ -f "/usr/local/cpanel/scripts/restartsrv_httpd" ]; then
    # Alternative cPanel restart script
    /usr/local/cpanel/scripts/restartsrv_httpd
elif systemctl is-active --quiet httpd; then
    # Standard systemd service name
    systemctl restart httpd
elif systemctl is-active --quiet apache2; then
    # Alternative systemd service name
    systemctl restart apache2
else
    echo "Warning: Could not determine Apache service name. Please restart Apache manually with: /scripts/restartsrv_httpd"
fi

# Provide status information
echo ""
echo "===== Setup Complete! ====="
echo "Gunicorn service status:"
systemctl status srassassins.service --no-pager

echo ""
echo "Next steps:"
echo "1. Ensure your domain is properly configured"
echo "2. Check firewall settings if necessary"
echo ""
echo "To troubleshoot:"
echo "- Gunicorn logs: journalctl -u srassassins.service"
echo "- Apache logs: check cPanel logs or /var/log/httpd/srassassins-error.log"
echo ""
echo "You can access your application at your domain or via http://your-server-ip"