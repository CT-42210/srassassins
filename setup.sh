#!/bin/bash

# Srassassins Flask Application Deployment Script
# This script should be run from /var/www/srassassins
# Assumes the git repository has already been cloned to this location

# Exit on any error
set -e

# Display a status message
echo "===== Setting up srassassins Flask Application ====="

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

# Create and activate virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
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

# Determine the correct Apache configuration directory for Alma OS
if [ -d "/etc/httpd/conf.d" ]; then
    APACHE_CONF_DIR="/etc/httpd/conf.d"
elif [ -d "/etc/apache2/conf.d" ]; then
    APACHE_CONF_DIR="/etc/apache2/conf.d"
else
    echo "Warning: Could not find Apache configuration directory. Using /etc/httpd/conf.d"
    APACHE_CONF_DIR="/etc/httpd/conf.d"
fi

# Copy service file instead of creating it
echo "Copying systemd service file..."
if [ -f "/var/www/srassassins/srassassins.service" ]; then
    cp "/var/www/srassassins/srassassins.service" "/etc/systemd/system/srassassins.service"
else
    echo "Error: srassassins.service file not found in the repository!"
    exit 1
fi

# Copy Apache configuration file instead of creating it
echo "Copying Apache configuration file..."
if [ -f "/var/www/srassassins/srassassins.conf" ]; then
    cp "/var/www/srassassins/srassassins.conf" "${APACHE_CONF_DIR}/srassassins.conf"
else
    echo "Error: srassassins.conf file not found in the repository!"
    exit 1
fi

# Enable Apache proxy modules
echo "Enabling Apache proxy modules..."
if command -v a2enmod &> /dev/null; then
    # Debian-based command
    a2enmod proxy
    a2enmod proxy_http
else
    # For RHEL/CentOS/Alma Linux, modules are enabled by default if installed
    # Ensure modules are loaded
    if ! grep -q "mod_proxy.so" /etc/httpd/conf.modules.d/*.conf; then
        echo "LoadModule proxy_module modules/mod_proxy.so" >> /etc/httpd/conf.modules.d/00-proxy.conf
    fi
    if ! grep -q "mod_proxy_http.so" /etc/httpd/conf.modules.d/*.conf; then
        echo "LoadModule proxy_http_module modules/mod_proxy_http.so" >> /etc/httpd/conf.modules.d/00-proxy.conf
    fi
fi

# Enable and start the Gunicorn service
echo "Starting Gunicorn service..."
systemctl daemon-reload
systemctl enable srassassins.service
systemctl start srassassins.service

# Restart Apache
echo "Restarting Apache..."
if systemctl is-active --quiet httpd; then
    systemctl restart httpd
elif systemctl is-active --quiet apache2; then
    systemctl restart apache2
else
    echo "Warning: Could not determine Apache service name. Please restart Apache manually."
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
echo "- Apache logs: /var/log/httpd/srassassins-error.log"
echo ""
echo "You can access your application at your domain or via http://your-server-ip"