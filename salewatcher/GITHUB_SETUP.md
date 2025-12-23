# GitHub Repository Setup

Follow these steps to initialize the SaleWatcher repository on GitHub.

## Prerequisites

- GitHub account
- Git installed locally
- GitHub CLI (`gh`) installed (optional but recommended)

## Option 1: Using GitHub CLI (Recommended)

```bash
# Navigate to project directory
cd salewatcher

# Initialize git
git init

# Create GitHub repository and push
gh repo create salewatcher --private --source=. --remote=origin --push

# Verify
gh repo view --web
```

## Option 2: Manual Setup

### 1. Create Repository on GitHub

1. Go to https://github.com/new
2. Repository name: `salewatcher`
3. Description: `Predict retail sales from Milled.com newsletter data for Amazon OA`
4. Visibility: Private (recommended for personal use)
5. Do NOT initialize with README (we already have one)
6. Click "Create repository"

### 2. Initialize Local Repository

```bash
# Navigate to project directory
cd salewatcher

# Initialize git
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial project setup with documentation"

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/salewatcher.git

# Push to main branch
git branch -M main
git push -u origin main
```

## Post-Setup: Configure Branch Protection (Optional)

For solo development, this is optional but good practice:

1. Go to repository Settings → Branches
2. Add branch protection rule for `main`
3. Recommended settings:
   - Require pull request reviews: No (solo dev)
   - Require status checks: Yes (once CI is set up)
   - Require conversation resolution: No
   - Include administrators: No

## Install Beads

After repository is created, install beads for task tracking:

```bash
# Install beads CLI (macOS/Linux)
curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash

# Initialize beads in project
cd salewatcher
bd init

# Set project prefix
bd config set prefix sw-

# Verify installation
bd status
```

## Connect to Railway

1. Install Railway CLI: `npm install -g @railway/cli`
2. Login: `railway login`
3. Create project: `railway init`
4. Add PostgreSQL: `railway add postgres`
5. Link to GitHub: Done in Railway dashboard

## Connect to Vercel

1. Install Vercel CLI: `npm install -g vercel`
2. Login: `vercel login`
3. Link project: `cd dashboard && vercel link`
4. Configure: Set root directory to `dashboard` in Vercel dashboard

## Repository Structure After Setup

```
salewatcher/
├── .beads/                   # Beads issue tracking (created by bd init)
│   └── issues.jsonl
├── .git/                     # Git repository
├── .gitignore
├── README.md
├── CLAUDE.md
├── SKILLS.md
├── CLAUDE_CODE_KICKOFF.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── FUNCTIONAL_SPEC.md
│   └── PLAN.md
├── backend/                  # Created during Phase 0
│   ├── src/
│   ├── tests/
│   └── requirements.txt
└── dashboard/                # Created during Phase 0
    ├── src/
    └── package.json
```

## Next Steps

1. Open Claude Code in the `salewatcher` directory
2. Paste the contents of `CLAUDE_CODE_KICKOFF.md`
3. Let Claude Code read documentation and begin Phase 0
