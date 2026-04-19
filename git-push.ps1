# PowerShell Script to Push to GitHub
cd "C:\Users\reddy\Downloads\object_detection_project\object_detection_project"

# Update these if needed
$REPO_URL = "https://github.com/koushiksarun/traffic-violation-detection.git"

# Initialize and Add
git init
git add .
git commit -m "🚀 Initial deploy of Smart Traffic Violation System"

# Configure Remote and Push
git remote set-url origin $REPO_URL 2>$null
if ($LASTEXITCODE -ne 0) {
    git remote add origin $REPO_URL
}

git branch -M main
Write-Host "Please authenticate in the browser window that opens..." -ForegroundColor Cyan
git push -u origin main
