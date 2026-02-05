#!/usr/bin/env python3
"""
Alert Management Web API

FastAPI-based web application for managing energy data alerts.
Provides both a REST API and web interface.
@MarcDurbach 2026
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
import sqlite3
from datetime import datetime
import os
from contextlib import contextmanager

app = FastAPI(
    title="Energy Alert Management API",
    description="API for managing energy data alerts and monitoring solar performance",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
datapath="./data/"
# Database configuration
DB_PATH = os.getenv("DB_PATH", datapath+"energy_data_energiepark.db")


# Pydantic models
class Alert(BaseModel):
    date: str
    pod_code: str
    pod_name: str
    value_kwh: float
    expected_kwh: float
    performance_ratio: float
    alert_sent: bool
    alert_acknowledged: bool
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-02-01",
                "pod_code": "LU0000010637000000000000070232023",
                "pod_name": "Solar Installation 1",
                "value_kwh": 45.5,
                "expected_kwh": 60.0,
                "performance_ratio": 0.758,
                "alert_sent": False,
                "alert_acknowledged": False
            }
        }


class AlertStats(BaseModel):
    total_alerts: int
    pending: int
    sent: int
    acknowledged: int


class ActionResponse(BaseModel):
    success: bool
    message: str
    affected_records: int


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# API Endpoints
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web interface."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Energy Alert Management</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }
            header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            h1 { font-size: 2.5em; margin-bottom: 10px; }
            .subtitle { opacity: 0.9; font-size: 1.1em; }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                padding: 30px;
                background: #f8f9fa;
            }
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                text-align: center;
            }
            .stat-value {
                font-size: 2.5em;
                font-weight: bold;
                color: #667eea;
                margin: 10px 0;
            }
            .stat-label {
                color: #666;
                font-size: 0.9em;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .controls {
                padding: 30px;
                background: white;
                border-top: 1px solid #e0e0e0;
            }
            .filter-group {
                display: flex;
                gap: 15px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }
            select, input, button {
                padding: 12px 20px;
                border: 2px solid #e0e0e0;
                border-radius: 6px;
                font-size: 1em;
                outline: none;
                transition: all 0.3s;
            }
            select:focus, input:focus {
                border-color: #667eea;
            }
            button {
                background: #667eea;
                color: white;
                border: none;
                cursor: pointer;
                font-weight: 600;
            }
            button:hover {
                background: #5568d3;
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }
            button.danger {
                background: #e74c3c;
            }
            button.danger:hover {
                background: #c0392b;
            }
            button.success {
                background: #27ae60;
            }
            button.success:hover {
                background: #229954;
            }
            .alerts-table {
                padding: 30px;
                overflow-x: auto;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.95em;
            }
            th, td {
                padding: 15px;
                text-align: left;
                border-bottom: 1px solid #e0e0e0;
            }
            th {
                background: #f8f9fa;
                font-weight: 600;
                color: #333;
                position: sticky;
                top: 0;
            }
            tr:hover {
                background: #f8f9fa;
            }
            .badge {
                display: inline-block;
                padding: 5px 12px;
                border-radius: 20px;
                font-size: 0.85em;
                font-weight: 600;
            }
            .badge.pending {
                background: #fff3cd;
                color: #856404;
            }
            .badge.sent {
                background: #d1ecf1;
                color: #0c5460;
            }
            .badge.acknowledged {
                background: #d4edda;
                color: #155724;
            }
            .performance {
                font-weight: 600;
            }
            .performance.low {
                color: #e74c3c;
            }
            .performance.medium {
                color: #f39c12;
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: #666;
            }
            .error {
                background: #f8d7da;
                color: #721c24;
                padding: 15px;
                border-radius: 6px;
                margin: 20px;
            }
            .success-message {
                background: #d4edda;
                color: #155724;
                padding: 15px;
                border-radius: 6px;
                margin: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>⚡ Energy Alert Management</h1>
                <p class="subtitle">Monitor and manage solar installation performance alerts</p>
            </header>
            
            <div class="stats" id="stats">
                <div class="stat-card">
                    <div class="stat-label">Total Alerts</div>
                    <div class="stat-value" id="total-alerts">-</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Pending</div>
                    <div class="stat-value" id="pending-alerts">-</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Sent</div>
                    <div class="stat-value" id="sent-alerts">-</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Acknowledged</div>
                    <div class="stat-value" id="acknowledged-alerts">-</div>
                </div>
            </div>
            
            <div class="controls">
                <div class="filter-group">
                    <select id="status-filter">
                        <option value="all">All Alerts</option>
                        <option value="pending">Pending</option>
                        <option value="sent">Sent</option>
                        <option value="acknowledged">Acknowledged</option>
                    </select>
                    <input type="date" id="date-filter" placeholder="Filter by date">
                    <button onclick="loadAlerts()">🔍 Filter</button>
                    <button class="success" onclick="acknowledgeAll()">✓ Acknowledge All Pending</button>
                    <button class="danger" onclick="resetAll()">↺ Reset All</button>
                </div>
            </div>
            
            <div id="message-area"></div>
            
            <div class="alerts-table">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>POD Code</th>
                            <th>Installation</th>
                            <th>Actual (kWh)</th>
                            <th>Expected (kWh)</th>
                            <th>Performance</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="alerts-body">
                        <tr><td colspan="7" class="loading">Loading alerts...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            async function loadStats() {
                try {
                    const response = await fetch('/api/alerts/stats');
                    const data = await response.json();
                    document.getElementById('total-alerts').textContent = data.total_alerts;
                    document.getElementById('pending-alerts').textContent = data.pending;
                    document.getElementById('sent-alerts').textContent = data.sent;
                    document.getElementById('acknowledged-alerts').textContent = data.acknowledged;
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }
            
            async function loadAlerts() {
                const status = document.getElementById('status-filter').value;
                const date = document.getElementById('date-filter').value;
                
                let url = `/api/alerts?status=${status}`;
                if (date) url += `&date=${date}`;
                
                try {
                    const response = await fetch(url);
                    const alerts = await response.json();
                    
                    const tbody = document.getElementById('alerts-body');
                    
                    if (alerts.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="7" class="loading">No alerts found</td></tr>';
                        return;
                    }
                    
                    tbody.innerHTML = alerts.map(alert => {
                        let statusBadge = '';
                        if (alert.alert_acknowledged) {
                            statusBadge = '<span class="badge acknowledged">Acknowledged</span>';
                        } else if (alert.alert_sent) {
                            statusBadge = '<span class="badge sent">Sent</span>';
                        } else {
                            statusBadge = '<span class="badge pending">Pending</span>';
                        }
                        
                        const perfClass = alert.performance_ratio < 0.7 ? 'low' : 'medium';
                        const perfPercent = (alert.performance_ratio * 100).toFixed(1);
                        
                        return `
                            <tr>
                                <td>${alert.date}</td>
                                <td>${alert.pod_code.substring(0, 20)}...</td>
                                <td>${alert.pod_name}</td>
                                <td>${alert.value_kwh.toFixed(2)}</td>
                                <td>${alert.expected_kwh.toFixed(2)}</td>
                                <td><span class="performance ${perfClass}">${perfPercent}%</span></td>
                                <td>${statusBadge}</td>
                            </tr>
                        `;
                    }).join('');
                } catch (error) {
                    console.error('Error loading alerts:', error);
                    document.getElementById('alerts-body').innerHTML = 
                        '<tr><td colspan="7" class="error">Error loading alerts</td></tr>';
                }
            }
            
            async function acknowledgeAll() {
                if (!confirm('Acknowledge all pending alerts?')) return;
                
                try {
                    const response = await fetch('/api/alerts/acknowledge', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    showMessage(data.message, 'success');
                    loadStats();
                    loadAlerts();
                } catch (error) {
                    showMessage('Error acknowledging alerts', 'error');
                }
            }
            
            async function resetAll() {
                if (!confirm('Reset all alerts? This will allow them to be sent again.')) return;
                
                try {
                    const response = await fetch('/api/alerts/reset', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    showMessage(data.message, 'success');
                    loadStats();
                    loadAlerts();
                } catch (error) {
                    showMessage('Error resetting alerts', 'error');
                }
            }
            
            function showMessage(message, type) {
                const messageArea = document.getElementById('message-area');
                const className = type === 'success' ? 'success-message' : 'error';
                messageArea.innerHTML = `<div class="${className}">${message}</div>`;
                setTimeout(() => messageArea.innerHTML = '', 5000);
            }
            
            // Load data on page load
            loadStats();
            loadAlerts();
            
            // Refresh every 30 seconds
            setInterval(() => {
                loadStats();
                loadAlerts();
            }, 30000);
        </script>
    </body>
    </html>
    """


@app.get("/api/alerts", response_model=List[Alert])
async def get_alerts(
    status: Literal["all", "pending", "sent", "acknowledged"] = "all",
    date: Optional[str] = None,
    pod_code: Optional[str] = None
):
    """
    Get alerts with optional filtering.
    
    - **status**: Filter by alert status (all, pending, sent, acknowledged)
    - **date**: Filter by specific date (YYYY-MM-DD)
    - **pod_code**: Filter by POD code
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                date,
                pod_code,
                pod_name,
                value_kwh,
                expected_kwh,
                performance_ratio,
                alert_sent,
                alert_acknowledged
            FROM energy_data
            WHERE is_underperforming = 1
        '''
        params = []
        
        if status == 'pending':
            query += ' AND alert_sent = 0 AND alert_acknowledged = 0'
        elif status == 'sent':
            query += ' AND alert_sent = 1 AND alert_acknowledged = 0'
        elif status == 'acknowledged':
            query += ' AND alert_acknowledged = 1'
        
        if date:
            query += ' AND date = ?'
            params.append(date)
        
        if pod_code:
            query += ' AND pod_code = ?'
            params.append(pod_code)
        
        query += ' ORDER BY date DESC, pod_name'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        alerts = []
        for row in rows:
            alerts.append(Alert(
                date=row['date'],
                pod_code=row['pod_code'],
                pod_name=row['pod_name'],
                value_kwh=row['value_kwh'],
                expected_kwh=row['expected_kwh'],
                performance_ratio=row['performance_ratio'],
                alert_sent=bool(row['alert_sent']),
                alert_acknowledged=bool(row['alert_acknowledged'])
            ))
        
        return alerts


@app.get("/api/alerts/stats", response_model=AlertStats)
async def get_alert_stats():
    """Get statistics about alerts."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Total underperforming records
        cursor.execute('SELECT COUNT(*) as count FROM energy_data WHERE is_underperforming = 1')
        total_alerts = cursor.fetchone()['count']
        
        # Pending alerts
        cursor.execute('''
            SELECT COUNT(*) as count FROM energy_data 
            WHERE is_underperforming = 1 AND alert_sent = 0 AND alert_acknowledged = 0
        ''')
        pending = cursor.fetchone()['count']
        
        # Sent alerts
        cursor.execute('''
            SELECT COUNT(*) as count FROM energy_data 
            WHERE is_underperforming = 1 AND alert_sent = 1 AND alert_acknowledged = 0
        ''')
        sent = cursor.fetchone()['count']
        
        # Acknowledged alerts
        cursor.execute('''
            SELECT COUNT(*) as count FROM energy_data 
            WHERE is_underperforming = 1 AND alert_acknowledged = 1
        ''')
        acknowledged = cursor.fetchone()['count']
        
        return AlertStats(
            total_alerts=total_alerts,
            pending=pending,
            sent=sent,
            acknowledged=acknowledged
        )


@app.post("/api/alerts/acknowledge", response_model=ActionResponse)
async def acknowledge_alerts(
    pod_code: Optional[str] = None,
    date: Optional[str] = None
):
    """
    Acknowledge alerts to prevent them from being sent.
    
    - **pod_code**: Optional POD code to filter
    - **date**: Optional date to filter (YYYY-MM-DD)
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            if pod_code and date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE pod_code = ? AND date = ? AND is_underperforming = 1
                ''', (pod_code, date))
                message = f"Acknowledged alerts for POD {pod_code} on {date}"
            elif pod_code:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE pod_code = ? AND is_underperforming = 1
                ''', (pod_code,))
                message = f"Acknowledged all alerts for POD {pod_code}"
            elif date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE date = ? AND is_underperforming = 1
                ''', (date,))
                message = f"Acknowledged all alerts for date {date}"
            else:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 1
                    WHERE is_underperforming = 1
                ''')
                message = "Acknowledged all alerts"
            
            affected = cursor.rowcount
            conn.commit()
            
            return ActionResponse(
                success=True,
                message=message,
                affected_records=affected
            )
        except sqlite3.Error as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.post("/api/alerts/reset", response_model=ActionResponse)
async def reset_alerts(
    pod_code: Optional[str] = None,
    date: Optional[str] = None
):
    """
    Reset alert flags to allow alerts to be sent again.
    
    - **pod_code**: Optional POD code to filter
    - **date**: Optional date to filter (YYYY-MM-DD)
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            if pod_code and date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE pod_code = ? AND date = ?
                ''', (pod_code, date))
                message = f"Reset alerts for POD {pod_code} on {date}"
            elif pod_code:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE pod_code = ?
                ''', (pod_code,))
                message = f"Reset all alerts for POD {pod_code}"
            elif date:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE date = ?
                ''', (date,))
                message = f"Reset all alerts for date {date}"
            else:
                cursor.execute('''
                    UPDATE energy_data
                    SET alert_acknowledged = 0, alert_sent = 0
                    WHERE is_underperforming = 1
                ''')
                message = "Reset all alerts"
            
            affected = cursor.rowcount
            conn.commit()
            
            return ActionResponse(
                success=True,
                message=message,
                affected_records=affected
            )
        except sqlite3.Error as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)