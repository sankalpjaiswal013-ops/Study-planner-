# PowerShell helper: initialize repo, commit all changes, and push to remote
# Usage: Open PowerShell in the repository root and run:
#    ./git_push.ps1 -RemoteName origin -BranchName upgrade-ai -CommitMessage "feat(ai): ..."

param(
    [string]$RemoteName = "origin",
    [string]$BranchName = "upgrade-ai",
    [string]$CommitMessage = "feat(ai): upgrade to google-genai SDK; add rotating logs, backend badges, tests, VIVA docs",
    [string]$RemoteUrl = "",
    [switch]$ForceInit
)

function Check-Git {
    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        Write-Error "Git is not installed or not on PATH. Please install Git and re-run this script."
        exit 1
    }
}

Check-Git

if (-not (Test-Path ".git") -or $ForceInit) {
    Write-Host "Initializing git repository..."
    git init
    if ($RemoteUrl -ne "") {
        git remote add $RemoteName $RemoteUrl
    }
}

# Create branch (or switch if exists)
$branchExists = (git branch --list $BranchName) -ne ""
if ($branchExists) {
    git checkout $BranchName
} else {
    git checkout -b $BranchName
}

# Stage and commit
git add -A
$changes = git status --porcelain
if (-not $changes) {
    Write-Host "No changes to commit."
} else {
    git commit -m "$CommitMessage"
}

# Push
if ($RemoteUrl -ne "") {
    git remote set-url $RemoteName $RemoteUrl
}

try {
    git push -u $RemoteName $BranchName
} catch {
    Write-Warning "Push failed. Check remote settings and credentials."
}
