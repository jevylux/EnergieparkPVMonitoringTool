#!/usr/bin/env python3
"""
Energy Data Collector for Leneda API with Solar Performance Monitoring
Fetches energy data for defined PODS for Energiepark Mëllerdall, 
validates against expected solar production based on weather,
and sends email alerts for underperforming installations.
@MarcDurbach 2026
"""

import sqlite3
import requests
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnergyDataCollector:
    """Collects energy data from Leneda API and stores in SQLite database."""
    
    # Solar panel efficiency factor (typical: 0.75-0.85 accounting for losses)
    PANEL_EFFICIENCY = 0.80
    
    # Performance threshold (50% of expected)
    PERFORMANCE_THRESHOLD = 0.50
    
    def __init__(self, config_path: str = "configuration_energiepark.yaml"):
        """Initialize the collector with configuration."""
        self.config = self._load_config(config_path)
        # Use the URL from config
        base_url = self.config.get('leneda', {}).get('url', 'https://api.leneda.lu')
        self.api_base_url = f"{base_url}/api/metering-points"
        self.db_path = 'energy_data_energiepark.db'
        self._init_database()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise
    
    def _init_database(self):
        """Initialize SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table for energy data with performance tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS energy_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pod_code TEXT NOT NULL,
                pod_name TEXT,
                obis_code TEXT NOT NULL,
                obis_description TEXT,
                date DATE NOT NULL,
                value_kwh REAL NOT NULL,
                kwh_price REAL NOT NULL,
                earnings REAL NOT NULL,
                unit TEXT,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                calculated BOOLEAN,
                -- Performance tracking fields
                peak_power_kw REAL,
                sun_hours REAL,
                solar_irradiance_kwh_m2 REAL,
                expected_kwh REAL,
                performance_ratio REAL,
                is_underperforming BOOLEAN DEFAULT 0,
                alert_sent BOOLEAN DEFAULT 0,
                alert_acknowledged BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(pod_code, obis_code, date)
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_pod_date 
            ON energy_data(pod_code, date)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_alerts 
            ON energy_data(is_underperforming, alert_sent, alert_acknowledged)
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")
    
    def _get_previous_day_dates(self) -> tuple:
        """Get start and end dates for previous day."""
        yesterday = datetime.now().date() - timedelta(days=1)
        start_date = yesterday.strftime('%Y-%m-%d')
        end_date = yesterday.strftime('%Y-%m-%d')
        return start_date, end_date
    
    def _get_weather_data(self, lat: float, lon: float , date: str) -> Optional[Dict]:
        """
        Fetch weather data (sun hours and solar irradiance) for a location and date.
        Using Open-Meteo API (free, no API key required).
        
        Returns dict with:
            - sun_hours: Hours of sunshine
            - solar_irradiance: Average solar radiation in kWh/m²
        """
        try:

            # Open-Meteo API for historical weather data
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                'latitude': lat,
                'longitude': lon,
                'start_date': date,
                'end_date': date,
                'daily': 'sunshine_duration,shortwave_radiation_sum',
                'timezone': 'Europe/Luxembourg'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'daily' in data:
                daily = data['daily']
                # Sunshine duration in seconds, convert to hours
                sun_hours = daily['sunshine_duration'][0] / 3600 if daily['sunshine_duration'][0] else 0
                # Shortwave radiation in MJ/m², convert to kWh/m²
                # 1 MJ/m² = 0.2778 kWh/m²
                radiation_mj = daily['shortwave_radiation_sum'][0] if daily['shortwave_radiation_sum'][0] else 0
                solar_irradiance = radiation_mj * 0.2778
                
                logger.info(f"Weather for {lat} {lon} on {date}: "
                          f"{sun_hours:.1f}h sun, {solar_irradiance:.2f} kWh/m²")
                
                return {
                    'sun_hours': sun_hours,
                    'solar_irradiance': solar_irradiance
                }
            
            logger.warning(f"No weather data available for {lat} {lon} on {date}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather API request failed for {lat} {lon}: {e}")
            return None
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error parsing weather data for {lat} {lon}: {e}")
            return None
    
    def _calculate_expected_production(self, peak_power_kw: float, 
                                      solar_irradiance: float,
                                      sun_hours: float) -> float:
        """
        Calculate expected solar energy production.
        
        Args:
            peak_power_kw: Installed peak power in kW
            solar_irradiance: Daily solar radiation in kWh/m²
            sun_hours: Hours of sunshine
            
        Returns:
            Expected energy production in kWh
            
        Formula:
            Expected kWh = Peak Power (kW) × Solar Irradiance (kWh/m²) × Efficiency Factor
            
            Standard Test Conditions (STC): 1 kWh/m² irradiance
            So solar_irradiance represents the fraction of STC conditions
        """
        # Under STC (1000 W/m² = 1 kWh/m²), a 1kW panel produces 1kW
        # Actual production scales with irradiance and efficiency
        expected_kwh = peak_power_kw * solar_irradiance * self.PANEL_EFFICIENCY
        
        logger.debug(f"Expected calculation: {peak_power_kw}kW × "
                    f"{solar_irradiance:.2f}kWh/m² × {self.PANEL_EFFICIENCY} = "
                    f"{expected_kwh:.2f}kWh")
        
        return expected_kwh
    
    def _fetch_data(self, pod_code: str, obis_code: str, 
                   start_date: str, end_date: str) -> Optional[Dict]:
        """Fetch data from Leneda API for a specific POD and OBIS code."""
        # URL encode the OBIS code
        obis_encoded = obis_code.replace(':', '%3A')
        
        url = (f"{self.api_base_url}/{pod_code}/time-series/aggregated"
               f"?obisCode={obis_encoded}"
               f"&startDate={start_date}"
               f"&endDate={end_date}"
               f"&aggregationLevel=Infinite"
               f"&transformationMode=Accumulation")
        
        # Get headers from config
        leneda_config = self.config.get('leneda', {})
        api_key = leneda_config.get('apiKey', {}).get('value', '')
        energy_id = leneda_config.get('energyId', {}).get('value', '')
        
        headers = {
            'X-API-KEY': api_key,
            'X-ENERGY-ID': energy_id
        }
        
        try:
            logger.info(f"Fetching data for POD: {pod_code}, OBIS: {obis_code}")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed for {pod_code}/{obis_code}: {e}")
            return None
    
    def _store_data(self, pod_code: str, pod_name: str, obis_code: str,
                   obis_description: str, kwh_price: float, peak_power_kw: float,
                   api_response: Dict, date: str, weather_data: Optional[Dict]):
        """Store fetched data in SQLite database with performance analysis."""
        if not api_response or 'aggregatedTimeSeries' not in api_response:
            logger.warning(f"No data to store for {pod_code}/{obis_code}")
            return
        
        time_series = api_response['aggregatedTimeSeries']
        if not time_series:
            logger.warning(f"Empty time series for {pod_code}/{obis_code}")
            return
        
        # Get the first entry (should be only one for daily aggregation)
        data = time_series[0]
        value_kwh = data['value']
        earnings = value_kwh * kwh_price
        unit = api_response.get('unit', 'kWh')
        
        # Performance analysis
        sun_hours = None
        solar_irradiance = None
        expected_kwh = None
        performance_ratio = None
        is_underperforming = False
        
        if weather_data and peak_power_kw:
            sun_hours = weather_data['sun_hours']
            solar_irradiance = weather_data['solar_irradiance']
            
            # Calculate expected production
            expected_kwh = self._calculate_expected_production(
                peak_power_kw, solar_irradiance, sun_hours
            )
            
            # Calculate performance ratio
            if expected_kwh > 0:
                performance_ratio = value_kwh / expected_kwh
                
                # Check if underperforming (less than 50% of expected)
                if performance_ratio < self.PERFORMANCE_THRESHOLD:
                    is_underperforming = True
                    logger.warning(f"⚠️  Underperformance detected for {pod_name}: "
                                 f"{value_kwh:.2f}kWh actual vs {expected_kwh:.2f}kWh expected "
                                 f"({performance_ratio*100:.1f}%)")
                else:
                    logger.info(f"✓ Performance OK for {pod_name}: "
                              f"{value_kwh:.2f}kWh actual vs {expected_kwh:.2f}kWh expected "
                              f"({performance_ratio*100:.1f}%)")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if this error was already acknowledged
            cursor.execute('''
                SELECT alert_acknowledged FROM energy_data
                WHERE pod_code = ? AND obis_code = ? AND date = ?
            ''', (pod_code, obis_code, date))
            
            existing = cursor.fetchone()
            alert_acknowledged = existing[0] if existing else False
            
            cursor.execute('''
                INSERT OR REPLACE INTO energy_data 
                (pod_code, pod_name, obis_code, obis_description, date, 
                 value_kwh, kwh_price, earnings, unit, started_at, ended_at, calculated,
                 peak_power_kw, sun_hours, solar_irradiance_kwh_m2, expected_kwh,
                 performance_ratio, is_underperforming, alert_sent, alert_acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            ''', (
                pod_code,
                pod_name,
                obis_code,
                obis_description,
                date,
                value_kwh,
                kwh_price,
                earnings,
                unit,
                data.get('startedAt'),
                data.get('endedAt'),
                data.get('calculated', False),
                peak_power_kw,
                sun_hours,
                solar_irradiance,
                expected_kwh,
                performance_ratio,
                is_underperforming,
                alert_acknowledged  # Preserve acknowledged status
            ))
            
            conn.commit()
            logger.info(f"Stored data: {pod_code}/{obis_code} - "
                       f"{value_kwh} kWh, Earnings: €{earnings:.2f}")
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
        finally:
            conn.close()
    
    def collect_data(self):
        """Main method to collect data for all PODs and OBIS codes."""
        start_date, end_date = self._get_previous_day_dates()
        logger.info(f"Collecting data for date: {start_date}")
        
        # Get PODs from config
        pods = self.config.get('pod', [])
        if not pods:
            logger.error("No PODs defined in configuration")
            return
        
        # Get OBIS codes from config
        obis_codes = self.config.get('obis_codes', [])
        if not obis_codes:
            logger.error("No OBIS codes defined in configuration")
            return
        
        for pod in pods:
            pod_code = pod['id']
            pod_name = pod.get('address', pod_code)
            kwh_price = pod.get('price_per_kWh', 0.0)
            peak_power_kw = pod.get('peak_power', 0.0)
            lat = pod.get('Latitude', None)
            lon = pod.get('Longitude', None)
            
            logger.info(f"Processing POD: {pod_name} ({pod_code})")
            
            # Fetch weather data for this location
            weather_data = self._get_weather_data(lat, lon, start_date)
            
            # Process each OBIS code for this POD
            for obis_code in obis_codes:
                obis_description = f"OBIS {obis_code}"
                
                # Fetch data from API
                api_response = self._fetch_data(
                    pod_code, obis_code, start_date, end_date
                )
                
                if api_response:
                    # Store in database with performance analysis
                    self._store_data(
                        pod_code, pod_name, obis_code, obis_description,
                        kwh_price, peak_power_kw, api_response, start_date,
                        weather_data
                    )
    
    def get_pending_alerts(self) -> List[Dict]:
        """Get all underperforming installations that haven't been alerted yet."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                date,
                pod_code,
                pod_name,
                obis_code,
                value_kwh,
                expected_kwh,
                performance_ratio,
                sun_hours,
                solar_irradiance_kwh_m2
            FROM energy_data
            WHERE is_underperforming = 1 
              AND alert_sent = 0
              AND alert_acknowledged = 0
            ORDER BY date DESC, pod_name
        ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'date': row[0],
                'pod_code': row[1],
                'pod_name': row[2],
                'obis_code': row[3],
                'actual_kwh': row[4],
                'expected_kwh': row[5],
                'performance_ratio': row[6],
                'sun_hours': row[7],
                'solar_irradiance': row[8]
            })
        
        conn.close()
        return results
    
    def mark_alerts_sent(self, alerts: List[Dict]):
        """Mark alerts as sent in the database."""
        if not alerts:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for alert in alerts:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_sent = 1
                    WHERE pod_code = ? AND obis_code = ? AND date = ?
                ''', (alert['pod_code'], alert['obis_code'], alert['date']))
            
            conn.commit()
            logger.info(f"Marked {len(alerts)} alerts as sent")
        except sqlite3.Error as e:
            logger.error(f"Error marking alerts as sent: {e}")
        finally:
            conn.close()
    
    def reset_alert_flags(self, pod_code: Optional[str] = None, 
                         date: Optional[str] = None):
        """
        Reset alert acknowledged flags to allow new alerts.
        
        Args:
            pod_code: Optional POD code to reset (resets all if None)
            date: Optional date to reset (resets all if None)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if pod_code and date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE pod_code = ? AND date = ?
                ''', (pod_code, date))
                logger.info(f"Reset alerts for POD {pod_code} on {date}")
            elif pod_code:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE pod_code = ?
                ''', (pod_code,))
                logger.info(f"Reset all alerts for POD {pod_code}")
            elif date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE date = ?
                ''', (date,))
                logger.info(f"Reset all alerts for date {date}")
            else:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                ''')
                logger.info("Reset all alerts")
            
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error resetting alerts: {e}")
        finally:
            conn.close()
    
    def acknowledge_alerts(self, pod_code: Optional[str] = None,
                          date: Optional[str] = None):
        """
        Acknowledge alerts to prevent them from being sent again.
        
        Args:
            pod_code: Optional POD code to acknowledge (acknowledges all if None)
            date: Optional date to acknowledge (acknowledges all if None)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if pod_code and date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE pod_code = ? AND date = ? AND is_underperforming = 1
                ''', (pod_code, date))
                logger.info(f"Acknowledged alerts for POD {pod_code} on {date}")
            elif pod_code:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE pod_code = ? AND is_underperforming = 1
                ''', (pod_code,))
                logger.info(f"Acknowledged all alerts for POD {pod_code}")
            elif date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE date = ? AND is_underperforming = 1
                ''', (date,))
                logger.info(f"Acknowledged all alerts for date {date}")
            else:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE is_underperforming = 1
                ''')
                logger.info("Acknowledged all alerts")
            
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error acknowledging alerts: {e}")
        finally:
            conn.close()
    
    def send_alert_email(self, alerts: List[Dict]):
        """
        Send email alert for underperforming installations.
        
        Args:
            alerts: List of alert dictionaries
        """
        if not alerts:
            logger.info("No alerts to send")
            return
        
        # Get email configuration
        email_config = self.config.get('email', {})
        if not email_config:
            logger.error("Email configuration not found in config file")
            return
        
        smtp_server = email_config.get('smtp_server')
        smtp_port = email_config.get('smtp_port')
        sender_email = email_config.get('sender_email')

        sender_password = email_config.get('sender_password')
        recipient_config = email_config.get('recipient_email')
        # Parse recipient emails - support multiple formats
        recipient_emails = []
        if isinstance(recipient_config, list):
            # List of dicts: [{"mail": "x@y.com"}, {"mail": "a@b.com"}]
            for item in recipient_config:
                if isinstance(item, dict) and 'mail' in item:
                    recipient_emails.append(item['mail'])
                elif isinstance(item, str):
                    # Simple list: ["x@y.com", "a@b.com"]
                    recipient_emails.append(item)
        elif isinstance(recipient_config, str):
            # Single string: "x@y.com"
            recipient_emails.append(recipient_config)
        
        if not all([sender_email, sender_password, recipient_emails]):
            logger.error("Email configuration incomplete. Required: sender_email, sender_password, recipient_email")
            logger.debug(f"Config values - sender: {bool(sender_email)}, password: {bool(sender_password)}, recipients: {len(recipient_emails)}")
            return
        
        # Create email content
        subject = f"⚠️ Solar Performance Alert - {len(alerts)} Installation(s) Underperforming"
        
        # Group alerts by date
        alerts_by_date = {}
        for alert in alerts:
            date = alert['date']
            if date not in alerts_by_date:
                alerts_by_date[date] = []
            alerts_by_date[date].append(alert)
        
        # Build HTML email
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h2 {{ color: #d9534f; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th {{ background-color: #d9534f; color: white; padding: 10px; text-align: left; }}
                td {{ border: 1px solid #ddd; padding: 8px; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .warning {{ color: #d9534f; font-weight: bold; }}
                .info {{ color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <h2>⚠️ Solar Performance Alert</h2>
            <p>The following installations are performing below 50% of expected output:</p>
        """
        
        for date in sorted(alerts_by_date.keys(), reverse=True):
            date_alerts = alerts_by_date[date]
            html_body += f"""
            <h3>Date: {date}</h3>
            <table>
                <tr>
                    <th>Installation</th>
                    <th>Actual (kWh)</th>
                    <th>Expected (kWh)</th>
                    <th>Performance</th>
                    <th>Weather</th>
                </tr>
            """
            
            for alert in date_alerts:
                performance_pct = alert['performance_ratio'] * 100
                html_body += f"""
                <tr>
                    <td><strong>{alert['pod_name']}</strong><br/>
                        <span class="info">{alert['pod_code']} / {alert['obis_code']}</span></td>
                    <td>{alert['actual_kwh']:.2f}</td>
                    <td>{alert['expected_kwh']:.2f}</td>
                    <td class="warning">{performance_pct:.1f}%</td>
                    <td>{alert['sun_hours']:.1f}h sun<br/>
                        {alert['solar_irradiance']:.2f} kWh/m²</td>
                </tr>
                """
            
            html_body += "</table>"
        
        html_body += """
            <hr/>
            <p class="info">
                <strong>Note:</strong> This alert will not be sent again for these installations 
                until the alerts are manually reset in the system.
            </p>
            <p class="info">
                To acknowledge these alerts and prevent future notifications, 
                use the acknowledge_alerts() method.
            </p>
        </body>
        </html>
        """
        
        # Create message
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = sender_email
        message['To'] = ', '.join(recipient_emails)
        
        # Attach HTML
        html_part = MIMEText(html_body, 'html')
        message.attach(html_part)
        # Send email
        print("start sending email")
        server = smtplib.SMTP(smtp_server, smtp_port, 20)
        # uncomment the following line to get detailed info about the email sending process
        #server.set_debuglevel(1)
        #try:
        print("start tls")
        server.starttls()
        print("server login")
        server.login(sender_email, sender_password)
        print("server send message")
        server.send_message(message, to_addrs=recipient_emails)  # or
        #server.sendmail(message['From'], recipient_email, message.as_string())
        
        logger.info(f"Alert email sent to {recipient_emails} for {len(alerts)} installations")
        
        # Mark alerts as sent
        self.mark_alerts_sent(alerts)
            
        #except Exception as e:
            #logger.error(f"Failed to send email: {e}")
    
    def get_summary(self, days: int = 7) -> List[Dict]:
        """Get summary of data for the last N days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                date,
                pod_name,
                obis_description,
                value_kwh,
                earnings,
                expected_kwh,
                performance_ratio,
                is_underperforming
            FROM energy_data
            WHERE date >= date('now', '-' || ? || ' days')
            ORDER BY date DESC, pod_name, obis_description
        ''', (days,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'date': row[0],
                'pod_name': row[1],
                'obis_description': row[2],
                'value_kwh': row[3],
                'earnings': row[4],
                'expected_kwh': row[5],
                'performance_ratio': row[6],
                'is_underperforming': row[7]
            })
        
        conn.close()
        return results


def main():
    """Main entry point."""
    try:
        collector = EnergyDataCollector()
        
        # Collect data
        collector.collect_data()
        
        # Check for alerts and send email if needed
        pending_alerts = collector.get_pending_alerts()
        if pending_alerts:
            logger.info(f"Found {len(pending_alerts)} pending alerts")
            collector.send_alert_email(pending_alerts)
        else:
            logger.info("No pending alerts")
        
        # Print summary
        print("\n" + "="*90)
        print("SUMMARY - Last 7 Days")
        print("="*90)
        summary = collector.get_summary(7)
        
        if summary:
            print(f"{'Date':<12} | {'Installation':<25} | {'Actual':>8} | "
                  f"{'Expected':>8} | {'Perf%':>6} | {'Status':>12} | {'Earnings':>10}")
            print("-"*90)
            
            for entry in summary:
                actual = entry['value_kwh']
                expected = entry['expected_kwh']
                perf = entry['performance_ratio']
                status = "⚠️ ALERT" if entry['is_underperforming'] else "✓ OK"
                
                perf_str = f"{perf*100:.1f}%" if perf is not None else "N/A"
                expected_str = f"{expected:.2f}" if expected is not None else "N/A"
                
                print(f"{entry['date']:<12} | {entry['pod_name'][:25]:<25} | "
                      f"{actual:8.2f} | {expected_str:>8} | {perf_str:>6} | "
                      f"{status:>12} | €{entry['earnings']:8.2f}")
        else:
            print("No data available")
        
        print("="*90)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
