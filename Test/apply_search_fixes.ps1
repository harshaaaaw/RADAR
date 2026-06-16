# Reset and Apply Search Fixes Script
# This script deletes the existing index to apply new mappings and restarts the system

Write-Host "⚠️  WARNING: This will DELETE the current search index to apply mapping fixes."
Write-Host "    All documents will need to be re-indexed."
Write-Host "    Press Ctrl+C to cancel, or any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# 1. Stop the system
Write-Host "`n🛑 Stopping Document Search System..."
python src/main.py stop

# 2. Delete the index
Write-Host "`n🗑️  Deleting old OpenSearch index..."
try {
    $response = Invoke-RestMethod -Uri "http://localhost:9200/enterprise_documents" -Method Delete -ErrorAction SilentlyContinue
    Write-Host "   Index deleted successfully."
} catch {
    Write-Host "   Index not found or already deleted."
}

# 3. Start the system (re-creates index with new settings)
Write-Host "`n🚀 Restarting System with Search Fixes..."
# We start in 'full' mode to trigger re-indexing
Start-Process python -ArgumentList "src/main.py", "start", "--mode", "full", "--config", "config/config_aws.yaml" -NoNewWindow

Write-Host "`n✅ System restarted! The index has been recreated with:"
Write-Host "   - Increased keyword limits (better Excel search)"
Write-Host "   - Nested field fixes (no more search errors)"
Write-Host "   - Improved text analysis (better accuracy)"
Write-Host "`nRe-indexing has begun. You can monitor progress with: python src/main.py status"
