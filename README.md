# Energy Data Collector with Solar Performance Monitoring

Enhanced version of the Leneda energy data collector with automated solar performance monitoring and email alerting.

## Features

### New Features
- ✅ **Weather Data Integration**: Fetches daily sun hours and solar irradiance using Open-Meteo API
- ✅ **Expected Production Calculation**: Calculates expected solar output based on peak power and weather conditions
- ✅ **Performance Validation**: Compares actual vs. expected production (50% threshold)
- ✅ **Smart Alerting**: Email notifications for underperforming installations
- ✅ **Multiple Recipients**: Send alerts to multiple email addresses simultaneously
- ✅ **Alert Management**: Flags to prevent duplicate alerts with manual reset capability
- ✅ **Enhanced Database**: Stores weather data, expected values, and performance metrics

### Original Features
- Daily energy data collection from Leneda API
- SQLite database storage
- Multi-POD and multi-OBIS code support
- Earnings calculation

## Installation

### 1. Install Dependencies

install dependencies based on the requirements.txt file


### 2.Create a configuration file 

Create a configuration file based on the configuration_orig.yaml file
This file contains :
A section regarding email settings to send alarms 
A section with the details of the POD's
A section with a list of obiscodes
A section with the required info for LENEDA

### Daily Data Collection (Automated)

Run this script daily (e.g., via cron):

```bash
# Collect yesterday's data, analyze performance, send alerts if needed
python energy_data_collector_enhanced.py
```

The script will:
1. Fetch energy data from Leneda API
2. Fetch weather data for each installation
3. Calculate expected solar production
4. Compare actual vs. expected (50% threshold)
5. Send email alert if installations are underperforming
6. Store all data in SQLite database

### Manual Alert Management

Use the alert manager utility to view and manage alerts ( local access to the server required ):

```bash
# View all pending alerts
python alert_manager.py list --status pending

# View all alerts (any status)
python alert_manager.py list

# Show alert statistics
python alert_manager.py stats

# Acknowledge specific alerts (prevents re-sending)
python alert_manager.py acknowledge --pod LU0000010637000000000000070232023 --confirm

# Acknowledge all alerts for a specific date
python alert_manager.py acknowledge --date 2025-02-01 --confirm

# Reset alerts to allow re-sending (after fixing issue)
python alert_manager.py reset --pod LU0000010637000000000000070232023 --confirm

# Reset ALL alerts
python alert_manager.py reset --confirm
```

## How It Works

### Performance Calculation

1. **Weather Data**: Fetches daily sunshine hours and solar irradiance from Open-Meteo API
2. **Expected Production**: 
   ```
   Expected kWh = Peak Power (kW) × Solar Irradiance (kWh/m²) × Efficiency (0.80)
   ```
3. **Performance Ratio**: 
   ```
   Performance = Actual kWh / Expected kWh
   ```
4. **Threshold Check**: Alerts if performance < 50% of expected

### Alert Management System

```
┌─────────────────────────────────────────────────────────┐
│  New Underperformance Detected                          │
│  (actual < 50% of expected)                             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ Check alert_sent flag │
         └───────────┬───────────┘
                     │
         ┌───────────▼────────────┐
         │ alert_sent = 0?        │
         └───┬──────────────┬─────┘
             │ YES          │ NO
             │              │
             ▼              ▼
     ┌──────────────┐   [No Email]
     │  Send Email  │
     └──────┬───────┘
            │
            ▼
     ┌──────────────────┐
     │ Set alert_sent=1 │
     └──────────────────┘

User Actions:
  • acknowledge → Sets alert_acknowledged=1 (permanent suppression)
  • reset → Sets both flags=0 (allows new alerts)
```


## Automation Setup

### Cron Job (Daily)

Add to crontab for daily execution:

```bash
# Run every day at 6:00 AM (after previous day's data is available)
0 6 * * * /usr/bin/python3 /path/to/energy_data_collector_enhanced.py >> /var/log/energy_collector.log 2>&1
```
