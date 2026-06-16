"""
Enterprise Document Search System - Main Entry Point
Production-grade CLI interface and application launcher
"""

import click
import sys
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import get_config_manager, get_config
from core.logging_manager import setup_logging, get_logger
from core.constants import VERSION, SYSTEM_NAME


@click.group()
@click.version_option(version=VERSION, prog_name=SYSTEM_NAME)
def cli():
    """
    Enterprise Document Search System
    
    Production-grade document indexing and search platform
    """
    pass


@cli.command()
def check():
    """Check all required services are running before starting the system"""
    try:
        click.echo(f"\n{'='*80}")
        click.echo(f"{SYSTEM_NAME} v{VERSION}")
        click.echo("Service Health Check")
        click.echo(f"{'='*80}\n")
        
        config = get_config()
        all_ok = True
        
        # Check Tika instances
        import requests
        click.echo("Checking Tika instances...")
        tika_ok = 0
        for tika_inst in config.extraction.tika.instances:
            try:
                response = requests.get(
                    f"http://{tika_inst.host}:{tika_inst.port}/tika",
                    timeout=3
                )
                if response.status_code == 200:
                    click.secho(f"  ✓ Tika on port {tika_inst.port}: OK", fg='green')
                    tika_ok += 1
                else:
                    click.secho(f"  ✗ Tika on port {tika_inst.port}: HTTP {response.status_code}", fg='red')
                    all_ok = False
            except Exception as e:
                click.secho(f"  ✗ Tika on port {tika_inst.port}: Not running", fg='red')
                all_ok = False
        
        if tika_ok == 0:
            click.echo("\n  📝 To start Tika: cd bin && .\\start_tika.bat")
        
        # Check OpenSearch
        click.echo("\nChecking OpenSearch...")
        try:
            os_config = config.indexing.opensearch
            auth = (os_config.username, os_config.password) if os_config.username else None
            response = requests.get(
                os_config.hosts[0],
                auth=auth,
                verify=False,
                timeout=3
            )
            if response.status_code == 200:
                cluster_info = response.json()
                version = cluster_info.get('version', {}).get('number', 'unknown')
                click.secho(f"  ✓ OpenSearch {version}: OK", fg='green')
            else:
                click.secho(f"  ✗ OpenSearch: HTTP {response.status_code}", fg='red')
                all_ok = False
        except Exception as e:
            click.secho(f"  ✗ OpenSearch: Not running", fg='red')
            click.echo("\n  📝 To start OpenSearch: cd bin && .\\start_opensearch.bat")
            all_ok = False
        
        # Check Tesseract
        click.echo("\nChecking Tesseract OCR...")
        import subprocess
        try:
            result = subprocess.run(
                [config.ocr.tesseract.command, '--version'],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                click.secho(f"  ✓ {version_line}", fg='green')
            else:
                click.secho(f"  ✗ Tesseract check failed", fg='red')
                all_ok = False
        except Exception as e:
            click.secho(f"  ✗ Tesseract: Not found", fg='red')
            click.echo(f"  Configured path: {config.ocr.tesseract.command}")
            all_ok = False
        
        # Summary
        click.echo(f"\n{'='*80}")
        if all_ok:
            click.secho("✓ All services are running!", fg='green', bold=True)
            click.echo("\nYou can now run:")
            click.echo("  python src/main.py start")
        else:
            click.secho("✗ Some services are not running", fg='red', bold=True)
            click.echo("\nPlease start the required services before running the system.")
            click.echo("See the messages above for instructions.")
        click.echo(f"{'='*80}\n")
        
        return 0 if all_ok else 1
        
    except Exception as e:
        click.secho(f"\n✗ Check failed: {e}", fg='red', bold=True)
        import traceback
        traceback.print_exc()
        return 1


@cli.command()
@click.option('--config', default=None, help='Path to configuration file')
def init(config):
    """Initialize system: create directories, validate configuration, setup database"""
    try:
        click.echo(f"\n{'='*80}")
        click.echo(f"{SYSTEM_NAME} v{VERSION}")
        click.echo(f"Initialization")
        click.echo(f"{'='*80}\n")
        
        # Load configuration
        click.echo("Loading configuration...")
        config_manager = get_config_manager(config)
        system_config = config_manager.get_config()
        
        # Initialize logging
        click.echo("Initializing logging...")
        setup_logging()
        logger = get_logger("main")
        logger.info("System initialization started")
        
        # Create directories
        click.echo("Creating directory structure...")
        config_manager.ensure_directories()
        click.secho("✓ Directories created", fg='green')
        
        # Initialize queue database
        click.echo("Initializing queue database...")
        from core.queue_manager import get_queue_manager
        queue_manager = get_queue_manager()
        click.secho("✓ Queue database initialized", fg='green')
        
        # Validate services
        click.echo("\nValidating services...")
        
        # Check Tika instances
        import requests
        for tika_inst in system_config.extraction.tika.instances:
            try:
                response = requests.get(
                    f"http://{tika_inst.host}:{tika_inst.port}/tika",
                    timeout=5
                )
                if response.status_code == 200:
                    click.secho(f"✓ Tika instance on port {tika_inst.port} available", fg='green')
                else:
                    click.secho(f"✗ Tika instance on port {tika_inst.port} returned {response.status_code}", fg='red')
            except Exception as e:
                click.secho(f"✗ Tika instance on port {tika_inst.port} not accessible: {e}", fg='red')
        
        # Check OpenSearch
        try:
            os_config = system_config.indexing.opensearch
            auth = (os_config.username, os_config.password) if os_config.username else None
            response = requests.get(
                os_config.hosts[0],
                auth=auth,
                verify=False,
                timeout=5
            )
            if response.status_code == 200:
                click.secho(f"✓ OpenSearch available at {os_config.hosts[0]}", fg='green')
            else:
                click.secho(f"✗ OpenSearch returned {response.status_code}", fg='red')
        except Exception as e:
            click.secho(f"✗ OpenSearch not accessible: {e}", fg='red')
        
        # Check Tesseract
        import subprocess
        try:
            result = subprocess.run(
                [system_config.ocr.tesseract.command, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                click.secho(f"✓ Tesseract OCR available: {version_line}", fg='green')
            else:
                click.secho(f"✗ Tesseract OCR check failed", fg='red')
        except Exception as e:
            click.secho(f"✗ Tesseract OCR not accessible: {e}", fg='red')
        
        # Print configuration summary
        click.echo(f"\n{'='*80}")
        click.echo("Configuration Summary")
        click.echo(f"{'='*80}\n")
        config_manager.print_config_summary()
        
        click.secho(f"\n{'='*80}", fg='green')
        click.secho("✓ Initialization complete!", fg='green', bold=True)
        click.secho(f"{'='*80}\n", fg='green')
        
        logger.info("System initialization completed successfully")
        
    except Exception as e:
        click.secho(f"\n✗ Initialization failed: {e}", fg='red', bold=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--mode', type=click.Choice(['full', 'resume', 'incremental']), default='full',
              help='Operational mode')
def start(mode):
    """Start the document search system"""
    # Initialize logging before try block so logger is always available
    setup_logging()
    logger = get_logger("main")
    
    try:
        click.echo(f"\n{'='*80}")
        click.echo(f"{SYSTEM_NAME} v{VERSION}")
        click.echo(f"Starting in {mode.upper()} mode")
        click.echo(f"{'='*80}\n")
        
        logger.info(f"System starting in {mode} mode")
        
        # Import and start orchestrator
        click.echo("Starting master orchestrator...")
        from orchestrator.master_orchestrator import MasterOrchestrator
        
        orchestrator = MasterOrchestrator()
        
        click.secho("\n[OK] System started successfully", fg='green', bold=True)
        click.echo("\nPress Ctrl+C to stop gracefully\n")
        
        # Run orchestrator (blocks until shutdown)
        orchestrator.start(mode=mode)
        
        click.secho("\n[OK] System stopped gracefully", fg='green')
        
    except KeyboardInterrupt:
        click.echo("\n\nReceived shutdown signal...")
        logger.info("Shutdown signal received")
        click.secho("[OK] System stopped", fg='green')
    except Exception as e:
        click.secho(f"\n[ERROR] System error: {e}", fg='red', bold=True)
        logger.error(f"System error: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
def stop():
    """Stop the running system gracefully"""
    try:
        click.echo("Sending stop signal to running system...")
        
        # Send stop signal via API
        import requests
        config = get_config()
        
        response = requests.post(
            f"http://localhost:{config.api.port}/api/shutdown",
            headers={'Authorization': f'Bearer {config.api.api_token}'},
            timeout=5
        )
        
        if response.status_code == 200:
            click.secho("✓ Stop signal sent successfully", fg='green')
            click.echo("System will shutdown gracefully (60s grace period)")
        else:
            click.secho(f"✗ Failed to send stop signal: {response.status_code}", fg='red')
            
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg='red')
        click.echo("\nAlternative: Press Ctrl+C in the terminal running the system")


@cli.command()
def status():
    """Get current system status"""
    try:
        import requests
        config = get_config()
        
        response = requests.get(
            f"http://localhost:{config.api.port}/api/status",
            timeout=5
        )
        
        if response.status_code == 200:
            status = response.json()
            
            click.echo(f"\n{'='*80}")
            click.echo(f"System Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            click.echo(f"{'='*80}\n")
            
            click.echo(f"Status: {status.get('status', 'unknown').upper()}")
            click.echo(f"Mode: {status.get('mode', 'unknown')}")
            click.echo(f"Uptime: {status.get('uptime', 'unknown')}")
            
            if 'progress' in status:
                prog = status['progress']
                click.echo(f"\n Progress:")
                click.echo(f"  Discovered: {prog.get('discovered', 0):,}")
                click.echo(f"  Extracted:  {prog.get('extracted', 0):,}")
                click.echo(f"  Indexed:    {prog.get('indexed', 0):,}")
                click.echo(f"  OCR Pending: {prog.get('ocr_pending', 0):,}")
                click.echo(f"  OCR Complete: {prog.get('ocr_completed', 0):,}")
            
            if 'throughput' in status:
                tp = status['throughput']
                click.echo(f"\nThroughput:")
                click.echo(f"  Discovery: {tp.get('discovery_rate', 0):,.0f} files/sec")
                click.echo(f"  Extraction: {tp.get('extraction_rate', 0):,.0f} files/sec")
                click.echo(f"  Indexing: {tp.get('indexing_rate', 0):,.0f} docs/sec")
            
            if 'eta' in status:
                click.echo(f"\nEstimated Completion: {status['eta']}")
            
            click.echo(f"\n{'='*80}\n")
        else:
            click.secho(f"✗ Failed to get status: {response.status_code}", fg='red')
            
    except requests.exceptions.ConnectionError:
        click.secho("✗ System is not running", fg='red')
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg='red')


@cli.command()
def stats():
    """Get detailed statistics"""
    try:
        from core.queue_manager import get_queue_manager
        
        setup_logging()
        queue_manager = get_queue_manager()
        stats = queue_manager.get_queue_statistics()
        
        click.echo(f"\n{'='*80}")
        click.echo(f"Detailed Statistics - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"{'='*80}\n")
        
        # Discovery
        if 'discovery' in stats:
            d = stats['discovery']
            click.echo("Discovery:")
            click.echo(f"  Total:      {d.get('total', 0) or 0:,}")
            click.echo(f"  Pending:    {d.get('pending', 0) or 0:,}")
            click.echo(f"  Processing: {d.get('processing', 0) or 0:,}")
            click.echo(f"  Completed:  {d.get('completed', 0) or 0:,}")
            click.echo(f"  Failed:     {d.get('failed', 0) or 0:,}")
        
        # Extraction
        if 'extraction' in stats:
            click.echo("\nExtraction by Size Category:")
            for category, data in stats['extraction'].items():
                click.echo(f"  {category}:")
                click.echo(f"    Pending:    {data.get('pending', 0) or 0:,}")
                click.echo(f"    Processing: {data.get('processing', 0) or 0:,}")
                click.echo(f"    Completed:  {data.get('completed', 0) or 0:,}")
        
        # Indexing
        if 'indexing' in stats:
            i = stats['indexing']
            click.echo("\nIndexing:")
            click.echo(f"  Pending:    {i.get('pending', 0) or 0:,}")
            click.echo(f"  Processing: {i.get('processing', 0) or 0:,}")
            click.echo(f"  Completed:  {i.get('completed', 0) or 0:,}")
        
        # OCR
        if 'ocr' in stats:
            o = stats['ocr']
            click.echo("\nOCR:")
            click.echo(f"  Pending:    {o.get('pending', 0) or 0:,}")
            click.echo(f"  Processing: {o.get('processing', 0) or 0:,}")
            click.echo(f"  Completed:  {o.get('completed', 0) or 0:,}")
        
        # Completed
        if 'completed' in stats:
            c = stats['completed']
            click.echo("\nCompleted Files:")
            click.echo(f"  Total:         {c.get('total_completed', 0) or 0:,}")
            click.echo(f"  Duplicates:    {c.get('duplicates', 0) or 0:,}")
            avg_extract = c.get('avg_extraction_ms', 0) or 0
            avg_index = c.get('avg_indexing_ms', 0) or 0
            click.echo(f"  Avg Extract:   {avg_extract:.0f} ms")
            click.echo(f"  Avg Index:     {avg_index:.0f} ms")
        
        # Failures
        if 'failures' in stats and stats['failures']:
            click.echo(f"\nFailures ({stats.get('total_failures', 0) or 0:,} total):")
            for error_type, count in stats['failures'].items():
                click.echo(f"  {error_type}: {count or 0:,}")
        
        click.echo(f"\n{'='*80}\n")
        
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg='red')
        import traceback
        traceback.print_exc()


@cli.command()
@click.option('--force', is_flag=True, help='Force reset without confirmation')
def reset(force):
    """Reset system: clear all queues and data to start fresh"""
    try:
        click.echo(f"\n{'='*80}")
        click.echo("System Reset")
        click.echo(f"{'='*80}\n")
        
        if not force:
            click.secho("⚠ WARNING: This will delete ALL progress and queue data!", fg='yellow', bold=True)
            click.echo("The system will forget all processed files and re-index everything from scratch.")
            click.echo("This cannot be undone.")
            
            if not click.confirm("\nAre you sure you want to continue?"):
                click.echo("Reset cancelled.")
                return

        config = get_config()
        working_root = Path(config.paths.working_root)
        
        # 0. Kill any processes that might be holding database locks
        click.echo("Stopping processes that might hold database locks...")
        import subprocess
        processes_stopped = False
        try:
            # Try to kill streamlit processes more effectively
            result = subprocess.run(
                ['powershell', '-Command', 
                 'Get-Process | Where-Object {$_.ProcessName -like "*streamlit*"} | Stop-Process -Force -ErrorAction SilentlyContinue; '
                 '$LASTEXITCODE'],
                capture_output=True, timeout=10, text=True
            )
            processes_stopped = True
            click.echo("  Stopped related processes (if any were running)")
        except Exception as e:
            click.echo(f"  Note: Could not stop processes: {e}")
        
        # Small delay to allow file handles to be released
        import time
        time.sleep(1)
        
        # 1. Delete queue database directly (avoid SQLite locking issues)
        click.echo("Clearing queue database...")
        queue_dir = working_root / "queue"
        db_cleared = False
        if queue_dir.exists():
            for db_file in ["queues.db", "queues.db-wal", "queues.db-shm", "queues.db-journal"]:
                db_path = queue_dir / db_file
                if db_path.exists():
                    deleted = False
                    # Try multiple times with increasing delays
                    for attempt in range(3):
                        try:
                            import gc
                            gc.collect()
                            import time
                            time.sleep(0.5 * attempt)  # Increasing delay
                            db_path.unlink()
                            click.echo(f"  Deleted: {db_file}")
                            deleted = True
                            db_cleared = True
                            break
                        except PermissionError:
                            if attempt < 2:
                                continue
                            click.secho(f"  Warning: {db_file} is locked. Stop dashboard first.", fg='yellow')
                        except Exception as e:
                            click.secho(f"  Warning: Could not delete {db_file}: {e}", fg='yellow')
                            break
        
        if db_cleared:
            click.secho("✓ Queue database cleared", fg='green')
        else:
            click.secho("⚠ Queue database files locked", fg='yellow')
            click.echo("  Please close the dashboard (Streamlit) and try again:")
            click.echo("  1. Press Ctrl+C in the dashboard terminal")
            click.echo("  2. Or run: Get-Process *streamlit* | Stop-Process -Force")
            click.echo("  3. Then run: python src/main.py reset --force")
        
        # 1.5. Clear Redis database if using Redis
        click.echo("Checking Redis configuration...")
        try:
            import redis
            from core.redis_queue_manager import RedisQueueManager
            from core.config_manager import get_config_manager

            # Safely read raw config section for Redis (ConfigurationManager does not expose 'redis' in SystemConfig)
            cfg_mgr = get_config_manager()
            raw = getattr(cfg_mgr, 'raw_config', {}) or {}
            redis_section = raw.get('redis')

            if isinstance(redis_section, dict) and redis_section.get('url'):
                redis_url = redis_section.get('url')
                click.echo("Redis detected - clearing Redis database...")
                try:
                    redis_manager = RedisQueueManager(redis_url=redis_url)
                    redis_manager.reset_database()
                    click.secho("✓ Redis database cleared", fg='green')
                except Exception as redis_error:
                    if "connection" in str(redis_error).lower() or "refused" in str(redis_error).lower():
                        click.secho(f"  ⚠ Redis is not running (will be reset when started)", fg='yellow')
                    else:
                        click.secho(f"  Warning: Could not clear Redis: {redis_error}", fg='yellow')
            else:
                click.echo("  Redis not configured in config file. Attempting default Redis at redis://localhost:6379/0...")
                try:
                    # Try default Redis URL if present on system
                    redis_manager = RedisQueueManager()
                    redis_manager.reset_database()
                    click.secho("✓ Redis database cleared (default)", fg='green')
                except Exception as default_redis_error:
                    # If default Redis not running, skip silently
                    click.echo("  Default Redis not available, skipping Redis reset")
        except ImportError:
            click.echo("  Redis module not available, using SQLite mode")
        except Exception as e:
            click.secho(f"  Warning: Could not check Redis: {e}", fg='yellow')
        
        # 2. Clear Bloom filter files (important for re-discovery!)
        click.echo("Clearing Bloom filters...")
        discovery_dir = working_root / "discovery"
        if discovery_dir.exists():
            bloom_files = list(discovery_dir.glob("bloom_filter_*.pkl"))
            for bf in bloom_files:
                try:
                    bf.unlink()
                    click.echo(f"  Deleted: {bf.name}")
                except Exception as e:
                    click.secho(f"  Warning: Could not delete {bf.name}: {e}", fg='yellow')
            if bloom_files:
                click.secho(f"✓ Cleared {len(bloom_files)} Bloom filter files", fg='green')
            else:
                click.echo("  No Bloom filter files to clear")
        
        # 3. Clear ALL .pkl files in working directory (hash caches, etc.)
        click.echo("Clearing cache files...")
        pkl_count = 0
        for pkl_file in working_root.rglob("*.pkl"):
            try:
                pkl_file.unlink()
                pkl_count += 1
            except Exception:
                pass
        if pkl_count > 0:
            click.secho(f"✓ Cleared {pkl_count} cache files", fg='green')
        
        # 4. Clear checkpoints
        click.echo("Clearing checkpoints...")
        checkpoint_dir = working_root / "checkpoints"
        if checkpoint_dir.exists():
            checkpoint_files = list(checkpoint_dir.glob("checkpoint_*.json"))
            for cp in checkpoint_files:
                try:
                    cp.unlink()
                except Exception:
                    pass
            if checkpoint_files:
                click.secho(f"✓ Cleared {len(checkpoint_files)} checkpoint files", fg='green')
            else:
                click.echo("  No checkpoint files to clear")
        
        # 5. Clear OpenSearch index
        click.echo("Clearing OpenSearch index...")
        try:
            from opensearchpy import OpenSearch
            from opensearchpy.exceptions import ConnectionError as OSConnectionError
            os_config = config.indexing.opensearch
            
            # Parse hosts from config (list of URLs or host:port strings)
            hosts = []
            for host_str in os_config.hosts:
                if host_str.startswith('http'):
                    hosts.append(host_str)
                else:
                    parts = host_str.split(':')
                    host = parts[0]
                    port = int(parts[1]) if len(parts) > 1 else 9200
                    hosts.append({'host': host, 'port': port})
            
            client = OpenSearch(
                hosts=hosts,
                http_compress=True,
                timeout=5,
                max_retries=1
            )
            index_name = os_config.index_name
            if client.indices.exists(index=index_name):
                client.indices.delete(index=index_name)
                click.secho(f"✓ Deleted OpenSearch index: {index_name}", fg='green')
            else:
                click.echo(f"  OpenSearch index '{index_name}' does not exist")
        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower() or "refused" in error_msg.lower():
                click.secho(f"  ⚠ OpenSearch is not running (index will be recreated automatically)", fg='yellow')
                click.echo(f"  To start OpenSearch: cd bin && .\\start_opensearch.bat")
            else:
                click.secho(f"  Warning: Could not clear OpenSearch index: {e}", fg='yellow')
        
        # 6. Clear error logs (optional - fresh start)
        click.echo("Clearing old logs...")
        logs_dir = working_root / "logs"
        if logs_dir.exists():
            log_count = 0
            for log_file in logs_dir.glob("*.log"):
                try:
                    log_file.unlink()
                    log_count += 1
                except Exception:
                    pass
            if log_count > 0:
                click.secho(f"✓ Cleared {log_count} log files", fg='green')
        
        click.echo(f"\n{'='*80}")
        click.secho("✓ System reset complete!", fg='green', bold=True)
        click.echo("\nEverything has been cleared:")
        click.echo("  • Queue database (all file tracking)")
        click.echo("  • Bloom filters (duplicate detection)")
        click.echo("  • Cache files")
        click.echo("  • Checkpoints")
        click.echo("  • OpenSearch index (all indexed documents)")
        click.echo("  • Log files")
        click.echo("\nYou can now run 'python src/main.py start' to re-process everything.")
        click.echo(f"{'='*80}\n")
        
    except Exception as e:
        click.secho(f"✗ Reset failed: {e}", fg='red', bold=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--timeout-minutes', default=30, help='Timeout in minutes for stale items')
def reset_stale(timeout_minutes):
    """Reset stale processing items back to pending after crashes/shutdowns"""
    try:
        click.echo(f"\n{'='*80}")
        click.echo("Reset Stale Processing Items")
        click.echo(f"{'='*80}\n")
        
        from core.queue_manager import get_queue_manager
        queue_manager = get_queue_manager()
        
        # Reset stale items in each queue
        stale_timeout = timeout_minutes * 60  # Convert to seconds
        
        extraction_reset = queue_manager.reset_stale_processing(
            'extraction_queue', stale_timeout
        )
        indexing_reset = queue_manager.reset_stale_processing(
            'indexing_queue', stale_timeout
        )
        ocr_reset = queue_manager.reset_stale_processing(
            'ocr_queue', stale_timeout
        )
        
        if extraction_reset or indexing_reset or ocr_reset:
            click.secho("\nReset Summary:", fg='green')
            if extraction_reset:
                click.echo(f"  Extraction: {extraction_reset} items reset")
            if indexing_reset:
                click.echo(f"  Indexing: {indexing_reset} items reset")
            if ocr_reset:
                click.echo(f"  OCR: {ocr_reset} items reset")
        else:
            click.echo("No stale items found.")
        
        click.echo(f"\n{'='*80}\n")
        
    except Exception as e:
        click.secho(f"\n✗ Error: {e}", fg='red')
        import traceback
        traceback.print_exc()


@cli.command()
def validate():
    """Validate system configuration and dependencies"""
    try:
        click.echo(f"\n{'='*80}")
        click.echo("Configuration Validation")
        click.echo(f"{'='*80}\n")
        
        # Load configuration
        config_manager = get_config_manager()
        config = config_manager.get_config()
        
        issues = []
        warnings = []
        
        # Check Python version
        if sys.version_info < (3, 10):
            issues.append("Python 3.10+ required")
        else:
            click.secho(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}", fg='green')
        
        # Check source drive exists
        source_path = Path(config.paths.source_drive)
        if source_path.exists():
            click.secho(f"✓ Source drive exists: {config.paths.source_drive}", fg='green')
        else:
            issues.append(f"Source drive not found: {config.paths.source_drive}")
        
        # Check working root accessible
        working_root = Path(config.paths.working_root)
        if working_root.parent.exists():
            click.secho(f"✓ Working root parent accessible: {working_root.parent}", fg='green')
        else:
            issues.append(f"Working root parent not accessible: {working_root.parent}")
        
        # Check required Python packages
        required_packages = [
            'yaml', 'requests', 'opensearchpy', 'pytesseract',
            'PIL', 'cv2', 'mmh3', 'bitarray', 'fastapi', 'click'
        ]
        
        for package in required_packages:
            try:
                __import__(package)
                click.secho(f"✓ Package installed: {package}", fg='green')
            except ImportError:
                issues.append(f"Required package not installed: {package}")
        
        # Print summary
        click.echo(f"\n{'='*80}")
        if not issues and not warnings:
            click.secho("✓ Validation passed - no issues found!", fg='green', bold=True)
        else:
            if warnings:
                click.secho(f"\n⚠ Warnings ({len(warnings)}):", fg='yellow', bold=True)
                for warning in warnings:
                    click.secho(f"  • {warning}", fg='yellow')
            
            if issues:
                click.secho(f"\n✗ Issues ({len(issues)}):", fg='red', bold=True)
                for issue in issues:
                    click.secho(f"  • {issue}", fg='red')
                click.secho("\nPlease resolve issues before starting the system", fg='red')
        
        click.echo(f"{'='*80}\n")
        
    except Exception as e:
        click.secho(f"✗ Validation error: {e}", fg='red')
        import traceback
        traceback.print_exc()





@cli.command()
def health_check():
    """Check health of all services"""
    try:
        click.echo(f"\n{'='*80}")
        click.echo("Service Health Check")
        click.echo(f"{'='*80}\n")
        
        config = get_config()
        all_healthy = True
        
        # Check Tika instances
        import requests
        click.echo("Tika Instances:")
        for tika_inst in config.extraction.tika.instances:
            try:
                response = requests.get(
                    f"http://{tika_inst.host}:{tika_inst.port}/tika",
                    timeout=5
                )
                if response.status_code == 200:
                    click.secho(f"  ✓ Port {tika_inst.port}: Healthy", fg='green')
                else:
                    click.secho(f"  ✗ Port {tika_inst.port}: Unhealthy (HTTP {response.status_code})", fg='red')
                    all_healthy = False
            except Exception as e:
                click.secho(f"  ✗ Port {tika_inst.port}: Unreachable ({e})", fg='red')
                all_healthy = False
        
        # Check OpenSearch
        click.echo("\nOpenSearch:")
        try:
            os_config = config.indexing.opensearch
            auth = (os_config.username, os_config.password) if os_config.username else None
            response = requests.get(
                f"{os_config.hosts[0]}/_cluster/health",
                auth=auth,
                verify=False,
                timeout=5
            )
            if response.status_code == 200:
                health = response.json()
                status = health.get('status', 'unknown')
                if status == 'green':
                    click.secho(f"  ✓ Status: {status.upper()}", fg='green')
                elif status == 'yellow':
                    click.secho(f"  ⚠ Status: {status.upper()}", fg='yellow')
                    all_healthy = False
                else:
                    click.secho(f"  ✗ Status: {status.upper()}", fg='red')
                    all_healthy = False
            else:
                click.secho(f"  ✗ Unhealthy (HTTP {response.status_code})", fg='red')
                all_healthy = False
        except Exception as e:
            click.secho(f"  ✗ Unreachable ({e})", fg='red')
            all_healthy = False
        
        # Check Tesseract
        click.echo("\nTesseract OCR:")
        import subprocess
        try:
            result = subprocess.run(
                [config.ocr.tesseract.command, '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                click.secho(f"  ✓ Available", fg='green')
            else:
                click.secho(f"  ✗ Check failed", fg='red')
                all_healthy = False
        except Exception as e:
            click.secho(f"  ✗ Unreachable ({e})", fg='red')
            all_healthy = False
        
        # Summary
        click.echo(f"\n{'='*80}")
        if all_healthy:
            click.secho("✓ All services healthy", fg='green', bold=True)
        else:
            click.secho("✗ Some services unhealthy", fg='red', bold=True)
        click.echo(f"{'='*80}\n")
        
    except Exception as e:
        click.secho(f"✗ Health check error: {e}", fg='red')
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    cli()
