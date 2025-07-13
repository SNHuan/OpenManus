#!/usr/bin/env python3
"""System monitoring script for OpenManus project."""

import asyncio
import time
import psutil
import json
from datetime import datetime, timedelta
from typing import Dict, Any
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.logger import logger
from app.event.manager import event_manager
from app.database.database import get_database
from app.database.models import Event, Conversation, User
from sqlalchemy import select, func


class SystemMonitor:
    """System monitoring and metrics collection."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.metrics_history = []
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'error_rate': 0.1,  # 10% error rate
        }
    
    async def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system performance metrics."""
        try:
            # CPU and Memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network
            network = psutil.net_io_counters()
            
            # Process info
            process = psutil.Process()
            process_memory = process.memory_info()
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'system': {
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_used_gb': memory.used / (1024**3),
                    'memory_total_gb': memory.total / (1024**3),
                    'disk_percent': disk.percent,
                    'disk_used_gb': disk.used / (1024**3),
                    'disk_total_gb': disk.total / (1024**3),
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv,
                },
                'process': {
                    'memory_rss_mb': process_memory.rss / (1024**2),
                    'memory_vms_mb': process_memory.vms / (1024**2),
                    'cpu_percent': process.cpu_percent(),
                    'num_threads': process.num_threads(),
                }
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return {}
    
    async def collect_application_metrics(self) -> Dict[str, Any]:
        """Collect application-specific metrics."""
        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
            }
            
            # Event system metrics
            if event_manager._initialized:
                event_stats = event_manager.get_stats()
                metrics['events'] = event_stats
            
            # Database metrics
            try:
                async for session in get_database():
                    # Count users
                    user_count = await session.scalar(select(func.count(User.id)))
                    
                    # Count conversations
                    conv_count = await session.scalar(select(func.count(Conversation.id)))
                    active_conv_count = await session.scalar(
                        select(func.count(Conversation.id)).where(Conversation.status == 'active')
                    )
                    
                    # Count events
                    event_count = await session.scalar(select(func.count(Event.id)))
                    
                    # Recent events (last hour)
                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    recent_events = await session.scalar(
                        select(func.count(Event.id)).where(Event.timestamp >= one_hour_ago)
                    )
                    
                    # Error events (last hour)
                    error_events = await session.scalar(
                        select(func.count(Event.id)).where(
                            Event.timestamp >= one_hour_ago,
                            Event.status == 'failed'
                        )
                    )
                    
                    metrics['database'] = {
                        'total_users': user_count,
                        'total_conversations': conv_count,
                        'active_conversations': active_conv_count,
                        'total_events': event_count,
                        'recent_events_1h': recent_events,
                        'error_events_1h': error_events,
                        'error_rate_1h': error_events / max(recent_events, 1),
                    }
                    break
                    
            except Exception as e:
                logger.error(f"Failed to collect database metrics: {e}")
                metrics['database'] = {'error': str(e)}
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect application metrics: {e}")
            return {}
    
    async def check_alerts(self, system_metrics: Dict[str, Any], app_metrics: Dict[str, Any]):
        """Check for alert conditions."""
        alerts = []
        
        try:
            # System alerts
            if 'system' in system_metrics:
                sys_metrics = system_metrics['system']
                
                if sys_metrics['cpu_percent'] > self.alert_thresholds['cpu_percent']:
                    alerts.append({
                        'type': 'high_cpu',
                        'severity': 'warning',
                        'message': f"High CPU usage: {sys_metrics['cpu_percent']:.1f}%",
                        'value': sys_metrics['cpu_percent'],
                        'threshold': self.alert_thresholds['cpu_percent']
                    })
                
                if sys_metrics['memory_percent'] > self.alert_thresholds['memory_percent']:
                    alerts.append({
                        'type': 'high_memory',
                        'severity': 'warning',
                        'message': f"High memory usage: {sys_metrics['memory_percent']:.1f}%",
                        'value': sys_metrics['memory_percent'],
                        'threshold': self.alert_thresholds['memory_percent']
                    })
                
                if sys_metrics['disk_percent'] > self.alert_thresholds['disk_percent']:
                    alerts.append({
                        'type': 'high_disk',
                        'severity': 'critical',
                        'message': f"High disk usage: {sys_metrics['disk_percent']:.1f}%",
                        'value': sys_metrics['disk_percent'],
                        'threshold': self.alert_thresholds['disk_percent']
                    })
            
            # Application alerts
            if 'database' in app_metrics and 'error_rate_1h' in app_metrics['database']:
                error_rate = app_metrics['database']['error_rate_1h']
                if error_rate > self.alert_thresholds['error_rate']:
                    alerts.append({
                        'type': 'high_error_rate',
                        'severity': 'warning',
                        'message': f"High error rate: {error_rate:.1%}",
                        'value': error_rate,
                        'threshold': self.alert_thresholds['error_rate']
                    })
            
            # Log alerts
            for alert in alerts:
                if alert['severity'] == 'critical':
                    logger.error(f"CRITICAL ALERT: {alert['message']}")
                else:
                    logger.warning(f"ALERT: {alert['message']}")
            
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to check alerts: {e}")
            return []
    
    async def save_metrics(self, system_metrics: Dict[str, Any], app_metrics: Dict[str, Any]):
        """Save metrics to history."""
        try:
            combined_metrics = {
                'timestamp': datetime.now().isoformat(),
                'system': system_metrics,
                'application': app_metrics,
            }
            
            self.metrics_history.append(combined_metrics)
            
            # Keep only last 100 entries
            if len(self.metrics_history) > 100:
                self.metrics_history = self.metrics_history[-100:]
            
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get monitoring summary."""
        if not self.metrics_history:
            return {'error': 'No metrics available'}
        
        latest = self.metrics_history[-1]
        
        return {
            'status': 'healthy',
            'uptime': str(datetime.now() - self.start_time),
            'last_update': latest['timestamp'],
            'metrics_count': len(self.metrics_history),
            'latest_metrics': latest,
        }
    
    async def run_monitoring_cycle(self):
        """Run one monitoring cycle."""
        try:
            # Collect metrics
            system_metrics = await self.collect_system_metrics()
            app_metrics = await self.collect_application_metrics()
            
            # Check for alerts
            alerts = await self.check_alerts(system_metrics, app_metrics)
            
            # Save metrics
            await self.save_metrics(system_metrics, app_metrics)
            
            # Log summary
            if system_metrics and app_metrics:
                cpu = system_metrics.get('system', {}).get('cpu_percent', 0)
                memory = system_metrics.get('system', {}).get('memory_percent', 0)
                events = app_metrics.get('database', {}).get('recent_events_1h', 0)
                
                logger.info(f"System Status - CPU: {cpu:.1f}%, Memory: {memory:.1f}%, Events/1h: {events}")
            
            return len(alerts) == 0  # Return True if no alerts
            
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}")
            return False


async def main():
    """Main monitoring loop."""
    monitor = SystemMonitor()
    
    logger.info("Starting system monitoring...")
    logger.info(f"Alert thresholds: {monitor.alert_thresholds}")
    
    try:
        while True:
            healthy = await monitor.run_monitoring_cycle()
            
            if not healthy:
                logger.warning("System health check failed")
            
            # Wait before next cycle
            await asyncio.sleep(60)  # Monitor every minute
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Monitoring error: {e}")
    finally:
        # Print final summary
        summary = monitor.get_summary()
        logger.info(f"Monitoring summary: {json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
